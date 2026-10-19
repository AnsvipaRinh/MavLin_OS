# MavLinOS platform model — application-to-screen execution paths

**Status:** implementation-grade reference.  
**Sources:** AppKit selector+IMP index (Ghidra, 33719 methods), CoreGraphics CGS
symbol surface (287 imported by AppKit), existing TextEdit/Calculator/System
Preferences decompilations and NIB analyses. Evidence:
`vmwork/opencode/frameworks/index/`, `docs/UI_REFERENCE/native-findings.md`.

**Conventions:** `─▶` = a real call recovered from a decompiled method body or an
imported-symbol dependency. **[BIN]** / **[NIB]** / **[RT]** / **[INFERRED]**
as before. `mv.*` names are project abstractions, never Apple APIs.

---

## Path A — Application startup: launch → NSApplicationMain → run loop

**[BIN]** `-[NSApplication run]` (IMP 0x177a3), `-[NSApplication
sendEvent:]` (IMP 0x1c6f5f), `-[NSApplication
nextEventMatchingMask:untilDate:inMode:dequeue:]` (IMP 0x23861),
`+[NSApplication sharedApplication]`, `_NSApplicationMain` (defined symbol),
`-[NSApplication finishLaunching]` (selector present).

```
launchd / user double-click
   │
   ▼
main()  ─▶  NSApplicationMain(argc, argv)        [AppKit defined symbol]
            │
            ├─▶ +[NSApplication sharedApplication]   (create the singleton)
            ├─▶ load NSMainNibFile from Info.plist   (AppKit nib mechanism)
            ├─▶ -[NSApplication finishLaunching]     (awakeFromNib, etc.)
            └─▶ -[NSApplication run]                  (IMP 0x177a3)
                      │
                      └─▶ main loop:
                            -[NSApplication nextEventMatchingMask:...]  (IMP 0x23861)
                            │    blocks on the CGS event queue
                            │    (_CGSConnectionGetEventQueue → mach msg from WindowServer)
                            │    returns the next NSEvent
                            ▼
                      -[NSApplication sendEvent:]  (IMP 0x1c6f5f)
                            │    dispatch to target window / first responder
                            ▼
                   (responder chain — Path B)
```

**Ownership:** the main loop and event acquisition are **AppKit-owned** (`NSApplication`).
The *event source* is WindowServer via CGS (mach messages). AppKit merely
consumes the queue.

**Linux equivalent:** `mv.application` runs the X11/GDK main loop
(`XNextEvent`/`gdk_event_wait` → `sendEvent:`-equivalent dispatch). The
"CGS event queue" maps to the X11 socket + GDK event queue.

---

## Path B — Event dispatch: event → responder chain → action

**[BIN]** NSResponder methods: `mouseDown:` (0x2ee7a2), `keyDown:` (0x2c7ccd),
`flagsChanged:` (0x277911), `interpretKeyEvents:` (0x259be4),
`tryToPerform:with:` (0x353ecb). NSWindow is a Responder subclass; so is
NSView/NSControl.

```
-[NSApplication sendEvent:] (event)
   │
   ├─▶ determine target window from event window number
   │
   └─▶ forward to the window's first responder / key window
            │
            ▼
    responder chain walk via -[NSResponder tryToPerform:with:]:
        first-responder view → superviews → content view → NSWindow
        → NSWindowController → NSApplication → delegate
        (first responder that can perform the action handles it)
   │
   ├─▶ mouse event  ─▶ -[NSView hitTest:] (IMP 0x14f6b0) → deepest view
   │                        └─▶ view.mouseDown:  (NSResponder.mouseDown: 0x2ee7a2)
   │
   ├─▶ keyboard event ─▶ key window → first responder
   │                        └─▶ -[NSResponder keyDown:] (0x2c7ccd)
   │                             └─▶ -[NSResponder interpretKeyEvents:] (0x259be4)
   │                                  → text input / key equivalents (Cmd-*)
   │
   └─▶ menu item activation
            └─▶ -[NSMenuItem validateMenuItem:] / -[NSResponder validateUserInterfaceItem:]
                 (target-or-first-responder returns YES/NO → enable/disable)
                  then action sent to target via first-responder chain
```

