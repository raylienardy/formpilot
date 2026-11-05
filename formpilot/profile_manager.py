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
    strategy: str      # "existing" or "isolated"
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
        raise ProfileError(
            f"Unknown browser for existing profile: {browser.name}"
        )
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
        console.print(
            f"[cyan]Using isolated profile:[/cyan] [dim]{path}[/dim]"
        )
        return ProfileDecision(path=path, strategy="isolated", needs_relaunch=False)

    # For existing or ask, check if browser is running
    browser_running = is_browser_running(browser)

    if not browser_running:
        # Browser not running → use existing (instant login)
        path = get_existing_profile_path(browser)
        console.print(
            f"[green]Using existing profile (browser not running):[/green] "
            f"[dim]{path}[/dim]"
        )
        return ProfileDecision(path=path, strategy="existing", needs_relaunch=False)

    # Browser IS running
    if strategy == "existing":
        # Force existing: needs relaunch, no prompt
        path = get_existing_profile_path(browser)
        console.print(
            f"[yellow]Using existing profile (will require relaunch):[/yellow] "
            f"[dim]{path}[/dim]"
        )
        return ProfileDecision(path=path, strategy="existing", needs_relaunch=True)

    # strategy == "ask" AND browser running → prompt
    console.print()
    console.print(
        f"[bold yellow]{browser.display_name} sedang berjalan.[/bold yellow]"
    )
    console.print("[bold]Pilih profile strategy:[/bold]")
    console.print(
        "  [yellow]1.[/yellow] Relaunch dengan existing profile "
        "[dim](instant login, tapi semua tab hilang)[/dim]"
    )
    console.print(
        "  [yellow]2.[/yellow] Pakai isolated profile "
        "[dim](tab aman, login Google sekali di awal)[/dim]"
    )
    console.print("  [yellow]3.[/yellow] Cancel")

    while True:
        raw = Prompt.ask("[bold]Pilih (1-3)[/bold]", default="2", console=console)
        if raw == "1":
            path = get_existing_profile_path(browser)
            console.print(
                "[yellow]Existing profile dipilih. "
                "Browser akan ditutup dan diluncurkan ulang.[/yellow]"
            )
            return ProfileDecision(path=path, strategy="existing", needs_relaunch=True)
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
                accounts.append({
                    "email": email,
                    "profile_dir": subdir.name,
                })

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
            f"Account '{email}' not found in {browser.display_name} profile. "
            f"Available: {available}"
        )

    if len(matches) > 1:
        # Multiple profiles have same email — use first (rare)
        logger.warning(
            "Multiple profiles found for %s: %s, using first",
            email, [m["profile_dir"] for m in matches],
        )

    matched = matches[0]
    base = get_existing_profile_path(browser)
    profile_path = base / matched["profile_dir"]
    console.print(
        f"[green]Using account:[/green] {email} "
        f"[dim]({matched['profile_dir']})[/dim]"
    )
    return profile_path
