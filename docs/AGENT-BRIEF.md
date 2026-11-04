# AGENT-BRIEF.md — Handbook untuk AI Agent

Halo, agent. Kamu baru membuka sesi di project **FormPilot**. Dokumen ini adalah briefing lengkap agar kamu langsung paham konteks, batasan, dan langkah berikutnya — tanpa perlu user menjelaskan ulang dari nol.

**Baca dokumen ini sampai selesai. Butuh 5 menit. Menghemat 30 menit kebingungan.**

---

## 1. Apa itu FormPilot (30 detik)

Asisten lokal yang mengisi Google Forms dengan AI (v0.1.0 released 2026-11-04).
- User terima link kuisioner → verifikasi manual → jalankan CLI → AI isi form
- AI mulai dari memori KOSONG, lalu belajar dari jawaban user via CLI
- Kuisioner berikutnya: AI pakai memori, hanya tanya hal baru
- 100% lokal (Ollama), 100% open source (MIT)
- Status: v0.1.0 (single-page stable, multi-page best-effort)

---

## 2. Action saat buka sesi baru (WAJIB)

Baca dalam urutan ini, JANGAN dilompati:

1. `CHANGELOG.md` — versi terbaru (v0.1.0) dan fitur yang sudah rilis
2. `docs/STATE.md` — apa yang selesai, apa berikutnya, ada blocker?
3. `tasks/current/prd.md` — scope iterasi/fase yang sedang aktif
4. `docs/INDEX.md` — navigasi dokumen lain jika perlu detail
5. `docs/architecture.md` — peta modul (jika akan ubah kode)

Setelah baca, konfirmasi ke user: "Saya sudah baca STATE.md dan PRD. Saat ini kita di fase X, berikutnya Y. Siap lanjut?"

**JANGAN menulis kode sebelum 4 dokumen di atas dibaca.**

---

## 3. Prinsip inti (TIDAK BISA dilanggar)

### P1 — 100% lokal
Tidak ada API cloud: OpenAI, Anthropic, Gemini, Firebase, Supabase cloud, atau semacamnya. Semua LLM via Ollama. Semua memori di SQLite + ChromaDB lokal.

### P2 — Open source penuh (MIT)
JANGAN sarankan obfuscation, PyArmor, license binding, atau menyembunyikan logika. Kode harus tetap terbaca. Nilai bisnis ada di jasa setup (lihat ADR-001).

### P3 — Human-in-the-loop
AI tidak pernah submit form tanpa review user, kecuali flag `--auto-submit` eksplisit. AI juga tidak menyentuh link tanpa user verifikasi manual dulu.

### P4 — Memori tumbuh dari interaksi
AI mulai kosong. Setiap jawaban user disimpan ke memory. JANGAN hardcode jawaban atau pre-populate memori tanpa persetujuan user.

### P5 — Fase tidak dilompati
Setiap fase punya PRD di `tasks/current/prd.md`. Non-goals di PRD mengikat. Jika tergoda menambah fitur di luar scope, BERHENTI dan tanya user.

---

## 4. Workflow standar per task

### Task: Implementasi fitur baru
1. Baca `docs/STATE.md` + PRD aktif
2. Baca `docs/architecture.md` bagian modul terkait
3. **Patuhi output-skill** — tulis file .py PENUH, no truncate
4. Implementasi
5. Test dengan `pytest` (jika test framework sudah ada)
6. Update `docs/STATE.md` di akhir

### Task: Bug fixing
1. Baca STATE.md → reproduksi bug
2. Cari akar masalah (jangan patch gejala)
3. Fix
4. Test regresi
5. Catat di STATE.md

### Task: Audit / review
1. Minta laporan dulu, JANGAN langsung fix
2. Setelah user approve, fix 3 isu teratas saja
3. JANGAN over-engineer

### Task: Refactor
1. Cek dependensi dulu (`grep` atau `graphify affected`)
2. Refactor
3. Update semua pemanggil
4. Test
5. Tulis ADR baru di `docs/DECISIONS.md` jika mengubah arsitektur

---

## 5. Aturan keras (JANGAN DILANGGAR)

- ❌ `# ...`, `# sisa kode sama`, `# rest of code` saat tulis file
- ❌ Menambah dependensi cloud
- ❌ Submit form otomatis tanpa flag `--auto-submit`
- ❌ Commit file di `.gitignore` (data/, state/, config/production.yaml, .env, memory.db, chroma/)
- ❌ Ubah skema DB tanpa update docs/architecture.md
- ❌ Lompati fase / kerjakan non-goals tanpa izin
- ❌ Ubah ADR tanpa diskusi eksplisit dengan user
- ❌ Menebak keputusan bisnis/arsitektur
- ❌ Sarankan obfuscation / anti-copy

---

## 6. Anti-pattern

❌ Baca dokumen panjang-panjang di awal sesi (boros token). Baca STATE.md + PRD dulu, sisanya on-demand.
❌ Menulis kode sebelum baca STATE.md
❌ Menambah "fitur bagus" tanpa diminta — melanggar P5
❌ Auto-commit tanpa persetujuan user
❌ Menghapus test yang gagal (perbaiki, jangan hapus)
❌ Skip output-skill — output akan terpotong

---

## 7. Cara mengakhiri sesi (WAJIB)

1. Update `docs/STATE.md` dengan format yang ada di file tersebut
2. Jika ada keputusan arsitektur baru, tambah ADR di `docs/DECISIONS.md`
3. Tunjukkan `git diff` ringkas ke user
4. JANGAN push. JANGAN commit tanpa izin user.
5. Konfirmasi: "Sesi selesai. Berikutnya: [X]. Silakan review diff sebelum commit."

---

## 8. Di mana detail lebih lanjut

| Butuh | Baca |
| :--- | :--- |
| Visi produk & target akhir | `docs/PRODUCT.md` |
| Roadmap & milestone | `docs/ROADMAP.md` |
| Detail step-by-step tiap fase | `docs/PHASES.md` |
| Hardware & software | `docs/REQUIREMENTS.md` |
| Arsitektur & modul | `docs/architecture.md` |
| Keputusan yang sudah dikunci | `docs/DECISIONS.md` |
| Skill yang aktif | `docs/SKILLS-ADAPTED.md` |
| Perintah CLI | `docs/commands.md` |
| Peta semua dokumen | `docs/INDEX.md` |

---

## 9. Kalau ragu

**Selalu tanya user.** Jangan menebak. Jangan "menurut saya". Jangan "praktik umumnya". FormPilot punya keputusan yang sengaja dibuat berbeda dari default (misal: open source padahal ada risiko copy). Hormati itu.

Selamat bekerja. Kamu sekarang sudah tahu konteksnya.