**Keyboard focus:** the key window receives keyboard events.
`-[NSWindow makeKeyWindow]` (0x16d23c) / `becomeKeyWindow` (0x16db53) /
`resignKeyWindow` (0x268552) manage focus. Becoming frontmost requires
`_CPSSetFrontProcessWithOptions` (AppKit imports it) — activation is a
WindowServer/process-manager decision, not purely AppKit.

**Menu validation:** `-[NSMenu validateMenuItem:]`-style (`validateMenuItem:`)
evaluated during tracking before display (see Path F).

**Linux equivalent:** the widget layer owns a focus tree; key events go to the
focus view; `tryToPerform:`-style action forwarding must be implemented
explicitly (GTK has no ObjC responder chain). Menu `set_sensitive` driven by
the first-responder chain.

---

## Path C — Window creation: NSWindow → CGS window → screen

**[BIN]** `-[NSWindow initWithContentRect:styleMask:backing:defer:]` (IMP
0x4146b), `-[NSWindow setContentView:]` (IMP 0x5aab6), `-[NSWindow
makeKeyAndOrderFront:]` (IMP 0x1659c3), `-[NSWindow setLevel:]` (IMP 0x2ad80f),
`-[NSWindow orderFront:]` (IMP 0x2af486), `-[NSWindow orderBack:]`
(0x32b4af), `-[NSWindow display]`.

```
-[NSWindow initWithContentRect:styleMask:backing:defer:]
   │
   ├─▶ _commonInitFrame:styleMask:backing:defer:     (IMP 0x420ce)
   │      ├─▶ _initContent:styleMask:backing:defer:   (IMP 0x414a4)
   │      │      └─▶ create the backing content view (NSView)
   │      └─▶ _CGSNewWindow(...)                       [CoreGraphics import]
   │               └─▶ mach msg → WindowServer creates server window
   │                      returns CGS window id → stored in NSWindow ivar
   │
   -[NSWindow setContentView:]  (IMP 0x5aab6)
            └─▶ install root NSView into the window's view hierarchy
   │
   -[NSWindow makeKeyAndOrderFront:]  (IMP 0x1659c3)
            ├─▶ _CGSOrderWindow(window, front)        [CGS import]
            └─▶ key-window focus negotiation (CPS/CGS)
   │
   -[NSWindow setLevel:]  (IMP 0x2ad80f)
            └─▶ _CGSSetWindowLevel(window, level)     [CGS import]
```

**Window levels / ordering:**
- document window: normal level
- panel (`NSPanel`, `utilityWindow|nonactivating`): floats above documents,
  excluded from Window menu
- sheet (`docModalWindow`): attached to parent, parent dimmed
- alert: app-modal, closable, nonactivating

**Ownership:** NSWindow (AppKit) owns the *object and policy*; the CGS window id
and server-side surface are **WindowServer-owned** via `_CGSNewWindow`/`_CGSOrderWindow`/`_CGSSetWindowLevel`. AppKit issues requests; WindowServer arbitrates ordering/compositing.

**Linux equivalent:** `mv.window` creates an X11 window per NSWindow, maps
`styleMask` → `_NET_WM_WINDOW_TYPE_NORMAL/DIALOG/TOOLBAR/DOCK`, `setLevel:`
→ `_NET_WM_STATE_ABOVE/BELOW` + restacking, `makeKeyAndOrderFront:` →
`XMapWindow` + `_NET_ACTIVE_WINDOW`. Window ordering = xfwm4 restack + widget
requests.

---

## Path D — View hierarchy, layout, invalidation, drawing, compositing

**[BIN]** `-[NSView setNeedsDisplay:]` (IMP 0x331d1),
`-[NSView setNeedsDisplayInRect:]` (IMP 0x33337),
`-[NSView layoutSubtreeIfNeeded]` (IMP 0xbd241),
`-[NSView setNeedsLayout:]` (IMP 0xa457f),
`-[NSView hitTest:]` (IMP 0x14f6b0),
`-[NSTextView drawRect:]` (IMP 0x200303),
`-[NSView _recursive:displayRectIgnoringOpacity:inContext:topView:]` (IMP 0x2b6499),
`-[NSView _drawRectAsLayerTree:]` (IMP 0x183753),
`-[NSView setFrame:]` (IMP 0x5af73).

