"""Interactive CLI for FormPilot — Rich UI for needs_cli questions.

This module provides a user-facing prompt loop when brain.resolve_questions
cannot answer (returns needs_cli=True). It shows questions via Rich, prompts
the user, validates input, and saves answers to memory (SQLite for facts,
ChromaDB for narrative).

Not yet integrated into __main__.py — that's Sesi 7b.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from formpilot.memory.schema import Answer, FieldType, Question
from formpilot.memory.sqlite_store import SqliteStore
from formpilot.memory.vector_store import VectorStore
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.cli")

OPINION_KEYWORDS = ("karena", "agar", "menurut", "supaya", "sehingga", "sebab")
VECTOR_THRESHOLD_CHARS = 100


def prompt_for_answers(
    questions: list[Question],
    answers: list[Answer],
    session_id: int | None = None,
    sqlite_store: SqliteStore | None = None,
    vector_store: VectorStore | None = None,
    console: Console | None = None,
) -> list[Answer]:
    """Prompt user for each needs_cli=True question, save answers to memory.

    For each answer with needs_cli=True:
    1. Show question via Rich (with options if RADIO/DROPDOWN/CHECKBOX)
    2. Prompt user for input
    3. Validate (for choice types, must match options)
    4. Save to memory:
       - SHORT_TEXT (short, no opinion keyword) -> SQLite profile
       - PARAGRAPH or long text or opinion keyword -> ChromaDB
       - RADIO/DROPDOWN/LINEAR_SCALE/CHECKBOX -> SQLite profile
    5. Log to pending_questions (audit trail)

    Args:
        questions: All questions on current page (from scraper).
        answers: Resolved answers (from brain). Some may have needs_cli=True.
        session_id: Optional session ID for pending_questions audit.
        sqlite_store: Optional SQLite store for saving facts/preferences.
        vector_store: Optional vector store for saving narratives.
        console: Optional Rich Console (for testing; default creates new).

    Returns:
        Updated answers list — same order, needs_cli=False for answered ones.
    """
    if console is None:
        console = Console()

    updated = list(answers)  # copy so we don't mutate input
    questions_by_index = {q.index: q for q in questions}
    pending = [(i, a) for i, a in enumerate(updated) if a.needs_cli]

    if not pending:
        logger.debug("No questions need CLI input")
        return updated

    console.print()
    console.print(
        Panel(
            f"[bold yellow]FormPilot butuh info Anda[/bold yellow]\n"
            f"{len(pending)} pertanyaan tidak bisa dijawab otomatis.",
            border_style="yellow",
        )
    )

    for list_idx, answer in pending:
        q = questions_by_index.get(answer.question_index)
        if q is None:
            logger.warning(
                "Question index %d not found in questions list — skipping",
                answer.question_index,
            )
            continue

        _show_question(console, q)

        # Optional: audit log to pending_questions
        pending_qid = None
        if sqlite_store is not None and session_id is not None:
            try:
                pending_qid = sqlite_store.save_pending_question(
                    session_id=session_id,
                    page_number=0,  # caller can refine later
                    question_text=q.text,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to log pending question: %s", e)

        user_value = _ask_user(console, q)
        if not user_value:
            console.print("[dim]Skipped.[/dim]")
            updated[list_idx] = Answer(
                question_index=q.index,
                value="",
                source="user_skipped",
                needs_cli=False,
                confidence=0.0,
            )
            continue

        updated[list_idx] = Answer(
            question_index=q.index,
            value=user_value,
            source="user",
            needs_cli=False,
            confidence=1.0,
        )
        console.print(f"[green]Saved:[/green] {user_value[:60]}")

        # Save to memory
        _save_to_memory(q, user_value, sqlite_store, vector_store)

        # Mark answered in audit
        if pending_qid is not None and sqlite_store is not None:
            try:
                sqlite_store.answer_pending_question(pending_qid, user_value)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to mark pending answered: %s", e)

    console.print()
    console.print("[bold green]Semua pertanyaan terjawab.[/bold green]")
    return updated


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _show_question(console: Console, q: Question) -> None:
    """Display a single question via Rich."""
    console.print()
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold cyan]Tipe:[/bold cyan]", q.field_type.value)
    if q.required:
        table.add_row("[bold red]Wajib:[/bold red]", "Ya")
    if q.options:
        table.add_row(
            "[bold cyan]Opsi:[/bold cyan]",
            " | ".join(q.options),
        )
    console.print(table)
    console.print(f"[bold white]{q.text}[/bold white]")


def _ask_user(console: Console, q: Question) -> str:
    """Prompt user for a single answer, with type-specific validation."""
    try:
        if q.field_type in (FieldType.RADIO, FieldType.DROPDOWN, FieldType.LINEAR_SCALE):
            return _ask_choice(console, q)
        if q.field_type == FieldType.CHECKBOX:
            return _ask_checkbox(console, q)
        return _ask_text(console, q)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[red]Dibatalkan.[/red]")
        return ""


def _ask_text(console: Console, q: Question) -> str:
    """Free text input (SHORT_TEXT / PARAGRAPH / UNKNOWN)."""
    return Prompt.ask(
        "[yellow]Jawaban Anda[/yellow] (kosongkan untuk skip)",
        default="",
        console=console,
    ).strip()


def _ask_choice(console: Console, q: Question) -> str:
    """Radio/dropdown/linear scale — must match one of options."""
    if not q.options:
        return _ask_text(console, q)

    while True:
        raw = Prompt.ask(
            f"[yellow]Pilih (1-{len(q.options)})[/yellow]",
            default="",
            console=console,
        ).strip()
        if not raw:
            return ""
        # If user typed a number, map to option index
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(q.options):
                return q.options[idx]
            console.print(
                f"[red]Nomor harus antara 1 dan {len(q.options)}[/red]"
            )
            continue
        # Otherwise try exact match
        for opt in q.options:
            if opt.strip().lower() == raw.lower():
                return opt
        console.print(f"[red]Pilihan tidak valid. Ketik nomor 1-{len(q.options)}[/red]")


def _ask_checkbox(console: Console, q: Question) -> str:
    """Checkbox — comma-separated list, validate each against options."""
    if not q.options:
        return _ask_text(console, q)

    while True:
        raw = Prompt.ask(
            f"[yellow]Pilih (pisahkan dengan koma, nomor 1-{len(q.options)})[/yellow]",
            default="",
            console=console,
        ).strip()
        if not raw:
            return ""
        # Split and resolve each token (number or exact text)
        selected: list[str] = []
        valid = True
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            if token.isdigit():
                idx = int(token) - 1
                if 0 <= idx < len(q.options):
                    selected.append(q.options[idx])
                else:
                    valid = False
                    break
            else:
                matched = next(
                    (o for o in q.options if o.strip().lower() == token.lower()),
                    None,
                )
                if matched:
                    selected.append(matched)
                else:
                    valid = False
                    break
        if valid and selected:
            # Deduplicate preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for s in selected:
                if s not in seen:
                    seen.add(s)
                    unique.append(s)
            return ", ".join(unique)
        console.print(
            f"[red]Pilihan tidak valid. Ketik nomor 1-{len(q.options)} "
            f"dipisah koma.[/red]"
        )


def _should_save_to_vector(answer: str) -> bool:
    """True if answer should go to ChromaDB (narrative memory)."""
    if len(answer) >= VECTOR_THRESHOLD_CHARS:
        return True
    lower = answer.lower()
    return any(kw in lower for kw in OPINION_KEYWORDS)


def _save_to_memory(
    q: Question,
    value: str,
    sqlite_store: SqliteStore | None,
    vector_store: VectorStore | None,
) -> None:
    """Save user answer to SQLite (facts/preferences) or ChromaDB (narratives)."""
    # Choice types always go to SQLite (preferences)
    if q.field_type in (
        FieldType.RADIO,
        FieldType.DROPDOWN,
        FieldType.LINEAR_SCALE,
        FieldType.CHECKBOX,
    ):
        _save_to_sqlite(q, value, sqlite_store)
        return

    # Free-text: decide by length + keywords
    if _should_save_to_vector(value):
        _save_to_vector(q, value, vector_store)
    else:
        _save_to_sqlite(q, value, sqlite_store)


def _save_to_sqlite(
    q: Question,
    value: str,
    sqlite_store: SqliteStore | None,
) -> None:
    """Save to SQLite profile with a slugified key."""
    if sqlite_store is None:
        return
    key = _slugify_key(q.text)
    if not key:
        return
    try:
        sqlite_store.set_profile_field(key, value, category="user_answered")
        logger.debug("Saved to SQLite profile: %s=%s", key, value[:40])
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite save failed: %s", e)


def _save_to_vector(
    q: Question,
    value: str,
    vector_store: VectorStore | None,
) -> None:
    """Save to ChromaDB vector store."""
    if vector_store is None:
        return
    try:
        vector_store.add_answer(
            question=q.text,
            answer=value,
            category="user_answered",
        )
        logger.debug("Saved to ChromaDB: %s", value[:40])
    except Exception as e:  # noqa: BLE001
        logger.warning("ChromaDB save failed: %s", e)


def _slugify_key(text: str) -> str:
    """Convert question text to a snake_case key (max 50 chars).

    Example: "Berapa NIM Anda?" -> "berapa_nim_anda"
    """
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    words = cleaned.lower().split()[:6]
    key = "_".join(words)
    return key[:50]
