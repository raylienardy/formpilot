"""Tests for profile_manager.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from formpilot.browser_manager import BrowserInfo
from formpilot.profile_manager import (
    ProfileError,
    _should_skip_snapshot_item,
    detect_google_accounts,
    get_existing_profile_path,
    get_isolated_profile_path,
    get_snapshot_path,
    resolve_profile,
    snapshot_existing_profile,
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
        decision = resolve_profile(fake_browser, strategy="ask", console=quiet_console)
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is False


def test_resolve_profile_existing_not_running(fake_browser, quiet_console):
    """Existing strategy + browser not running = no relaunch needed."""
    with patch("formpilot.profile_manager.is_browser_running", return_value=False):
        decision = resolve_profile(fake_browser, strategy="existing", console=quiet_console)
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is False


def test_resolve_profile_existing_running_needs_relaunch(fake_browser, quiet_console):
    """Existing strategy + browser running = needs_relaunch=True."""
    with patch("formpilot.profile_manager.is_browser_running", return_value=True):
        decision = resolve_profile(fake_browser, strategy="existing", console=quiet_console)
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is True


def test_resolve_profile_ask_running_prompts_user(fake_browser, quiet_console):
    """Ask + browser running = prompt user, default 2 (isolated)."""
    with (
        patch("formpilot.profile_manager.is_browser_running", return_value=True),
        patch("formpilot.profile_manager.Prompt.ask", return_value="2"),
    ):
        decision = resolve_profile(fake_browser, strategy="ask", console=quiet_console)
    assert decision.strategy == "isolated"
    assert decision.needs_relaunch is False


def test_resolve_profile_ask_running_picks_relaunch(fake_browser, quiet_console):
    """Ask + running + user picks 1 = existing with relaunch."""
    with (
        patch("formpilot.profile_manager.is_browser_running", return_value=True),
        patch("formpilot.profile_manager.Prompt.ask", return_value="1"),
    ):
        decision = resolve_profile(fake_browser, strategy="ask", console=quiet_console)
    assert decision.strategy == "existing"
    assert decision.needs_relaunch is True


def test_resolve_profile_ask_running_cancel(fake_browser, quiet_console):
    """Ask + running + user picks 3 = cancel (raise)."""
    with (
        patch("formpilot.profile_manager.is_browser_running", return_value=True),
        patch("formpilot.profile_manager.Prompt.ask", return_value="3"),
        pytest.raises(ProfileError, match="cancelled"),
    ):
        resolve_profile(fake_browser, strategy="ask", console=quiet_console)


def test_detect_google_accounts_no_profile_dir(fake_browser):
    """detect_google_accounts returns [] if profile dir doesn't exist."""
    with patch(
        "formpilot.profile_manager.get_existing_profile_path",
        side_effect=ProfileError("no path"),
    ):
        result = detect_google_accounts(fake_browser)
    assert result == []


def test_detect_google_accounts_empty_profile(tmp_path):
    """detect_google_accounts returns [] if no accounts in Preferences."""
    profile_dir = tmp_path / "User Data" / "Default"
    profile_dir.mkdir(parents=True)
    (profile_dir / "Preferences").write_text("{}", encoding="utf-8")

    browser = BrowserInfo(
        name="edge",
        display_name="Edge",
        executable=tmp_path / "fake.exe",
        priority=1,
    )
    with patch(
        "formpilot.profile_manager.get_existing_profile_path",
        return_value=tmp_path / "User Data",
    ):
        result = detect_google_accounts(browser)
    assert result == []


def test_detect_google_accounts_with_email(tmp_path):
    """detect_google_accounts parses account_info[].email correctly."""
    import json

    profile_dir = tmp_path / "User Data" / "Profile 1"
    profile_dir.mkdir(parents=True)
    prefs = {
        "account_info": [
            {"email": "budi@gmail.com"},
            {"email": "budi.kampus@univ.ac.id"},
        ]
    }
    (profile_dir / "Preferences").write_text(json.dumps(prefs), encoding="utf-8")

    browser = BrowserInfo(
        name="edge",
        display_name="Edge",
        executable=tmp_path / "fake.exe",
        priority=1,
    )
    with patch(
        "formpilot.profile_manager.get_existing_profile_path",
        return_value=tmp_path / "User Data",
    ):
        result = detect_google_accounts(browser)

    assert len(result) == 2
    assert any(a["email"] == "budi@gmail.com" for a in result)
    assert any(a["profile_dir"] == "Profile 1" for a in result)


# ---------------------------------------------------------------------------
# Snapshot tests (ADR-014)
# ---------------------------------------------------------------------------


def test_get_snapshot_path(fake_browser):
    """Snapshot path is ~/.formpilot/profiles/<browser>-snapshot/."""
    path = get_snapshot_path(fake_browser)
    assert path == Path.home() / ".formpilot" / "profiles" / "edge-snapshot"


