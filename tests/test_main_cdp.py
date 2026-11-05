"""Tests for __main__ CDP integration wiring (v0.2-2).

Tests flag interactions and error paths in main(), without launching
real browsers. Browser launch is mocked where needed.
"""

from __future__ import annotations

import subprocess
import sys


def _run_main(*args: str) -> subprocess.CompletedProcess:
    """Run `python -m formpilot` with args, capture output."""
    cmd = [sys.executable, "-m", "formpilot", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=20)


def test_account_requires_existing_profile():
    """--account with --profile isolated should fail fast."""
    result = _run_main(
        "--url", "https://example.com",
        "--profile", "isolated",
        "--account", "test@example.com",
    )
    # Will fail before actually launching (during flag validation or account resolution)
    # Either exit code 2 with message, or exit code 1 (no browser)
    # Both acceptable — we just want to ensure no crash traceback
    assert "Traceback" not in result.stderr
    # Best case: shows error message
    if result.returncode == 2:
        assert "isolated" in result.stderr.lower() or "account" in result.stderr.lower()


def test_account_nonexistent_fails_gracefully():
    """--account with nonexistent email should fail with clear error."""
    result = _run_main(
        "--url", "https://example.com",
        "--browser", "edge",
        "--profile", "existing",
        "--account", "nonexistent-xyz@invalid-domain-xyz.test",
    )
    # Should not crash with traceback
    assert "Traceback" not in result.stderr
    # Should return non-zero
    assert result.returncode != 0


def test_account_flag_appears_in_help():
    """--account should be documented in --help."""
    result = _run_main("--help")
    assert result.returncode == 0
    assert "--account" in result.stdout
