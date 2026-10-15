# TextEdit crash isolation — findings

Status: **partially delivered.** The feature switches, stage markers and the
frame-view traversal are implemented, built and contract-tested. The test
matrix is **not** complete; three guest-side defects prevented it. All of
them are recorded below with the evidence, because each one silently
invalidated an earlier "result" and the same class of error would invalidate
the next one too.

## Implemented in this milestone

`tools/uiref/nsinspect.c` (builds clean, `tests/uiref/test_nsinspect.py` passes):

| Switch | Meaning |
|---|---|
| `NSINSPECT_STAGES` | comma list of `win`, `view`, `menu`. Unset = all three. Set to anything else (e.g. `none`) = inject the library and extract nothing. |
| `NSINSPECT_MENU_MAXDEPTH` | submenu recursion budget; `0` emits the menu bar items with no submenus. |

Both are read with `getenv` **at capture time**, never in the constructor.

Stage markers are written to fd 2 unbuffered and bracket: runtime resolve,
app lookup, window count, window list, menu walk begin/end, content walk
begin/end, frame-view walk begin/end, serialization begin/end. Menu traversal
additionally emits `menu-descend` (with class and depth), `menu-descend-items`
(with item count) and one `menu-item` line per item actually read, so the last
marker before a fault names the operation that caused it.

The capture document gained `"stages"` (the resolved switch values),
`"primary_frame_view"` with `"frame_view_views"` / `"frame_view_controls`,
and `"frame_view_total_views"`. `views_visited` and `controls_found` keep
their old meaning — the content tree only — so existing captures stay
comparable.

## Defect 1: the matrix ran against a stale library

The runner used `~/ns/nsinspect-full.dylib`. The freshly built dylib was only
written to the share, and the script never installed it. Every case therefore
ran the *previous* build: all six logs were byte-identical at 25809 bytes and
contained no stage markers at all, which is the signature of "the switch does
not exist in this binary", not of "the switch has no effect".

The script now starts with `cp $OUT/ns.dylib $NS` and fails loudly if that
copy does not work.

## Defect 2: `mcopy` does not overwrite without `-o`

`mcopy -i img file ::run.sh` fails silently when `run.sh` already exists.
Two updated copies of the runner script therefore never reached the share,
and two further matrix runs executed the *old* script. Visible signature: the
new script's `log=`/`json=` line format never appeared in `matrix.txt`.

Every later `mcopy` in this workstream must pass `-o`.

## Defect 3: the guest keeps serving a cached FAT copy

After a successful host-side overwrite (`run.sh` verified as 1838 bytes on the
image), the guest still executed the 1481-byte previous script. macOS 10.9's
VFAT driver caches file contents, and a host-side overwrite does not
invalidate that cache. Re-plugging the USB image via QMP was attempted to
force a fresh mount; the `blockdev-add` never completed, so the matrix was
re-run against the cached script for a fourth time.

Reliable procedure for the next attempt, in order:

1. Host: `mcopy -o` the script and the dylib, then verify with `mdir` and
   compare sizes and `md5sum`.
2. Hot-unplug the share (`device_del`), wait for the guest to show the
   "Disk Not Ejected Properly" notification, then `device_add` it again so
   the guest re-mounts and re-reads the directory.
3. In the guest, confirm the script is the new one before trusting the run —
   e.g. `grep -c 'log=' /volumes/mvns/run.sh` must print a non-zero count.
   Only then start the matrix.
4. Dismiss every crash-reporter sheet first. A leftover "X quit
   unexpectedly" sheet takes keyboard focus and swallows the typed command,
   which already cost one run.

## What the stale-binary run did prove (accidentally, but it is real)

The single valid run that did happen captured, for **every** case including
the document case, a complete document with `"status": "ok"` and a closing
`---END JSON---`. Nothing crashed during the capture.

It also revealed why "state B" looked broken. With a document argument, at
the instant the capture runs the only window in `[NSApplication windows]` is
an `NSPanel` whose content view is `_NSAlertContentView` with `target
NSAlert`, `action buttonPressed:` — TextEdit is showing an **alert**, and the
capture was faithfully recording the alert rather than the document window.
The earlier "TextEdit quit unexpectedly" sheet was that alert.

So "state B produced no usable capture" was never a crash of the extractor.
The extractor worked; it captured the wrong window because an alert owned the
window list at that moment. Reproducing that needs the alert's text, which
this capture shape does not record.

## Remaining possibilities for the original crash

Not yet distinguished, listed in the order the next run should test them:

1. The alert itself. TextEdit opening a document from `~/te.txt` on a FAT
   share may raise a format/encoding alert; the crash reporter sheet that
   followed could be a consequence of the app being killed while that alert
   was up, not an extractor fault.
2. `NSINSPECT_MENU_MAXDEPTH` unset in the old script meant the default 12.
   Unbounded submenu recursion over `Services` menus, which are built
   lazily from loaded bundles, is the most plausible extractor-side fault and
   is exactly what case `d1` (depth 0) is designed to separate from `e1`.
3. `Services` menus specifically. They are populated by the system and can
   change while being read, which a recursive walk does not guard against.

## Why the TextEdit capture has only 8 views

The 8 views are the complete content tree and nothing filtered it out:
`depth_max` is 32 and `view_cap` is 4000, and the walk reported 8 distinct
objects with 0 duplicate visits.

```
NSView (content)
└── NSKVONotifying_ScalingScrollView
    └── NSClipView
        ├── _NSClipViewOverhangView
        ├── _NSClipViewOverhangView
        └── NSKVONotifying_NSTextView
NSKVONotifying_NSScroller
NSScroller
```

The toolbar with font controls and the ruler visible in
`textedit-crash-screen.ppm` are **not in the content view hierarchy** on
10.9: they are drawn into the window's theme frame. A content-view walk
cannot see them at any depth. This milestone adds `primary_frame_view`,
walked from `-[NSWindow frameView]` with an independent visit set, which is
the measurement that settles it. It has been built and contract-tested but
**no guest run of it has completed yet**, so the frame-view counts are still
unknown.

## Input reliability (requirement 4)

The corruption seen earlier was **not** the virtual keyboard. Two independent
causes were identified and both are now avoided:

* `_` really does arrive as `-` for typed text (`DYLD-INSERT-LIBRARIES` in a
  failed log), so no environment variable is ever typed.
* The "NSINSPECT not found" error was `mcopy` (Defect 2), not the keyboard.

The matrix is driven entirely by a script on the share; the only typed
characters are `sh /volumes/mvns/run.sh`, all lowercase, no shifted keys.

## Regression status

`tests/uiref/test_nsinspect.py` and `python3 tools/lint-tests.py` pass
(0 errors). The Calculator runtime capture has **not** been re-run against
this build — the earlier "Calculator quit unexpectedly" sheet on screen
predates this milestone and its cause was not investigated. This is an open
item, not a passed check.
