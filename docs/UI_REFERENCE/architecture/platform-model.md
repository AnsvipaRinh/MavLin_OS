# MavLinOS platform model — native macOS Mavericks 10.9 application UI runtime

**Status:** implementation-grade reference (evidence-backed).  
**Source of truth:** installed Mavericks frameworks extracted read-only from the
guest HFS+ volume (`/System/Library/Frameworks/{AppKit,Foundation,CoreGraphics,
CoreFoundation,QuartzCore,Carbon/HIToolbox}`), analysed with Ghidra 12.1.2 +
PyGhidra and with the repo's `framework_index.py` Mach-O/ObjC pipeline.
Raw evidence: `docs/UI_REFERENCE/runtime/raw/native/` and
`vmwork/opencode/frameworks/{extracted,index}`.

**Conventions.** **[BIN]** = static binary evidence (Mach-O ObjC metadata,
symbol table, dependencies, Ghidra decompilation). **[NIB]** = REA compiled-NIB
evidence. **[RT]** = `nsinspect`/`mvprobe` runtime capture. **[INFERRED]** =
reasoned interpretation pending verification. Native macOS contracts are quoted
as selectors/API names; project `mv.*` abstractions are explicitly prefixed and
never presented as Apple APIs.

---

## 1. Responsibility model — who owns what

The Mavericks UI runtime is split across four layers. The Linux port must
reproduce the *boundaries*, not reimplement Apple's internals.

```
┌─────────────────────────────────────────────────────────────┐
│  Application (Finder, TextEdit, Dock, …)                    │
│  ├─ owns: business logic, NIB contents, targets/actions,    │
│  │     document model, view-mode switching (FFK*View)        │
│  └─ talks to: AppKit (all UI), LaunchServices (running apps)│
├─────────────────────────────────────────────────────────────┤
│  AppKit (ApplicationServices umbrella)                      │
│  ├─ owns: NSApplication event loop, responder chain,        │
│  │     NSWindow/NSView hierarchy, layout, invalidation,      │
│  │     drawing, controls, menus, tracking, validation,       │
│  │     sheets/panels/alerts, pasteboard, drag-and-drop       │
│  └─ talks to: CoreGraphics (CGS → WindowServer),            │
│  │     CoreFoundation, libobjc, HIToolbox (Carbon menus/     │
│  │     hotkeys/process focus), QuartzCore (layer animation)  │
├─────────────────────────────────────────────────────────────┤
│  CoreGraphics / CoreGraphics Services (CGS)                 │
│  ├─ owns: the public/private CGS API surface that AppKit    │
│  │     imports (287 `_CGS*` symbols: windows, surfaces,      │
│  │     spaces, ordering, tracking rects, events, displays)   │
│  └─ talks to: WindowServer via IPC (mach messages on the    │
│  │     CGS server port)                                      │
├─────────────────────────────────────────────────────────────┤
│  WindowServer (system process)                              │
│  ├─ owns: window server state, compositing, display         │
│  │     management, Spaces, global event queue, cursor        │
│  └─ talks to: kernel (display/input), CGS clients           │
└─────────────────────────────────────────────────────────────┘
```

**Rule:** AppKit owns *policy and presentation*; CGS/WindowServer owns *screen
real estate and global arbitration*. An `NSWindow` is an AppKit object that
*wraps* a CGS window (a server-side surface). AppKit never touches pixels
directly for window placement — it issues `_CGS*` requests; WindowServer
composites.

### Framework coupling (measured, **[BIN]**)

