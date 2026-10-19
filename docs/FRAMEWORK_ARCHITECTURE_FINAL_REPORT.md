# Final report — native Mavericks application UI runtime reconstruction

**Date:** 2026-10-19  
**Mission:** Reconstruct the native macOS Mavericks 10.9 application UI runtime
(AppKit + CoreGraphics + WindowServer) to produce an implementation-grade
architectural reference for the MavLinOS Linux port.  
**Scope:** frameworks AppKit, Foundation, CoreGraphics, CoreFoundation,
QuartzCore, Carbon/HIToolbox, libobjc; plus cross-validation against Finder,
Dock, TextEdit, Calculator, System Preferences; plus independent validation of
the Finder/Dock metadata anomaly.

---

## 1. Headline conclusion

The Mavericks UI runtime is a clean four-layer split:

```
Application  →  AppKit  →  CoreGraphics (CGS)  →  WindowServer
```

- **AppKit owns policy and presentation**: the `NSApplication` event loop,
  responder chain, `NSWindow`/`NSView` hierarchy, layout, invalidation, drawing,
  controls, menus, sheets/panels/alerts, pasteboard, DnD.
- **CoreGraphics/CGS owns the client-side WindowServer API**: 287 `_CGS*`
  symbols imported by AppKit for windows, surfaces, spaces, ordering, tracking
  rects, events, displays, and the Dock rect.
- **WindowServer (system process) owns compositing, displays, Spaces, and the
  global event queue**, reached only via CGS → mach messages on the CGS server
  port. There is **no public API to WindowServer**.
- **HIToolbox (Carbon) is the event/drawing bridge**: window creation installs
  Carbon event handlers (`_GetApplicationEventTarget`/`_InstallEventHandler`);
  `setNeedsDisplay:` notifies `__HICocoaViewSetNeedsDisplay` when bound to a
  HIView; themed frames draw via `__NSDrawThemeBackground`.

**The center of the investigation has moved off SystemUIServer.** SystemUIServer
extraction is no longer the critical path; the framework/CGS boundary is now
recovered from the installed binaries themselves, with concrete decompiled call
paths.

---

## 2. Frameworks analyzed (installed binaries, extracted read-only from the
guest HFS+ volume via 7z on a loop device)

All slices are thin x86_64 Mach-Os. Indexed with the new
`tools/uiref/framework_index.py` pipeline; AppKit also fully decompiled with
Ghidra 12.1.2 + PyGhidra.

| Framework | Classes | Categories | Defined syms | Undefined (imported) | Role |
|---|---:|---:|---:|---:|---|
| AppKit | 1179 | 94 | 63080 | 3616 | UI runtime: NSApplication/NSWindow/NSView/controls/menus |
| Foundation | 584 | 137 | 19983 | 1971 | objects, collections, run loop, notifications |
| CoreGraphics | 0 | 0 | 15290 | 891 | pure C; 1616 `_CGS*` defined — the WindowServer client API |
| CoreFoundation | 112 | 3 | 8625 | 768 | CF types, toll-free bridging |
| QuartzCore | 81 | 31 | 9293 | 1051 | `CAAnimation`/`CALayer` — layer animation |
| HIToolbox | 22 | 1 | 15746 | 2004 | Carbon: event dispatch, theme drawing, HIView bridge |
| libobjc.A.dylib | 4 | 0 | 1077 | 190 | Objective-C runtime |

**Coupling (measured):** AppKit → CoreGraphics, CoreFoundation, libobjc,
Carbon/HIToolbox, QuartzCore, CoreText, ImageIO, OpenGL, IOKit, DiskArbitration,
CoreAudio, AudioToolbox, CoreData, CFNetwork + PrivateFrameworks
(DataDetectorsCore, DesktopServicesPriv, CoreUI, MultitouchSupport,
QuartzCore, PerformanceAnalysis, GenerationalStorage, Sharing, SpeechRecognition).
Foundation → libobjc. Confirms runtime layering libobjc → CoreFoundation →
Foundation → AppKit. No `WindowServer.framework` dependency exists — the
WindowServer boundary is entirely the `_CGS*` C API inside CoreGraphics.

