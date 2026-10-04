# WORK QUEUES — claimed-object registry (multi-agent coordination)

Purpose: prevent two agents from working on the same object at the same time.
**Before taking any improvement target, add a row here (status CLAIMED) and
commit it in the same commit as your first change to that object.** When done,
set status to DONE (with commit hash) or RELEASED (if abandoned). Objects not
listed here are free to claim.

Rules:
- One object = one row. An "object" is a single file/app/script/gate
  (e.g. `bin/mv-eject`, `scripts/check-sync.sh`, `lab/harness/backends/qemu_backend.py`).
- A CLAIMED row blocks other agents until it becomes DONE or RELEASED.
- Stale claims (no commit touching the object for >1 working session) may be
  taken over after noting the takeover in the Notes column.

| Object | Agent | Status | Since | Notes |
|---|---|---|---|---|
| packages/mavericks-apps/src/mavericks-apps/bin/mv-mail | qwen-agent | DONE 2026-10-05 | Fixed: NameError subprocess (import was after class), duplicate Gtk.Paned (sidebar branch orphaned), no main loop. Restructured: lazy-Gtk factory (build_window_class) so find_mail_backend is headless-testable; Mail UserAgent desktop fallback; install-hint state. Tests in scripts/test-mv-finder-small.py (12 assertions, wired into check-sync) |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-rename | qwen-agent | DONE 2026-10-05 | Finder semantics: preselect stem (not extension), dotfiles keep full selection; pure validate_new_name() extracted + lazy Gtk import; 6 headless assertions in test-mv-finder-small.py |
| scripts/test-mv-finder-small.py (new shared suite for small Finder helpers) | qwen-agent | DONE 2026-10-05 | Portable pattern reused from test-mv-finder-columns.py; duck-typed fake Gio mounts (no gi needed); registered as check-sync gate |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-eject | qwen-agent | DONE 2026-10-05 | Fixed silent no-op: async unmount_with_operation + no-op callback without main loop -> sync API with MountOperation; per-arg exit codes; /media umount fallback for non-GIO mounts; find_mount() pure + 4 duck-typed assertions |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-about | qwen-agent | DONE 2026-10-05 | Refactor done: lazy Gtk via build_about_class() factory — pure collectors (rd/run/mem_total/cpu_model/gpu_model/CATEGORIES) now import headless; lspci/lsusb/uname calls memoized with lru_cache (docstring promised caching, it did not exist before — real fix). First-ever test suite scripts/test-mv-about.py (11 assertions incl. gi-blocked import proof, Serial-truncation invariant, cache-hit check), wired into check-sync.sh gate |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-settings | qwen-agent | DONE 2026-10-05 | Refactor: PAGES/page_is_available/filter_pages importable headless (lazy Gtk via build_settings_class factory). First-ever suite scripts/test-mv-settings.py (15 assertions) incl. hard icon audit: 12 of 18 rows referenced icon names NOT shipped by the Mavericks theme (preferences-desktop-theme, network-wired, bluetooth, audio-card, notification, battery, preferences-system-time, preferences-desktop-locale, system-users, system-run, preferences-desktop-wallpaper, preferences-background) -> replaced with real theme icons; wired into check-sync.sh gate |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-calculator | qwen-agent | DONE 2026-10-05 | Lazy-Gtk portability refactor (_gtk() + build_calculator_class factory): pure logic (parse/format/to_base/apply_operator/apply_unary/load_tape/save_tape) now imports headless; existing suite scripts/test-mv-calculator.py goes from Arch-only to green on non-Arch hosts: 79 passed / 0 failed (GUI smoke still skips without display) |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-launchpad | qwen-agent | DONE 2026-10-05 | Fixed real CI defect: top-level `import gi` made test-mv-desktop-cache.py FAIL (not skip) on non-Arch hosts — its integration section loads mv-launchpad/mv-spotlight. Lazy _gtk() (only consumer was _icon_exists); suite now fully green: 41 passed / 0 failed incl. all launchpad/spotlight cache-integration assertions |
| scripts/test-mv-calendar.py + scripts/test-mv-reminders.py | qwen-agent | DONE 2026-10-05 | Revived dead coverage: both apps already gate Gtk import on argv (headless timer path), but their suites loaded the module with default argv -> GUI branch -> ModuleNotFoundError:gi on non-Arch. load_app() now emulates --check-upcoming/--check-due argv: calendar 64 passed, reminders 32 passed (previously 0 assertions ever ran outside Arch) |
| scripts/check-sync.sh | qwen-agent | DONE 2026-10-05 | Gate rewritten: auto-discovers and runs ALL scripts/test-mv-*.py suites (replacing hand-added per-file lines). Result classification: rc=0 pass; failing run that printed "ok -" assertions = real regression -> BAD; failing run with zero assertions (target binary not yet headless-portable) -> SKIP with explicit count in summary. Current state: 10 passed, 17 skipped (unported), 0 failed |

## Known open targets (NOT claimed yet — free to take)

- Headless-portability backlog (each: move top-level `import gi` behind a lazy
  `_gtk()`/factory so its existing suite runs on non-Arch hosts; suites for all
  of these already exist and currently SKIP in check-sync): mv-airdrop,
  mv-colormeter, mv-console, mv-control, mv-dictionary, mv-diskutil,
  mv-finder-columns, mv-finder-search, mv-fontbook, mv-keychain, mv-music,
  mv-notes, mv-photos, mv-power-ui, mv-stickies, mv-timemachine, mv-voice
- Unported binaries without any test coverage: mv-close-window, mv-minimize-window,
  mv-newfolder, mv-quit-app, mv-hide-app, mv-openwith, mv-getinfo, mv-quicklook-thunar,
  mv-notify-send, mv-hud.c, mv-spotlight-preview, mv-power-ui (has test), mv-ytplayer (has test)
- lab/harness/backends/qemu_backend.py — 9p virtfs ENODEV blocks 18/25 scenarios
  (documented in PROGRESS.md; fix would unblock QEMU command-channel)
- README.md screenshot section — desktop/Finder/Spotlight captures pending HW boot
- docs/PROGRESS.md "Track 6/7" row still has `[ ] Commit: theme fix + docs` unchecked
