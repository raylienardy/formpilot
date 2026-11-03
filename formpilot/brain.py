"""Ollama Brain for FormPilot.

Responsibilities:
- Check Ollama server health
- Generate answers using local LLM via Ollama API
- Select options for multiple choice fields (validate against allowed options)
- Signal uncertainty via <UNKNOWN> marker so CLI can escalate to user

Non-responsibilities (Fase 4+):
- Memory retrieval (SQLite / ChromaDB)
- Long-term storage of answers
"""

from __future__ import annotations

import re
from pathlib import Path

import requests

from formpilot.memory.schema import Answer, FieldType, MemoryHit, Question
from formpilot.memory.sqlite_store import SqliteStore
from formpilot.memory.vector_store import VectorStore
from formpilot.utils.config_loader import AppConfig
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.brain")

UNKNOWN_MARKER = "<UNKNOWN>"
PROMPTS_DIR = Path(__file__).parent / "prompts"


class BrainError(Exception):
    """Raised when brain fails to resolve a question."""


def check_ollama_ready(config: AppConfig) -> bool:
    """Check if Ollama server is accessible and model exists.

    Returns:
        True if server reachable AND model present in `ollama list`.

    Raises:
        BrainError: If server unreachable or model not found (fail fast).
    """
    url = f"{config.ollama.base_url}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise BrainError(
            f"Ollama server not reachable at {config.ollama.base_url}. "
            f"Is Ollama running? Start it with: `ollama serve`. Error: {e}"
        ) from e

    models = [m.get("name", "") for m in response.json().get("models", [])]
    if config.ollama.model not in models:
        raise BrainError(
            f"Model '{config.ollama.model}' not found in Ollama. "
            f"Available: {models}. Install with: `ollama pull {config.ollama.model}`"
        )

    logger.info("Ollama ready (model=%s)", config.ollama.model)
    return True


def call_ollama(config: AppConfig, prompt: str, system_prompt: str = "") -> str:
    """Call Ollama /api/generate endpoint (non-streaming).

    Args:
        config: App configuration with ollama settings.
        prompt: User prompt.
        system_prompt: Optional system prompt.

    Returns:
        Model response as string (stripped).

    Raises:
        BrainError: If API call fails.
    """
    url = f"{config.ollama.base_url}/api/generate"
    payload = {
        "model": config.ollama.model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": config.ollama.temperature,
        },
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        response = requests.post(url, json=payload, timeout=config.ollama.timeout_seconds)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise BrainError(f"Ollama API call failed: {e}") from e

    text = response.json().get("response", "").strip()
    logger.debug("Ollama response (first 100 chars): %s", text[:100])
    return text


def resolve_questions(
    config: AppConfig,
    questions: list[Question],
    sqlite_store: SqliteStore | None = None,
    vector_store: VectorStore | None = None,
) -> list[Answer]:
    """Resolve a list of questions using memory or LLM."""
    return [_resolve_single_question(config, q, sqlite_store, vector_store) for q in questions]


def _resolve_single_question(
    config: AppConfig,
    q: Question,
    sqlite_store: SqliteStore | None = None,
    vector_store: VectorStore | None = None,
) -> Answer:
    """Resolve a single question via Memory or LLM.

    Strategy:
    1. Check SQLite for exact keyword match (if sqlite_store provided).
    2. Check VectorStore for semantic match (if vector_store provided).
    3. Fallback to LLM if no memory hit found.
    4. Validate memory hits for RADIO/DROPDOWN if necessary.
    """
    if q.has_media or q.field_type == FieldType.UNKNOWN:
        logger.info("Question %d has media/unknown — escalate to user", q.index)
        return Answer(
            question_index=q.index,
            value="",
            source="skip",
            needs_cli=True,
            confidence=0.0,
        )

    # 1. Memory Lookups
    if sqlite_store:
        sqlite_hits = sqlite_store.find_relevant(q.text)
        if sqlite_hits and sqlite_hits[0].similarity >= 0.6:
            hit = sqlite_hits[0]
            logger.info("Memory hit (SQLite) for Q%d: %s", q.index, hit.answer)
            return _handle_memory_hit(q, hit, sqlite_store, vector_store)

    if vector_store:
        vector_hits = vector_store.search_similar(q.text, top_k=1, min_similarity=0.6)
        if vector_hits:
            hit = vector_hits[0]
            logger.info("Memory hit (Chroma) for Q%d: %s", q.index, hit.answer)
            return _handle_memory_hit(q, hit, sqlite_store, vector_store)

    # 2. LLM Fallback
    try:
        if q.field_type in (FieldType.SHORT_TEXT, FieldType.PARAGRAPH):
            return _resolve_text(config, q)
        if q.field_type in (FieldType.RADIO, FieldType.DROPDOWN):
            return _resolve_radio(config, q)
        if q.field_type == FieldType.CHECKBOX:
            return _resolve_checkbox(config, q)
        if q.field_type == FieldType.LINEAR_SCALE:
            return _resolve_scale(config, q)
    except BrainError as e:
        logger.error("Brain failed for question %d: %s", q.index, e)
        return Answer(
            question_index=q.index,
            value="",
            source="error",
            needs_cli=True,
            confidence=0.0,
        )

    return Answer(
        question_index=q.index,
        value="",
        source="skip",
        needs_cli=True,
        confidence=0.0,
    )


