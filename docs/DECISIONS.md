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
