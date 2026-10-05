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
app suites **33 passed / 0 skipped / 0 failed** — the last pre-existing
skip (`test-mv-spotlight.py`) was ported in the same session: two
tests loaded extension-less `bin/mv-spotlight` via
`spec_from_file_location` (returns None without a loader — now
`SourceFileLoader`), 24 over-escaped `\\n` made the .desktop fixtures
single lines, and the never-registered `desktop_launch_contract` test
was fixed to the canonical-ID contract (PR #64) and registered.
`pytest tests/test_mv_launchpad.py`: 32/32. Standalone runner: 26/26.

### Note on concurrent tree activity

While this integration ran, a concurrent session (not registered in the
session registry) added `scripts/qwen-integration/`, `docs/QWEN_*.md` and
the "Qwen Web Automation Research" block above, and modified
`docs/DECISIONS.md`. Its DECISIONS notes are committed here as-is (doc
content, audited-read); its scripts/docs remain untracked for their
author to commit. Repo state was never blanket-staged (`git add -A` not
used).

### 2026-10-05 — Global-menu contract regression (PR #18) found and restored

**Context:** `scripts/test-global-menu.py` (owner PR #7 contract test) was
wired into neither check-sync nor CI, so its red status went unnoticed.

**Findings (verified against git history, not assumed):**
- `mv-mail`, `mv-keychain`, `mv-diskutil` lost global-menu integration when
  PR #18's headless-safe rewrite (`0b4becf`) replaced their entries with a
  private `Gtk.main()` loop; `build_mail_menu`/`build_keychain_menu` were
  deleted with it. Pre-#18 code had `run_application` + builders.
- `mv-calculator` lost the literal `install_application_menu` reference when
  the qwen port (`0496ae3`) switched it to the shared `run_application`
  runner (functionally equivalent — the runner performs that install).

**Decisions:**
1. Restore the three apps' integration ON TOP of PR #18's lazy-factory
   design (never reverting #18): menu builder + `run_application` entry.
   `window_factory` must return an INSTANCE — passing the class-returning
   builder made `activate()` die with `Expected Gtk.Window, but got
   GObjectMeta`; only Xvfb launch smoke caught this, text tests could not.
2. mv-mail menu does NOT re-add "New Message" (owner removed it as
   nonfunctional in `c818a12`; owner directive stands). `launch` action
   now targets the post-#18 `launch_backend()` method.
3. `test-global-menu.py` calculator assertion changed from the literal
   `install_application_menu` to `run_application` (stale-vs-architecture;
   spec preserved: Calculator exposes its app menu via the shared runner).
4. `test-global-menu.py` is now run by `check-sync.sh` (which CI already
   runs) — orphan tests are exactly how this regression survived.
5. New `scripts/smoke-launch.sh` (Xvfb; graceful skip without xvfb-run/gi):
   launch-and-stay gate for windowed apps. Proven to catch the factory bug
   (red on the broken form, green after the fix). Wired for the three
   restored apps; extend to other P0 apps incrementally.
6. New `scripts/test-mv-mail.py` (23 tests): backend selection (geary →
   Mail UserAgent fallback → absent/ignore), menu builder against real Gio,
   runner contract.

### 2026-10-05 — Dock pins for plain pacman installs + stale P0 matrix rows

**Dock pins (P0 #18 gap "no pinned apps"):** pins existed only in the ISO
airootfs skel; `mavericks-theme` (the path for a plain pacman install)
shipped dock settings but no launchers, so non-ISO users got an empty
Dock. Decision: ship the pins as *package files* from
`configs/desktop/plank/dock1/launchers` (source of truth, sync-gated vs
airootfs) into `/etc/skel/.config/plank/dock1/launchers` — package files
are tracked/removed by pacman, unlike extending the `.install` heredoc
(which would create a third hand-maintained copy).
`scripts/test-dock-launchers.py` now also byte-compares configs ↔ airootfs
(all files, not just the required six) and asserts PKGBUILD coverage.
Verified with a real `makepkg -d -f`: package contains all six `.dockitem`
files, byte-identical to configs. pkgrel 2 → 3.

**Known build quirk (documented, not changed):** `mavericks-theme`
`build()` runs `optipng` in place over tracked sources under `src/`, so a
local `makepkg` rewrites ~267 PNGs (`git status` noise; revert with
`git checkout -- packages/mavericks-theme/src/mavericks-theme/` after a
build). Opting for documentation over restructuring package() (the
optimized output is the point of that step; a copy-based build would
double the tree and diverge from the current source layout).

**Stale P0 matrix rows corrected after verification (§13.5):**
- *Menu Bar* → IMPLEMENTED — HARDWARE VALIDATION REQUIRED: global menu
  exists (vala-panel-appmenu + appmenu-gtk-module + mv-apple; the row's
  "no global-menu plugin" was false). Panel has no tasklist/applicationsmenu
  by design (macOS model).
- *Application Menu* → IMPLEMENTED — HARDWARE VALIDATION REQUIRED: the
  row still described the stock `applicationsmenu` plugin; it was replaced
  by the mv-apple Apple menu + appmenu export (PR #7 stack, gated).
- *Dock*: "no pinned apps" was stale for the ISO path; now true for all
  paths (see above). Remaining gap: no fallback if plank is absent.
- *Desktop/Wallpaper/Session*: "no xfdesktop config (no desktop icons)"
  was stale — `xfce4-desktop.xml` (home/trash/removable, wallpaper) exists
  and is gated by `test-desktop-icons`. Real remaining gap: no
  xfce4-session customization.


---

## Session 2026-10-05 (late) — launch-smoke honesty + app fixes

**Launch smoke measures the app, not the wrapper.** `smoke-launch.sh`
now tracks the `python3|bash <script>` process itself and reaps each
launch as a process group under `setsid`. Why: watching xvfb-run made
Xvfb startup/teardown latency the verdict (locally ~3-4 s > SMOKE_STAY=3
→ false "stayed up", which hid `mv-colormeter`'s missing `__main__` call
for weeks), and `kill xvfb-run` leaked Xvfb/python children (117 on the
dev host) until `-a` display allocation failed and later apps "never
started". Verified: 0 Xvfb leftovers after a full gate run.

**File-taking Gtk.Application apps strip argv.** Convention: capture
`sys.argv[1:]` first, then `app.run([sys.argv[0]])`. Why: GApplication
without `HANDLES_OPEN` aborts positional args with "This application can
not open files" before `activate` runs (hit `mv-preview` with FILE and
`mv-finder-columns` with FOLDER). Future (P1): implement a real
`HANDLES_OPEN`/forwarder so a second invocation of an already-running
Preview passes new files to the primary instance instead of only
presenting the first window.

**Notification Center closes on focus-out only after a real focus.**
A synthetic focus-in/out pair fires the moment the panel maps under a
session without a window manager (proved under Xvfb/CI), which destroyed
the panel in milliseconds. Rule: `_ever_focused` AND focus-out arriving
>0.8 s after map. With a real WM the panel opens focused and the
grace window is invisible to the user; Escape/close button still work.

**GTK3 CSS: no `text-transform`.** The Gtk3 CssProvider rejects it
("not a valid property name") and the error killed `mv-calendar` at
window construction. Removed from `mv-calendar`/`mv-preview` (labels now
uppercased in code); `mv-dictionary` keeps it — that CSS renders HTML,
where the property is valid. All 20 `load_from_data` sites are wrapped
in try/except: cosmetic CSS must never take down an application.

**Suites must be distro-neutral.** `test-mv-fontbook` hard-required
Fedora font layouts (`/usr/share/fonts/gnu-free/...`), crashing the
Ubuntu CI runner with `TypeError` on a `None` fixture. Fixture fonts are
now discovered (gnu-free → freefont → dejavu → any `/usr/share/fonts`),
install/remove assertions use the discovered basename, and GUI probes
use a family present on the host. Same rule for cairo guards: a missing
optional binding skips the GUI section with an `ok -` line instead of
crashing the suite.

**CI runner profile.** The static-analysis job installs the Gtk3 typelib
set + pycairo/gi-cairo + xvfb, because `import gi` succeeding does NOT
mean Gtk is usable (runner has python3-gi without `gir1.2-gtk-3.0`): the
smoke probe now requires the typelib explicitly, and with the typelibs
installed the launch smoke and headless suites run for real instead of
skipping.


---

## Session 2026-10-05 (follow-up) — why NC/control died at random: host Wayland + focus model

**Root cause of the residual smoke flakiness (~40-50% of launches killing
mv-notification-center/mv-control "within 3s"):** the dev host exposes a
live Wayland compositor (`WAYLAND_DISPLAY=wayland-0`), and GTK3 prefers
Wayland whenever it is set — `xvfb-run` only sets `DISPLAY`. So the
smoke-tested windows were opening on the *host compositor*, not on the
Xvfb under test: real host focus churn arrived as focus-in/out pairs
(measured 0.0–1.3 s after map, pointer never moving) and the panels'
"close on focus-out" destroyed them at random. Two other local-only
"phantom input" tracebacks (mv-console hover preview, mv-photos photo
open) came from the same source — real host input landing on the test
windows.

**Fixes (two independent layers):**
1. `smoke-launch.sh` exports `GDK_BACKEND=x11`: smoke must test the
   target session's backend (MavLinOS = Xfce/X11), match CI (no Wayland
   there), and stop painting test windows on the real desktop.
2. mv-notification-center and mv-control close-on-focus-out only under a
   real window manager: `_NET_SUPPORTING_WM_CHECK` present on the root
   window. No WM (Xvfb smoke, CI, bare sessions) = ignore focus-out —
   Escape/close button remain. With xfwm4, click-away closes as designed.
   The earlier0.8 s grace + `_ever_focused` guards stay as belt-and-braces
   for the WM path.

**Two genuine user-facing bugs found on the way (fixed):**
- mv-console: `get_iter_at_location()` returns `(ok, TextIter)`, but the
  hover/click handlers used the raw tuple as an iterator →
  `AttributeError: '_ResultTuple' has no no attribute 'copy'` on the FIRST
  hover over the log view (broken for real users, not just smoke).
- mv-photos: `Gtk.Dialog.get_headerbar()` does not exist (correct API is
  `get_header_bar()`) → opening ANY photo crashed with AttributeError.

Stability after the fixes: NC+control 0/10 failures and console+photos
0/8 failures under the X11-forced harness (previously ~40-50% failed).

---

## 2026-10-05 — Owner PR triage verdict: all 8 Oct-4 PRs superseded (close, do not merge)

**Context:** Triage of owner PRs #3, #4, #5, #6, #61, #68, #77, #78
(oid OS-owner-prs-triage; read-only, no merges). All owner-authored →
mandatory directives. All 8 are CONFLICTING/DIRTY against
origin/main (183c9d9); bases are 458/458/458/458/74/56/24/24 commits
behind.

**Judgment calls (with reasons):**
- **REJECT-as-superseded for all 8.** Each PR's substance already
  exists on main via differently-worded commits: theme-validation gate
  (#3 → main ci.yml "Theme validation" + sassc/gir deps),
  self-contained firstboot (#4 → PROFILE_SELECTOR/PROFILE_STORE +
  check-profile-sync contract L88-106 + check-sync PAIRS),
  Finder column launcher (#5 → `Exec=mv-finder-columns %U` +
  test-finder-launcher gate), panel-config gate (#6 → test-panel-config
  in static analysis + synced panel-xml twins a57de5a), recursive
  XDG desktop IDs (#61 → mv_desktop_cache.py `rel.replace(os.sep,"-")`
  + #60 quarantine + #76 escapes), Launchpad migration persistence
  (#68 → load_folders `changed = changed or migrated` via PR #70),
  menu-bar/app-menu inventory rows (#77/#78 → main APPS.md rows are
  already IMPLEMENTED — HARDWARE VALIDATION REQUIRED with plugin
  chain + gating tests). Rebasing would re-land already-landed work
  and risk regressions; closing preserves the audit trail.
- **#61 → #68 dependency order recorded** (canonical IDs before
  migration persistence) in case the owner revives either; both
  already on main, so order is documentation-only.
- **#77 vs #78: mutually exclusive** (identical APPS.md hunk); both
  stale. Neither merges; if one must survive, #78 is the more detailed
  wording, but main's rows supersede both.
- **PR #5 zero-check-runs root cause** = invalid workflow YAML
  (job-level step inside the `if: false` hardware-tests job), not a
  runner outage — verified via check-runs API (total_count 0).
- **#19 confirmed closed-superseded** (closed 2026-10-04T21:27Z,
  unmerged); its `double_click_action=maximize` content is already on
  main in both xfwm4.xml twins; supersession recorded in 6090037.
- **#4's Profile Sync failure is a genuine contract violation**
  (one-sided twin edit of mavericks-profile-select.sh) — recorded as
  the reason that PR needs both-twins sync even before staleness.

**Verification:** full per-PR CI log forensics (runs 37227849232,
37228109529,37228398329,37240905549,37241315726,37241264425,
37242682389); three-way diff vs origin/main for every PR head;
check-runs API for #5; mergeable re-poll → CONFLICTING ×8. Results in
docs/EXTERNAL_AUDIT.md (dated section 2026-10-05). No product code
changed; no merges; no pushes of product code.

---

## 2026-10-05 — Mission Control dedicated overview layer: GO verdict + target architecture

**Context:** Owner issue #1 un-deferred a dedicated Mission Control window-overview layer IF rofi/wmctrl has a demonstrated fidelity ceiling. This decision documents the ceiling evidence, the GO verdict, and the target architecture.

**Fidelity-ceiling evidence (rofi/wmctrl):**
The current path (`mv-mission-control`) enumerates windows via `wmctrl -l -x` and renders them as a text list in rofi script mode. Ten concrete Mavericks behaviors are structurally impossible:
1. No live thumbnails (wmctrl returns text only; no X11 composite access)
2. No spatial grid layout (rofi is a vertical list, `columns: 1`)
3. No open/close animation (rofi has no window-position awareness)
4. No workspace thumbnails (text labels only, no workspace content capture)
5. No drag-and-drop between workspaces (rofi has no DnD API)
6. No live content updates (static list while open)
7. No minimized window thumbnails (no X11 composite = no capture)
8. No fullscreen app representation (no `_NET_WM_STATE_FULLSCREEN` check)
9. No multi-monitor layout (single rofi window, no Xinerama support)
10. No Mavericks visual styling (flat modern theme, not skeuomorphic)

**skippy-xd ceiling:** Addresses thumbnails via XComposite but fails on Mavericks styling, workspace model, animations, DnD, packaging (AUR-only, not in ISO), and desktop integration. Not a complete solution.

**Decision: GO — dedicated overview layer is required.**

**Target architecture:**
- One-shot Python/GTK3 overlay (`mv-mc-overview`)
- Window enumeration via Gdk EWMH (fallback: wmctrl)
- Thumbnail capture via XComposite (ctypes → libXcomposite)
- Rendering via Gtk.DrawingArea + Cairo (full Mavericks styling control)
- Input: click/arrows/Enter/Escape via Gtk event handlers
- Process model: one-shot (enumerate → capture → render → input → activate → exit)
- No daemon, no polling, no resident process

**Performance budget (§7):**
- Idle CPU: 0% (process exits after selection/Escape)
- Idle memory: 0 MB (no resident process)
- Open latency: < 500ms for 12 windows
- Thumbnail memory: ~80 MB peak (freed on exit)
- Wakeups: 0 at idle

**Migration boundary:**
- Phase A (current): Super+Tab → mv-mission-control --native (skippy-xd → rofi fallback)
- Phase B (migration): Super+Tab → mv-mc-overview (fallback: mv-mission-control --native → rofi)
- Phase C (complete): Super+Tab → mv-mc-overview (fallback: rofi only; skippy-xd retired)
- mv-mission-control (rofi) preserved as fallback throughout migration
- skippy-xd E-MC retired after migration complete

**Rollback:** Hotkey binding revert to `mv-mission-control --native`; remove mv-mc-overview from ISO; restore rofi-only path. Documented in plan §6.

**Dependencies:** No new AUR packages. Uses Arch core: python-gobject, libxcomposite, libxrender. Python stdlib: ctypes, gi.repository.

**Verification:** Plan document at `docs/MISSION_CONTROL_PLAN.md` with 10 ordered objectives, each independently testable. Test strategy: Xvfb :97 + gui-isolation.sh, 9 test files. 10 HW-validation items identified.
---

## 2026-10-05 — OS-mc-impl-3 push blocked by merge conflict with co-author's parallel Mission Control work (STOPPED FOR USER DIRECTION)

**Status: local commit `3ae6a7b` complete and tested; push to origin/main blocked by content conflict. Per CO-AUTHOR READINESS RULE ("Merge conflicts → stop and report") this is NOT auto-resolved.**

### Two histories (merge-base `06b866c` = slice 2 layout model)

- **Local (mine):** `3ae6a7b` "feat: mission-control thumbnails via XComposite/XDamage/XFixes (slice 3)" — 756 lines in `lib/mission_control.py` (`ThumbnailCapture`: redirect→NameWindowPixmap→XGetImage, vectorized BGRA→RGBA, nearest-neighbour scale, XDamage+XFixes live damage via `poll_damage`, placeholder fallback, MV_FORBIDDEN_DISPLAYS guard) + 615 lines tests (32 total, incl. live Xvfb :97 integration; found+fixed libX11 XEvent-192 heap-overflow bug). On top: foreign concurrent-session commit `5300ed3` (qwen web worker — NOT part of this objective, left untouched).
- **Remote (co-author AnsvipaRinh):** 20 commits `06b866c..8484978` implementing the SAME slice 3 independently (b574b81 separate module `lib/mission_control_thumbnail.py`: NameWindowPixmap WITHOUT redirect, RGB888 GdkPixbuf, no XDamage/live, no placeholder) PLUS later slices: EWMH activation (837c271, d92d400), native GTK overview `bin/mv-mc-overview` (65bf979..172d325), keyboard/workspace navigation (0d9613b, 8078a07, 8484978), PKGBUILD/Makefile wiring, docs.

### Exact conflict

`git merge origin/main` → CONFLICT (content) in:
1. `packages/mavericks-apps/src/mavericks-apps/lib/mission_control.py` — both sides appended new sections at the same anchor (after `get_workspaces()`): mine = `ThumbnailCapture` block; remote = EWMH activation helpers (`_parse_window_id`, `_send_root_client_message`, `_switch_workspace_xlib`, `_unminimize_window_xlib`, `_activate_window_xlib`, `switch_workspace`, `activate_window`).
2. `packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control.py` — both sides replaced the `if __name__ == "__main__"` runner/test list.

Semantic overlap requiring an integration decision (why this is not mechanical):
- duplicate window-id parsers: my `_normalize_win_id` vs remote `_parse_window_id`;
- two thumbnail backends with different contracts (raw RGBA bytes + damage events + placeholder vs GdkPixbuf RGB one-shot); remote's overview app consumes the remote one;
- test-runner list must union both suites.

### Needed from user (one of)

a) keep BOTH: my damage/live layer adapted to call/extend the co-author's module, conflicts resolved in favour of union (recommended — complements: theirs = one-shot pixbuf, mine = live updates + fallback + guards);
b) prefer co-author's implementation: rebase my slice onto theirs keeping only the XEvent-192 fix + tests + guards that still apply;
c) prefer mine: rebase remote activation/overview commits onto `ThumbnailCapture` API;
d) explicit instruction to resolve the merge union-style automatically.

