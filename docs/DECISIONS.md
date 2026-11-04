# Architecture Decision Records (ADR)

Agen AI WAJIB baca ini sebelum saran perubahan besar.

## ADR-001: Open Source Penuh (MIT), Monetisasi via Jasa Setup

**Tanggal:** 2026-10-25
**Status:** Diterima

**Konteks:** Pilihan antara open source penuh + jasa setup, vs source-available + obfuscation.

**Keputusan:** Open source penuh (MIT).

**Alasan:**
1. Portofolio GitHub lebih bernilai dari proteksi kode
2. Pasar non-teknis tidak akan setup sendiri (moat alami = kompleksitas)
3. Obfuscation bertentangan dengan nilai edukasi
4. Garansi + tuning + training tidak bisa dicopy

**Konsekuensi:**
- Kode bisa dibaca siapa saja (diterima)
- Tidak ada proteksi teknis (diterima)
- Tuning disimpan di config/production.yaml (di-ignore)

**Jangan diubah tanpa diskusi eksplisit dengan pemilik project.**

## ADR-002: 100% Lokal — Ollama, Bukan API Cloud

**Tanggal:** 2026-10-25
**Status:** Diterima

**Keputusan:** Ollama di localhost. Tidak ada cloud.

**Alasan:** Privasi, kuisioner berisi data pribadi, model 7B-13B cukup untuk laptop modern.

**Konsekuensi:**
- Butuh RAM ≥ 16GB
- Kualitas lebih rendah dari cloud
- User pull model manual

## ADR-003: ChromaDB untuk Memori Semantik

**Tanggal:** 2026-10-25
**Status:** Diterima

**Keputusan:** ChromaDB.

**Alasan:** API Python sederhana, persistensi built-in, komunitas besar, cukup untuk skala personal.

**Alternatif ditolak:** LanceDB (overkill), Qdrant (butuh Docker), FAISS (tanpa metadata).

## ADR-004: Playwright untuk Otomasi Browser

**Tanggal:** 2026-10-25
**Status:** Diterima

**Keputusan:** Playwright (Python).

**Alasan:** API modern, auto-wait, Chromium headless stabil, simpan browser state.

**Alternatif ditolak:** Selenium (flaky), Puppeteer (Node.js).

## ADR-005: Dual Memory — SQLite + ChromaDB

**Tanggal:** 2026-10-25
**Status:** Diterima

**Keputusan:** SQLite (faktual) + ChromaDB (naratif).

**Alasan:** Faktual tidak butuh semantic search, ChromaDB untuk naratif saja, audit mudah, query deterministik.

**Aturan:** < 100 char tanpa opini → SQLite. ≥ 100 char atau opini → ChromaDB. Ragu → tanya user.

## ADR-006: PARAGRAPH Always Escalates to User

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
Manual test Form 2b dan Form 3 menunjukkan LLM menjawab PARAGRAPH
questions dengan narasi generik. Source=llm, jawaban tidak masuk memory,
Chroma count tetap 0. Memory tidak tumbuh.

**Keputusan:**
PARAGRAPH questions selalu escalate ke user via interactive CLI.
LLM tidak menjawab paragraph.

**Alasan:**
1. Sesuai P4: "Memori tumbuh dari interaksi"
2. Paragraph = refleksi pribadi = butuh input user asli
3. LLM generic answer tidak berguna untuk user
4. Dengan user answer, memory tumbuh dan RUN 2 bisa auto-fill
5. Chroma path end-to-end teruji

**Konsekuensi:**
- Setiap PARAGRAPH di form baru akan prompt user (first time)
- Setelah dijawab sekali, RUN berikutnya auto-fill dari Chroma
- FormPilot terasa lebih "belajar" dari user, bukan "mengarang"

**Jangan diubah tanpa diskusi eksplisit.** Untuk v0.2, opsi "LLM draft,
user edit" bisa dievaluasi.

## ADR-007: Hybrid Profile Strategy

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
FormPilot butuh akses browser yang sudah login Google. Dua opsi:
existing user profile (instant login, tapi harus close semua tab) vs
dedicated isolated profile (aman tapi login sekali di awal).

**Keputusan:**
Hybrid — existing profile default, fallback isolated.

