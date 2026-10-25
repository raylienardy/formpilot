# PHASES.md — Detail Step-by-Step per Fase

Dokumen ini adalah "cookbook" untuk setiap fase. ROADMAP.md menjawab "apa & kapan", PHASES.md menjawab "bagaimana, step by step".

Sebelum mulai fase baru, baca STATE.md untuk memastikan fase sebelumnya selesai.

---

## FASE 1 — Scraper MVP

### Fase 1.1 — Setup pyproject.toml
**File:** `pyproject.toml`
**Isi:** Metadata project, dependencies, ruff config, pytest config
**Verifikasi:** `pip install -e ".[dev]"` → sukses
**Estimasi:** 15 menit

### Fase 1.2 — Package init
**File:** `formpilot/__init__.py`
**Isi:** docstring + `__version__ = "0.1.0"`
**Verifikasi:** `python -c "import formpilot; print(formpilot.__version__)"` → `0.1.0`
**Estimasi:** 5 menit

### Fase 1.3 — Logger
**File:** `formpilot/utils/logger.py`
**Isi:** Setup logging dua handler (console INFO, file DEBUG). File: `logs/formpilot.log`.
**Verifikasi:** log muncul di console dan file
**Estimasi:** 20 menit

### Fase 1.4 — Config Loader
**File:** `formpilot/utils/config_loader.py`
**Isi:** Pydantic `AppConfig`, baca `config/production.yaml` + `.env`
**Verifikasi:** `load_config()` membaca file contoh, raise error jika field hilang
**Estimasi:** 40 menit

### Fase 1.5 — Schema Pydantic
**File:** `formpilot/memory/schema.py`
**Isi:** `FieldType` enum, `Question`, `ExtractedForm`, `Answer`, `MemoryHit`, `FormSession`
**Verifikasi:** `Question(text="...", field_type=FieldType.RADIO, options=["A","B"])` → instance valid
**Estimasi:** 45 menit

### Fase 1.6 — Scraper: open_form
**File:** `formpilot/scraper.py`
**Isi:** `open_form(url, headless)` → Playwright Page
**Verifikasi:** Buka form nyata, tidak crash
**Estimasi:** 30 menit

### Fase 1.7 — Scraper: extract_questions
**File:** `formpilot/scraper.py`
**Isi:** Ekstrak `div[role="listitem"]` → list `Question`
**Verifikasi:** Form 3-pertanyaan (teks, radio, paragraf) → JSON dengan tipe benar
**Estimasi:** 90 menit (paling tricky, DOM Google Forms)

### Fase 1.8 — Scraper: is_last_page & close
**File:** `formpilot/scraper.py`
**Isi:** Deteksi tombol Submit, cleanup
**Verifikasi:** Form 1-halaman → `is_last_page=True`
**Estimasi:** 20 menit

### Fase 1.9 — __main__.py prototipe
**File:** `formpilot/__main__.py`
**Isi:** Parse `--url`, open, extract, print JSON, close
**Verifikasi:** `python -m formpilot --url "..."` → JSON valid
**Estimasi:** 20 menit

### Fase 1.10 — Tests
**File:** `tests/test_scraper.py`, `tests/fixtures/sample_form.html`
**Isi:** `test_extract_single_page`, `test_detect_last_page`
**Verifikasi:** `pytest -v` → semua lulus
**Estimasi:** 60 menit

### Fase 1.11 — Update STATE.md
**File:** `docs/STATE.md`
**Isi:** Tandai Fase 1 selesai, tulis berikutnya (Fase 2)
**Estimasi:** 10 menit

**Total Fase 1: 5-6 jam**

**Acceptance Fase 1:**
- [ ] Semua 10 sub-fase selesai
- [ ] `pytest` lulus semua
- [ ] `ruff check formpilot/ tests/` bersih
- [ ] Manual test dengan 3 form berbeda berhasil
- [ ] STATE.md diupdate

---

## FASE 2 — Multi-page

### Fase 2.1 — click_next
**File:** `formpilot/scraper.py`
**Isi:** Klik "Berikutnya"/"Next", tunggu `networkidle`, return bool
**Verifikasi:** Form 3-halaman → klik next dari halaman 1 ke 2 berhasil
**Estimasi:** 45 menit