def _handle_memory_hit(
    q: Question,
    hit: MemoryHit,
    sqlite_store: SqliteStore | None,
    vector_store: VectorStore | None,
) -> Answer:
    """Validate and return a memory hit."""
    if q.field_type in (FieldType.SHORT_TEXT, FieldType.PARAGRAPH):
        return Answer(
            question_index=q.index,
            value=hit.answer,
            source=hit.source,
            needs_cli=False,
            confidence=min(hit.similarity, 0.9),
        )

    if q.field_type in (FieldType.RADIO, FieldType.DROPDOWN):
        matched = _match_option(hit.answer, q.options)
        if matched:
            return Answer(
                question_index=q.index,
                value=matched,
                source=f"{hit.source}_validated",
                needs_cli=False,
                confidence=min(hit.similarity, 0.9),
            )
        logger.info("Memory hit invalid for Q%d options: %s", q.index, hit.answer)

    if q.field_type == FieldType.CHECKBOX:
        # Validate each comma-separated token against options
        tokens = [t.strip() for t in hit.answer.split(",") if t.strip()]
        matched_list = []
        for tok in tokens:
            m = _match_option(tok, q.options)
            if m is not None and m not in matched_list:
                matched_list.append(m)
        if matched_list:
            return Answer(
                question_index=q.index,
                value=", ".join(matched_list),
                source=f"{hit.source}_validated",
                needs_cli=False,
                confidence=min(hit.similarity, 0.9),
            )
        logger.info("Memory hit invalid for Q%d checkbox: %s", q.index, hit.answer)

    if q.field_type == FieldType.LINEAR_SCALE:
        matched = _match_option(hit.answer, q.options)
        if matched:
            return Answer(
                question_index=q.index,
                value=matched,
                source=f"{hit.source}_validated",
                needs_cli=False,
                confidence=min(hit.similarity, 0.9),
            )
        logger.info("Memory hit invalid for Q%d scale: %s", q.index, hit.answer)

    return Answer(
        question_index=q.index,
        value="",
        source="memory_invalid",
        needs_cli=True,
        confidence=0.0,
    )


def _load_prompt_template(name: str) -> str:
    """Load prompt template from formpilot/prompts/<name>.txt."""
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise BrainError(f"Prompt template missing: {path}")
    return path.read_text(encoding="utf-8")


def _resolve_text(config: AppConfig, q: Question) -> Answer:
    """Resolve SHORT_TEXT or PARAGRAPH via LLM."""
    template = _load_prompt_template("text_prompt")
    prompt = template.format(question=q.text)
    response = call_ollama(config, prompt).strip()

    # Robust UNKNOWN detection (handles both <UNKNOWN> and UNKNOWN from model)
    if UNKNOWN_MARKER in response or "UNKNOWN" in response.upper() or not response:
        logger.info("LLM returned UNKNOWN for Q%d — needs user input", q.index)
        return Answer(
            question_index=q.index,
            value="",
            source="llm_unknown",
            needs_cli=True,
            confidence=0.0,
        )

    return Answer(
        question_index=q.index,
        value=response,
        source="llm",
        needs_cli=False,
        confidence=0.7,
    )


