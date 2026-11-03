"""SQLite store for FormPilot.

Manages three tables:
- profile:            key-value facts about the user (nama, NIM, jurusan, ...)
- sessions:           form-filling session log (audit & debugging)
- pending_questions:  questions that needed user input (audit trail)

Design notes (see ADR-005):
- SQLite is for structured facts, not narrative memory
- Narrative answers go to vector_store.py (Sesi 6b)
- All writes are synchronous and transactional
- Schema is idempotent (CREATE IF NOT EXISTS)
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from formpilot.memory.schema import MemoryHit
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.memory.sqlite_store")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    category    TEXT,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    started_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at  TIMESTAMP,
    mode         TEXT,
    status       TEXT,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS pending_questions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER REFERENCES sessions(id),
    page_number  INTEGER,
    question_text TEXT NOT NULL,
    user_answer  TEXT,
    answered_at  TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pending_session ON pending_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_profile_category ON profile(category);
"""


class SqliteStore:
    """SQLite wrapper for profile, sessions, pending questions.

    Usage:
        store = SqliteStore("./memory.db")
        store.set_profile_field("nama_lengkap", "Budi Santoso", "identity")
        nama = store.get_profile_field("nama_lengkap")

        sid = store.log_session_start("https://forms.gle/xxx", "draft")
        store.log_session_finish(sid, "success", "Done in 2m")
    """

    def __init__(self, db_path: str | Path = "./memory.db") -> None:
        """Initialize store, create schema if not exists.

        Args:
            db_path: Path to SQLite file. Parent dir must exist.
        """
        self.db_path = Path(db_path)
        parent = self.db_path.parent
        if not parent.exists():
            raise FileNotFoundError(f"Directory not found: {parent}. Create it first.")
        self._init_schema()
        logger.debug("SqliteStore initialized at %s", self.db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager: connect, commit on success, rollback on error, close."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Create tables and indexes if not exist."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)
        logger.debug("Schema initialized")

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_profile_field(self, key: str) -> str | None:
        """Get a single profile field. Returns None if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_profile_field(self, key: str, value: str, category: str | None = None) -> None:
        """Upsert a profile field. Updates updated_at on conflict."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO profile (key, value, category, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = COALESCE(excluded.category, profile.category),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value, category),
            )
        logger.debug("Profile updated: %s (category=%s)", key, category)

    def get_all_profile(self) -> dict[str, str]:
        """Get all profile fields as dict."""
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM profile").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def delete_profile_field(self, key: str) -> bool:
        """Delete a profile field. Returns True if existed."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM profile WHERE key = ?", (key,))
        return cursor.rowcount > 0

    def find_relevant(self, question_text: str) -> list[MemoryHit]:
        """Simple keyword search against profile.

        Matches if any word in question_text (len >= 3) appears in profile key
        OR value (case-insensitive). Returns list of MemoryHit sorted by
        number of keyword matches (descending).

        This is a naive fallback. ChromaDB (Sesi 6b) will do semantic search.
        """
        keywords = [w.lower() for w in question_text.split() if len(w) >= 3 and w.isalnum()]
        if not keywords:
            return []

        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM profile").fetchall()

        hits: list[MemoryHit] = []
        for row in rows:
            haystack = f"{row['key']} {row['value']}".lower()
            matches = sum(1 for kw in keywords if kw in haystack)
            if matches > 0:
                hits.append(
                    MemoryHit(
                        question=question_text,
                        answer=row["value"],
                        similarity=min(matches / len(keywords), 1.0),
                        source="sqlite",
                    )
                )

        hits.sort(key=lambda h: h.similarity, reverse=True)
        return hits

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def log_session_start(self, url: str, mode: str = "draft") -> int:
        """Log start of a form-filling session. Returns session ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (url, mode, status) VALUES (?, ?, ?)",
                (url, mode, "pending"),
            )
            session_id = cursor.lastrowid
        logger.info("Session started: id=%d, url=%s, mode=%s", session_id, url, mode)
        return session_id

    def log_session_finish(self, session_id: int, status: str, notes: str = "") -> None:
        """Mark session finished. status: 'success' | 'failed' | 'aborted'."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET finished_at = CURRENT_TIMESTAMP, status = ?, notes = ?
                WHERE id = ?
                """,
                (status, notes, session_id),
            )
        logger.info("Session finished: id=%d, status=%s", session_id, status)

    def get_session(self, session_id: int) -> dict | None:
        """Get session by ID. Returns None if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def list_recent_sessions(self, limit: int = 10) -> list[dict]:
        """List recent sessions (newest first)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Pending questions
    # ------------------------------------------------------------------

    def save_pending_question(self, session_id: int, page_number: int, question_text: str) -> int:
        """Record a question that needs user input. Returns question ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pending_questions
                    (session_id, page_number, question_text)
                VALUES (?, ?, ?)
                """,
                (session_id, page_number, question_text),
            )
            qid = cursor.lastrowid
        logger.debug("Pending question saved: id=%d", qid)
        return qid

    def answer_pending_question(self, question_id: int, answer: str) -> None:
        """Mark a pending question as answered."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pending_questions
                SET user_answer = ?, answered_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (answer, question_id),
            )
        logger.debug("Pending question answered: id=%d", question_id)

    def list_pending_questions(
        self, session_id: int | None = None, unanswered_only: bool = False
    ) -> list[dict]:
        """List pending questions. Optional filter by session or unanswered."""
        query = "SELECT * FROM pending_questions WHERE 1=1"
        params: list = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if unanswered_only:
            query += " AND user_answer IS NULL"
        query += " ORDER BY id ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
