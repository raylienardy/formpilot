# Changelog

All notable changes to FormPilot are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-04

First public release. FormPilot can fill Google Forms with AI-assisted
question resolution, persistent memory, and interactive CLI.

### Added
- Playwright-based Google Forms scraper (single-page + multi-page)
- Anti-bot stealth mode (msedge/chrome channel, navigator masking)
- CDP mode for login-required forms (`--cdp-url`)
- Response receipt auto-handle (Send me a copy / Simpan email saya)
- Local LLM integration via Ollama (qwen2.5:7b)
- LLM-based question resolution with <UNKNOWN> escalation
- PARAGRAPH questions always escalate to user (ADR-006)
- SQLite store for profile, sessions, pending questions
- ChromaDB vector store for narrative memory (nomic-embed-text)
- Memory priority: SQLite → ChromaDB → LLM fallback
- Interactive CLI prompt loop (`--interactive`)
- Session logging to SQLite
- Multi-page navigation with validation error detection
- Checkbox, radio, linear_scale memory validation
- Template-based prompts (text, radio, checkbox, linear scale)

### Fixed
- _is_required detection for Google Forms modern asterisk
- total_pages_estimate parsing (Halaman/Bagian/Page/Section)
- click_next detects disabled buttons and unchanged pages (no more infinite loop)
- fill_answers uses q.index not positional zip (auxiliary listitems)
- find_relevant keyword extraction for punctuation
- Checkbox detection without role=group wrapper
- ChromaDB similarity clamped to [0,1]
- Form title excluded from question extraction

### Known Limitations
- **Multi-page navigation with response receipts**: partially tested; may fail on some form configs. Single-page forms fully stable.
- Requires manual Edge/Chrome launch with `--remote-debugging-port=9222` for login forms
- Cannot handle image/video in questions (escalates to user)
- Dropdown filling not implemented (v0.1.1)
- No auto-submit (always draft mode)
- Web UI not available (v1.2+)
- Indonesian + English interface only

### Technical
- 136 unit tests + 6 integration tests
- Python 3.11+ required
- 100% local — no cloud API calls
- Open source (MIT)

## [0.0.1-dev] - 2026-11-04

Development milestone before first public release. M4 (Memory System) complete.

### Added
- Playwright scraper for Google Forms (single & multi-page)
- Anti-bot stealth mode (msedge/chrome channel, navigator masking)
- CDP mode for login-required forms (`--cdp-url`)
- Local LLM integration via Ollama (qwen2.5:7b)
- LLM-based question resolution with `<UNKNOWN>` escalation
- SQLite store for profile, sessions, pending questions
- ChromaDB vector store for narrative memory (nomic-embed-text)
- Memory priority: SQLite → ChromaDB → LLM fallback
- Interactive CLI prompt loop (`--interactive`)
- Session logging to SQLite
- Multi-page navigation with validation error detection
- Template-based prompts (text, radio, checkbox, linear scale)

### Fixed
- `_is_required()` detection for Google Forms modern asterisk
- `total_pages_estimate` parsing for "Halaman X dari Y" / "Section X of Y"
- `click_next()` now detects disabled buttons (fail fast)
- Playwright automation detection (partial mitigation)

### Known Limitations
- Requires manual Edge/Chrome launch with `--remote-debugging-port=9222` for login forms
- Cannot handle image/video in questions (escalates to user)
- Dropdown filling not implemented (Fase 5+)
- No auto-submit (always draft mode)
- Web UI not available (v1.2+)
- Indonesian + English interface only

### Technical
- 122 unit tests + 6 integration tests
- Python 3.11+ required
- 100% local — no cloud API calls
- Open source (MIT)
