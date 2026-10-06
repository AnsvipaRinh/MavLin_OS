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

---

## 2026-10-05 — Owner PR triage: #3, #4, #5, #6, #61, #68, #77, #78 (Oct-4 owner batch)

**Scope:** read-only triage (oid OS-owner-prs-triage). No merges, no
product-code changes. All 8 PRs are owner-authored (AnsvipaRinh,
2026-10-04T19:17–23:08Z) → mandatory directives per OWNER-ISSUES RULE.

**Headline finding:** all 8 PRs are based on stale main (#3/#4/#5/#6:
458 commits behind, cut from d3ad090; #61: 74 behind, from PR #60
merge 3f97047; #68: 56 behind; #77/#78: 24 behind, from PR #75 merge
aef81e6). Re-polled `mergeable` after collection: **all 8 are
CONFLICTING / mergeStateStatus DIRTY** against origin/main (183c9d9).
Every PR's substance already exists on main via differently-worded
commits/PRs (#7, #18, the #37–#76 sync range c484b8d, PR #70
9429440, bfe60c2, f643a2d, a57de5a, d18829b). **Verdict: all 8
REJECT-as-superseded (close, do not merge).**

### Per-PR verdict table

| PR | Scope (files) | CI (why red) | Conflict w/ main | Verdict |
|---|---|---|---|---|
| #3 ci: enforce real GTK3 theme validation | ci.yml unit-tests job: sassc+gir deps, test-theme-css.py gate, lab-harness tests, discovery/firefox gates | Contribution Format (## headings, missing sections); Static Analysis (`E: Unable to locate package xmllint` — old workflow installs xmllint as an apt package; it ships in libxml2-utils); Unit Tests (`ModuleNotFoundError: No module named 'lab'` — lab/harness/tests/test_harness.py does `from lab.harness.fixtures import builder` while run as a file; needs PYTHONPATH=. or `python3 -m`); Profile Sync + Secret Scan green | CONFLICTING, 458 behind; main already runs `python3 scripts/test-theme-css.py` as "Theme validation" with sassc + gir1.2-gtk-3.0 installed | REJECT — superseded; lab gate broken as written. Revive only as fresh PR rebased on 183c9d9 with import fix + ### body |
| #4 fix: firstboot self-contained | mavericks-firstboot.sh, new mavericks-profile-select.sh, new mavericks-firstboot.service, profiledef.sh, apply-hardware-selection.sh, check-profile-sync.sh | Contribution Format; Static Analysis (xmllint); **Profile Sync — real contract violation: PR edited only the airootfs twin of mavericks-profile-select.sh; scripts/install twin drifted (check-profile-sync requires byte-identical pairs)**; Unit Tests + Secret Scan green | CONFLICTING, 458 behind; main already self-contained (PROFILE_SELECTOR/PROFILE_STORE paths, contract enforced in check-profile-sync.sh L88-106, both twins in check-sync PAIRS); main's firstboot also already dropped skel/lightdm/firefox/pacman-local installs (PR's deletions match main's direction) | REJECT — superseded + internal sync violation |
| #5 fix: Finder desktop entry | ci.yml, mv-finder.desktop, new test-finder-launcher.py | **NO CHECKS RUN AT ALL (0 check runs, statusCheckRollup [])**: PR's ci.yml edit is invalid YAML — a step injected at job level (`    - name:` 4-space indent) inside the `if: false` hardware-tests job → workflow parse failure | CONFLICTING, 458 behind; main already has `Exec=mv-finder-columns %U` + "Finder launcher regression gate" (scripts/test-finder-launcher.py) in unit-tests | REJECT — superseded + broken workflow file |
| #6 fix: panel plugin config validity | ci.yml static-analysis job, airootfs xfce4-panel.xml, new test-panel-config.py | Contribution Format (all 12 sections present but ## level; job requires ###); Static Analysis (xmllint; plus latent check-sync drift: PR edits only the airootfs panel-xml twin — configs/desktop/xfce/xfce4-panel.xml untouched, pair enforced by check-sync.sh L50); Profile Sync/Unit/Secret green | CONFLICTING, 458 behind; main already runs test-panel-config.py in static analysis ("Panel configuration validation") and synced the panel-xml twins (a57de5a); main's panel has NO genmon plugin (mv-apple→appmenu→separator→systray→clock→power-manager) — PR's genmon plugin-7/milliseconds repair targets a layout that no longer exists | REJECT — superseded; genmon defect non-reproducible on main's panel layout |
| #61 fix: preserve XDG desktop entry IDs | mv-launchpad, mv-spotlight, mv_desktop_cache.py, test-mv-desktop-cache.py | Contribution Format only (omits "Visual" section); Profile Sync/Static Analysis/Unit Tests/Secret Scan green | CONFLICTING, 74 behind; main's mv_desktop_cache.py already computes `desktop_id = rel.replace(os.sep, "-")` recursively with user/system precedence, plus later hardening (quarantine from #60, value escapes from #76, XDG_CURRENT_DESKTOP/PATH in fingerprint, lazy Gtk) | REJECT — superseded (landed via #37–#76 sync) |
| #68 fix: persist Launchpad ID migrations | mv-launchpad load_folders + new test-mv-launchpad-migration-persistence.py | Contribution Format only (omits "Visual"); all other gates green | CONFLICTING, 56 behind; main's load_folders contains the exact 2-line change (`migrated_ids, migrated = _migrate_app_ids(...); changed = changed or migrated`) feeding the existing atomic-save path — landed via PR #70 / #37–#76 sync | REJECT — superseded |
| #77 docs: sync menu bar inventory | docs/APPS.md Menu Bar + Application Menu rows | Contribution Format only (omits "Visual") | CONFLICTING, 24 behind; **same hunk as #78** (@@ -68,9 +68,9 @@); main's rows are already IMPLEMENTED — HARDWARE VALIDATION REQUIRED with more detail (plugin chain, xsettings, gating tests) | REJECT — superseded + direct collision with #78 |
| #78 docs: refresh global menu status | docs/APPS.md (same two rows) | Contribution Format only (omits "Visual") | CONFLICTING, 24 behind; same hunk as #77 — mutually exclusive | REJECT — superseded; backends named correctly (vala-panel-appmenu + appmenu-gtk-module + custom mv-apple) but main's rows already document this with equal-or-greater detail |