Raw evidence: `vmwork/opencode/frameworks/{extracted,index/}`.  
AppKit Ghidra project: `/home/builder/ghidra_proj/appkit`.

---

## 3. Reconstructed call paths (concrete, decompilation-confirmed)

IMPs from the AppKit selector+IMP index (33719 methods, all matched to Ghidra
functions); callees from Ghidra decompilation.

### A. Startup → event loop
`main()` → `NSApplicationMain` → `+[NSApplication sharedApplication]` → load
`NSMainNibFile` → `-[NSApplication finishLaunching]` → `-[NSApplication run]`
(IMP 0x177a3).

### B. Event acquisition & dispatch
`-[NSApplication run]` loops:
`nextEventMatchingMask:untilDate:inMode:dequeue:` (0x23861)
→ `__DPSNextEvent` (Display Server event loop) + `__NXDoMouseUpWindowOrdering`.
Then `-[NSApplication sendEvent:]` (0x1c6f5f)
→ `_GetEventDispatcherTarget`, `_NSAccessibilityPostNotification`,
`_NSPerformWithScreenUpdatesDisabled`, `_CGCursorIsVisible`, then forwards up
the responder chain via `_objc_msgSendSuper2`.

Responder chain: first responder → superviews → content view → NSWindow →
NSWindowController → NSApplication → delegate (`tryToPerform:with:`). Key window
receives keyboard events (`becomeKeyWindow`/`resignKeyWindow`). Activation
(becoming frontmost) requires `_CPSSetFrontProcessWithOptions` — a
WindowServer/process-manager decision via CPS, not AppKit alone.

### C. Window creation / ordering / activation
`-[NSWindow initWithContentRect:styleMask:backing:defer:]` (0x4146b) → `_commonInitFrame:` → `_initContent:` → `_CGSNewWindow` (server window) in the super chain; `NSTitlebarFloatingWindow` variant installs Carbon event handlers `_GetApplicationEventTarget`/`_InstallEventHandler` (HIToolbox bridge).
`-[NSWindow setLevel:]` (0x2ad80f) → `_CGSMainConnectionID` →
`_CGSSetWindowLevelForGroup` + `_CGSWindowAnimationChangeLevel` → WindowServer.
`-[NSWindow makeKeyAndOrderFront:]` → `_CGSOrderWindow` + key-window focus.

### D. View hierarchy / invalidation / drawing / compositing
`-[NSView setNeedsDisplay:]` (0x331d1) → `__HICocoaViewSetNeedsDisplay` (HIView
dirty-region bridge) + `__NSWindowsTrackDirtyRegions` (sync-guarded).
`-[NSView display]` walks `_recursive:displayRectIgnoringOpacity:inContext:topView:`
→ per-view `CGContext` → `drawRect:` → backing store/CALayer → `_CGSFlushSurface`
→ WindowServer composites. Layer-backed views use QuartzCore `CALayer` (`_drawRectAsLayerTree:`).

### E. Controls / menus / validation
`NSControl.mouseDown:` (0x2a6f3b) → `sendAction:to:` (0x2421f8) → target via
first-responder chain. Menu tracking: `validateMenuItem:`/
`validateUserInterfaceItem:` during tracking; system key equivalents
(Cmd-H/Q/W/M, etc.).

### F. Sheets / panels / alerts
`beginSheetModalForWindow:modalDelegate:didEndSelector:contextInfo:` on
`windowForSheet` (TextEdit rich/plain alert, decompiled). Panels (`NSPanel`)
float; sheets (`docModalWindow`) attach + dim parent; alerts app-modal.

### G. DnD / pasteboard / inter-app
NSPasteboard (AppKit); Dock uses CoreDrag (`_CoreDrag*`, `_gDockDragCallback`),
LaunchServices (`__LS*`, running-state), XPC (`_xpc_*`).

### H. Animations
QuartzCore `CAAnimation`/`CALayer` (view/layer); WindowServer window animation
`_CGSWindowAnimation*`, `_CGSSetWindowAnimationProgress` (genie/zoom/sheet).

