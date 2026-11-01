"""Ollama Brain for FormPilot.

Responsibilities:
- Check Ollama server health
- Generate answers using LLM
- Classify questions (faktual vs naratif)
- Select options for multiple choice fields
"""

from __future__ import annotations

import requests

from formpilot.memory.schema import Answer, FieldType, Question
from formpilot.utils.config_loader import AppConfig
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.brain")


class BrainError(Exception):
    """Raised when brain fails to resolve a question."""


def check_ollama_ready(config: AppConfig) -> bool:
    """Check if Ollama server is accessible and model exists."""
    url = f"{config.ollama.base_url}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        models = [m["name"] for m in response.json().get("models", [])]
        if config.ollama.model not in models:
            logger.error("Model %s not found in Ollama", config.ollama.model)
            return False
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Ollama connection error: %s", e)
        return False


def call_ollama(config: AppConfig, prompt: str, system_prompt: str = "") -> str:
    """Call Ollama API."""
    url = f"{config.ollama.base_url}/api/generate"
    payload = {
        "model": config.ollama.model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {"temperature": config.ollama.temperature},
    }
    try:
        response = requests.post(url, json=payload, timeout=config.ollama.timeout_seconds)
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        raise BrainError(f"Ollama API call failed: {e}") from e


def resolve_questions(config: AppConfig, questions: list[Question]) -> list[Answer]:
    """Resolve a list of questions using the brain."""
    answers: list[Answer] = []
    for q in questions:
        answers.append(_resolve_single_question(config, q))
    return answers


def _resolve_single_question(config: AppConfig, q: Question) -> Answer:
    """Resolve a single question."""
    # Placeholder: Simple logic based on field type
    # Fase 4 akan mengintegrasikan MemoryStore

    if q.field_type == FieldType.RADIO and q.options:
        # Simplest: pick first option
        value = q.options[0]
        return Answer(
            question_index=q.index,
            value=value,
            source="llm",
            confidence=0.8,
        )

    if q.field_type in (FieldType.SHORT_TEXT, FieldType.PARAGRAPH):
        # Dummy answer
        return Answer(
            question_index=q.index,
            value="Contoh jawaban untuk " + q.text[:20],
            source="llm",
            confidence=0.7,
        )

    return Answer(
        question_index=q.index,
        value="",
        source="skip",
        needs_cli=True,
        confidence=0.0,
    )