### Fase 2.2 — click_submit & is_last_page refinement
**File:** `formpilot/scraper.py`
**Isi:** Deteksi tombol submit, klik dengan konfirmasi
**Verifikasi:** Form 1-halaman → is_last_page=True, click_submit berhasil
**Estimasi:** 30 menit

### Fase 2.3 — has_validation_error
**File:** `formpilot/scraper.py`
**Isi:** Deteksi `div[role="alert"]` setelah klik Next
**Verifikasi:** Form dengan required field kosong → error terdeteksi
**Estimasi:** 30 menit

### Fase 2.4 — Loop multi-halaman di __main__
**File:** `formpilot/__main__.py`
**Isi:** Loop: extract → print → click_next → ulangi
**Verifikasi:** Form 3-halaman → cetak pertanyaan tiap halaman
**Estimasi:** 45 menit

### Fase 2.5 — Conditional branching detection
**File:** `formpilot/scraper.py`
**Isi:** Setelah klik Next, bandingkan pertanyaan baru vs yang diharapkan. Log jika melompat.
**Verifikasi:** Form dengan percabangan → tidak crash, log melompat
**Estimasi:** 30 menit

### Fase 2.6 — Tests multi-page
**File:** `tests/test_multipage.py`
**Isi:** `test_three_page`, `test_validation_error`, `test_branching`
**Estimasi:** 60 menit

**Total Fase 2: 4-5 jam**

**Acceptance Fase 2:**
- [ ] Form 3-halaman: ekstrak semua
- [ ] Form percabangan: tidak crash
- [ ] Form required kosong: deteksi error
- [ ] pytest lulus
- [ ] STATE.md diupdate

---

## FASE 3 — Ollama Integration

### Fase 3.1 — Health check Ollama
**File:** `formpilot/brain.py`
**Isi:** `check_ollama_ready()` — cek server + model, raise error jelas jika tidak siap
**Verifikasi:** Ollama mati → error dengan instruksi; Ollama jalan → pass
**Estimasi:** 30 menit

### Fase 3.2 — Prompt templates
**File:** `formpilot/prompts/` (text files)
**Isi:** Prompt untuk: (a) klasifikasi faktual vs naratif, (b) jawab naratif dari konteks, (c) pilih opsi pilihan ganda
**Estimasi:** 60 menit (iteratif)

### Fase 3.3 — Ollama client wrapper
**File:** `formpilot/brain.py`
**Isi:** `call_ollama(prompt, model)` dengan retry + timeout
**Estimasi:** 30 menit

### Fase 3.4 — resolve_questions (no memory)
**File:** `formpilot/brain.py`
**Isi:** Terima questions, klasifikasi → panggil LLM → return Answer
**Catatan:** Pilihan ganda, paksa LLM pilih dari opsi valid (validate output)
**Estimasi:** 60 menit

### Fase 3.5 — Tests
**File:** `tests/test_brain.py`
**Isi:** Mock Ollama response, test resolve untuk 5 tipe pertanyaan
**Estimasi:** 60 menit

**Total Fase 3: 4-5 jam**

**Acceptance Fase 3:**
- [ ] Health check fail fast dengan pesan jelas
- [ ] Pertanyaan faktual → jawaban masuk akal
- [ ] Pilihan ganda → opsi valid
- [ ] Paragraf → naratif pendek
- [ ] pytest lulus

---

## FASE 4 — Memory System

### Fase 4.1 — SQLite store: skema
**File:** `formpilot/memory/sqlite_store.py`
**Isi:** Init DB, create tables (profile, sessions, pending_questions)
**Estimasi:** 30 menit

### Fase 4.2 — SQLite store: CRUD
**File:** `formpilot/memory/sqlite_store.py`
**Isi:** get_profile_field, set_profile_field, get_all_profile, log_session, save_pending_question
**Estimasi:** 45 menit

### Fase 4.3 — Vector store: init Chroma
**File:** `formpilot/memory/vector_store.py`
**Isi:** Init ChromaDB persistent client, koleksi `answers`
**Estimasi:** 30 menit

### Fase 4.4 — Vector store: embedding & search
**File:** `formpilot/memory/vector_store.py`
**Isi:** add_answer (embed via Ollama), search_similar (cosine)
**Estimasi:** 45 menit