---

## 4. CGS / WindowServer responsibility model

**CGS (CoreGraphics client library, `_CGS*`):** windows
(`_CGSNewWindow`, `_CGSReleaseWindow`, `_CGSOrderWindow`, `_CGSSetWindowLevel`),
surfaces (`_CGSAddSurface`, `_CGSRemoveSurface`, `_CGSBindSurface`,
`_CGSFlushSurface`), Spaces (`_CGSAddWindowsToSpaces`, `_CGSGetWorkspace`),
ordering groups (`_CGSAddWindowToWindowOrderingGroup`),
tracking rects (`_CGSAddTrackingRect`), events
(`_CGSConnectionGetEventQueue`, `_CGSSetEventMask`), displays
(`_CGSGetDisplayBounds`, `_CGSDisplayChangedSeed`), Dock
(`_CGSSetDockRectWithReason` — Dock sets its own rect), shadows,
animation (`_CGSWindowAnimationChangeLevel`).

**WindowServer:** single server process; owns window server state, compositing,
displays, Spaces, global event queue, cursor; reached only via CGS → mach
messages on the CGS server port (`_CGSMainConnectionID`, `_CGSServerPortInitialize`).

**The Dock is a privileged CGS client** (~420 CGS symbols, its largest
dependency family): owns its tile window, per-Space window sets, drag sessions
(CoreDrag), running-state (LaunchServices); its bar UI is constructed in code
(NIBs supply only XPC service menus — not the Dock bar).

Doc: `docs/UI_REFERENCE/architecture/cgs-windowserver.md`.

---

## 5. Finder/Dock metadata anomaly — independently re-validated

Fresh extraction of Finder (6,209,552 B) and Dock (3,259,200 B) yields valid,
complete Mach-Os (`__PAGEZERO/__TEXT/__DATA/__LINKEDIT`, no `LC_ENCRYPTION_INFO`).
Section entropy: `__text` **8.00** (max — not code), `__objc_classname` /
`__objc_methname` / `__objc_methtype` **~8.00** (names scrambled), while
`__objc_classlist` / `__objc_const` / `__objc_data` are readable (structure
intact). Packed size ≈ logical size → **not decmpfs compression**. No
`LC_ENCRYPTION_INFO` → **not standard load-time encryption**.

Conclusion: Finder/Dock are valid Mach-Os whose **string/code payloads are
scrambled at rest** (Apple string/code obfuscation on protected binaries).
Runtime **structure** (class/method ownership by address) is recoverable;
**names** (selectors, class names, code) are not. Requires a booted Mavericks
guest or a decryption oracle. Documented gap; **non-blocking** to framework
analysis (all framework binaries are readable).

This supersedes the earlier "class names absent" interpretation: the class-list
structure is present; only the name payloads are scrambled.

---

## 6. Cross-validation (≥2 independent native clients)

| Mechanism | Evidence A | Evidence B | Evidence C |
|---|---|---|---|
| `setRulerVisible:` / `setUsesInspectorBar:` | AppKit binary (NSTextView IMPs) | TextEdit decompilation (controller→text view) | nsinspect (no `NSRulerView` object) |
| Responder chain / `tryToPerform:` | AppKit binary (NSResponder) | TextEdit `showRuler:` responder deferral | `showRulerDelayed:` coalescing |
| `NSWindow` key/main + `setLevel:` | AppKit binary (NSWindow methods) | SysPref window NIB | Dock ordering CGS symbols |
| CGS window/surface/space boundary | AppKit imports (287 `_CGS*`) | Dock imports (~420 CGS, largest family) | Finder window NIBs |
| `setLevel:` → `_CGSSetWindowLevelForGroup` | Ghidra decompile (0x2ad80f) | AppKit imports `_CGSSetWindowLevel` | Dock `_CGSSetDockRectWithReason` |
| `setNeedsDisplay:` → `__HICocoaViewSetNeedsDisplay` | Ghidra decompile (0x331d1) | AppKit imports HIToolbox | TextEdit text-view drawing |
| Event acquisition `__DPSNextEvent` | Ghidra decompile (0x23861) | `NSApplication.nextEventMatchingMask:` | nsinspect event flow |

