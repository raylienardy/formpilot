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

## Dokumen Referensi

- **Agent baru wajib baca:** `docs/AGENT-BRIEF.md`
- **Peta dokumen:** `docs/INDEX.md`
- **Roadmap:** `docs/ROADMAP.md`
- **Step-by-step:** `docs/PHASES.md`
- **Visi produk:** `docs/PRODUCT.md`
- **Keperluan teknis:** `docs/REQUIREMENTS.md`