"""Tests for multi-page navigation, submit, and validation detection."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from formpilot.memory.schema import FieldType
from formpilot.scraper import (
    click_next,
    click_submit,
    extract_questions,
    has_validation_error,
    is_last_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def multipage_html() -> str:
    path = FIXTURES / "sample_form_multipage.html"
    assert path.exists(), f"Missing fixture: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def validation_html() -> str:
    path = FIXTURES / "sample_form_validation.html"
    assert path.exists(), f"Missing fixture: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def page():
    """Fresh browser page per test."""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    p = context.new_page()
    yield p
    browser.close()
    playwright.stop()


# ---------------------------------------------------------------------------
# Multi-page navigation
# ---------------------------------------------------------------------------


def test_first_page_not_last(page, multipage_html) -> None:
    page.set_content(multipage_html, wait_until="domcontentloaded")
    assert is_last_page(page) is False


def test_click_next_succeeds(page, multipage_html) -> None:
    page.set_content(multipage_html, wait_until="domcontentloaded")
    page.fill("#q1-input", "Budi")
    assert click_next(page) is True


def test_navigate_three_pages(page, multipage_html) -> None:
    """Navigate from page 1 to 3 sequentially."""
    page.set_content(multipage_html, wait_until="domcontentloaded")

    # Page 1
    p1 = extract_questions(page, page_number=1)
    assert len(p1.questions) == 1
    assert p1.questions[0].field_type == FieldType.SHORT_TEXT
    assert p1.is_last_page is False

    # Click to page 2
    # Ensure button is ready
    page.wait_for_selector('div[role="button"]:has-text("Berikutnya")')
    page.fill("#q1-input", "Budi")
    assert click_next(page) is True
    p2 = extract_questions(page, page_number=2)
    assert len(p2.questions) == 1
    assert p2.questions[0].field_type == FieldType.RADIO

    # Click to page 3
    assert click_next(page) is True
    p3 = extract_questions(page, page_number=3)
    assert len(p3.questions) == 1
    assert p3.questions[0].field_type == FieldType.PARAGRAPH
    assert p3.is_last_page is True


def test_click_next_returns_false_on_last_page(page, multipage_html) -> None:
    """On page 3 (last), no Next button; only Submit."""
    page.set_content(multipage_html, wait_until="domcontentloaded")
    # Jump to last page directly
    page.evaluate("showPage(3)")
    assert click_next(page) is False


def test_click_submit_on_last_page(page, multipage_html) -> None:
    """Submit button works on last page."""
    page.set_content(multipage_html, wait_until="domcontentloaded")
    page.evaluate("showPage(3)")
    click_submit(page)
    # Verify marker set by JS
    assert page.locator('[data-submitted="true"]').count() == 1


def test_click_submit_raises_when_no_button(page, validation_html) -> None:
    """Validation fixture has no Submit button; click_submit should raise."""
    page.set_content(validation_html, wait_until="domcontentloaded")
    with pytest.raises(RuntimeError, match="No Submit button"):
        click_submit(page)


# ---------------------------------------------------------------------------
# Validation error detection
# ---------------------------------------------------------------------------


def test_no_validation_error_initially(page, validation_html) -> None:
    page.set_content(validation_html, wait_until="domcontentloaded")
    assert has_validation_error(page) is None


def test_validation_error_after_empty_submit(page, validation_html) -> None:
    """Clicking Next with empty required field shows alert."""
    page.set_content(validation_html, wait_until="domcontentloaded")
    page.locator('div[role="button"]:has-text("Berikutnya")').click()
    error = has_validation_error(page)
    assert error is not None
    assert "wajib" in error.lower() or "required" in error.lower()


def test_validation_cleared_after_fill(page, validation_html) -> None:
    """Fill required field, then validate → no error."""
    page.set_content(validation_html, wait_until="domcontentloaded")
    page.fill("#required-input", "Budi")
    page.locator('div[role="button"]:has-text("Berikutnya")').click()
    assert has_validation_error(page) is None


# ---------------------------------------------------------------------------
# New tests for filling and disabled button
# ---------------------------------------------------------------------------


def test_fill_short_text(page, multipage_html) -> None:
    """fill_answers fills SHORT_TEXT input."""
    from formpilot.memory.schema import Answer, FieldType, Question
    from formpilot.scraper import fill_answers

    page.set_content(multipage_html, wait_until="domcontentloaded")
    q = Question(index=0, text="Nama?", field_type=FieldType.SHORT_TEXT, required=True)
    a = Answer(question_index=0, value="Budi", source="llm", confidence=0.9)
    filled = fill_answers(page, [q], [a])
    assert filled == 1
    assert page.input_value("#q1-input") == "Budi"


def test_fill_radio(page, multipage_html) -> None:
    """fill_answers clicks matching radio option."""
    from formpilot.memory.schema import Answer, FieldType, Question
    from formpilot.scraper import fill_answers

    page.set_content(multipage_html, wait_until="domcontentloaded")
    page.evaluate("showPage(2)")  # Jump to page 2 with radio
    q = Question(index=0, text="Jurusan?", field_type=FieldType.RADIO, options=["TI", "SI"])
    a = Answer(question_index=0, value="SI", source="llm", confidence=0.9)
    filled = fill_answers(page, [q], [a])
    assert filled == 1


def test_fill_answers_sparse_indices():
    """Regression: fill_answers must use q.index, not positional zip.

    Bug: DOM with auxiliary listitems (headers) causes sparse q.index
    (0, 1, 5 with 6 DOM items). Positional zip paired Q5 answer with
    item[2] (auxiliary), causing fill timeout.
    """
    from formpilot.memory.schema import Answer, FieldType, Question
    from formpilot.scraper import fill_answers

    html = """
    <!DOCTYPE html><html><body>
      <div role="main">
        <div role="listitem">
          <div role="heading" aria-level="3">Q1?</div>
          <input type="text" id="q1" />
        </div>
        <div role="listitem">
          <!-- auxiliary: header (visible, no heading) -->
          <div style="width: 100px; height: 20px">Section</div>
        </div>
        <div role="listitem">
          <!-- auxiliary: image (visible, no heading) -->
          <div style="width: 100px; height: 20px">Banner</div>
        </div>
        <div role="listitem">
          <!-- auxiliary: spacer (visible, no heading) -->
          <div style="width: 100px; height: 20px">Spacer</div>
        </div>
        <div role="listitem">
          <div role="heading" aria-level="3">Q2?</div>
          <input type="text" id="q2" />
        </div>
      </div>
    </body></html>
    """

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.set_content(html, wait_until="domcontentloaded")
        # Questions have sparse indices 0 and 4 (matching DOM positions)
        qs = [
            Question(index=0, text="Q1?", field_type=FieldType.SHORT_TEXT),
            Question(index=4, text="Q2?", field_type=FieldType.SHORT_TEXT),
        ]
        ans = [
            Answer(question_index=0, value="A1", source="user", confidence=1.0),
            Answer(question_index=4, value="A2", source="user", confidence=1.0),
        ]
        filled = fill_answers(page, qs, ans)
        assert filled == 2
        assert page.input_value("#q1") == "A1"
        assert page.input_value("#q2") == "A2"
    finally:
        browser.close()
        playwright.stop()


def test_click_next_disabled_returns_false(page, multipage_html) -> None:
    """click_next returns False if button is disabled (no 30s timeout)."""
    page.set_content(multipage_html, wait_until="domcontentloaded")
    # Required field is empty → Next is disabled
    assert click_next(page) is False


def test_click_next_enabled_after_fill(page, multipage_html) -> None:
    """After filling required field, Next works."""
    page.set_content(multipage_html, wait_until="domcontentloaded")
    page.fill("#q1-input", "Budi")
    # JS should have enabled the button
    assert click_next(page) is True


def test_has_validation_error_disabled_button(page, multipage_html) -> None:
    """has_validation_error detects disabled Next button."""
    page.set_content(multipage_html, wait_until="domcontentloaded")
    error = has_validation_error(page)
    assert error is not None
    assert "disabled" in error.lower() or "required" in error.lower()
