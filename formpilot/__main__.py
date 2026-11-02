"""Temporary CLI prototype for Fase 1+2+3+2.7.

Usage:
    python -m formpilot --url "..." [--headed] [--ai] [--dummy-fill]

--ai           : resolve questions via brain.py (needs Ollama)
--dummy-fill   : in --ai mode, fill needs_cli answers with placeholders
                 (TEST ONLY — Fase 4 will replace with CLI loop)
"""

from __future__ import annotations

import argparse
import json
import sys

from formpilot.brain import BrainError, check_ollama_ready, resolve_questions
from formpilot.memory.schema import Answer, FieldType, Question
from formpilot.scraper import (
    click_next,
    close,
    extract_questions,
    fill_answers,
    has_validation_error,
    open_form,
)
from formpilot.utils.config_loader import ConfigError, load_config
from formpilot.utils.logger import get_logger, setup_logger


MAX_PAGES = 50


def _dummy_value_for(q: Question) -> str:
    """Placeholder answer for testing (--dummy-fill)."""
    if q.options:
        return q.options[0]
    if q.field_type == FieldType.PARAGRAPH:
        return "Test answer for verification."
    return "TEST"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--ai", action="store_true")
    parser.add_argument(
        "--dummy-fill",
        action="store_true",
        help="In --ai mode: fill needs_cli with placeholders (TEST ONLY)",
    )
    parser.add_argument("--config", default="./config/production.yaml")
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

    if args.dummy_fill and not args.ai:
        print("--dummy-fill requires --ai", file=sys.stderr)
        return 1

    page = None
    try:
        page = open_form(args.url, headless=not args.headed)

        all_pages: list[dict] = []
        page_number = 1
        previous_texts: list[str] = []

        while page_number <= MAX_PAGES:
            extracted = extract_questions(page, page_number=page_number)
            page_dict = extracted.model_dump(mode="json")

            if args.ai and config is not None:
                answers = resolve_questions(config, extracted.questions)

                if args.dummy_fill:
                    for i, a in enumerate(answers):
                        if a.needs_cli:
                            answers[i] = Answer(
                                question_index=a.question_index,
                                value=_dummy_value_for(extracted.questions[i]),
                                source="dummy",
                                needs_cli=False,
                                confidence=0.0,
                            )

                # Fill answers into current page
                filled = fill_answers(page, extracted.questions, answers)
                page_dict["answers"] = [a.model_dump(mode="json") for a in answers]
                page_dict["fields_filled"] = filled

            all_pages.append(page_dict)

            current_texts = [q.text for q in extracted.questions]
            if page_number > 1 and current_texts == previous_texts:
                logger.warning("Page %d identical to previous — branching?", page_number)
            previous_texts = current_texts

            if extracted.is_last_page:
                break

            if not click_next(page):
                error = has_validation_error(page)
                if error:
                    print(
                        json.dumps(
                            {
                                "error": "cannot_advance",
                                "page": page_number,
                                "message": error,
                                "hint": "Required fields empty. Fase 4 will add CLI loop. "
                                "Use --dummy-fill for testing.",
                                "all_pages": all_pages,
                            },
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                    return 2
                break

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
