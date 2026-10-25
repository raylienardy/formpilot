# FormPilot

Asisten lokal berbasis AI untuk mengisi Google Forms secara otonom, dengan memori persisten yang belajar dari pengguna.

**Status:** Fase scaffolding. Belum ada kode fungsional. Lihat `tasks/current/prd.md`.

---

## Prinsip Project

1. **100% lokal.** Tidak ada data yang dikirim ke cloud. LLM berjalan via Ollama di laptop pengguna, memori disimpan di SQLite + ChromaDB lokal.
2. **Open source penuh (MIT).** Semua kode, prompt, dan dokumentasi arsitektur publik. Monetisasi via jasa setup — lihat `docs/DECISIONS.md` ADR-001.
3. **Human-in-the-loop.** Pengguna memverifikasi bahwa sebuah link adalah kuisioner sebelum AI menyentuhnya. Pengguna juga menjadi sumber data ketika AI tidak yakin.
4. **Memori yang tumbuh.** AI mulai dari kosong. Setiap pertanyaan yang tidak bisa dijawab akan ditanyakan ke pengguna via CLI, lalu disimpan ke memori.

---

## Stack

| Komponen | Teknologi | Fungsi |
| :--- | :--- | :--- |
| Bahasa | Python 3.11+ | Runtime utama |
| Otomasi browser | Playwright (Chromium) | Buka form, ekstrak, isi, klik Next/Submit |
| LLM lokal | Ollama (default: `qwen2.5:7b-instruct`) | Memahami pertanyaan, menyusun jawaban |
| Memori terstruktur | SQLite | Profil faktual (nama, NIM, jurusan, semester) |
| Memori semantik | ChromaDB | Jawaban naratif (motivasi, opini, saran) |
| CLI | Rich (Python) | Interaksi dua arah |
| Konfigurasi | YAML + env vars | Pengaturan mesin & model |

---

## Cara Jalan (setelah kode ada)

```bash
# 1. Clone
git clone <repo-url> formpilot
cd formpilot

# 2. Virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Dependensi
pip install -r requirements.txt
playwright install chromium

# 4. Model Ollama
ollama pull qwen2.5:7b-instruct

# 5. Config
cp config/example.yaml config/production.yaml
cp config/example.env .env

# 6. Jalankan
python -m formpilot.cli --url "https://docs.google.com/forms/d/e/..."
```

Detail perintah: `docs/commands.md`.

---

## Model Bisnis

Kode open source penuh. Nilai jual adalah **jasa setup**: instalasi, pemilihan model sesuai laptop, tuning prompt, sesi pengisian memori awal. Lihat `docs/DECISIONS.md` ADR-001.

---

## Lisensi

MIT.
