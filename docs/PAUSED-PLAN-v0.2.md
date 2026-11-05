# PAUSED PLAN — v0.2 (Playwright/CDP Approach)

**Status:** PAUSED (2026-11-05)
**Reason:** Google and Microsoft Edge security features fundamentally block automated browsers from reusing real profiles without triggering 2FA/Security alerts.

---

## 1. What We Tried (v0.2-1 to v0.2-2.5)

We attempted to make FormPilot launch the user's browser (Edge/Chrome) directly with their existing profile, so they wouldn't have to log in manually.

1. **v0.2-1:** Created `browser_manager.py` (detect Edge/Chrome) and `profile_manager.py` (profile paths).
2. **v0.2-2:** Tried CDP (Chrome DevTools Protocol) to attach to the real profile. **Failed:** Edge 127+ blocks `--remote-debugging-port` on the default profile.
3. **v0.2-2.5:** Tried "Snapshot" (copying the real profile to a new folder). **Failed:** Google detects the copied profile as "not secure" (ABE - App-Bound Encryption) and forces re-login. Also, 2FA (Two-Step Verification) makes manual re-login highly painful.

## 2. The Root Cause (Why It Failed)

- **App-Bound Encryption (ABE):** Edge 127+ encrypts cookies tied to the exact file path and process. If Playwright copies it or attaches to it, Edge refuses to decrypt the cookies. Login lost.
- **Google Anti-Bot:** Google actively blocks logins from browsers controlled by Playwright/CDP (shows "This browser or app may not be secure").
- **2FA:** Requiring the user to log in manually every time (or once per new isolated profile) is unacceptable because they have to grab their phone for 2FA.

## 3. The Pivot (Future v0.3 Plan)

We must abandon browser automation (Playwright) for the UI layer and pivot to a **Browser Extension (Manifest V3)**.

**How the Extension will work:**
1. User opens Google Forms in their normal Edge/Chrome (100% real profile, extensions intact, no login, no 2FA).
2. User clicks the FormPilot Extension icon.
3. The Extension (JavaScript) reads the form questions from the DOM.
4. The Extension sends an HTTP request to a **Local Python API** (e.g., FastAPI/Flask running on `localhost:8000`).
5. The Python API uses the existing Brain (Ollama) and Memory (SQLite/ChromaDB) to generate answers.
6. The API sends answers back to the Extension.
7. The Extension fills the form fields automatically.

**Why this is better:**
- **No login required. Ever.** Uses the user's actual browser session.
- **2FA is a non-issue.** Google sees normal human browsing.
- **Faster.** No waiting for Playwright to boot Chromium.
- **Memory & AI stay 100% local.**

## 4. What to Keep vs. Discard

- **KEEP:** `formpilot/brain.py`, `formpilot/memory/*`, `formpilot/prompts/*`, `formpilot/cli.py`. These are the core AI and memory logic.
- **KEEP (for reference):** `formpilot/scraper.py`, `formpilot/browser_manager.py`, `formpilot/profile_manager.py`. (May be deleted in v0.3, but keep for now).
- **DISCARD LATER:** All Playwright/CDP logic in `__main__.py`. v0.3 will introduce `formpilot/api.py` (FastAPI).

## 5. How to Resume Later

When ready to build v0.3:
1. Read this file.
2. Read `docs/VISION-V020.md` for the original auto-fill goals.
3. Create `docs/VISION-V030.md` for the Extension approach.
4. Start building the FastAPI local server (`formpilot/api.py`).
5. Build a simple Chrome Extension (`extension/manifest.json`, `extension/content.js`).

**Do not attempt Playwright/CDP profile sharing again.**