| Framework | Classes | Categories | Defined syms | Undefined (imported) | Key dependencies |
|---|---:|---:|---:|---:|---|
| AppKit | 1179 | 94 | 63080 | 3616 | CoreGraphics, CoreFoundation, libobjc, Carbon/HIToolbox, QuartzCore, CoreText, ImageIO, OpenGL, IOKit, DiskArbitration, CoreAudio, AudioToolbox, CoreData, CFNetwork; Private: DataDetectorsCore, DesktopServicesPriv, CoreUI, MultitouchSupport, QuartzCore, PerformanceAnalysis, GenerationalStorage, Sharing, SpeechRecognition |
| Foundation | 584 | 137 | 19983 | 1971 | libobjc, CFNetwork, SystemConfiguration, Security, CoreServices, IOKit, libSystem |
| CoreGraphics | 0 | 0 | 15290 | 891 | CoreFoundation, IOKit, IOSurface, CoreServices, Security, Accelerate, libSystem |
| CoreFoundation | 112 | 3 | 8625 | 768 | libobjc, libSystem |
| QuartzCore | 81 | 31 | 9293 | 1051 | Foundation, CoreGraphics, CoreFoundation, CoreText, ImageIO, IOSurface, OpenGL, libSystem |
| HIToolbox | 22 | 1 | 15746 | 2004 | CoreFoundation, IOKit, ApplicationServices, Foundation, CoreGraphics, CoreText, libobjc |
| libobjc.A.dylib | 4 | 0 | 1077 | 190 | libSystem, libauto, libc++ |

- CoreGraphics is pure C (0 ObjC classes): the `_CGS*` API is a C interface to
  WindowServer, imported by AppKit as undefined symbols (287 of them).
- AppKit imports `libobjc.A.dylib` and `CoreFoundation`; Foundation imports
  `libobjc`. Confirms the runtime layering: `libobjc` (runtime) →
  `CoreFoundation` → `Foundation` → `AppKit`.
- AppKit does **not** depend on a `WindowServer.framework`; the WindowServer
  boundary is entirely the `_CGS*` C API inside CoreGraphics, reached through
  the CGS server port (IPC). This is the architectural fact MavLinOS must
  respect: the Dock and every app are CGS clients of WindowServer.

Evidence: `frameworks/index/*.x86_64.json` (produced by
`tools/uiref/framework_index.py` from the extracted thin x86_64 slices).

---

## 2. Objective-C runtime layer

**[BIN]** The 10.9 runtime is objc4 64-bit. Class layout verified against
Ghidra's object model:

- `objc_class`: isa(+0), super(+8), cache(+16), vtable(+24), data(+32)
- `class_ro_t`: flags(+0), instanceStart(+4), instanceSize(+8), reserved(+12),
  ivarLayout(+16), name(+24), baseMethodList(+32), ...
- `method_t` (absolute 24-byte): SEL* name, const char* types, IMP* imp
- `method_list_t`: entsize_and_flags(u32), count(u32), entries

TextEdit (control, readable): 15 classes / 1 category / 253 methods,
253/253 with selector+IMP+Ghidra function. Calculator shell 11 classes/217
methods; BasicAndSci plug-in 8 classes/153 methods; Hexadecimal 2 classes/77
methods — all byte-identical to prior evidence, confirming the pipeline is
stable.

**Finder/Dock anomaly (independently re-validated):** fresh extraction of
Finder (6,209,552 B) and Dock (3,259,200 B) yields valid complete Mach-Os
(`__PAGEZERO, __TEXT, __DATA, __LINKEDIT`, no `LC_ENCRYPTION_INFO`). Section
entropy: `__text` **8.00** (max, not code), `__objc_classname`/`__objc_methname`
**8.00** (names scrambled), while `__objc_classlist`/`__objc_const`/`__objc_data`
are readable (structure intact). Packed size ≈ logical size → not decmpfs
compression. No `LC_ENCRYPTION_INFO` → not standard load-time encryption.
Conclusion: Finder/Dock string/code payloads are obfuscated/encrypted at rest
through the current extraction pipeline; structure (class/method ownership by
address) is recoverable, names are not. Requires a booted guest or decryption
oracle. Documented gap, non-blocking to framework analysis.

