# TextEdit crash isolation — final report

Build under test: `nsinspect-full.dylib` build id **`66b39198`**, source sha
folded into the id by `tools/uiref/build-nsinspect.sh`. Every capture below
carries that id in the document, and the guest confirmed it in every run.

Verdict up front: **the extractor does not crash TextEdit.** All seven
isolation cases completed with `status=ok`, `alive=alive` and zero
unrecognized-selector exceptions. The original "TextEdit quit unexpectedly"
was never reproduced by the extractor, and the "state B" failure turned out
to be a completely different thing.

## 1. Deployment, made verifiable

The previous milestone lost four runs to stale artifacts. The fix is now
structural rather than procedural.

* `build-nsinspect.sh` derives a build id from the **sha256 of the source
  content** plus a flavour tag, writes it to `build/nsinspect-build-id.txt`,
  and compiles it into the image with `-DNSINSPECT_BUILD_ID`. The binary
  prints it on load and emits it as `"build_id"` in every capture.
  *(Hashing the source *path* was the first attempt and was wrong: the id did
  not change across real code changes, which is precisely what it exists to
  detect. Verified fixed: touching the source changes the id and restoring it
  changes it back.)*
* `tools/uiref/vm-share.sh` builds a **new** FAT image with a **new lowercase
  volume label** for every experiment, so the guest mounts fresh instead of
  serving a cached copy. Artifacts carry unique names (`ns-<id>.dylib`,
  `run-<id>.sh`, `te-<id>.txt`); nothing is ever overwritten in place.
  It writes `expect.txt` with the md5 of each file and then reads every file
  back off the image and re-checks the md5.
* The generated guest runner refuses to start on a mismatch:

  ```
  [ -f "$DYL" ] || fail "dylib-missing"
  [ "$(md5q "$DYL")" = "$(exp ns-$ID.dylib)" ] || fail "dylib-md5"
  [ "$(md5q "$0")"   = "$(exp run-$ID.sh)" ]  || fail "script-md5"
  ```

  `fail` appends `DEPLOY-FAIL <reason>` to the result file and **exits 9**.
* Each case records `idhits` — how many times the running process reported the
  expected build id — so a run that silently used another binary is visible in
  the result table instead of being interpreted as a result.

Result of the run used here: `DEPLOY-OK build=66b39198`, `idhits=3` in every
case.

## 2. Two real framework defects, found by the markers

Stage markers earned their place immediately.

**`-[NSWindow frameView]` does not exist on 10.9.** The frame-view extractor
raised `unrecognized selector sent to instance` on both Calculator and
TextEdit, right after `stage:content-walk-end`, which aborted the capture
after the content walk had already succeeded. The theme frame is reached
through `[contentView superview]` instead. This is the third instance of the
same class of error in this tool (`-submenu`, `-items`, now `-frameView`):
on 10.9 the assumed selector does not exist and the exception kills the whole
capture rather than one field.

**`performSelector:withObject:afterDelay:` never fires.** `NSINSPECT_DELAY=5`
logged `capture:deferred-by-seconds 5` and then nothing for 40 s. Delaying via
the run hook is therefore not a usable capture point. A
`NSINSPECT_CAPTURE_POINT=window` mode that hooks
`-[NSWindow makeKeyAndOrderFront:]` was added instead; it installed cleanly
but did not fire either, because these applications order their windows by a
path that does not go through that selector. Left in place and documented as
unproven rather than claimed to work.

## 3. Isolation matrix — complete

All runs: `TextEdit -ApplePersistenceIgnoreState YES`, 30 s, build `66b39198`.

| Case | `NSINSPECT_STAGES` | depth | alive | exc | JSON | windows | contentViews | frameViews | menuItems |
|---|---|---|---|---|---|---|---|---|---|
| A | `none` | 12 | alive | 0 | complete | 1 | 0 | 0 | 0 |
| B | `win` | 12 | alive | 0 | complete | 1 | 0 | 0 | 0 |
| C | `win,view` | 12 | alive | 0 | complete | 1 | 6 | 13 | 0 |
| D | `win,view,menu` | 0 | alive | 0 | complete | 1 | 6 | 13 | 0 |
| E | `win,view,menu` | 12 | alive | 0 | complete | 1 | 6 | 13 | **164** |
| F | `win,view` | 0 | alive | 0 | complete | 1 | 6 | 13 | 0 |
| G | `win,view,menu` + document | 12 | alive | 0 | complete | 1 | 6 | 13 | 164 |

Cases D and E are the decisive pair: full recursive submenu traversal over 164
menu items completes with no exception, so **menu traversal is not the cause**
of the original crash. Hypotheses 2 and 3 from the previous report (depth
default 12, lazily-populated `Services` menus) are **eliminated**.