### Special-attention items

**#78 vs the merged implementation:** matches on backends
(vala-panel-appmenu, appmenu-gtk-module, custom mv-apple panel plugin)
and on "no polling" behavior, but was written against a
24-commits-old APPS.md. Main's rows already state the full plugin
chain (mv-apple → appmenu → expand separator → systray → clock →
power-manager), the xsettings wiring (ShellShowsMenubar /
ShellShowsAppmenu = true, Modules = appmenu-gtk-module), and the
gating contracts (test-panel-config + test-global-menu +
test-appmenu-module). Nothing new to merge.

**#61 + #68 — destructive potential:** LOW. #61 changes only cache
fingerprint/keying — the cache invalidates automatically on fingerprint
change (rebuild; no user data touched). #68 writes
~/.config/mv-launchpad/folders.json through the existing atomic-save
path (tmp + replace); corrupt-file handling in load_folders already
preserves a bad user file instead of overwriting it. Neither PR ships
explicit backup/rollback provisions, but atomic-save + corrupt-preserve
semantics bound the blast radius. Both changes are already on main with
these same properties. **Dependency order if ever revived: #61 first
(canonical desktop IDs), then #68 (migration persistence consumes the
ID translator).**

**#19 (xfwm double-click) — current state:** CLOSED 2026-10-04T21:27Z,
never merged (mergeCommit null). Its content IS on main: both xfwm4.xml
twins already carry `<property name="double_click_action" type="string"
value="maximize"/>` (line 13). Main commit 6090037 explicitly records
"PR #19 supersession". The triage-note conflict is resolved:
closed-superseded, content landed via another path.

