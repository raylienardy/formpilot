"""Tests for __main__.py interactive CLI integration.

Tests flag validation only — does NOT run full main() (needs browser+Ollama).
"""

from __future__ import annotations

import subprocess
import sys


def _run_main(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "formpilot", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def test_interactive_requires_ai():
    """--interactive without --ai fails fast."""
    result = _run_main("--url", "https://example.com", "--interactive")
    assert result.returncode == 1
    assert "--interactive requires --ai" in result.stderr


def test_interactive_conflicts_with_dummy_fill():
    """--interactive and --dummy-fill cannot coexist."""
    result = _run_main(
        "--url", "https://example.com",
        "--ai", "--interactive", "--dummy-fill",
    )
    assert result.returncode == 1
    assert "mutually exclusive" in result.stderr


def test_dummy_fill_still_requires_ai():
    """Regression: --dummy-fill alone without --ai still fails."""
    result = _run_main("--url", "https://example.com", "--dummy-fill")
    assert result.returncode == 1
    assert "--dummy-fill requires --ai" in result.stderr


def test_interactive_help_shows_flag():
    """--help mentions --interactive."""
    result = _run_main("--help")
    assert result.returncode == 0
    assert "--interactive" in result.stdout