Work stops here per the rule; no remote state was modified. All slice-3 tests pass locally (32/32, incl. live Xvfb :97, 0 host-display guard violations).

---

## 2026-10-05 — OS-mc-merge: Mission Control union merge executed per option (a)

**Status: RESOLVED.** User approved parallel work + active integration; `git merge origin/main` (tip 7ae2186; 06b866c..7ae2186 includes the co-author's EWMH activation, native GTK overview, workspace previews/DnD/count controls, Poppy visual parity, fonts, action icons) resolved UNION-style (option a above). Merge commit preserves both histories; no rebase, no history rewrite, no force push; foreign commits (incl. `5300ed3` qwen worker) untouched.

### Resolution layout (single module per repo conventions)

- `lib/mission_control.py` — enumeration (slice 1) + layout (slice 2) + EWMH activation/workspace-transfer (co-author's slices). My `ThumbnailCapture` block REMOVED from here.
- `lib/mission_control_thumbnail.py` — BOTH capture backends, complementary by design:
  - co-author's `capture_window()` one-shot → GdkPixbuf RGB (the GTK rendering path; consumed by `mv-mc-overview`);
  - my ctypes `ThumbnailCapture` (redirect + NameWindowPixmap + XGetImage raw RGBA, XDamage/XFixes live tracking, deterministic placeholder, MV_FORBIDDEN_DISPLAYS guard, XEvent-192 heap-overflow regression coverage) for the future live-update slice.
  - One `_XImage` struct kept (co-author's superset definition); my block's duplicate dropped.
- **Parser dedup:** canonical strict `mission_control._parse_window_id` (my bool/negative-rejecting semantics under the co-author's public name; all their activation tests pass unchanged); thumbnail module imports it. My `_normalize_win_id` removed everywhere.
- Tests mirror modules: thumbnail suites (theirs 5 + mine 14, incl. Xvfb :97 integration) unified in `tests/test_mission_control_thumbnail.py` (19 tests); `tests/test_mission_control.py` keeps enumeration/layout (18 tests); `tests/test_mission_control_activation.py` taken from origin (10 tests).

### Bugs found in co-author's committed code, fixed as part of the union (minimal, intent-preserving; none reverted)

1. `_scale_channel()` returned constant 255 for 8-bit channels — their own `test_image_to_rgb_32bit` was red at commit time on origin/main (verified against pristine origin). Fixed: bits==8 → identity.
2. `XGetImage` on a pixmap leaves red/green/blue masks ZERO (undefined for pixmaps per protocol; verified on Xvfb) — their mask-driven `_image_to_rgb()` produced uniformly BLACK thumbnails for every caller in every environment. Fixed: zero-mask fallback to standard ZPixmap layouts (565 for 16bpp, 888 for 24/32bpp).
3. `tests/test_mission_control_activation.py` shipped with literal `\\` double-backslash continuations → SyntaxError, suite could not run at all on origin/main (same paste-mangling disease as the earlier `mv-mc-overview` newlines, which the co-author fixed themselves in 8a273e3/754cf4e). Fixed to single `\\` continuations; 10/10 green.

### Other integration facts

- Pixbuf one-shot precondition: the window must be compositor-redirected (xfwm4 `use_compositing=true` in production configs; explicit Automatic redirect in the test). Documented in the test + MISSION_CONTROL_PLAN.md O3; validated pixel-exact on :97.
- `libxdamage` + `libxfixes` added to mavericks-apps `depends` (live-capture backend runtime libs; co-author had already declared `libxcomposite`).
- Gates: check-sync.sh ALL CHECKS PASSED; MC totals 18/18 + 10/10 + 19/19 (incl. live :97: ctypes fullscreen capture ~50-66ms, pixbuf path 32x24 pixel-exact); `mv-mc-overview` (origin's fixed version) smoke green on :97; host-display guard 0 violations.
- **Concurrent-session incident during resolution:** a live qwen-worker session ran `git reset` mid-merge (reflog 7619f21 `reset: moving to HEAD`), destroying the first in-flight (uncommitted) resolution. Rebuilt deterministically and committed promptly. Parallel work is user-approved; this record documents the event, no revert performed.
- Env gap fixed along the way: python-xlib installed in the build container (activation suite needs it).
- **Second wave during push:** origin advanced again (7ae2186 → 50a4c8b, 29 commits: MC grouping/Space selection refinement, workspace count/remove controls + helpers, Plank Trash docklet gate, icons). Follow-up merge was conflict-free; all new MC suites green (window-spaces/spaces-remove/workspaces-count). Reconciliation included: `mv-mc-window-spaces` rewritten onto the shared `mission_control` backend — its original `python3-ewmh` dependency does not exist in Arch repos (AUR-only) and duplicated slice-1 enumeration; output JSON contract preserved exactly. Push sequence: first push rejected non-FF by the same race; second push carries both merges. Third wave (d0d4dbc): overview had been shrunk by 191fd78 to a 130-line CLI stub (deleting the 507-line GTK UI with grouped stacks/DnD/Spaces strip); union resolution keeps BOTH: restored the 507-line GTK UI as default mode AND preserved the stub's CLI contract (--list/--debug/--activate, headless-safe via deferred GTK import); their helper tests (overview 3/3, thumbnail-helper, grid, window-spaces, workspace-count) + GTK 3s smoke all green. mv-mc-thumbnail (import/scrot CLI) and mv-mc-grid remain standalone helpers; the overview renders via in-process mission_control_thumbnail (no external screenshot deps).