### Collision map

- **ci.yml**: #3 (unit-tests job ~L109-150), #5 (EOF, malformed,
  inside `if: false` hardware-tests job), #6 (static-analysis job ~L47)
  — no inter-PR hunk overlap among the three, but all conflict with
  main's heavily-evolved ci.yml.
- **xfce4-panel.xml twins**: #6 edits the airootfs side only →
  check-sync drift vs configs/desktop twin.
- **mavericks-profile-select.sh twins**: #4 edits the airootfs side
  only → check-profile-sync drift vs scripts/install twin.
- **mv-launchpad**: #61 (load_desktop_apps ~L51) vs #68 (load_folders
  ~L164) — no hunk overlap; #68 is downstream of #61.
- **docs/APPS.md**: #77 ≡ #78, identical hunk — mutually exclusive.

### Hypothetical merge order (NOT recommended — all superseded)

If the owner revives any of this work: (1) #61 → (2) #68 (hard
dependency), (3) #3/#5/#6 in any order but only after full rebase onto
183c9d9 with the fixes listed above, (4) #4 after rebase + both-twins
sync, (5) at most one of #77/#78. **Recommended action: close all 8
as superseded**; if the lab-harness CI gate (#3's unique addition) or
the genmon panel repair (#6) is still wanted on current main, open
fresh PRs rebased onto 183c9d9.

### Process notes

- All 8 PRs fail Contribution Format for body reasons: #3/#4/#5 use
  ## headings and lack most of the 12 required sections; #6 uses ##
  (job regex requires ###); #61/#68/#77/#78 omit the "Visual" section.
- PRs #3/#4/#6 carry the old workflow containing the broken `xmllint`
  apt package (fixed on main: libxml2-utils only, see ci.yml L24).
- GitHub reported mergeable=UNKNOWN at collection start; re-polled to
  CONFLICTING/DIRTY for all 8 after compute completed.
- PR heads fetched read-only to local refs refs/remotes/pr-{3,4,5,6,61,
  68,77,78,19} for three-way analysis; no product code modified.

(End of owner-PR triage 2026-10-05)

---

## 2026-10-05 — Owner PR closeout (oid OS-pr-closeout)

All 8 superseded owner PRs closed as **close-do-not-merge** per df02e3e triage verdict.
Each PR's substance already exists on main (df02e3e01d6a1bc3a92635f7538a30af3b2ea457) via
different commits/PRs; branches were 24–458 commits behind and CONFLICTING.

| PR | Closed | Superseded by (main commits) |
|----|--------|------------------------------|
| #3 | 2026-10-05 | Theme validation gate (python3 scripts/test-theme-css.py) already in CI via df02e3e lineage |
| #4 | 2026-10-05 | Self-contained firstboot + profile selector (mavericks-profile-select.sh → mavericks-firstboot.sh) on main |
| #5 | 2026-10-05 | Finder desktop entry launches mv-finder-columns; implementation present on main |
| #6 | 2026-10-05 | Panel config validation (test-panel-config.py) + Mavericks menu bar (mv-apple + appmenu + systray + clock + power-manager) on main |
| #61 | 2026-10-05 | Nested desktop entry discovery + XDG desktop-ID preservation in mv_desktop_cache.py (os.walk, rel.replace) on main via #37–#76 sync |
| #68 | 2026-10-05 | Launchpad migration persistence (migrated return value + changed flag) in mv-launchpad load_folders() on main |
| #77 | 2026-10-05 | Menu Bar + Application Menu status = IMPLEMENTED — HARDWARE VALIDATION REQUIRED in docs/APPS.md on main |
| #78 | 2026-10-05 | Duplicate of #77; same rows already updated on main |

All closures pushed to origin.
---

## 2026-10-05 — GitHub sweep (oid OS-gh-sweep, post-f7602c4 wave)

**Baseline:** local HEAD `0291e83` (1 ahead of origin/main `f7602c4` — the MC
union merge). Sweep window: everything newer than the previously handled set
(PRs #3-#8, #61, #68, #77, #78 closed as superseded; issues #1, #2, #84 known).

### Inventory

| Surface | Count | Delta since last sweep |
|---|---|---|
| origin/main commits beyond f7602c4 | 0 | none (local was ahead) |
| Open PRs | 2 (#83, #86) | **+2 new** (#82 closed in-window) |
| Closed PRs in window | 1 (#82) | new |
| New/updated issues | 5 (#79 #80 #81 #84 #85) | **+3 new** (#79 #80 #81 #85); #84 updated |
| Releases / tags | 0 | none |
| Remote branches | 83 | only PR heads new: fix/mission-control-{markup-escaping,packaging,packaging-v2} |
| CI | stalled | green through 18:51Z; 3 failures 19:16-19:17Z (MC previews/drag/workspace-transfer pushes); **all runs since ~19:58Z permanently QUEUED** (runner/infra stall, includes f7602c4 push run 37371919511) |

### PR verdicts

**#86 — "fix: escape Mission Control window labels" — ACCEPT (merged `d9ebb8b`, --no-ff).**
- Claimed vs actual: TRUE. `mv-mc-gui` inserted raw X11 window titles/app names
  into `Gtk.Label.set_markup()` — `<`/`>`/`&` in a title corrupt or crash Pango
  parsing. Fix adds `html.escape` on both values; truncation happens BEFORE
  escaping (correct order — cannot split an entity).
- Static review: +4/-1, single file, no layout/activation/packaging impact.
  Secrets-grep: clean. Owner-authored (AnsvipaRinh).
- Verification (CI queued ⇒ local evidence): `py_compile` OK;
  `tests/test_mission_control_gui.py` 2/2 PASS; `test_mission_control_packaging.py`
  5/5 PASS with the merge in place. Merge clean vs local `0291e83` (its
  mv-mc-gui change is mode-only 644→755, no textual conflict).

**#83 — "fix: install Mission Control GUI and helper scripts" (v2) — ADAPT (partial supersession; left OPEN).**
- Claimed vs actual: packaging claim TRUE but INCOMPLETE — installs 5 MC
  helpers + `lib/mission_control.py`, misses `mv-workspace-count`; no tests.
  Local `0291e83` (issue #80, pushed in this sweep) installs all 6 + lib +
  187-line regression gate + CI wiring. Both bump pkgrel 5→6 identically ⇒
  textual conflict, and the local fix is strictly stricter.
- UNIQUE VALUE NOT superseded: commit `333e862` rewrites `mv-mc-thumbnail`
  from ImageMagick-`import`/`scrot`/`convert` subprocess chaining to the shared
  XComposite backend (`mission_control_thumbnail.capture_window`) — this is the
  actual fix for issue #85 and is NOT on main.
- Follow-up (MC-zone agent, not sweep): land the thumbnail-backend refactor on
  main (adapt `333e862`), keeping `0291e83`'s manifest/test gate; then close.
- #82 (v1, single commit, closed 3 min before #83 opened, no comment):
  superseded by #83 by construction. No action.

### Issue verdicts

| # | State | Verdict / evidence |
|---|---|---|
| 79 | OPEN | **Fixed on main by f7602c4**: both xfce4-panel.xml twins clean (0 conflict markers, production plugin tree mv-apple/appmenu/systray/clock/power-manager), Super+F3→mv-mc-gui bound. Residual red pre-existing on main: `tests/test_f3_mission_control_binding.py` fails — keyboard-shortcuts.xml has no `custom` shortcuts section (file byte-identical to origin/main; NOT touched by 0291e83/d9ebb8b). Belongs to #79/MC zone. Comment posted; owner to close. |
| 80 | OPEN | **Fixed by `0291e83`** (all 6 helpers + lib + pkgrel 6 + regression gate), published by this sweep's push. PR #83 also claims it — superseded (see above). Comment posted; owner to close. |
| 81 | CLOSED | Closure justified: main `mv-mc-overview` is the native GTK3 overlay importing shared MC libs — no CLI placeholder (restored by the MC union merge). |
| 84 | OPEN | No sweep action — fixed in `cc45518`, comment already present, awaiting owner closure per convention. |
| 85 | CLOSED | **Closure PREMATURE**: main's `mv-mc-thumbnail` still shells to ImageMagick/scrot/convert (verified on HEAD and identical on origin/main); the fix exists only in unmerged PR #83 (`333e862`). Covered by the #83 ADAPT follow-up. Clarifying comment posted. |

### Remote branches

No new branches beyond the three PR heads above. All other unmerged branches
(qwen-port-work, global-menu*, native-expose v1-v6, portable-app-fixes,
xfwm-double-click-*, runtime-contract, theme-validation-gate,
panel-config-validity, finder-launcher, self-contained-firstboot, docs/*)
are unchanged since the 2026-10-04/05 triage sections above — re-verified via
`git cherry` patch-equivalence; no new divergence, no action.

### CI stall note

GitHub Actions has been fully QUEUED since ~19:58Z (23+ runs incl. main
pushes and PR checks; last completed run 18:51Z success). All merge/accept
decisions in this section therefore rest on local test evidence recorded
above, not on remote green checks. Runner restoration should trigger a full
re-run; the queued f7602c4/0291e83 push runs will validate main retroactively.

(End of sweep 2026-10-05, oid OS-gh-sweep)

---

## 2026-10-06 — Second sweep of the day (oid OS-gh-sweep2)

**Baseline:** `d0956c1` (first sweep 2026-10-05: PR #86 ACCEPT/merged `d9ebb8b`,
PR #83 ADAPT-left-open, issues #79/#80/#81/#85 triaged).
**Zone:** GitHub inbound + docs ONLY (a parallel agent recovered the worktree in
code zones). Static review only; no foreign code was executed.

### 0. Worktree damage recovery (zone prerequisite)

`docs/EXTERNAL_AUDIT.md` was found REVERTED in the worktree by the parallel
`git stash` damage incident (−199 lines, the whole 2026-10-05 owner-PR triage
section). Restored with `git restore docs/EXTERNAL_AUDIT.md` from HEAD before
appending this section. `docs/PROGRESS.md` and `docs/DECISIONS.md` were intact.

### 1. Inventory (all counts measured, not estimated)

| Class | Count | Notes |
|---|---|---|
| Commits on `main` since `d0956c1` | **76** | 40 `Mavericks Linux Agent`, 36 `AnsvipaRinh` |
| PRs created since baseline | **19** | #89, #103–#121 |
| PRs merged since baseline | **13** | #103,104,106,107,108,109,114,115,117,118,119,120,121 |
| PRs closed-unmerged since baseline | **6** | #105, #113, #116 (+#82/#88 earlier), see table |
| PRs open at sweep start | **2** | #89, #112 |
| Issues created since baseline | **16** | #87, #90–#102, #110, #111 |
| Issues still open | **1** | #1 (owner architecture plan, by design) |
| Releases | **0** | no tags/releases on the remote at all |
| Remote branches | **105** | 13 new since baseline; all are PR heads |
| CI runs failing | **72 / 80** | 100 % red on `main` since `e3af5a8` — see §5 |

### 2. PR verdicts — new inbound items

| PR | Author | Claimed | Actual (verified) | Verdict |
|---|---|---|---|---|
| **#89** `e9ddff0` | owner | rewrite `mv-mc-thumbnail` onto the shared XComposite backend | **TRUE and in-scope.** Diff is 1 file, +33/−85; uses `mission_control_thumbnail.capture_window(win_id, max_size=(w,w))`, whose `scale = min(max_w/w, max_h/h)` keeps the thumbnail aspect ratio identical to the old `width x width*h/w` resize, so **no fidelity regression**. LIBDIR `/usr/share/mavericks-apps` matches the Makefile install target. Bonus: `int(wid, 0)` now accepts `0x…` window ids. No new deps (`python-xlib`, `libxcomposite`, `libxdamage`, `libxfixes` already in `depends`), no secrets, no network, in-repo GPL2. | **ACCEPT — merged `d9cc7a9`** |
| **#112** `6607cde` | owner | drop the ISO-side manual `systemd-zram-setup@zram0.service` enablement | **TRUE and non-duplicated.** Merged PR #107 (`91fda8c`) removed the *firstboot* `systemctl enable` but left this symlink. Upstream `zram-generator(8)` verified this sweep: the generator emits `dev-zramN.swap`, wires it into `swap.target`, and the setup service is pulled in as a dependency ⇒ manual enablement is unnecessary. The removed symlink pointed at `/usr/lib/systemd/system/systemd-zram-setup@zram0.service`, which the generator materialises transiently in `/run/systemd/generator` — i.e. it was a **dangling pointer**, so removing it cannot regress zram. | **ACCEPT — merged `d75b723`** |

**Pre-merge validation actually executed** (clean `git clone` of `origin/main`
in `/tmp`, never in the damaged shared worktree):

- both merges are conflict-free onto `e8afdd8` (ort strategy, no manual hints)
- #89: `test_mission_control_thumbnail_helper` 3/3 · `test_mission_control_packaging`
  5/5 · `test_mission_control_thumbnail` 19/19 · `py_compile` OK
- #112: `scripts/check-profile-sync.sh` OK
- `scripts/check-sync.sh` failure set is **byte-identical before and after** each
  merge (`global menu contract` → now fixed by `f09dd2f`; `test-mv-finder-columns`;
  `test-mv-spotlight`) ⇒ **neither merge introduces a regression**
- secrets grep over both diffs: no `ghp_`/`github_pat_`/private-key material

### 3. Issue #85 — CONFIRMED OPEN GAP, now closed by this sweep

Last sweep flagged #85 as "fixed only inside unmerged PR #83". Re-verified:

- commit `333e862` is reachable **only** from `origin/fix/mission-control-packaging-v2`
  (= PR #83) — `git branch -r --contains 333e8620` → `pr/83` only, **not on main**
- main's `bin/mv-mc-thumbnail` shelled out to `import` (ImageMagick), `scrot`,
  `convert`, `xdotool getwindowgeometry`, plus a `/tmp/mc_thumb_<wid>.png` temp
  file — while `PKGBUILD` `depends` declared none of imagemagick/scrot
- the fix had been re-scoped as PR #89 and PR #83 was closed **superseded**
  (unmerged) at 2026-10-05T21:05:31Z with no comment on #89 at that time
- the path is LIVE: `mv-mc-gui` calls `run_helper("mv-mc-thumbnail", …)` once per
  window, so every Mission Control launch shelled into undeclared binaries
- **#85 is now genuinely fixed on `main` by merge `d9cc7a9`.** The issue can be
  closed.

### 4. Closed-unmerged PRs — all owner-closed, all superseded (no action)

| PR | Superseded by | Evidence on main |
|---|---|---|
| #82, #83 | #89 (this sweep) + `0291e83` | MC packaging already installed by `0291e83` |
| #88 | `a6113d4` | Calendar EDS helper installed |
| #105 | `7c7cd5a` + `b00ad0b` | timezone preservation landed **twice** (duplicate commits — history noise, see §6) |
| #113 | `a7cdf9b` (#114) | hotkey skills taxonomy fixed |
| #116 | PKGBUILD `optdepends` | `gthumb` + `exiftool` already declared |

Duplicate-commit finding: `b00ad0b` and `7c7cd5a` are byte-identical messages
("fix: preserve installer timezone during firstboot") applied twice to the two
firstboot twins. Harmless, but the second is redundant history.

### 5. NEW FINDING — CI has been 100 % RED on `main` for 30+ commits

This is the most important inbound fact of the sweep and it was **not** a
regression from any PR in the window: 72 of the last 80 runs are `failure`, last
green `main` run was `f8b335d` (2026-10-05T21:54Z); every `main` push since
`e3af5a8` is red, including the 13 owner PR merges and the parallel track's
visual-demo commits. The earlier "runner stall" is over — runs complete in ~3 min
now — so this is genuine red, not infrastructure.

Exactly **three** defects remain at tip `e8afdd8` (each reproduced locally on a
pristine checkout):

1. `scripts/test-hotkey-layer.py` — 2 checks fail **only in the runner**:
   `override saved; live channel unavailable (xfconf-query not found)`
   (`cli set stores the override`, `cli set reports the new accelerator`).
   Locally: `82 checks passed`. This is a **test hermeticity defect** (the suite
   silently depends on a live xfconf channel that the CI image does not provide),
   not a product defect. Owner decision needed: install `xfconf-query` in the
   runner, or make the live-channel assertions skip when it is absent.
2. `scripts/test-mv-finder-columns.py` — `AttributeError: module
   'mv_finder_columns' has no attribute 'build_columns_classes'`.
   `1eecbb9` ("visual-demo blockers") removed that API; the test still requires it.
   Already recorded in `DECISIONS.md` by the recovery commit — needs a decision
   on which side is authoritative (product API vs test).
3. `scripts/test-mv-spotlight.py::test_rofi_preview_integration` — asserts
   `children: [ inputbar, listview-split ];` but `1eecbb9` deliberately replaced
   that layout with `listview` + a native `preview` element because rofi aborted
   on `listview-split`/`icon-current-entry`. The **test is stale, the theme is
   intentional**; also recorded in `DECISIONS.md`.

`test-global-menu.py` is **fixed** on main (`f09dd2f`, dropped a stray space in
`XFCE_PANEL_PLUGIN_REGISTER (construct)`; the product was always valid C, the
contract assertion was byte-exact) — confirmed green locally and in run
`37402214672` no longer appears in the failure list.

None of 1–3 is in this sweep's zone: all three live in `scripts/` + product code.

### 6. Documentation drift created by the merged owner PRs (follow-ups, not fixed here)

- `docs/HARDWARE.md:42` still claims "systemd-zram-setup@zram0.service enabled",
  `docs/BOOT_AUDIT.md:247` claims firstboot "enables" it, `docs/COMPLETENESS_C2.md:295`
  lists the unit as enabled. After #107 + #112 nobody enables it any more — the
  generator owns it. These rows are now wrong.
- `scripts/demo/run-demo.sh:40` comment still says "mv-mc-thumbnail -> scrot";
  after `d9cc7a9` there is no scrot in that path (the PATH pin is still needed for
  other helpers, the comment is not).
- `docs/EXTERNAL_AUDIT.md` §3-row for #85 above is superseded by this section.

### 7. Owner-directive audit (#84–#111 — merged)

Spot-checked that each issue's substance actually landed, not just that the PR
merged: #84 protocol version (`AGENTS.md:1259` v18) ✓ · #87 helper modules
(`Makefile:53 mv_dialogs.py`) ✓ · #90 `thunar-uca-ytplayer.xml` install
(`Makefile:64`) ✓ · #91 Time Machine timer (`firstboot:199` loop over
`mv-reminders/mv-calendar/mv-timemachine-check.timer`) ✓ · #92 `libpulse` in
`depends` ✓ · #98 firstboot/profile-selector twin pair enforced
(`check-profile-sync.sh:95-100`) ✓ · #99 `docs/INSTALLATION_CONTRACT.md` ✓ ·
#2 Poppy prior-art audit (`docs/POPPY_AUDIT.md`, `PRIOR_ART_POPPY_OS_X_REVIEVE_AUDIT.md`) ✓.
One duplicate observed: issue #93's timezone fix landed as two commits (§4).

(End of sweep 2026-10-06, oid OS-gh-sweep2)
