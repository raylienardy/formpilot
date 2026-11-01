"""Temporary CLI prototype for Fase 1+2.

Usage:
    python -m formpilot --url "https://docs.google.com/forms/d/e/..." [--headed]

Extracts questions from all pages and prints as JSON.
This file will be replaced by full cli.py in Fase 5.
"""

from __future__ import annotations

import argparse
import json
import sys

from formpilot.scraper import (
    click_next,
    close,
    extract_questions,
    has_validation_error,
    open_form,
)
from formpilot.utils.logger import get_logger, setup_logger

MAX_PAGES = 50  # safety limit against infinite loop


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FormPilot prototype: extract questions from a Google Form (multi-page)",
    )
    parser.add_argument("--url", required=True, help="Google Forms URL")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser with UI (default: headless)",
    )
    args = parser.parse_args()

    setup_logger("formpilot", level="INFO")
    logger = get_logger("formpilot.__main__")

    page = None
    try:
        page = open_form(args.url, headless=not args.headed)

        all_pages: list[dict] = []
        page_number = 1
        previous_question_texts: list[str] = []

        while page_number <= MAX_PAGES:
            extracted = extract_questions(page, page_number=page_number)
            all_pages.append(extracted.model_dump(mode="json"))

            # Branching detection: warn if new page has identical questions to previous
            current_texts = [q.text for q in extracted.questions]
            if page_number > 1 and current_texts == previous_question_texts:
                logger.warning(
                    "Page %d has identical questions to previous page — "
                    "possible branching issue or navigation failure",
                    page_number,
                )
            previous_question_texts = current_texts

            if extracted.is_last_page:
                logger.info("Reached last page (%d)", page_number)
                break

            # Check validation error BEFORE clicking next
            # (validation errors typically appear after clicking next)
            if not click_next(page):
                logger.warning("No Next button — stopping at page %d", page_number)
                break

            # After click, check for validation error
            error = has_validation_error(page)
            if error:
                logger.error(
                    "Validation error on page %d: %s — cannot proceed",
                    page_number,
                    error,
                )
                print(
                    json.dumps(
                        {
                            "error": "validation_error",
                            "page": page_number,
                            "message": error,
                            "all_pages": all_pages,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return 2

            page_number += 1

        if page_number > MAX_PAGES:
            logger.error("Exceeded MAX_PAGES=%d — possible infinite loop", MAX_PAGES)
            return 3

        # Print full result
        print(
            json.dumps(
                {"total_pages_extracted": len(all_pages), "pages": all_pages},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        close(page)


if __name__ == "__main__":
    sys.exit(main())