def test_should_skip_snapshot_item():
    """Skip patterns for locked/cache files."""
    # Should skip
    assert _should_skip_snapshot_item("BrowserMetrics") is True
    assert _should_skip_snapshot_item("BrowserMetrics-abc.pma") is True
    assert _should_skip_snapshot_item("SingletonLock") is True
    assert _should_skip_snapshot_item("Crashpad") is True
    assert _should_skip_snapshot_item("some.lock") is True

    # Should NOT skip
    assert _should_skip_snapshot_item("Cookies") is False
    assert _should_skip_snapshot_item("Preferences") is False
    assert _should_skip_snapshot_item("Default") is False


def test_snapshot_existing_profile_missing_source(fake_browser, quiet_console):
    """Snapshot fails if source profile doesn't exist."""
    with (
        patch(
            "formpilot.profile_manager.get_existing_profile_path",
            return_value=Path("/nonexistent-profile"),
        ),
        patch(
            "formpilot.profile_manager.get_snapshot_path",
            return_value=Path("/some-snapshot"),
        ),
        pytest.raises(ProfileError, match="not found"),
    ):
        snapshot_existing_profile(fake_browser, console=quiet_console)


def test_snapshot_existing_profile_creates_copy(tmp_path, quiet_console):
    """Snapshot copies Cookies file correctly, skips locked files."""
    src = tmp_path / "User Data"
    default_dir = src / "Default"
    default_dir.mkdir(parents=True)
    (default_dir / "Cookies").write_text("fake-cookies-data")
    (default_dir / "Preferences").write_text("{}")
    (src / "BrowserMetrics").mkdir()
    (src / "BrowserMetrics" / "file.pma").write_text("locked")

    dst = tmp_path / "snapshot"

    browser = BrowserInfo(
        name="edge",
        display_name="Edge",
        executable=tmp_path / "fake.exe",
        priority=1,
    )
    with (
        patch(
            "formpilot.profile_manager.get_existing_profile_path",
            return_value=src,
        ),
        patch(
            "formpilot.profile_manager.get_snapshot_path",
            return_value=dst,
        ),
    ):
        result = snapshot_existing_profile(browser, console=quiet_console)

    assert result == dst
    assert (dst / "Default" / "Cookies").exists()
    assert (dst / "Default" / "Preferences").exists()
    # BrowserMetrics should NOT be copied (skipped)
    assert not (dst / "BrowserMetrics").exists()


def test_snapshot_reuses_existing(tmp_path, quiet_console):
    """Snapshot with existing snapshot + no refresh returns cached path."""
    src = tmp_path / "User Data"
    src.mkdir()
    dst = tmp_path / "snapshot"
    (dst / "Default").mkdir(parents=True)
    (dst / "Default" / "Cookies").write_text("old-snapshot")

    browser = BrowserInfo(
        name="edge",
        display_name="Edge",
        executable=tmp_path / "fake.exe",
        priority=1,
    )
    with (
        patch(
            "formpilot.profile_manager.get_existing_profile_path",
            return_value=src,
        ),
        patch(
            "formpilot.profile_manager.get_snapshot_path",
            return_value=dst,
        ),
    ):
        result = snapshot_existing_profile(
            browser,
            console=quiet_console,
            force_refresh=False,
        )

    assert result == dst
    # Old cookie content preserved
    assert (dst / "Default" / "Cookies").read_text() == "old-snapshot"


def test_snapshot_force_refresh_deletes_old(tmp_path, quiet_console):
    """force_refresh=True deletes old snapshot and re-copies source Cookies."""
    src = tmp_path / "User Data"
    (src / "Default").mkdir(parents=True)
    (src / "Default" / "Cookies").write_text("new-source")

    dst = tmp_path / "snapshot"
    (dst / "Default").mkdir(parents=True)
    (dst / "Default" / "Cookies").write_text("old-snapshot")

    browser = BrowserInfo(
        name="edge",
        display_name="Edge",
        executable=tmp_path / "fake.exe",
        priority=1,
    )
    with (
        patch(
            "formpilot.profile_manager.get_existing_profile_path",
            return_value=src,
        ),
        patch(
            "formpilot.profile_manager.get_snapshot_path",
            return_value=dst,
        ),
    ):
        result = snapshot_existing_profile(
            browser,
            console=quiet_console,
            force_refresh=True,
        )

    assert result == dst
    assert (dst / "Default" / "Cookies").read_text() == "new-source"


def test_snapshot_fails_if_no_cookies(tmp_path, quiet_console):
    """Snapshot raises if no Cookies file in source."""
    src = tmp_path / "User Data"
    (src / "Default").mkdir(parents=True)
    # No Cookies file
    (src / "Default" / "Preferences").write_text("{}")

    dst = tmp_path / "snapshot"

    browser = BrowserInfo(
        name="edge",
        display_name="Edge",
        executable=tmp_path / "fake.exe",
        priority=1,
    )
    with (
        patch(
            "formpilot.profile_manager.get_existing_profile_path",
            return_value=src,
        ),
        patch(
            "formpilot.profile_manager.get_snapshot_path",
            return_value=dst,
        ),
        pytest.raises(ProfileError, match="no Cookies"),
    ):
        snapshot_existing_profile(browser, console=quiet_console)