Evidence: `frameworks/anomaly/`, `docs/UI_REFERENCE/runtime/raw/native/finder-abi-layout.json`.

---

## 3. Application startup and the NSApplication event loop

**[BIN]** AppKit symbols + method table:

| Selector | Class | IMP | Role |
|---|---|---|---|
| `run` | NSApplication | 0x177a3 | enters the main event loop |
| `sendEvent:` | NSApplication | 0x1c6f5f | dispatches one event |
| `nextEventMatchingMask:untilDate:inMode:dequeue:` | NSApplication | 0x23861 | acquires the next event |
| `postEvent:atStart:` | NSApplication | 0x2408fe | injects an event |
| `currentEvent` | NSApplication | 0x1639b9 | the current event |
| `runModalForWindow:` | NSApplication | 0x3812f9 | modal session |
| `sharedApplication` | NSApplication (+) | — | the singleton |

NSApplication is a subclass of **NSResponder** (546 instance methods, 18 ivars).
The responder chain root is `NSResponder` (97 methods), subclassed by
`NSApplication`, `NSWindow`, `NSView` (and `NSControl` → `NSButton`).

**Execution path (application startup → screen):**

1. `main()` calls `NSApplicationMain(argc, argv)` (AppKit defined symbol
   `___NSApplicationMain` + `_NSApplicationMain`), which creates
   `NSApplication` (sharedApplication), loads `NSMainNibFile` from the bundle's
   `Info.plist`, and sends `-finishLaunching` then `-run`.
2. `-[NSApplication run]` runs the main loop: repeatedly
   `nextEventMatchingMask:untilDate:inMode:dequeue:` → blocks in the CGS event
   queue waiting for the next mach-message event → `sendEvent:`.
3. `-[NSApplication sendEvent:]` is the dispatch point: it determines the
   target window/view and forwards the event down the responder chain
   (`NSResponder.mouseDown:`, `keyDown:`, `flagsChanged:`,
   `interpretKeyEvents:`, `tryToPerform:with:`).

**Activation / front process.** AppKit imports `_CPSSetFrontProcessWithOptions`,
`_CPSBringNextToFront`, `_CPSReleaseKeyFocus`, `_CPSStealKeyFocus`,
`_CPSModifyConnectionNotifications` (CoreProcess / CPS, 5 symbols). Becoming the
frontmost (active) application is not an AppKit-only decision: AppKit asks the
window server / process manager via CPS to make this process frontmost; only
then does it receive key events and the menu bar.

**Implication for Linux:** `NSApplication.run` maps to the X11/GDK main loop;
`nextEventMatchingMask:` maps to `XNextEvent`/GDK event read; `sendEvent:` maps
to the project's event-dispatch widget that walks the responder chain. Activation
maps to X11 `_NET_ACTIVE_WINDOW` + WM focus, not a separate process-manager.

---

## 4. Event acquisition, dispatch, responder chain, keyboard focus

**[BIN]** NSResponder method surface:

| Selector | Role |
|---|---|
| `mouseDown:` / `mouseUp:` / `mouseDragged:` | pointer tracking |
| `keyDown:` / `keyUp:` / `flagsChanged:` | keyboard |
| `interpretKeyEvents:` | turn raw key events into text/actions |
| `tryToPerform:with:` | responder-chain action forwarding |
| `validateUserInterfaceItem:` / `validateMenuItem:` | menu/item enabling |
| `sendEvent:` | forward an event (NSApplication and NSResponder) |

**Responder chain order:** first responder (view) → its superview chain up to
the window's content view → the NSWindow → the NSWindowController → the
NSApplication → the delegate. `tryToPerform:with:` walks this chain; the first
responder that responds YES handles the action. Menu item activation (`validateMenuItem:`)
is evaluated during menu tracking before display (target-or-first-responder
returns YES/NO to enable/disable).

