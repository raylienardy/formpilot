# Perintah FormPilot

Dijalankan dari root project dengan virtualenv aktif.

## Setup Awal

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
cp config/example.yaml config/production.yaml
cp config/example.env .env
```

## Menjalankan

```bash
# Draft (default)
python -m formpilot.cli --url "https://docs.google.com/forms/d/e/..."

# Auto-submit (hati-hati)
python -m formpilot.cli --url "..." --auto-submit

# Browser terlihat (debug)
python -m formpilot.cli --url "..." --headed

# Config custom
python -m formpilot.cli --url "..." --config ./config/production.yaml
```

### CLI flags reference (v0.1.0)

| Flag | Purpose | Notes |
| :--- | :--- | :--- |
| `--url` | Google Forms URL | Required |
| `--ai` | Enable LLM resolution | Ollama must run; model from config |
| `--use-memory` | Enable SQLite + ChromaDB | Required for memory & session log |
| `--interactive` | Prompt user for needs_cli | Requires `--ai`; conflicts with `--dummy-fill` |
| `--dummy-fill` | Fill with placeholders | Testing only; requires `--ai` |
| `--cdp-url` | Attach via CDP | For login-required forms; Edge with `--remote-debugging-port=9222` |
| `--headed` | Visible browser | Default headless |
| `--config` | Config path | Default `./config/production.yaml` |

### Interactive mode details

When `--interactive` runs and brain returns `needs_cli=True`, FormPilot:
1. Shows Rich panel with question (type, options if any)
2. Prompts for input (validates against options for radio/checkbox/scale)
3. Saves answer to memory (facts → SQLite, narratives → ChromaDB)
4. Applies answer to form field
5. Continues to next needs_cli question or next page

### Response receipts handling

If form has "Send me a copy of my responses" / "Simpan email saya" toggle,
FormPilot auto-checks it on page 1 (works in CDP mode with logged-in user).

## Development

```bash
ruff check formpilot/ tests/
ruff format formpilot/ tests/
pytest -v
pytest --cov=formpilot --cov-report=term-missing
```

## Debugging

```bash
curl http://localhost:11434/api/tags
ollama list
tail -f logs/formpilot.log
```

## Memory

```bash
sqlite3 memory.db "SELECT * FROM profile;"
sqlite3 memory.db "SELECT * FROM sessions ORDER BY id DESC LIMIT 10;"
cp -r memory.db chroma/ backups/$(date +%Y%m%d)/
rm memory.db && rm -rf chroma/   # HATI-HATI
```

## Git

```bash
git status
git add .
git commit -m "<tipe>: <deskripsi>"
```

Tipe commit: feat, fix, docs, chore, refactor, test.

### Interactive Mode (Fase 4)

Prompt user untuk pertanyaan yang AI tidak bisa jawab (`needs_cli=True`). Jawaban otomatis disimpan ke memory untuk sesi berikutnya.

```bash
# First run: AI tanya NIM/jurusan, user jawab, jawaban disimpan
python -m formpilot --url "https://docs.google.com/forms/d/e/xxx/viewform" --ai --use-memory --interactive --cdp-url "http://127.0.0.1:9222"

# Second run: memory menjawab otomatis, tanpa prompt
python -m formpilot --url "..." --ai --use-memory --interactive --cdp-url "..."
```

**Catatan:** `--interactive` requires `--ai`, mutually exclusive dengan `--dummy-fill`.