**[RT]** TextEdit: `-[DocumentWindowController showRuler:]` →
`[firstTextView setRulerVisible:YES]` — the ruler is a text-view property, no
`NSRulerView` object. `-[NSTextView setUsesInspectorBar:]` toggles
`__NSInspectorBarView` (observed inside `NSThemeFrame`). These are real AppKit
calls, confirmed at framework level (NSTextView implements all three).

```
setNeedsDisplay: / setNeedsDisplayInRect:
   │    mark the view (and subtree) dirty
   ▼
display run (NSDisplay / displayIfNeeded)
   │    walks the view tree:
   │    _recursive:displayRectIgnoringOpacity:inContext:topView:  (0x2b6499)
   │        └─▶ build a CGContext per view
   │        └─▶ view.drawRect:  (NSTextView.drawRect: 0x200303)
   │
   ├─▶ flat drawing: into the window's CGContext/backing store
   │              └─▶ _CGSFlushSurface(...)          [CGS import → WindowServer]
   │
   └─▶ layer-backed (QuartzCore CALayer):
          _drawRectAsLayerTree:  (0x183753)
             └─▶ CALayer tree → QuartzCore composites
                └─▶ (still flushed to the window surface via CGS)
   │
   layout (independent of drawing):
   setNeedsLayout:  →  layoutSubtreeIfNeeded  →  -[NSView layout]
   (autoresizing mask / constraints; AppKit-owned)
```

**Invalidation → screen:** dirty rect → display pass → `drawRect:` → backing
store/CALayer → `_CGSFlushSurface` → WindowServer composites the surface to the
display (damage-region based).

**Ownership:** layout + invalidation + `drawRect:` are **AppKit-owned**; the
backing-store flush + compositing are **WindowServer-owned** via CGS.

**Linux equivalent:** GTK widget tree → `queue_draw`/`queue_draw_region`
(`setNeedsDisplay:`/`InRect:`), `GtkWidget.draw` signal (`drawRect:`),
X11 damage regions + compositor (`_CGSFlushSurface` equivalent). Layer-backed
views → offscreen surfaces per view.

---

## Path E — Standard controls, menus, tracking, validation

**[BIN]** `NSControl.mouseDown:` (0x2a6f3b), `NSControl.sendAction:to:`
(0x2421f8), `NSControl.sendActionOn:`; `NSMenu.popUpMenuPositioningItem:atLocation:inView:`,
`NSMenuItem.validateMenuItem:`; `NSScrollView`, `NSSplitView`.

```
control (e.g. NSButton) receives mouseDown:
   │  [NSControl mouseDown:]  (0x2a6f3b)
   ▼
   highlight + track (mouseDragged:/mouseUp:)
   ▼
   on click: -[NSControl sendAction:to:]  (0x2421f8)
            │    action selector sent to target (target = controller / first responder)
            └─▶ target.action  (responder chain — Path B)
   │
menu tracking:
   click menu bar → enter tracking mode
   pull-down opens → type-ahead active
   hover/arrows navigate (submenus open on →)
   click/Return/Space → action to target via first-responder chain
   click outside/Escape → dismiss
   during tracking: -[NSMenuItem validateMenuItem:]  (enable/disable,
                    target-or-first-responder decides)
```

**Key equivalents (system-reserved):** Cmd-H, Cmd-Opt-H, Cmd-Q, Cmd-,, Cmd-W,
Cmd-Opt-W, Cmd-M, Cmd-Opt-M, Cmd-`, Cmd-~, Cmd-1..9, Ctrl-F2.

**Linux equivalent:** `GtkWidget` subclasses with MavLinOS behavior wrappers;
global menu bar (`mv.menubar` service); `validateMenu-item:` →
`GtkMenuItem.set_sensitive` driven by first-responder chain; accelerators via
GTK accel groups mapped to Mavericks key equivalents.

---

## Path F — Sheets, panels, alerts, open/save dialogs

**[BIN]** TextEdit `-[DocumentWindowController
beginSheetModalForWindow:modalDelegate:didEndSelector:contextInfo:]` used for
the rich/plain alert (decompiled). `[document windowForSheet]` gets the parent.
`-[NSWindow contentView]`/`setContentView:` for sheet attachment.

**[NIB]** Finder Get Info (InfoWindow*.nib), Preferences (PreferencesWindow.nib),
Connect (ConnectToWindow.nib); System Preferences pane NIBs.

```
alert (NSAlert)                       ─▶ app-modal, fade, Escape/button
save/open panel (NSSavePanel/NSOpenPanel) ─▶ app-modal, collapsed/expanded
sheet (NSWindow docModalWindow)        ─▶ document-modal, slide down/up,
                                          parent dimmed, attached to parent
