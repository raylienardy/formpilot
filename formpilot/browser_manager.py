"""Browser detection and launch for FormPilot.

Detects installed Chromium-family browsers, provides Rich menu selection,
and launches with remote debugging enabled.

Supports: Edge, Chrome, Brave, Chromium, Vivaldi (per ADR-010).
Firefox and WebKit deferred to v0.3.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from formpilot.utils.logger import get_logger

logger = get_logger("formpilot.browser_manager")

DEFAULT_DEBUG_PORT = 9222
LAUNCH_TIMEOUT_SECONDS = 30


class BrowserError(Exception):
    """Raised when browser detection or launch fails."""


@dataclass
class BrowserInfo:
    """Detected browser metadata."""

    name: str          # "edge", "chrome", "brave", "chromium", "vivaldi"
    display_name: str  # "Microsoft Edge"
    executable: Path   # Full path to exe
    priority: int      # 1=highest (Edge), 5=lowest (Vivaldi)


# Standard install locations per OS (Windows-first, macOS/Linux stubs)
_BROWSER_PATHS = {
    "windows": {
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "brave": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "chromium": [
            r"C:\Program Files\Chromium\Application\chrome.exe",
        ],
        "vivaldi": [
            r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
            r"C:\Program Files (x86)\Vivaldi\Application\vivaldi.exe",
        ],
    },
    "darwin": {
        "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "brave": ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"],
        "chromium": ["/Applications/Chromium.app/Contents/MacOS/Chromium"],
        "vivaldi": ["/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"],
    },
    "linux": {
        "edge": ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"],
        "chrome": ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"],
        "brave": ["/usr/bin/brave-browser", "/usr/bin/brave"],
        "chromium": ["/usr/bin/chromium", "/usr/bin/chromium-browser"],
        "vivaldi": ["/usr/bin/vivaldi", "/usr/bin/vivaldi-stable"],
    },
}

_DISPLAY_NAMES = {
    "edge": "Microsoft Edge",
    "chrome": "Google Chrome",
    "brave": "Brave Browser",
    "chromium": "Chromium",
    "vivaldi": "Vivaldi",
}

_PRIORITY = {
    "edge": 1,
    "chrome": 2,
    "brave": 3,
    "chromium": 4,
    "vivaldi": 5,
}


def _get_os_key() -> str:
    """Return 'windows', 'darwin', or 'linux'."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def detect_browsers() -> list[BrowserInfo]:
    """Detect installed Chromium-family browsers.

    Returns:
        List of BrowserInfo sorted by priority (Edge first).
    """
    os_key = _get_os_key()
    paths_for_os = _BROWSER_PATHS.get(os_key, {})
    found: list[BrowserInfo] = []

    for name, candidate_paths in paths_for_os.items():
        for path_str in candidate_paths:
            path = Path(path_str)
            if path.exists():
                found.append(
                    BrowserInfo(
                        name=name,
                        display_name=_DISPLAY_NAMES[name],
                        executable=path,
                        priority=_PRIORITY[name],
                    )
                )
                break  # First match per browser

    found.sort(key=lambda b: b.priority)
    logger.debug("Detected %d browsers: %s", len(found), [b.name for b in found])
    return found


def pick_browser(
    console: Console | None = None,
    preferred: str | None = None,
) -> BrowserInfo:
    """Detect browsers and let user pick via Rich menu.

    Args:
        console: Optional Rich console.
        preferred: If set and installed, use without prompting.

    Returns:
        Selected BrowserInfo.

    Raises:
        BrowserError: If no browsers installed.
    """
    if console is None:
        console = Console()

    browsers = detect_browsers()
    if not browsers:
        raise BrowserError(
            "No Chromium-family browser detected. Install Edge, Chrome, "
            "Brave, Chromium, or Vivaldi first."
        )

    # Preferred: use if installed
    if preferred:
        for b in browsers:
            if b.name == preferred.lower():
                console.print(f"[green]Using preferred browser:[/green] {b.display_name}")
                return b
        console.print(
            f"[yellow]Preferred '{preferred}' not installed, "
            f"falling back to menu.[/yellow]"
        )

    # Single browser: use without prompt
    if len(browsers) == 1:
        b = browsers[0]
        console.print(f"[green]Using only detected browser:[/green] {b.display_name}")
        return b

    # Multiple: show menu
    console.print()
    console.print("[bold cyan]Browser terdeteksi:[/bold cyan]")
    table = Table(show_header=False, box=None, padding=(0, 1))
    for i, b in enumerate(browsers, start=1):
        table.add_row(f"[yellow]{i}.[/yellow]", b.display_name, f"[dim]{b.executable}[/dim]")
    console.print(table)

    while True:
        raw = Prompt.ask(
            f"[bold]Pilih browser (1-{len(browsers)})[/bold]",
            default="1",
            console=console,
        ).strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(browsers):
                return browsers[idx]
        # Also allow name match
        for b in browsers:
            if b.name == raw.lower():
                return b
        console.print(f"[red]Pilihan tidak valid. Ketik 1-{len(browsers)}.[/red]")