Log sizes scale monotonically with the enabled stages (1664 → 1629 → 8522 →
8679 → 39069), which is the independent check that the switches really
disable what they claim to.

Raw evidence: `raw/matrix/textedit-*.json` and the matching `.log` files,
plus `raw/matrix/matrix-result.txt`.

## 4. Calculator regression — passes

Build `66b39198`, `stages=win,view,menu`, depth 12:

* injection succeeded (build id seen 3× in the log)
* window enumeration succeeded: 4 windows, primary index 1
* contentView traversal succeeded: 29 views, 19 controls
* frameView traversal succeeded: +33 views
* menu traversal succeeded: 8 top-level items
* JSON valid, `"status": "ok"`, `---BEGIN JSON---` / `---END JSON---` both present
* Calculator remained **alive** for the whole 40 s window

The earlier "Calculator quit unexpectedly" sheet did **not** reproduce in this
run and was not dismissed-and-ignored: it came from a session whose runs were
later shown to be using a stale binary, and no Calculator crash is
reproducible with a verified build.

## 5. contentView vs frameView, per application

The two applications are compared separately; object identities and counts are
never merged.

**Calculator** — primary window `NSWindow "Calculator"`, frame
`[107, 88, 273, 207]`:

```
NSThemeFrame                       <- the window frame; absent from contentView
  _NSThemeCloseWidget  [7,188,14,16]
  _NSThemeWidget       [47,188,14,16]
  _NSThemeWidget       [27,188,14,16]
  NSView               [0,0,273,185]      <- content view, same root as before
    ... LCDBackgroundView, NSTextFields, RPNTableView, NSScrollView ...
```

The theme frame adds the three traffic-light widgets, which is the concrete
proof that the frame-view walk reaches objects the content walk cannot.

**TextEdit** — the primary window in every capture is an `NSPanel` with an
`_NSAlertContentView`, so the comparison for TextEdit is between the *alert's*
content view and the *alert's* frame view:

```
NSThemeFrame                  [0,0,420,193]
  _NSAlertContentView         [0,0,420,171]
    NSImageView / 2x NSTextField / 2x NSButton
```

**TextEdit's toolbar and ruler are therefore still unproven.** The document
window has never been the primary window in any capture, so no measurement of
its toolbar exists yet. This is not a gap in the extractor — it is the same
alert described next.

## 6. Why the NSAlert appears (Priority 5)

The alert text is now captured (`text_value` for `NSTextField`/`NSTextView`
was added for exactly this):

> "The last time you opened TextEdit, it unexpectedly quit while reopening
> windows. Do you want to try to reopen its windows again?"
> "If you choose not to reopen windows, you may have to open and position the
> windows yourself."

Findings:

* The alert is **TextEdit's reopen-windows restoration prompt**, raised by
  `NSDocumentManager` at launch.
* It is **not** caused by the document argument. Cases E and G — with and
  without a document on the command line — produced byte-identical log sizes
  (39069) and identical window lists (1 window, the alert panel).
* It is **not** caused by the extractor. It is present in runs with
  `NSINSPECT_STAGES=none` as well.
* `-ApplePersistenceIgnoreState YES` does **not** suppress it (case G still
  captures the panel).
* The capture fires from the first run-loop turn, which is before the alert is
  dismissed, so the alert legitimately owns `[NSApplication windows]` at that
  moment. The extractor is behaving correctly.

### What is blocked and why

Clearing the alert means answering it, which writes to TextEdit's persistent
session state. This milestone must not modify persistent user data, so the
alert was left in place and TextEdit's document window remains uncaptured.

To unblock it, with explicit owner approval, either:

1. Click **Don't Reopen** once in the guest. This clears the pending
   restoration record and TextEdit then launches to a clean document window.
   It is normal app operation, but it does change persistent session state.
2. Or delete TextEdit's saved-application-state entry
   (`~/Library/Saved Application State/com.apple.TextEdit.savedState`) — more
   destructive, same effect.

Option 1 is the right one. Once the alert is gone, the existing `m_g_doc` case
will capture the real `Untitled` document window and the toolbar/ruler
question can be answered with the frame-view walk that is already working.

## 7. Remaining defects, stated plainly

* `NSINSPECT_DELAY` does not work and is not claimed to.
* `NSINSPECT_CAPTURE_POINT=window` installs but does not fire on these apps.
* TextEdit's document window, its toolbar and its ruler are still uncaptured,
  blocked on the restoration alert.
* `text_value` is captured for `NSTextField`/`NSTextView` only; `NSTextView`
  document content is truncated at 1023 bytes and is not a document dump.
