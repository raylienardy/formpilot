"""Temporary CLI prototype for Fase 1+2+3.

Usage:
    python -m formpilot --url "..." [--headed] [--ai]

Without --ai: extract questions only (behavior from Fase 2).
With --ai:    extract + resolve via brain.py (LLM) + show answers or needs_cli.
"""

from __future__ import annotations

import argparse
import json
import sys

from formpilot.brain import BrainError, check_ollama_ready, resolve_questions
from formpilot.scraper import (
    click_next,
    close,
    extract_questions,
    has_validation_error,
    open_form,
)
from formpilot.utils.config_loader import ConfigError, load_config
from formpilot.utils.logger import get_logger, setup_logger

MAX_PAGES = 50


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FormPilot prototype: extract questions and optionally resolve with AI",
    )
    parser.add_argument("--url", required=True, help="Google Forms URL")
    parser.add_argument("--headed", action="store_true", help="Run browser with UI")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Resolve answers via brain.py (requires Ollama running)",
    )
    parser.add_argument(
        "--config",
        default="./config/production.yaml",
        help="Path to config YAML",
    )
    args = parser.parse_args()

    setup_logger("formpilot", level="INFO")
    logger = get_logger("formpilot.__main__")

    config = None
    if args.ai:
        try:
            config = load_config(args.config)
            check_ollama_ready(config)
        except (ConfigError, BrainError) as e:
            print(f"AI setup failed: {e}", file=sys.stderr)
            return 2

    page = None
    try:
        page = open_form(args.url, headless=not args.headed)

        all_pages: list[dict] = []
        page_number = 1
        previous_question_texts: list[str] = []

        while page_number <= MAX_PAGES:
            extracted = extract_questions(page, page_number=page_number)

            page_dict = extracted.model_dump(mode="json")

            # Resolve with AI if requested
            if args.ai and config is not None:
                answers = resolve_questions(config, extracted.questions)
                page_dict["answers"] = [a.model_dump(mode="json") for a in answers]

            all_pages.append(page_dict)

            current_texts = [q.text for q in extracted.questions]
            if page_number > 1 and current_texts == previous_question_texts:
                logger.warning(
                    "Page %d identical to previous — branching or navigation issue",
                    page_number,
                )
            previous_question_texts = current_texts

            if extracted.is_last_page:
                break

            if not click_next(page):
                break

            error = has_validation_error(page)
            if error:
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
