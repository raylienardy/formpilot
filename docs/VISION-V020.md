# VISION-V020.md — FormPilot v0.2 Vision

**Status:** Locked (2026-11-04)
**Target Release:** v0.2.0 (core, 7 sesi) + v0.2.1 (polish, 2 sesi)
**Baseline:** v0.1.0 (commit 2b5172d)

---

## 1. Elevator Pitch

FormPilot v0.2 mengubah FormPilot dari "AI yang menanyakan jawaban"
menjadi "AI yang mengisi otomatis, Anda tinggal review." Fokus:
zero-prompt auto-fill dengan safety net, preview di browser, dan
two-way sync memory.

Satu command: `formpilot auto <url>` → browser pilih sendiri → form
terisi dari memory → preview → submit → memory ter-update.

---

## 2. Problem Statement v0.1.0

v0.1.0 stabil untuk single-page forms. Yang masih menyakitkan:

1. **Prompt-heavy** — walau memory sudah terisi, `--interactive` tetap
   prompt untuk setiap `needs_cli=True`. Tidak ada "auto mode".
2. **Manual browser launch** — user harus launch Edge dengan
   `--remote-debugging-port=9222` manual. Friction tinggi.
3. **No field safety** — kalau user sudah isi partial manual, FormPilot
   akan overwrite. Tidak ada "preserve user input".
4. **No two-way sync** — kalau user edit di browser setelah fill,
   perubahan tidak tersimpan ke memory.
5. **Single browser** — hardcoded ke Edge. User Chrome/Brave harus
   edit code.

Target v0.2.0: **"One command, auto-fill, preview, submit, memory grows."**

---

## 3. UX Shift

### v0.1.0 Flow
    formpilot --url <url> --ai --use-memory --interactive --cdp-url ...
    → launch Edge manual debug
    → prompt Q1 → user jawab → save → fill
    → prompt Q2 → user jawab → save → fill
    → form terisi, user review, klik Submit
    → memory NOT updated (kalau user ubah)

### v0.2.0 Flow
    formpilot auto <url>
    → [detect browser] → menu
    → [profile strategy] → login check
    → [auto-fill dari memory] → confidence threshold
    → [prompt HANYA kalau miss/stale/konflik]
    → terminal: "Preview di browser. Klik Submit kalau OK."
    → user review, edit 1-2, klik Submit
    → [detect submit] → diff vs memory → update DB
    → "Memory updated. 2 changes stored."

---

## 4. Use Case Konkret v0.2.0

### UC-1: Kuisioner evaluasi dosen semester baru
- Form baru, pertanyaan sama dengan semester lalu
- v0.1.0: 10 prompts
- v0.2.0: **0 prompts** (semua auto-fill) → review → submit
- Time saved: 8-10 menit

### UC-2: Registrasi kegiatan pertama (memory kosong)
- v0.2.0: `formpilot auto` → pick browser → auto-fill (kosong)
- Prompt 5 fields → save → fill → preview → submit
- Next similar form: 0 prompts

### UC-3: Survey kepuasan bulanan
- Sudah pernah isi bulan lalu
- v0.2.0: `formpilot auto` → Chroma hit → preview
- User ubah rating 3→4 → submit → memory update

### UC-4: Multi-account (kakak-adik)
- Kakak: `formpilot auto <url> --user kakak`
- Adik: `formpilot auto <url> --user adik`
- Memory terpisah: `~/.formpilot/users/<name>/`

---

## 5. Scope v0.2.0 (7 sesi)

### 5.1 Browser Picker
- Auto-detect browser terinstall (Edge, Chrome, Brave, Chromium, Vivaldi)
- Priority: Edge → Chrome → Brave → Chromium → Vivaldi
- Rich menu pilihan
- Flag: `--browser <name>` atau `--browser <path>`
- Config: `browser.preferred` di production.yaml

### 5.2 Profile Strategy (Hybrid — ADR-007)
- Default: existing profile (instant Gmail login)
- Kalau browser running → prompt: relaunch / isolated / cancel
- Dedicated profile path: `~/.formpilot/profiles/<browser>/`
- Flag: `--profile existing|isolated|ask`

### 5.3 Multi-Account Gmail
- Detect Google accounts di profile (via cookies)
- Kalau 2+ → prompt: "Akun mana?"
- Store preferred di config
- Flag: `--account <email-or-alias>`

### 5.4 Auto-Fill Mode
- Flag: `--auto-fill` (no prompts kecuali safety triggers)
- Flag: `--interactive` (v0.1.0 backward compat)
- Flag: `--review` (hybrid)
- Confidence threshold: `memory.auto_fill_threshold: 0.7`
- Staleness: `memory.staleness_days: 180`
- Staleness uses `last_verified` field (added in Sesi v0.2-3, see ADR-013)

### 5.5 Field Safety — Smart Ask (ADR-009)
Auto-fill dulu. Prompt HANYA kalau:
- Field kosong, memory punya, similarity < 0.7
- Field kosong, memory tidak punya, **required**
- Field sudah ada isi, beda dengan memory
- Memory `last_verified` > 180 hari (field added in Sesi v0.2-3, see ADR-013)
- Default: skip fill untuk field yang sudah ada isi manual
- Flag: `--force` (overwrite)

