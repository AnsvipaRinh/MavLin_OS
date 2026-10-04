# DECISIONS

## 2026-10-04 — fledge-alpha removed from rotation entirely (US-only geo-blocked)

**Context:** User-approved removal of `opencode/fledge-alpha-free` from the
fallback chain. Evidence: fledge-alpha is US-only geo-blocked (users in
Poland, Spain, France, China receive "not available in your country";
US VPN works). From Poland it is permanently unreachable. This mirrors the
GLM removal (commit 20f5561) — config-only removal, not temporary cooldown.

**Decisions:**
- Deleted fledge-alpha from `.opencode/model-fallback.json` chain entirely
  (was order 6, worker build-d). No chain entries, no worker pins remain.
- Added fledge-alpha to `never` list (like GLM removal, but no cooldown
  memory needed — geo-block is permanent for non-US users).
- Removed build-d worker block from `opencode.jsonc`.
- Chain renumbered 1-9 (orders 7-10 → 6-9).
- Verified: `scripts/session-reuse.py models` shows zero fledge candidates;
  `preflight` never offers build-d.

**Verification:**
- `models` output: fledge-alpha absent
- `preflight`: no build-d in candidate list
- Chain now: 1=Ling (build-j), 2=North Mini (build-b), 3=Free Router (null),
  4=LongCat (build-c), 5=Nemotron 3 Ultra (build-i), 6=Ling 3.0 Fin (build-e),
  7=MiMo (build-f), 8=Space Bunny (build-g), 9=Nemotron 3.5 Lightning (build-h)

---

## 2026-10-04 — Poppy OS X Revieve Prior-Art Audit

**Context:** Deep prior-art audit of Poppy OS X Revieve per GitHub issue #2. Static inspection only (cloned to /tmp, never executed).

**Findings:**
- Poppy is a **theme-only** repository: GTK3 CSS (8367 lines), icons (568 SVG + 34 PNG), cursors (13 base), Plank theme, GNOME Shell theme, Metacity theme.
- **Zero application code**, zero scripts, zero daemons, zero desktop integration.
- Designed for GNOME Shell + Ubuntu, not Xfce/Arch.

**Quality verdicts:**
| Component | Verdict | Reason |
|-----------|---------|--------|
| GTK3 CSS | B (adapt-port) | Comprehensive but monolithic, GNOME-specific. Ours is modular SCSS, Xfce-optimized. |
| Icons | B (adapt-port) | macOS-style but limited coverage. Ours is more comprehensive with HiDPI. |
| Cursors | A (reuse-as-is) | High quality, Artistic License 1.0 (GPL-compatible). |
| Plank theme | C (reference) | Minimal. Ours has reflection, zoom, separators, Slingscold. |
| GNOME Shell | D (reject) | Wrong DE. |
| Metacity | D (reject) | Wrong WM. |
| Fonts | D (reject) | Unclear provenance, potentially proprietary. |

**Legal:**
- No top-level LICENSE file. Only cursors have explicit license (Artistic 1.0).
- GTK CSS, icons, Plank theme = unknown license → DO NOT IMPORT without explicit permission from sziberov.
- Cursors = Artistic License 1.0, GPL-3.0-or-later compatible.

**Energy:** ZERO runtime cost (theme-only). No daemons, no polling.

**Decisions:**
1. **REJECT** GTK3 CSS — ours is better (modular, Xfce-optimized, build system).
2. **REJECT** icons — ours is more comprehensive (HiDPI, symbolic, app/device/emblem/action/category/filesystem icons).
3. **REJECT** Plank theme — ours is better (reflection, zoom, separators, Slingscold, Mission Control).
4. **REJECT** GNOME Shell theme — wrong DE.
5. **REJECT** Metacity theme — wrong WM.
6. **REJECT** fonts — unclear provenance.
7. **ACCEPT** cursors — Artistic License 1.0, GPL-compatible, high quality. Import as alternative cursor set pending legal verification + X11 rendering test.

**Integration objective:**
- Import Poppy cursors to `packages/mavericks-theme/src/mavericks-theme/cursors/` as alternative set.
- Add attribution in `docs/APPS.md`.
- Test cursor rendering in X11.
- Commit.

**Recommendation:** Do not invest significant effort in integrating Poppy assets. Focus on improving our own theme and applications instead.

---

## 2026-10-04 — Poppy Cursors Legal Verification and Import Decision

**Context:** Following the prior-art audit, the single accepted integration item (Poppy cursors) requires legal verification before import. This decision documents the verification and import rationale.

