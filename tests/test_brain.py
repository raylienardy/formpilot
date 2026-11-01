"""Tests for brain.py (mocked Ollama)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from formpilot.brain import check_ollama_ready, resolve_questions
from formpilot.memory.schema import FieldType, Question
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
    """Create a test config."""
    return AppConfig(
        ollama=OllamaConfig(
            base_url="http://localhost:11434",
            model="qwen2.5:7b-instruct",
            embedding_model="nomic-embed-text",
            temperature=0.3,
            timeout_seconds=60,
        ),
        browser=BrowserConfig(
            headless=True,
            user_data_dir="./state/browser_profile",
            timeout_ms=30000,
        ),
        memory=MemoryConfig(
            sqlite_path="./memory.db",
            chroma_path="./chroma",
        ),
        cli=CliConfig(
            auto_submit=False,
            batch_questions=True,
            language="id",
        ),
        logging=LoggingConfig(
            level="INFO",
            file="./logs/formpilot.log",
        ),
    )


def test_check_ollama_ready_success(mock_config):
    """Test Ollama health check passes."""
    with patch("formpilot.brain.requests.get") as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [{"name": "qwen2.5:7b-instruct"}, {"name": "nomic-embed-text"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert check_ollama_ready(mock_config) is True


def test_check_ollama_ready_model_not_found(mock_config):
    """Test Ollama health check fails when model not present."""
    with patch("formpilot.brain.requests.get") as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"models": [{"name": "other-model"}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert check_ollama_ready(mock_config) is False


def test_check_ollama_ready_connection_error(mock_config):
    """Test Ollama health check fails on connection error."""
    with patch("formpilot.brain.requests.get") as mock_get:
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError()
        assert check_ollama_ready(mock_config) is False


def test_resolve_radio_questions(mock_config):
    """Test resolving radio button questions."""
    questions = [
        Question(
            index=0,
            text="Pilih jurusan:",
            field_type=FieldType.RADIO,
            options=["TI", "SI", "DKV"],
        ),
    ]
    answers = resolve_questions(mock_config, questions)
    assert len(answers) == 1
    assert answers[0].value == "TI"
    assert answers[0].source == "llm"
    assert answers[0].confidence == 0.8


def test_resolve_short_text(mock_config):
    """Test resolving short text questions."""
    questions = [
        Question(
            index=0,
            text="Nama Anda?",
            field_type=FieldType.SHORT_TEXT,
        ),
    ]
    answers = resolve_questions(mock_config, questions)
    assert len(answers) == 1
    assert answers[0].source == "llm"
    assert "Nama" in answers[0].value or "Contoh" in answers[0].value


def test_resolve_paragraph(mock_config):
    """Test resolving paragraph questions."""
    questions = [
        Question(
            index=0,
            text="Ceritakan motivasi Anda:",
            field_type=FieldType.PARAGRAPH,
        ),
    ]
    answers = resolve_questions(mock_config, questions)
    assert len(answers) == 1
    assert answers[0].source == "llm"


def test_resolve_unknown_needs_cli(mock_config):
    """Test unknown field type returns needs_cli=True."""
    questions = [
        Question(
            index=0,
            text="Unknown question?",
            field_type=FieldType.UNKNOWN,
        ),
    ]
    answers = resolve_questions(mock_config, questions)
    assert len(answers) == 1
    assert answers[0].needs_cli is True
    assert answers[0].source == "skip"
    assert answers[0].confidence == 0.0


def test_resolve_empty_questions(mock_config):
    """Test resolving empty list returns empty list."""
    assert resolve_questions(mock_config, []) == []


def test_resolve_multiple_questions(mock_config):
    """Test resolving multiple questions at once."""
    questions = [
        Question(index=0, text="Q1?", field_type=FieldType.SHORT_TEXT),
        Question(index=1, text="Q2?", field_type=FieldType.RADIO, options=["A", "B"]),
        Question(index=2, text="Q3?", field_type=FieldType.PARAGRAPH),
    ]
    answers = resolve_questions(mock_config, questions)
    assert len(answers) == 3
    assert answers[0].source == "llm"
    assert answers[1].value == "A"
    assert answers[2].source == "llm"