**Perilaku:**
- Browser tidak running → launch dengan existing profile (instant login)
- Browser running → prompt: [1] relaunch (tab hilang), [2] isolated, [3] cancel
- Flag `--profile existing|isolated|ask`

**Alasan:**
1. Instant login untuk user yang tidak sedang kerja di browser
2. User kontrol penuh (tidak auto-kill tab)
3. Fallback tersedia untuk multi-session user
4. Dedicated profile path terisolasi: `~/.formpilot/profiles/<browser>/`

**Konsekuensi:**
- Existing profile = FormPilot bisa akses history/password user (trust)
- Isolated profile = login Google sekali di awal, setelah itu persist
- Multi-account harus di-handle (ADR untuk multi-account terpisah)

## ADR-008: Auto-Fill Confidence Threshold + Staleness

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
Auto-fill dari memory bisa salah kalau memory stale atau semantic
similarity rendah. Perlu safety net.

**Keputusan:**
- Confidence threshold: 0.7 (similarity < 0.7 → skip auto-fill, escalate)
- Staleness: 180 hari (last_verified > 180 hari → warning)
- Configurable di `config/production.yaml`:
  - `memory.auto_fill_threshold: 0.7`
  - `memory.staleness_days: 180`

**Alasan:**
1. Threshold 0.7 empiris: below = terlalu generic/mismatch
2. 180 hari = 6 bulan, reasonable staleness untuk data pribadi
3. Configurable = user power user bisa adjust

**Konsekuensi:**
- Memory entry butuh field `last_verified` (ditambahkan di Sesi v0.2-3, see ADR-013)
- Prompt muncul kalau similarity < 0.7
- Warning di preview kalau stale

## ADR-009: Smart Ask Field Safety

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
Field di form bisa sudah terisi manual oleh user sebelum FormPilot run.
Auto-fill bisa overwrite. Perlu safety.

**Keputusan:**
Smart Ask — auto-fill dulu, prompt hanya pada 4 kondisi:

1. Field kosong, memory punya, similarity < 0.7 → prompt
2. Field kosong, memory tidak punya, required → prompt
3. Field sudah ada isi, beda dengan memory → prompt konflik
4. Memory `last_verified` > 180 hari → warning (bukan prompt)

Default: **skip** fill untuk field yang sudah ada isi manual.
Flag `--force` untuk overwrite.

**Alasan:**
1. Respect user manual input
2. Prompt hanya saat perlu (bukan setiap field)
3. Zero-prompt di form matured (memory full + no conflict)
4. Konflik eksplisit di-handle (bukan silent overwrite)

**Konsekuensi:**
- `_fill_single` harus cek `input.value` dulu
- Conflict resolution UI dibutuhkan
- `--force` untuk power user
- Staleness check pakai `last_verified` (ditambahkan di Sesi v0.2-3, see ADR-013)

## ADR-010: Chromium v0.2, Firefox v0.3

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
Playwright support Chromium + Firefox + WebKit. Firefox tidak punya
CDP (Chrome DevTools Protocol), profile reuse tidak bisa.

**Keputusan:**
- v0.2: Chromium family only (Chrome, Edge, Brave, Chromium, Vivaldi)
- v0.3: Tambah Firefox (arsitektur terpisah)

**Alasan:**
1. CDP = foundation for profile reuse & instant login
2. Chromium family = 85%+ market share
3. Firefox butuh arsitektur berbeda (no `connect_over_cdp`)
4. Risk untuk tambah Firefox di v0.2 = scope creep

**Konsekuensi:**
- User Firefox = tidak bisa pakai v0.2
- Defer v0.3 (target setelah v0.2.0 stable)
- Docs menyebut limitation jelas

## ADR-011: `formpilot auto` Command Shortcut

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
v0.1.0 butuh flag panjang: `--ai --use-memory --interactive --cdp-url`.
v0.2 butuh lebih (auto-fill, review, profile). Friction tinggi.

**Keputusan:**
Add subcommand `formpilot auto <url>` sebagai shortcut:

```
formpilot auto <url>
# equivalent to:
formpilot --url <url> --ai --use-memory --auto-fill --profile ask --preview
```

Override dengan flag tambahan:
- `formpilot auto --user <name> <url>`
- `formpilot auto --browser <name> <url>`
- `formpilot auto --force <url>` (overwrite manual fields)

