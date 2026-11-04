# FormPilot

Local AI assistant that fills Google Forms autonomously, with a persistent
memory that learns from you. 100% offline, 100% open source.

**Version:** v0.1.0 (released 2026-11-04) · [Changelog](CHANGELOG.md)

---

## What it does

You receive a questionnaire link. You verify it's a real questionnaire.
You run `python -m formpilot --url <link>`. FormPilot:
- Opens the form in your browser (single-page or multi-page)
- Extracts questions (text, radio, checkbox, dropdown, linear scale)
- Answers from memory (SQLite facts + ChromaDB narratives)
- Prompts you interactively when it doesn't know (memory grows)
- Fills the form and stops before submit (draft mode)

Next time you see a similar form, memory answers automatically.

## Principles

- **100% local.** No cloud API. Ollama runs on localhost. Data stays on your laptop.
- **Open source (MIT).** All code, prompts, docs public. Monetized via setup service.
- **Human-in-the-loop.** You verify the form link. You answer what AI can't. You click submit.
- **Memory grows.** AI starts empty. Learns from your answers. Next run auto-fills.

## Stack

| Component | Tech | Purpose |
| :--- | :--- | :--- |
| Language | Python 3.11+ | Runtime |
| Browser | Playwright Chromium + CDP | Open form, extract, fill, navigate |
| LLM | Ollama + `qwen2.5:7b` | Understand questions, resolve answers |
| Embeddings | Ollama + `nomic-embed-text` | Semantic memory |
| Memory (facts) | SQLite | Profile, sessions, pending questions |
| Memory (narrative) | ChromaDB | Paragraph answers, semantic search |
| CLI | Rich | Interactive prompts |

## Install

Prerequisites: Python 3.11+, Git, Ollama installed and running (`ollama serve`).

```bash
git clone https://github.com/raylienardy/formpilot.git
cd formpilot

# Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows
# source .venv/bin/activate       # Linux/Mac

# Install project + dev deps
pip install -e ".[dev]"

# Install Chromium for Playwright
playwright install chromium

# Pull Ollama models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Copy config
Copy-Item config/example.yaml config/production.yaml
Copy-Item config/example.env .env
```

Edit `config/production.yaml` if your Ollama URL or model differs.

## Usage

### 1. For public forms (no login required)

```bash
python -m formpilot --url "https://docs.google.com/forms/d/e/xxx/viewform" --ai --use-memory --interactive --headed
```

### 2. For login-required forms (campus questionnaires)

Google Forms with "Limit to 1 response" or "Collect email addresses" require login. Use CDP mode:

```bash
# Launch Edge with remote debugging (in one terminal)
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\formpilot-profile"

# In the Edge window: login Google, open form, verify you can type manually
# Then (in another terminal):
python -m formpilot --url "https://docs.google.com/forms/d/e/xxx/viewform" --ai --use-memory --interactive --cdp-url "http://127.0.0.1:9222"
```

### 3. No AI (extract only)

```bash
python -m formpilot --url "..." 
```

### 4. Dummy fill (testing without interactive prompts)

```bash
python -m formpilot --url "..." --ai --use-memory --dummy-fill
```

## CLI flags

| Flag | Purpose |
| :--- | :--- |
| `--url` | Google Forms URL (required) |
| `--ai` | Enable LLM resolution (Ollama must run) |
| `--use-memory` | Enable SQLite + ChromaDB memory |
| `--interactive` | Prompt user for needs_cli questions (requires `--ai`) |
| `--dummy-fill` | Fill needs_cli with placeholders (testing only, conflicts with `--interactive`) |
| `--cdp-url` | Attach to existing browser via CDP (for login forms) |
| `--headed` | Run browser with UI |
| `--config` | Config file path (default: `./config/production.yaml`) |

## Known limitations (v0.1.0)

- **Multi-page navigation**: best-effort. May fail on some response-receipt configs. Single-page fully stable.
- **Login-required forms**: requires manual Edge launch with `--remote-debugging-port=9222` and Google login.
- **Dropdown filling**: not implemented yet (v0.1.1).
- **Image/video in questions**: not analyzed; escalates to you via CLI.
- **No auto-submit**: always draft mode. You click Submit in browser.
- **Web UI**: not available (v1.2+).

## Setup service

If you can't set this up yourself (Ollama tuning, model selection, prompt engineering, initial memory training), I offer setup as a service. Contact [@raylienardy](https://github.com/raylienardy) for details.

## License

MIT. See [LICENSE](LICENSE).