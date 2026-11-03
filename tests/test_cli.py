"""Tests for cli.py — interactive prompt loop (mocked input)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from formpilot.cli import (
    _save_to_memory,
    _should_save_to_vector,
    _slugify_key,
    prompt_for_answers,
)
from formpilot.memory.schema import Answer, FieldType, Question

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_q(
    idx: int = 0,
    text: str = "Nama Anda?",
    ftype: FieldType = FieldType.SHORT_TEXT,
    options: list[str] | None = None,
    required: bool = False,
) -> Question:
    return Question(
        index=idx,
        text=text,
        field_type=ftype,
        options=options or [],
        required=required,
    )


def _mk_a(idx: int = 0, needs_cli: bool = True) -> Answer:
    return Answer(
        question_index=idx,
        value="",
        source="llm_unknown",
        needs_cli=needs_cli,
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# _should_save_to_vector
# ---------------------------------------------------------------------------


def test_short_factual_answer_goes_to_sqlite():
    assert _should_save_to_vector("Budi Santoso") is False


def test_long_answer_goes_to_vector():
    assert _should_save_to_vector("x" * 150) is True


def test_opinion_keyword_goes_to_vector():
    assert _should_save_to_vector("Ingin belajar karena suka") is True


def test_opinion_keyword_menurut():
    assert _should_save_to_vector("Menurut saya bagus") is True


# ---------------------------------------------------------------------------
# _slugify_key
# ---------------------------------------------------------------------------


def test_slugify_removes_punctuation():
    assert _slugify_key("Berapa NIM Anda?") == "berapa_nim_anda"


def test_slugify_truncates_long_question():
    key = _slugify_key("Apa " * 20)
    assert len(key) <= 50


def test_slugify_empty():
    assert _slugify_key("") == ""


# ---------------------------------------------------------------------------
# _save_to_memory
# ---------------------------------------------------------------------------


def test_save_radio_to_sqlite():
    q = _mk_q(ftype=FieldType.RADIO, options=["A", "B"])
    sqlite = Mock()
    vector = Mock()
    _save_to_memory(q, "A", sqlite, vector)
    sqlite.set_profile_field.assert_called_once()
    vector.add_answer.assert_not_called()


def test_save_short_text_to_sqlite():
    q = _mk_q(ftype=FieldType.SHORT_TEXT, text="Nama?")
    sqlite = Mock()
    vector = Mock()
    _save_to_memory(q, "Budi", sqlite, vector)
    sqlite.set_profile_field.assert_called_once()
    vector.add_answer.assert_not_called()


def test_save_long_text_to_vector():
    q = _mk_q(ftype=FieldType.PARAGRAPH, text="Motivasi?")
    sqlite = Mock()
    vector = Mock()
    long_answer = "Saya ingin belajar karena " + "x" * 150
    _save_to_memory(q, long_answer, sqlite, vector)
    sqlite.set_profile_field.assert_not_called()
    vector.add_answer.assert_called_once()


def test_save_no_stores_does_not_crash():
    q = _mk_q(ftype=FieldType.SHORT_TEXT)
    _save_to_memory(q, "Budi", None, None)  # should not raise


# ---------------------------------------------------------------------------
# prompt_for_answers
# ---------------------------------------------------------------------------


def test_no_needs_cli_returns_same():
    q = _mk_q()
    a = _mk_a(needs_cli=False)
    result = prompt_for_answers([q], [a])
    assert result[0].needs_cli is False
    assert result[0].value == ""


def test_prompt_short_text_saves_and_returns():
    q = _mk_q(ftype=FieldType.SHORT_TEXT, text="Nama?")
    a = _mk_a(needs_cli=True)
    sqlite = Mock()
    with patch("formpilot.cli.Prompt.ask", return_value="Budi"):
        result = prompt_for_answers([q], [a], sqlite_store=sqlite)
    assert result[0].needs_cli is False
    assert result[0].value == "Budi"
    assert result[0].source == "user"
    sqlite.set_profile_field.assert_called_once()


def test_prompt_empty_input_marks_skipped():
    q = _mk_q(ftype=FieldType.SHORT_TEXT)
    a = _mk_a(needs_cli=True)
    with patch("formpilot.cli.Prompt.ask", return_value=""):
        result = prompt_for_answers([q], [a])
    assert result[0].needs_cli is False
    assert result[0].source == "user_skipped"
    assert result[0].value == ""


def test_prompt_radio_by_number():
    q = _mk_q(ftype=FieldType.RADIO, options=["PTIK", "TEKOM", "PSIKOLOG"])
    a = _mk_a(needs_cli=True)
    with patch("formpilot.cli.Prompt.ask", return_value="2"):
        result = prompt_for_answers([q], [a])
    assert result[0].value == "TEKOM"


def test_prompt_radio_invalid_then_valid():
    q = _mk_q(ftype=FieldType.RADIO, options=["A", "B"])
    a = _mk_a(needs_cli=True)
    # First ask returns invalid, second returns valid
    with patch("formpilot.cli.Prompt.ask", side_effect=["9", "1"]):
        result = prompt_for_answers([q], [a])
    assert result[0].value == "A"


def test_prompt_checkbox_multiple_by_number():
    q = _mk_q(ftype=FieldType.CHECKBOX, options=["Programming", "Design", "Data"])
    a = _mk_a(needs_cli=True)
    with patch("formpilot.cli.Prompt.ask", return_value="1, 3"):
        result = prompt_for_answers([q], [a])
    assert result[0].value == "Programming, Data"


def test_prompt_with_session_id_logs_pending():
    q = _mk_q(ftype=FieldType.SHORT_TEXT)
    a = _mk_a(needs_cli=True)
    sqlite = Mock()
    sqlite.save_pending_question.return_value = 42
    with patch("formpilot.cli.Prompt.ask", return_value="Budi"):
        prompt_for_answers([q], [a], session_id=1, sqlite_store=sqlite)
    sqlite.save_pending_question.assert_called_once()
    sqlite.answer_pending_question.assert_called_once_with(42, "Budi")


def test_prompt_multiple_questions():
    qs = [
        _mk_q(0, "Nama?", FieldType.SHORT_TEXT),
        _mk_q(1, "Jurusan?", FieldType.RADIO, ["A", "B"]),
    ]
    ans = [_mk_a(0, True), _mk_a(1, True)]
    with patch("formpilot.cli.Prompt.ask", side_effect=["Budi", "2"]):
        result = prompt_for_answers(qs, ans)
    assert result[0].value == "Budi"
    assert result[1].value == "B"
    assert all(not a.needs_cli for a in result)


def test_prompt_mixed_some_not_needing_cli():
    qs = [
        _mk_q(0, "Nama?", FieldType.SHORT_TEXT),
        _mk_q(1, "Jurusan?", FieldType.RADIO, ["A", "B"]),
    ]
    ans = [
        _mk_a(0, False),  # already answered
        _mk_a(1, True),
    ]
    ans[0] = Answer(question_index=0, value="Budi", source="llm", needs_cli=False, confidence=0.9)
    with patch("formpilot.cli.Prompt.ask", return_value="1"):
        result = prompt_for_answers(qs, ans)
    assert result[0].value == "Budi"
    assert result[1].value == "A"
