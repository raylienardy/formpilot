# SKILLS-ADAPTED.md — Adaptasi Skill Guide untuk FormPilot

Adaptasi dari skill guide X-PRO ke project Python+Playwright+Ollama.

## Status Skill

| # | Skill | Status | Catatan |
| :--- | :--- | :--- | :--- |
| 1 | `output-skill` | WAJIB | Universal |
| 2 | `graphify` | Cek dulu | Cek `--help`, support .py? |
| 3 | `soft-skill` | PARKIR | Fase web UI nanti |
| 4 | `redesign-skill` | PARKIR | Sama |
| 5 | `react-best-practices` | TIDAK RELEVAN | Tidak ada React |
| 6 | `composition-patterns` | TIDAK RELEVAN | Tidak ada React |
| 7 | `web-design-guidelines` | PARKIR | Fase web UI nanti |

## 1. output-skill — WAJIB

Trigger: setiap generate/edit `.py`.

Cara: "Patuhi output-skill — tulis file Python lengkap, jangan truncate."

Aturan: file penuh, tidak ada `# ...`, tidak skip imports, sertakan semua type hints & docstring.

## 2. graphify — Verifikasi Dulu

Langkah 1: `graphify --help` — support `.py`?

Jika YA:
```bash
graphify build --root formpilot/ --output graphify-out/graph.json
graphify query "resolve_questions" --graph graphify-out/graph.json
graphify god-nodes --graph graphify-out/graph.json --top 10
graphify affected "brain.resolve_questions" --graph graphify-out/graph.json --depth 3
```

Jika TIDAK: pakai `grep -rn` + `docs/architecture.md`.

Catat hasil di `docs/STATE.md`.

## 3-7. Web/React Skills — PARKIR

Aktifkan hanya jika fase web UI lokal dimulai. Saat itu tiba, terjemahkan konsepnya.

## Workflow (4-phase)

1. Paham: baca `docs/architecture.md` + grep/graphify
2. Implementasi: tulis file penuh (output-skill)
3. Verifikasi: pytest + manual test
4. Catat: update `docs/STATE.md` + ADR jika perlu

## Anti-Pattern

❌ Gabung banyak skill dalam 1 prompt
❌ Skip output-skill saat generate .py
❌ Pakai skill Web/React di fase CLI
❌ `graphify query` tanpa `--graph`
❌ Percaya graphify tanpa cek `--help`
❌ Tambah dependensi cloud (langgar ADR-002)
❌ Saran obfuscation (langgar ADR-001)
❌ Submit otomatis tanpa flag

## Yang Selalu Dilakukan

✅ Setiap .py: "Patuhi output-skill"
✅ Paham codebase: grep/graphify dulu
✅ Akhir sesi: update STATE.md
✅ Keputusan arsitektur: tulis ADR
✅ Fix: tunjukkan git diff
✅ Akhir task: pytest + ruff check
