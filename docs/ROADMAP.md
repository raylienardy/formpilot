# ROADMAP.md — Peta Jalan FormPilot

## Visi akhir (1 paragraf)

FormPilot adalah asisten lokal yang membantu pengguna mengisi kuisioner Google Forms tanpa mengorbankan privasi. Bagi pengguna yang tidak punya waktu atau tidak ingin mengisi kuisioner berulang, FormPilot hadir sebagai partner: memulai dari nol, belajar dari setiap interaksi, dan seiring waktu mampu menjawab kuisioner baru secara otonom — dengan pengawasan manusia yang tetap memegang kendali. Kode 100% open source, monetisasi via jasa setup.

## Milestone besar

| Milestone | Target | Definisi selesai |
| :--- | :--- | :--- |
| **M0 — Foundation** | Selesai | Dokumentasi arsitektur, ADR, STATE, PRD lengkap. Repo publik. |
| **M1 — Scraper MVP** | 2-3 sesi | Playwright bisa buka form 1 halaman, ekstrak pertanyaan, cetak JSON |
| **M2 — Multi-page** | 1-2 sesi | Scraper handle form multi-halaman dengan Next/Submit |
| **M3 — LLM Integration** | 2 sesi | Ollama jalan, brain.py bisa jawab pertanyaan faktual sederhana |
| **M4 — Memory System** | 2-3 sesi | SQLite + ChromaDB, CLI tanya user, memori tumbuh |
| **M5 — End-to-End** | 1-2 sesi | CLI lengkap, form bisa diisi dari A-Z |
| **M6 — v0.1 Release** | 1 sesi | README, demo video, tag v0.1.0 di GitHub |
| **M7 — Web UI (opsional)** | 3-4 sesi | Halaman review lokal (localhost), tidak wajib |

## Fase teknis detail

