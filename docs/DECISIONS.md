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
