"""Tests for memory integration in brain.resolve_questions.

Verifies priority: SQLite keyword → Chroma semantic → LLM fallback.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from formpilot.brain import resolve_questions
from formpilot.memory.schema import FieldType, MemoryHit, Question
from formpilot.utils.config_loader import (
    AppConfig,
    BrowserConfig,
    CliConfig,
    LoggingConfig,
    MemoryConfig,
    OllamaConfig,
)


@pytest.fixture
def mock_config() -> AppConfig:
    return AppConfig(
        ollama=OllamaConfig(
            base_url="http://fake",
            model="fake-model",
            embedding_model="fake-emb",
            temperature=0.3,
            timeout_seconds=1,
        ),
        browser=BrowserConfig(headless=True, user_data_dir="./state", timeout_ms=1),
        memory=MemoryConfig(sqlite_path="./m.db", chroma_path="./c"),
        cli=CliConfig(auto_submit=False, batch_questions=True, language="id"),
        logging=LoggingConfig(level="INFO", file="./logs/t.log"),
    )


def test_resolve_questions_sqlite_priority(mock_config):
    """SQLite hit takes priority; vector store not queried."""
    q = Question(index=1, text="Nama Anda?", field_type=FieldType.SHORT_TEXT)
    sqlite = Mock()
    sqlite.find_relevant.return_value = [
        MemoryHit(
            question="Nama Anda?",
            answer="Budi",
            similarity=0.9,
            source="sqlite",
        )
    ]
    vector = Mock()

    answers = resolve_questions(mock_config, [q], sqlite_store=sqlite, vector_store=vector)

    assert answers[0].value == "Budi"
    assert answers[0].source == "sqlite"
    sqlite.find_relevant.assert_called_once_with("Nama Anda?")
    vector.search_similar.assert_not_called()


def test_resolve_questions_vector_fallback(mock_config):
    """No SQLite hit → falls back to vector store."""
    q = Question(index=1, text="Apa hobi Anda?", field_type=FieldType.SHORT_TEXT)
    sqlite = Mock()
    sqlite.find_relevant.return_value = []

    vector = Mock()
    vector.search_similar.return_value = [
        MemoryHit(
            question="Apa hobi Anda?",
            answer="Membaca",
            similarity=0.9,
            source="chroma",
        )
    ]

    answers = resolve_questions(mock_config, [q], sqlite_store=sqlite, vector_store=vector)

    assert answers[0].value == "Membaca"
    assert answers[0].source == "chroma"
    vector.search_similar.assert_called_once()


def test_resolve_questions_llm_fallback(mock_config):
    """No memory hits → falls back to LLM."""
    q = Question(index=1, text="Apa hobi Anda?", field_type=FieldType.SHORT_TEXT)
    sqlite = Mock()
    sqlite.find_relevant.return_value = []

    vector = Mock()
    vector.search_similar.return_value = []

    with patch("formpilot.brain.call_ollama", return_value="Berenang"):
        answers = resolve_questions(mock_config, [q], sqlite_store=sqlite, vector_store=vector)
        assert answers[0].value == "Berenang"
        assert answers[0].source == "llm"