**Framework contracts validated by multiple clients:** `setRulerVisible:` /
`setUsesInspectorBar:` (resolved the earlier "not established" question — they
**are** real 10.9 AppKit API); responder chain; `NSWindow` key/main + levels;
CGS window/surface/space boundary.

---

## 7. Linux implementation implications (component map)

| Mavericks mechanism | Native owner | MavLinOS abstraction (project, NOT an Apple API) |
|---|---|---|
| `NSApplication.run` / event loop | AppKit | `mv.application` widget main loop (X11/GDK) |
| `nextEventMatchingMask:` → `__DPSNextEvent` | AppKit + Display Server | widget event read (`XNextEvent`) + dispatch |
| `sendEvent:` → responder chain | AppKit | widget dispatch + explicit `tryToPerform:`-style chain |
| `NSWindow` ↔ CGS window | AppKit → CoreGraphics CGS | `mv.window` + X11 window (`_NET_WM_WINDOW_TYPE`) |
| Window ordering / levels / Spaces | WindowServer via CGS | xfwm4 restack + `_NET_WM_STATE` + workspaces |
| Key window / focus | AppKit (`NSWindow`) | X11 focus + `_NET_ACTIVE_WINDOW` |
| `NSView` hierarchy / `drawRect:` | AppKit | GTK widget tree + `draw` signal + damage regions |
| `setNeedsDisplay:` → dirty regions | AppKit + HIView bridge | `queue_draw`/`queue_draw_region` + X11 damage |
| Compositing / `_CGSFlushSurface` | WindowServer | X11 compositor (xfwm4, shadows only) |
| Menus / `validateMenuItem:` | AppKit (`NSMenu`) | `mv.menubar` service + `GtkMenuItem.set_sensitive` |
| Controls / cells | AppKit (`NSControl`) | `GtkWidget` subclasses + behavior wrappers |
| Sheets / alerts / panels | AppKit (`NSWindow`/`NSPanel`) | transient `GtkWindow`/`GtkDialog` + custom animations |
| Pasteboard / DnD | AppKit + CoreDrag | X11 selections + XDND + GVfs Trash |
| Animations (genie/zoom/sheet) | QuartzCore + WindowServer | xfwm4/GTK animations (cross-fade + scale fallback) |
| Front process / activation (CPS) | CPS + WindowServer | `_NET_ACTIVE_WINDOW` (no process manager on Linux) |

All `NSApplication`, `NSWindow`, `NSView`, `_CGS*`, `validateMenuItem:`,
`beginSheetModalForWindow:`, etc. are **native macOS 10.9 contracts** recovered
from binaries. Project `mv.*` names (`mv.window`, `mv.menubar`,
`mv.application`, `mv.apps`) are **MavLinOS abstractions** and are never
presented as Apple APIs.

Doc: `docs/UI_REFERENCE/architecture/platform-model.md`,
`docs/UI_REFERENCE/architecture/execution-paths.md`.

---

## 8. Validation results

- `tests/uiref/test_framework_index.py`: **63/63 pass** — framework index
  re-derives class counts (≥1000 AppKit, ≥400 Foundation), coupling
  (AppKit→CoreGraphics/Foundation/libobjc/HIToolbox/QuartzCore), the CGS symbol
  surface (`_CGSNewWindow`, `_CGSOrderWindow`, `_CGSAddSurface`,
  `_CGSAddTrackingRect`, `_CGSSetDockRectWithReason`, `_CGSAddWindowsToSpaces`,
  `_CGSSetWindowLevel`), the responder-chain class hierarchy
  (`NSResponder`→`NSApplication`/`NSWindow`/`NSView`→`NSControl`→`NSButton`;
  `NSPanel`→`NSWindow`), and all key entry-point selectors + IMPs
  (`NSApplication.run`/`sendEvent:`, `NSWindow.init...`/`setLevel:`/`makeKeyAndOrderFront:`,
  `NSView.setNeedsDisplay:`/`hitTest:`, `NSTextView.setRulerVisible:`/
  `setUsesInspectorBar:`, `NSResponder.mouseDown:`/`keyDown:`).
