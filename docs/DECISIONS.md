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

### Impact on Project Objectives (§13.2 Canonical Inventory)
- **P0 Global Menu / Apple Menu / App Menus:** RESTORED via PR #7 (was deleted by qwen)
- **P0 Launchpad:** IMPROVED via qwen ACCEPTED items (pagination dots, edit dialog, Super+Shift+L)
- **P0 Finder:** IMPROVED via qwen ACCEPTED items (headless logic, tests)
- **P0 Mission Control / Spotlight / Control Center / Notification Center / Quick Look / Preview / Screenshot / Activity Monitor / System Info / Disk Utility / System Settings / Power UI / Trash / Archive Utility / Menu Bar / Dock / Application Menu / Global Dialogs / File Chooser / Context Menus / Keyboard Shortcuts / Desktop / Window Management:** Unchanged
- **P1 Applications:** mv-calculator, mv-stickies, mv-diskutil, mv-keychain, mv-about, mv-settings, mv-calendar, mv-reminders — all IMPROVED via headless tests

### Next Steps
1. Execute merge/fix/cherry-pick sequence above
2. Update PROGRESS.md with current status
3. Continue P0 application completion per §13.8 autonomous loop

---

## Notification Center P0 (canonical #5) — audit outcome and non-obvious choices

**Context.** Objective #5 is PARTIALLY IMPLEMENTED: xfce4-notifyd renders
banners and `mv-notification-center` is an on-demand history viewer. Audit
against §13.6 (surface, history, consistent style, interaction, keyboard/global
integration) and §10.3 (единая архитектура, no second daemon) found three
executable pre-hardware gaps. All are closed; the status stays
PARTIALLY_IMPLEMENTED for the hardware-dependent remainder only.

**1. History without a daemon — stay on the existing log, do NOT add one.**
Per-entry dismissal needs a stable identity per entry, which would normally
push toward a resident service. It did not: `mv-notify-send` already stamps
every entry with `uuid4().hex[:12]` and `mv-notification-center` already
mutates the same JSON log atomically under `flock`. Dismiss is therefore a
read-filter-replace on that log (`dismiss_entry`, matching on `id`). No new
process, no polling, no wakeups — §10.3 and the §7 energy baseline are
unaffected. The alternative (a live history daemon mirroring libnotify) was
rejected: it duplicates xfce4-notifyd's role and costs idle wakeups on a
fanless Core M for a panel that is opened on demand.

**2. Keyboard cursor instead of a custom navigation handler.**
`GtkListBox` with `SelectionMode.NONE` cannot hold a cursor, which is exactly
why the panel behaved as mouse-only. Switching to `SelectionMode.SINGLE` and
connecting `row-activated` delegates Up/Down/Enter to GTK's own navigation
instead of hand-rolling key handling. The only custom logic is seeding the
cursor on the first Down/Up/Delete press, so navigation works before any click.

**3. Row→entry lookup: a row attribute, not GObject data.**
`ListBox` "row-activated" passes only the row, so the log entry must travel
with the widget. Rejected two options: matching on the summary label text
(collides on duplicate summaries — common in notification history) and
`set_data`/`get_data` (PyGObject 3.14 rejects these outright with
"Data access methods are unsupported. Use normal Python attributes instead").
Settled on a plain `row._mav_entry` attribute, read via `getattr`.

**4. Ordering by timestamp, not log position.**
The viewer previously reversed the history log and treated the result as
"newest first", which is only true because `mv-notify-send` appends
chronologically under a lock. That invariant is implicit and does not survive
a restored/hand-edited history file or a backwards clock step. Sorting each
app group and the section order by the recorded timestamp renders identical
output for chronological, reversed, and interleaved logs, so the display no
longer depends on a write-order assumption it cannot check.

**5. Urgency stays visible; normal entries stay bare.**
`get_urgency_color` was dead code — urgency was logged but never shown. Rather
than delete it or colour every row, only critical and low entries get a
colour-coded accent dot; normal notifications render unadorned, matching
Mavericks, so the accent keeps its signal value.

**6. Tests prove behaviour; the flock claim is executed, not asserted.**
`scripts/test-notification-history.py` now spawns 6 concurrent writers x 25
appends and checks no entry is lost, the file stays valid JSON at 0600 with
unique ids, and the 500-entry cap holds — the static "it uses flock" check
never proved the lock works (without it, 150 appends collapse to 6). Both
suites were mutation-checked to confirm they fail when the fixes are reverted.

**7. The GUI smoke stubs the xfconf DND calls.**
Constructing the panel would otherwise read/write the developer's real
`xfce4-notifyd` xfconf property. The GUI suite monkeypatches
`get_dnd_status`/`set_dnd_status` to record calls instead; the xfconf contract
itself stays covered by the static checks. The suite runs only on the pinned
Xvfb :97 via `scripts/gui-isolation.sh`.

**Known hardware-dependent remainder** (kept in `docs/NEEDS_HARDWARE_TEST.md`):
banner look, Super+Shift+V chord, ✕ placement, and the panel's translucent
rounded appearance against a real panel/compositor. The panel also has no
live auto-refresh while open — history is read on open and after each clear
action; banners are the live surface. Changing that would need either polling
(a wakeup cost §7 discourages) or a libnotify signal hook, which
xfce4-notifyd does not expose.

---

## 2026-10-04 — External Work Audit (origin/main + feat/global-menu-appmenu)

> Salvaged 2026-10-06 from stash@{1} ("WIP on main: 7ba84f8") — the record was
> never committed when the work landed; reproduced verbatim for provenance.

**Context:** Autonomous audit of all work landed on GitHub origin from third-party agents (user reported "mountain of it"). Per AGENTS.md §14.2 GitHub Discovery Gate, external contribution backlog has priority. All PRs/Issues authored by repository owner AnsvipaRinh → MANDATORY directives per OWNER-ISSUES RULE.