def resolve_browser_from_arg(
    value: str | None,
    console: Console | None = None,
) -> BrowserInfo:
    """Resolve browser from --browser flag value.

    Args:
        value: Browser name (edge, chrome, brave, chromium, vivaldi) OR
            absolute path to executable. None = auto-detect + menu.
        console: Optional Rich console.

    Returns:
        BrowserInfo (either from detection or from path).

    Raises:
        BrowserError: If specified browser not installed / path invalid.
    """
    if console is None:
        console = Console()

    if value is None:
        return pick_browser(console)

    # Path provided
    if os.path.sep in value or "/" in value:
        path = Path(value)
        if not path.exists():
            raise BrowserError(f"Browser path not found: {value}")
        return BrowserInfo(
            name="custom",
            display_name=path.name,
            executable=path,
            priority=99,
        )

    # Name provided — must be installed
    browsers = detect_browsers()
    for b in browsers:
        if b.name == value.lower():
            return b
    raise BrowserError(
        f"Browser '{value}' not found. Installed: "
        f"{[b.name for b in browsers] or 'none'}"
    )


def launch_browser(
    browser: BrowserInfo,
    profile_path: Path,
    debug_port: int = DEFAULT_DEBUG_PORT,
) -> subprocess.Popen:
    """Launch browser with remote debugging enabled.

    Args:
        browser: BrowserInfo from detect/pick/resolve.
        profile_path: User data dir (existing or isolated).
        debug_port: CDP debug port.

    Returns:
        Popen process handle.

    Raises:
        BrowserError: If launch fails.
    """
    profile_path.mkdir(parents=True, exist_ok=True)

    args = [
        str(browser.executable),
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    logger.info(
        "Launching %s with profile %s on port %d",
        browser.display_name, profile_path, debug_port,
    )

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except OSError as e:
        raise BrowserError(
            f"Failed to launch {browser.display_name}: {e}"
        ) from e


def is_browser_running(browser: BrowserInfo) -> bool:
    """Check if any process with the browser's exe is running.

    Args:
        browser: BrowserInfo to check.

    Returns:
        True if at least one process is running.

    Note:
        This is a heuristic. Process name on Windows may not match
        executable path exactly.
    """
    try:
        if sys.platform.startswith("win"):
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {browser.executable.name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # tasklist returns "INFO: No tasks..." if not running
            return browser.executable.name.lower() in result.stdout.lower()
        else:
            result = subprocess.run(
                ["pgrep", "-f", browser.executable.name],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("Cannot check browser process status, assuming not running")
        return False


def wait_for_cdp_ready(
    port: int = DEFAULT_DEBUG_PORT,
    timeout_seconds: int = 30,
    poll_interval_seconds: float = 0.5,
) -> bool:
    """Wait for CDP endpoint to become available on localhost:port.

    Polls http://127.0.0.1:{port}/json/version until HTTP 200 or timeout.

    Args:
        port: CDP debug port.
        timeout_seconds: Max wait time.
        poll_interval_seconds: Time between polls.

    Returns:
        True if CDP ready, False if timeout.
    """
    import time
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout_seconds
    attempt = 0

    logger.info("Waiting for CDP on %s (timeout %ds)...", url, timeout_seconds)

    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    logger.info("CDP ready after %d attempts", attempt)
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(poll_interval_seconds)

    logger.error("CDP not ready after %ds (%d attempts)", timeout_seconds, attempt)
    return False


def kill_browser(
    browser: BrowserInfo,
    timeout_seconds: int = 10,
) -> bool:
    """Kill all running processes of a browser (all windows).

    WARNING: This closes ALL windows/tabs of the browser. User data
    (history, open tabs) is preserved in profile, but unsaved work in
    tabs may be lost.

    Args:
        browser: BrowserInfo of browser to kill.
        timeout_seconds: Max time to wait for processes to exit.

    Returns:
        True if browser is no longer running (was killed or never running).
        False if processes remain after timeout.
    """
    import time

    if not is_browser_running(browser):
        logger.debug("%s not running, nothing to kill", browser.name)
        return True

    exe_name = browser.executable.name
    logger.warning("Killing %s (all windows will close)", browser.display_name)

    try:
        if sys.platform.startswith("win"):
            subprocess.run(
                ["taskkill", "/F", "/IM", exe_name],
                capture_output=True,
                timeout=10,
            )
        else:
            subprocess.run(
                ["pkill", "-f", exe_name],
                capture_output=True,
                timeout=10,
            )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.error("Failed to kill %s: %s", browser.display_name, e)
        return False

    # Wait for processes to actually exit (Windows can be slow)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_browser_running(browser):
            logger.info("%s killed successfully", browser.display_name)
            return True
        time.sleep(0.5)

    logger.error("%s still running after %ds", browser.display_name, timeout_seconds)
    return False