### FASE 0 — Fondasi ✅ SELESAI
**Tujuan:** Dokumentasi lengkap sebelum nulis kode.
**Deliverable:** README, AGENTS, docs/*, tasks/current/prd.md, config examples, LICENSE.
**Acceptance:** 11 file + LICENSE, 1 commit bersih, .gitignore teruji.

### FASE 1 — Scraper MVP (Iterasi 1)
**Tujuan:** Buktikan Playwright bisa buka Google Form 1 halaman dan ekstrak pertanyaan.
**Non-goals:** AI, memori, fill, multi-page, CLI Rich, gambar, login, auto-submit.
**Deliverable:**
- `pyproject.toml`
- `formpilot/__init__.py`
- `formpilot/utils/logger.py`
- `formpilot/utils/config_loader.py`
- `formpilot/memory/schema.py` (Pydantic: Question, Answer, MemoryHit, FormSession, FieldType)
- `formpilot/scraper.py` (open_form, extract_questions, is_last_page, close)
- `formpilot/__main__.py` (sementara, print JSON)
- `tests/test_scraper.py`

**Acceptance:**
- `pip install -e ".[dev]"` sukses
- `playwright install chromium` sukses
- `python -m formpilot --url "<form-1-halaman>"` mencetak JSON pertanyaan lengkap
- `pytest -v` lulus semua
- `ruff check` bersih
- STATE.md diperbarui

**Estimasi:** 4-6 jam
**Dependency:** Fase 0 selesai

### FASE 2 — Multi-page
**Tujuan:** Handle form dengan section/multi-halaman.
**Deliverable:**
- `scraper.py`: `click_next()`, `click_submit()`, `has_validation_error()`
- Loop per-halaman di `__main__.py`
- Deteksi percabangan (conditional)
- `tests/test_multipage.py`

**Acceptance:**
- Form 3-halaman: ekstrak semua halaman berurutan
- Form dengan percabangan: tidak crash, laporkan halaman yang muncul
- Form dengan field required kosong: deteksi error validasi
- `pytest` lulus

**Estimasi:** 3-4 jam
**Dependency:** Fase 1 selesai

### FASE 3 — Ollama Integration
**Tujuan:** Brain bisa jawab pertanyaan dari konteks minimal (tanpa memory dulu).
**Deliverable:**
- `formpilot/brain.py` dengan `resolve_questions()`, `generate_answer()`
- `formpilot/prompts/` template prompt
- Integrasi Ollama client (`ollama` Python package)
- Health check Ollama di awal (fail fast jika tidak jalan)
- `tests/test_brain.py`

**Acceptance:**
- `python -m formpilot --url <form>` mengisi jawaban dari LLM (masih tanpa memory)
- Jawaban untuk pertanyaan pilihan ganda memilih opsi yang valid
- Timeout handling jika Ollama lambat
- `pytest` lulus

**Estimasi:** 4-5 jam
**Dependency:** Fase 2 selesai

### FASE 4 — Memory System
**Tujuan:** SQLite + ChromaDB. AI mulai dari kosong, belajar dari user via CLI.
**Deliverable:**
- `formpilot/memory/sqlite_store.py`
- `formpilot/memory/vector_store.py`
- Embedding via Ollama (nomic-embed-text)
- Aturan simpan: < 100 char faktual → SQLite, naratif → ChromaDB
- CLI loop untuk needs_cli=True
- `tests/test_memory.py`

**Acceptance:**
- Pertama kali jalan: semua pertanyaan butuh user
- User jawab via CLI, jawaban tersimpan
- Jalan kedua: jawaban diambil dari memory (tidak tanya ulang)
- `pytest` lulus

**Estimasi:** 6-8 jam
**Dependency:** Fase 3 selesai

### FASE 5 — End-to-End CLI
**Tujuan:** CLI lengkap dengan Rich, mode draft/auto, session logging.
**Deliverable:**
- `formpilot/cli.py` — entry point lengkap
- Rich progress bar, batch questions per halaman
- Mode draft (default), mode `--auto-submit`
- Logging sesi ke `sessions` table
- `docs/commands.md` diupdate

**Acceptance:**
- User bisa jalankan end-to-end: buka form → jawab → review → submit
- Log sesi tercatat
- `--auto-submit` hanya submit setelah semua pertanyaan terjawab
- `pytest` lulus

**Estimasi:** 4-5 jam
**Dependency:** Fase 4 selesai

### FASE 6 — v0.1 Release
**Tujuan:** Rilis publik pertama di GitHub.
**Deliverable:**
- README lengkap dengan demo GIF
- `CHANGELOG.md`
- Tag `v0.1.0`
- Release notes di GitHub

**Acceptance:**
- Kloning segar → install → jalan dalam < 15 menit
- 3 orang (Anda + 2 teman) berhasil setup sendiri
- Tidak ada bug kritis di 5 form berbeda

**Estimasi:** 2-3 jam
**Dependency:** Fase 5 selesai

### FASE 7 — Web UI lokal (OPSIONAL)
**Tujuan:** Pengganti CLI dengan browser. Hanya jika CLI terbukti kurang.
**Estimasi:** 8-12 jam
**Dependency:** Fase 6 selesai + minat user

### FASE 8 — Setup Service Packaging
**Tujuan:** Paket untuk jasa setup berbayar.
**Deliverable:**
- `docs/SETUP-GUIDE.md`
- Script `setup.sh` (idempotent)
- Template config per RAM
- Training material 1 jam

**Estimasi:** 4-6 jam
**Dependency:** Fase 6 selesai

## Dependency graph

```
Fase 0 → Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6
                                                          ↓
                                              ┌───────────┴───────────┐
                                              v                       v
                                          Fase 7 (opsional)       Fase 8
```

## Estimasi total

| Milestone | Jam |
| :--- | :--- |
| Fase 0 (selesai) | 6 |
| Fase 1-6 (MVP) | 23-33 |
| Fase 7 (opsional) | 8-12 |
| Fase 8 (setup service) | 4-6 |

**Total MVP (Fase 0-6):** ~30-40 jam kerja terfokus.
Realistis: 3-4 minggu kalau kerja santai, 1-2 minggu kalau fokus.

## Aturan per fase

1. Satu fase = satu atau dua sesi kerja
2. Setiap fase mulai dengan update PRD di `tasks/current/prd.md`
3. Setiap fase selesai dengan update `docs/STATE.md`
4. Tidak ada fase dilompati (lihat P5 di AGENT-BRIEF)
5. Setiap fase punya test yang lulus sebelum lanjut
6. Setiap milestone (M0-M6) di-tag di Git