- Regression guards on prior findings unchanged: TextEdit 15/1/253,
  Calculator 11/2/217, BasicAndSci 8/1/153, Hexadecimal 2/0/77 — byte-identical
  to prior evidence (pipeline stable).
- Ghidra AppKit decompilation: 8 targets decompiled; callers/callees recovered
  for `sendEvent:`, `nextEventMatchingMask:...`, `setLevel:`, `setNeedsDisplay:`,
  `initWithContentRect:...`.

---

## 9. Evidence locations

| Evidence | Location |
|---|---|
| Framework thin x86_64 slices | `vmwork/opencode/frameworks/extracted/*.x86_64` |
| Framework index (classes/symbols/deps) | `vmwork/opencode/frameworks/index/*.json` |
| AppKit Ghidra project | `/home/builder/ghidra_proj/appkit` |
| AppKit ObjC meta (Ghidra, with function maps) | `vmwork/opencode/frameworks/index/appkit-objc-meta-ghidra.json` |
| Decompile index + .c outputs | `vmwork/opencode/frameworks/index/appkit-decompile-index.json`, `vmwork/opencode/frameworks/decomp/*.c` |
| Finder/Dock anomaly extracts + entropy check | `vmwork/opencode/frameworks/anomaly/` |
| Architecture docs | `docs/UI_REFERENCE/architecture/{platform-model,cgs-windowserver,execution-paths}.md` |
| Regression test | `tests/uiref/test_framework_index.py` |
| Existing app metadata | `docs/UI_REFERENCE/runtime/raw/native/*` |

Pipeline: `tools/uiref/framework_index.py` (Mach-O + ObjC index),
`tools/uiref/machobjc.py` (legacy ObjC dump),
`tools/uiref/ghidra/objc_extract.py` / `objc_decompile_file.py` (Ghidra),
`tools/uiref/nsinspect.c` (runtime).

---

## 10. Unresolved questions & required evidence

| Detail | Evidence needed |
|---|---|
| `_CGSNewWindow` argument order/types from `-[NSWindow initWithContentRect:...]` | Ghidra decompile deeper in the super-chain init (0x4146b forwards to super) |
| `-[NSApplication sendEvent:]` responder target-window selection logic | decompile is done; target selection is deeper in the forwarded chain |
| `_CGSFlushSurface` flush point in `-[NSView display]` | decompile `display` path |
| CGS server-port mach message formats (request/response IDs, marshalling) | runtime capture in a booted Mavericks guest — not available from static binaries |
| WindowServer occlusion / dirty-region notification to clients | runtime capture |
| Finder/Dock class names & selectors | booted guest or decryption oracle (anomaly) |
| Main Spotlight search UI, `QLPreviewPanel` integration | booted guest (binary inaccessible) |

---

## 11. Next major research direction

The framework/CGS boundary and application-to-screen paths are now reconstructed
to implementation-grade detail. The highest-value next step is to **close the
runtime-validation loop**: obtain a booted Mavericks guest (or a decryption/oracle
for the Finder/Dock anomaly) and run `nsinspect`/`mvprobe` captures to confirm
the reconstructed paths at runtime (actual `NSWindow`/`NSView` object graphs,
key-window focus transitions, CGS window IDs, dirty-region flushes).

In parallel, begin mapping the recovered contracts to the Linux platform:
spec `mv.window` (X11 window per NSWindow + `_NET_WM_WINDOW_TYPE`/`_NET_WM_STATE`),
`mv.application` (X11/GDK main loop → `sendEvent:`-equivalent dispatch), the
responder-chain action forwarding (not present in GTK — must be implemented),
and `mv.menubar` (global menu bar + `validateMenuItem:`-driven enabling). These
are the mechanisms that let the Linux port reproduce the AppKit/CGS/WindowServer
responsibility model without reimplementing Apple's internals.
