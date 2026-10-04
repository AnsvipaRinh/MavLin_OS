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
| packages/mavericks-apps/src/mavericks-apps/bin/mv-mail | qwen-agent | CLAIMED | 2026-10-05 | Fix real bugs: missing `import subprocess` before use (top-level re-import after class), double `Gtk.Paned` creation (first one added to window stays empty), dead sidebar code; add tests |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-rename | qwen-agent | CLAIMED | 2026-10-05 | Add headless test coverage (pure logic + GUI smoke); review Finder semantics (extension-aware selection) |
| scripts/test-mv-finder-columns.py (+test harness pattern for new app tests) | qwen-agent | CLAIMED | 2026-10-05 | Reuse its SourceFileLoader/portable pattern for mv-rename/mv-eject tests |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-eject | qwen-agent | CLAIMED | 2026-10-05 | Bug: async unmount with no main loop → process exits before unmount runs (fire-and-forget callback does nothing). Fix to sync-with-op or run loop; add mock-Gio tests |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-about | qwen-agent | CLAIMED | 2026-10-05 | Extract pure collectors (mem_total/cpu_model/gpu/CATEGORIES) behind lazy Gtk import so they are testable headless; add tests |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-settings | qwen-agent | CLAIMED | 2026-10-05 | Same refactor: PAGES table + search-filter logic testable without display; verify icon names exist in our icon theme |

## Known open targets (NOT claimed yet — free to take)

- Unported binaries without any test coverage: mv-close-window, mv-minimize-window,
  mv-newfolder, mv-quit-app, mv-hide-app, mv-openwith, mv-getinfo, mv-quicklook-thunar,
  mv-notify-send, mv-hud.c, mv-spotlight-preview, mv-power-ui (has test), mv-ytplayer (has test)
- lab/harness/backends/qemu_backend.py — 9p virtfs ENODEV blocks 18/25 scenarios
  (documented in PROGRESS.md; fix would unblock QEMU command-channel)
- README.md screenshot section — desktop/Finder/Spotlight captures pending HW boot
- docs/PROGRESS.md "Track 6/7" row still has `[ ] Commit: theme fix + docs` unchecked
- check-sync.sh — could run all scripts/test-mv-*.py suites, not just firefox-chrome
