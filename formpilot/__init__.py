"""FormPilot — Local AI assistant for filling Google Forms autonomously.

FormPilot helps users fill Google Forms questionnaires without sending
any data to the cloud. It uses a local LLM (via Ollama), persistent
memory (SQLite + ChromaDB), and browser automation (Playwright).

Key principles:
- 100% local: no cloud API calls
- Open source: MIT license
- Human-in-the-loop: user reviews before submit
- Growing memory: AI learns from user interactions

See AGENTS.md and docs/AGENT-BRIEF.md for full context.
"""

__version__ = "0.1.0"
__author__ = "Raynato Lienardy"
__license__ = "MIT"
