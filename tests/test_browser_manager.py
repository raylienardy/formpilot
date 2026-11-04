"""Tests for browser_manager.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from formpilot.browser_manager import (
    BrowserError,
    BrowserInfo,
    detect_browsers,
    launch_browser,
    resolve_browser_from_arg,
)


def test_detect_browsers_returns_list():
    """Detection returns a list (may be empty on test machine)."""
    result = detect_browsers()
    assert isinstance(result, list)
    for b in result:
        assert isinstance(b, BrowserInfo)


def test_detect_browsers_sorted_by_priority():
    """Detected browsers sorted Edge first."""
    result = detect_browsers()
    if len(result) >= 2:
        priorities = [b.priority for b in result]
        assert priorities == sorted(priorities)


def test_resolve_browser_from_path(tmp_path):
    """Absolute path to existing file accepted."""
    fake_exe = tmp_path / "fake-browser.exe"
    fake_exe.write_text("dummy")
    result = resolve_browser_from_arg(str(fake_exe))
    assert result.name == "custom"
    assert result.executable == fake_exe


def test_resolve_browser_from_invalid_path():
    """Invalid path raises BrowserError."""
    with pytest.raises(BrowserError, match="not found"):
        resolve_browser_from_arg("/nonexistent/path/to/browser.exe")


def test_resolve_browser_unknown_name():
    """Unknown browser name raises BrowserError."""
    with pytest.raises(BrowserError):
        resolve_browser_from_arg("firefox-never-installed")


def test_resolve_browser_from_none_uses_menu(monkeypatch):
    """None triggers pick_browser (menu)."""
    monkeypatch.setattr(
        "formpilot.browser_manager.detect_browsers",
        lambda: [],
    )
    with pytest.raises(BrowserError, match="No Chromium-family"):
        resolve_browser_from_arg(None)


def test_launch_browser_creates_profile_dir(tmp_path):
    """launch_browser creates profile dir if missing."""
    fake_exe = tmp_path / "fake-browser.exe"
    fake_exe.write_text("dummy")
    browser = BrowserInfo(
        name="custom",
        display_name="Fake Browser",
        executable=fake_exe,
        priority=99,
    )
    profile = tmp_path / "profile"
    assert not profile.exists()

    with patch("formpilot.browser_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value = object()
        launch_browser(browser, profile, debug_port=9999)

    assert profile.exists()


def test_launch_browser_args_correct(tmp_path):
    """launch_browser passes correct args to subprocess."""
    fake_exe = tmp_path / "fake-browser.exe"
    fake_exe.write_text("dummy")
    browser = BrowserInfo(
        name="custom",
        display_name="Fake Browser",
        executable=fake_exe,
        priority=99,
    )
    profile = tmp_path / "profile"

    with patch("formpilot.browser_manager.subprocess.Popen") as mock_popen:
        mock_popen.return_value = object()
        launch_browser(browser, profile, debug_port=9999)

    call_args = mock_popen.call_args[0][0]
    assert str(fake_exe) in call_args
    assert "--remote-debugging-port=9999" in call_args
    assert f"--user-data-dir={profile}" in call_args