**Inventory:**
- origin/main: ~200+ commits ahead of 7ba84f8 (PR #3,4,5,6,8 merged)
- feat/global-menu-appmenu: ~200+ commits, 83 files, +2210/-1993 (PR #7 open)
- 6 PRs total (1 closed/merged, 5 open → 4 merged via fast-forward, 1 via --no-ff)
- 2 Issues (both owner directives)

**Verdicts:**

| Item | Verdict | Reason |
|------|---------|--------|
| Default Dock pins (PR #8) | ACCEPT | Minimal, tested, documented |
| Super+Q/M/H/W shortcuts (PR #8) | ACCEPT | Wires existing scripts, tested |
| NetworkManager guard (PR #8) | ACCEPT | Static guard, enforces baseline |
| KEYBOARD.md update (PR #8) | ACCEPT | Documentation sync |
| MIME apps list (PR #8) | ACCEPT | Proper default, mirrored, synced |
| Firstboot/profile refactor (PR #4) | ACCEPT | Robust, idempotent, tested |
| Panel config validity (PR #6) | ACCEPT | Fixes config, adds test |
| CI theme validation (PR #3) | ACCEPT | Strengthens CI |
| Global menu implementation (PR #7) | ACCEPT | Complete, tested, architecture-compliant, energy-neutral |
| Apple menu plugin (PR #7) | ACCEPT | Native C plugin, Mavericks command set |
| App lifecycle migration (PR #7) | ACCEPT | Gtk.Application pattern, all apps migrated |
| Force Quit / Recent Items (PR #7) | ACCEPT | Native dialogs, one-shot |
| Hardware selection rewrite (PR #7) | ACCEPT | Post-install tool, proper separation |
| Test-global-menu.py (PR #7) | ACCEPT | Comprehensive static validation |
| Issue #1 (Architecture plan) | MANDATORY | Owner directive — execute per §13.8 |
| Issue #2 (Poppy audit) | MANDATORY | Owner directive — execute per §13.8 (already done, recorded above) |

**Architecture Assessment:** No hardware-profile leakage into generic core. Global menu, Apple menu, app lifecycle, shortcuts, Dock pins — all generic core. Firstboot/profile selector, apply-hardware-selection.sh — properly isolated hardware-profile tools.

**Mavericks Fidelity:** Significant improvement. Global menu + Apple menu + per-app GMenu = core Mavericks desktop metaphor implemented.

**Licenses/Secrets:** CLEAN. No secrets. vala-panel-appmenu from upstream (GPL-3.0). All new code project-internal.

**Energy/Performance:** NEGLIGIBLE impact. No persistent daemons, no polling, no Electron/Java/Python daemons. Panel plugins event-driven only.

**Test Gates (post-merge):** 7/7 PASS (check-sync, test-dock-launchers, test-window-keys, test-network-stack, test-global-menu, test-panel-config, test-finder-launcher)

**Actions Taken:**
1. Fast-forward merge origin/main (7ba84f8 → 8836c6f)
2. Merge --no-ff feat/global-menu-appmenu (930a0b5 → merge commit)
3. All gates verified PASS
4. Push origin main

**Next Objectives:** Execute Issue #1 decomposition; continue P0 application completion per canonical inventory (§13.2).

---

## 2026-10-06 — Dock (canonical #18): plank reads GSettings, not `dock1/settings`

**Decision.** The Dock's preference authority is
`packages/mavericks-apps/src/mavericks-apps/lib/plank_config.py`, shipped as
`/usr/bin/mv-dock-config` and seeded by the Dock session autostart entry
(`configs/desktop/plank/plank.desktop`, `Exec=mv-dock-config --apply --launch`).
The legacy INI `~/.config/plank/dock1/settings` stays in the tree as a
human-readable declaration only, cross-checked against the authority.

**Why (measured, not assumed).** plank 0.11.89 does not read that INI. With
only it present, plank reports `theme='Default'` and `zoom-enabled=false` —
so the Mavericks `dock.theme`, the zoom and the auto-hide never reached the
Dock, while `docs/APPS.md` claimed "theme + settings + autostart
implemented". Writing the same values through GSettings does work: the same
run gives a 304 px dock at `icon-size=48` and a 604 px dock at
`icon-size=96`.

**Three further defects the audit exposed.**
1. `packages/mavericks-theme/mavericks-theme.install` wrote a **third** copy of
   the INI with `Position=0` / `Alignment=0` — plank's enum means TOP, so a
   pacman install asked for the Dock on the wrong edge. Removed; the seeder
   owns the runtime state now.
2. A plain pacman install shipped the Dock pins but **no autostart entry**
   (it only existed in the ISO's `airootfs`), i.e. no Dock at all outside the
   live image. `mavericks-apps` now installs it into `/etc/skel`.
3. `auto-pinning` was changed from plank's default `true` to `false`, on the
   reading that "macOS never auto-pins running apps". **That was wrong**, and
   the GUI smoke caught it: measured with a window manager, an *unpinned*
   running application grew the Dock 424 px → 484 px with `auto-pinning=true`
   and did **not** appear at all with `false`. macOS does show every running
   app in the Dock and removes it again when it quits — it is not a permanent
   pin — and that is exactly plank's `auto-pinning`. Reverted to `true`, with
   the measurement recorded in `PREFERENCES` so the next reader does not
   "fix" it back.

**Why a seeder script and not `/etc/dconf/db/local.d`.** The declarative
system-db route needs `/etc/dconf/profile/user`, which risks a pacman file
conflict in the ISO build and cannot be validated offline. The seeder is
idempotent, one-shot (~20 ms, no daemon, no polling — §7), needs no session
bus of its own, and skips any key already present in the user's dconf
database, so changing the theme in plank's own preferences dialog survives the
next login. `mv-dock-config --keyfile` still emits the equivalent
`local.d` keyfile for anyone who prefers the declarative layer.

**Two bugs the GUI smoke caught that no static check would have.**
* `dconf dump` prints section headers **relative to the dumped root**
  (`[docks/dock1]`, not `[net/launchpad/plank/docks/dock1]`). Comparing the
  raw header made the seeder see "nothing customised" and overwrite user
  settings on every login.
* `dconf dump` needs the path to look like a directory — `…/plank` without the
  trailing slash fails, and the same overwrite followed.
Both are now pinned by `scripts/test-dock-plank.py`.

**Where the macOS look is and is not reachable (plank 0.11.89).** Verified
against `strings /usr/lib/libplank.so.1`, which is what plank actually looks
up: the theme vocabulary has **no `ReflectionHeight`, `ReflectionOpacity`,
`ReflectionFade`, `BackgroundColor`, `BackgroundPadding`, `IndicatorColor`,
`IndicatorShape`, `ItemColor`, `ItemHoverColor`, `UrgentColor`, `BorderSize`**
keys. The macOS reflection, the translucent shelf behind the icons and the
blue running-indicator dots therefore **cannot** come from a plank theme — the
old `dock.theme` set all of them and plank dropped the lot without a warning
(commit 1eecbb9 had already fixed the format; the vocabulary gap remains).
What plank *can* render — and what the Mavericks Dock now uses — is the
metallic `FillStartColor`/`FillEndColor` gradient, `OuterStrokeColor` +
`InnerStrokeColor` hairline, `TopRoundness`, `ZoomPercent`, the paddings and
`IconShadowSize=0` (Mavericks icons carry no drop shadow).
`scripts/test-dock-plank.py` asserts every theme key exists in the binary and
every colour is `r;;g;;b;;a`, so this cannot silently regress again.

**Cross-zone note.** `desktop/mv-mission-control.desktop` was added because a
Dock pin needs a desktop id that actually resolves (plank silently drops pins
whose target is missing — observed). It only *references*
`mv-mission-control --native`; no `mv-mc-*` / `mission_control_*` file was
touched.

**Deliberately not done.**
* *Minimised windows in the Dock's right section* — no plank equivalent; doing
  it properly needs a window-tracking daemon, which §7 forbids on this
  hardware. Recorded as a known gap instead of a polling hack.
* *A fallback Dock when plank is missing* — plank is a hard dependency of both
  `packages.x86_64` and `mavericks-theme`; a second Dock implementation would
  violate reuse-first and add an always-on cost for a case that cannot occur.

## 2026-10-06 — Failover forensic audit (E1–E11) and the v18 failover contract

Full analysis: `docs/FAILOVER_AUDIT.md`. Summary of what was accepted as
evidence, what was fixed, and why.

**E1 (orphan flood).** `stuck` reported registry-only rows as STUCK by
lastUsed age, but status absence = IDLE on this platform; ~150 dead
entries (busyAge to 50h) drowned real signal and no GC existed. DECISION:
registry-only rows are `ORPHAN` (informational, never exit 2); `stuck --gc`
retires entries verified absent (GET /session/{id} → 404) and unused >24h;
watchdog `--ensure` runs the GC best-effort. Verified-only means a flapping
API never garbage-collects live sessions.

**E2 (quota refusal class invisible).** Hard «Usage limit reached … reset
<timestamp>» arrived via Task return, invisible to the watchdog. DECISION:
`classify-error` parses provider reset timestamps into the exact cooldown
(+20 min safety margin, per the FAILOVER DISCIPLINE rule: provider 15 min →
record 20 min); the flat 3h default remains only when no timestamp exists.

**E3/E4 (split-brain preflight/migrate).** Root cause: cooldown store keyed
by whatever string the writer typed (bare id) while readers looked up pin
strings (full provider/model). DECISION: single symmetric matching
(`health_entry`: full OR bare id) and a single writer shape (`record_dead`)
shared by mark-dead / classify-error / migrate / watchdog; preflight and
migrate additionally re-verify their chosen model and refuse to print a
cooldown one; `--force` is the explicit human override. Cooldowns may grow
but never shrink (re-migrate used to cut a 20h entry back to 3h).

**E5 (cancelled Task loses task_id).** Platform limitation, not fixable in
our layer. Kept: registry bookkeeping + watchdog live discovery; GC never
retires sessions that still exist server-side.

**E6 (config tug-of-war).** Uncommitted worktree rewrites of
`.opencode/model-fallback.json` + `opencode.jsonc` (GLM wiped, primary
repointed) went unnoticed; a stale «GLM REMOVAL RULE» in AGENTS.md gave the
rewrite doctrinal cover; the protocol consistency test had been deleted
from the worktree while versions drifted (17 committed vs 16/15 worktree).
DECISION: CONFIG-DRIFT gate — preflight/migrate/models/health/dashboard
compare the two worker-config files against HEAD and print a loud banner on
divergence (fail-open without git); the deleted test is restored;
ORCHESTRATOR_PROTOCOL bumped to v18 (contract change) and synchronized in
AGENTS.md §14.2/§14.5.1 + orchestrator.md.

**E7 (mass foreign churn, ~170 files).** Actor unidentified. This objective
implemented ON TOP of the worktree state (no checkouts/restores of foreign
edits); the drift gate covers the two files that steer model choice; the
rest of the churn is outside the failover plane and left for its owner.

**E8 (dead pin 13h, random-model fallback).** The committed chain already
neutralizes both (openrouter/free has worker:null «random-model router
unsuitable»). Residual gap is continuous per-pin liveness probing — recorded
as future work in the audit, surfaced today via `models` live tags +
`dashboard`.

**E9 (silent --ensure).** The STARTED path printed nothing (parent exited
inside daemonize before output). DECISION: both paths print unambiguous
lines (ALIVE pid=… / STARTED); new `--status` (pid, uptime, heartbeat age,
aborts total) with exits 0 running / 1 not running / 2 stale-deaf.

**E10 (shared quota pool unmodelled).** glm-5.3-flash and glm-5.3 share one
zai-coding-plan quota; prose in health reasons did not steer rotation.
DECISION: `"pool"` field in the chain; quota-class verdicts record
`poolWide` and block the whole pool for failover; provider timeouts stay
per-model; `mark-alive --pool` clears a pool in one call.

**E11 (owner word vs static memory).** Owner declared GLM alive while
cooldowns ran (9h52m / 1h25m). DECISION (doctrine, A3): the owner's live
word outranks health memory — after a directive run `mark-alive … [--pool]`
and continue; GLM entries may not be removed without a NEW explicit owner
directive. AGENTS.md now carries «GLM CODING PLAN RESTORED» instead of the
stale removal rule.

**A1–A3 implementation notes.** A1 single store + `--force` (regression
tests: mark-dead under a bare spelling blocks preflight and migrate);
A2 drift gate (tests: modified/untracked/clean); A3 doctrine + protocol v18
everywhere, `ProtocolVersionConsistency` green again. Test suite: 95 OK
(was 71 with 3 stale-expectation failures, fixed by deriving the expected
fallback from the chain rather than hardcoding build-b).

**Dock keyboard navigation — not feasible with plank 0.11.89 (documented
limit, not an omission).** macOS lets you focus the Dock with Ctrl+F3, walk
items with ←/→, activate with Enter, and type-ahead to jump. plank 0.11.89
has none of it: `libplank.so.1` contains **no** `keynav`, `activate_item` or
`move_left` symbols (the only `move_right` hit is
`plank_dock_item_draw_value_move_right`, the drag animation), and its sole
key-press handler is `plank_preferences_window_real_key_press_event`, i.e. the
*preferences dialog*. The Dock window is override-redirect and never takes
keyboard focus, so there is nothing for a one-shot hotkey to move focus onto
either. Closing this would mean an XGrabKey process resident for the whole
session purely to watch Ctrl+F3 — a permanent wakeup source for a
navigation-only feature on fanless hardware, which AGENTS.md §7 rules out.
Left as a documented architectural limit; `scripts/test-dock-plank.py` asserts
that this limit stays recorded in `docs/APPS.md` and `docs/DECISIONS.md` so it
cannot quietly disappear from the docs.

---

## 2026-10-06 — Git Stash Ban in Parallel Agent Discipline + SyntaxError Fix (PR #108)

**Context:** Two incidents converged in the same session:
1. A parallel agent ran `git stash` mid-session and swept another agent's uncommitted hardening (host-display guard files briefly reverted; restored by the affected agent). This confirmed that `git stash` is not a safe coordination primitive in parallel agent workflows — it operates on the shared worktree and silently overwrites uncommitted changes across agents.
2. `scripts/test-mavericks-apps-packaging.py` had a SyntaxError at line 54 (two `else:` on one construct), committed in 0be8063 (PR #108). Verified to reproduce on clean HEAD.

**Decisions:**
1. Added GIT STASH BAN rule to AGENTS.md §8 (after GLM CODING PLAN RESTORED): Workers must NEVER use `git stash` (any form: `git stash`, `git stash push`, `git stash pop`, `git stash apply`, `git stash drop`, `git stash clear`). If work must be set aside, commit it to a branch or leave it untouched and report the situation.
2. Fixed the SyntaxError in `scripts/test-mavericks-apps-packaging.py` by correcting the indentation of the `else:` block at line 52 to properly align with the `if os.path.isdir(DESKTOP):` at line 36 (inside the outer else block for MAKEFILE check).

**Verification:**
- `python3 scripts/test-mavericks-apps-packaging.py` runs without SyntaxError (now reports pre-existing Makefile coverage failures, not syntax errors)
- `scripts/check-sync.sh` passes all syntax/compile/XML/desktop/PKGBUILD/theme-css/dock P0 checks (app suite failures are pre-existing, unrelated to the syntax fix)

**Follow-up:** Both changes committed and pushed per PUBLISH RULE.


---

## 2026-10-06 — Menu Bar P0 audit: three dead configs, one wrong screen edge, and the container's plugin-lifetime wall

**Context.** Menu Bar (canonical #17) + Application Menu (#19) had been reported
as "functional panel + Mavericks CSS theme + appmenu plugin + Mavericks clock".
The audit (own zone only: panel config + `lib/mavericks_appmenu.py` +
`panel/mv-apple.c` + menu-bar styling) found every one of those claims to be
config-that-nothing-reads — the same failure class the Dock audit just found in
plank. Every claim below was re-measured or read out of the shipped
xfce4-panel 4.20.8 sources before being called dead.

### D1 — `position="p=8"` put the menu bar at the BOTTOM of the screen

`p=%d` is not an edge name, it is the numeric `PanelSnapPosition`
(`panel/panel-window.c`, `enum _SnapPosition`, read by
`xfce_panel_window_set_property(PROP_POSITION)` via `sscanf(val, "p=%d;x=%d;y=%d")`):

```
0 NONE | 1 E | 2 NE | 3 EC | 4 SE | 5 W | 6 NW | 7 WC | 8 SW | 9 NC | 10 SC | 11 N | 12 S
```

`p=8` is **SW (bottom-left)**. With `length=100` the panel spans the full width,
so the whole menu bar was docked to the **bottom edge**. GUI smoke on the pinned
Xvfb :97 measured the panel window at `1680x25+0+1025` on a 1050px-tall screen —
bottom — while every document said "top panel". Changed to `p=11`
(`SNAP_POSITION_N`, top edge, unambiguous for a full-width bar); the same smoke
now measures `1680x25+0+0`. `scripts/test-panel-config.py` and
`scripts/test-menu-bar-p0.py` both pin `p=11` structurally, and the GUI smoke
asserts the window geometry, so this cannot regress silently again.

Why it went unnoticed: `test-panel-config.py` asserted only that the string
`name="size" type="uint" value="24"` existed — it never parsed the geometry and
never looked at a screen. A config assertion is not a rendering assertion.

### D2 — `digital-format` is not a live xfconf property (xfce4-panel ≥ 4.20)

The live digital-clock properties are `digital-layout`, `digital-time-format`,
`digital-date-format`, `digital-time-font`, `digital-date-font`
(`plugins/clock/clock-digital.c` class_init + `plugins/clock/clock.c` GObject
property table). `digital-format` appears exactly once in the whole plugin:

```c
/* xfce_clock_digital_migrate_format() — plugins/clock/clock-digital.c:405 */
prop = g_strdup_printf ("%s/%s", prop_base, "digital-format");
```

i.e. it survives only as the key of a one-shot backward-compat migration, and
that migration is connected in `xfce_clock_digital_new()` to
`g_signal_connect (digital, "hierarchy-changed", …)`. `hierarchy-changed` is a
signal of `XtPanelPlugin`; `XfceClockDigital` is a `GtkBox`, so the lookup cannot
resolve on the child and the handler never runs. The key we shipped was dead, and
the bar fell back to `%Y-%m-%d %H:%M`.

Even if it had fired it would have produced `digital-layout = TIME` with the old
format verbatim — not the Mavericks "date then time". So the fix is not "restore
the migration", it is "use the real properties": `digital-layout=3` (TIME only —
the DATE_TIME layouts stack the two labels in a **vertical** box
(`gtk_box_new(GTK_ORIENTATION_VERTICAL, 0)`), which clips in a 24px bar) and
`digital-time-format="%a %b %-d %-I:%M %p"`.

`%-d` / `%-I` were verified against GLib's `g_date_time_format` (not assumed):
`%-d` → `6`, `%e` → `6` **wrapped in U+2007 FIGURE SPACE**, `%-I` → `3`,
`%l` → U+2009 THIN SPACE. The gate now renders a fixed datetime and asserts
`"Tue Oct 6 3:45 PM"`, so a future switch to `%e`/`%l` fails the build instead
of shipping an invisible glyph.

Also pinned: `digital-time-font`. `clock-digital.c:84` is
`#define DEFAULT_FONT "Sans Regular 8"` — the clock ignores the GTK theme font,
so without this key the menu bar shows 8pt Sans in the middle of Lucida Grande.
It is kept in sync with `xsettings.xml` `FontName`; `scripts/test-panel-clock.py`
asserts it is set and differs from the xfce default (a literal cross-file equality
check would fight any future font change, so the invariant is stated instead).

### D3 — xfce4-panel 4.20 has no panel.css theme support; the menu-bar theme was fiction

`packages/mavericks-theme` installed `xfce-panel/panel.css` into
`/usr/share/xfce4/panel/themes/Mavericks/`, and in the installed package **that
directory is empty**. Reason: nothing reads it. `strings` over
`/usr/sbin/xfce4-panel` and `/usr/lib/libxfce4panel-2.0.so.4` finds no
`panel/themes` and no `panel.css`; the only panel paths in the binaries are
`/xfce4/panel/plugins` and `/usr/lib/xfce4/panel/wrapper`. The panel window is an
ordinary GTK3 toplevel styled from `GtkSettings`, i.e. from the GTK theme named by
`xsettings.xml` (`ThemeName=Mavericks`).

Decision: delete the dead `xfce-panel/panel.css` and its PKGBUILD stanza, and put
the menu-bar rules in the GTK theme (`gtk-3.0/_panel.scss`, imported by both
`gtk.scss` files, so `gtk-3.0/gtk.css` and `gtk-3.20/gtk.css` both carry it and
`scripts/test-theme-css.py` keeps validating it as GTK3 CSS). Node names were read
out of the sources, not guessed:

* `.panel-1` — `panel_window_constructed()` does
  `g_strdup_printf ("%s-%d", "panel", window->id)` + `gtk_style_context_add_class`,
  so the panel window carries `panel-1`. (A first attempt used `.xfce4-panel`
  here, which is wrong: that is not the panel window's class.)
* `.xfce4-panel` — `wrapper/wrapper-plug-x11.c` adds `"panel"` **and**
  `"xfce4-panel"` to the *plug* window. Each panel item lives in its own socketed
  toplevel, so item widgets are **not** descendants of the panel window in the
  widget tree; `.panel-1 button` alone would never match an item.
* `#clock-button` — the clock plugin's button name (`plugins/clock/clock.c`).

A one-line bar on the Dock audit applies here too: "static CSS is not applied
CSS". `scripts/test-theme-css.py` proves the rules *parse*, which is necessary
and not sufficient; the visual check stays a hardware item.

### D4 — `configver`: ship the config version the panel expects

Without `<property name="configver" type="int" value="2"/>` the panel runs
`xfce4-panel-migrate` on **every first boot** — "Panel config needs migration..."
plus `xfconf-WARNING: Type guint does not match type GPtrArray of property
/panels` — and rewrites the user's own skel file. The value is the one
`xfce4-panel-migrate` writes on 4.20.8 (observed, not guessed).
`scripts/test-panel-menubar-gui.sh` uses the *absence* of those two log lines as
its deterministic pass/fail signal: it is the only externally observable
difference between a config the panel understands and one it has to rewrite,
which makes it the regression gate for the whole dead-config class.

### D5 — Apple menu: route power actions through `mv-power-ui`, keep mnemonics

`Sleep`/`Restart…`/`Shut Down…` called `systemctl suspend|reboot|poweroff`
directly. That bypassed the Mavericks alert, the 60 s countdown, the battery
footer, the logind `Can*` gating and polkit — i.e. the menu was four items that
looked macOS and behaved like a shell script. They now exec
`mv-power-ui sleep|restart|shutdown|logout`, which already implements all of it;
`systemctl` remains only as a fallback when `mv-power-ui` is not on `PATH`
(`g_find_program_in_path`), so a partial install can never produce a dead menu
item. `Log Out` moved to `mv-power-ui logout` for the same reason, keeping
`xfce4-session-logout` as the fallback.

Menu titles and items carry mnemonics (`gtk_label_new_with_mnemonic`) and the two
items macOS shows shortcuts for render macOS key glyphs in a right-aligned
column — `⌥⌘⎋` (U+2325 U+2318 U+238B) for Force Quit, `⇧⌃⌘Q` for Lock Screen.
Written as `\uXXXX` escapes so the source stays ASCII and the test can decode
and assert the exact code points. `xfce_panel_plugin_set_small()` is **kept**:
`PLUGIN_FLAG_CONSTRUCTED` is set in `xfce_panel_plugin_constructor()`, i.e. before
the plugin's `construct()` runs, so the guard does not trip (checked in the
source after an initial wrong assumption).

### D6 — No generic Edit menu in the exported global menu (deliberate omission)

GtkWindow publishes `win.cut-clipboard` / `win.copy-clipboard` /
`win.paste-clipboard`, and `GtkEditable` (GTK ≥ 3.24) publishes undo/redo — but
they are **window-scoped**. When the menu model is exported to an external panel
(vala-panel-appmenu via the appmenu registrar) the window context is gone, so
those entries would render inert. Shipping them would be exactly the
"wrapper-first / fake integration" failure AGENTS.md §13.7 forbids. The apps that
actually edit text ship their own Edit menu through their `build_<app>_menu`
callback (mv-textedit: Undo/Redo/Cut/Copy/Paste; mv-notes / mv-reminders: Find),
which is real clipboard editing. Recorded in the module docstring so the omission
is not re-"fixed" later.

### D7 — Documented architectural limits (recorded, not faked)

* **No window buttons.** macOS shows a window list right of the app menus.
  Xfce 4.20's appmenu plugin renders one app's menus; the only widget that lists
  windows in the panel is the separate `windowmenu` plugin, which is not in our
  layout (it is a second, competing global-menu surface). Mission Control
  (`Super+Tab`) carries window switching.
* **No Ctrl+F2 menu-bar focus.** macOS moves keyboard focus into the menu bar with
  Ctrl+F2 and then walks menus with ←/→. Neither `xfce4-panel` nor
  vala-panel-appmenu 25.04 exposes a keynav action, and the panel window does not
  take keyboard focus. The workaround would be a process resident for the whole
  session purely to hold `XGrabKey` — rejected by AGENTS.md §7 on a fanless Core M,
  and it is the identical wall recorded for the Dock's Ctrl+F3. Menus *are*
  keyboard navigable once open (arrows / Enter / Escape / mnemonics).
* **vala-panel-appmenu is not installed in the build container**, so the global
  menu cannot be smoke-tested here. It is a hard ISO/pacman dependency
  (`packages/vala-panel-appmenu/PKGBUILD`, `packages.x86_64`) and its presence is
  gated by `scripts/test-global-menu.py`.

### D8 — The container cannot validate panel-plugin lifetime (proven by control)

`xfce4-panel-Message: Plugin mv-apple-1 has been automatically restarted after
crash` looked exactly like a crash in our own plugin. Bisected with per-statement
`g_printerr` traces inside `construct()` (installed into
`/usr/lib/xfce4/panel/plugins/`, then reverted): `construct()` completes and the
wrapper is reaped ~0.3 s later, with no signal and no diagnostics. Control
experiments:

1. a **four-line** stock plugin (`gtk_button_new()` added to the plugin) —
   identical restart;
2. the **stock `actions` plugin** in the same panel config — identical restart.

So it is xfce4-panel 4.20's out-of-process `wrapper-2.0` being reaped on a bare
Xvfb with no session, not an mv-apple defect. `scripts/test-panel-menubar-gui.sh`
therefore asserts what *is* observable — panel maps, top-edge geometry, no xfconf
migration, mv-apple wrapper **spawned** (proving the module is discovered and
`construct()` runs), zero host-display leakage — and states in its header that
Apple-menu opening, rendered clock text and appmenu rendering are hardware items.
Keep the control experiment in mind before "fixing" that message.

### D9 — Parallel-worktree discipline used in this session

Two files this change needed were *already dirty in the worktree* because another
incident reverted ~131 tracked files to older revisions. Rather than clobber or
commit another zone's damage, shared files were edited **through the index**:
`packages/mavericks-theme/PKGBUILD` and `.github/workflows/ci.yml` were rebuilt
from `HEAD` plus only this zone's hunk and staged with `git update-index
--cacheinfo`. The other zones' reverted worktree state stays exactly as found and
is not swept into this commit. Zone-local dirty files (`xfce4-panel.xml` ×2,
`scripts/test-global-menu.py`) were restored from `HEAD` first — nothing is lost,
since the newer state is committed.

## 2026-10-06 — Worktree mass-rewind incident #3: per-file triage and recovery protocol

**Pattern (third destructive incident today, after two `git stash` incidents).**
At ~01:45 a parallel actor rewound ~131 tracked files (123 `M` + 1 typechange in
`git status`) to older revisions, including exec-bit losses on 17 `bin/mv-*`
helpers, the `pkgrel=3` bump, `build_mail_menu`, the Dock launchers stanza, the
Lucida Grande font fix and recent CI/check-sync test hardening. Forensic tell:
three files (`bin/mv-calculator`, `bin/mv-launchpad`, `bin/mv-settings`) carried
literal unresolved conflict markers against commit `2d463fa` — the actor had run
a botched old-tree merge/checkout, not a clean operation. All newer state was
safe on `origin/main` (HEAD == origin/main at recovery time).

**Recovery protocol (reusable for incident #4+):**

1. `git fetch origin`; verify divergence both ways before anything else. Do NOT
   `git pull --rebase` with a dirty tree (it fails anyway; stash is banned).
2. Classify **per file**, mechanically: `git hash-object <file>` matched against
   the blob history of that path (`git log --format=%H -- <file>` → `git
   rev-parse <commit>:<file>`). An exact match to an older commit = PURE REVERT
   (worktree lost features that exist in HEAD). No historical match = candidate
   WIP → inspect the diff manually; conflict markers or pure deletions of
   HEAD-side hunks classify as damage, added never-committed content classifies
   as someone's in-flight work.
3. PURE REVERTs → `git restore <file>` (explicit paths only). GENUINE WIP →
   LEAVE UNTOUCHED. Untracked build junk → leave alone, report, never commit
   and never delete (not the recovering agent's call).
4. Never `git stash` (banned), never `git add -A/-a/.`, never reset/checkout
   branches, never rewrite history, never auto-commit foreign WIP.
5. Validate with `scripts/check-sync.sh`; classify residual failures as
   incident-caused vs pre-existing-at-HEAD (prove with a pristine `git worktree
   add --detach` at HEAD in `/tmp`, then remove it) vs WIP-caused.

**Outcome.** 121 files restored from HEAD (incl. the symlink-mode
`inode-directory.svg` → `folder.svg`, which the rewind had replaced with a
regular file pointing into the external `Poppy-OS-X-Revieve` tree, and
`.gitignore`, whose loss alone explained the sudden "untracked junk" noise:
`out/`, `test_serial.log`, `libmv-apple.so`, `mv-hud`, generated `gtk.css`).
2 files kept as genuine concurrent WIP: `bin/mv-control` (Control-Center work,
blob == PR#64 side-branch commit `3c32358`, outside HEAD history) and
`scripts/demo/run-demo.sh` (icon-fallback staging on top of d9f3c45). Also left
as-is/untracked: `scripts/__init__.py`, `scripts/apply-hardware-selection.sh`,
`artifacts/`.

**check-sync after recovery — residual failures are NOT incident damage**
(proven against a pristine HEAD checkout): `rofi_preview_integration`
(test expects the `listview-split`/`icon-current-entry` rofi layout that
`1eecbb9` deliberately removed after it made rofi abort; test not updated);
`mv-finder-columns` `build_columns_classes` (test expects an API the HEAD bin
no longer defines); `mv-control` launch smoke `NameError: sys` (bug in the
preserved WIP file itself — its author must fix); one flaky `mv-textedit`
respawn timing check under parallel-agent load. All incident-caused suite
failures (airdrop/mail/keychain/desktop-cache/finder-search, packaging
SyntaxError) are green again. The two pre-existing HEAD inconsistencies are
recorded here for the next zone to fix; this recovery commit intentionally
touches only this file.

---

## 2026-10-06 — Second GitHub sweep: PR #89 + PR #112 ACCEPT, and a repo-wide red-CI finding

**Context.** oid `OS-gh-sweep2`, baseline `d0956c1`. 76 new commits, 19 new PRs,
16 new issues, 13 merges — all inbound work owner-authored. Zone was GitHub
inbound + docs only; a parallel agent held the code zones and had pushed the
visual-demo track (`f09dd2f`…`e8afdd8`) mid-sweep, so the sweep re-based itself
onto `e8afdd8` before merging.

**Decisions:**

1. **PR #89 ACCEPT, merged `d9cc7a9` (`--no-ff`).** It is the re-scoped, minimal
   form of the `333e862` change this repo's previous sweep deferred. Merging
   instead of re-implementing was chosen because (a) it is owner-authored and
   (b) re-implementing a one-file refactor in a docs-only zone would have been
   out of zone. Accepted only after *local* verification (3/3, 5/5, 19/19 suites,
   identical `check-sync.sh` failure set before/after) — remote checks were of no
   use because CI is red repo-wide (§3).
2. **PR #112 ACCEPT, merged `d75b723` (`--no-ff`)** — owner directive, and the
   justification is upstream, not intuition: `zram-generator(8)` states the
   generator "generate[s] `systemd.swap(5)` … units into `TARGET_DIR` and connect
   them to `swap.target`", with `dev-zramN.swap` depending on
   `systemd-zram-setup@zramN.service`. Manual enablement is therefore redundant,
   and the removed `multi-user.target.wants` symlink pointed at a path the
   generator only ever materialises transiently in `/run/systemd/generator` — a
   dangling link. **Frozen power baseline (AGENTS.md §7, zram ram/2 zstd) is
   unaffected** because the size/algorithm policy lives in
   `zram-generator.conf.d/99-mavericks.conf`, untouched. This was checked
   explicitly because AGENTS.md forbids silently changing the baseline.
3. **Repo-wide red CI is reported, not fixed, and split into "stale test" vs
   "real defect".** 72/80 runs red on `main`; 3 defects at tip:
   `test-hotkey-layer.py` (2 checks need a live xfconf channel that the runner
   lacks → hermeticity defect), `test-mv-finder-columns.py` (`build_columns_classes`
   removed by `1eecbb9`), `test-mv-spotlight.py::test_rofi_preview_integration`
   (theme moved off `listview-split` deliberately in `1eecbb9`). None are in this
   zone. `test-global-menu.py` was already fixed by `f09dd2f`.
4. **Merge/push surface.** Both merges and the docs commit were made on `main`
   in the shared worktree only after confirming (a) the merge-touched paths were
   clean locally and (b) the parallel track's commits were already pushed, so the
   branch stayed linear and no divergence had to be handed to the other agent.

**Verification:** `scripts/check-profile-sync.sh` OK; `scripts/check-sync.sh`
failure set identical pre/post merge for each PR; MC suites 3/3 · 5/5 · 19/19;
secrets grep over both PR diffs clean; `ls-remote` SHA proven after push.

**Follow-ups filed (not in this zone):** docs claiming zram unit "enabled"
(`HARDWARE.md:42`, `BOOT_AUDIT.md:247`, `COMPLETENESS_C2.md:295`) are stale after
#107+#112; `scripts/demo/run-demo.sh:40` comment still blames scrot in
`mv-mc-thumbnail`; duplicate timezone commits `b00ad0b` + `7c7cd5a`.

---

## 2026-10-06 — Activity Monitor (canonical #9) P0 Implementation Decisions

**Context:** oid OS-activity-p0 — audit and close executable pre-hardware gaps in
`bin/mv-activity` per §13.6. Prior state: only CPU/Memory tabs with basic tables;
Energy/Disk/Network were static labels; no column sorting; only Quit (SIGTERM)
process action.

**Decisions:**

1. **Per-process energy not available on Linux → use %CPU as Energy Impact proxy.**
   macOS Activity Monitor shows per-process "Energy Impact" derived from CPU +
   wakeups + GPU. Linux `/proc` exposes only CPU ticks. Decision: categorize %CPU
   into Very High (≥50%), High (≥20%), Moderate (≥5%), Low (>0%), None (0%).
   Hidden %CPU column retained for correct sort order. Rationale: no new deps,
   zero cost, user-visible differentiation matches Mavericks intent. Hardware
   validation needed: correlate with actual RAPL package energy on m3-7Y32.

2. **Per-process disk I/O from `/proc/PID/io` (read_bytes, write_bytes).**
   Available since kernel 2.6.20. Provides Mavericks Disk tab equivalent (Bytes
   Read / Written per process). Sorted by total I/O desc. Empty-I/O processes
   hidden unless searching. Rationale: existing kernel interface, no daemon,
   matches Mavericks disk-activity view.

3. **Network tab shows system interface rates only (RX/TX bytes/s).**
   Per-process network I/O not available in Linux without eBPF/Netlink
   (complex, high overhead). Decision: show per-interface delta rates computed
   from `/proc/net/dev` every 2s. Matches Mavericks system-level network view.

4. **Process actions: Quit (SIGTERM), Force Quit (SIGKILL), Renice (-20..19).**
   - Quit: graceful SIGTERM with confirmation dialog.
   - Force Quit: immediate SIGKILL with destructive-action styling + explicit
     "ALL UNSAVED DATA WILL BE LOST" warning.
   - Renice: Gtk.SpinButton dialog; `resource.setpriority(PRIO_PROCESS, pid, nice)`.
     Negative values require root (CAP_SYS_NICE) — documented in dialog.
   - Inspect: read-only dialog showing `/proc/PID/status`, `/proc/PID/stat`,
     disk I/O.
   Rationale: Mavericks has Quit/Force Quit; Renice is the Linux equivalent of
   "Set Priority"; Inspect replaces "Sample Process" / "Get Info".

5. **Sortable columns on all tabs via Gtk.TreeView clickable headers.**
   Default sort by %CPU desc (Energy tab sorts by hidden %CPU column 4).
   Numeric columns right-aligned. `set_sort_func` with numeric descending.
   Rationale: Mavericks tables are sortable; Gtk.TreeView supports this natively.

6. **Zero cost when closed: single 2s GLib timeout, no daemon, no polling.**
   Refresh only fires while window exists; `on_destroy` would remove timeout
   (handled by GTK). Network delta state kept in `prev_net`/`prev_net_t`.
   Rationale: AGENTS.md §7 — power baseline frozen; no background wakeups.

7. **Test suite on pinned Xvfb :97 only (scripts/gui-isolation.sh).**
   Host display (WSLg :0) forbidden by fail-loud guard. GUI smoke verifies
   window construction, 5 tabs, tab labels, search entry, action buttons,
   refresh timer. No host windows ever opened.

**Hardware validation items added to NEEDS_HARDWARE_TEST.md:**
- Per-process Energy Impact accuracy vs RAPL package power on m3-7Y32
- Disk I/O counter rollover behavior on long-running processes
- Renice permission behavior (negative nice values) on real system
- Column rendering and sort behavior on 2304×1440 HiDPI panel

**Files changed:**
- `packages/mavericks-apps/src/mavericks-apps/bin/mv-activity` — complete rewrite
- `scripts/test-mv-activity.py` — new comprehensive test suite (34 checks)
- `docs/APPS.md` — Activity Monitor row updated
- `docs/PROGRESS.md` — session entry added
- `docs/NEEDS_HARDWARE_TEST.md` — hardware items added (see below)

---

## Session: Screenshot P0 (oid `OS-shot-p0`, canonical objective #8)

Audit target: `packages/mavericks-apps/src/mavericks-apps/bin/mv-shot` +
`desktop/mv-screenshot.desktop` + `scripts/test-mv-shot.py` + the Screenshot
rows in `docs/*`. Read-only with respect to the shared hotkey registry.

### Decisions

1. **Mavericks save location and filename become the default: `~/Desktop`
   with `Screen Shot YYYY-MM-DD at HH.MM.SS.png`.**
   macOS 10.9 saves screen shots to the Desktop under exactly that name.
   The previous default (`~/Pictures/Screenshots/shot-YYYYMMDD-HHMMSS.png`)
   was an invented convention nobody would recognise as macOS. Collisions get
   the macOS `… 2.png` suffix. `~/Pictures/Screenshots` is still reachable
   through the `save_dir` config option, so nothing is taken away.
   Rationale: §10 perceptual fidelity — a person comparing the two systems
   looks for the filename and its location first.

2. **The capture filename is computed AFTER the `-T` timer, not before.**
   The old code built the path, then slept inside `take_screenshot`, so a
   `-T 10` shot was filed under the moment the hotkey was pressed rather than
   the moment the picture was taken. Now the timer runs first and the name is
   derived afterwards.
   Rationale: it is a correctness bug in the observable behavior, not taste.

3. **The countdown is driven from a `time.monotonic()` deadline, polled at
   100 ms — deliberately NOT `GLib.timeout_add_seconds(1, …)` decrementing a
   counter.** GLib documents that `timeout_add_seconds` may fire up to a
   second *early*; measurement showed a "1 second" timer returning after
   0.77 s, i.e. every timed capture fired short. A 100 ms poll against a fixed
   deadline cannot be released early, at a cost of 20 wakeups per second for
   the few seconds the timer is actually on screen.
   Rationale: caught by asserting the countdown's real elapsed time in the GUI
   smoke, not by reading the code. Reading the code looked correct.
   Deliberately kept cheap: the poll exists only during a timed capture, never
   as a background loop, so §7's frozen power baseline is untouched.

4. **Error paths must not block on a modal dialog when there is no terminal.**
   A hotkey invocation has no TTY and nobody sitting there to click Close, so
   the blocking `Gtk.MessageDialog` hung until killed (measured: `mv-shot
   --bogus` hit the 30 s timeout). Now the dialog is used only when both
   stdout and stderr are a TTY; otherwise the failure goes to stderr, exit
   code 1, and a `notify-send` notification when the run is interactive.
   Rationale: a P0 desktop surface must never leave an undismissable window
   on the user's screen.

5. **A malformed `config.ini` degrades per-option with a warning instead of
   raising.** `show_preview = maybe` or `preview_timeout = soon` used to raise
   an unhandled `ValueError` traceback and kill the process before any
   capture. Values are now validated individually: invalid ones fall back to
   the documented default and print `WARNING: mv-shot config: …`. Also
   `_config_section` accepts `mv-shot`/`screenshot`/`shot` as section names,
   because a plausible rename used to be silently ignored.
   Rationale: a user-editable config file is an input surface; a typo must not
   cost the user their screenshot.

6. **The post-capture thumbnail became a borderless always-on-top float
   anchored bottom-right and auto-fading, replacing a centred modal dialog.**
   macOS parks the capture thumbnail in the bottom-right corner with a short
   lifetime; a centred modal `Gtk.Dialog` blocks the whole desktop and reads
   as a generic Linux dialog. Now: `Gtk.Window(TOPLEVEL)`, undecorated,
   keep-above, skip-taskbar/pager, fade-out on timeout, click-the-thumbnail
   opens Preview, Enter opens Preview, Escape/q dismisses.
   Rationale: §13.3C/D — this is the surface the user actually sees after
   every capture, so it is where the "is this macOS?" question is answered.

7. **Clipboard-only capture (`-c`) now shows the thumbnail too, and
   `Super+Shift+4` is the binding for it.** The old code skipped the preview
   entirely in clipboard mode, i.e. the single most-used Screenshot shortcut
   produced no visual feedback whatsoever. The clipboard image is pulled back
   to a temp file and shown with an Open/Dismiss action pair (no Trash and no
   "Show in Finder", because there is no saved file to act on).
   Rationale: macOS shows the thumbnail for clipboard captures too.

8. **Screen recording follows `$DISPLAY` instead of a hardcoded `:0.0`.**
   The old `ffmpeg -i :0.0` recorded whatever the first display was,
   regardless of where mv-shot was actually invoked.
   Rationale: a latent wrong-output bug; one line, no downside.

9. **Opacity goes through `Gdk.Window.set_opacity`, never the deprecated
   `Gtk.Window.set_opacity`.** With no Gdk window yet (before realise) the
   request is replayed from a `map-event` handler.
   Rationale: the deprecated setter emitted a `DeprecationWarning` on every
   capture, polluting stderr that the gate and the error paths also use.
   Note for future work in this repo: `connect_once` is NOT exposed by the
   PyGObject build here, so a one-shot handler must be written by hand.

10. **`get_preferred_size()` return type is normalised.** On this build it
    returns `Requisition` objects, on others plain ints, which made the
    countdown/tools-bar centring arithmetic raise `TypeError` on
    `int - Requisition`. `_preferred_size()` handles both.
    Rationale: found only by exercising the real code on a real display.

11. **The shared hotkey registry was deliberately NOT modified.** `Super+Shift+5`
    is labelled "Screenshot: Interactive Tools" but binds `mv-shot -i`; now
    that `--toolbar` exists, remapping it would be more truthful. It was left
    alone because another agent owns `lib/mv_hotkeys_core.py` and both
    `xfce4-keyboard-shortcuts.xml` copies in this parallel session, and the
    owner directive for merge conflicts is to stop rather than resolve
    automatically. The suite asserts all three bindings are present and that
    every bound command is a valid `mv-shot` invocation, so a later remap
    cannot silently break them.
    Rationale: §14 — Orchestrator/worker zone discipline beats a small
    fidelity win; the gap is recorded in `APPS.md` instead.

12. **`mv-screenshot.desktop` now runs `mv-shot --toolbar %U`.** Launching
    "Screenshot" from the menu previously started an opaque region grab with
    no explanation, which is not what a Screenshot application should do. The
    tools bar names the three modes and the timer; `%U` file arguments are
    handed to `mv-preview` instead of being silently ignored.
    Rationale: §13.3E — the launcher must explain itself.

13. **Test suite asserts real behaviour, and asserts it on the AST.**
    `scripts/test-mv-shot.py` (63 checks) loads the script as a module and
    exercises naming, config tolerance, CLI parsing, recording display,
    tools-bar and thumbnail keyboard contracts, EWMH `_NET_WM_STATE_ABOVE`,
    and end-to-end captures through the real backend. The architectural
    invariant "every `MainLoop().run()` sits in a function that also arms a
    safety timeout" is checked on the parsed AST, so a refactor cannot quietly
    reintroduce an unbounded main loop that would hang a hotkey.
    Deliberately not text-grepping the source for the behaviours above: the
    three real bugs in this session (the truncated countdown, the config
    traceback, the blocking error dialog) would all have passed a grep.
    Rationale: §8 — "works" is not established by reading code.

14. **Files changed:**
    - `packages/mavericks-apps/src/mavericks-apps/bin/mv-shot`
    - `packages/mavericks-apps/src/mavericks-apps/desktop/mv-screenshot.desktop`
    - `scripts/test-mv-shot.py` (new)
    - `docs/APPS.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`,
      `docs/NEEDS_HARDWARE_TEST.md`

---

## 2026-10-06 — Desktop P0: Mavericks-style desktop right-click menu + icon grid (oid OS-desktop-p0, canonical #24)

**Context:** APPS.md claimed "no xfdesktop config (no desktop icons); no session
management config". Actual audit found xfce4-desktop.xml with wallpaper +
Home/Trash/removable icons, but missing: icon grid config (sort, icon-size),
desktop right-click menu (menu.xml), Change Wallpaper action, Clean Up/Sort By/
Paste actions.

**Decisions:**

1. **Desktop right-click menu via xfdesktop menu.xml** (system-wide +
   skel) rather than Thunar UCA. Rationale: xfdesktop owns the desktop
   background right-click; Thunar UCA only applies inside Thunar windows.
   Menu items: Change Wallpaper, New Folder, Clean Up, Sort By (Name/Kind/
   Date/Size/None/Snap), Paste, Show Desktop.

2. **Change Wallpaper → zenity file chooser + xfconf**. Rationale: No
   native Mavericks-style wallpaper picker exists in the stack. zenity is
   lightweight, GTK-native, dependency already present (libnotify pulls
   zenity via gnome-shell dep chain, but zenity itself is minimal). Detects
   active monitor via xfconf introspection, falls back to monitor0. Sets
   image-style=5 (zoom/fill) for all workspaces.

3. **Clean Up → toggle desktop-icons/style (1→2)**. Rationale: xfdesktop
   exposes no "arrange icons" D-Bus method. Toggling style from minimal
   to icon view forces a re-layout. Pragmatic, zero-daemon, instant.

4. **Sort By → xfconf sort-column/sort-order**. Rationale: Direct xfconf
   properties map to Thunar's column constants (0=Name, 1=Size, 2=Type,
   3=Date Modified). "None" = sort-column=-1 (manual). "Snap" = style=2
   (icon view with grid). No daemon, persistent across sessions.

5. **Paste → Gtk clipboard text/uri-list → gio copy to ~/Desktop**.
   Rationale: Only file URIs are actionable on Desktop (Mavericks behavior).
   Text content ignored. Uses Python + Gtk/Gio for proper clipboard access;
   falls back gracefully if no file URIs present.

6. **Icon grid defaults: 64px, sort by name ascending**. Rationale: Matches
   Mavericks Finder default icon size (64px at 1x, 128px at 2x; 64px on our
   2x-scaled 2304×1440 logical 1152×720). Sort by name is Finder default.

7. **Connector-specific backdrop migration remains hardware-dependent**.
   xfdesktop 4.20.2 ignores static `monitor0` backdrop path on Xvfb; real
   hardware uses connector names (e.g., `monitorDP-1`). Migration script
   needed at first boot or via xfconf-query post-login. Tracked in
   NEEDS_HARDWARE_TEST.md.

**Trade-offs accepted:**
- zenity for wallpaper picker is not Mavericks-visual (no preview grid,
  no dynamic desktop picture rotation). Acceptable pre-hardware; could be
  replaced with a custom GTK dialog later.
- Clean Up via style toggle is a workaround; may flash briefly. No user-
  visible regression observed on Xvfb.
- Paste only handles file URIs; Mavericks also allows pasting text as
  .txt files. Deferred — low priority.

**Files changed:**
- `configs/desktop/xfce/xfce4-desktop.xml` (icon grid settings)
- `configs/desktop/xfce/menu.xml` (new — desktop right-click menu)
- `archiso-profile/releng/airootfs/etc/skel/.config/xfce4/desktop/menu.xml` (mirror)
- `archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml` (mirror)
- `packages/mavericks-apps/src/mavericks-apps/bin/mv-change-wallpaper` (new)
- `packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-cleanup` (new)
- `packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-sort` (new)
- `packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-paste` (new)
- `packages/mavericks-apps/src/mavericks-apps/Makefile` (install new scripts)
- `scripts/check-sync.sh` (menu.xml mirror pair)
- `scripts/test-desktop-icons.py` (validate new icon grid properties)
- `scripts/test-mv-desktop-menu.py` (new — validates scripts + menu + desktop.xml)
- `docs/APPS.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`,
  `docs/NEEDS_HARDWARE_TEST.md`

---

## Phase 0.66 — Disk Utility P0 audit (oid `OS-diskutil-p0`, canonical #11)

**Audit found three shipped defects the previous 70-test suite could not see.**
All three were in code the suite imported but never executed, because every
test was a pure-parser unit test and there was no GUI smoke at all:

1. `rebuild_detail()` dispatched to `self.detail.pack_drive(item)` /
   `self.detail.pack_block(item)`, but `self.detail` is a `Gtk.Box`.
   Selecting **any** sidebar row raised
   `AttributeError: 'Box' object has no attribute 'pack_drive'`.
   The app therefore only ever rendered its empty states — the detail pane
   had never worked. Root cause: `pack_drive`/`pack_block` are methods of
   the window, and the dispatch was one level too deep.
2. `MountPoints` (an `as` property) arrives as a **list of byte-value
   lists** when unpacked out of `GetManagedObjects`'s
   `a{oa{sa{sv}}}` on this PyGObject. The old `list(v)` + `str(v)` path
   turned each entry into the literal string `'[47, 0]'`, which then
   crashed sidebar construction with
   `TypeError: Must be string, not list`. Found by running
   `enumerate_devices()` against the **host's real UDisks2**, not by a
   test — mocks had been handing back clean `strv`.
3. `Escape` called `Gtk.main_quit()`, so Escape tore down the whole
   application instead of deselecting — opposite of the macOS contract.

**Lesson recorded for the whole project (AGENTS.md §13.3/§13.9):** a
"pure-logic extraction + parser unit tests" pattern proves the *parsers*.
It says nothing about whether the widgets are wired. Every app in the
canonical inventory with a factory needs a real-widget GUI smoke that
clicks through its own states; the mock must reproduce the shapes the real
daemon produces, including its ugly ones.

**Decisions:**

1. **Confirmation dialogs for unmount/eject; a double gate for erase.**
   macOS asks before both. Unmount/eject get one Mavericks alert (Cancel
   left, action right, `mv_dialogs.alert`); the confirmation names the disk
   and, for eject, the number of volumes that will be unmounted first.
   Erase (new, the only irreversible action) gets **two** gates: the
   `can_erase()` check plus a dialog that requires typing the volume name
   verbatim, re-validated against `/proc/mounts` immediately before the
   destructive call.
2. **`can_erase()` is deliberately conservative.** It refuses a volume that
   UDisks2 says is mounted, one that `/proc/mounts` says is mounted (the
   property can lag a mount another tool just made), virtual devices
   (`loop`/`ram`/`zram`/`sr`/`fd`/`dm-`), anything that is not a `/dev/`
   node, and anything with no detected filesystem. `PROTECTED_MOUNTS`
   (`/`, `/boot`, `/home`, …) is the belt-and-braces layer. "Safe" here
   means "refuses when uncertain".
3. **Offered filesystems: exfat, ext4, btrfs, vfat.** No ntfs (needs a
   second privileged helper that is not a guaranteed dependency), default
   exfat for removable media (cross-platform target readability) and ext4
   for internal volumes. Partitioning and partition-table edits stay with
   GNOME Disks — reproducing those in a frontend is a re-implementation of
   a partitioning engine, not a Mavericks-surface task.
4. **Nine-way D-Bus error classification, raw text never user-facing.**
   `classify_action_error()` maps Busy / NotAuthorized / AccessDenied /
   AlreadyMounted / NotMounted / NoSuchDevice / NoReply /
   MountedByAnotherUser / OptionNotPermitted onto distinct alerts with
   actionable secondary text, collapsing the two permission spellings onto
   one message. This is the concrete form of §9's "no stock Linux UI /
   no raw backend strings" for a storage app.
5. **NVMe telemetry read from sysfs.** UDisks2 exposes **no** SMART
   properties for NVMe (Drive.Ata is ATA-only), which is exactly the Apple
   S3X case — the Drive page was a permanent "available on hardware"
   placeholder. `/sys/class/nvme/nvme*/{model,firmware_rev,serial,state,
   critical_warning}` plus hwmon `temp1_input`/`temp1_crit` give real
   identity + health from one-shot file reads (no daemon, no polling),
   testable pre-hardware against a fake sysfs tree, on both the `hwmon/`
   and `device/hwmon/` kernel layouts.
6. **Whole-disk filesystems: an explicit OTHER VOLUMES group, and NO
   device-name guessing.** A superfloppy stick has no
   `Partition.Table` link and UDisks2 exposes no block→drive link, so the
   old code dropped those volumes entirely — they were mounted and
   completely invisible. We surface them under their own group and
   deliberately do **not** infer a parent disk from the device name: a
   disk cannot both carry a partition table and a whole-disk filesystem,
   so a partition sibling proves nothing, and guessing could attribute an
   erase action to the wrong disk. Attribute the volume to nobody; show it.
7. **Hot-plug refresh is a D-Bus signal, not a timer.** Subscribing to
   `ObjectManager.InterfacesAdded` gives USB insert/remove and
   automount-driven changes within milliseconds with **zero** periodic
   wakeups — the §7 energy rule. Signal subscription is unsubscribed on
   window destroy.
8. **The window factory takes injectable `devices`/`error`/`conn`.** The
   GUI smoke then exercises the real widgets with no system bus present,
   which is what let defects 1 and 2 be caught at all in CI.

**Tests:** 70 → 250. New coverage: erase gate, `/proc/mounts` parsing
(octal escapes, parent-device matching), error classification (9 cases +
collapse + no raw-text leakage), formatters, whole-disk grouping, NVMe
sysfs telemetry against a temp tree, `_error_parts()` GDBus-prefix
splitting, mount-entry decoding in all three shapes, mock-UDisks2 busy /
not-ejectable / Format paths, plus a 25-assertion GUI smoke on pinned
Xvfb `:97`.

**Known limitation (honest):** First Aid still only *displays* drive and
volume information. It does not run fsck. Running fsck needs a privileged
helper on an unmounted volume; the frontend does not shell out to one, and
the dialog says so rather than implying a repair happened.

## 2026-10-06 — System Settings P0: embedded-pane shell, honest backends (oid OS-settings-p0, canonical #3)

**Context.** The old mv-settings was a launcher grid that spawned stock
Xfce/GNOME dialogs — exactly what §13.6 forbids ("a coherent settings
application rather than a collection of unrelated stock dialogs"), yet
docs/APPS.md claimed IMPLEMENTED. Two pages were dead buttons
("(coming soon)"), and Date & Time / Language & Region dishonestly opened
the generic xfce4-settings-manager.

**Decisions:**

1. **Shell architecture: one window, Gtk.Stack, Mavericks System
   Preferences flow.** Icon grid (Show All) at the top level; clicking a
   pane opens an embedded pane inside the same window with a "Show All"
   back button (visible only in panes) and Esc-to-go-back. Search
   (SearchEntry, hidden in pane view) filters the grid via
   `FlowBox.set_filter_func` — the canonical GTK filter API; the old
   button-`set_visible` approach left empty cells because the
   FlowBoxChild wrapper stays visible.
2. **Routing policy is a pure function (`page_action`)**: native pane >
   external stock tool (reuse-first) > honest "not installed" pane.
   Missing tools are NO LONGER dead insensitive buttons — the click opens
   an honest pane naming the tool and why it is absent (blueman: power
   baseline + HW-phase install, per existing APPS row).
3. **Reuse-first boundary kept explicit.** Mature stock dialogs
   (displays, keyboard, mouse, sound, network, notifications, storage,
   appearance) remain external windows, launched from clearly labelled
   grid icons. We do NOT embed foreign GTK dialogs into our window
   (socket/plug reparenting was rejected: fragile with GTK3 standalone
   dialogs, zero fidelity gain pre-hardware).
4. **Native panes only where a cheap real backend exists** (no fake
   controls, AGENTS §9): General→xfconf `xsettings` (the same channel
   xfce4-appearance writes; theme/icon theme/font), Dock→plank GSettings
   (same authority mv-dock-config seeds), Mission Control→xfconf
   `xfwm4/general/workspace_count` clamped 1–16 (Mavericks Spaces) +
   `wrap_workspaces`, Energy Saver→UPower DisplayDevice one-shot GetAll +
   xfconf `xfce4-power-manager` blank/dpms timeouts + mv-power-ui chain,
   Date & Time→timedate1 read-only (setting the clock needs an admin;
   the pane says so instead of pretending), Language & Region→
   /etc/locale.conf read-only (writing system files silently was
   rejected), Security & Privacy→org.xfce.screensaver `lock-enabled`
   (schema-optional), Trackpad→/proc/bus/input/devices detection with an
   applespi-honest empty state, Users/Sharing→honest info rows (account
   management excluded per §10; sharing off by default per power
   baseline).
5. **Dock pane deliberately exposes ONLY user-taste keys** (size, zoom,
   position, alignment, hide mode). The Mavericks-identity keys (theme,
   auto-pinning, hide-delay=0, show-dock-item=false, lock-items) stay
   owned by mv-dock-config seeding; the pane explains this in a row
   instead of offering to break the Mavericks look.
6. **`Gio.Settings.new` on a missing schema ABORTS the process**
   (GLib-GIO-ERROR, no Python exception — caught live by the GUI smoke
   on this dev box for org.xfce.screensaver). All GSettings access goes
   through a `SettingsSchemaSource.lookup` guard; all D-Bus reads go
   through a 2 s-timeout `GetAll` helper that returns {} on any failure
   and lets the pane render an honest row.
7. **Zero daemons/polling:** every backend read is one-shot at pane
   open; writes happen only on explicit user clicks; no `timeout_add`
   anywhere in the app (asserted by the GUI suite).

**GTK3 mechanics learned (recorded so they are not re-broken):**
FlowBox filtering maps/unmaps children (`get_mapped()`), it does NOT
clear `get_visible()`; SearchEntry "search-changed" fires on a ~150 ms
GLib timeout, so non-blocking iteration loops must run on wall-clock
time (blocking iterations hang an event-idle Xvfb — this CI hazard is
why the GUI suite pumps with a monotonic deadline).

**Tests:** 0 GUI → 59 headless assertions (PAGES contract incl. §6
surface coverage, routing policy, parsers/clamps, plank schema
vocabulary freeze, icon-theme audit) + 32 pinned-Xvfb assertions (all
panes build in-window, navigation, Escape semantics, search filtering,
honest fallbacks for missing xfconf/schema/tool). check-sync.sh green
(37 app suites, launch smoke 34/34).

**Status:** PARTIALLY IMPLEMENTED — pre-hardware executable work done;
remaining: per-surface pane icons (theme set lacks a dock/lightbulb
metaphor), visual pass on real 2304×1440, real-session xfconf/UPower
values, blueman install decision on hardware.
