# PRODUCT.md — Visi, Target, dan Bayangan Akhir FormPilot

## Elevator pitch (1 kalimat)

Asisten lokal open source yang mengisi kuisioner Google Forms secara otonom, belajar dari setiap interaksi, tanpa mengirim data ke cloud.

## Problem statement

Pengguna (mahasiswa, karyawan, anggota komunitas) sering menerima kuisioner Google Forms yang berulang: evaluasi mata kuliah, survei kepuasan, feedback acara, registrasi kegiatan. Mengisinya memakan waktu 10-30 menit per kuisioner, dan banyak pertanyaan berulang dari form ke form.

Tools yang ada (form filler browser extension) hanya mengisi field statis (nama, email), tidak bisa menjawab pertanyaan naratif atau pilihan ganda yang butuh konteks. Tools AI cloud (ChatGPT) bisa menjawab, tapi mengirim data pribadi ke server pihak ketiga.

## Target user

### Persona 1 — Mahasiswa sibuk (primary)
- Nama: Andi, 20 tahun, semester 5
- Menerima 3-5 kuisioner per minggu (evaluasi, survei, registrasi)
- Tidak punya waktu, tapi tidak ingin mengisi asal-asalan
- Peduli privasi (tidak mau data pribadi keluar)
- Tech-savvy sedang: bisa install aplikasi, tapi tidak akan coding

### Persona 2 — Pekerja kantoran (secondary)
- Nama: Budi, 28 tahun, staf HR
- Sering mengisi form internal (feedback, survei engagement)
- Ingin jawaban konsisten antar form
- Concern: data karier tidak boleh bocor

### Persona 3 — Anda sendiri (primary untuk MVP)
Anda adalah user pertama. Fase MVP dibangun untuk menyelesaikan masalah Anda. Setelah MVP terbukti, baru expand ke Persona 1 & 2 via jasa setup.

## Use case konkret

### UC-1: Kuisioner evaluasi mata kuliah
- 10 pertanyaan Likert 1-5 + 2 naratif
- Formulir sama tiap semester, hanya dosen/matkul berbeda
- FormPilot: pertama tanya skala preferensi + 2 naratif. Kedua kali: langsung isi.

### UC-2: Registrasi kegiatan kampus
- 15 pertanyaan pilihan ganda (jurusan, semester, minat, preferensi waktu)
- Formulir berubah tiap kegiatan, banyak field sama
- FormPilot: ambil dari profil (nama, NIM, jurusan, semester), tanya hal baru

### UC-3: Survei kepuasan layanan
- 8 pertanyaan Likert + 1 naratif
- FormPilot: gunakan preferensi skala dari memori, untuk naratif ambil dari jawaban sebelumnya jika relevan

### UC-4: Feedback acara
- 5 pertanyaan campuran
- FormPilot: isi cepat, user hanya review

## Prinsip produk

1. **Human-in-the-loop, bukan human-out-of-loop.** Manusia tetap memegang kendali.
2. **Privacy by design.** Data tidak pernah keluar dari laptop. Bukan opt-in, tapi arsitektur.
3. **Memori yang tumbuh, bukan diprogram.** AI tidak pre-loaded jawaban. Belajar dari interaksi.
4. **Open source bukan cuma lisensi, tapi nilai.** Kode publik, prompt publik, arsitektur publik.
5. **Setup berbayar, bukan software berbayar.** Nilai jual ada di jasa, bukan di kode terkunci.

## Non-goals (SECARA SENGAJA tidak dikerjakan)

- ❌ Form builder (hanya mengisi, tidak membuat)
- ❌ Multi-user / shared profiles (satu laptop = satu user)
- ❌ Cloud sync / backup otomatis
- ❌ Browser extension (CLI dulu, web UI kalau perlu)
- ❌ Dukungan form selain Google Forms (v1.0 hanya Google Forms)
- ❌ Auto-detect form baru dari email/WA (manual URL paste)
- ❌ OCR gambar pertanyaan
- ❌ Analisis gambar/video
- ❌ Auto-submit tanpa konfirmasi (default)

## Success metrics

### Untuk MVP (v0.1)
- Setup dari kloning → jalan < 15 menit
- Bisa handle 5 form nyata tanpa crash
- Waktu isi form turun 50% dibanding manual
- Memori relevan di 70% pertanyaan form kedua

### Untuk v1.0
- Setup < 10 menit untuk user non-teknis
- 20+ form sukses tanpa intervensi manual
- 3 user (selain Anda) memakai rutin
- 0 kebocoran data

## Bayangan akhir (final state — v1.0)

Setelah semua fase selesai, FormPilot terlihat seperti ini:

### Untuk user (non-teknis)
1. Terima link kuisioner via WA
2. Buka link, baca sebentar, copy URL
3. Buka terminal, ketik: `formpilot --url <URL>`
4. AI buka form, tampilkan preview pertanyaan
5. Jika ada yang tidak diketahui: AI tanya via terminal (batch per halaman)
6. User jawab cepat
7. AI isi semua field
8. Form terbuka di browser (mode headed), user review
9. User klik Submit sendiri
10. Selesai. Total waktu: 2-5 menit (dari 15-30 menit manual)

### Untuk developer (kontributor)
1. Clone repo, `pip install -e ".[dev]"`
2. `docs/STATE.md` tunjukkan apa yang aktif
3. `pytest` jalan
4. Bisa kontribusi di 30 menit pertama

### Untuk Anda (pemilik, model bisnis)
1. Repo GitHub publik, MIT license, 200+ stars (target)
2. README dengan demo GIF
3. Blog post "How I built local AI form filler"
4. Landing page untuk jasa setup (opsional)
5. Klien hubungi Anda: "bisa setup di laptop saya?"
6. Anda: 2 jam setup (install, tuning, training memory awal)
7. Klien bayar, dapat garansi 3 bulan
8. Klien pakai FormPilot, Anda dapat testimonial

### Untuk ekosistem
- Model kecil (7B) cukup untuk tugas ini → membuktikan AI lokal berguna untuk task sempit
- Open source penuh → orang bisa fork untuk form lain (Typeform, Microsoft Forms)
- Dokumentasi lengkap → template untuk project open source lain

## Future versions (di luar v1.0)

### v1.1 — Form support tambahan
- Typeform, Microsoft Forms, Tally (via adapter pattern)

### v1.2 — Web UI
- Halaman review lokal (localhost:5000)
- Ganti terminal interaksi dengan browser

### v2.0 — Setup service productized
- Installer otomatis (double-click)
- Model selection wizard
- Memory import/export

### Never (secara eksplisit)
- Cloud version
- API SaaS
- Subscription for cloud features

## Nada & personality

FormPilot bukan produk korporat. Project personal yang dibuka untuk publik. Komunikasinya:
- Jujur tentang keterbatasan ("ini bukan pengganti berpikir")
- Fokus pada privasi, bukan pada "AI magic"
- Tidak hype, tidak marketing-speak
- Ramah pemula, tapi tidak merendahkan

## Ringkasan 5 prinsip inti

1. **Lokal dulu.** Privasi bukan fitur, tapi fondasi.
2. **Manusia mengendalikan.** AI membantu, tidak menggantikan.
3. **Belajar, bukan diprogram.** Memori tumbuh dari interaksi nyata.
4. **Terbuka, bukan terkunci.** Kode publik, monetisasi via jasa.
5. **Sempit dulu, luas nanti.** Google Forms v1.0, ekspansi setelah terbukti.
