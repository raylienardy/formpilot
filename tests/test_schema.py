"""Tests for Pydantic schemas.

Verifies that models accept valid data and reject invalid data.
No external dependencies — runs fast.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from formpilot.memory.schema import (
    Answer,
    ExtractedForm,
    FieldType,
    MemoryHit,
    Question,
)


def test_field_type_values() -> None:
    """All expected field types exist."""
    assert FieldType.SHORT_TEXT.value == "short_text"
    assert FieldType.PARAGRAPH.value == "paragraph"
    assert FieldType.RADIO.value == "radio"
    assert FieldType.CHECKBOX.value == "checkbox"
    assert FieldType.DROPDOWN.value == "dropdown"
    assert FieldType.LINEAR_SCALE.value == "linear_scale"
    assert FieldType.UNKNOWN.value == "unknown"


def test_question_minimal() -> None:
    """Question can be created with minimal required fields."""
    q = Question(index=0, text="Nama Anda?", field_type=FieldType.SHORT_TEXT)
    assert q.index == 0
    assert q.text == "Nama Anda?"
    assert q.field_type == FieldType.SHORT_TEXT
    assert q.options == []
    assert q.required is False
    assert q.has_media is False


def test_question_radio_with_options() -> None:
    """Question with options for radio/checkbox/dropdown."""
    q = Question(
        index=1,
        text="Pilih jurusan:",
        field_type=FieldType.RADIO,
        options=["TI", "SI", "DKV"],
        required=True,
    )
    assert q.options == ["TI", "SI", "DKV"]
    assert q.required is True


def test_question_rejects_empty_text() -> None:
    """Question text cannot be empty."""
    with pytest.raises(ValidationError):
        Question(index=0, text="", field_type=FieldType.SHORT_TEXT)


def test_question_rejects_negative_index() -> None:
    """Question index must be non-negative."""
    with pytest.raises(ValidationError):
        Question(index=-1, text="Test?", field_type=FieldType.SHORT_TEXT)


def test_extracted_form() -> None:
    """ExtractedForm aggregates questions correctly."""
    q1 = Question(index=0, text="Q1", field_type=FieldType.SHORT_TEXT)
    q2 = Question(index=1, text="Q2", field_type=FieldType.RADIO, options=["A", "B"])
    form = ExtractedForm(
        url="https://docs.google.com/forms/d/e/test",
        page_number=1,
        questions=[q1, q2],
        is_last_page=False,
    )
    assert form.url == "https://docs.google.com/forms/d/e/test"
    assert form.page_number == 1
    assert len(form.questions) == 2
    assert form.is_last_page is False


def test_answer_valid() -> None:
    """Answer with valid confidence."""
    ans = Answer(
        question_index=0,
        value="Budi Santoso",
        source="profile",
        confidence=0.95,
    )
    assert ans.confidence == 0.95
    assert ans.needs_cli is False


def test_answer_rejects_invalid_confidence() -> None:
    """Confidence must be between 0 and 1."""
    with pytest.raises(ValidationError):
        Answer(question_index=0, value="x", source="llm", confidence=1.5)


def test_memory_hit() -> None:
    """MemoryHit with similarity score."""
    hit = MemoryHit(
        question="Motivasi Anda?",
        answer="Ingin belajar",
        similarity=0.87,
        source="chroma",
    )
    assert hit.similarity == 0.87
    assert hit.source == "chroma"