**Alasan:**
1. Marketing-friendly (one command = easy to share)
2. Lower friction untuk user awam
3. Backward compat (v0.1.0 flags tetap jalan)
4. Future-proof (bisa add default behavior di auto tanpa ubah long flags)

**Konsekuensi:**
- `__main__.py` butuh refactor (subcommand + flags)
- Docs harus tunjukkan `auto` sebagai primary UX
- Flag panjang tetap documented sebagai advanced

## ADR-012: Two-Way Sync MVP = Submit Detection Only

**Tanggal:** 2026-11-04
**Status:** Diterima

**Konteks:**
User bisa edit di browser setelah fill. Perubahan harus masuk ke
memory. Dua approach: real-time input watcher (complex) atau
submit-boundary sync (simpler).

**Keputusan:**
v0.2 MVP: submit detection only.

**Perilaku:**
- Attach listener: `document.addEventListener('submit', ...)` via `page.evaluate`
- Poll (non-blocking) untuk submit event
- On submit: extract all field values, diff vs memory, update changed entries
- On tab-close-without-submit: log warning, next run diff

**Alasan:**
1. Submit = clean boundary (user selesai fill)
2. Real-time = race condition, banyak writes, complexity
3. Tab-close fallback = safety net
4. v0.3 bisa upgrade ke real-time kalau perlu

**Konsekuensi:**
- v0.2 requires polling loop (poll setiap 2 detik)
- Tab-close = diff done next run (bisa prompt user)
- Real-time watcher = v0.3

## ADR-013: Extend Memory Schema with `last_verified` Field (v0.2-3)

**Tanggal:** 2026-11-04
**Status:** Diterima (implementasi ditunda ke Sesi v0.2-3)

**Konteks:**
PLAN audit v0.2-0 menemukan bahwa VISION-V020.md, ADR-008, dan ADR-009
mereferensikan field `last_verified` untuk staleness tracking, tapi
field ini tidak ada di `formpilot/memory/schema.py` (v0.1.0 baseline).

Field yang ada:
- SQLite `profile` table: `key, value, category, updated_at`
- Chroma metadata: `question, category, timestamp`
- Pydantic `MemoryHit`: `question, answer, similarity, source, timestamp`

**Keputusan:**
Tambahkan field `last_verified` untuk staleness tracking. Implementasi
di Sesi v0.2-3 (auto-fill mode), bukan sekarang.

**Perubahan schema yang akan dilakukan di v0.2-3:**

1. **SQLite `profile` table:**
   - `ALTER TABLE profile ADD COLUMN last_verified TIMESTAMP`
   - Migration logic: cek `PRAGMA table_info(profile)`, add jika tidak ada
   - `set_profile_field`: set `last_verified = CURRENT_TIMESTAMP` (assumsi:
     setting nilai = user baru verify)
   - New method: `mark_profile_verified(key)` — update `last_verified` saja
   - New method: `get_stale_profile_keys(threshold_days)` — return keys
     dengan `last_verified` older than threshold

2. **ChromaDB metadata:**
   - `add_answer`: tambah `last_verified` = same as `timestamp` (new entry)
   - New method: `mark_verified(doc_id)` — update `last_verified` metadata
   - Search result: populate `MemoryHit.last_verified`

3. **Pydantic `MemoryHit`:**
   - Tambah `last_verified: datetime | None = None`

**Alasan:**
1. `updated_at` tidak cukup untuk staleness — itu track "kapan value terakhir
   diubah", bukan "kapan user terakhir verify"
2. Kalau user submit form dengan nilai yang sama 5 kali tanpa ubah, `updated_at`
   tetap di tanggal awal → staleness false positive
3. `last_verified` di-update saat submit form (two-way sync ADR-012) — akurat
4. Small change, migration trivial di SQLite

**Konsekuensi:**
- v0.2-0 docs reference "last_verified (to be added in v0.2-3)"
- v0.2-3 expands scope: schema + migration + staleness logic + tests
- v0.2-3 estimasi: 3-4 jam (dari 2-3 jam)
- v0.1.0 memory.db compatible via auto-migration saat init

**Jangan implementasi sebelum Sesi v0.2-3 dimulai.**