**Keyboard focus:** the "key window" receives keyboard events. Window
`becomeKeyWindow` / `resignKeyWindow` are the focus transitions; `NSWindow`
owns key/main status (`makeKeyWindow`, `makeKeyAndOrderFront:`).
`NSStatusItem` (75 methods) owns menu-bar status items (right side).

**Implication for Linux:** the widget layer owns a focus tree mirroring
`NSWindow` key/main state; key events go to the focus view; the responder chain
is reimplemented in the widget layer (GTK does not have an ObjC-style chain, so
MavLinOS must implement `tryToPerform:`-style action forwarding explicitly).

---

## 5. NSWindow creation, registration, ordering, activation, destruction

**[BIN]** NSWindow (1379 instance methods, 30 ivars), subclass of NSResponder.
`NSPanel` (21 methods) subclasses `NSWindow` — utility/non-activating floating
windows.

| Selector | IMP | Role |
|---|---|---|
| `initWithContentRect:styleMask:backing:defer:` | 0x4146b | designated initializer |
| `initWithContentRect:styleMask:backing:defer:screen:` | 0x792446 | with screen |
| `setContentView:` | 0x5aab6 | install the root NSView |
| `contentView` | 0x6030b | root view accessor |
| `makeKeyWindow` | 0x16d23c | become key window |
| `makeKeyAndOrderFront:` | 0x1659c3 | key + visible |
| `orderFront:` | 0x2af486 | order to front |
| `orderBack:` | 0x32b4af | order behind |
| `becomeKeyWindow` / `resignKeyWindow` | 0x16db53 / 0x268552 | focus transitions |
| `setLevel:` | 0x2ad80f | window level (floating, etc.) |
| `setOpaque:` | 0x29ce98 | opacity |
| `setFrame:display:animate:` | 0x144423 | geometry + redraw |
| `display` | — | trigger redraw |

**Window → CGS mapping (the core boundary).** AppKit imports 287 `_CGS*`
symbols from CoreGraphics. The window-relevant ones:

- `_CGSNewWindow`, `_CGSNewWindowWithOpaqueShape` — create a server window
- `_CGSReleaseWindow` — destroy
- `_CGSOrderWindow`, `_CGSOrderSurface` — ordering (front/back)
- `_CGSGetWindowBounds`, `_CGSSetWindowTransform` — geometry
- `_CGSGetWindowLevel`, `_CGSSetWindowLevel` — level (floating dock/panel)
- `_CGSSetWindowOpacity`, `_CGSSetWindowAlpha` — alpha
- `_CGSGetWindowOwner`, `_CGSGetWindowType` — ownership/type
- `_CGSAddWindowToWindowOrderingGroup`, `_CGSReorderWindows` — groups
- `_CGSAddWindowsToSpaces`, `_CGSRemoveWindowsFromSpaces` — Spaces membership
- `_CGSGetWorkspaceWindowGroup` — workspace group
- `_CGSSetWindowShadowParameters`, `_CGSSetWindowShadowAndRimParameters` — shadow
- `_CGSAddTrackingRect` / `_CGSRemoveTrackingArea` — mouse tracking rects
- `_CGSGetDockRectWithReason` / `_CGSSetDockRectWithReason` — Dock rect (Dock is
  a privileged CGS client setting its own rect)
- `_CGSGetActiveMenuBarDrawingStyle`, `_CGSSetMenuBarDrawingStyle` — menu bar

**Execution path (window creation):** `-[NSWindow
initWithContentRect:styleMask:backing:defer:]` → `_commonInitFrame:` →
`_initContent:` → AppKit calls `_CGSNewWindow(...)` to create the server-side
CGS window, stores the CGS window ID in the NSWindow ivar, then `-setContentView:`
installs the root view. `-makeKeyAndOrderFront:` → `_CGSOrderWindow` (front) +
key-window focus negotiation via CPS/CGS.

