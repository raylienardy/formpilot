"""Temporary CLI prototype for Fase 1.

Usage:
    python -m formpilot --url "https://docs.google.com/forms/d/e/..."

Extracts questions from page 1 and prints as JSON.
This file will be replaced by full cli.py in Fase 5.
"""

from __future__ import annotations

import argparse
import json
import sys

from formpilot.scraper import close, extract_questions, open_form


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FormPilot prototype: extract questions from a Google Form (single page)",
    )
    parser.add_argument("--url", required=True, help="Google Forms URL")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser with UI (default: headless)",
    )
    args = parser.parse_args()

    page = None
    try:
        page = open_form(args.url, headless=not args.headed)
        extracted = extract_questions(page, page_number=1)
        # Print as JSON for machine-readable output
        print(json.dumps(extracted.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        close(page)


if __name__ == "__main__":
    sys.exit(main())
