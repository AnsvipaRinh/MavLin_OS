# Claim: opencode-ui-runtime-guest

agent: opencode
task: TextEdit runtime capture (state A complete, state B open) Runtime AppKit extraction from the Mavericks guest — Calculator (done) and TextEdit
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
