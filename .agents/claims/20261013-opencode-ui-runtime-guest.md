# Claim: opencode-ui-runtime-guest

agent: opencode
task: TextEdit document-window extraction COMPLETE (blank/text/blank-repeat captured, Calculator regression pass, segfault root-caused and fixed)
paths: tools/uiref/**, tests/uiref/**, docs/UI_REFERENCE/**, .agents/claims/20261013-opencode-ui-runtime-guest.md
expires: 2026-10-15T20:00Z
started: 2026-10-13
note: >
  Working pipeline: nsinspect-full.dylib injected via DYLD_INSERT_LIBRARIES,
  capture on the main thread from a -[NSApplication run] swizzle, geometry via
  NSInvocation. No worker thread, no dlsym in the constructor — both deadlock or
  crash on 10.9. Guest disk, OpenCore image and TCC.db are untouched; the guest
  was restored only from the verified backup mavericks-hdd.raw.backup-2026-10-15.

- 2026-10-15: TextEdit state A captured (2 windows, 8 views, 166 menu items); state B (document argument) still hangs in traversal and is recorded as an open gap.
- 2026-10-15: isolation machinery landed (NSINSPECT_STAGES, NSINSPECT_MENU_MAXDEPTH, fd-2 stage markers, primary_frame_view). Matrix run blocked by three documented guest-side defects; findings and the exact rerun procedure are in docs/UI_REFERENCE/runtime/raw/textedit-crash-isolation.md.
- 2026-10-15: build-identity + verified deployment landed (sha256-derived build id, md5-checked immutable VFAT artifacts, non-zero deploy failure). Full 7-case matrix passes, menu traversal eliminated as crash cause, NSThemeFrame/traffic lights captured via frameView. TextEdit document window blocked by its reopen-windows alert; clearing it would modify persistent session state.
- 2026-10-16: document-window milestone delivered with build 8a904458 (window-show hooks, empty-list segfault guard, AppleScript clean quits, sandbox-container doc path). Host reboot survived: QEMU relaunched via run-installed.sh, harness rebuilt on persistent paths (vmwork/mvvm.py + mvclick.py + vmwork/opencode/qmp.py), no /tmp dependencies remain. Evidence in docs/UI_REFERENCE/runtime/raw/textedit-doc/.
