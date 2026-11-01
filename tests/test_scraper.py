"""Tests for scraper.py using local HTML fixture (no network required)."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from formpilot.memory.schema import FieldType
from formpilot.scraper import extract_questions, is_last_page

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_form.html"


@pytest.fixture(scope="module")
def fixture_html() -> str:
    """Load fixture HTML once per module."""
    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def page(fixture_html):
    """Launch headless Chromium, load fixture HTML, yield Page."""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    p = context.new_page()
    p.set_content(fixture_html, wait_until="domcontentloaded")
    yield p
    browser.close()
    playwright.stop()


def test_extract_returns_six_questions(page) -> None:
    """Fixture has 6 questions; all should be extracted."""
    result = extract_questions(page, page_number=1)
    assert len(result.questions) == 6


def test_extract_short_text(page) -> None:
    """Q1 is SHORT_TEXT and required."""
    result = extract_questions(page)
    q = result.questions[0]
    assert q.field_type == FieldType.SHORT_TEXT
    assert "Nama lengkap" in q.text
    assert q.required is True


def test_extract_radio_with_options(page) -> None:
    """Q2 is RADIO with 3 options."""
    result = extract_questions(page)
    q = result.questions[1]
    assert q.field_type == FieldType.RADIO
    assert len(q.options) == 3
    assert "Teknik Informatika" in q.options


def test_extract_paragraph_required(page) -> None:
    """Q3 is PARAGRAPH and required."""
    result = extract_questions(page)
    q = result.questions[2]
    assert q.field_type == FieldType.PARAGRAPH
    assert q.required is True


def test_extract_checkbox(page) -> None:
    """Q4 is CHECKBOX with 3 options."""
    result = extract_questions(page)
    q = result.questions[3]
    assert q.field_type == FieldType.CHECKBOX
    assert len(q.options) == 3


def test_extract_linear_scale(page) -> None:
    """Q5 is LINEAR_SCALE (1-5)."""
    result = extract_questions(page)
    q = result.questions[4]
    assert q.field_type == FieldType.LINEAR_SCALE
    assert len(q.options) == 5


def test_has_media_detected(page) -> None:
    """Q6 has an image; has_media=True."""
    result = extract_questions(page)
    q = result.questions[5]
    assert q.has_media is True


def test_is_last_page_true(page) -> None:
    """Fixture has 'Kirim' button; is_last_page=True."""
    assert is_last_page(page) is True


def test_url_and_page_number_preserved(page) -> None:
    """ExtractedForm carries url and page_number."""
    result = extract_questions(page, page_number=3)
    assert result.page_number == 3
    assert isinstance(result.url, str)


# ---------------------------------------------------------------------------
# Regression tests for Sesi 3 known limitation: _is_required() bug
# ---------------------------------------------------------------------------


def test_required_detected_via_google_forms_asterisk_class() -> None:
    """Bug fix: _is_required() must detect Google Forms modern asterisk span."""
    html = """
    <!DOCTYPE html>
    <html><body>
      <div role="listitem">
        <div role="heading" aria-level="3">
          Pertanyaan wajib:
          <span class="freebirdFormviewerComponentsQuestionBaseRequiredAsterisk">*</span>
        </div>
        <input type="text" />
      </div>
      <div role="button">Kirim</div>
    </body></html>
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.set_content(html, wait_until="domcontentloaded")
        result = extract_questions(page)
        assert len(result.questions) == 1
        assert result.questions[0].required is True
    finally:
        browser.close()
        playwright.stop()


def test_required_detected_via_aria_label() -> None:
    """Bug fix: _is_required() must detect aria-label 'Wajib'."""
    html = """
    <!DOCTYPE html>
    <html><body>
      <div role="listitem">
        <div role="heading" aria-level="3">Pertanyaan?</div>
        <span aria-label="Wajib">*</span>
        <input type="text" />
      </div>
      <div role="button">Kirim</div>
    </body></html>
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.set_content(html, wait_until="domcontentloaded")
        result = extract_questions(page)
        assert len(result.questions) == 1
        assert result.questions[0].required is True
    finally:
        browser.close()
        playwright.stop()


def test_required_false_when_no_markers() -> None:
    """Non-required question should stay required=False."""
    html = """
    <!DOCTYPE html>
    <html><body>
      <div role="listitem">
        <div role="heading" aria-level="3">Pertanyaan opsional</div>
        <input type="text" />
      </div>
      <div role="button">Kirim</div>
    </body></html>
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.set_content(html, wait_until="domcontentloaded")
        result = extract_questions(page)
        assert result.questions[0].required is False
    finally:
        browser.close()
        playwright.stop()


# ---------------------------------------------------------------------------
# Regression test for Sesi 3 known limitation: total_pages_estimate always null
# ---------------------------------------------------------------------------


def test_total_pages_from_indonesian_text() -> None:
    """Bug fix: get_total_pages must parse 'Halaman X dari Y'."""
    html = """
    <!DOCTYPE html>
    <html><body>
      <div>Halaman 1 dari 5</div>
      <div role="listitem">
        <div role="heading" aria-level="3">Test?</div>
        <input type="text" />
      </div>
      <div role="button">Berikutnya</div>
    </body></html>
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.set_content(html, wait_until="domcontentloaded")
        result = extract_questions(page)
        assert result.total_pages_estimate == 5
    finally:
        browser.close()
        playwright.stop()


def test_total_pages_from_english_text() -> None:
    """Bug fix: get_total_pages must parse 'Page X of Y'."""
    html = """
    <!DOCTYPE html>
    <html><body>
      <div>Page 2 of 4</div>
      <div role="listitem">
        <div role="heading" aria-level="3">Test?</div>
        <input type="text" />
      </div>
      <div role="button">Next</div>
    </body></html>
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.set_content(html, wait_until="domcontentloaded")
        result = extract_questions(page)
        assert result.total_pages_estimate == 4
    finally:
        browser.close()
        playwright.stop()


def test_total_pages_none_when_not_present(page) -> None:
    """If no page indicator, total_pages_estimate should be None."""
    result = extract_questions(page)
    # sample_form.html has no page indicator
    assert result.total_pages_estimate is None
