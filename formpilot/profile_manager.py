"""Profile management for FormPilot.

Handles existing vs isolated profile strategies (ADR-007):
- existing: use user's default browser profile (instant Gmail login)
- isolated: use dedicated FormPilot profile (login once, persists)

If existing profile chosen but browser is running, prompt user:
[1] Relaunch (kill browser, reopen with debug) — loses tabs
[2] Isolated profile (login once, tabs preserved)
[3] Cancel
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.prompt import Prompt

from formpilot.browser_manager import BrowserInfo, is_browser_running
from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.profile_manager")

ProfileStrategy = Literal["existing", "isolated", "ask"]


class ProfileError(Exception):
    """Raised when profile resolution fails."""


@dataclass
class ProfileDecision:
    """Result of profile resolution."""

    path: Path
    strategy: str  # "existing" or "isolated"
    needs_relaunch: bool  # True if existing profile but browser was running


def get_existing_profile_path(browser: BrowserInfo) -> Path:
    """Get user's default browser profile path.

    Args:
        browser: BrowserInfo with name (edge, chrome, brave, chromium, vivaldi).

    Returns:
        Path to existing User Data directory.

    Raises:
        ProfileError: If path cannot be determined for OS.
    """
    if sys.platform.startswith("win"):
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        if not local.exists():
            raise ProfileError("LOCALAPPDATA not set")
        mapping = {
            "edge": local / "Microsoft" / "Edge" / "User Data",
            "chrome": local / "Google" / "Chrome" / "User Data",
            "brave": local / "BraveSoftware" / "Brave-Browser" / "User Data",
            "chromium": local / "Chromium" / "User Data",
            "vivaldi": local / "Vivaldi" / "User Data",
        }
    elif sys.platform == "darwin":
        home = Path.home()
        mapping = {
            "edge": home / "Library" / "Application Support" / "Microsoft Edge",
            "chrome": home / "Library" / "Application Support" / "Google" / "Chrome",
            "brave": home / "Library" / "Application Support" / "BraveSoftware" / "Brave-Browser",
            "chromium": home / "Library" / "Application Support" / "Chromium",
            "vivaldi": home / "Library" / "Application Support" / "Vivaldi",
        }
    else:  # linux
        home = Path.home()
        mapping = {
            "edge": home / ".config" / "microsoft-edge",
            "chrome": home / ".config" / "google-chrome",
            "brave": home / ".config" / "BraveSoftware" / "Brave-Browser",
            "chromium": home / ".config" / "chromium",
            "vivaldi": home / ".config" / "vivaldi",
        }

    if browser.name not in mapping:
        raise ProfileError(f"Unknown browser for existing profile: {browser.name}")
    return mapping[browser.name]


def get_isolated_profile_path(browser: BrowserInfo) -> Path:
    """Get dedicated FormPilot profile path for browser.

    Args:
        browser: BrowserInfo.

    Returns:
        Path ~/.formpilot/profiles/<browser>/
    """
    home = Path.home()
    return home / ".formpilot" / "profiles" / browser.name


def resolve_profile(
    browser: BrowserInfo,
    strategy: ProfileStrategy = "ask",
    console: Console | None = None,
) -> ProfileDecision:
    """Resolve profile path based on strategy and browser state (ADR-007).

    Behavior:
    - strategy="existing": use existing profile. If browser running,
      prompt user to relaunch (needs_relaunch=True) or fallback.
    - strategy="isolated": use isolated profile (no prompt).
    - strategy="ask" (default): existing if browser not running,
      prompt user if running.

    Args:
        browser: Selected browser.
        strategy: "existing", "isolated", or "ask".
        console: Optional Rich console.

    Returns:
        ProfileDecision with path + strategy + needs_relaunch flag.

    Raises:
        ProfileError: If resolution fails.
    """
    if console is None:
        console = Console()

    # Isolated: simple, no prompt
    if strategy == "isolated":
        path = get_isolated_profile_path(browser)
        console.print(f"[cyan]Using isolated profile:[/cyan] [dim]{path}[/dim]")
        return ProfileDecision(path=path, strategy="isolated", needs_relaunch=False)

    # For existing or ask, use snapshot (Edge 136+ blocks CDP on default
    # profile, so we snapshot to a different user-data-dir, per ADR-014).
    browser_running = is_browser_running(browser)

    if strategy == "existing" or (strategy == "ask" and not browser_running):
        # Determine if relaunch needed
        needs_relaunch = False
        if strategy == "existing" and browser_running:
            needs_relaunch = True
            console.print(
                f"[yellow]{browser.display_name} running. "
                f"Will close and relaunch from snapshot.[/yellow]"
            )

        # Snapshot the existing profile
        try:
            snap_path = snapshot_existing_profile(
                browser,
                console=console,
                force_refresh=False,
            )
        except ProfileError as e:
            raise ProfileError(
                f"Snapshot failed: {e}. Try: --profile isolated (login once, then use that)."
            ) from e

        return ProfileDecision(
            path=snap_path,
            strategy="existing",
            needs_relaunch=needs_relaunch,
        )

    # strategy == "ask" AND browser running → prompt
    console.print()
    console.print(f"[bold yellow]{browser.display_name} sedang berjalan.[/bold yellow]")
    console.print("[bold]Pilih profile strategy:[/bold]")
    console.print(
        "  [yellow]1.[/yellow] Snapshot profile existing "
        "[dim](instant login, tab lama ditutup)[/dim]"
    )
    console.print(
        "  [yellow]2.[/yellow] Pakai isolated profile "
        "[dim](tab aman, login Google sekali di awal)[/dim]"
    )
    console.print("  [yellow]3.[/yellow] Cancel")

    while True:
        raw = Prompt.ask("[bold]Pilih (1-3)[/bold]", default="1", console=console)
        if raw == "1":
            try:
                snap_path = snapshot_existing_profile(
                    browser,
                    console=console,
                    force_refresh=False,
                )
            except ProfileError as e:
                console.print(f"[red]Snapshot failed: {e}[/red]")
                continue
            return ProfileDecision(
                path=snap_path,
                strategy="existing",
                needs_relaunch=True,
            )
        if raw == "2":
            path = get_isolated_profile_path(browser)
            console.print(f"[cyan]Isolated profile:[/cyan] [dim]{path}[/dim]")
            return ProfileDecision(path=path, strategy="isolated", needs_relaunch=False)
        if raw == "3":
            raise ProfileError("User cancelled profile selection")
        console.print("[red]Pilihan tidak valid. Ketik 1-3.[/red]")


def detect_google_accounts(browser: BrowserInfo) -> list[dict]:
    """Detect Google accounts in existing profile folders.

    Scans profile subdirs (Default, Profile 1, Profile 2, ...) and parses
    Preferences JSON for account_info[].email entries.

    Works only for existing profiles (not isolated). Returns empty list if
    no existing profile dir or no accounts.

    Args:
        browser: BrowserInfo.

    Returns:
        List of dicts: [{"email": "...", "profile_dir": "Default"}, ...].
        Empty if no accounts found.
    """
    import json

    try:
        base = get_existing_profile_path(browser)
    except ProfileError:
        return []

    if not base.exists():
        return []

    accounts: list[dict] = []
    for subdir in base.iterdir():
        if not subdir.is_dir():
            continue
        # Profile folders are Default or "Profile N"
        if subdir.name != "Default" and not subdir.name.startswith("Profile "):
            continue

        prefs_file = subdir / "Preferences"
        if not prefs_file.exists():
            continue

        try:
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue

        # Chrome/Edge: preferences.account_info[].email
        account_info = data.get("account_info", [])
        for acct in account_info:
            email = acct.get("email", "").strip()
            if email and "@" in email:
                accounts.append(
                    {
                        "email": email,
                        "profile_dir": subdir.name,
                    }
                )

    logger.debug("Detected %d accounts in %s profile", len(accounts), browser.name)
    return accounts


def resolve_account_profile(
    browser: BrowserInfo,
    email: str,
    console: Console | None = None,
) -> Path:
    """Resolve profile subdir for a specific Google account email.

    Args:
        browser: BrowserInfo.
        email: Google account email to find.
        console: Optional Rich console.

    Returns:
        Path to profile subdir (e.g. User Data/Profile 1).

    Raises:
        ProfileError: If email not found in existing profile accounts.
    """
    if console is None:
        console = Console()

    accounts = detect_google_accounts(browser)
    matches = [a for a in accounts if a["email"].lower() == email.lower()]

    if not matches:
        available = ", ".join(a["email"] for a in accounts) or "none"
        raise ProfileError(
            f"Account '{email}' not found in {browser.display_name} profile. Available: {available}"
        )

    if len(matches) > 1:
        # Multiple profiles have same email — use first (rare)
        logger.warning(
            "Multiple profiles found for %s: %s, using first",
            email,
            [m["profile_dir"] for m in matches],
        )

    matched = matches[0]
    base = get_existing_profile_path(browser)
    profile_path = base / matched["profile_dir"]
    console.print(f"[green]Using account:[/green] {email} [dim]({matched['profile_dir']})[/dim]")
    return profile_path


def get_snapshot_path(browser: BrowserInfo) -> Path:
    """Get snapshot profile path for browser.

    Snapshot = auto-copied version of existing user profile.
    Used because Edge 136+ blocks --remote-debugging-port on default
    profile. Snapshot preserves cookies (instant login) but is a
    different user-data-dir so CDP works.

    Args:
        browser: BrowserInfo.

    Returns:
        Path ~/.formpilot/profiles/<browser>-snapshot/
    """
    return Path.home() / ".formpilot" / "profiles" / f"{browser.name}-snapshot"


# Files/dirs to skip when snapshotting (locked, temp, cache)
_SNAPSHOT_SKIP_PATTERNS = (
    "BrowserMetrics",
    "Crashpad",
    "Safe Browsing",
    "ShaderCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
    "lockfile",
)


def _should_skip_snapshot_item(name: str) -> bool:
    """Check if a file/dir name should be skipped during snapshot copy."""
    for pattern in _SNAPSHOT_SKIP_PATTERNS:
        if pattern.lower() in name.lower():
            return True
    if name.endswith(".pma"):  # BrowserMetrics
        return True
    return name.endswith(".lock")


def snapshot_existing_profile(
    browser: BrowserInfo,
    console: Console | None = None,
    force_refresh: bool = False,
) -> Path:
    """Snapshot existing profile to .formpilot/profiles/<browser>-snapshot/.

    If snapshot exists and force_refresh=False, returns existing path
    without copying.

    Copy may skip locked/cache files (BrowserMetrics, Crashpad, etc.).
    This is expected — cookies and preferences are what matter.

    Args:
        browser: BrowserInfo.
        console: Optional Rich console.
        force_refresh: If True, delete existing snapshot and re-copy.

    Returns:
        Path to snapshot directory.

    Raises:
        ProfileError: If source profile missing or copy fails critically.
    """
    import shutil

    if console is None:
        console = Console()

    src = get_existing_profile_path(browser)
    if not src.exists():
        raise ProfileError(
            f"Existing profile not found: {src}. Login to {browser.display_name} first, then retry."
        )

    dst = get_snapshot_path(browser)

    # Reuse existing snapshot unless refresh forced
    if dst.exists() and not force_refresh:
        console.print(f"[cyan]Using existing snapshot:[/cyan] [dim]{dst}[/dim]")
        console.print(
            "[dim]Tip: use --refresh-snapshot to re-copy from live profile "
            "after you update Google login in Edge.[/dim]"
        )
        return dst

    # Delete old snapshot if refreshing
    if dst.exists():
        console.print("[yellow]Deleting old snapshot...[/yellow]")
        try:
            shutil.rmtree(dst)
        except OSError as e:
            raise ProfileError(f"Failed to delete old snapshot: {e}") from e

    dst.parent.mkdir(parents=True, exist_ok=True)

    console.print(
        f"[cyan]Copying profile snapshot...[/cyan]\n"
        f"[dim]  from: {src}[/dim]\n"
        f"[dim]  to:   {dst}[/dim]\n"
        f"[dim]This may take 30-90 seconds (first time only).[/dim]"
    )

    skipped: list[str] = []

    def _ignore_func(dir_path: str, names: list[str]) -> list[str]:
        """Ignore function for copytree — skip locked/cache files."""
        ignore_list: list[str] = []
        for name in names:
            if _should_skip_snapshot_item(name):
                ignore_list.append(name)
                skipped.append(name)
        return ignore_list

    try:
        shutil.copytree(
            src,
            dst,
            ignore=_ignore_func,
            dirs_exist_ok=True,
            ignore_dangling_symlinks=True,
        )
    except (OSError, shutil.Error) as e:
        # Partial copy may still work (cookies copied, some cache failed)
        # Log warning but proceed if dst has key files
        console.print(f"[yellow]Copy had issues (may be OK): {e}[/yellow]")

    # Verify critical file exists (Cookies)
    cookies_candidates = [
        dst / "Default" / "Cookies",
        dst / "Default" / "Network" / "Cookies",
    ]
    if not any(c.exists() for c in cookies_candidates):
        raise ProfileError(
            f"Snapshot copy failed: no Cookies file found in {dst}. "
            f"Close {browser.display_name} completely and retry."
        )

    console.print(
        f"[green]Snapshot ready.[/green] "
        f"[dim]Skipped {len(skipped)} cache/locked items (expected).[/dim]"
    )
    logger.info(
        "Snapshot created: %s -> %s (skipped %d items)",
        src,
        dst,
        len(skipped),
    )
    return dst


def is_snapshot_stale(
    browser: BrowserInfo,
    threshold_days: int = 7,
) -> bool:
    """Check if snapshot is older than threshold compared to live profile.

    Compares mtime of live Cookies vs snapshot Cookies.

    Args:
        browser: BrowserInfo.
        threshold_days: Days threshold.

    Returns:
        True if live profile is newer than snapshot by >threshold_days.
        False if snapshot up-to-date or any check fails (be lenient).
    """

    try:
        live = get_existing_profile_path(browser)
        snap = get_snapshot_path(browser)
    except ProfileError:
        return False

    if not snap.exists():
        return True  # No snapshot = definitely "stale" (need create)

    # Find cookies in both
    def _find_cookies(base: Path) -> Path | None:
        for cand in [
            base / "Default" / "Cookies",
            base / "Default" / "Network" / "Cookies",
        ]:
            if cand.exists():
                return cand
        return None

    live_cookies = _find_cookies(live)
    snap_cookies = _find_cookies(snap)

    if live_cookies is None or snap_cookies is None:
        return False  # Can't compare — don't nag user

    try:
        live_mtime = live_cookies.stat().st_mtime
        snap_mtime = snap_cookies.stat().st_mtime
    except OSError:
        return False

    threshold_sec = threshold_days * 86400
    return (live_mtime - snap_mtime) > threshold_sec
