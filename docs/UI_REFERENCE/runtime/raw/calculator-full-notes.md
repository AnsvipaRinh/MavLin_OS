# Calculator — full runtime capture (repeatable)

Two consecutive runs inside the real Mavericks guest, both captured from the
live Calculator process by injecting `nsinspect-full.dylib` through
`DYLD_INSERT_LIBRARIES`. Files: `calculator-full-run-a.json`, `-b.json`.

## What is in the documents

| | run A | run B |
|---|---|---|
| pid | 961 | 974 |
| NSWindow instances | 4 | 4 |
| primary window | index 0, `NSWindow` "Calculator" | index 0, same |
| NSViews visited | 29 | 29 |
| NSControls found | 19 | 19 |

All four windows are preserved, including the auxiliary ones, each with its own
independently collected facts:

| class | title | visible | level | frame |
|---|---|---|---|---|
| `NSWindow` | `Calculator` | false | 0 | `[107, 88, 273, 207]` |
| `CustomWindow` | `Window` | false | 25 | `[10000, 10000, 1, 1]` |
| `NSWindow` | `Paper Tape` | false | 0 | `[345, 88, 228, 292]` |
| `NSPanel` | (empty) | true | 0 | `[430, 392, 420, 193]` |

The `CustomWindow` at level 25 parked at `10000,10000` is a genuine off-screen
utility panel, not a decoding artefact: it was recorded the same way before the
geometry path changed.

## Geometry

All geometry comes from `NSInvocation`
(`-methodSignatureForSelector:` → `-invocationWithMethodSignature:` →
`-invoke` → `-getReturnValue:`), never through a hand-cast `objc_msgSend`.
Every window field records `"frame_source": "NSInvocation"` so the provenance
is explicit.

Values are self-consistent: the primary window frame `[107, 88, 273, 207]`
contains its content view frame `[0, 0, 273, 185]`, and the display box
`[0, 0, 257, 56]` sits inside its parent at `[9, 129, 257, 56]`.

## Recursive hierarchy (abridged, from the primary window's content view)

```
NSView                  frame=[0, 0, 273, 185]
  NSView                frame=[214, 57, 52, 128]
    NSButton            frame=[1, 64, 49, 30]  cell=NSButtonCell  target=LCDController/rpnRollDown:
    NSButton            frame=[1, 96, 49, 30]  cell=NSButtonCell  target=LCDController/rpnExchange:
    NSButton            frame=[1, 0, 49, 30]   cell=NSButtonCell  target=LCDController/rpnDrop:
    NSButton            frame=[1, 32, 49, 30]  cell=NSButtonCell  target=LCDController/rpnRollUp:
  NSView                frame=[9, 129, 257, 56]
    NSBox               frame=[0, 0, 257, 56]
      NSView            frame=[0, 0, 257, 56]
        LCDBackgroundView  frame=[3, 3, 250, 50]
        NSTextField     frame=[10, 33, 217, 18]  cell=NSTextFieldCell
        NSTextField     frame=[161, 8, 30, 15]   cell=NSTextFieldCell
```

`LCDBackgroundView` is an application-defined class, obtained from the live
object graph, not from any nib. Target/action pairs such as
`LCDController`/`rpnRollDown:` are read from the real control objects.

## Repeatability

* identical NSView hierarchy class sequence in both runs;
* identical view and control counts (29 / 19);
* identical primary window and identical window class ordering;
* Calculator remained alive in every run; no hangs, no crashes.

One difference was observed and is recorded rather than smoothed over: the
per-window *set* comparison differed between the two runs while the class
ordering, the hierarchy and all counts matched, i.e. at least one window's
recorded facts moved between captures. That is expected for windows AppKit
manages dynamically and is left visible in the raw data.

## Primary-window selection

Selection uses structural signals only — real `NSWindow` class, window level 0,
a non-empty title, and an on-screen, non-degenerate frame. `isMainWindow`,
`isKeyWindow` and `isVisible` are **recorded** per window but deliberately not
used for the decision: the capture runs from inside `-[NSApplication run]`,
before the application can become active, so those flags were false in one run
and true in another and made repeated captures disagree. The document states
this in `primary_selection_note`.

Distinguishing Calculator's main window from its `Paper Tape` window needs
application-level knowledge; both are real windows and both are preserved, so
that judgement belongs in the normalized layer, not in the raw capture.

## Limits of this evidence

* Single application (Calculator), two runs, under TCG emulation.
* Geometry is in screen coordinates as reported by AppKit at capture time.
* Text-bearing controls record their class and cell, not their rendered text.
* This is native AppKit evidence. It is not an accessibility tree and not a
  nib; those remain separate sources.
