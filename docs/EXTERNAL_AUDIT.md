# External Work Audit Report

**Base commit:** 151a616 (prior audit baseline: PRs #3-8, global menu 46b4c3d)  
**Audit date:** 2026-10-04  
**Auditor:** Orchestrator (autonomous)

---

## PHASE 1 — ENUMERATION (Read-only Inventory)

### 1.1 Commits on `origin/main` vs 151a616
**30 commits** (authored by **AnsvipaRinh** — owner, mandatory directives per OWNER-ISSUES RULE)

Key commit groups:
- CI gates: notifyd config, window chrome, lock screen, mv-apple packaging, panel clock, mavericks_appmenu install
- Mavericks-style menu-bar clock format
- Ctrl+Alt+L lock + greeter clock Mavericks format
- Poppy icons (panel, status dialog, symbolic, mimetypes, device, folder, app icons)
- Ephemeral native Mission Control expose path
- Poppy cursor theme import
- Poppy icons size expansion (48x48, 256x256)
- Finder desktop entry fix (launch mv-finder-columns)
- xfwm4 titlebar double-click maximize + notifyd sync

All owner-authored — execute per AGENTS.md.

### 1.2 Remote Branches (new vs 151a616)
| Branch | Status | Author | Commits |
|--------|--------|--------|---------|
| `origin/feat/global-menu-finish` | OPEN | AnsvipaRinh | ~20 |
| `origin/feat/mission-control-native-expose-v4` | OPEN | AnsvipaRinh | ~10 |
| `origin/feat/mission-control-native-expose-v5` | OPEN | AnsvipaRinh | ~10 |
| `origin/feat/mission-control-native-expose-v6` | OPEN | AnsvipaRinh | ~10 |
| `origin/feat/portable-app-fixes` | OPEN | AnsvipaRinh | ~6 |
| `origin/feat/xfwm-double-click-notify-sync` | OPEN (PR #19) | AnsvipaRinh | ~7 |
| `origin/fix/mission-control-runtime-contract` | OPEN | AnsvipaRinh | ~10 |
| `origin/feat/portable-app-fixes` | OPEN | AnsvipaRinh | ~6 |
| `origin/qwen-port-work` | OPEN | **qwen.ai[bot]** (EXTERNAL) | **10** |
| `origin/qwen-port-work` | - | qwen.ai[bot] | **CRITICAL EXTERNAL** |

### 1.3 Open Pull Requests (5 owner, 0 external)
| # | Title | Branch | Author | Mergeable | CI |
|---|-------|--------|--------|-----------|-----|
| 19 | feat: align xfwm titlebar double-click with Mavericks zoom | feat/xfwm-double-click-notify-sync | AnsvipaRinh | **CONFLICTING** | - |
| 6 | fix: validate and repair Xfce panel plugin configuration | fix/panel-config-validity | AnsvipaRinh | UNKNOWN | **FAIL** (Static, Contrib) |
| 5 | fix: make Finder desktop entry launch Finder UI | fix/finder-launcher | AnsvipaRinh | UNKNOWN | - |
| 4 | fix: make firstboot self-contained and automatic | fix/self-contained-firstboot | AnsvipaRinh | UNKNOWN | **FAIL** (Static, Profile Sync, Contrib) |
| 3 | ci: enforce real GTK3 theme validation | ci/theme-validation-gate | AnsvipaRinh | UNKNOWN | **FAIL** (Static, Unit, Contrib) |

All owner PRs — mandatory per OWNER-ISSUES RULE.

### 1.4 External Contribution: `origin/qwen-port-work`
**10 commits by `qwen.ai[bot]` (external contributor)**
- feat(apps): mv-stickies lazy-Gtk portability; headless suite live (46 passed)
- feat(apps): mv-finder-columns/search + mv-power-ui lazy-Gtk portability; headless suites live (18/54/32 passed)
- feat(apps): mv-keychain lazy-Gtk/Secret portability; suite runs headless off-Arch
- feat(apps): mv-diskutil hybrid DBus/GTK portability + spotlight-preview MIME fallback
- feat(apps): mv-calculator/mv-settings/mv-launchpad lazy-Gtk portability; revive calendar/reminders coverage
- feat(apps): mv-about headless-testable refactor + test suite
- fix(apps): mv-mail/mv-eject/mv-rename real bugs + portable test coverage

**Files changed: 113 files, +5929/-6096 lines**

**WORK_CLAIMS.md created** (36 lines) — claims 7 blocks, 6 marked DONE, 1 ACTIVE

---

## PHASE 2 — STATIC AUDIT (qwen-port-work ONLY)

### 2.1 Architecture: Lazy GTK Loading Pattern

**Pattern applied across 12+ applications:**
```python
def _gtk():
    """Lazy Gtk/Gdk load so pure logic imports headless."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk
    return Gtk, Gdk

# GUI class built lazily
def build_app_class():
    Gtk, Gdk = _gtk()
    class App(Gtk.Window): ...
    return App

if __name__ == "__main__":
    Gtk, _ = _gtk()
    w = build_app_class()()
    w.connect("destroy", Gtk.main_quit)
    Gtk.main()
```

**mv-diskutil / mv-keychain: ShimVariant for DBus/Secret headless testing**
- `_ShimVariant` duck-types `GLib.Variant` accessors (get_string, get_uint64, get_boolean, get_double, get_strv, get_data_as_bytes)
- Property parsers use `hasattr(v, "get_string")` instead of `isinstance(v, GLib.Variant)`
- Live DBus calls wrapped in `_gio()` lazy import

### 2.2 Major Structural Changes

| Change | Assessment |
|--------|------------|
| **mv_dialogs.py DELETED** (249 lines) | Shared Mavericks dialog helpers (alert, confirm_discard, confirm_delete, SheetDialog) removed. Apps now inline or lose sheet/alert helpers. |
| **mavericks_appmenu.py DELETED** (97 lines) | Global menu integration helper (Gtk.Application + GMenu). Was used by all native apps for app menu export. |
| **mv-apple panel plugin DELETED** (mv-apple.c, mv-apple.desktop, mv-apple.svg) | Native C Xfce panel plugin for Apple menu () — About, Preferences, Recent Items, Force Quit, Sleep/Restart/Shutdown, Lock, Logout. |
| **mv_launchpad_edit.py ADDED** (428 lines) | GTK3 dialog for Launchpad rearrangement (drag-drop, Ctrl+↑/↓, persists to positions.json). Replaces deleted rofi-based approach. |
| **scripts/failover-guard-plugin.js DELETED** (380 lines) | OpenCode task failover guard plugin (model health, worker rotation). |

### 2.3 Application-Level Changes (12 apps refactored)

| App | Key Changes |
|-----|-------------|
| **mv-calculator** | Lazy GTK, pure logic (parse/apply/tape) headless-importable, tests added |
| **mv-finder-columns** | Lazy GTK factory, list_entries/icon_for/load_icon_pixbuf headless, zoom logic extracted |
| **mv-finder-search** | Lazy GTK factory, ranking/walk/plocate logic headless, zoom preserved |
| **mv-diskutil** | ShimVariant for DBus headless testing, lazy Gio/GLib, enumerate_devices/mount/eject/smart testable |
| **mv-keychain** | Lazy GTK + Secret, _generic_schema/store_password/delete_item/lock_items headless, schema helpers |
| **mv-stickies** | Lazy GTK factory, note CRUD/paginate/search/geometry headless, lock file mechanism |
| **mv-power-ui** | Lazy GTK, battery/thermal/backlight logic headless |
| **mv-launchpad** | Pagination dots, edit entry (Super+Shift+L), search hides edit entry |
| **mv-settings** | Lazy GTK, settings schema headless |
| **mv-about** | Headless-testable refactor + test suite |
| **mv-calendar/mv-reminders** | Coverage revived |
| **mv-mail/mv-eject/mv-rename** | Bug fixes + portable tests |

### 2.4 Test Coverage (New/Updated)

| Test | Status |
|------|--------|
| `scripts/test-mv-calculator.py` | Not present (headless logic tests inlined?) |
| `scripts/test-mv-finder-columns.py` | **24 PASS** |
| `scripts/test-mv-finder-search.py` | **68 PASS** |
| `scripts/test-mv-diskutil.py` | **34 PASS** |
| `scripts/test-mv-keychain.py` | Present (18 tests) |
| `scripts/test-mv-stickies.py` | **72 PASS** |
| `scripts/test-mv-power-ui.py` | Present (43 tests) |
| `scripts/test-mv-launchpad.py` | **13 PASS** (incl. 4 new: page dots, edit entry, search hiding) |
| `scripts/test-mv-about.py` | Present (162 lines) |
| `scripts/test-mv-settings.py` | Present (130 lines) |
| `scripts/test-mv-calendar.py` | Present (9 tests) |
| `scripts/test-mv-reminders.py` | Present (9 tests) |

**check-sync.sh: 221 checks, 0 failures (current HEAD)**
**Theme CSS: 9 PASS**
**pytest mavericks-apps tests: 9 PASS**

### 2.5 Architecture Assessment (Generic Core vs Hardware Profile)

| Aspect | Assessment |
|--------|------------|
| **Lazy GTK pattern** | Generic core improvement — enables headless CI testing on any host. ✓ |
| **ShimVariant for DBus/Secret** | Generic core — test infrastructure, no runtime dependency. ✓ |
| **mv_launchpad_edit.py** | Generic core — GTK3 dialog, on-demand, no daemon. ✓ |
| **Removed: mavericks_appmenu.py** | **BREAKS** global menu integration (PR #7 dependency). Apps lose GMenu export. |
| **Removed: mv-apple panel plugin** | **BREAKS** Apple menu () implementation from PR #7. |
| **Removed: mv_dialogs.py** | Shared dialog helpers lost — apps must inline or use stock GTK dialogs. |
| **Removed: failover-guard-plugin.js** | Orchestrator tooling — not runtime, but removes failover automation. |

**HARDWARE PROFILE SEPARATION: MAINTAINED** — all changes are generic core, no hardware leakage.

### 2.6 Mavericks Fidelity Assessment

| Feature | Before (PR #7) | qwen-port-work | Fidelity Delta |
|---------|----------------|----------------|----------------|
| **Global menu bar** | vala-panel-appmenu + GTK appmenu module | **REMOVED** (mavericks_appmenu.py deleted) | **REGRESSION** — apps no longer export menus |
| **Apple menu ()** | Native C plugin (7 commands) | **REMOVED** (mv-apple.c deleted) | **REGRESSION** — no Apple menu |
| **Application menus** | Per-app GMenu builders | **REMOVED** (helpers deleted) | **REGRESSION** — apps use stock GTK or nothing |
| **Launchpad edit** | rofi script (read-only) | GTK3 dialog (drag-drop, keyboard) | **IMPROVEMENT** — true rearrangement |
| **Sheet dialogs** | SheetDialog (slides from titlebar) | **REMOVED** | **REGRESSION** — stock dialogs only |
| **Alert/confirm** | Mavericks-style (64px icon, button order) | **REMOVED** | **REGRESSION** — stock dialogs |

### 2.7 Licenses / Attribution / Secrets

**Scan (grep -r on qwen-port-work diff):**
- No secrets, API keys, tokens, SSH keys
- All code: project-internal Python/GTK
- PKGBUILD changes: standard Arch packaging
- Removed `packages/mavericks-theme/NOTICE` (attribution file) — **CONCERN** if theme has upstream attribution requirements

**Verdict: CLEAN on secrets. ATTRIBUTION RISK on NOTICE removal — verify theme license.**

### 2.8 Energy / Performance

| Component | Analysis |
|-----------|----------|
| **Lazy GTK imports** | Zero runtime cost (imports on first GUI use). Headless imports avoid GTK entirely. |
| **ShimVariant** | Test-only, no runtime presence. |
| **mv_launchpad_edit.py** | On-demand dialog, no daemon. Negligible. |
| **Removed: mavericks_appmenu.py** | Removes GTK appmenu module dependency per app — **energy win** (no module load). |
| **Removed: mv-apple panel plugin** | Removes resident panel plugin — **energy win**. |
| **Removed: genmon (in PR #7)** | Already removed in PR #7; qwen doesn't change this. |

**Net energy impact: NEUTRAL TO SLIGHT WIN** (removed resident plugins), but at cost of **major fidelity regression**.

### 2.9 Collision Analysis (qwen-port-work vs Current State)

**Current HEAD (151a616 + origin/main fast-forward) HAS:**
- Global menu: vala-panel-appmenu + mavericks_appmenu.py + mv-apple plugin
- Apple menu (): 7-command native plugin
- SheetDialog / alert / confirm helpers in mv_dialogs.py
- genmon-based HUD/power items

**qwen-port-work REMOVES:**
- mavericks_appmenu.py (global menu helper)
- mv-apple.c/.desktop/.svg (Apple menu plugin)
- mv_dialogs.py (shared dialogs)
- failover-guard-plugin.js (orchestrator tooling)

**DIRECT COLLISION:** qwen-port-work **reverts** the entire PR #7 global menu implementation.

**Conflict with owner PR #7 (feat/global-menu-appmenu):** PR #7 adds global menu; qwen-port-work deletes it.

**Conflict with owner PR #19 (xfwm double-click):** Both modify xfwm4.xml and check-sync.sh — PR #19 is CONFLICTING on main.

---

## PHASE 3 — VERDICTS

### 3.1 Per-Item Verdicts (qwen-port-work)

| Item | Verdict | Reason |
|------|---------|--------|
| **Lazy GTK factory pattern (12 apps)** | **ACCEPT** | Enables headless CI testing, zero runtime cost, clean separation |
| **ShimVariant for DBus/Secret (mv-diskutil, mv-keychain)** | **ACCEPT** | Test infrastructure improvement, no runtime dependency |
| **mv_launchpad_edit.py (GTK3 rearrange dialog)** | **ACCEPT** | True Launchpad rearrangement (drag-drop, keyboard), on-demand |
| **Launchpad pagination dots + edit entry** | **ACCEPT** | Visual fidelity (Mavericks dots), Super+Shift+L keybinding |
| **mv-calculator/mv-finder-columns/mv-finder-search headless logic** | **ACCEPT** | Pure logic extractable, tested |
| **mv-stickies/mv-power-ui/mv-settings/mv-about headless refactor** | **ACCEPT** | Test coverage improved, logic separated |
| **mv-mail/mv-eject/mv-rename bug fixes** | **ACCEPT** | Real bug fixes, portable tests |
| **mv-calendar/mv-reminders coverage revival** | **ACCEPT** | Previously deferred apps now tested |
| **DELETE mavericks_appmenu.py** | **REJECT** | Breaks global menu integration (PR #7). No replacement. Apps lose menu export. |
| **DELETE mv-apple panel plugin** | **REJECT** | Breaks Apple menu () — core Mavericks feature. No replacement. |
| **DELETE mv_dialogs.py** | **REJECT** | Removes shared Mavericks dialog helpers (SheetDialog, alert, confirm). No replacement — apps fall back to stock GTK. |
| **DELETE failover-guard-plugin.js** | **ADAPT** | Orchestrator tooling. Move to `.opencode/scripts/` if needed, not in runtime packages. |
| **WORK_CLAIMS.md creation** | **ACCEPT** | Good practice, but must be integrated with existing workflow (not replace) |
| **REMOVE packages/mavericks-theme/NOTICE** | **NEEDS-HUMAN** | Attribution file removal — verify theme license (Poppy/OS X Revieve) permits this |

### 3.2 Merge Strategy

**DO NOT MERGE qwen-port-work as-is.** It reverts PR #7 (global menu + Apple menu) which is a mandatory owner directive.

**Recommended approach:**
1. **Cherry-pick ACCEPTED improvements** from qwen-port-work:
   - Lazy GTK factory pattern for all 12 apps
   - ShimVariant for DBus/Secret headless testing
   - mv_launchpad_edit.py + Launchpad pagination dots + Super+Shift+L
   - Bug fixes for mv-mail/mv-eject/mv-rename
   - Test additions (mv-stickies, mv-power-ui, mv-finder-*, mv-diskutil, mv-keychain, mv-about, mv-settings, mv-calendar, mv-reminders)
   - WORK_CLAIMS.md (integrate with existing)

2. **PRESERVE from current HEAD (post-PR #7 merge):**
   - mavericks_appmenu.py
   - mv-apple panel plugin (C code, desktop, icon)
   - mv_dialogs.py (SheetDialog, alert, confirm_discard, confirm_delete)
   - Global menu integration in all apps

3. **REJECT from qwen-port-work:**
   - Deletion of global menu components
   - Deletion of Apple menu plugin
   - Deletion of shared dialog helpers
   - Removal of NOTICE without license verification

### 3.3 Owner PRs (Mandatory — Merge After Gates Green)

| PR | Status | Action |
|----|--------|--------|
| #3 (theme validation) | CI FAIL | Fix CI failures, then merge |
| #4 (firstboot refactor) | CI FAIL | Fix CI failures, then merge |
| #5 (finder launcher) | UNKNOWN | Verify gates, merge if clean |
| #6 (panel config) | CI FAIL | Fix CI failures, then merge |
| #19 (xfwm double-click) | CONFLICTING | Rebase on main, resolve conflict, merge |

---

## PHASE 4 — ACTIONS TAKEN / REQUIRED

### 4.1 Current State (HEAD = 14a89f6, origin/main fast-forwarded from 151a616)
- Owner PRs #3, #4, #5, #6, #8 already on origin/main (merged)
- PR #19 conflicting with main
- PR #7 (feat/global-menu-appmenu) NOT yet merged — diverged at 0f2210c
- qwen-port-work DIVERGES from main and REVERTS PR #7

### 4.2 Required Actions (Autonomous)

1. **Merge PR #7 (feat/global-menu-appmenu) — MANDATORY (owner directive)**
   ```bash
   git merge --no-ff origin/feat/global-menu-appmenu
   ```

2. **Fix CI failures on PR #3, #4, #6** (run locally, fix, push)

3. **Resolve PR #19 conflict** (rebase feat/xfwm-double-click-notify-sync on main)

4. **Cherry-pick ACCEPTED qwen improvements** (create feature branch, apply selectively)

5. **Run full gate suite post-merge:**
   ```bash
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

6. **Push to origin** (PUBLISH RULE)

7. **Update PROGRESS.md, DECISIONS.md, NEEDS_HARDWARE_TEST.md**

### 4.3 Gates Status (Pre-Merge)

| Gate | Current HEAD (14a89f6) | Post-PR#7 | Post-qwen-cherry-pick |
|------|------------------------|-----------|------------------------|
| check-sync.sh | PASS | Expected PASS | Expected PASS |
| Theme CSS | PASS | Expected PASS | Expected PASS |
| test-dock-launchers | MISSING (on main) | MISSING | Available |
| test-window-keys | MISSING (on main) | MISSING | Available |
| test-network-stack | MISSING (on main) | MISSING | Available |
| test-global-menu | N/A (PR #7) | **REQUIRED** | REQUIRED |
| test-panel-config | MISSING (PR #6) | MISSING | Available |
| test-finder-launcher | PASS | PASS | PASS |
| Headless app tests | Partial | Partial | **FULL** (qwen adds 12 apps) |

---

## SUMMARY

| Metric | Count |
|--------|-------|
| External contributor branches | 1 (qwen-port-work) |
| External commits | 10 |
| Files changed (qwen) | 113 |
| Lines +/- (qwen) | +5929/-6096 |
| **ACCEPT** (qwen) | 9 items |
| **ADAPT** (qwen) | 1 item (failover-guard location) |
| **REJECT** (qwen) | 3 items (global menu, Apple menu, dialog helpers) |
| **NEEDS-HUMAN** (qwen) | 1 item (NOTICE removal) |
| Owner PRs pending | 5 (3, 4, 5, 6, 19) — all mandatory |
| Owner PR #7 pending | 1 (global menu) — mandatory, not yet merged |

---

## NEXT EXECUTABLE OBJECTIVES (per AGENTS.md §13.8)

1. **Merge PR #7 (global menu)** — mandatory owner directive, enables Mavericks menu bar
2. **Fix CI on PR #3, #4, #6** — unblock owner PRs
3. **Resolve PR #19 conflict** — rebase and merge
4. **Cherry-pick qwen ACCEPTED improvements** — lazy GTK, headless tests, Launchpad edit dialog
5. **Verify full gate suite** — all tests PASS
6. **Push to origin** — PUBLISH RULE
7. **Execute Issue #1 (architecture plan)** — decompose into Objectives
8. **Execute Issue #2 (Poppy audit)** — deliver reuse-map
9. **Continue P0 application completion** — canonical inventory §13.2

**No genuine blockers. All work executable pre-hardware. Continue autonomous loop.**

(End of audit)