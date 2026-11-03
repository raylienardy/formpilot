# STATE — Jurnal Sesi

Memori kerja project. Setiap sesi WAJIB update di sini. Sesi berikutnya baca file ini.

## Status Saat Ini

**Fase:** Fase 2.7 Selesai (CDP Mode for Login-Required Forms)
**Iterasi aktif:** `tasks/current/prd.md` — Iterasi 1
**Kode fungsional:** `formpilot/scraper.py`, `formpilot/brain.py` (real LLM), `formpilot/__main__.py` (dengan `--ai`, `--dummy-fill`, `--cdp-url`)
**Blocker:** Tidak ada

## Log Sesi

### 2026-11-03 — Sesi 5.7 & 5.8 (CDP Mode — Login-Required Forms)

**Konteks:**
Form "Test Bot 4" memerlukan Google login (setting "Limit to 1 response" atau "Collect email"). Playwright stealth biasa tidak bisa handle karena form men-disable input untuk user yang belum login.

**Root cause terkonfirmasi:**
- Fingerprint stealth bersih (`webdriver=None, plugins=5, platform=Win32`)
- Tapi body form menampilkan "Sign in to continue" → input disabled
- **Bukan anti-bot detection** — ini authentication state

**Solusi:**
CDP (Chrome DevTools Protocol) attach ke Edge/Chrome yang sudah login.

**Selesai:**
- `scraper.py`: `open_form_via_cdp(cdp_url, url)` — attach ke existing browser via CDP
- `__main__.py`: flag `--cdp-url` untuk switch mode CDP vs stealth-launch
- `scraper.py`: `_fill_single` fail-fast 3s + diagnostic log disabled inputs (Sesi 5.5)
- `tests/test_real_form.py`: integration test (auto-skip jika TEST_FORM_URL tidak diset)

**Verifikasi:**
- `pytest -v -m "not integration"`: 54 passed
- `pytest -m integration`: 4 passed (Ollama integration)
- `ruff check formpilot/ tests/ scripts/`: clean
- **Manual test CDP mode:**
  ```
  ✅ Port 9222 READY (Edge Edg/156.0.4314.58)
  ✅ Attached to context with 1 existing pages
  ✅ Form loaded via CDP: Test Bot 4
  ✅ Filled 1/1 fields
  ✅ JSON fields_filled: 1
  ```
- Form "Nama?" terisi manual bisa diketik → confirm login state valid
- Form terisi otomatis oleh FormPilot via CDP → confirm automation works

**Keputusan:**
- **CDP mode** = primary path untuk form yang butuh login (mayoritas kuisioner kampus)
- **Stealth open_form** = fallback untuk form public (tanpa login)
- **Auto-fallback** tidak diperlukan; user pilih via `--cdp-url` flag
- User perlu launch Edge dengan `--remote-debugging-port=9222` manual sebelum run

**Known Limitations:**
- **CDP mode butuh manual setup:** launch Edge dengan debug port + login Google sekali
- **Stealth mode masih ada** untuk form public (tidak optimal untuk form login)
- **Multi-page navigation via CDP** belum diverifikasi dengan form asli multi-halaman + login (form "Test Bot 4" hanya 1 halaman)
- **Dropdown filling** belum diimplementasi (Fase 4)
- **`--dummy-fill` adalah placeholder** — Fase 4 akan replace dengan CLI loop yang tanya user

**Berikutnya (Sesi 6a — Fase 4.1: SQLite Store):**
- Implementasi `formpilot/memory/sqlite_store.py`
- Skema: tabel `profile`, `sessions`, `pending_questions`
- CRUD: `get_profile_field`, `set_profile_field`, `get_all_profile`
- Fungsi: `log_session`, `save_pending_question`
- Test dengan fixtures, tanpa integrasi brain dulu

**Blocker:** (tidak ada)

---

### 2026-11-03 — Sesi 6a (SQLite Store)

**Selesai:**
- `formpilot/memory/sqlite_store.py`: `SqliteStore` class with 3 tables
  - Profile: get, set (upsert), get_all, delete, find_relevant (keyword)
  - Sessions: log_start, log_finish, get, list_recent
  - Pending questions: save, answer, list (filter by session / unanswered)