panel (NSPanel)                        ─▶ modeless, fade
progress sheet (custom NSPanel)        ─▶ document-modal, slide, cancel/complete
```

**Sheet presentation:** `beginSheetModalForWindow:modalDelegate:didEndSelector:contextInfo:`
on `windowForSheet`; delegate receives `didEnd...:returnCode:contextInfo:`.

**Dialog layout (measured):** width 320–600 pt; button bar 40 pt high, 12 pt
spacing, right-to-left order (Default blue / Cancel / Third); message font
system 13 bold/regular; dimming overlay white 50% animated.

**Ownership:** AppKit owns the dialog/sheet objects and presentation; the
parent window dimming is AppKit-driven window ordering + alpha.

**Linux equivalent:** sheets = transient-for GTK windows with custom slide
animation; alerts/panels = `GtkDialog` with MavLinOS button ordering + styling;
file chooser = MavLinOS-styled chooser (not stock GTK in dialogs).

---

## Path G — Drag-and-drop, pasteboard, inter-application interaction

**[BIN]** Dock imports: CoreDrag `_CoreDrag*` (56 symbols),
`_gDockDragCallback`, `_gDockDragWindowCallback`,
`_CoreDragCopyTrashLabel/_CoreDragIsTrashLabelSet/_CoreDragSetTrashLabel`;
LaunchServices `__LS*`, `__kLS*`, `_kCSBackupdKeyIsRunning` (running-state);
XPC `_xpc_*`. AppKit provides NSPasteboard / NSDrag.

- Pasteboard: NSPasteboard (AppKit) — cross-app data exchange.
- DnD: AppKit drag operations + CoreDrag for Dock tiles.
- Running-state: LaunchServices — which apps are running (Dock indicators).
- Trash: CoreDrag trash-label functions.
- IPC: XPC.

**Linux equivalent:** pasteboard = X11 selections + `gtk_clipboard`;
DnD = XDND/GTK drag; trash = freedesktop Trash (GVfs); running apps =
`/proc` + `mv.apps` service.

---

## Path H — Animations, transitions, window effects

**[BIN]** QuartzCore (81 classes, 31 categories): `CAAnimation`,
`CABasicAnimation`, `CAKeyframeAnimation`, `CATransition`, `CALayer`, etc.
AppKit depends on QuartzCore. WindowServer-driven window animation symbols:
`_CGSWindowAnimationChangeLevel`, `_CGSWindowAnimationChangeShiftPoint`,
`_CGSWindowAnimationHideSlot`, `_CGSWindowAnimationSetParent`,
`_CGSSetWindowAnimationProgress`.

- Genie minimize: WindowServer surface warp toward the Dock tile (`_CGSSetDockRectWithReason` target).
- Zoom: window fills screen minus Dock/menu bar (NSWindow + CGS).
- Sheet slide-down/up: AppKit window-order + CGS animation.
- Fade dialogs: AppKit alpha via `_CGSSetWindowAlpha`.

**Ownership:** view/layer animation = QuartzCore (AppKit-owned via layer
backing); window-level animation (genie/zoom/sheet) = WindowServer via CGS.

**Linux equivalent:** window animations in the compositor/widget layer
(xfwm4 animations or custom GTK); cross-fade + scale fallback for genie.

---

## Path I — Accessibility and system integration

**[BIN]** AppKit depends on PrivateFrameworks `DataDetectorsCore`,
`DesktopServicesPriv`, `CoreUI`, `MultitouchSupport`, `SpeechRecognition`.
Accessibility: `AccessibilityBundles` private framework; AppKit exposes
accessibility attributes (e.g. `NSTableView` subclass
`accessibilityAttributeValue:` seen in the Spotlight prefPane).

**Linux equivalent:** AT-SPI via GTK accessibility; `mv.accessibility` maps
Mavericks attributes to AT-SPI roles/states.

---

## Concrete call paths recovered via Ghidra decompilation (AppKit)

The following are **directly decompiled from the AppKit binary** (IMP addresses in
parentheses) and confirm the symbol-level model above:

**Path B — event acquisition:**
`-[NSApplication nextEventMatchingMask:untilDate:inMode:dequeue:]` (0x23861)
→ `__DPSNextEvent` (the Display Server / core event loop), `__NXDoMouseUpWindowOrdering`
(mouse-up window reordering), `__NSPopoverPreProcessLocalEvent`.
So event acquisition = `__DPSNextEvent` reading the Display Server event queue,
not a direct CGS call per event.

**Path B — event dispatch:**
`-[NSApplication sendEvent:]` (0x1c6f5f) → `_GetEventDispatcherTarget`,
`_NSAccessibilityPostNotification`, `_NSPerformWithScreenUpdatesDisabled`,
`_CGCursorIsVisible`, `_CFAbsoluteTimeGetCurrent`, `_ActiveNonFloatingWindow`,
`_NSLog`, `_NSBeep`. The actual dispatch to responder views proceeds up the
chain via `_objc_msgSendSuper2` (seen in `NSCarbonWindow.sendEvent:`,
`HICocoaWindowAdapter.sendEvent:`, `NSDocumentRevisionsWindow.sendEvent:`).

**Path C — window level / ordering / animation:**
`-[NSWindow setLevel:]` (0x2ad80f) → `_CGSMainConnectionID` (the CGS server-port
connection), `_CGSSetWindowLevelForGroup` (← the actual CGS level request),
`_CGSWindowAnimationChangeLevel` (← window-level animation), `_PSsetwindowlevel`.
So `setLevel:` → `_CGSSetWindowLevelForGroup` → WindowServer. Confirmed.

**Path C — window creation & event bridge:**
`-[NSWindow initWithContentRect:...]` variants forward to `super`; the
`NSTitlebarFloatingWindow` variant installs Carbon event handlers via
`_GetApplicationEventTarget` + `_InstallEventHandler` on
`_GetApplicationEventTarget`, plus `__NSToolbarGetMenuBarFullScreenReveal`.
Confirms the HIToolbox (Carbon) event bridge is wired at window creation.

**Path D — invalidation / dirty-region bridge:**
`-[NSView setNeedsDisplay:]` (0x331d1) → `__HICocoaViewSetNeedsDisplay`
(← HIToolbox dirty-region notification when the view is bound to a HIView),
`__NSWindowsTrackDirtyRegions`, guarded by `_objc_sync_enter`/`_objc_sync_exit`.
So `setNeedsDisplay:` marks dirty regions and, via `__HICocoaViewSetNeedsDisplay`,
notifies the Carbon/HIView side. Confirmed.

**Path D — themed drawing:**
`[NSTitlebarThemeFrame drawRect:]` → `__NSDrawThemeBackground` (HIToolbox
themed background), `NSGraphicsContext.currentContext.graphicsPort`,
`_NSRectFillUsingOperation`, shadow image draw. Confirms HIToolbox theme
drawing for title-bar frames.

---

## Cross-validation summary (≥2 independent clients)

| Mechanism | Evidence A | Evidence B | Evidence C |
|---|---|---|---|
| `setRulerVisible:` / `setUsesInspectorBar:` | AppKit binary (NSTextView, IMPs) | TextEdit decompilation (controller → text view) | nsinspect runtime (no NSRulerView object) |
| Responder chain / `tryToPerform:` | AppKit binary (NSResponder methods) | TextEdit `showRuler:` responder deferral (`performSelector:afterDelay:`) | `showRulerDelayed:` coalescing |
| `NSWindow` key/main + `setLevel:` | AppKit binary (NSWindow methods) | System Preferences window NIB (key/main window) | Dock ordering CGS symbols |
| CGS window/surface/space boundary | AppKit imports (287 `_CGS*`) | Dock imports (~420 CGS, largest family) | Finder window NIBs (window structure) |

---

## Unresolved in call paths

| Detail | Evidence needed |
|---|---|
| Exact `_CGSNewWindow` argument order/types from `-[NSWindow initWithContentRect:...]` | Ghidra decompile `initWithContentRect:` (IMP 0x4146b) |
| `-[NSApplication sendEvent:]` target-window selection logic | Ghidra decompile `sendEvent:` (IMP 0x1c6f5f) |
| `_CGSFlushSurface` flush point in `-[NSView display]` | Ghidra decompile `display` path |
| CGS server-port mach message formats | runtime capture in booted guest (not available from static binaries) |
