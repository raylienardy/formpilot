"""Vector store for FormPilot — semantic memory for narrative answers.

Uses ChromaDB persistent client with Ollama embeddings.

Design notes (see ADR-003, ADR-005):
- ChromaDB for narrative answers (motivations, opinions, essays)
- Embeddings via Ollama nomic-embed-text (local, no cloud)
- Persistent at ./chroma/ (path from config, but constructor param)
- SQLite store (sqlite_store.py) is separate — this is semantic memory only
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import chromadb
import requests
from chromadb.config import Settings

from formpilot.memory.schema import MemoryHit
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.memory.vector_store")

COLLECTION_NAME = "answers"


class VectorStoreError(Exception):
    """Raised when vector store operation fails."""


class VectorStore:
    """ChromaDB wrapper for narrative answer memory.

    Usage:
        store = VectorStore(
            chroma_path="./chroma",
            ollama_base_url="http://localhost:11434",
            embedding_model="nomic-embed-text",
        )
        store.add_answer("Apa motivasi Anda?", "Ingin belajar hal baru")
        hits = store.search_similar("Kenapa Anda ikut organisasi?", top_k=3)
    """

    def __init__(
        self,
        chroma_path: str | Path = "./chroma",
        ollama_base_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
    ) -> None:
        """Initialize vector store.

        Args:
            chroma_path: Path for ChromaDB persistent storage.
            ollama_base_url: Ollama server for embeddings.
            embedding_model: Ollama embedding model name.
        """
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.embedding_model = embedding_model

        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug(
            "VectorStore initialized at %s (collection=%s, count=%d)",
            self.chroma_path,
            COLLECTION_NAME,
            self._collection.count(),
        )

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        """Get embedding vector from Ollama.

        Raises:
            VectorStoreError: If Ollama call fails.
        """
        url = f"{self.ollama_base_url}/api/embeddings"
        try:
            response = requests.post(
                url,
                json={"model": self.embedding_model, "prompt": text},
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise VectorStoreError(
                f"Ollama embedding failed: {e}. "
                f"Is Ollama running? Model '{self.embedding_model}' pulled?"
            ) from e

        data = response.json()
        embedding = data.get("embedding")
        if not embedding:
            raise VectorStoreError(f"Ollama returned no embedding. Response: {data}")
        return embedding

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_answer(
        self,
        question: str,
        answer: str,
        category: str | None = None,
    ) -> str:
        """Add a narrative answer to memory.

        Args:
            question: The question that was asked.
            answer: The answer to store.
            category: Optional category (e.g. 'motivation', 'opinion').

        Returns:
            The generated document ID.

        Raises:
            VectorStoreError: If embedding fails.
        """
        if not answer or not answer.strip():
            raise ValueError("Cannot add empty answer")

        embedding = self._embed(answer)
        doc_id = str(uuid.uuid4())
        metadata: dict = {
            "question": question,
            "category": category or "general",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self._collection.add(
            ids=[doc_id],
            documents=[answer],
            embeddings=[embedding],
            metadatas=[metadata],
        )
        logger.info(
            "Answer added: id=%s, category=%s, len=%d",
            doc_id,
            metadata["category"],
            len(answer),
        )
        return doc_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search_similar(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> list[MemoryHit]:
        """Search for similar answers.

        Args:
            query: Search query (usually a form question).
            top_k: Maximum number of results.
            min_similarity: Minimum similarity threshold (0-1). Hits below
                this are filtered out.

        Returns:
            List of MemoryHit, sorted by similarity (descending). Empty if
            collection empty or no hits above threshold.

        Raises:
            VectorStoreError: If embedding fails.
        """
        if self._collection.count() == 0:
            logger.debug("Vector store empty — no results")
            return []

        query_embedding = self._embed(query)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        hits: list[MemoryHit] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for _doc_id, doc, meta, dist in zip(ids, docs, metas, distances, strict=False):
            # Chroma cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity: 1 - (distance / 2), range [0, 1]
            # Clamp to [0, 1] to guard against float precision
            # (Chroma can return slightly negative distance, causing
            #  1 - (dist/2) to exceed 1.0 by ~1e-8, failing Pydantic le=1.0)
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
            if similarity < min_similarity:
                continue

            timestamp = None
            ts_str = meta.get("timestamp")
            if ts_str:
                with contextlib.suppress(ValueError):
                    timestamp = datetime.fromisoformat(ts_str)

            hits.append(
                MemoryHit(
                    question=meta.get("question", ""),
                    answer=doc,
                    similarity=similarity,
                    source="chroma",
                    timestamp=timestamp,
                )
            )

        logger.debug(
            "Search '%s...' → %d hits (min_sim=%.2f)",
            query[:40],
            len(hits),
            min_similarity,
        )
        return hits

    def count(self) -> int:
        """Total number of documents in collection."""
        return self._collection.count()

    def clear(self) -> None:
        """Delete all documents. For testing only."""
        self._client.delete_collection(name=COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("VectorStore cleared")
