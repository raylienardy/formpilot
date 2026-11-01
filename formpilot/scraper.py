"""Playwright-based scraper for Google Forms.

Responsibilities:
- Open form URL
- Extract questions per page (Google Forms has multiple pages)
- Detect field types (short text, paragraph, radio, checkbox, dropdown, linear scale)
- Detect whether current page is the last page
- Detect questions with media (image/video)

Non-responsibilities:
- Filling answers (Fase 2+)
- Clicking Next/Submit (Fase 2+)
- Calling Ollama (brain.py)
- Reading/writing memory (memory/)
"""

from __future__ import annotations

from playwright.sync_api import Page, sync_playwright

from formpilot.memory.schema import ExtractedForm, FieldType, Question
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.scraper")

DEFAULT_TIMEOUT_MS = 30000

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

    Google Forms DOM structure (as of 2026):
    - Each question is in `div[role="listitem"]`
    - Question text is in `div[role="heading"][aria-level="3"]`
    - Field type detected by child elements

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
        questions=questions,
        is_last_page=is_last_page(page),
    )

    logger.info(
        "Extracted %d questions (last_page=%s)",
        len(questions),
        extracted.is_last_page,
    )
    return extracted


def is_last_page(page: Page) -> bool:
    """Check whether Submit button is present on this page.

    Google Forms shows 'Kirim' (Indonesian) or 'Submit' (English)
    on the last page, and 'Berikutnya'/'Next' on earlier pages.
    """
    submit = page.locator(
        'div[role="button"]:has-text("Kirim"), '
        'div[role="button"]:has-text("Submit"), '
        'div[role="button"]:has-text("Send")'
    )
    return submit.count() > 0 and submit.first.is_visible()


def close(page: Page | None = None) -> None:
    """Close browser and stop Playwright.

    Safe to call multiple times. Pass page for API symmetry;
    actual cleanup uses module-level globals.
    """
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
    raw = heading.inner_text().strip()
    # Google Forms appends "*" for required or "Wajib" marker
    for marker in ["\n*", " *", "Wajib", "Required"]:
        raw = raw.replace(marker, "")
    return raw.strip()


def _detect_field_type(item) -> tuple[FieldType, list[str]]:
    """Inspect DOM inside item to detect field type + options."""
    # Paragraph (multi-line)
    if item.locator("textarea").count() > 0:
        return FieldType.PARAGRAPH, []

    # Short text
    if item.locator('input[type="text"]').count() > 0:
        return FieldType.SHORT_TEXT, []

    # Radio / Linear Scale (both use role="radiogroup")
    radio_group = item.locator('div[role="radiogroup"]')
    if radio_group.count() > 0:
        options = _extract_options_from_group(radio_group.first, role="radio")
        # Heuristic: linear scale has 5-11 short numeric options (1-5, 1-10)
        if 5 <= len(options) <= 11 and all(_looks_like_scale(o) for o in options):
            return FieldType.LINEAR_SCALE, options
        return FieldType.RADIO, options

    # Checkbox
    checkbox_group = item.locator('div[role="group"]')
    if checkbox_group.count() > 0:
        checkboxes = item.locator('div[role="checkbox"]')
        if checkboxes.count() > 0:
            options = _extract_options_from_group(checkbox_group.first, role="checkbox")
            return FieldType.CHECKBOX, options

    # Dropdown (listbox)
    if item.locator('div[role="listbox"]').count() > 0:
        return FieldType.DROPDOWN, []  # options load on click; not extractable statically

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
    """True if option looks like a scale point (1, 2, 3, 'Sangat Setuju', etc)."""
    stripped = option.strip()
    if stripped.isdigit():
        return True
    # Short labels are typical for scales
    return len(stripped) < 20


def _is_required(item) -> bool:
    """Check if question is marked required."""
    # Method 1: aria-label="Wajib" on question text
    if item.locator('[aria-label*="Wajib"], [aria-label*="Required"]').count() > 0:
        return True
    # Method 2: asterisk in heading text
    heading = item.locator('div[role="heading"]').first
    return bool(heading.count() > 0 and "*" in heading.inner_text())


def _has_media(item) -> bool:
    """Check if question contains image or video."""
    return item.locator("img, video").count() > 0
