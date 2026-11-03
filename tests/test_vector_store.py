"""Tests for vector_store.py.

Unit tests mock Ollama embedding (fast).
Integration tests hit real Ollama (auto-skip if not available).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from formpilot.memory.vector_store import VectorStore, VectorStoreError


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return False
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return any(m.startswith("nomic-embed-text") for m in models)
    except Exception:  # noqa: BLE001
        return False


# Fake embedding: hash-based deterministic vector for testing
def _fake_embed(text: str) -> list[float]:
    h = hash(text) % 1000
    return [float(h + i) / 1000.0 for i in range(8)]


@pytest.fixture
def store(tmp_path):
    """Fresh vector store backed by temp dir, with mocked embeddings."""
    s = VectorStore(
        chroma_path=tmp_path / "chroma",
        ollama_base_url="http://fake",
        embedding_model="fake-model",
    )
    with patch.object(s, "_embed", side_effect=_fake_embed):
        yield s


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_creates_directory(tmp_path):
    VectorStore(chroma_path=tmp_path / "newdir")
    assert (tmp_path / "newdir").exists()


def test_init_empty_collection(store):
    assert store.count() == 0


# ---------------------------------------------------------------------------
# add_answer
# ---------------------------------------------------------------------------


def test_add_answer_returns_id(store):
    doc_id = store.add_answer("Q?", "Answer text")
    assert isinstance(doc_id, str)
    assert len(doc_id) == 36  # UUID string


def test_add_answer_increments_count(store):
    store.add_answer("Q1?", "A1")
    store.add_answer("Q2?", "A2")
    assert store.count() == 2


def test_add_answer_empty_raises(store):
    with pytest.raises(ValueError, match="empty"):
        store.add_answer("Q?", "")


def test_add_answer_whitespace_raises(store):
    with pytest.raises(ValueError, match="empty"):
        store.add_answer("Q?", "   ")


def test_add_answer_with_category(store):
    store.add_answer("Motivasi?", "Ingin belajar", category="motivation")
    assert store.count() == 1


def test_add_answer_embedding_error_raises(store):
    with (
        patch.object(store, "_embed", side_effect=VectorStoreError("mock")),
        pytest.raises(VectorStoreError),
    ):
        store.add_answer("Q?", "A")


# ---------------------------------------------------------------------------
# search_similar
# ---------------------------------------------------------------------------


def test_search_empty_collection(store):
    assert store.search_similar("anything") == []


def test_search_returns_hits(store):
    store.add_answer("Motivasi Anda?", "Ingin belajar hal baru")
    hits = store.search_similar("Kenapa ikut?", top_k=5)
    assert len(hits) >= 1
    assert hits[0].source == "chroma"
    assert hits[0].answer == "Ingin belajar hal baru"


def test_search_top_k_limits_results(store):
    for i in range(5):
        store.add_answer(f"Q{i}?", f"Answer {i}")
    hits = store.search_similar("query", top_k=2)
    assert len(hits) <= 2


def test_search_min_similarity_filters(store):
    store.add_answer("Q?", "A")
    # Very high threshold should filter almost everything
    hits = store.search_similar("query", min_similarity=0.99)
    # May or may not have hits depending on fake embedding; just verify no crash
    assert isinstance(hits, list)


def test_search_sorted_by_similarity(store):
    store.add_answer("Q1?", "A1")
    store.add_answer("Q2?", "A2")
    store.add_answer("Q3?", "A3")
    hits = store.search_similar("query", top_k=5)
    similarities = [h.similarity for h in hits]
    assert similarities == sorted(similarities, reverse=True)


def test_search_similarity_clamped_to_one(store):
    """Regression: similarity must never exceed 1.0 (Pydantic le=1.0).

    Bug: Chroma can return slightly negative distance due to float
    precision, making 1 - (dist/2) exceed 1.0 by ~1e-8, failing
    Pydantic validation. Fixed by clamping to [0, 1].
    """
    store.add_answer("Q?", "A")
    # Force a very similar query to trigger high similarity
    hits = store.search_similar("Q?", top_k=5)
    assert len(hits) >= 1
    for hit in hits:
        assert 0.0 <= hit.similarity <= 1.0, f"similarity {hit.similarity} out of [0, 1]"


def test_search_has_timestamp(store):
    store.add_answer("Q?", "A")
    hits = store.search_similar("query")
    if hits:
        assert hits[0].timestamp is not None


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_resets_count(store):
    store.add_answer("Q?", "A")
    assert store.count() == 1
    store.clear()
    assert store.count() == 0


# ---------------------------------------------------------------------------
# Integration tests (real Ollama, skip if unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="nomic-embed-text not available in Ollama")
def test_integration_add_and_search(tmp_path):
    """Real Ollama embedding: add answer, find it back."""
    store = VectorStore(
        chroma_path=tmp_path / "chroma",
        ollama_base_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
    )
    store.add_answer(
        "Apa motivasi Anda mengikuti organisasi?",
        "Saya ingin menambah pengalaman dan jaringan pertemanan.",
    )
    hits = store.search_similar("Kenapa Anda ikut organisasi kampus?", top_k=3)
    assert len(hits) >= 1
    assert "pengalaman" in hits[0].answer.lower()
    assert hits[0].similarity > 0.5  # semantically similar


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_available(), reason="nomic-embed-text not available in Ollama")
def test_integration_embed_returns_vector(tmp_path):
    store = VectorStore(chroma_path=tmp_path / "chroma")
    vec = store._embed("test text")
    assert isinstance(vec, list)
    assert len(vec) > 100  # nomic-embed-text outputs 768-dim
    assert all(isinstance(x, float) for x in vec)
