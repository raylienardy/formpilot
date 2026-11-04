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

from rich.console import Console

from formpilot.brain import BrainError, check_ollama_ready, resolve_questions
from formpilot.browser_manager import (
    BrowserError,
    resolve_browser_from_arg,
)
from formpilot.cli import prompt_for_answers
from formpilot.memory.schema import Answer, FieldType, Question
from formpilot.memory.sqlite_store import SqliteStore
from formpilot.memory.vector_store import VectorStore
from formpilot.profile_manager import ProfileError, resolve_profile
from formpilot.scraper import (
    click_next,
    close,
    extract_questions,
    fill_answers,
    handle_response_receipts,
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
    parser.add_argument(
        "--browser",
        default=None,
        help=(
            "Browser to use: edge | chrome | brave | chromium | vivaldi "
            "OR absolute path to executable. Default: auto-detect + menu."
        ),
    )
    parser.add_argument(
        "--profile",
        choices=["existing", "isolated", "ask"],
        default=None,
        help=(
            "Profile strategy for CDP mode. "
            "'existing' = use default profile (instant login). "
            "'isolated' = use dedicated FormPilot profile. "
            "'ask' = prompt if browser running. Default: from config."
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
        elif args.browser or (config and config.browser.preferred) or args.profile:
            # Browser manager path: user wants control over browser/profile
            _console = Console()
            try:
                browser = resolve_browser_from_arg(
                    args.browser or (config.browser.preferred if config else None),
                    console=_console,
                )
                strategy = args.profile or (
                    config.browser.profile_strategy if config else "ask"
                )
                decision = resolve_profile(
                    browser,
                    strategy=strategy,
                    console=_console,
                )
                if decision.needs_relaunch:
                    _console.print(
                        "[yellow]Note: existing profile with browser running. "
                        "You must manually close the browser before FormPilot "
                        "can attach, or use --profile isolated.[/yellow]"
                    )
                # Set cdp_url to localhost:9222 (launch_browser already launched)
                # For now, print path — full integration with scraper in v0.2-2
                _console.print(
                    f"[green]Browser ready:[/green] {browser.display_name}\n"
                    f"[green]Profile:[/green] {decision.path}\n"
                    f"[dim]CDP integration in v0.2-2[/dim]"
                )
                # Fallback to standard open_form for now
                page = open_form(args.url, headless=not args.headed)
            except (BrowserError, ProfileError) as e:
                print(f"Browser setup failed: {e}", file=sys.stderr)
                return 2
        else:
            page = open_form(args.url, headless=not args.headed)

        all_pages: list[dict] = []
        page_number = 1
        previous_texts: list[str] = []

        while page_number <= MAX_PAGES:
            extracted = extract_questions(page, page_number=page_number)
            page_dict = extracted.model_dump(mode="json")

            # Handle response receipts toggle (only on page 1, once per run)
            if page_number == 1:
                handle_response_receipts(page)

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
                logger.error(
                    "Page %d has identical questions to page %d — "
                    "cannot advance. Stopping to prevent infinite loop.",
                    page_number,
                    page_number - 1,
                )
                print(
                    json.dumps(
                        {
                            "error": "stuck_on_page",
                            "page": page_number,
                            "message": (
                                "Page content identical to previous. "
                                "Next button may be blocked by validation "
                                "(required field empty or format invalid)."
                            ),
                            "hint": (
                                "Check if form has field validation constraints "
                                "(e.g., NIM must be specific length). "
                                "Try filling manually in browser to confirm."
                            ),
                            "all_pages": all_pages,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return 3
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
                                "hint": (
                                    "Validation failed after Next click. "
                                    "Required field empty, format invalid, "
                                    "or branching condition."
                                ),
                                "all_pages": all_pages,
                            },
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                    return 2
                # click_next returned False but no visible error — log diagnostic
                logger.error(
                    "click_next returned False on page %d (last_page=False). "
                    "Navigation blocked but no alert found.",
                    page_number,
                )
                print(
                    json.dumps(
                        {
                            "error": "navigation_blocked",
                            "page": page_number,
                            "message": (
                                "Next click did not advance page, no error alert detected. "
                                "Form may have silent validation or branching."
                            ),
                            "all_pages": all_pages,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                return 4
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