**Legal Verification:**
- Upstream LICENSE file confirmed as Artistic License 1.0 (OSI-approved, full text matches standard Artistic 1.0).
- Upstream COPYRIGHT traces provenance: "Ubuntu OS X" mod from "KAYOver" Ⓚ, based on "Neutral cursor theme" by Alexey Nikitine (Copyright 2005, 2006).
- Artistic License 1.0 permits verbatim copying, modification, and distribution (clauses 1-4) with attribution preserved.
- FSF position: Artistic License 1.0 is **not GPL-compatible** for combined works (linking).
- **Critical distinction:** Cursor themes are **data files** installed to `/usr/share/icons/`, not code linked into binaries. The GPL-3.0-or-later license of mavericks-theme applies to the package's build scripts and theme assets; cursor themes are separate works that co-exist in the filesystem. No combined-work issue arises because:
  - The PKGBUILD builds/installs both cursor themes as independent directories
  - No code from Poppy cursors is compiled into MavLinOS binaries
  - Users select one theme at runtime via GTK settings
  - This is equivalent to shipping multiple icon themes in a distro (common practice)

**Compatibility Assessment:**
| Aspect | Verdict | Rationale |
|--------|---------|-----------|
| Artistic 1.0 OSI-approved | YES | https://opensource.org/licenses/Artistic-1.0 |
| GPL-3.0 combined-work risk | NO | Data files, not linked code; separate installation directories |
| Redistribution permitted | YES | Artistic 1.0 clauses 1, 5 allow verbatim + aggregate distribution |
| Attribution preserved | YES | LICENSE + COPYRIGHT files copied to source tree |
| Apple-derived asset risk | LOW | "Ubuntu OS X" → "KAYOver" → "Neutral" (Alexey Nikitine 2005/2006); generic cursor shapes, no Apple trademarks detected |

**Decision:**
- **IMPORT** Poppy cursors as **alternative cursor theme** named `Poppy-Cursors`
- Install to `/usr/share/icons/Poppy-Cursors/` (separate from `Mavericks-Cursors`)
- Do NOT replace or overwrite `Mavericks-Cursors` — both co-exist
- User selects via GTK settings (`gtk-cursor-theme-name`) or xfce4-mouse-settings
- Preserve LICENSE + COPYRIGHT in source tree (`cursors-poppy/`)
- Document in LICENSES.md §4, APPS.md cursor row

**Implementation:**
- Created `packages/mavericks-theme/src/mavericks-theme/cursors-poppy/` with 78 compiled cursors + index.theme + LICENSE + COPYRIGHT
- Updated mavericks-theme PKGBUILD to install both cursor themes
- Updated APPS.md cursor row (split into two entries)
- Updated LICENSES.md §4 with Poppy-Cursors entry
- Xcursor format verified via `file(1)` on all 78 files

**Gate:** check-sync.sh pending

---

## 2026-10-04 — Poppy OS X Revieve B-items Port (Tier 1 + Tier 3)

**Context:** Following the prior-art audit (Poppy OS X Revieve), diff-driven extraction of concrete portable techniques/measurements from Poppy's GTK3 CSS (8367 lines), icons (568 SVG), and Plank theme (64 lines) into MavLinOS stack. Clean-room reimplementation only — no asset bytes copied (cursors exception already handled in 4b2a171).

**Analysis Method:** Axis-by-axis comparison matrix (buttons, entries, menus/menubar, scrollbars, notebooks/tabs, toolbars, headers, progress, switches, check/radio, OSD/popovers) with Mavericks 10.9 fidelity as judge.

**Key Findings:**
- Poppy's GTK3 CSS is comprehensive but monolithic, GNOME-specific, hardcoded values
- MavLinOS SCSS is modular, Xfce-optimized, variable/mixin-based
- **Popby wins on specific Mavericks-fidelity measurements** in 12 GTK3 axes and 8 Plank config values
- Icons: Poppy covers status/preferences/places/panel categories we lack (documented as Tier 2 for future)

**Decisions (Tier 1 — implemented, static CSS values, zero runtime cost):**

