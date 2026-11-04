"""Tests for profile_manager.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from formpilot.browser_manager import BrowserInfo
from formpilot.profile_manager import (
    ProfileError,
    get_existing_profile_path,
    get_isolated_profile_path,
    resolve_profile,
)


@pytest.fixture
def fake_browser(tmp_path) -> BrowserInfo:
    """Fake browser for testing."""
    exe = tmp_path / "fake.exe"
    exe.write_text("dummy")
    return BrowserInfo(
        name="edge",
        display_name="Fake Edge",
        executable=exe,
        priority=1,
    )


@pytest.fixture
def quiet_console() -> Console:
    """Console that doesn't print (for testing)."""
    return Console(quiet=True)


def test_get_isolated_profile_path(fake_browser):
    """Isolated path is ~/.formpilot/profiles/<browser>/."""
    path = get_isolated_profile_path(fake_browser)
    assert path == Path.home() / ".formpilot" / "profiles" / "edge"


def test_get_existing_profile_path_returns_path(fake_browser):
    """Existing path is determined (OS-specific, may not exist)."""
    path = get_existing_profile_path(fake_browser)
    assert isinstance(path, Path)


def test_get_existing_profile_path_unknown_browser():
    """Unknown browser raises ProfileError."""
    browser = BrowserInfo(
        name="unknown",
        display_name="Unknown",
        executable=Path("/tmp/x"),
        priority=99,
    )
    with pytest.raises(ProfileError, match="Unknown browser"):
        get_existing_profile_path(browser)


def test_resolve_profile_isolated_no_prompt(fake_browser, quiet_console):
    """Isolated strategy returns immediately, no browser check."""
    decision = resolve_profile(fake_browser, strategy="isolated", console=quiet_console)
    assert decision.strategy == "isolated"
    assert decision.needs_relaunch is False
    assert ".formpilot" in str(decision.path)


def test_resolve_profile_ask_not_running(fake_browser, quiet_console):
    """Ask + browser not running = existing profile."""
    with patch("formpilot.profile_manager.is_browser_running", return_value=False):
        decision = resolve_profile(
            fake_browser, strategy="ask", console=quiet_console
        )
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is False


def test_resolve_profile_existing_not_running(fake_browser, quiet_console):
    """Existing strategy + browser not running = no relaunch needed."""
    with patch("formpilot.profile_manager.is_browser_running", return_value=False):
        decision = resolve_profile(
            fake_browser, strategy="existing", console=quiet_console
        )
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is False


def test_resolve_profile_existing_running_needs_relaunch(fake_browser, quiet_console):
    """Existing strategy + browser running = needs_relaunch=True."""
    with patch("formpilot.profile_manager.is_browser_running", return_value=True):
        decision = resolve_profile(
            fake_browser, strategy="existing", console=quiet_console
        )
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is True


def test_resolve_profile_ask_running_prompts_user(fake_browser, quiet_console):
    """Ask + browser running = prompt user, default 2 (isolated)."""
    with patch(
        "formpilot.profile_manager.is_browser_running", return_value=True
    ), patch("formpilot.profile_manager.Prompt.ask", return_value="2"):
        decision = resolve_profile(
            fake_browser, strategy="ask", console=quiet_console
        )
    assert decision.strategy == "isolated"
    assert decision.needs_relaunch is False


def test_resolve_profile_ask_running_picks_relaunch(fake_browser, quiet_console):
    """Ask + running + user picks 1 = existing with relaunch."""
    with patch(
        "formpilot.profile_manager.is_browser_running", return_value=True
    ), patch("formpilot.profile_manager.Prompt.ask", return_value="1"):
        decision = resolve_profile(
            fake_browser, strategy="ask", console=quiet_console
        )
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is True


def test_resolve_profile_ask_running_cancel(fake_browser, quiet_console):
    """Ask + running + user picks 3 = cancel (raise)."""
    with patch(
        "formpilot.profile_manager.is_browser_running", return_value=True
    ), patch(
        "formpilot.profile_manager.Prompt.ask", return_value="3"
    ), pytest.raises(
        ProfileError, match="cancelled"
    ):
        resolve_profile(
            fake_browser, strategy="ask", console=quiet_console
        )
