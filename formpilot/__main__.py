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
from formpilot.cli import prompt_for_answers
from formpilot.memory.schema import Answer, FieldType, Question
from formpilot.memory.sqlite_store import SqliteStore
from formpilot.memory.vector_store import VectorStore
from formpilot.scraper import (
    click_next,
    close,
    extract_questions,
    fill_answers,
    has_validation_error,
    open_form,
    open_form_via_cdp,
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
    parser.add_argument("--use-memory", action="store_true", help="Use SQLite/ChromaDB memory.")
    parser.add_argument(
        "--dummy-fill",
        action="store_true",
        help="In --ai mode: fill needs_cli with placeholders (TEST ONLY)",
    )
    parser.add_argument("--config", default="./config/production.yaml")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help=(
            "Interactively prompt for needs_cli questions via Rich. "
            "Requires --ai. Mutually exclusive with --dummy-fill."
        ),
    )
    parser.add_argument(
        "--cdp-url",
        default=None,
        help=(
            "Attach to existing Chrome/Edge via CDP "
            "(e.g., http://localhost:9222). Use when form requires Google login. "
            "Launch browser first with: chrome.exe --remote-debugging-port=9222"
        ),
    )
    args = parser.parse_args()

    setup_logger("formpilot", level="INFO")
    logger = get_logger("formpilot.__main__")

    config = None
    if args.ai or args.use_memory:
        try:
            config = load_config(args.config)
            if args.ai:
                check_ollama_ready(config)
        except (ConfigError, BrainError) as e:
            print(f"Setup failed: {e}", file=sys.stderr)
            return 2

    sqlite_store = None
    vector_store = None
    if args.use_memory and config is not None:
        try:
            sqlite_store = SqliteStore(config.memory.sqlite_path)
            vector_store = VectorStore(
                chroma_path=config.memory.chroma_path,
                ollama_base_url=config.ollama.base_url,
                embedding_model=config.ollama.embedding_model,
            )
        except Exception as e:
            print(f"Memory setup failed: {e}", file=sys.stderr)
            return 2

    if args.dummy_fill and not args.ai:
        print("--dummy-fill requires --ai", file=sys.stderr)
        return 1
    if args.interactive and not args.ai:
        print("--interactive requires --ai", file=sys.stderr)
        return 1
    if args.interactive and args.dummy_fill:
        print(
            "--interactive and --dummy-fill are mutually exclusive",
            file=sys.stderr,
        )
        return 1

    # Session logging (audit trail)
    session_id: int | None = None
    if sqlite_store is not None:
        mode = "interactive" if args.interactive else "draft"
        session_id = sqlite_store.log_session_start(args.url, mode)

    page = None
    try:
        if args.cdp_url:
            logger.info("Using CDP mode: attaching to existing browser")
            page = open_form_via_cdp(args.cdp_url, args.url)
        else:
            page = open_form(args.url, headless=not args.headed)

        all_pages: list[dict] = []
        page_number = 1
        previous_texts: list[str] = []

        while page_number <= MAX_PAGES:
            extracted = extract_questions(page, page_number=page_number)
            page_dict = extracted.model_dump(mode="json")

            if args.ai and config is not None:
                answers = resolve_questions(
                    config,
                    extracted.questions,
                    sqlite_store=sqlite_store,
                    vector_store=vector_store,
                )

                if args.interactive:
                    answers = prompt_for_answers(
                        extracted.questions,
                        answers,
                        session_id=session_id,
                        sqlite_store=sqlite_store,
                        vector_store=vector_store,
                    )
                elif args.dummy_fill:
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

        if sqlite_store is not None and session_id is not None:
            sqlite_store.log_session_finish(
                session_id,
                "success",
                notes=f"{len(all_pages)} pages extracted",
            )
        return 0

    except Exception as e:  # noqa: BLE001
        if sqlite_store is not None and session_id is not None:
            sqlite_store.log_session_finish(session_id, "failed", notes=str(e)[:500])
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        close(page)


if __name__ == "__main__":
    sys.exit(main())
