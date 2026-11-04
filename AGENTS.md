# AGENTS.md — FORMPILOT PROJECT

Konteks wajib untuk setiap AI coding agent (DeepSeek, OpenCode, Claude Code, Cursor). Baca sampai selesai sebelum menulis kode.

---

## 1. IDENTITAS PROJECT

**Nama:** FormPilot
**Tujuan:** Asisten lokal pengisi Google Forms otonom, memori persisten.
**Stack:** Python 3.11+, Playwright, Ollama, ChromaDB, SQLite, Rich.
**Lisensi:** MIT (open source penuh).
**Status:** v0.1.0 released (2026-11-04). See CHANGELOG.md for features. See docs/ROADMAP.md for next milestones (v0.1.1 in planning).

**Prinsip inti:**
1. **100% lokal.** Tidak ada API cloud (OpenAI, Anthropic, Gemini, Firebase, Supabase cloud).
2. **Open source penuh.** JANGAN sarankan obfuscation, PyArmor, license server.
3. **Human-in-the-loop.** AI tidak pernah submit tanpa review, kecuali `--auto-submit`.
4. **Memori tumbuh.** AI mulai kosong, belajar dari jawaban user via CLI.

---

## 2. BACA DULU SEBELUM KERJA

1. `docs/architecture.md`
2. `docs/STATE.md`
3. `tasks/current/prd.md`
4. `docs/DECISIONS.md`
5. `docs/SKILLS-ADAPTED.md`

Jika `docs/STATE.md` menyebut blocker, tanya user.

---

## 3. ATURAN KERAS

### TIDAK boleh:
- ❌ Dependensi cloud (`openai`, `anthropic`, `firebase-admin`, `supabase`, `google-cloud-*`)
- ❌ Ubah skema SQLite/ChromaDB tanpa update `docs/architecture.md`
- ❌ Commit file di `.gitignore` (`data/`, `state/`, `config/production.yaml`, `.env`, `memory.db`, `chroma/`)
- ❌ Submit otomatis tanpa flag `--auto-submit`
- ❌ Saran obfuscation/license binding (bertentangan ADR-001)
- ❌ Ubah prompt di `formpilot/prompts/` tanpa ADR baru
- ❌ Lompati fase (Iterasi 1 = Playwright ekstraksi saja)
- ❌ `# ...` atau `# sisa kode sama` saat menulis file

### WAJIB:
- ✅ Patuhi `output-skill` (file penuh, no truncate)
- ✅ Update `docs/STATE.md` di akhir sesi
- ✅ Tulis ADR baru untuk keputusan arsitektur baru
- ✅ Jalankan `pytest` sebelum selesai (setelah test ada)
- ✅ Tanya user jika ragu

---

## 4. SKILL AKTIF

Detail: `docs/SKILLS-ADAPTED.md`.

| Skill | Status | Kapan |
| :--- | :--- | :--- |
| `output-skill` | WAJIB | Setiap `.py` |
| `graphify` | Aktif jika support `.py` | Navigasi |
| `soft-skill` | PARKIR | Fase web UI nanti |
| `redesign-skill` | PARKIR | Fase web UI nanti |
| `react-best-practices` | TIDAK RELEVAN | — |
| `composition-patterns` | TIDAK RELEVAN | — |
| `web-design-guidelines` | PARKIR | Fase web UI nanti |

---

## 5. KONVENSI KODE

- Bahasa kode: Inggris. Komentar bisnis: boleh Indonesia.
- Type hints wajib untuk fungsi publik.
- Docstring wajib (Google style).
- Format: `ruff format` (100 chars).
- Lint: `ruff check`.
- Test: `pytest` di `tests/`.
- File: `snake_case.py`, Class: `PascalCase`, Konstanta: `UPPER_SNAKE_CASE`.

---

## 6. STRUKTUR FOLDER

```
formpilot/
├── formpilot/
│   ├── cli.py
│   ├── scraper.py
│   ├── brain.py
│   ├── memory/
│   │   ├── sqlite_store.py
│   │   ├── vector_store.py
│   │   └── schema.py
│   ├── prompts/
│   └── utils/
│       ├── logger.py
│       └── config_loader.py
├── tests/
├── docs/
├── tasks/
├── config/
└── pyproject.toml
```

Detail: `docs/architecture.md`.

---

## 7. NON-GOALS

- Web UI / GUI desktop (nanti)
- Multi-user
- Sinkronisasi cloud
- Obfuscation
- Form non-Google (nanti)
- OCR gambar
- Analisis video/audio

---

## 8. MODEL BISNIS

Open source (MIT). Monetisasi via jasa setup. JANGAN sarankan sebaliknya.

---

## 9. BLOCKER

Lihat `docs/STATE.md`. Saat ini: tidak ada.

---

## 10. CARA MENGAKHIRI SESI

1. Update `docs/STATE.md`
2. ADR baru jika ada keputusan arsitektur
3. Tandai PRD selesai jika berlaku
4. Tunjukkan `git diff`
5. Jangan commit tanpa izin user

---

## 11. NAVIGASI DOKUMEN

Handbook lengkap untuk agent ada di `docs/AGENT-BRIEF.md`. Baca itu setiap sesi baru.

Peta semua dokumen: `docs/INDEX.md`.

Dokumen kunci:
- `docs/AGENT-BRIEF.md` — handbook lengkap agent (WAJIB baca sesi baru)
- `docs/PRODUCT.md` — visi, target, bayangan akhir project
- `docs/ROADMAP.md` — fase, milestone, estimasi
- `docs/PHASES.md` — step-by-step detail tiap fase
- `docs/REQUIREMENTS.md` — hardware, software, skill
- `docs/STATE.md` — status terkini
