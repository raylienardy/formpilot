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
