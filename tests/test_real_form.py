"""Integration test that verifies input can actually be filled on real Google Form.

SKIP by default. Run manually with:
    pytest tests/test_real_form.py -v -s
Only run when you have a known-test-form URL in env var TEST_FORM_URL.
"""

from __future__ import annotations

import os

import pytest

from formpilot.scraper import close, extract_questions, open_form

TEST_FORM_URL = os.environ.get("TEST_FORM_URL", "")


@pytest.mark.integration
@pytest.mark.skipif(not TEST_FORM_URL, reason="TEST_FORM_URL not set")
def test_real_form_input_not_disabled():
    """Regression test: input field must NOT be disabled on real Google Form."""
    page = open_form(TEST_FORM_URL, headless=True)
    try:
        extracted = extract_questions(page)
        assert len(extracted.questions) >= 1, "No questions extracted"

        # Find first text input
        text_input = page.locator('input[type="text"]').first
        if text_input.count() > 0:
            disabled = text_input.get_attribute("disabled")
            aria_disabled = text_input.get_attribute("aria-disabled")
            assert disabled is None, f"Input disabled (attr): {disabled}"
            assert aria_disabled != "true", f"Input disabled (aria): {aria_disabled}"

            # Try to actually fill
            text_input.fill("test", timeout=3000)
            assert text_input.input_value() == "test"
    finally:
        close(page)