**Window levels (ordering):** style mask (`titled`, `closable`, `miniaturizable`,
`resizable`, `unifiedTitleAndToolbar`) + level. Panels (`NSPanel`,
`utilityWindow`, `nonactivating`) float above document windows; sheets
(`docModalWindow`) attach to a parent and dim it; alerts are app-modal.

**Implication for Linux:** an `mv.window` service owns an X11 window per
NSWindow, mapped to X11 window types (`_NET_WM_WINDOW_TYPE_NORMAL/DIALOG/
DOCK/TOOLBAR`), `_NET_WM_STATE` for modal/floating, and `_NET_ACTIVE_WINDOW`
for key window. Ordering = X11 restack + `_NET_WM_STATE`/`wmutils`-style level.
The CGS window ID is an opaque handle the widget layer tracks.

---

## 6. NSView hierarchies, layout, invalidation, drawing, compositing

**[BIN]** NSView (1123 instance methods, 12 ivars), subclass of NSResponder.
`NSControl` (146) → `NSButton` (69); `NSScrollView` (310); `NSSplitView` (126).

| Selector | IMP | Role |
|---|---|---|
| `display` | — | redraw this view (and dirty subtree) |
| `drawRect:` | — | actual rendering (NSTextView: 0x200303) |
| `setNeedsDisplay:` | 0x331d1 | mark dirty |
| `setNeedsDisplayInRect:` | 0x33337 | mark dirty rect |
| `layoutSubtreeIfNeeded` | 0xbd241 | run layout if needed |
| `setNeedsLayout:` | 0xa457f | mark needs layout |
| `layout` | — | perform layout |
| `hitTest:` | 0x14f6b0 | deepest view at a point (hit testing) |
| `setFrame:` | 0x5af73 | geometry |
| `setNeedsDisplay`/display recursion | `_recursive:displayRectIgnoringOpacity:inContext:topView:` | 0x2b6499 |

**Drawing path:** `setNeedsDisplay:` marks the view dirty; the display run
(`NSDisplay` / `displayIfNeeded`) walks the view tree via
`_recursive:displayRectIgnoringOpacity:inContext:topView:`, building a
`CGContext` for each view and invoking `drawRect:`. Views may be layer-backed
(QuartzCore `CALayer`) — `_drawRectAsLayerTree:` (0x183753) — in which case
QuartzCore composites the layer tree; otherwise AppKit draws into the window's
CGContext and flushes via `_CGSFlushSurface`.

**Invalidation → compositing:** dirty rect → `setNeedsDisplayInRect:` → display
pass → `drawRect:` into CGContext → (layer-backed: QuartzCore layer tree;
flat: window backing store) → `_CGSFlushSurface` pushes the backing store to
WindowServer → WindowServer composites to screen.

**Implication for Linux:** GTK `GtkWidget` tree maps to NSView hierarchy;
`queue_draw`/`queue_draw_region` maps to `setNeedsDisplay:`/`InRect:`;
`GtkWidget.draw` signal maps to `drawRect:`; compositing is handled by the X11
compositor (xfwm4) — the widget layer flushes damage regions to the X11 window.
Layer-backed views (QuartzCore CALayer) map to an offscreen surface per view.

---

## 7. Standard controls, menus, tracking, validation, keyboard navigation

**[BIN]** controls:

| Class | Methods | Notes |
|---|---:|---|
| NSControl | 146 | base: `mouseDown:` (0x2a6f3b), `sendAction:to:` (0x2421f8), `sendActionOn:` |
| NSButton | 69 | button cell |
| NSMenu | 185 | `popUpMenuPositioningItem:atLocation:inView:`, tracking |
| NSMenuItem | 143 | `validateMenuItem:` enabled state |
| NSToolbar | 245 | toolbar |
| NSToolbarItem | 136 | toolbar item |
| NSTextView | 856 | `setRulerVisible:` (0x157c40), `setUsesInspectorBar:` (0x739e36), `setUsesRuler:` (0x271222) — **real 10.9 public API**, validated against TextEdit findings |
| NSScrollView | 310 | scroller + content |