### 5.6 Preview Handoff
- Browser tidak auto-close setelah fill
- Rich banner di terminal: "Review di browser. Klik Submit kalau OK."

### 5.7 Two-Way Sync MVP (ADR-012)
- Submit detection via JS submit event listener
- On submit: extract final values → diff vs memory → update DB
- On tab-close-without-submit: log warning, diff on next run
- NOT real-time input watcher (v0.3)

### 5.8 Command Shortcut (ADR-011)
- `formpilot auto <url>` = `--ai --use-memory --auto-fill --profile ask --preview`
- `formpilot auto --user <name> <url>` untuk multi-user
- `formpilot auto --browser <name> <url>` explicit browser

### 5.9 Multi-User
- Flag: `--user <name>`
- Memory path: `~/.formpilot/users/<name>/`
- Default: `default` (backward compat v0.1.0)
- Prompt on first run: "Nama user?"

---

## 6. Scope v0.2.1 (2 sesi polish)

### 6.1 Bahasa Interface (id/en)
- Simple dict-based i18n, no external library
- Flag: `--lang id|en`
- Priority strings: prompts, banners, errors
- Internal logs stay English

### 6.2 Memory Export/Import
- `formpilot memory export <file.json>`
- `formpilot memory import <file.json>` (merge default, `--replace` flag)
- JSON schema versioned
- Use case: backup, migrate laptop

---

## 7. Non-Goals v0.2

| Fitur | Target |
| :--- | :--- |
| Full two-way sync (real-time) | v0.3 |
| Firefox support | v0.3 |
| Web UI (localhost) | v1.2 |
| Dropdown filling | v0.2.1 |
| Multi-page refinement | v0.2.1 |
| Cloud sync | Never |
| Auto-submit | Never |
| Obfuscation / license binding | Never (ADR-001) |

---

## 8. Design Decisions (Locked via ADR-007..012)

- **ADR-007:** Hybrid profile strategy (existing default, isolated fallback)
- **ADR-008:** Auto-fill confidence 0.7 + staleness 180 hari
- **ADR-009:** Smart ask field safety (skip default, prompt on conflict)
- **ADR-010:** Chromium v0.2, Firefox v0.3
- **ADR-011:** `formpilot auto` command shortcut
- **ADR-012:** Two-Way sync MVP = submit detection only
- **ADR-013:** Extend memory schema with `last_verified` (in Sesi v0.2-3)

---

## 9. Target End State v0.2.0 (Definition of Done)

User baru bisa:

1. Install via `pip install -e ".[dev]"`
2. Run `formpilot auto <url>`
3. Browser picker → pilih Edge → prompt "Tutup tab?" → Y
4. Edge relaunch, **instant login** (cookies existing profile)
5. Form terisi otomatis dalam <30 detik (memory matured)
6. Terminal: "Preview di browser. Klik Submit kalau OK."
7. User edit 2 field, klik Submit
8. Terminal: "Detected 2 changes. Memory updated."
9. Run `formpilot auto <url2>` → 2 changes applied → 0 prompts

**Time from run to submit: ~2 menit** (dari 15-30 menit manual).
**Prompt count after memory matured: 0-1 per form** (dari 5-10).

---

## 10. Risks & Mitigations

| Risk | Mitigasi |
| :--- | :--- |
| User close 30 tab kerjaan | Prompt + isolated fallback (ADR-007) |
| Memory stale → auto-fill salah | Threshold 0.7 + staleness 180d (ADR-008) |
| User tutup tab tanpa submit | Diff on next run (ADR-012) |
| Multi-account ambiguity | Detect & prompt (5.3) |
| CDP port conflict | Kill + prompt (ADR-007) |
| Browser detection gagal | Manual path fallback |

---

## 11. Success Metrics v0.2.0

- Prompt count setelah memory matured: <1 per form
- Time to fill: ~2 menit
- Memory accuracy: 85% auto-fill matches final
- User feedback: "Feels magical but in control"

---

## 12. Roadmap v0.2.0 (7 sesi)

| Sesi | Target | Deliverable |
| :--- | :--- | :--- |
| 1 | Browser picker + profile strategy | `browser_manager.py`, ADR-007 impl |
| 2 | Multi-account + auto-launch | Account detect, prompts |
| 3 | Auto-fill mode + threshold | `--auto-fill`, ADR-008 impl |
| 4 | Field safety | Diff vs existing, ADR-009 impl |
| 5 | Preview + submit detect | Watch submit, banner |
| 6 | Two-way sync + `auto` shortcut | ADR-011, ADR-012 impl |
| 7 | Multi-user + tests + docs + tag v0.2.0 | `--user`, release |

**v0.2.1** (2 sesi): Sesi 8 i18n, Sesi 9 export/import.

---

## 13. Referensi

- `PRODUCT.md` — v0.1.0 baseline
- `ROADMAP.md` — Milestones lengkap
- `DECISIONS.md` — ADR-007 to ADR-012
- `tasks/current/prd_v020.md` — Detailed PRD
- `docs/STATE.md` — Sesi log

---

**End of VISION-V020.md**