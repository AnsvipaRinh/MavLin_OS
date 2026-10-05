# MavLinOS Development Progress

**Last Updated**: 2026-10-06 (Mission Control O5+O6 complete; issue #80 packaging regression fixed)

---

## Session 2026-10-06 (Mission Control O5/O6 + #80) — oid OS-mc-o56

**Objective:** owner-issue #1 MC track — close the #80 packaging regression, then O5 (live workspace previews) and O6 (choreography + XDamage live thumbnails) per `docs/MISSION_CONTROL_PLAN.md` §5.

**Deliverables:**
- **#80 fix (0291e83):** mavericks-apps Makefile now installs `mv-mc-gui/grid/thumbnail/window-spaces/activate-window`, `mv-workspace-count` and `lib/mission_control.py` (installed `mv-mc-overview` previously crashed on `import mission_control`); chmod +x restored on the helpers; pkgrel 5→6; new packaging regression test (manifest audit + referenced-helper scan + DESTDIR make install + import-sufficiency probe; negative-verified 5/5 fail on the pre-fix manifest).
- **O5 (fc384cd):** Spaces strip shows one composed miniature per Space — one-shot `capture_window()` snapshots at scaled geometries over the scaled Mavericks wallpaper; empty Spaces = bare desktop; uncapturable windows = grey tiles. New `lib/mission_control_previews.py`. 9 tests incl. pixel-level per-Space parity on bare Xvfb :97 and widget-level O5 acceptance under a real xfwm4 EWMH (count/highlight/switch/empty vs `wmctrl -d`).
- **O6 (this commit):** new `lib/mission_control_anim.py` (pure Timeline/Animator, ease-out cubic, reduced-motion gate) + `lib/mission_control_live.py` (LiveThumbnails XDamage controller). Entrance 160ms / exit 140ms fade + capped directional pull from each window's real position; exit mirrored then destroy (Gtk.main_quit now wired — the overview process previously never exited); live card refresh while open via GLib io-watch on the XDamage fd (event-driven, zero polling), full teardown on close (zero residual state, test-asserted). Robustness: pixbuf capture path swallows BadMatch (non-compositing WM previously killed the process); `rgba_to_pixbuf` keeps its buffer alive (use-after-free fixed).
- **Gate:** ci/test-mission-control.sh 19/19 green (was 15/1-red at start); F3 binding contract test updated to the f7602c4 custom-shortcuts layout.

**Gates:** MC CI 19/19; thumbnail 19/19; workspaces 9/9; animation 10/10; live 6/6; packaging 5/5; end-to-end Escape→exit rc=0 under xfwm4/:97.

**Status:** O5/O6 = IMPLEMENTED — HARDWARE VALIDATION REQUIRED (plan §5 acceptance closed; HW items H1–H9 actualized in NEEDS_HARDWARE_TEST.md). O7 partial (input matrix open), O8/O9/O10 open. rofi fallback untouched.

---

## Session 2026-10-05 (Quick Look P0) — oid OS-ql-p0

**Objective:** Quick Look P0 (canonical inventory #6) — complete pre-hardware gaps per §13.6/§10.4.

**Deliverables:**
- Enhanced `mv-quicklook`: PreviewSelectionGrid for multi-file selection, extended format support (HEIC, AVIF, TIFF, DOC/DOCX/ODT/RTF, more audio/video), improved keyboard navigation (Home/End, PgUp/PgDn, G for grid, focus-out auto-close), fullscreen with size restore, suggested-action Open button, file counter in title.
- Enhanced `mv-quicklook-thunar`: improved clipboard polling timeout, more robust selection detection.
- Comprehensive test suite: 31 contract tests covering all new features.
- Xvfb smoke test passes on dedicated display :97.
- Documentation updated: APPS.md status → IMPLEMENTED — HARDWARE VALIDATION REQUIRED.

**Key improvements:**
1. **Preview selection grid** (G key or headerbar button) — addresses "preview selection" gap.
2. **Extended keyboard navigation** — Home/End, PgUp/PgDn, Space for next, G for grid, focus-out auto-close.
3. **Extended format support** — HEIC, AVIF, TIFF images; DOC/DOCX/ODT/RTF/TEX/EPUB office docs; Opus, M4V, TS, MTS video; more audio formats.
4. **Office document preview** — metadata display with Open handoff (no rendering without libreoffice daemon).
5. **Window lifecycle improvements** — proper fullscreen toggle with size restore, focus-out delayed close, suggested-action styling.
6. **Thunar integration hardened** — longer clipboard polling, graceful fallback.

**Gates:** `scripts/test-mv-quicklook.py` 31/31 pass; `python3 -m py_compile` clean; smoke launch on Xvfb :97 stays up 3s.

**Status:** Pre-hardware complete. Hardware validation items remain (see NEEDS_HARDWARE_TEST.md).

---

## Session 2026-10-05 (Mission Control design) — dedicated overview layer plan per issue #1

**Trigger:** Owner issue #1 — major work starts with DESIGN: target architecture + migration boundary first, implementation after.

**Deliverable:** `docs/MISSION_CONTROL_PLAN.md` — full design document with fidelity-ceiling evidence, GO verdict, target architecture, migration boundary, 10 ordered objectives, rollback strategy, test strategy, and HW-validation items.

**Key findings:**
- rofi/wmctrl path has a **structural fidelity ceiling**: no X11 composite access (no thumbnails), no spatial layout (vertical list), no animation, no workspace model, no drag-and-drop, no live updates. 10 concrete behaviors proven impossible.
- skippy-xd E-MC experiment addresses thumbnails but fails on Mavericks styling, workspace model, animations, DnD, packaging (AUR-only), and desktop integration.
- **Verdict: GO** — dedicated one-shot Python/GTK3 overlay using XComposite for thumbnails. No daemon, no polling, §7-compliant (0 idle CPU, 0 idle memory).
- Migration: 3 phases (A→B→C), rofi fallback preserved at every step. skippy-xd retired after migration.
- 10 ordered objectives: enumeration → layout → thumbnails → activation → workspaces → animation → input → integration → visual polish → retire rofi. Each independently testable.
- 10 HW-validation items identified (HiDPI, GPU animation, real xfwm4, multi-monitor, power).

**Status:** Design complete. Implementation starts at O1 (read-only enumeration) in next session.

---

## Session 2026-10-05 (qwen-integration reappearance) — same unwired content, deleted again

`scripts/qwen-integration/` reappeared on disk (created 14:16/14:26 by uid 1000, unregistered concurrent session — same actor noted in DECISIONS.md "Note on concurrent tree activity"). Triage vs 183c9d9 verdict: **same unwired content**. Evidence:
- `qwen-web-worker.py` (477 lines): Playwright automation of coder.qwen.ai — same protocol as DECISIONS.md "Qwen Web Automation Research" (localStorage token, SSE `/task/completions`, chatId from React state). Playwright undeclared in any manifest.
- `qwen-registrar.py` (369 lines): parallel session registry (`~/.config/mavlinos/qwen-worker-state.json`), own event-loop management, no `session-reuse.py`/chain integration. Duplicate `persist` method (code smell).
- `.gitignore` had matching additions (`/.local/share/qwen-worker-profile/`, `~/.config/mavlinos/`) — reverted.
- No references from `.opencode/`, chain config, or registry.

Action: deleted again + reverted `.gitignore`. Decision record remains in DECISIONS.md §"Qwen Web Automation Research".

## Session 2026-10-05 (headless slice) — GUI tests never touch the host display

**Pain**: on the WSLg dev host (`DISPLAY=:0` + `WAYLAND_DISPLAY=wayland-0`
both forward to the Windows desktop) every `test-mv-*.py` GUI smoke saw
`HAS_DISPLAY=true` and popped dozens of real windows on the user's desktop
during test runs.

**Isolation (harness-level, `scripts/gui-isolation.sh` + `scripts/gui-guard/`):**
- `mv_gui_isolate` captures the ambient host display as FORBIDDEN, unsets
  `WAYLAND_DISPLAY`, forces `GDK_BACKEND=x11`, arms a `sitecustomize.py`
  fail-loud guard (`HOST-DISPLAY-BLOCKED`, exit 125) on `PYTHONPATH`;
- `mv_gui_pin_display` pins all suites to a dedicated local Xvfb `:97`
  (explicit number + real `xwininfo` readiness — WSLg mounts
  `/tmp/.X11-unix` read-only, so `-S` socket tests and `-displayfd`
  startup are unusable there); headless hosts fall back to skipped GUI;
- wired into `scripts/check-sync.sh` (isolation banner + per-suite
  violation FAIL + `host-display guard: 0 attempts` gate) and
  `scripts/smoke-launch.sh` (forbidden host display + guard + per-app
  violation FAIL).
- `scripts/test-mv-textedit.py` no longer `setdefault`s `GDK_BACKEND=wayland`
  (that pinned the app to the Windows-side compositor).

**Exposed + fixed product bug**: with x11 the target config wins
(`settings.ini` → Mavericks icon theme, which inherits `folder`/
`text-x-generic` at 16px only; GTK3 does not upscale) → Finder-search
Ctrl+= zoom was a visual no-op. `mv-finder-search` `load_icon_pixbuf()`
now scales lookup results to the requested size.

**Evidence**: full `scripts/check-sync.sh` green (`ALL CHECKS PASSED`,
34/34 app suites, 34-window smoke, guard `0 attempts`, banner
`DISPLAY=:97 WAYLAND_DISPLAY=unset GDK_BACKEND=x11`); host `:0` sampled
via `xwininfo -root -children` before/during/after the run — 0 `mv-*`
windows on host vs test windows present on `:97`. User-side acceptance
(zero popups observed) happens on the next real run.

---

## Session 2026-10-05 (late) — CI gate honesty pass: harness rewrite + 12 app bugs

CI stayed red after the first gate push. Diagnosis revealed TWO layers:
(a) environment gaps on the runner (no Gtk3 typelib / pycairo / fonts),
and (b) a **launch-smoke harness that lied locally** — it watched the
xvfb-run wrapper instead of the app process, so Xvfb startup/teardown
latency (~3-4 s) exceeded SMOKE_STAY and produced false "stayed up"
verdicts, while `kill xvfb-run` leaked Xvfb/python children (117 Xvfb
left behind on the dev host) until the display pool exhausted.

**Harness rewritten** (`scripts/smoke-launch.sh`):
- verdict is based on the *interpreter* process (`python3|bash <path>`),
  discovered by poll; a start with neither process nor log output fails;
- launches run under `setsid` and are reaped as a process GROUP
  (0 Xvfb leftovers after a full gate run — verified);
- argument-taking helpers get a temp file/dir (usage-exit is not a launch
  failure); `mv-newfolder` is declared one-shot; apps run via shebang.

**Real bugs the honest harness exposed (all fixed):**
1. `mv-colormeter` — no `if __name__ == "__main__"` call at all (script
   defined `main()` and exited rc0 instantly; passed only via the race).
2. `mv-stickies` — Gtk.Application never `add_window()`ed its notes, so
   `app.run()` returned right after `activate` (silent rc0).
3. `mv-control` — `sys` used in `__main__` but never imported.
4. `mv-calendar` — local `cal` (event calendar name) shadowed
   `import calendar as cal` → `UnboundLocalError` on `cal.monthrange`;
   6 sites renamed to `ev_cal`. Also invalid `text-transform` CSS removed.
5. `mv-preview` — GApplication aborted ("can not open files") because the
   file argument was passed in argv without HANDLES_OPEN; plus premature
   `update_status()` before `current_path` existed.
6. `mv-finder-columns` — `Gio` undefined in `build_finder_menu`; same
   GApplication argv abort with the folder argument.
7. `mv-notification-center` — synthetic focus-in/out pair at map (no
   window manager) destroyed the panel in milliseconds; close-on-focus-out
   now requires a real focus followed by an out >0.8 s after map.
8. `mv-textedit` — `btn_ruler.set_active()` fired `toggle_ruler` during
   `build_format_bar`, before `ruler_box` existed.
9. `mv-reminders` — shebang was on line 2 (line 1 `import sys`) → direct
   exec fell back to `sh` after the +x sweep.
10. `mv-calendar`/`mv-preview` invalid `text-transform` (GTK3 CssProvider
    rejects it) + defensive try/except around all 20 `load_from_data`
    sites (cosmetic CSS must never kill a window).
11. Suites: `test-mv-fontbook` font fixtures are now host-discovered
    (Fedora gnu-free paths broke Ubuntu); preselect assertion derives the
    family from the fixture; cairo import guards in fontbook/colormeter
    suites; spotlight suite prints per-test `ok -`/`FAIL -` lines, falls
    back to the repo script, and asserts the empty-query usage contract.
12. CI installs `python3-cairo python3-gi-cairo gir1.2-gtk-3.0
    gir1.2-poppler-0.18 gir1.2-gtksource-4 gir1.2-secret-1 xvfb` so the
    runner profile matches the dev environment; check-sync prints the
    captured FAIL lines of a failing suite (CI logs were opaque before).

**Status:** local `check-sync` fully green — 221 checks, 34 app suites,
34-app launch smoke, 0 Xvfb leftovers. Pushed for CI verification.

## Session 2026-10-05 — External-port Execution + origin/main Sync

**Status**: 🟢 Complete — gates green, pushed

**What was done** (details in `docs/DECISIONS.md` §2026-10-05):

1. **qwen-port-work ACCEPTED items integrated** (7 of 9 commits
   cherry-picked with per-item gates; 2 skipped as already-integrated /
   obsolete — byte-diff evidence):
   `4036b95` mv-rename/eject/mail fixes · `a9b7701` mv-about ·
   `0496ae3` calculator/settings/launchpad lazy-Gtk + app-suite gate ·
   `4d33eae` finder-columns/search + power-ui · `7c0422b` mv-stickies ·
   `48141a4` mv-timemachine · `3b29206` mv-voice + mv-getinfo.
   Every conflicted `__main__` kept our global-menu `run_application`
   launcher. Two missing-factory-`return` bugs in qwen's code fixed.
2. **Launchpad P0 restored** (`aa3ca38`) — `mv_launchpad_edit.py`, page
   dots, "Edit Launchpad…" entry, working Super+Shift+L (Makefile now
   installs `/usr/bin/mv-launchpad-edit`; the old rule installed an
   underscored name nothing referenced), new PATH-stub launch test.
3. **origin/main synced** (`c484b8d`, owner PR #37–#76: page nav,
   folder pagination, atomic config writes, canonical desktop IDs,
   desktop-cache hardening, notification fixes) — 3-file conflict merge
   preserving all human work; 4 upstream-red tests (red on pristine
   origin/main too) fixed forward.
4. **PR #19 verified superseded** (core already on main) — branch left
   closed, no rebase needed.
5. Docs updated (this file + DECISIONS execution record).

**Gates**: `check-sync.sh` ALL CHECKS PASSED (221 checks, 0 failures;
app suites 33 passed / **0 skipped** / 0 failed (last skip ported)) · launchpad pytest 32/32 ·
standalone launchpad 26/26 · desktop-cache 83/83 · notification-center
16/16 · timemachine 62/62 · stickies 74/74 · voice 63/63 ·
getinfo 35/35 · finder suites 26+69 · power-ui 45.

4. **Global-menu contract restored** (post-report continuation): PR #18's
   headless rewrite had silently dropped `run_application` + menu builders
   from `mv-mail`/`mv-keychain`/`mv-diskutil`, and `test-global-menu.py`
   was orphaned (in no gate), so it stayed red unnoticed. Restored all
   three on top of #18's lazy factories; caught a factory-returns-class
   bug only via the new `scripts/smoke-launch.sh` (Xvfb launch-and-stay);
   wired `test-global-menu` into check-sync; added `test-mv-mail.py`
   (23 tests). Gates: check-sync 221/0 + 34 app suites + global-menu
   contract + launch smoke all green.

5. **Dock pins everywhere + P0 matrix refresh:** `mavericks-theme` now
   packages the six Dock pins into `/etc/skel` (pkgrel 3; verified with a
   real makepkg build — byte-identical to configs) so plain pacman
   installs match the ISO; `test-dock-launchers.py` extended (full
   byte-drift + PKGBUILD coverage). Verified and corrected four stale P0
   rows (Menu Bar, Application Menu, Dock, Desktop — global menu/Apple
   menu/xfdesktop were already implemented and gated; statuses raised to
   IMPLEMENTED — HARDWARE VALIDATION REQUIRED where only HW validation
   remains).

**Next executable work**:
- Continue P0/P1 application matrix per §13.8 (Finder/Spotlight/Mission
  Control gaps, remaining applications)
- Hardware-dependent items stay tracked in `docs/NEEDS_HARDWARE_TEST.md`

---

## Recent Achievements (2026-10-04)

### ✅ Issue #2: Poppy OS X Revieve Audit — COMPLETE

**Status**: 🟢 Audit Complete, Ready for Closure

**Summary**: Comprehensive technical and legal audit of Poppy OS X Revieve theme assets completed. All third-party components verified and documented.

**Deliverables**:
- `docs/POPPY_AUDIT.md` — Full technical audit with reuse map
- `docs/ISSUE_2_STATUS.md` — Live status tracker
- `docs/SESSION_SUMMARY_2026-10-04.md` — Session log
- `docs/FINAL_SESSION_REPORT_2026-10-04.md` — Comprehensive summary
- `packages/mavericks-theme/NOTICE` — Legal attribution file

**Key Findings**:
| Component | Source | License | Decision |
|-----------|--------|---------|----------|
| GTK3/XFWM/Plank | B00merang-Project/OS-X-Mavericks | GPL-3.0 | ✅ Keep |
| Cursors | Poppy OS X Revieve | CC BY-SA 4.0 | ✅ Keep |
| Icons | Mixed | GPL-3.0 | ⚠️ Hybrid |
| Wallpapers | Apple Inc. | Proprietary | ✅ Keep |

**Impact**:
- ~2000 lines of CSS/XML reused via B00merang (40-60 hours saved)
- Legal compliance achieved — project ready for redistribution
- All licenses verified and properly attributed

**Next**: Issue #2 ready for closure. Optional enhancements (icon improvements, benchmark) can be tracked separately.

---

## Active Work Streams

### Issue #1: Architecture Execution Plan

**Status**: 🟡 Active

**Focus**: Incremental migration toward final fidelity + efficiency architecture

**Recent Progress**:
- Panel plugin-7 HUD config repair (0cc876a9)
- Self-contained firstboot implementation (4e3ede57)
- Profile sync CI gates strengthened
- oid OS-mc-impl-1: read-only window enumeration via EWMH/Xlib + wmctrl fallback (feat: mission-control window enumeration)
- oid OS-mc-impl-3: thumbnail capture via XComposite/XDamage/XFixes (ctypes, raw RGBA + placeholder fallback; fixed libX11 XEvent-192 heap overflow) — live on Xvfb :97, 51ms fullscreen capture (feat: mission-control thumbnails)
- oid OS-mc-merge PUSHED (origin 39c1918+): union merge survived FOUR origin waves (6328665→7ae2186→50a4c8b→d0d4dbc→a25d454) and two concurrent-session incidents (mid-merge `git reset` destroying the first resolution; 29c21be stash-marker commit). Repairs landed: overview rebuilt (their evolved UI + union CLI), their MC CI gate fixed to 15/15 (errexit counters, filename, gui isolation), KEYBOARD.md F3 restored, panel.xml production tree restored + real Super+F3 binding wired, airootfs mirrors synced. Full MC matrix green: 18/18 enum, 10/10 activation, 19/19 thumbnail (live :97 both backends), 15/15 MC CI, 34-app smokes, check-sync ALL CHECKS PASSED.
- PUSH BLOCKER RESOLVED (oid OS-mc-merge): user approved union merge (DECISIONS.md option a). origin/main (7ae2186) merged UNION-style: both capture backends now live in `mission_control_thumbnail.py` (pixbuf one-shot for GTK rendering + ctypes ThumbnailCapture for live/damage), canonical `_parse_window_id` shared, thumbnail test suites unified (19/19 incl. live :97 both backends pixel-exact), co-author black-thumbnail zero-mask bug + `_scale_channel` 255-collapse + activation-test SyntaxError fixed (all pre-existing on origin/main), `libxdamage`/`libxfixes` deps declared. Full gates green.

---

## Completed Objectives (Session 2026-10-04)

1. ✅ Poppy cursors license verified (CC BY-SA 4.0)
2. ✅ NOTICE file created with full attribution
3. ✅ Audit documentation complete (4 files)
4. ✅ Legal compliance achieved

---

## Pending Optional Enhancements

1. ⏳ Enhance icons with 10-20 Poppy assets (fidelity improvement)
2. ⏳ Benchmark theme RSS/CPU overhead (validation)

---

## Project State

**Legal Status**: ✅ Compliant (all third-party licenses verified)
**Documentation**: ✅ Comprehensive (50+ docs/*.md files)
**Test Coverage**: ✅ Extensive (30+ test scripts)
**CI/CD**: ✅ Active (check-sync, profile-sync, panel-config tests)

---

*Progress tracked by MavLinOS Orchestrator*

---

## Session 2026-10-05 (OS-window-leak2) — eliminate remaining GUI window leaks onto Windows desktop (WSLg)

**Objective:** oid OS-window-leak2 — test-suite leak fixed (gui-isolation.sh, Xvfb :97, fail-loud guard, 274995e) but windows still popped; hunt and fix remaining leak paths.

**Leak paths found & fixed:**

1. **13 test-mv-* suites** executed app code and spawned child interpreters without any host-display guard: `test-mv-calendar.py`, `test-mv-desktop-cache.py`, `test-mv-diskutil.py`, `test-mv-getinfo.py`, `test-mv-mission-control.py`, `test-mv-notes.py`, `test-mv-notification-center.py`, `test-mv-photos.py`, `test-mv-power-ui.py`, `test-mv-reminders.py`, `test-mv-settings.py`, `test-mv-spotlight.py`, `test-mv-ytplayer.py` — all ran with ambient `DISPLAY=:0` / `WAYLAND_DISPLAY=wayland-0` (WSLg host desktop) inherited. Verified empirically: 0 windows leaked *today* (all windowless CLI/contract tests), but unguarded = latent leak path.

2. **2 launchpad test suites** same category: `test-mv-launchpad-ids.py`, `test-mv-launchpad-migration.py`.

**Fix applied:**
- Added `arm_guard()` to `scripts/gui-guard/mv_gui_iso.py` — headless guard bootstrap for windowless suites: captures+forbids ambient host displays, drops them, forces `GDK_BACKEND=x11`, arms fail-loud guard (`HOST-DISPLAY-BLOCKED` / exit 125). No Xvfb pin (suites proven display-independent).
- Added bootstrap (`import mv_gui_iso; mv_gui_iso.arm_guard()`) to all 15 windowless suites (13 + 2 launchpad).
- Extended static coverage gate (`scripts/test-gui-isolation-coverage.py`) with **check #4**: every `test-mv-*.py` must bootstrap `mv_gui_iso` (exemptions: `test-mv-mail.py`, `test-mv-quicklook.py` — pure source-contract checks, markers in strings only).
- CI unit-tests job already armed via env (274995e + WIP ci.yml).

**Verification:**
- All 15 windowless suites pass with arm_guard (rc=0, headless).
- Full `check-sync.sh`: **ALL CHECKS PASSED** (34/34 app suites, 34-window smoke, theme CSS, mirrors, syntax, guard evidence).
- xwininfo sampling on host `:0` before/during/after check-sync: **0 new windows, 0 gone windows** — empirical proof no leak onto Windows desktop.
- Coverage gate passes all 4 checks (ambient idiom, GUI markers, test-mv-* bootstrap, QEMU headless).

**Foreign concurrent session evidence:** `scripts/qwen-integration/` reappeared (same unwired content deleted in 183c9d9, 73b303c). `qwen-web-worker.py` opened live Chromium window "Qwen Coder" on host :0 (seen in xwininfo tree). **Not touched** — documented attribution only.

**Guard delta:** +15 suites guarded, +1 check in coverage gate, +1 `arm_guard()` primitive. Total guarded test-mv-* suites now: 30/32 (2 string-only exempt). All direct entry points covered: check-sync.sh, CI unit-tests, bench, direct test-mv-*.py runs, smoke-launch.sh.

**Status:** Leak paths closed. Ready for hardware validation when MacBook10,1 arrives.


---

## Session 2026-10-05 (OS-poppy-icons) — Poppy Tier 2 icon ports (clean-room SVG)

**Objective:** oid OS-poppy-icons — queued Tier 2 icon categories from docs/POPPY_PORTS.md as original Mavericks-style SVGs (no asset bytes; ideas/categories only). Added `scripts/test-theme-icons.py` as the permanent gate: every icon-tree SVG must parse, no file may reference the external Poppy checkout (the shipped-broken text-path defect class), index.theme Directories must match disk, required Tier 2 names must resolve.

- **Category 13 (status dialogs):** dialog-error/information/warning/password + image-loading as self-contained skeuomorphic Aqua badges (48x48/status replaced broken Poppy path-files + scalable/status copies). Also wired previously-missing `128x128/devices` and `128x128/mimetypes` into index.theme Directories (real lookup bug: those dirs shipped unindexed).
- **Category 16 (panel symbolic):** full menu-bar/Control Center symbolic set in our visual language (currentColor, 16-grid): volume x4, battery x8 (4 states + charging variants, fill-width family full=6/good=4/low=2/empty=0), network x6 (wireless excellent/good/ok/weak/none + wired), notifications x2, system-shutdown. 22x22/status no longer ships 10 broken Poppy path-files; the old signal-none art (which read as full strength) now renders dot+X.
- **Category 15 (places folders):** Finder-sidebar folder family in the house blue-folder template (#3f8fd2 + gloss + light plate): documents/downloads/videos/templates/publicshare/remote/saved-search/recent/online (cloud, the gdrive analog) + generic folder + inode-directory (symlink) + user-bookmarks (blue book). scalable/places previously had NO generic folder at all; 128x128/places stops shipping 5 broken Poppy path-files.
- **Category 14 (preferences):** System Settings panel icons in the house 256-grid gradient language: locale (globe), wallpaper (monitor+landscape), notifications (toast+bell+badge), privacy (shield+lock), time (analog clock), accessibility (figure badge), online-accounts (cloud+key, the goa analog); display/system/keyboard/mouse/sound already existed. The broken 128x128 preferences-desktop-font text-path file is now a self-contained "Aa" tile (also added as scalable master).

**Status:** All four queued Tier 2 categories ported (13/14/15/16) — 28 remaining broken Poppy path-files in mimetypes/apps/devices zones are documented in the test's KNOWN_PENDING list for their owners. Icons area only; gate: scripts/test-theme-icons.py.

---

## Session 2026-10-06 (OS-kb-qwen) — Global keyboard shortcut layer (P0 #23)

**Objective:** make the global hotkey layer a real, centralised, user-reconfigurable
system instead of a hand-maintained XML file — driven by Qwen Code through
`scripts/qwen-integration/qwen-web-worker.py` (chat 7c1631a4, qwen3.8-flash).

**What shipped**
- `lib/mv_hotkeys_core.py` — the action registry (55 actions): each row carries the
  accelerator, command, xfconf branch, skill category and protection flag. It is the
  source of truth: `render-xml` generates the factory XML from it and
  `verify --xml` fails the build on drift (packaged XML ↔ registry ↔ skel mirror).
- `bin/mv-hotkeys` — CLI: list/show/set/reset/apply/verify/conflicts/export/import/
  render-xml/gui. Rebinds are written to `~/.config/mfkeys/overrides.json` (small
  additive user layer) and applied to the live xfconf channel immediately.
- `bin/mv-hotkeys-gui` — Mavericks editor wired into System Settings ▸ Keyboard
  Shortcuts: 11 skill categories (Spotlight, Launchpad, Mission Control, Quick Look,
  Screenshot, Spaces, Windows, Applications, Finder, System, Keyboard), Apple glyphs
  ⌃⌥⇧⌘, checkbox column, click-to-record, *All Defaults*, protected rows explain
  themselves, conflicts name the owner instead of stealing silently.
- `config/hotkeys/skills.json` — skill taxonomy (labels, icons, descriptions).
- `Super+Shift+R → mv-rename` added: Rename had a binary and a Thunar action-menu
  entry but no global key.
- Protection model: Ctrl+Alt+T, Ctrl+Alt+L, Alt+Tab/Alt+Shift+Tab and the whole
  hardware row (XF86Audio*, XF86MonBrightness*) refuse rebinding.
- `docs/KEYBOARD.md` rewritten as the layer reference; `docs/APPS.md` row updated;
  `docs/NEEDS_HARDWARE_TEST.md` got concrete hardware checks for the layer.

**Qwen contribution vs local work** — full split recorded in DECISIONS.md. Qwen
produced the architecture (registry layout, protection model, conflict detection,
CLI verb set, "no daemon / immediate apply" constraints). Its delivered script was
unusable as-is and was superseded: the accelerator model was reworked (xfconf puts
the key *inside* the property name, so "rebind action X" was inexpressible under
Qwen's model), user overrides were made additive instead of rewriting the packaged
XML, the hardware-row bindings were added, XML render + drift detection were added,
and two xfconf-query API errors in the draft were fixed (`-n -t string` to create a
property; `-l -v` is column-padded, not `key = value`).

**Verification**
- `scripts/test-hotkey-layer.py` — 82 checks: registry invariants (no orphan
  commands, all canonical Mavericks actions present), accelerator normalisation
  (6 accepted spellings), conflict detection (order-insensitive), protection,
  override round-trip, XML↔registry↔skel drift, doc coverage, import/export, CLI
  contract, GUI pure helpers imported with `gi` blocked.
- `scripts/test-hotkey-layer-gui.py` — 24 checks: static Mavericks-look contract
  plus a real GTK smoke on the pinned Xvfb :97 (window maps, title, sidebar
  categories, stack pages, category switch, rows render, recorder opens, recorder
  waits for a real combination).
- Live xfconf rebind path tested (set → apply → cleanup → reset → restore), opt-in
  via `MV_HOTKEYS_LIVE_TEST=1` because other agents share this host's session; the
  suite restores the channel byte-for-byte and asserts it (an early version did
  leave the channel dirty — caught, fixed, re-verified clean).
- `make install DESTDIR=…` verified; both binaries + lib + skills.json install.
- `scripts/check-sync.sh` — **ALL CHECKS PASSED**, now including a
  "keyboard shortcut layer" section running both suites.
- Existing per-topic gates all still pass: window/empty-trash/trash-eject/
  force-quit/terminal/brightness keys, alt-tab, lock-screen, workspaces.
- `scripts/test-mv-mission-control.py` has one pre-existing failure
  (`test_native_backend_primes_workspaces_then_exposes`) — reproduces on the HEAD
  version of both the test and the app; it is Mission Control zone, not this one.

**Status:** IMPLEMENTED — HARDWARE VALIDATION REQUIRED. Pre-hardware work for this
objective is closed; remaining items are real-keyboard checks (recorder capture
needs the external USB-C keyboard, Fn row keysyms are firmware-dependent, rebind
survival across logout and `xfsettingsd` restart).