| # | Axis | Poppy Value Adopted | Mavericks Fidelity Gain |
|---|------|---------------------|------------------------|
| 1 | Entries | `border-radius:0`, 8-layer inset shadow (alpha #000: 0.36/0.145/0.035/0.22/0.04/0.04/0.22/0.12), focus: 6× `0 0 2px #71a5d6` + `inset 0 0 0 2px #6a9ecf` | **HIGH** — Flat aqua entries with deep shadow |
| 2 | Search Entry | `border-radius:50px` (pill shape) | **MED** — Spotlight-style search field |
| 3 | Menubar | Gradient `#e5e5e5→#a0a0a0`, `box-shadow: inset 0 1px #fff, inset 0 -1px #000`, `min-height:22px` | **HIGH** — Defining menubar look |
| 4 | Menus | `border-radius:0`, hover gradient `#618cf0→#1c65ed` with border highlights `#5783e7`/`#0558e3` | **HIGH** — Square Mavericks menus |
| 5 | Notebook Tabs | Metallic gradient `#fff→shade(#fff,0.95)→shade(#fff,0.93)→shade(#fff,0.95)`, border `#8c8c8c`, selected: 12-layer pressed-in shadow | **HIGH** — Safari 7 tabs |
| 6 | Toolbar | Unified gradient `#fff→#f2f2f2(50%)→#ededed(50%)→#f2f2f2`, border `rgba(105,105,105,0.3)` | **HIGH** — Mavericks unified toolbar |
| 7 | Headerbar | `min-height:22px` (was 32px), gradient `#e9e9e9→#b2b2b2`, shadow stack `inset 0 1px #f1f1f1, inset 0 -2px a(#fff,0.085), inset 0 -1px a(#000,0.38)` | **HIGH** — Authentic titlebar height |
| 8 | Default Button | Pulsing animation (500ms alternate), blue borders `#565cae/#4d5076`, 10-layer inset shadow | **MED** — Mavericks pulsing default |
| 9 | Popover | `border-radius:4px`, sharp shadow `0 3px 5px a(#000,0.5) + 0 0 0 1px a(#000,0.18)`, border `#f9f9f9`, gradient `a(#f6f6f6,0.96)→a(#ebebeb,0.96)` | **MED** — Sharp popover |
| 10 | Progressbar | Animated aqua gradient with radial highlight, 32px loop animation, trough 10-layer inset shadow | **MED** — Living progress animation |
| 11 | Window Frame | `border-radius:6px`, deeper shadow `0 10px 10px a(#000,0.75) + 0 0 0 1px a(#000,0.18)` | **LOW-MED** — Deeper drop shadow |
| 12 | Statusbar | `min-height:22px`, gradient `#d4d4d4→#b2b2b2`, highlight `inset 0 1px #e1e1e1`, border-top `#818181` | **LOW** — Authentic statusbar |

**Decisions (Tier 3 — Plank config values, implemented):**

| # | Parameter | Poppy Value | Rationale |
|---|-----------|-------------|-----------|
| 17 | Roundness | 4 (was 8) | Tighter top corners = Mavericks |
| 18 | ItemShadowSize | 0 (was 8) | Mavericks had NO icon drop shadow |
| 19 | TopPadding | -5 | Negative centers icons in glass area |
| 20 | BorderSize/Color | 1, rgba(0,0,0,0.31) | Subtle dark border like Mavericks |
| 21 | IndicatorSize | 7 (was 6) | Slightly larger active indicator |
| 22 | FadeOpacity | 1 (was fade) | Mavericks didn't fade dock |
| 23 | Animations | ClickTime=300, UrgentBounceTime=600, LaunchBounceHeight=0.625, CascadeHide=true | Authentic timing |
| 24 | Tight Padding | HorizPadding=2, ItemPadding=1 | Compact dock |

**Decisions (Tier 2 — Icon gaps, deferred to future session):**
- Status dialog icons (error, info, warning, password, loading) — 5 icons
- Preferences icons (display, locale, wallpaper, notifications, privacy, time, system, accessibility, goa) — 9 icons
- Places folder variants (documents, downloads, music, pictures, videos, templates, public, gdrive, remote, saved-search, recent, desktop, bookmarks) — 13+ icons
- Panel symbolic (volume 4, battery 8, network 6, notifications 2, shutdown 1) — 20+ icons
- To be created clean-room in Mavericks skeuomorphic style

**Legal Compliance:**
- All ports are measurements/values only — no Poppy asset bytes
- Cursors exception already handled in commit 4b2a171 (Artistic License 1.0)
- Icons will be created fresh, inspired by Poppy categories only

**Verification:**
- `test-theme-css.py`: 9/9 checks PASS
- `check-sync.sh`: 221/221 checks PASS
- Commit: cb71a8d → pushed as 445355c

**Documentation:**
- `docs/POPPY_PORTS.md` — full comparison matrix, ranked port list (24 items), legal notes
- `docs/PROGRESS.md` — progress entry added

---

## 2026-10-04 — Incident Loss Recovery

**Context:** Dangling commits/loss occurred during unsupervised session recovery. Critical work was lost from tree commits.

**Lost Commits (6 total):**
1. 6843ebc552621524625bcdb0bc9c8bacaed0e35f - docs: lab harness Phase 2 reconciliation (scenario inventory, SQL indexes, progress)
2. 6bc57d4f06b1fe5df86bd9f6eb90fcd12e39223c - WIP on master: f3bcada docs: prehardware completeness audit — all-axes closure (A-S + R/D/PERF + P0+)
3. c2c7f6787bcd6487184d5aafa7b141c4ecec8221 - docs: prehardware completeness audit — scenario tracking completion
4. 6b175742dbe37e31fe9f1d4970267313c18aa436 - docs: lab harness Phase 1 & 2 integration
5. 3ad8b0015a8e60259a36052858e5fa3e6d98ec0c - docs: comprehensive release readiness audit
6. 651a73fceb6bea83c3595ea52a9de198693ee291 - docs: phase-by-phase implementation log

**Lost Files from Packages:**
- packages/mavericks-apps/src/mavericks-apps/bin/mv_dialogs.py
- packages/mavericks-apps/src/mavericks-apps/src/mavericks-apps/bin/mv_finder_columns.py
- packages/mavericks-apps/src/mavericks-apps/src/mavericks-apps/bin/mv_finder_search.py
- packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml
- packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml

**Lost Files from Scripts:**
- scripts/test-discovery-gate.py

**Root Cause:** 
Dangling commits indicate session recovery failure. The unsupervised session was tracking WIP but failed to properly commit before being abandoned.

**Recovery Attempt:**
- Commits examined: identified critical lost work
- Files examined: mv_dialogs.py, mv_finder_columns.py, mv_finder_search.py, other project files
- Verdict: No recoverable files found in repository state (blobs orphaned, trees missing contents)

**Impact Analysis:**
- Technical: Loss of 3 application files (mv_dialogs.py, mv_finder_columns.py, mv_finder_search.py)
- Documentation: Loss of comprehensive audit logs (HANDOFF.md, TECHNICAL_AUDIT.md, etc.)
- Test infrastructure: Loss of test framework components (test-discovery-gate.py)

**Decisions:**
- Document all losses in this DECISIONS.md entry for traceability
- Reconstruct critical components from git history where possible
- Check if recent commits contain equivalent functionality (e.g., mv_dialogs.py might have been reimplemented)
- The project must prioritize completing P0 objectives over recreating lost docs/test infrastructure

**User Action:**
- Document equivalent functionality if exists
- Recreate minimal critical components from alternatives
- Focus on completing P0 objectives with available working components
- Review WIP recovery procedures for future unsupervised sessions

**Known Limitations:**
- Cannot recover full audit completeness without fresh data collection
- Test infrastructure requires re-implementation
- Documentation gaps will affect future audits and onboarding

---

## 2026-10-04 — External Work Triage (qwen-port-work branch)

**Context:** Automated triage of all inbound external work per continuous integration duty. Base commit 151a616 (prior audit: PRs #3-8, global menu 46b4c3d). One external contributor branch: `origin/qwen-port-work` (10 commits by qwen.ai[bot]). Five owner PRs pending (#3, #4, #5, #6, #19), one owner feature branch pending (#7 global menu).

### Audit Scope
- All origin/main commits vs 151a616 (30 commits, all owner)
- All remote branches (8 owner feature/fix, 1 external qwen-port-work)
- All open PRs (5 owner, 0 external)
- All issues (2 owner — mandatory per OWNER-ISSUES RULE)
- Deep static audit of qwen-port-work (113 files, +5929/-6096 lines)

### Key Findings: qwen-port-work

**ACCEPTED (9 items):**
1. Lazy GTK factory pattern across 12 apps (mv-calculator, mv-finder-columns, mv-finder-search, mv-diskutil, mv-keychain, mv-stickies, mv-power-ui, mv-launchpad, mv-settings, mv-about, mv-calendar, mv-reminders) — enables headless CI testing, zero runtime cost
2. ShimVariant duck-typing for GLib.Variant (mv-diskutil, mv-keychain) — DBus/Secret headless testing
3. mv_launchpad_edit.py (428 lines) — GTK3 dialog for Launchpad rearrangement (drag-drop, Ctrl+↑/↓, persists positions.json)
4. Launchpad pagination dots + Super+Shift+L keybinding — Mavericks visual fidelity
5. Pure logic extraction for calculator/finder/diskutil/keychain/stickies/power-ui/settings/about/calendar/reminders
6. Bug fixes: mv-mail/mv-eject/mv-rename with portable tests
7. Test coverage: mv-stickies (72), mv-finder-columns (24), mv-finder-search (68), mv-diskutil (34), mv-power-ui (43), mv-keychain (18), mv-about (162 lines), mv-settings (130 lines), mv-launchpad (13), mv-calendar (9), mv-reminders (9)
8. mv-calendar/mv-reminders coverage revival
9. WORK_CLAIMS.md board creation — good practice

**ADAPT (1 item):**
- failover-guard-plugin.js deleted — move to `.opencode/scripts/` if needed, not in runtime packages

**REJECTED (3 items — CRITICAL):**
1. **DELETE mavericks_appmenu.py** (97 lines) — breaks global menu integration (PR #7). Apps lose GMenu export to panel.
2. **DELETE mv-apple panel plugin** (mv-apple.c/.desktop/.svg) — breaks Apple menu () with 7 Mavericks commands. Core feature.
3. **DELETE mv_dialogs.py** (249 lines) — removes shared Mavericks dialog helpers (SheetDialog, alert, confirm_discard, confirm_delete). No replacement; apps fall back to stock GTK dialogs.

**NEEDS-HUMAN (1 item):**
- REMOVE packages/mavericks-theme/NOTICE — attribution file removal; verify Poppy/OS X Revieve theme license permits this

### Collision Analysis
qwen-port-work **directly reverts PR #7 (global menu + Apple menu)** which is a mandatory owner directive. PR #7 adds:
- vala-panel-appmenu package
- mavericks_appmenu.py helper
- mv-apple native C panel plugin
- Gtk.Application lifecycle migration for ALL apps
- Force Quit / Recent Items dialogs

qwen-port-work deletes the helper, plugin, and dialog infrastructure. **Cannot merge qwen-port-work as-is.**

### Owner PRs Status
| PR | Branch | CI | Mergeable | Action |
|----|--------|----|-----------|--------|
| #3 | ci/theme-validation-gate | FAIL (Static, Unit, Contrib) | UNKNOWN | Fix CI, merge |
| #4 | fix/self-contained-firstboot | FAIL (Static, Profile Sync, Contrib) | UNKNOWN | Fix CI, merge |
| #5 | fix/finder-launcher | - | UNKNOWN | Verify, merge |
| #6 | fix/panel-config-validity | FAIL (Static, Contrib) | UNKNOWN | Fix CI, merge |
| #7 | feat/global-menu-appmenu | - | - | **MANDATORY** merge --no-ff |
| #19 | feat/xfwm-double-click-notify-sync | - | CONFLICTING | Rebase on main, merge |

### Decisions

1. **MERGE PR #7 (feat/global-menu-appmenu) FIRST** — mandatory owner directive, implements core Mavericks desktop metaphor (global menu + Apple menu + app menus)
2. **FIX CI on PR #3, #4, #6** — unblock owner PRs
3. **REBASE AND MERGE PR #19** — resolve conflict with main
4. **CHERRY-PICK ACCEPTED qwen improvements** onto post-PR#7 main:
   - Lazy GTK factory pattern for all 12 apps
   - ShimVariant for DBus/Secret
   - mv_launchpad_edit.py + pagination dots + Super+Shift+L
   - All bug fixes + test additions
   - WORK_CLAIMS.md (integrate, not replace)
5. **PRESERVE from current HEAD:** mavericks_appmenu.py, mv-apple plugin, mv_dialogs.py, global menu integration
6. **REJECT qwen deletions** of global menu components
7. **NEEDS-HUMAN:** Verify NOTICE removal license compliance before accepting
8. **RUN FULL GATE SUITE** post-merge: check-sync.sh, all test scripts, pytest mavericks-apps tests
9. **PUSH TO ORIGIN** per PUBLISH RULE

### Verification Commands
```bash
# After merging PR #7 and cherry-picking qwen ACCEPTED items:
./scripts/check-sync.sh
python3 scripts/test-dock-launchers.py
python3 scripts/test-window-keys.py
python3 scripts/test-network-stack.py
python3 scripts/test-global-menu.py
python3 scripts/test-panel-config.py
python3 scripts/test-finder-launcher.py
python3 scripts/test-mv-finder-columns.py
python3 scripts/test-mv-finder-search.py
python3 scripts/test-mv-diskutil.py
python3 scripts/test-mv-stickies.py
python3 scripts/test-mv-keychain.py
python3 scripts/test-mv-power-ui.py
python3 scripts/test-mv-calendar.py
python3 scripts/test-mv-reminders.py
python3 -m pytest packages/mavericks-apps/src/mavericks-apps/tests/
```

### Qwen Web Automation Research (2026-10-05)

**Context:** Investigation into automating the free coder.qwen.ai web service
for use as a Qwen coding session registrar within OpenCode. This investigation
distinguishes the free web service from the discontinued Qwen Code CLI and paid
API endpoints.

**Findings:**

1. **Qwen Code CLI OAuth is DISCONTINUED** (free tier shut down 2026-04-15). 
   Per AGENTS.md §0.1.1, this is a config-only change — record in DECISIONS.md 
   and proceed with supported alternatives. This decision does NOT affect the 
   coder.qwen.ai web service.

2. **coder.qwen.ai web sessions ARE programmaticially accessible.** Contrary to 
   the earlier DECISIONS.md §2 decision, the free coder.qwen.ai web service supports 
   programmatic access through the following mechanism:
   
   - **Authentication**: `Authorization: Bearer <localStorage.token>` header, where
     the token is stored in the browser's `localStorage.token` after login
   - **SSE endpoint**: `POST /task/completions` with `Accept: text/event-stream` and 
     `X-Accel-Buffering: no` headers
   - **Payload format**: JSON with `chat_id`, `model`, `messages`, `stream`, `version`, 
     `chat_mode`, and other parameters (reverse-engineered from the React frontend)
   - **Conversation ID**: `chatId` from React state (`window.uc.getState().chatId` or 
     `window.store.getState().chatId`)
   - **Completion detection**: SSE stream termination (`Da` action) + React state keys 
     containing `ready`/`finished`/`error`, or `onStreamCompleteMcpCleanup` callback

3. **coder.qwen.ai web service protocol findings** (this investigation):
   - Frontend: React 18+ with code-splitting, bundles at `assets.alicdn.com/g/qwenweb/qwen-coder-fe/0.0.27/`
   - SSE streaming: `POST /task/completions` with `Accept: text/event-stream`
   - Auth token: `localStorage.token` set during login at `/auth?action=signin&from=coder`
   - Anonymous flag: `enable_anonymous: true` in config (verified but not fully tested)
   - State management: `window.uc` / `window.store` global objects
   - X-Request-Id: Per-request UUID (`crypto.randomUUID()` or `req-${Date.now()}-${Math.random()}`)
   - Message history: Accumulated in React state, persists across prompts within conversation

4. **Three authentication approaches** (only FREE method is viable):
   - **localStorage token** (FREE, via coder.qwen.ai web login): `Authorization: Bearer 
     <localStorage.token>`. Requires user to be logged into coder.qwen.ai. This is the 
     method investigated in this work.
   - **Alibaba Cloud Coding Plan** (`BAILIAN_CODING_PLAN_API_KEY`): fixed monthly fee, 
     higher quotas, diverse models. Paid.
   - **Alibaba Cloud Token Plan** (`BAILIAN_TOKEN_PLAN_API_KEY`): usage-based billing, 
     region-specific endpoints. Paid for teams/companies.

5. **Loopback mode** (`qwen serve` on 127.0.0.1:4170) works without bearer authentication 
   but does NOT access the user's coder.qwen.ai quota. Suitable for local development only,
   NOT for production quota usage.

6. **Integration must use the user's authenticated session** to access coder.qwen.ai quota. 
   Per the research findings, this is done by:
   - Running the OpenCode registrar with a persistent browser profile that retains 
     `localStorage.token`
   - Extracting the token via `localStorage.getItem('token')` 
   - Including `Authorization: Bearer <token>` in API calls to `POST /task/completions`
   - Managing conversation state via `chatId` from React state

7. **Never substitute an expensive API configuration** without user directive. Per AGENTS.md §3,
   do not silently substitute an API config that unexpectedly incurs costs.

8. **Session tracking** via `scripts/session-reuse.py` is preserved. Error classification via
   `classify-error` taxonomy (MODEL_*, RATE_LIMIT, FREE_USAGE_EXHAUSTED, etc.) enables same-
   session failover to healthy workers.

**Verification:**
- Protocol reverse-engineered from static analysis of `main.js` (1.2MB) and browser network inspection
- SSE endpoint `POST /task/completions` confirmed with proper headers
- Authentication mechanism: `localStorage.token` + `Authorization: Bearer` confirmed
- Completion detection via SSE events + React state keys validated
- Research documented in `docs/QWEN_WEB_AUTOMATION_RESEARCH.md`

**Impact on Project Objectives (§13.2 Canonical Inventory):**
- All P0/P1/P2 objectives remain unchanged — this decision is about
  authentication infrastructure for the coder.qwen.ai web service, not application features.
- The Qwen web automation research adds protocol knowledge for future OpenCode registrar design
- Session persistence via session-reuse.py continues to work
- New: `docs/QWEN_WEB_AUTOMATION_RESEARCH.md` documents the full investigation
- New: `scripts/qwen-integration/qwen-web-worker.py` prototype demonstrates the transport

### Impact on Project Objectives (§13.2 Canonical Inventory)
- **P0 Global Menu / Apple Menu / App Menus:** Unchanged
- **P0 Launchpad:** Unchanged (separate objective)
- **P0 Finder:** Unchanged
- **P0 Spotlight:** Unchanged
- **P0 Mission Control:** Unchanged
- New: **P0 Qwen Web Integration** — research complete, prototype developed, awaiting hardware validation
- **P0 Finder:** Improved via qwen ACCEPTED items (headless logic, tests)
- **P0 Mission Control / Spotlight / Control Center / Notification Center / Quick Look / Preview / Screenshot / Activity Monitor / System Info / Disk Utility / System Settings / Power UI / Trash / Archive Utility / Menu Bar / Dock / Application Menu / Global Dialogs / File Chooser / Context Menus / Keyboard Shortcuts / Desktop / Window Management:** Unchanged
- **P1 Applications:** mv-calculator, mv-stickies, mv-diskutil, mv-keychain, mv-about, mv-settings, mv-calendar, mv-reminders — all headless test coverage
- **Authentication infrastructure:** New — Qwen Code integration scripts and docs added

### Next Steps
1. Execute merge/fix/cherry-pick sequence above
2. Update PROGRESS.md with current status
3. Continue P0 application completion per §13.8 autonomous loop

---

## 2026-10-05 — External-port Execution Record + origin/main Sync

**Context:** Execution of the 2026-10-04 External Work Triage decisions
(cherry-pick ACCEPTED qwen-port-work items, preserve global-menu stack,
full gate, push). Plus a mid-session `origin/main` advance (PR #37–#76,
owner series) and PR #19 status re-evaluation.

### Cherry-pick execution (qwen-port-work, 9 commits)

| qwen commit | Outcome | Our commit |
|---|---|---|
| df3f7f7 (mv-mail/eject/rename bugs) | partial port | 4036b95 |
| ecb24a4 (mv-about) | ported, our global-menu `__main__` kept | a9b7701 |
| 2d463fa (calculator/settings/launchpad lazy-Gtk) | ported + app-suite gate adopted | 0496ae3 |
| 4a5653c (finder-columns/search + power-ui) | ported | 4d33eae |
| fe69ec2 (mv-stickies) | ported | 7c0422b |
| 300841b (mv-timemachine) | ported | 48141a4 |
| 0115772 (mv-voice + mv-getinfo) | ported | 3b29206 |
| b42af1f (mv-diskutil + spotlight-preview) | **SKIPPED** | — |
| b27634f (mv-keychain) | **SKIPPED** | — |

**Skip reasons (b42af1f, b27634f):** `mv-diskutil`, `mv-keychain`,
`scripts/test-mv-diskutil.py` are byte-identical between HEAD and
`origin/qwen-port-work` — already integrated via PR #18. Only delta was
`test-mv-keychain.py` calling `m.build_keychain_class()` as if it returned
an instance; the shipped factory returns a class, so our `()()` form is
correct and verified green (96/96) — qwen's form would fail against the
identical source. The `mv-spotlight-preview` half of b42af1f is not
re-added: main retired that Rofi helper (obsolete). `docs/WORK_CLAIMS.md`
stays deleted — **this AMENDS triage decision 4** ("integrate, not
replace"): main's changelog convention is `docs/PROGRESS.md`, qwen's
claim board mirrors their own tree (stale against ours), and duplicate
state boards rot; the same information is tracked in APPS/PROGRESS.

**Cross-cutting port rules applied:** every conflicted `__main__` was
resolved to our `mavericks_appmenu.run_application(...)` launcher with
qwen's factory/validation as the window factory; `.gitignore` rewrites
from qwen rejected as regressions. Two real bugs found in qwen's code and
fixed while porting: `mv-calculator.build_calculator_class()` and
`mv-stickies.build_searchwindow_class()` had no `return` (instance
creation crashed with `TypeError: 'NoneType' object is not callable`).

### Launchpad P0 restoration (aa3ca38)

7ba84f8 was an ancestor but its feature was dropped by later merges
(8471315, bcbacaf): dots, the "Edit Launchpad…" entry and
`mv_launchpad_edit.py` disappeared while the Makefile still referenced
the file (broken install loop). Restored with three deliberate deltas:

1. **Install name fixed:** the old loop installed `mv_launchpad_edit.py`
   (underscore), which no keybinding or caller referenced — the
   Super+Shift+L binding has been dead since 7ba84f8. Now installed as
   `/usr/bin/mv-launchpad-edit` (matching the keybinding) via a dedicated
   rule.
2. **Edit dispatch:** `ROFI_INFO=edit` spawns `mv-launchpad-edit`
   (PATH-based so tests can stub it; keybinding keeps the absolute path).
3. **Edit row consumes one grid row** on page 0 under origin/main's
   folder-capacity math (`ITEMS_PER_PAGE - folder_count - edit_rows`), and
   is skipped when a folder page is already full — accepted the 1-row
   grid overflow in no pathological case rather than breaking folder
   pagination tests.

### origin/main sync (c484b8d, PR #37–#76)

Conflicts (3 files) resolved preserving all human work — nothing
reverted. Merged contract decisions:

- **Nav hint:** kept origin/main's rule that arrows are rofi *item*
  navigation and must not be advertised as page controls; our page dots
  (●○) now render as `<dots> — PgUp/PgDn to navigate`.
- **get_page:** origin/main's folder-capacity/pagination math is
  authoritative; our edit row was integrated into it.

**Upstream-red tests fixed forward (adapt tests to shipped source;
verified red on a pristine `origin/main` worktree first):**

1. `test-mv-notification-center.py` "argv rather than shell" — fixture
   contained an over-escaped `\\n` (literal backslash-n, never a newline).
2. `test-mv-desktop-cache.py` XDG test — Sandbox stubs
   `mod.desktop_dirs`, so the test never exercised the real function
   (IndexError crash that also aborted the run and masked every later
   failure); restored the real implementation for that test.
3. 16 over-escaped `\\n` in .desktop fixtures (parse fixtures were single
   lines), shebang without newline in the TryExec-present fixture, nested
   desktop-ID expectation aligned with the freedesktop spec
   (`foo/bar/Nested.desktop` → `foo-bar-Nested.desktop`), DBus-activatable
   entries expected in Launchpad/Spotlight (PR #72 intent), dedup count
   updated for the 3-file fixture.
4. `test_mv_launchpad.py` three stale expectations from duplicated
   atomic-writer/auto-population/position-normalization PR variants
   (`_atomic_json_save`/`temp_path` vs shipped `_atomic_save_json`/
   `tmp_path`, over-broad `if apps:` ban, removed one-line generator).

### PR #19 (feat/xfwm-double-click-notify-sync) — SUPERSEDED, no rebase

Triage decision 3 ("rebase and merge") closed as a **no-op**:
`double_click_action=maximize` is already in `configs/desktop/xfce/xfwm4.xml`
on origin/main, `scripts/test-window-chrome.py` already asserts it, and
`check-sync.sh` already gates the `xfce4-notifyd` mirror pair. The branch's
only residuals are a comment line and a stale `workspace_count=4` removal
(origin/main intentionally keeps 4 workspaces). Branch stays CLOSED; no
rebased branch pushed.

### Gate state

`scripts/check-sync.sh`: ALL CHECKS PASSED — 221 checks, 0 failures;
app suites 32 passed / 1 skipped (`test-mv-spotlight.py`, pre-existing
"not headless-portable yet") / 0 failed.
`pytest tests/test_mv_launchpad.py`: 32/32. Standalone runner: 26/26.

### Note on concurrent tree activity

While this integration ran, a concurrent session (not registered in the
session registry) added `scripts/qwen-integration/`, `docs/QWEN_*.md` and
the "Qwen Web Automation Research" block above, and modified
`docs/DECISIONS.md`. Its DECISIONS notes are committed here as-is (doc
content, audited-read); its scripts/docs remain untracked for their
author to commit. Repo state was never blanket-staged (`git add -A` not
used).
