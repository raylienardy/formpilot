"""Playwright-based scraper for Google Forms.

Responsibilities:
- Open form URL
- Extract questions per page (Google Forms has multiple pages)
- Detect field types (short text, paragraph, radio, checkbox, dropdown, linear scale)
- Navigate between pages (Next / Submit)
- Detect validation errors
- Detect whether current page is the last page
- Detect total page count from progress indicator

Non-responsibilities:
- Filling answers (Fase 2+ / Fase 4+)
- Calling Ollama (brain.py)
- Reading/writing memory (memory/)
"""

from __future__ import annotations

import re
from contextlib import suppress

from playwright.sync_api import Page, sync_playwright

from formpilot.memory.schema import ExtractedForm, FieldType, Question
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.scraper")

DEFAULT_TIMEOUT_MS = 30000
PAGE_TRANSITION_WAIT_MS = 600  # wait after clicking Next, for DOM update

# Module-level singletons; managed by open_form() / close()
_playwright = None
_browser = None


def open_form(url: str, headless: bool = True, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Page:
    """Launch browser and navigate to form URL.

    Args:
        url: Google Forms URL.
        headless: Run browser without UI (True) or visible (False).
        timeout_ms: Page navigation timeout.

    Returns:
        Playwright Page object. Must be closed via close(page).

    Raises:
        playwright.sync_api.TimeoutError: If page doesn't load within timeout.
    """
    global _playwright, _browser

    logger.info("Opening form: %s (headless=%s)", url, headless)

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=headless)
    context = _browser.new_context()
    page = context.new_page()
    page.set_default_timeout(timeout_ms)
    page.goto(url, wait_until="networkidle", timeout=timeout_ms)

    logger.info("Form loaded: %s", page.title())
    return page


def extract_questions(page: Page, page_number: int = 1) -> ExtractedForm:
    """Extract questions from current page.

    Args:
        page: Playwright Page with form loaded.
        page_number: Current page number (1-indexed).

    Returns:
        ExtractedForm with all questions on this page.
    """
    logger.debug("Extracting questions from page %d", page_number)

    items = page.locator('div[role="listitem"]').all()
    questions: list[Question] = []

    for idx, item in enumerate(items):
        if not item.is_visible():
            logger.debug("Skipping listitem %d: not visible", idx)
            continue

        text = _extract_question_text(item)
        if not text:
            logger.debug("Skipping listitem %d: empty text", idx)
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
        logger.debug(
            "  [%d] %s (type=%s, options=%d, required=%s)",
            idx,
            text[:50],
            field_type.value,
            len(options),
            required,
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


def click_next(page: Page) -> bool:
    """Click 'Next' button and wait for page transition.

    Returns:
        True if Next button was found and clicked successfully.
        False if no Next button (meaning we're on the last page).
    """
    next_btns = page.locator(
        'div[role="button"]:has-text("Berikutnya"), '
        'div[role="button"]:has-text("Next"), '
        'div[role="button"]:has-text("Lanjutkan"), '
        'div[role="button"]:has-text("Continue")'
    ).all()

    visible_btn = None
    for btn in next_btns:
        if btn.is_visible():
            visible_btn = btn
            break

    if visible_btn is None:
        logger.debug("No visible Next button found (last page?)")
        return False

    logger.debug("Clicking Next")
    visible_btn.click()

    # Wait for DOM to settle. Try networkidle first (for real forms),
    # fall back to timeout (for JS-only pages like test fixtures).
    with suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=2000)
    page.wait_for_timeout(PAGE_TRANSITION_WAIT_MS)

    logger.debug("Page transition complete")
    return True


def click_submit(page: Page) -> None:
    """Click Submit button. Does not verify successful submission."""
    submit_btns = page.locator(
        'div[role="button"]:has-text("Kirim"), '
        'div[role="button"]:has-text("Submit"), '
        'div[role="button"]:has-text("Send")'
    ).all()

    visible_btn = None
    for btn in submit_btns:
        if btn.is_visible():
            visible_btn = btn
            break

    if visible_btn is None:
        raise RuntimeError("No Submit button found on this page")

    logger.info("Clicking Submit")
    visible_btn.click()
    with suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=5000)


