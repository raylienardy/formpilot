"""Tests for sqlite_store.py.

All tests use temporary DB in tmp_path (pytest fixture). No real memory.db
touched. Fast, isolated.
"""

from __future__ import annotations

import pytest

from formpilot.memory.sqlite_store import SqliteStore


@pytest.fixture
def store(tmp_path):
    """Fresh store backed by temp DB per test."""
    db_path = tmp_path / "test.db"
    return SqliteStore(db_path)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_creates_tables(store):
    """All three tables exist after init."""
    with store._connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert "profile" in tables
    assert "sessions" in tables
    assert "pending_questions" in tables


def test_init_missing_parent_raises():
    """Init with non-existent parent directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Directory not found"):
        SqliteStore("/nonexistent_dir_xyz/memory.db")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_get_nonexistent_returns_none(store):
    assert store.get_profile_field("tidak_ada") is None


def test_set_and_get_profile(store):
    store.set_profile_field("nama_lengkap", "Budi Santoso", "identity")
    assert store.get_profile_field("nama_lengkap") == "Budi Santoso"


def test_set_profile_upsert(store):
    store.set_profile_field("nim", "12345", "academic")
    store.set_profile_field("nim", "99999", "academic")
    assert store.get_profile_field("nim") == "99999"


def test_set_profile_without_category(store):
    store.set_profile_field("hobi", "coding")
    assert store.get_profile_field("hobi") == "coding"


def test_get_all_profile(store):
    store.set_profile_field("a", "1", "cat1")
    store.set_profile_field("b", "2", "cat2")
    result = store.get_all_profile()
    assert result == {"a": "1", "b": "2"}


def test_get_all_profile_empty(store):
    assert store.get_all_profile() == {}


def test_delete_profile(store):
    store.set_profile_field("to_delete", "x")
    assert store.delete_profile_field("to_delete") is True
    assert store.get_profile_field("to_delete") is None


def test_delete_nonexistent_returns_false(store):
    assert store.delete_profile_field("tidak_ada") is False


def test_profile_unicode(store):
    """Indonesian characters, emoji, etc stored correctly."""
    store.set_profile_field("nama", "Budi Santoso 中文 🎓", "identity")
    assert store.get_profile_field("nama") == "Budi Santoso 中文 🎓"


# ---------------------------------------------------------------------------
# find_relevant
# ---------------------------------------------------------------------------


def test_find_relevant_matches_key(store):
    store.set_profile_field("nim", "12345", "academic")
    hits = store.find_relevant("Berapa NIM Anda?")
    assert len(hits) >= 1
    assert any(h.answer == "12345" for h in hits)


def test_find_relevant_matches_value(store):
    store.set_profile_field("nama_lengkap", "Budi Santoso", "identity")
    hits = store.find_relevant("Nama Budi siapa?")
    assert len(hits) >= 1
    assert any("Budi Santoso" in h.answer for h in hits)


def test_find_relevant_no_match(store):
    store.set_profile_field("nama", "Budi", "identity")
    hits = store.find_relevant("Berapa harga tiket pesawat?")
    assert hits == []


def test_find_relevant_empty_question(store):
    store.set_profile_field("nama", "Budi")
    assert store.find_relevant("") == []


def test_find_relevant_sorted_by_similarity(store):
    store.set_profile_field("nim", "12345")
    store.set_profile_field("nama", "Budi")
    # Question mentions both "nim" and "nama" — both should match
    hits = store.find_relevant("NIM dan nama Anda?")
    assert len(hits) >= 1
    # Sorted descending
    if len(hits) >= 2:
        assert hits[0].similarity >= hits[1].similarity


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def test_log_session_start_returns_id(store):
    sid = store.log_session_start("https://forms.gle/xxx", "draft")
    assert isinstance(sid, int)
    assert sid > 0


def test_log_session_start_status_pending(store):
    sid = store.log_session_start("https://forms.gle/xxx")
    session = store.get_session(sid)
    assert session["status"] == "pending"
    assert session["finished_at"] is None


def test_log_session_finish(store):
    sid = store.log_session_start("https://forms.gle/xxx")
    store.log_session_finish(sid, "success", "Done in 2m")
    session = store.get_session(sid)
    assert session["status"] == "success"
    assert session["notes"] == "Done in 2m"
    assert session["finished_at"] is not None


def test_get_session_nonexistent(store):
    assert store.get_session(99999) is None


def test_list_recent_sessions(store):
    for i in range(3):
        store.log_session_start(f"https://forms.gle/{i}")
    recent = store.list_recent_sessions(limit=2)
    assert len(recent) == 2
    # Newest first
    assert recent[0]["url"] == "https://forms.gle/2"


def test_list_recent_sessions_empty(store):
    assert store.list_recent_sessions() == []


# ---------------------------------------------------------------------------
# Pending questions
# ---------------------------------------------------------------------------


def test_save_pending_question(store):
    sid = store.log_session_start("https://forms.gle/xxx")
    qid = store.save_pending_question(sid, 1, "Berapa NIM?")
    assert isinstance(qid, int)
    assert qid > 0


def test_answer_pending_question(store):
    sid = store.log_session_start("https://forms.gle/xxx")
    qid = store.save_pending_question(sid, 1, "Berapa NIM?")
    store.answer_pending_question(qid, "12345")

    questions = store.list_pending_questions(session_id=sid)
    assert len(questions) == 1
    assert questions[0]["user_answer"] == "12345"
    assert questions[0]["answered_at"] is not None


def test_list_pending_questions_unanswered_only(store):
    sid = store.log_session_start("https://forms.gle/xxx")
    q1 = store.save_pending_question(sid, 1, "Q1")
    q2 = store.save_pending_question(sid, 2, "Q2")
    store.answer_pending_question(q1, "answer1")

    unanswered = store.list_pending_questions(unanswered_only=True)
    assert len(unanswered) == 1
    assert unanswered[0]["id"] == q2


def test_list_pending_questions_by_session(store):
    s1 = store.log_session_start("url1")
    s2 = store.log_session_start("url2")
    store.save_pending_question(s1, 1, "Q1")
    store.save_pending_question(s2, 1, "Q2")

    s1_questions = store.list_pending_questions(session_id=s1)
    assert len(s1_questions) == 1
    assert s1_questions[0]["question_text"] == "Q1"