**Menu tracking cycle (AppKit):** click menu bar → enter tracking → pull-down
opens → type-ahead → hover/arrows navigate → click/Return/Space sends action to
target via first-responder chain → click outside/Escape dismisses.
`validateMenuItem:`/`validateUserInterfaceItem:` called during tracking before
display to enable/disable.

**Key equivalents (system, reserved):** Cmd-H, Cmd-Opt-H, Cmd-Q, Cmd-,, Cmd-W,
Cmd-Opt-W, Cmd-M, Cmd-Opt-M, Cmd-`, Cmd-~, Cmd-1..9, Ctrl-F2.

**Implication for Linux:** controls are `GtkWidget` subclasses with MavLinOS
behavior wrappers; menus are a global menu bar (project `mv.menubar` service)
plus app menus; `validateMenuItem:` maps to `GtkMenuItem.set_sensitive` driven
by the first-responder chain; keyboard navigation (arrows in menus, tab between
controls) is implemented in the widget layer.

---

## 8. Sheets, panels, alerts, open/save dialogs, transient windows

**[BIN]** + **[NIB]** (Finder Get Info / Preferences / Connect NIBs; System
Preferences pane NIBs):

| Type | Class | Modality | Animation | Dismissal |
|---|---|---|---|---|
| Alert | NSAlert | app-modal | fade | Escape / button |
| Save/Open panel | NSSavePanel / NSOpenPanel | app-modal | fade | Escape / button |
| Sheet | NSWindow (docModalWindow) | document-modal | slide down/up | Escape / button |
| Panel | NSPanel | modeless | fade | close / Escape |
| Progress sheet | custom NSPanel | document-modal | slide | cancel / complete |

Sheets are attached to a parent (`windowForSheet`), presented with
`beginSheetModalForWindow:modalDelegate:didEndSelector:contextInfo:` (TextEdit
rich/plain alert uses this exact path, **[BIN]**). Parent is dimmed (white 50%,
animated).

Dialog layout rules **[INFERRED]** from NIB geometry: dialog min/max width
320–600 pt; button bar 40 pt high, 12 pt spacing, right-to-left order (Default
blue, Cancel, Third); message font system 13 bold/regular.

**Implication for Linux:** sheets are transient-for GTK windows with a custom
slide animation; alerts/panels are `GtkDialog` with MavLinOS button ordering and
styling; file chooser is a MavLinOS-styled chooser (not the stock GTK chooser
in dialogs).

---

## 9. Drag-and-drop, pasteboard, inter-application interaction

**[BIN]** Dock imported symbols: CoreDrag (`_CoreDrag*`, 56 symbols),
`_gDockDragCallback`, `_gDockDragWindowCallback`, `_CoreDragCopyTrashLabel`,
`_CoreDragIsTrashLabelSet`, `_CoreDragSetTrashLabel` (trash). Running-state via
LaunchServices (`__LS*`, `__kLS*`, `_kCSBackupdKeyIsRunning`). Inter-process via
XPC (`_xpc_*`).

AppKit-level pasteboard/DD is NSPasteboard / NSDrag operations (AppKit defined
symbols). The Dock is the drag session owner for Dock tiles.

**Implication for Linux:** pasteboard = X11 selections + `gtk_clipboard`;
drag-and-drop = XDND / GTK drag protocols; trash = freedesktop Trash via GVfs;
running apps via `/proc` + LaunchServices-equivalent (`mv.apps` service).

---

## 10. Animations, transitions, window effects

**[BIN]** QuartzCore (81 classes, 31 categories) is the animation framework:
`CAAnimation`, `CABasicAnimation`, `CAKeyframeAnimation`, `CATransition`,
`CALayer`, `CAScrollLayer`, `CATiledLayer`, etc. AppKit depends on QuartzCore.
Window effects: `_CGSWindowAnimationChangeLevel`, `_CGSWindowAnimationChangeShiftPoint`,
`_CGSWindowAnimationHideSlot`, `_CGSWindowAnimationSetParent`,
`_CGSSetWindowAnimationProgress` (CGS symbols) — WindowServer-driven window
animations (genie minimize, sheet slide, window level changes).

- Genie minimize: CGS surface warp toward Dock tile (WindowServer).
- Zoom: fills screen minus Dock/menu bar (NSWindow + CGS).
- Sheet slide-down/up: AppKit-driven window-order + CGS animation.
- Fade-in/out dialogs: AppKit alpha animation via `_CGSSetWindowAlpha`.

**Implication for Linux:** window minimize/zoom/sheet animations implemented in
the compositor/widget layer (xfwm4 window animations or custom GTK animations);
cross-fade + scale fallback where genie isn't available.

---

## 11. Accessibility and system integration

**[BIN]** AppKit depends on PrivateFrameworks `DataDetectorsCore`,
`DesktopServicesPriv`, `CoreUI`, `MultitouchSupport`, `SpeechRecognition`.
Dock depends on LaunchServices, CoreDrag, XPC, Carbon menus.

Accessibility: the `AccessibilityBundles` private framework; AppKit exposes
accessibility attributes (NSTableView subclass `accessibilityAttributeValue:`,
seen in Spotlight prefPane).

**Implication for Linux:** AT-SPI via GTK accessibility; `mv.accessibility`
maps Mavericks attributes to AT-SPI roles/states where a faithful mapping
exists.

---

## 12. Linux implementation implications — component map

| Mavericks mechanism | Native owner | Linux equivalent (project) | Fidelity note |
|---|---|---|---|
| NSApplication event loop | AppKit | `mv.application` widget main loop | event loop is app-owned |
| nextEventMatchingMask / sendEvent | AppKit | widget dispatch | forward to responder chain |
| Responder chain / tryToPerform | AppKit (NSResponder) | widget layer (custom) | GTK has no ObjC chain — must implement |
| NSWindow ↔ CGS window | AppKit → CoreGraphics CGS | `mv.window` + X11 window | CGS window ID = opaque handle |
| Window ordering / levels / Spaces | WindowServer (via CGS) | xfwm4 + `_NET_WM_STATE` | Spaces = virtual desktops |
| Key window / focus | AppKit (NSWindow) | X11 focus + `_NET_ACTIVE_WINDOW` | widget focus tree |
| NSView hierarchy / drawRect | AppKit | GTK widget tree + draw signal | layer-backed = offscreen surface |
| Invalidation / flush | AppKit + CGS | `queue_draw` + X11 damage | compositor composites |
| Menus / validateMenuItem | AppKit (NSMenu) | `mv.menubar` + GtkMenu | global menu bar |
| Controls / cells | AppKit (NSControl) | GtkWidget subclasses | behavior wrappers |
| Sheets / alerts / panels | AppKit (NSWindow/NSPanel) | transient GtkWindow/GtkDialog | custom animations |
| Pasteboard / DnD | AppKit + CoreDrag | X11 selections + XDND | GVfs trash |
| Animations | QuartzCore + WindowServer | xfwm4 / GTK animations | genize fallback |
| Front process / activation | CPS + WindowServer | `_NET_ACTIVE_WINDOW` | no process manager on Linux |

---

## 13. Cross-validation against native applications (evidence)

| Application | Framework contracts confirmed | Evidence |
|---|---|---|
| TextEdit 1.9 | `NSTextView.setRulerVisible:`, `setUsesInspectorBar:`, `setUsesRuler:` are real 10.9 API; ruler is text-view property not NSRulerView; rich/plain via `beginSheetModalForWindow:` | **[BIN]** Ghidra 253/253 methods; **[RT]** nsinspect |
| Calculator | plug-in shell vs engine; `CalculatorView` protocol; `setBackEndMode:` swaps engines; NIB owner = plug-in | **[BIN]** 217/153/77 methods; **[NIB]** |
| System Preferences | `NSPrefPanesManager` discovery/switch/load; `PreferencePanesCenter` cache; `selected_preference_pane_bundleID` persistence; NIB↔native outlet/selector correlation | **[BIN]** 301 methods; **[NIB]** |
| Finder | view modes = FFK*View subclasses swapped in `mBrowserView`; 435 menu actions; `FFKBrowserView/Column/List/Icon/FlowView` | **[NIB]** 74 NIBs (native binary metadata scrambled — see anomaly) |
| Dock | `_CGSSetDockRectWithReason`, `_CGSAddWindowsToSpaces`, `_CGSAddTrackingRect`, CoreDrag, LaunchServices — Dock is a privileged CGS client | **[BIN]** imported symbols; **[NIB]** menus only |

**Framework contracts validated by ≥2 clients:** `setRulerVisible:`/`setUsesInspectorBar:` (AppKit binary + TextEdit decompilation + nsinspect); `NSResponder` responder chain (AppKit binary + TextEdit `showRuler:` responder deferral); `NSWindow` key/main + `setLevel:` (AppKit binary + System Preferences window NIB + Dock ordering symbols); CGS window/surface/space APIs (AppKit imports + Dock imports + Finder window NIBs).

---

## 14. Unresolved details and required evidence

| Detail | Evidence needed |
|---|---|
| Exact `-[NSWindow initWithContentRect:...]` → `_CGSNewWindow` argument mapping | Ghidra decompile `initWithContentRect:` (IMP 0x4146b) |
| `-[NSApplication sendEvent:]` responder-chain target selection | Ghidra decompile `sendEvent:` (IMP 0x1c6f5f) |
| `-[NSView display]` → `_CGSFlushSurface` flush point | Ghidra decompile `display` path |
| WindowServer IPC message formats (CGS server port) | not available from static binaries; runtime capture or docs |
| Finder/Dock class names & selectors | booted guest or decryption oracle (anomaly) |
| Main Spotlight search UI, QLPreviewPanel integration | booted guest (binary inaccessible) |

---

## 15. Evidence index

| Evidence | Location |
|---|---|
| Framework thin x86_64 slices | `vmwork/opencode/frameworks/extracted/*.x86_64` |
| Framework index (classes/symbols/deps) | `vmwork/opencode/frameworks/index/*.json` |
| AppKit Ghidra project | `/home/builder/ghidra_proj/appkit` |
| AppKit ObjC meta (ghidra) | `vmwork/opencode/frameworks/index/appkit-objc-meta-ghidra.json` |
| Finder/Dock anomaly extracts | `vmwork/opencode/frameworks/anomaly/` |
| Existing app metadata | `docs/UI_REFERENCE/runtime/raw/native/*` |
| Regression tests | `tests/uiref/test_native_evidence.py`, `test_objc_classnames.py` |

Pipeline: `tools/uiref/framework_index.py` (Mach-O + ObjC index),
`tools/uiref/machobjc.py` (legacy ObjC dump), `tools/uiref/ghidra/objc_extract.py`,
`tools/uiref/ghidra/objc_decompile.py` (Ghidra), `tools/uiref/nsinspect.c` (runtime).

---

**Native contract vs project abstraction.** All class/method/API names above
(NSApplication, NSWindow, NSView, NSResponder, _CGSNewWindow,
setRulerVisible:, validateMenuItem:, beginSheetModalForWindow:, …) are native
macOS 10.9 contracts recovered from the binaries. Project `mv.*` names
(`mv.window`, `mv.menubar`, `mv.application`, `mv.apps`) are MavLinOS
abstractions and are labeled as such; they are never presented as Apple APIs.
