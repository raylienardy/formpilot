# Arsitektur FormPilot

Peta teknis. Setiap perubahan wajib update ini DAN tambah ADR.

---

## 1. Peta Modul

```
+---------------------+
|      cli.py         |  Entry point. Orkestrasi scraper + brain.
+----------+----------+
           |
     +-----+-----+
     v           v
+----------+  +----------+
|scraper.py|  | brain.py |
|Playwright|  | Ollama   |
+----------+  +-----+----+
                    |
                    v
              +-----------+
              | memory/   |
              |sqlite+    |
              |chroma     |
              +-----------+
```

---

## 2. Tanggung Jawab Modul

### `formpilot/cli.py`
- Parse argumen (`--url`, `--mode`, `--config`, `--auto-submit`)
- Muat config via `utils/config_loader.py`
- Loop per halaman: minta scraper ekstrak, brain resolve, tampilkan needs_cli via Rich
- Simpan jawaban user ke memory
- Mode draft: berhenti sebelum submit. Mode auto: submit.

### `formpilot/scraper.py`
- Playwright buka form (headless default)
- Ekstrak pertanyaan per halaman (Google Forms multi-halaman)
- Deteksi tipe: short_text, paragraph, radio, checkbox, dropdown, linear_scale
- Deteksi `has_media`
- Isi field
- Klik Next/Submit, tunggu `networkidle`
- Deteksi validasi error

Kontrak:
```python
def open_form(url, headless=True) -> Page: ...
def extract_questions(page, page_number=1) -> ExtractedForm: ...
def fill_answers(page, answers) -> None: ...
def click_next(page) -> bool: ...
def is_last_page(page) -> bool: ...
def click_submit(page) -> None: ...
def has_validation_error(page) -> str | None: ...
def close(page) -> None: ...
```

### `formpilot/brain.py`
- Terima questions dari scraper
- Cek sqlite_store (faktual) → vector_store (naratif) → Ollama
- Flag `needs_cli=True` jika tidak yakin
- Return answers ke cli

Kontrak:
```python
def resolve_questions(questions) -> list[Answer]: ...
def generate_answer(question, context) -> str: ...
```

### `formpilot/memory/sqlite_store.py`
- Skema SQLite profil faktual
- CRUD: `get_profile_field`, `set_profile_field`, `get_all_profile`
- `find_relevant(question_text) -> list[MemoryHit]` (keyword match)

### `formpilot/memory/vector_store.py`
- ChromaDB di `chroma/`
- Koleksi `answers`
- `add_answer(question, answer)`, `search_similar(question, top_k=5)`
- Embedding via Ollama (`nomic-embed-text`)

### `formpilot/memory/schema.py`
- Pydantic models: `Question`, `Answer`, `MemoryHit`, `FormSession`

### `formpilot/utils/config_loader.py`
- Baca `config/production.yaml` + `.env`
- Validasi Pydantic `AppConfig`

### `formpilot/utils/logger.py`
- Logging console (INFO) + file `logs/formpilot.log` (DEBUG)

### `formpilot/prompts/`
- Template prompt (publik). Tuning klien di `config/production.yaml` (di-ignore).

---

## 3. Aliran Data per Halaman

```
1. cli.py → scraper.open_form(url)
2. Per halaman:
   a. scraper.extract_questions(page)
   b. brain.resolve_questions(questions) → answers
   c. Untuk needs_cli=True: tampilkan via Rich, tunggu input
   d. Simpan jawaban user ke memory
   e. scraper.fill_answers(page, answers)
   f. Cek validation error
   g. Jika is_last_page: break
   h. scraper.click_next(page)
3. Mode draft: tunggu review. Mode auto: submit.
```

---

## 4. Skema Database

### 4.1 SQLite (`memory.db`)

```sql
CREATE TABLE IF NOT EXISTS profile (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    category    TEXT,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    started_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at  TIMESTAMP,
    mode         TEXT,
    status       TEXT,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS pending_questions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER REFERENCES sessions(id),
    page_number  INTEGER,
    question_text TEXT NOT NULL,
    user_answer  TEXT,
    answered_at  TIMESTAMP
);
```

Contoh `profile`: `nama_lengkap`, `nim`, `jurusan`, `semester`, `preferensi_skala`.

### 4.2 ChromaDB (`chroma/`)

Koleksi `answers`: `{question, answer, embedding, category, timestamp}`.

**Aturan simpan:**
- < 100 karakter, faktual → SQLite
- ≥ 100 karakter atau mengandung "karena/agar/menurut" → ChromaDB
- Ragu → tanya user

---

## 5. Konfigurasi (`config/production.yaml`)

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "qwen2.5:7b-instruct"
  embedding_model: "nomic-embed-text"
  temperature: 0.3
  timeout_seconds: 60

browser:
  headless: true
  user_data_dir: "./state/browser_profile"
  timeout_ms: 30000

memory:
  sqlite_path: "./memory.db"
  chroma_path: "./chroma"

cli:
  auto_submit: false
  batch_questions: true
  language: "id"

logging:
  level: "INFO"
  file: "./logs/formpilot.log"
```

---

## 6. Penanganan Error

| Skenario | Perilaku |
| :--- | :--- |
| Ollama tidak jalan | cek `ollama list`, exit 2 |
| Model belum pull | saran `ollama pull`, exit 2 |
| Timeout load | retry 2x, raise `ScraperTimeoutError` |
| Validasi gagal | laporkan, tunggu user |
| Pertanyaan bergambar | `needs_human=True` |
| ChromaDB korup | exit 3, saran backup |
| SQLite lock | retry 3x backoff |

Exit codes: 0 sukses, 1 error umum, 2 dependensi, 3 memory.

---

## 7. Non-Goals Arsitektur

- Tidak ada retry otomatis untuk submit
- Tidak ada paralelisasi
- Tidak ada cloud storage
- Hanya Google Forms
- Tidak ada dukungan pertanyaan bergambar