def has_validation_error(page: Page) -> str | None:
    """Check if form shows a validation error after clicking Next.

    Returns:
        Error message string if found, None otherwise.
    """
    alerts = page.locator('div[role="alert"]').all()
    for alert in alerts:
        if alert.is_visible():
            msg = alert.inner_text().strip()
            if msg:
                logger.warning("Validation error detected: %s", msg[:100])
                return msg

    # Fallback: search for common error text
    error_patterns = [
        "This is a required question",
        "Pertanyaan ini wajib diisi",
        "Wajib diisi",
        "Required question",
    ]
    for pattern in error_patterns:
        locator = page.locator(f'text="{pattern}"')
        if locator.count() > 0 and locator.first.is_visible():
            logger.warning("Validation error text found: %s", pattern)
            return pattern

    return None


def get_total_pages(page: Page) -> int | None:
    """Estimate total page count from 'Page X of Y' or 'Halaman X dari Y' text.

    Returns:
        Total page count, or None if not detectable.
    """
    patterns = [
        r"Halaman\s+\d+\s+dari\s+(\d+)",
        r"Page\s+\d+\s+of\s+(\d+)",
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
    """Check whether Submit button is present on this page."""
    submit_btns = page.locator(
        'div[role="button"]:has-text("Kirim"), '
        'div[role="button"]:has-text("Submit"), '
        'div[role="button"]:has-text("Send")'
    ).all()
    return any(btn.is_visible() for btn in submit_btns)


def close(page: Page | None = None) -> None:
    """Close browser and stop Playwright. Safe to call multiple times."""
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

    logger.debug("Browser closed")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_question_text(item) -> str:
    """Extract clean question text, removing 'Wajib' / '*' markers."""
    heading = item.locator('div[role="heading"]').first
    if heading.count() == 0:
        return ""

    # Note: can't easily delete DOM nodes via locator; use text extraction with fallback
    # Google Forms modern asterisk class and aria-labels are handled by _is_required()

    raw = heading.inner_text().strip()
    # Strip trailing markers
    for marker in ["\n*", " *", "*\n", "Wajib", "Required"]:
        raw = raw.replace(marker, "")
    raw = raw.rstrip("*").strip()
    return raw


def _detect_field_type(item) -> tuple[FieldType, list[str]]:
    """Inspect DOM inside item to detect field type + options."""
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
    if checkbox_group.count() > 0:
        checkboxes = item.locator('div[role="checkbox"]')
        if checkboxes.count() > 0:
            options = _extract_options_from_group(checkbox_group.first, role="checkbox")
            return FieldType.CHECKBOX, options

    if item.locator('div[role="listbox"]').count() > 0:
        return FieldType.DROPDOWN, []

    return FieldType.UNKNOWN, []


def _extract_options_from_group(group, role: str) -> list[str]:
    """Extract option labels from a radiogroup or checkbox group."""
    options: list[str] = []
    opts = group.locator(f'div[role="{role}"]').all()
    for opt in opts:
        label = opt.get_attribute("aria-label") or opt.inner_text().strip()
        if label:
            options.append(label)
    return options


def _looks_like_scale(option: str) -> bool:
    """True if option looks like a scale point."""
    stripped = option.strip()
    if stripped.isdigit():
        return True
    return len(stripped) < 20


def _is_required(item) -> bool:
    """Check if question is marked required.

    Handles Google Forms modern + older variants:
    - Spans with class 'freebirdFormviewerComponentsQuestionBaseRequiredAsterisk'
    - aria-label 'Wajib' or 'Required'
    - Asterisk '*' in heading text
    """
    # Method 1: Google Forms required asterisk class
    asterisk = item.locator(".freebirdFormviewerComponentsQuestionBaseRequiredAsterisk")
    if asterisk.count() > 0:
        return True

    # Method 2: aria-label containing Wajib/Required
    aria_required = item.locator('[aria-label*="Wajib"], [aria-label*="Required"]')
    if aria_required.count() > 0:
        return True

    # Method 3: Asterisk in heading text
    heading = item.locator('div[role="heading"]').first
    if heading.count() > 0:
        heading_text = heading.inner_text().strip()
        if heading_text.endswith("*") or "*" in heading_text:
            return True

    return False


def _has_media(item) -> bool:
    """Check if question contains image or video."""
    return item.locator("img, video").count() > 0
