# PRD — v0.2.0 (Core Auto-Fill Release)

**Status:** Skeleton (expanded per-sesi)
**Vision:** See `docs/VISION-V020.md`
**Sesi:** v0.2-1 to v0.2-7

---

## Sesi v0.2-1: Browser Picker + Profile Strategy

**Deliverable:**
- `formpilot/browser_manager.py` — detect browsers, launch with debug
- `formpilot/profile_manager.py` — handle existing vs isolated profile
- Flag `--browser`, `--profile`
- Config: `browser.preferred`, `browser.profile_strategy`

**Acceptance:**
- Detect Edge, Chrome, Brave, Chromium, Vivaldi
- Menu selection in CLI
- Prompt if browser running (relaunch / isolated / cancel)
- 8+ tests

## Sesi v0.2-2: Multi-Account + Auto-Launch

**Deliverable:**
- Detect Google accounts via cookies
- Prompt account selection
- Flag `--account`
- Config: `account.preferred`

**Acceptance:**
- Detect 1 vs 2+ accounts
- Prompt only if 2+
- Tests for single/multi account

## Sesi v0.2-3: Auto-Fill Mode + Threshold

**Deliverable:**
- Flag `--auto-fill`, `--review` (hybrid)
- Confidence threshold 0.7
- Staleness tracking (`last_verified` in memory)
- Config: `memory.auto_fill_threshold`, `memory.staleness_days`

**Acceptance:**
- 0 prompts if memory matured (all similarity >= 0.7)
- Prompt if similarity < 0.7
- Warning if stale > 180 days
- Tests for threshold logic

## Sesi v0.2-4: Field Safety

**Deliverable:**
- Detect existing field value before fill
- Skip default, prompt on conflict
- Flag `--force`

**Acceptance:**
- Skip fill if field has manual value (default)
- Prompt "Form 'X', memory 'Y', choose" on conflict
- `--force` overwrites
- Tests for all 4 prompt conditions (miss required, conflict, stale, low conf)

## Sesi v0.2-5: Preview + Submit Detection

**Deliverable:**
- Browser not auto-close
- Rich banner
- Submit listener (`page.evaluate`)

**Acceptance:**
- Browser stays open after fill
- Banner shows "Review, submit when ready"
- Submit detected via JS event
- Tests (mock page)

## Sesi v0.2-6: Two-Way Sync + `auto` Command

**Deliverable:**
- On submit: extract values, diff vs memory, update DB
- On tab-close: log warning, diff on next run
- `formpilot auto <url>` subcommand

**Acceptance:**
- Change in browser → memory updated
- Tab-close-without-submit → diff on next run
- `auto` works as shortcut
- Tests for diff + update flow

## Sesi v0.2-7: Multi-User + Release

**Deliverable:**
- Flag `--user <name>`
- Memory path per-user
- Docs update
- Tag v0.2.0

**Acceptance:**
- 2 users have isolated memory
- v0.1.0 compat (no --user = 'default')
- Full test suite green
- Tag pushed

---

## v0.2.1 (2 sesi, backlog)

### Sesi v0.2.1-1: Bahasa Interface (id/en)
- Dict-based i18n
- Flag `--lang id|en`

### Sesi v0.2.1-2: Memory Export/Import
- `formpilot memory export <file.json>`
- `formpilot memory import <file.json> [--replace]`

---

## Known Constraints

- Chromium only (Chrome, Edge, Brave, Chromium, Vivaldi)
- Firefox defer v0.3
- No cloud sync, no auto-submit (ADR-001, v0.1.0 principles)
- 100% local, no external API