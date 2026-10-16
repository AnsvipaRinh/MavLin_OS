# TextEdit document-window runtime extraction — report

Build under test: `nsinspect-full.dylib` build id **`8a904458`**
(content-sha-derived, see `build/nsinspect-build-id.txt`).
Guest: OS X 10.9 (13A603), TextEdit 1.9 (310). All runs use the verified
deployment procedure (fresh FAT image per experiment, immutable artifact
names, guest-side md5 check against `expect.txt`, non-zero abort on mismatch,
build-id sightings recorded per run).

## Verdict

**The TextEdit document window is captured at runtime.** Three required
states — blank, disposable text document, blank repeat — each produced a
complete, valid capture (`status=ok`, `---BEGIN/END JSON---` present) with
the real `NSWindow`, its content tree, its theme-frame tree including the
formatting toolbar, menus and controls. Blank and blank-repeat are
structurally identical (content tree, frame tree); only object addresses
and menu item states differ, as expected between processes.

Raw evidence: `raw/textedit-doc/textedit-doc-{blank,with-text,blank-repeat}.{json,log}`,
`raw/textedit-doc/doc-capture-result.txt`,
Calculator regression in `raw/textedit-doc/calculator-regression.{json,log}`,
result table in `raw/textedit-doc/calc-regression-result.txt`.

## What each capture contains

Blank (`Untitled`, frame `[133, 208, 550, 468]`) and blank-repeat
(byte-identical structure): 2 windows, 8 content views, 2 content controls,
32 frame views total, 7 top-level menu items.

- Content: `NSView` -> `NSKVONotifying_ScalingScrollView` -> `NSClipView`
  -> 2× `_NSClipViewOverhangView` + `NSKVONotifying_NSTextView`, plus two
  scrollers. This answers the old "why only 8 views" question definitively:
  the content tree genuinely has 8 views; the toolbar was never in it.
- Frame: `NSThemeFrame` + 3 traffic-light widgets
  (`_NSThemeCloseWidget`, 2× `_NSThemeWidget`),
  `NSKVONotifying_NSThemeAutosaveButton`, and **`__NSInspectorBarView`**
  `[0, 420, 550, 26]` with `NSPopUpButton` (style, font, typeface),
  `NSTexturedComboBox` (size, reads `12`), 2× `NSPopoverColorWell`,
  2× `NSSegmentedControl`, 2 more popups. The formatting toolbar lives in
  the theme frame, exactly as hypothesised.
- No `NSRulerView` is present in any capture. The ruler seen in screenshots
  belongs to a different TextEdit state (ruler enabled); in the captured
  state it is not instantiated. Screenshot-only, not runtime-proven.

With-text (`te.txt`, frame `[133, 264, 640, 412]`): 1 window, 8 content
views. The `NSKVONotifying_NSTextView` carries the document text
(`text_value`: the two sample lines). The frame adds
`NSThemeDocumentButton` (proxy icon — only present with a real file) and
has NO inspector bar: the `.txt` opened in plain-text mode. The tool
faithfully records the behavioural difference instead of inventing a
toolbar.

## Defects found and fixed in this milestone

1. **Segfault on empty window list (root cause, proven by crash log).**
   `TextEdit_2026-10-15-145205` crash: `EXC_BAD_ACCESS (SIGSEGV)`,
   `EXC_I386_GPFLT`, `objc_msgSend() selector name: contentView`,
   receiver `0x636570736e69736e` = ASCII `"nsinspect"`. The `wlist[256]`
   array was uninitialised stack memory; with zero windows the primary
   index fell through to slot 0 and `-contentView` went to whatever bytes
   sat there — our own string literal. Fix: zero-initialised array plus an
   explicit empty-list guard that emits null views. Raw crash report kept
   as `raw/textedit-doc/TextEdit-segv-contentView.crash`. No crash has
   recurred in any later run (5 captures since the fix, 0 exceptions,
   0 segfaults).
2. **In-hook enumeration is unsafe; post-only forwarding is safe.**
   Querying `sharedApplication`/`windows` from inside an `-orderFront:`
   hook killed the process silently every time. The hook now only forwards
   to the main thread; all enumeration runs in the run-loop context.
3. **Late-capture mechanisms that do not work here, documented not claimed:**
   `performSelector:withObject:afterDelay:` never fires (modal alert loop
   runs no default-mode timers); a detached-thread replacement deadlocks
   (thread creation is unsafe in this environment, constructor or not, so
   `NSINSPECT_DELAY` was removed); counting `nextEvent` turns stalls
   forever (an idle app blocks inside a single `nextEvent` call, so turns
   only advance on user events). The working mechanism is window-show
   hooks (`orderFront:`, `makeKeyAndOrderFront:`, `orderFrontRegardless`,
   `makeKeyWindow`, `makeMainWindow`) that forward to the main thread.
   `makeKeyAndOrderFront:` alone never fired; the broadened set does.
4. **SIGTERM poisoning.** Killing TextEdit with SIGTERM marks it
   "unexpectedly quit" and the next launch raises the restoration alert,
   which then owns the window list. All runner scripts now quit via
   AppleScript (`tell application ... to quit`, verified clean: process
   gone, no flag set) and use SIGTERM only as a fallback that is recorded
   per run (`quit=cleanquit|killfallback`).
5. **Sandboxed file arguments.** A document passed as a CLI path outside
   TextEdit's sandbox reads as "You don't have permission" (verified alert
   text; file mode/ACLs/xattrs all clean). The working path is the app's
   own container:
   `~/Library/Containers/com.apple.TextEdit/Data/Documents/te.txt`.
   Placing the disposable test document there is test-input setup, not a
   preferences/saved-state change.

## Incidental corrections to earlier claims

- The "virtual keyboard corrupts shifted characters" claim is narrowed:
  double quotes type correctly (verified `echo "QWERTY"`); only `_` (and
  `~`, `$` via shift-drop) are unreliable. Underscore-free commands are
  still the rule, but quoted AppleScript is usable.
- QEMU HMP `sendkey` accepts NO Command modifier (`meta`, `command`,
  `super` all return `invalid parameter`), so keyboard app-switching is
  impossible here; the calibrated `mvclick.py` (not raw tablet coords) is
  the correct click path.
- The earlier "Calculator quit unexpectedly" sheet traces to sessions later
  shown to run a stale binary; with verified builds Calculator shows no
  crash. Calculator regression with `8a904458`: `status=ok`, 4 windows,
  content+frame+menu captured, process alive (primary index landed on
  Paper Tape instead of Calculator this run — the known primary-heuristic
  tie, data complete either way; plus one untitled `NSPanel` noted as an
  open item, not investigated).

## Remaining gaps (honest)

- `NSRulerView` runtime hierarchy: unmeasured (ruler not enabled in the
  captured state).
- The `.json` sidecar file is never written in the guest (`fopen` returns
  NULL under injection — pre-existing); the stderr mirror is the evidence
  channel and is complete in every run.
- `NSINSPECT_CAPTURE_POINT=window` installs but the pre-existing
  `makeKeyAndOrderFront:`-only mode never fired; superseded, kept for
  compatibility.
- Menu trees differ between runs beyond addresses (states); not analysed.
