# STATE — Jurnal Sesi

Memori kerja project. Setiap sesi WAJIB update di sini. Sesi berikutnya baca file ini.

## Status Saat Ini

**Fase:** Fase 3 Selesai (Real LLM Integration — Sesi 5-Koreksi)
**Iterasi aktif:** `tasks/current/prd.md` — Iterasi 1
**Kode fungsional:** `formpilot/scraper.py`, `formpilot/brain.py` (real LLM), `formpilot/__main__.py` (dengan `--ai` flag)
**Blocker:** Tidak ada

## Log Sesi

### 2026-11-02 — Sesi 5-Koreksi (Fix Fase 3: Real LLM Integration)

**Konteks:**
Commit `b8fbf9f` mengklaim "Fase 3 Selesai" tetapi sebenarnya hanya stub:
`_resolve_single_question` tidak memanggil LLM, `__main__.py` tidak integrasi, semua test mock.

**Selesai di sesi koreksi:**
- `config/example.yaml`: model fix `qwen2.5:7b-instruct` → `qwen2.5:7b` (tag valid di Ollama)
- `formpilot/brain.py`: **REWRITE** — `_resolve_single_question` sekarang memanggil `call_ollama()` untuk semua tipe field (text, radio, checkbox, linear_scale), dengan validasi output + `<UNKNOWN>` escalation pattern
- `formpilot/prompts/*.txt`: rewrite lengkap (text, radio, checkbox, linear_scale)
- `formpilot/__main__.py`: tambah flag `--ai` (opt-in), integrasi dengan brain
- `tests/test_brain.py`: tambah 4 integration tests (auto-skip jika Ollama tidak jalan)
- `scripts/verify_brain.py`: skrip verifikasi manual (5 kasus, harus PASS semua)
- `docs/REQUIREMENTS.md`: fix model reference

**Verifikasi (setelah sesi koreksi):**
- `pytest -v -m "not integration"`: 49 passed
- `pytest -m integration`: 4 passed (setelah warmup fixture)
- `pytest -v`: 53 passed
- `python scripts/verify_brain.py`: ALL CHECKS PASSED
- `ruff check formpilot/ tests/ scripts/`: All checks passed!
- **Manual form test (form multi-halaman 3 section):**
  - Navigasi 3 halaman otomatis: ✅
  - `required: true` untuk NIM: ✅ (fix Fase 2 verified)
  - `total_pages_estimate: 3`: ✅ (fix Fase 2 verified)
  - NIM → llm_unknown: ✅ (no hallucination, correct escalation)
  - Jurusan → llm_unknown: ✅ (correct — LLM tidak tahu jurusan user)
  - Motivasi → llm_unknown: ✅ (correct — LLM tidak tahu motivasi user)
  - Semua jawaban `needs_cli: true`: ✅ (EXPECTED behavior tanpa memory)
  - Total waktu: [isi detik]

**Keputusan:**
- `<UNKNOWN>` escalation adalah **perilaku yang diinginkan**, bukan bug
- Fase 4 (memory) akan mengisi gap: pertanyaan personal dijawab dari memory setelah user jawab sekali via CLI
- Warmup fixture ditambahkan di test_brain.py untuk handle cold start Ollama (30-90s load pertama)

**Known Limitations:**
- **Tanpa memory (Fase 4), semua pertanyaan personal akan `llm_unknown`** — ini desain, bukan bug
- **`UNKNOWN` detection dilonggarkan** (`"UNKNOWN" in response.upper()`) — bisa false-positive untuk respons dengan kata "unknown" dalam konteks lain. Akan diperketat di Fase 4.
- **`text_prompt.txt` membedakan personal vs general** — refinement iteratif, perlu uji lebih banyak kasus.

**Known Limitations:**
- `_resolve_text` tidak bisa membedakan "opini umum" vs "personal fact yang mirip opini" — LLM bisa salah klasifikasi. Akan diperbaiki di Fase 4 (memory system).
- `total_pages_estimate` masih null untuk form single-page (expected), belum diverifikasi untuk form multi-halaman asli.
- `_is_required()` belum diverifikasi untuk form asli multi-halaman.

**Berikutnya (Sesi 6 — Fase 4: Memory System):**
- Implementasi `formpilot/memory/sqlite_store.py`
- Implementasi `formpilot/memory/vector_store.py`
- Integrasi memory ke `brain.py` (sebelum panggil LLM, cek dulu)
- CLI loop untuk needs_cli

**Blocker:** (tidak ada)

---

## Dokumen Referensi

Fondasi v2 lengkap. Navigasi:

- **Agent baru wajib baca:** `docs/AGENT-BRIEF.md`
- **Peta dokumen:** `docs/INDEX.md`
- **Roadmap:** `docs/ROADMAP.md`
- **Step-by-step:** `docs/PHASES.md`
- **Visi produk:** `docs/PRODUCT.md`
- **Keperluan teknis:** `docs/REQUIREMENTS.md`
