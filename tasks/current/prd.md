# PRD — Iterasi 1: Playwright Ekstraksi Single-Page

**Status:** Belum dimulai
**Target sesi:** Sesi 2-3
**Prasyarat:** Fondasi Sesi 1 selesai.

## 1. Tujuan

Buktikan Playwright bisa buka Google Form **1 halaman**, ekstrak semua pertanyaan, cetak ke terminal terstruktur.

**Belum ada AI. Belum ada memori. Belum ada pengisian.** Iterasi ini validasi scraper.

## 2. Non-Goals

- ❌ Ollama (brain.py tidak disentuh)
- ❌ SQLite/ChromaDB (memory/ tidak disentuh)
- ❌ Pengisian jawaban (fill_answers)
- ❌ Multi-halaman
- ❌ CLI Rich (pakai print)
- ❌ Deteksi pertanyaan bergambar
- ❌ --auto-submit
- ❌ Login/session

## 3. Deliverables

### 3.1 pyproject.toml

```toml
[project]
name = "formpilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "playwright>=1.40",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 3.2 formpilot/__init__.py — kosong dengan docstring

### 3.3 formpilot/memory/schema.py

```python
class FieldType(str, Enum):
    SHORT_TEXT = "short_text"
    PARAGRAPH = "paragraph"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    LINEAR_SCALE = "linear_scale"
    UNKNOWN = "unknown"

class Question(BaseModel):
    index: int
    text: str
    field_type: FieldType
    options: list[str] = []
    required: bool = False
    has_media: bool = False

class ExtractedForm(BaseModel):
    url: str
    page_number: int
    questions: list[Question]
    is_last_page: bool
```

### 3.4 formpilot/scraper.py

Fungsi wajib:
```python
def open_form(url, headless=True) -> Page: ...
def extract_questions(page, page_number=1) -> ExtractedForm: ...
def is_last_page(page) -> bool: ...
def close(page) -> None: ...
```

`fill_answers`, `click_next`, `click_submit`, `has_validation_error` ditunda.

### 3.5 formpilot/__main__.py

`python -m formpilot --url "..."` → buka form, ekstrak, cetak JSON, tutup.

### 3.6 tests/test_scraper.py

- `test_extract_single_page`
- `test_detect_last_page`

## 4. Acceptance Criteria

1. `pip install -e ".[dev]"` berhasil
2. `playwright install chromium` berhasil
3. `python -m formpilot --url "<form-1-halaman>"` cetak JSON
4. JSON berisi `text`, `field_type`, `options`, `required`
5. `pytest -v` lulus
6. `ruff check` bersih
7. `docs/STATE.md` diperbarui
8. `git diff` ditunjukkan ke user

## 5. Test Plan Manual

1. Form 1 pertanyaan teks
2. Form 1 radio 4 opsi
3. Form campuran 5 pertanyaan
4. Form dengan gambar (`has_media=True`)

## 6. Risiko

| Risiko | Mitigasi |
| :--- | :--- |
| Google Forms DOM berubah | Pakai `role="listitem"`, `role="heading"` |
| Playwright timeout | config `timeout_ms` 30 detik |
| Format tak dikenal | `FieldType.UNKNOWN` |
| Test butuh online | Fixture HTML lokal |

## 7. Estimasi

Sesi 2: 2-3 jam. Sesi 3: 3-4 jam.

## 8. Setelah Iterasi

Update STATE.md. Usulkan PRD Iterasi 2. Jangan lanjut tanpa izin.