### Fase 4.5 — brain.py integration with memory
**File:** `formpilot/brain.py`
**Isi:** Sebelum panggil LLM, cek SQLite (faktual), cek Chroma (naratif). Jika ketemu → pakai. Jika tidak → needs_cli=True.
**Estimasi:** 60 menit

### Fase 4.6 — CLI loop needs_cli
**File:** `formpilot/cli.py` (baru, atau expand `__main__.py`)
**Isi:** Tampilkan pertanyaan needs_cli via Rich, tunggu input, simpan ke memory
**Aturan simpan:** < 100 char faktual → SQLite; naratif → ChromaDB; ragu → tanya user
**Estimasi:** 90 menit

### Fase 4.7 — Tests
**File:** `tests/test_memory.py`, `tests/test_cli_integration.py`
**Isi:** Skenario: pertama kosong → semua tanya; kedua → ambil dari memori
**Estimasi:** 90 menit

**Total Fase 4: 6-8 jam**

**Acceptance Fase 4:**
- [ ] Pertama: semua pertanyaan needs_cli
- [ ] Setelah dijawab: tersimpan di tempat benar
- [ ] Kedua (pertanyaan sama): jawaban dari memory
- [ ] Pertanyaan berbeda tapi terkait: semantic search ketemu
- [ ] pytest lulus

---

## FASE 5 — End-to-End CLI

### Fase 5.1 — cli.py entry point
**File:** `formpilot/cli.py`
**Isi:** Argparse dengan `--url`, `--config`, `--auto-submit`, `--headed`
**Estimasi:** 30 menit

### Fase 5.2 — Rich progress & batch
**File:** `formpilot/cli.py`
**Isi:** Progress bar per halaman, batch pertanyaan needs_cli per halaman
**Estimasi:** 60 menit

### Fase 5.3 — Mode draft vs auto
**File:** `formpilot/cli.py`
**Isi:** Draft: berhenti sebelum submit, tunggu user. Auto: submit setelah semua terjawab.
**Estimasi:** 30 menit

### Fase 5.4 — Session logging
**File:** `formpilot/cli.py`, `formpilot/memory/sqlite_store.py`
**Isi:** Catat ke tabel sessions: url, started_at, mode, status, notes
**Estimasi:** 30 menit

### Fase 5.5 — Tests end-to-end
**File:** `tests/test_e2e.py`
**Isi:** Skenario penuh: form 3-halaman, semua needs_cli, user jawab, submit
**Estimasi:** 90 menit

**Total Fase 5: 4-5 jam**

**Acceptance Fase 5:**
- [ ] User jalankan: buka → jawab → review → submit
- [ ] Log sesi tercatat
- [ ] Auto-submit hanya submit setelah semua terjawab
- [ ] pytest lulus

---

## FASE 6 — v0.1 Release

### Fase 6.1 — README final dengan demo
**File:** `README.md`
**Isi:** GIF demo, screenshot, testimonial (jika ada)
**Estimasi:** 60 menit

### Fase 6.2 — CHANGELOG.md
**File:** `CHANGELOG.md`
**Isi:** 0.1.0 release notes
**Estimasi:** 15 menit

### Fase 6.3 — Tag & release
**Command:** `git tag -a v0.1.0 -m "First public release"` → `git push --tags`
**Estimasi:** 15 menit

### Fase 6.4 — User testing (3 orang)
**Isi:** 3 orang setup mandiri dari README, catat feedback
**Estimasi:** 90 menit

### Fase 6.5 — Perbaikan feedback
**Estimasi:** 60 menit

**Total Fase 6: 4-5 jam**

**Acceptance Fase 6:**
- [ ] Kloning segar → install → jalan < 15 menit
- [ ] 3 orang berhasil setup mandiri
- [ ] Tidak ada bug kritis di 5 form
- [ ] Release notes di GitHub

---

## Setelah v0.1

Fase 7 (Web UI) dan Fase 8 (Setup Service) dimulai HANYA jika:
1. Fase 6 selesai dan terverifikasi
2. User secara eksplisit meminta

Detail fase 7 & 8 akan ditulis saat mulai.

## Prinsip per fase

1. Satu sub-fase = satu commit (maks)
2. Test sebelum lanjut sub-fase berikutnya
3. Update STATE.md di akhir setiap sub-fase
4. Kalau stuck > 30 menit di satu sub-fase, tanya user
