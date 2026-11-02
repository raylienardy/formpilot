"""Playwright-based scraper for Google Forms.

Responsibilities:
- Open form URL
- Extract questions per page
- Fill answers into current page
- Navigate between pages (Next / Submit)
- Detect validation errors (both alert and disabled-button signals)
- Detect total page count from progress indicator

Non-responsibilities:
- LLM calls (brain.py)
- Memory storage (memory/, Fase 4)
- CLI loop for needs_cli (Fase 4)
"""

from __future__ import annotations

import contextlib
import re

from playwright.sync_api import Page, sync_playwright

from formpilot.memory.schema import Answer, ExtractedForm, FieldType, Question
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.scraper")

DEFAULT_TIMEOUT_MS = 30000
PAGE_TRANSITION_WAIT_MS = 600

_playwright = None
_browser = None


def open_form(url: str, headless: bool = True, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Page:
    """Launch browser and navigate to form URL.

    Uses stealth techniques to avoid Google Forms anti-bot detection:
    - Overrides navigator.webdriver
    - Prefers real Edge/Chrome over Playwright Chromium
    - Disables automation control feature flag
    - Realistic user agent + viewport
    """
    global _playwright, _browser

    logger.info("Opening form: %s (headless=%s)", url, headless)

    _playwright = sync_playwright().start()

    # Try real Edge/Chrome first (better fingerprint), fallback to Chromium
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
        ],
    }

    _browser = None
    for channel in ("msedge", "chrome", None):
        with contextlib.suppress(Exception):
            if channel:
                _browser = _playwright.chromium.launch(channel=channel, **launch_kwargs)
                logger.info("Launched real browser: %s", channel)
            else:
                _browser = _playwright.chromium.launch(**launch_kwargs)
                logger.info("Launched Playwright Chromium (fallback)")
            break

    if _browser is None:
        raise RuntimeError("Failed to launch any browser (msedge, chrome, chromium)")

    context = _browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        ),
        locale="id-ID",
        timezone_id="Asia/Jakarta",
    )

    # Mask automation fingerprints
    context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['id-ID', 'id', 'en-US', 'en'],
        });
        window.chrome = window.chrome || { runtime: {} };
        """
    )

    page = context.new_page()
    page.set_default_timeout(timeout_ms)
    page.goto(url, wait_until="networkidle", timeout=timeout_ms)

    logger.info("Form loaded: %s", page.title())

    # Verify stealth worked
    webdriver = page.evaluate("() => navigator.webdriver")
    if webdriver:
        logger.warning(
            "navigator.webdriver still exposed (%r). Anti-bot may still trigger.",
            webdriver,
        )
    else:
        logger.info("Stealth active: navigator.webdriver is undefined")

    return page


def extract_questions(page: Page, page_number: int = 1) -> ExtractedForm:
    """Extract questions from current page."""
    logger.debug("Extracting questions from page %d", page_number)

    items = [item for item in page.locator('div[role="listitem"]').all() if item.is_visible()]
    questions: list[Question] = []

    for idx, item in enumerate(items):
        text = _extract_question_text(item)
        if not text:
            continue

        field_type, options = _detect_field_type(item)
        required = _is_required(item)
        has_media = _has_media(item)

        questions.append(
            Question(
                index=idx,
                text=text,
                field_type=field_type,
                options=options,
                required=required,
                has_media=has_media,
            )
        )

    extracted = ExtractedForm(
        url=page.url,
        page_number=page_number,
        total_pages_estimate=get_total_pages(page),
        questions=questions,
        is_last_page=is_last_page(page),
    )

    logger.info(
        "Extracted %d questions (last_page=%s, total_pages=%s)",
        len(questions),
        extracted.is_last_page,
        extracted.total_pages_estimate,
    )
    return extracted


def fill_answers(page: Page, questions: list[Question], answers: list[Answer]) -> int:
    """Fill answers into current page. Skip needs_cli=True or empty values.

    Returns: number of fields successfully filled.
    """
    items = [item for item in page.locator('div[role="listitem"]').all() if item.is_visible()]
    if len(items) != len(questions):
        logger.warning(
            "Item count mismatch: %d DOM items, %d questions",
            len(items),
            len(questions),
        )

    filled = 0
    for item, q, a in zip(items, questions, answers, strict=False):
        if a.needs_cli or not a.value:
            logger.debug("Skip Q%d (needs_cli=%s, value=%r)", q.index, a.needs_cli, a.value)
            continue
        try:
            _fill_single(item, q, a.value)
            filled += 1
            logger.debug("Filled Q%d with %r", q.index, a.value[:50])
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to fill Q%d: %s", q.index, e)

    logger.info("Filled %d/%d fields", filled, len(questions))
    return filled


def click_next(page: Page) -> bool:
    """Click Next button. Returns False if button missing OR disabled."""
    next_btn = page.locator(
        'div[role="button"]:has-text("Berikutnya"), '
        'div[role="button"]:has-text("Next"), '
        'div[role="button"]:has-text("Lanjutkan"), '
        'div[role="button"]:has-text("Continue")'
    ).filter(visible=True)

    if next_btn.count() == 0:
        logger.debug("No Next button (last page?)")
        return False

    # NEW: detect disabled state (required field empty)
    disabled = next_btn.first.get_attribute("aria-disabled")
    if disabled == "true":
        logger.warning(
            "Next button is disabled — required field(s) likely empty. "
            "Cannot proceed without filling them."
        )
        return False

    logger.debug("Clicking Next")
    next_btn.first.click()

    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=2000)
    page.wait_for_timeout(PAGE_TRANSITION_WAIT_MS)
    return True


def click_submit(page: Page) -> None:
    """Click Submit button."""
    submit_btn = page.locator(
        'div[role="button"]:has-text("Kirim"), '
        'div[role="button"]:has-text("Submit"), '
        'div[role="button"]:has-text("Send")'
    ).filter(visible=True)

    if submit_btn.count() == 0:
        raise RuntimeError("No Submit button on this page")

    if submit_btn.first.get_attribute("aria-disabled") == "true":
        raise RuntimeError("Submit button is disabled — required field(s) empty")

    logger.info("Clicking Submit")
    submit_btn.first.click()
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=5000)


def has_validation_error(page: Page) -> str | None:
    """Check for validation error after clicking Next.

    Two signals:
    1. role="alert" elements with error text
    2. Next button is disabled (indicates required field empty)
    """
    # Signal 1: alert text
    alerts = page.locator('div[role="alert"]').all()
    for alert in alerts:
        if alert.is_visible():
            msg = alert.inner_text().strip()
            if msg:
                logger.warning("Validation error (alert): %s", msg[:100])
                return msg

    # Fallback: search common error text
    error_patterns = [
        "This is a required question",
        "Pertanyaan ini wajib diisi",
        "Wajib diisi",
        "Required question",
    ]
    for pattern in error_patterns:
        locator = page.locator(f'text="{pattern}"')
        if locator.count() > 0 and locator.first.is_visible():
            return pattern

    # Signal 2: Next button disabled
    next_btn = page.locator(
        'div[role="button"]:has-text("Berikutnya"), div[role="button"]:has-text("Next")'
    ).filter(visible=True)
    if next_btn.count() > 0 and next_btn.first.get_attribute("aria-disabled") == "true":
        return "Next button disabled — required field(s) empty"

    return None


def get_total_pages(page: Page) -> int | None:
    """Parse 'Halaman X dari Y', 'Bagian X dari Y', 'Page X of Y', 'Section X of Y'."""
    patterns = [
        r"Halaman\s+\d+\s+dari\s+(\d+)",
        r"Bagian\s+\d+\s+dari\s+(\d+)",
        r"Page\s+\d+\s+of\s+(\d+)",
        r"Section\s+\d+\s+of\s+(\d+)",
    ]
    body_text = page.locator("body").inner_text()

    for pattern in patterns:
        match = re.search(pattern, body_text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None


def is_last_page(page: Page) -> bool:
    """Check if Submit button is present and visible."""
    submit = page.locator(
        'div[role="button"]:has-text("Kirim"), '
        'div[role="button"]:has-text("Submit"), '
        'div[role="button"]:has-text("Send")'
    ).filter(visible=True)
    return submit.count() > 0


def close(page: Page | None = None) -> None:
    """Close browser and stop Playwright."""
    global _playwright, _browser

    if _browser is not None:
        try:
            _browser.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Error closing browser: %s", e)
        _browser = None

    if _playwright is not None:
        try:
            _playwright.stop()
        except Exception as e:  # noqa: BLE001
            logger.warning("Error stopping playwright: %s", e)
        _playwright = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_question_text(item) -> str:
    heading = item.locator('div[role="heading"]').first
    if heading.count() == 0:
        return ""
    raw = heading.inner_text().strip()
    for marker in ["\n*", " *", "*\n", "Wajib", "Required"]:
        raw = raw.replace(marker, "")
    raw = raw.rstrip("*").strip()
    return raw


def _detect_field_type(item) -> tuple[FieldType, list[str]]:
    if item.locator("textarea").count() > 0:
        return FieldType.PARAGRAPH, []

    if item.locator('input[type="text"]').count() > 0:
        return FieldType.SHORT_TEXT, []

    radio_group = item.locator('div[role="radiogroup"]')
    if radio_group.count() > 0:
        options = _extract_options_from_group(radio_group.first, role="radio")
        if 5 <= len(options) <= 11 and all(_looks_like_scale(o) for o in options):
            return FieldType.LINEAR_SCALE, options
        return FieldType.RADIO, options

    checkbox_group = item.locator('div[role="group"]')
    if checkbox_group.count() > 0 and item.locator('div[role="checkbox"]').count() > 0:
        options = _extract_options_from_group(checkbox_group.first, role="checkbox")
        return FieldType.CHECKBOX, options

    if item.locator('div[role="listbox"]').count() > 0:
        return FieldType.DROPDOWN, []

    return FieldType.UNKNOWN, []


def _extract_options_from_group(group, role: str) -> list[str]:
    options: list[str] = []
    for opt in group.locator(f'div[role="{role}"]').all():
        label = opt.get_attribute("aria-label") or opt.inner_text().strip()
        if label:
            options.append(label)
    return options


def _looks_like_scale(option: str) -> bool:
    stripped = option.strip()
    if stripped.isdigit():
        return True
    return len(stripped) < 20


def _is_required(item) -> bool:
    if item.locator(".freebirdFormviewerComponentsQuestionBaseRequiredAsterisk").count() > 0:
        return True
    if item.locator('[aria-label*="Wajib"], [aria-label*="Required"]').count() > 0:
        return True
    heading = item.locator('div[role="heading"]').first
    return bool(heading.count() > 0 and "*" in heading.inner_text())


def _has_media(item) -> bool:
    return item.locator("img, video").count() > 0


def _fill_single(item, q: Question, value: str, timeout_ms: int = 3000) -> None:
    """Fill a single field based on type.

    Fails fast (3s timeout) if field is disabled. Logs diagnostic info.
    """
    if q.field_type == FieldType.SHORT_TEXT:
        inp = item.locator('input[type="text"]').first
        if inp.is_disabled():
            attrs = inp.evaluate(
                "el => ({disabled: el.disabled, ariaDisabled: el.getAttribute('aria-disabled'), "
                "readOnly: el.readOnly, required: el.required, visible: el.offsetParent !== null})"
            )
            logger.warning(
                "Q%d input DISABLED. attrs=%s. "
                "Google Forms may be anti-botting or form has special config.",
                q.index,
                attrs,
            )
            raise ValueError(f"Q{q.index} input disabled")
        inp.fill(value, timeout=timeout_ms)
        return

    if q.field_type == FieldType.PARAGRAPH:
        ta = item.locator("textarea").first
        if ta.is_disabled():
            raise ValueError(f"Q{q.index} textarea disabled")
        ta.fill(value, timeout=timeout_ms)
        return

    if q.field_type in (FieldType.RADIO, FieldType.LINEAR_SCALE):
        opt = _find_option(item, "radio", value)
        opt.click(timeout=timeout_ms)
        return

    if q.field_type == FieldType.CHECKBOX:
        for opt_value in [s.strip() for s in value.split(",") if s.strip()]:
            opt = _find_option(item, "checkbox", opt_value)
            opt.click(timeout=timeout_ms)
        return

    if q.field_type == FieldType.DROPDOWN:
        raise NotImplementedError("Dropdown filling: Fase 4")

    raise ValueError(f"Unsupported field type: {q.field_type}")


def _find_option(item, role: str, value: str):
    """Find radio/checkbox option by aria-label or text."""
    # Try aria-label exact
    by_aria = item.locator(f'div[role="{role}"][aria-label="{value}"]')
    if by_aria.count() > 0:
        return by_aria.first
    # Try text match
    by_text = item.locator(f'div[role="{role}"]').filter(
        has_text=re.compile(rf"^{re.escape(value)}$")
    )
    if by_text.count() > 0:
        return by_text.first
    raise ValueError(f"Option {value!r} not found (role={role})")
