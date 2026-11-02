"""Tests for brain.py.

Unit tests use mocks (fast, no Ollama needed).
Integration tests use real Ollama (skip if not running).
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from formpilot.brain import (
    UNKNOWN_MARKER,
    BrainError,
    _match_option,
    call_ollama,
    check_ollama_ready,
    resolve_questions,
)
from formpilot.memory.schema import FieldType, Question
from formpilot.utils.config_loader import (
    AppConfig,
    BrowserConfig,
    CliConfig,
    LoggingConfig,
    MemoryConfig,
    OllamaConfig,
)


@pytest.fixture(scope="session", autouse=True)
def _warmup_ollama_if_available():
    """Warm up Ollama before integration tests.

    First LLM call loads model into RAM (~30-90s). Warmup here so the
    actual integration test doesn't hit cold-start timeout.
    """
    if not _ollama_available_session_scoped():
        return  # unit tests will still run
    try:
        requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": "Hi",
                "stream": False,
                "options": {"num_predict": 1},  # minimal generation
            },
            timeout=180,
        )
    except Exception:  # noqa: BLE001
        pass  # warmup failure should not block tests


def _ollama_available_session_scoped() -> bool:
    """Check if Ollama is running (fast, no model load)."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
def mock_config() -> AppConfig:
    return AppConfig(
        ollama=OllamaConfig(
            base_url="http://localhost:11434",
            model="qwen2.5:7b",
            embedding_model="nomic-embed-text",
            temperature=0.3,
            timeout_seconds=120,
        ),
        browser=BrowserConfig(headless=True, user_data_dir="./state", timeout_ms=30000),
        memory=MemoryConfig(sqlite_path="./m.db", chroma_path="./c"),
        cli=CliConfig(auto_submit=False, batch_questions=True, language="id"),
        logging=LoggingConfig(level="INFO", file="./logs/t.log"),
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_check_ollama_ready_success(mock_config):
    with patch("formpilot.brain.requests.get") as mock_get:
        mock_resp = Mock()
        mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        assert check_ollama_ready(mock_config) is True


def test_check_ollama_ready_model_not_found(mock_config):
    with patch("formpilot.brain.requests.get") as mock_get:
        mock_resp = Mock()
        mock_resp.json.return_value = {"models": [{"name": "other:model"}]}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        with pytest.raises(BrainError, match="not found"):
            check_ollama_ready(mock_config)


def test_check_ollama_ready_connection_error(mock_config):
    with (
        patch(
            "formpilot.brain.requests.get",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ),
        pytest.raises(BrainError, match="not reachable"),
    ):
        check_ollama_ready(mock_config)


# ---------------------------------------------------------------------------
# Option matching helper
# ---------------------------------------------------------------------------


def test_match_option_exact():
    assert _match_option("PTIK", ["PTIK", "TEKOM"]) == "PTIK"


def test_match_option_case_insensitive():
    assert _match_option("ptik", ["PTIK", "TEKOM"]) == "PTIK"


def test_match_option_substring():
    assert _match_option("Saya pilih PTIK", ["PTIK", "TEKOM"]) == "PTIK"


def test_match_option_no_match():
    assert _match_option("XYZ", ["PTIK", "TEKOM"]) is None


# ---------------------------------------------------------------------------
# Resolve questions (mocked LLM)
# ---------------------------------------------------------------------------


def test_resolve_text_real_llm_response(mock_config):
    q = Question(index=0, text="Motivasi Anda?", field_type=FieldType.PARAGRAPH)
    with patch("formpilot.brain.call_ollama", return_value="Ingin belajar hal baru"):
        answers = resolve_questions(mock_config, [q])
    assert len(answers) == 1
    assert answers[0].value == "Ingin belajar hal baru"
    assert answers[0].needs_cli is False
    assert answers[0].source == "llm"


def test_resolve_text_unknown_marker(mock_config):
    q = Question(index=0, text="Nama lengkap?", field_type=FieldType.SHORT_TEXT)
    with patch("formpilot.brain.call_ollama", return_value=UNKNOWN_MARKER):
        answers = resolve_questions(mock_config, [q])
    assert answers[0].needs_cli is True
    assert answers[0].source == "llm_unknown"


def test_resolve_radio_valid_option(mock_config):
    q = Question(
        index=0,
        text="Jurusan?",
        field_type=FieldType.RADIO,
        options=["PTIK", "TEKOM"],
    )
    with patch("formpilot.brain.call_ollama", return_value="PTIK"):
        answers = resolve_questions(mock_config, [q])
    assert answers[0].value == "PTIK"
    assert answers[0].needs_cli is False


def test_resolve_radio_invalid_option_escalates(mock_config):
    q = Question(
        index=0,
        text="Jurusan?",
        field_type=FieldType.RADIO,
        options=["PTIK", "TEKOM"],
    )
    with patch("formpilot.brain.call_ollama", return_value="Kedokteran"):
        answers = resolve_questions(mock_config, [q])
    assert answers[0].needs_cli is True
    assert answers[0].source == "llm_invalid"


def test_resolve_checkbox_multiple(mock_config):
    q = Question(
        index=0,
        text="Minat?",
        field_type=FieldType.CHECKBOX,
        options=["Programming", "Design", "Data"],
    )
    with patch("formpilot.brain.call_ollama", return_value="Programming, Data"):
        answers = resolve_questions(mock_config, [q])
    assert answers[0].needs_cli is False
    assert "Programming" in answers[0].value
    assert "Data" in answers[0].value


def test_resolve_scale_valid(mock_config):
    q = Question(
        index=0,
        text="Kepuasan?",
        field_type=FieldType.LINEAR_SCALE,
        options=["1", "2", "3", "4", "5"],
    )
    with patch("formpilot.brain.call_ollama", return_value="4"):
        answers = resolve_questions(mock_config, [q])
    assert answers[0].value == "4"
    assert answers[0].needs_cli is False


def test_resolve_unknown_field_escalates(mock_config):
    q = Question(index=0, text="?", field_type=FieldType.UNKNOWN)
    answers = resolve_questions(mock_config, [q])
    assert answers[0].needs_cli is True
    assert answers[0].source == "skip"


def test_resolve_media_escalates(mock_config):
    q = Question(
        index=0,
        text="Amati gambar",
        field_type=FieldType.SHORT_TEXT,
        has_media=True,
    )
    answers = resolve_questions(mock_config, [q])
    assert answers[0].needs_cli is True


def test_resolve_brain_error_escalates(mock_config):
    q = Question(index=0, text="Test?", field_type=FieldType.SHORT_TEXT)
    with patch(
        "formpilot.brain.call_ollama",
        side_effect=BrainError("mock failure"),
    ):
        answers = resolve_questions(mock_config, [q])
    assert answers[0].needs_cli is True
    assert answers[0].source == "error"


# ---------------------------------------------------------------------------
# Integration tests (real Ollama; skipped if not available)
# ---------------------------------------------------------------------------


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running on localhost:11434")
def test_integration_health_check_real_ollama(mock_config):
    """Real Ollama must be reachable and model present."""
    assert check_ollama_ready(mock_config) is True


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running on localhost:11434")
def test_integration_call_ollama_real(mock_config):
    """Real call returns non-empty string."""
    response = call_ollama(mock_config, "Balas dengan satu kata: HALO")
    assert isinstance(response, str)
    assert len(response) > 0
    assert UNKNOWN_MARKER not in response


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running on localhost:11434")
def test_integration_resolve_radio_real(mock_config):
    """Real LLM must pick a valid option."""
    q = Question(
        index=0,
        text="Jurusan yang paling cocok untuk orang yang suka logika?",
        field_type=FieldType.RADIO,
        options=["Seni", "Teknik Informatika", "Sastra"],
    )
    answers = resolve_questions(mock_config, [q])
    assert len(answers) == 1
    assert answers[0].needs_cli is False
    assert answers[0].value in q.options


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running on localhost:11434")
def test_integration_resolve_personal_info_escalates(mock_config):
    """LLM should return <UNKNOWN> for personal info it doesn't know."""
    q = Question(
        index=0,
        text="Berapa NIM Anda?",
        field_type=FieldType.SHORT_TEXT,
    )
    answers = resolve_questions(mock_config, [q])
    assert len(answers) == 1
    # Must escalate (LLM doesn't know NIM)
    assert answers[0].needs_cli is True
