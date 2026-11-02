# REQUIREMENTS.md — Keperluan Hardware, Software, Skill

## 1. Hardware minimum

| Komponen | Minimum | Rekomendasi | Kenapa |
| :--- | :--- | :--- | :--- |
| RAM | 16 GB | 32 GB | Model 7B quantized butuh ~6-8 GB free |
| CPU | 4 core modern | 8 core | Inference + Playwright |
| Storage | 10 GB free | 20 GB | Model + Chroma + browser + venv |
| GPU | Tidak wajib | NVIDIA 6GB+ VRAM | Percepat inference 2-5x |
| OS | Windows 10 / macOS 12 / Ubuntu 22.04 | Windows 11 / macOS 14 / Ubuntu 24.04 | Support baik |

### Tanpa GPU: model apa?
- 16 GB RAM → `qwen2.5:7b` (~4.5 GB)
- 32 GB RAM → `qwen2.5:14b` (~9 GB) — kualitas lebih baik
- `< 16 GB RAM` → **TIDAK disarankan**. Model 3B terlalu kecil untuk tugas ini.

### Dengan GPU (NVIDIA):
- 6-8 GB VRAM → model 7B full di GPU (sangat cepat)
- 12+ GB VRAM → model 14B di GPU

## 2. Software yang harus diinstall

### Wajib
| Software | Versi | Fungsi | Command install (Windows) |
| :--- | :--- | :--- | :--- |
| Python | 3.11+ | Runtime | python.org installer |
| Git | 2.40+ | Version control | git-scm.com |
| Ollama | Latest | Local LLM runtime | ollama.com/download |
| PowerShell | 5.1+ | Terminal | built-in |

### Opsional (development)
- VS Code / PyCharm Community
- Windows Terminal

### Yang diinstall via pip
- playwright, chromadb, ollama (client), pydantic, pyyaml, rich, pytest, ruff

### Yang diinstall via Playwright
- Chromium browser

### Yang di-download via Ollama
- `qwen2.5:7b` (~4.5 GB)
- `nomic-embed-text` (~274 MB, untuk embedding)

**Total download:** ~5-6 GB (pertama kali)

## 3. Network requirements

### Setup pertama
- Python installer (~30 MB)
- Git installer (~60 MB)
- Ollama installer (~700 MB)
- Model download (5-6 GB)
- pip packages (~200 MB)
- Playwright Chromium (~150 MB)

**Total download awal:** ~6-7 GB, butuh internet stabil, ~30-60 menit.

### Setelah setup
- **Tidak butuh internet.** Semua jalan offline.
- Pengecualian: Google Forms harus bisa diakses (dari browser).

**Ini keuntungan utama FormPilot:** setelah setup, bisa jalan di mana saja.

## 4. Skill requirements

### Untuk user (yang mau pakai)
- Bisa install aplikasi Windows
- Bisa buka terminal
- Bisa copy-paste command
- **Tidak perlu coding**

Setara orang yang pernah install Office atau game.

### Untuk setup person (Anda)
- Semua di atas
- Bisa troubleshoot: cek `ollama list`, cek log error
- Paham konsep dasar: virtualenv, pip, model size vs RAM

Setara sysadmin junior.

### Untuk kontributor
- Python 3.11+ intermediate
- Playwright basic
- Pydantic familiarity
- Git branching
- Testing dengan pytest

Setara mahasiswa semester 4 informatika.

## 5. Time requirements

### Setup pertama (end-user)
| Step | Estimasi |
| :--- | :--- |
| Download Python + Git + Ollama | 15 menit |
| Install | 10 menit |
| Pull Ollama models | 10-20 menit (koneksi-dependent) |
| Clone repo | 1 menit |
| pip install + playwright install | 5 menit |
| Config file | 2 menit |
| **Total setup** | **45-60 menit** |

**Ini sebabnya jasa setup punya nilai.** 45-60 menit setup = waktu user yang bisa dihemat.

### Per-form usage (setelah setup)
| Step | Estimasi |
| :--- | :--- |
| Buka link, verifikasi, copy URL | 30 detik |
| Jalankan CLI | 5 detik |
| AI extract + cek memory | 10-30 detik |
| User jawab needs_cli (batch) | 30 detik - 2 menit |
| AI isi form | 10-20 detik |
| User review & submit | 30 detik - 1 menit |
| **Total per form** | **2-5 menit** |

**Dibanding manual (15-30 menit), penghematan 80-90%.**

### Development time (Anda)
Lihat `docs/ROADMAP.md`. **Total MVP (Fase 0-6):** 30-40 jam kerja terfokus.

Realistis: 3-4 minggu kalau kerja santai, 1-2 minggu kalau fokus.

## 6. Environment checklist

Sebelum mulai development:

- [ ] Python 3.11+ terinstall (`python --version`)
- [ ] Git terinstall (`git --version`)
- [ ] Ollama terinstall dan jalan (`ollama list`)
- [ ] Model sudah di-pull
- [ ] RAM ≥ 16 GB
- [ ] Storage ≥ 10 GB free
- [ ] Bisa akses https://github.com
- [ ] Bisa akses https://docs.google.com

Jika semua ✓, siap mulai.

## 7. Known limitations

### Teknis
- Model 7B tidak sepandai GPT-4
- Playwright bisa rusak kalau Google Forms ubah DOM
- Form dengan gambar/video tidak bisa dianalisis
- Form SSO butuh intervensi user
- Windows Defender kadang flag installer Ollama

### Etis
- Mengisi kuisioner evaluasi dosen dengan AI bisa dianggap pelanggaran akademik
- User wajib tahu implikasi ini sebelum pakai
- FormPilot tidak mencegah penyalahgunaan, tapi tidak memfasilitasi

### Bisnis
- Kode open source → siapa saja bisa clone
- Yang dibayar adalah jasa setup
- Tidak ada proteksi teknis terhadap copy

## 8. FAQ singkat

**Q: Bisa jalan di 8 GB RAM?**
A: Bisa dengan model 3B, tapi kualitas rendah. Tidak disarankan.

**Q: Pakai model lain selain qwen2.5?**
A: Ya. Configurable. Rekomendasi: llama3.1:8b, mistral:7b.

**Q: Butuh API key?**
A: Tidak. Tidak ada.

**Q: Bisa offline total?**
A: Setelah setup, ya.

**Q: Biaya operasional?**
A: Rp 0. Semua lokal.

**Q: Kalau laptop rusak?**
A: Backup manual `memory.db` + `chroma/`. Tidak ada cloud sync.

**Q: Bisa dipakai di HP?**
A: Tidak, ini desktop. Web UI di masa depan (opsional).