def _resolve_radio(config: AppConfig, q: Question) -> Answer:
    """Resolve RADIO/DROPDOWN — LLM must pick one of q.options."""
    if not q.options:
        return Answer(
            question_index=q.index,
            value="",
            source="skip",
            needs_cli=True,
            confidence=0.0,
        )

    template = _load_prompt_template("radio_prompt")
    options_block = "\n".join(f"- {opt}" for opt in q.options)
    prompt = template.format(question=q.text, options=options_block)
    response = call_ollama(config, prompt).strip()

    if UNKNOWN_MARKER in response or "UNKNOWN" in response.upper():
        return Answer(
            question_index=q.index,
            value="",
            source="llm_unknown",
            needs_cli=True,
            confidence=0.0,
        )

    # Validate: response must match one of the options (case-insensitive, stripped)
    matched = _match_option(response, q.options)
    if matched is None:
        logger.warning(
            "LLM response '%s' not in options for Q%d. Falling back to needs_cli.",
            response[:50],
            q.index,
        )
        return Answer(
            question_index=q.index,
            value="",
            source="llm_invalid",
            needs_cli=True,
            confidence=0.0,
        )

    return Answer(
        question_index=q.index,
        value=matched,
        source="llm",
        needs_cli=False,
        confidence=0.8,
    )


def _resolve_checkbox(config: AppConfig, q: Question) -> Answer:
    """Resolve CHECKBOX — LLM may select multiple options."""
    if not q.options:
        return Answer(
            question_index=q.index,
            value="",
            source="skip",
            needs_cli=True,
            confidence=0.0,
        )

    template = _load_prompt_template("checkbox_prompt")
    options_block = "\n".join(f"- {opt}" for opt in q.options)
    prompt = template.format(question=q.text, options=options_block)
    response = call_ollama(config, prompt).strip()

    if UNKNOWN_MARKER in response or "UNKNOWN" in response.upper():
        return Answer(
            question_index=q.index,
            value="",
            source="llm_unknown",
            needs_cli=True,
            confidence=0.0,
        )

    # Response expected as comma-separated list
    selected = [s.strip() for s in response.split(",") if s.strip()]
    matched_list = []
    for sel in selected:
        m = _match_option(sel, q.options)
        if m is not None and m not in matched_list:
            matched_list.append(m)

    if not matched_list:
        return Answer(
            question_index=q.index,
            value="",
            source="llm_invalid",
            needs_cli=True,
            confidence=0.0,
        )

    return Answer(
        question_index=q.index,
        value=", ".join(matched_list),
        source="llm",
        needs_cli=False,
        confidence=0.7,
    )


def _resolve_scale(config: AppConfig, q: Question) -> Answer:
    """Resolve LINEAR_SCALE — LLM picks number in range."""
    if not q.options:
        return Answer(
            question_index=q.index,
            value="",
            source="skip",
            needs_cli=True,
            confidence=0.0,
        )

    template = _load_prompt_template("linear_scale_prompt")
    range_str = f"{q.options[0]} sampai {q.options[-1]}"
    prompt = template.format(question=q.text, range=range_str)
    response = call_ollama(config, prompt).strip()

    if UNKNOWN_MARKER in response:
        return Answer(
            question_index=q.index,
            value="",
            source="llm_unknown",
            needs_cli=True,
            confidence=0.0,
        )

    matched = _match_option(response, q.options)
    if matched is None:
        return Answer(
            question_index=q.index,
            value="",
            source="llm_invalid",
            needs_cli=True,
            confidence=0.0,
        )

    return Answer(
        question_index=q.index,
        value=matched,
        source="llm",
        needs_cli=False,
        confidence=0.7,
    )


def _match_option(response: str, options: list[str]) -> str | None:
    """Match response against options (case-insensitive, whitespace-trimmed)."""
    response_norm = re.sub(r"\s+", " ", response.strip().lower())
    for opt in options:
        opt_norm = re.sub(r"\s+", " ", opt.strip().lower())
        if opt_norm == response_norm:
            return opt
    # Substring fallback: option contained in response
    for opt in options:
        opt_norm = opt.strip().lower()
        if opt_norm in response_norm:
            return opt
    return None