- `tests/test_sqlite_store.py`: 23 unit tests
- `docs/STATE.md`: this log

**Verifikasi:**
- `pytest tests/test_sqlite_store.py -v`: 23 passed
- `pytest -v -m "not integration"`: 77 passed total (54 existing + 23 new)
- `ruff check formpilot/ tests/ scripts/`: clean

**Keputusan:**
- `find_relevant` uses simple keyword match (words len >= 3). Not semantic.
  ChromaDB (Sesi 6b) will handle narrative memory with real embeddings.
- Upsert via `ON CONFLICT(key) DO UPDATE` — no separate update logic.
- `_connect()` is a context manager — auto commit/rollback/close.
- Schema is idempotent (`CREATE IF NOT EXISTS`).

**Known Limitations:**
- `find_relevant` keyword match misses synonyms (e.g. "nama" vs "name")
- No pagination for `list_recent_sessions` (assumes small DB)

**Berikutnya (Sesi 6b — Vector Store / ChromaDB):**
- `formpilot/memory/vector_store.py`: ChromaDB persistent client
- Embedding via Ollama (`nomic-embed-text`)
- `add_answer`, `search_similar`
- Tests with mock embeddings

---

### 2026-11-03 — Sesi 6b (Vector Store — ChromaDB)

**Selesai:**
- `formpilot/memory/vector_store.py`: `VectorStore` class using ChromaDB
  - `_embed`: Ollama nomic-embed-text via /api/embeddings
  - `add_answer`: insert with UUID, metadata (question, category, timestamp)
  - `search_similar`: cosine search with min_similarity filter
  - `count`, `clear` (for testing)
- `tests/test_vector_store.py`: unit tests (mocked embed) + integration tests (real Ollama, auto-skip)
- `pyproject.toml`: added `chromadb>=0.5` dependency
- Prerequisite: `ollama pull nomic-embed-text` (done)

**Verifikasi:**
- `pytest tests/test_vector_store.py -v -m \"not integration\"`: passed
- `pytest -v -m \"not integration\"`: passed total
- `pytest -m integration`: integration tests passed if nomic-embed-text available
- `ruff check formpilot/ tests/ scripts/`: clean

**Keputusan:**
- Chroma cosine distance → similarity conversion: `1 - (dist / 2)` (range [0,1])
- `min_similarity` threshold as filter (default 0.0, caller can raise)
- UUID auto-generated per answer (no manual ID management)
- Metadata: question (original), category (optional), timestamp (ISO)

**Known Limitations:**
- No update / delete per-document (only `clear` for all)
- No pagination in search (returns top_k only)
- Embedding dimension fixed by nomic-embed-text (768)

### 2026-11-03 — Sesi 6c (Memory Integration into Brain & CLI)

**Selesai:**
- `formpilot/brain.py`: Updated `resolve_questions` and `_resolve_single_question` to accept `sqlite_store` and `vector_store`.
  - Resolution priority: SQLite keyword match (>=0.6) → Chroma semantic search (>=0.6) → LLM fallback.
  - Validation of retrieved memory answers against options for RADIO/DROPDOWN fields.
- `formpilot/__main__.py`: Added `--use-memory` flag, which initializes `SqliteStore` and `VectorStore` based on configuration paths and passes them to `resolve_questions`.
- `tests/test_brain_memory.py`: Added unit tests verifying SQLite priority, Chroma fallback, and LLM fallback.

**Verifikasi:**
- `pytest -v -m "not integration"`: 98 passed successfully.
- `pytest -m integration`: 6 passed, 1 skipped.

**Berikutnya (Fase 5 — End-to-End CLI / Interactive loop):**
- `formpilot/cli.py`: Full interactive CLI loop with Rich UI for `needs_cli` questions, saving answers back to SQLite/ChromaDB.

---

## Dokumen Referensi

- **Agent baru wajib baca:** `docs/AGENT-BRIEF.md`
- **Peta dokumen:** `docs/INDEX.md`
- **Roadmap:** `docs/ROADMAP.md`
- **Step-by-step:** `docs/PHASES.md`
- **Visi produk:** `docs/PRODUCT.md`
- **Keperluan teknis:** `docs/REQUIREMENTS.md`