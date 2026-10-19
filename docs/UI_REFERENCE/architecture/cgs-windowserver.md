# MavLinOS platform model — CoreGraphics Services (CGS) / WindowServer boundary

**Status:** implementation-grade reference (evidence-backed).  
**Sources:** CoreGraphics framework imported-symbol table (287 `_CGS*` symbols
imported by AppKit; 1616 `_CGS*` defined in CoreGraphics), Dock imported symbols
(420 CGS symbols, the largest dependency family), Finder/AppKit NSWindow NIBs,
and the AppKit class/method index. Raw evidence:
`vmwork/opencode/frameworks/index/{CoreGraphics,AppKit,Dock}.x86_64.json`,
`docs/UI_REFERENCE/native-findings.md` (F9/F11).

**Conventions:** **[BIN]** = static binary evidence. **[INFERRED]** = reasoned
interpretation. Native CGS/WindowServer APIs are quoted as symbol names;
project `mv.*` names are explicitly project abstractions.

---

## 1. The boundary in one sentence

AppKit (and every GUI application, including the Dock) is a **CGS client**.
WindowServer is the single server process. AppKit never addresses WindowServer
directly by name; it calls the C functions in the `_CGS*` family exported by
CoreGraphics, which marshal requests into mach messages on the CGS server port
and (for results) read replies back. WindowServer owns the window server state,
compositing, displays, and Spaces; CGS is the client-side IPC stub library.

## 2. What the symbol surface proves (measured, **[BIN]**)

CoreGraphics defines **1616 `_CGS*` symbols**. AppKit imports **287** of them
(undefined symbols). The Dock imports ~420 CGS symbols — its largest dependency
family — confirming the Dock is *first and foremost* a WindowServer client, not
a standalone view.

Categorization of the `_CGS*` surface (from CoreGraphics defined symbols):

| Category | Count | Representative symbols | What it controls |
|---|---:|---|---|
| connection / server | ~70 | `_CGSConnectionInitialize`, `_CGSServerPortInitialize`, `_CGSMainConnectionID`, `_CGSServerOperationState` | CGS client→server channel |
| window | 344 | `_CGSNewWindow`, `_CGSReleaseWindow`, `_CGSOrderWindow`, `_CGSGetWindowBounds`, `_CGSGetWindowLevel`, `_CGSSetWindowLevel`, `_CGSSetWindowOpacity`, `_CGSSetWindowTransform`, `_CGSGetWindowOwner`, `_CGSGetWindowType`, `_CGSGetWindowWorkspaceIgnoringVisibility` | create/destroy/order/geometry/level/owner/type |
| surface | 36 | `_CGSAddSurface`, `_CGSRemoveSurface`, `_CGSBindSurface`, `_CGSFlushSurface`, `_CGSGetSurfaceBounds` | backing stores / surfaces |
| space / Spaces | 81 (incl. color-space false positives) | `_CGSAddWindowsToSpaces`, `_CGSRemoveWindowsFromSpaces`, `_CGSGetWorkspace`, `_CGSGetSpaceManagementMode`, `_CGSSpaceCopyName`, `_CGSSpaceSetShape` | Spaces membership + shapes |
| group / ordering | 146 | `_CGSAddWindowFilter`, `_CGSAddWindowToWindowOrderingGroup`, `_CGSReorderWindows`, `_CGSGetWorkspaceWindowGroup` | window groups + global ordering |
| tracking | 14 | `_CGSAddTrackingRect`, `_CGSAddTrackingAreas`, `_CGSRemoveTrackingArea`, `_CGSSetTrackingAreaClip/Enabled/Option/Rect` | mouse tracking rectangles |
| event | 283 | `_CGSEventInitialize`, `_CGSConnectionGetEventQueue`, `_CGSEventQueueCreate`, `_CGSSetEventMask`, `_CGSGetCurrentMouseButtonState`, `_CGSRegisterConnectionEventDatagramHandler` | event queue + input state |
| display | 140 | `_CGSDisplayInitialize`, `_CGSGetDisplayBounds`, `_CGSGetNumberOfDisplays`, `_CGSGetActiveDisplayList`, `_CGSGetDisplaysWithRect`, `_CGSDisplayChangedSeed` | displays + geometry propagation |
| dock | 2 | `_CGSGetDockRectWithReason`, `_CGSSetDockRectWithReason` | Dock tile rect (privileged) |
| shadow | 9 | `_CGSSetWindowShadowParameters`, `_CGSSetWindowShadowAndRimParameters`, `_CGStyleCreateShadow*` | window shadows/rims |
| animation | 6 | `_CGSWindowAnimationChangeLevel`, `_CGSWindowAnimationChangeShiftPoint`, `_CGSWindowAnimationHideSlot`, `_CGSWindowAnimationSetParent`, `_CGSSetWindowAnimationProgress` | WindowServer-driven window animation |
| cursor | ~8 | `_CGSShowCursor`, `_CGSHideCursor`, `_CGSRegisterCursorWithImages`, `_CGSObscureCursor`, `_CGSRevealCursor` | cursor |
| shared memory | ~12 | `_CGSShmemCreateMappedMemory`, `_CGSShmemRWLockLockForReading`, `_CGSShmemReferenceResolve` | shared backing-store memory |

**Key architectural facts established by the symbol surface:**

1. **WindowServer is the ordering authority.** `_CGSOrderWindow`, `_CGSOrderSurface`, `_CGSReorderWindows`, `_CGSAddWindowToWindowOrderingGroup`, `_CGSGetWorkspaceWindowGroup` — all ordering operations go through CGS→WindowServer. AppKit's `NSWindow.orderFront:`/`orderBack:`/`setLevel:` are thin wrappers around these.

2. **Surfaces are separate from windows.** `_CGSAddSurface`/`_CGSRemoveSurface`/`_CGSBindSurface`/`_CGSFlushSurface` — a CGS surface is a backing store; a window references one or more surfaces. `_CGSFlushSurface` is the flush point AppKit uses after drawing into a view's CGContext.

3. **Spaces are server-managed window membership.** `_CGSAddWindowsToSpaces`/`_CGSRemoveWindowsFromSpaces` assign windows to Spaces; `_CGSGetWorkspaceWindowGroup` is the group for a workspace. The Dock uses these to manage per-Space window sets.

4. **Tracking rects are server-side.** `_CGSAddTrackingRect`/`_CGSRemoveTrackingArea` — mouse-tracking regions live in WindowServer, which reports enter/exit/moved events back to the client. This is how `NSTrackingArea` / hover works without polling.

5. **The Dock is a privileged CGS client.** `_CGSSetDockRectWithReason` lets the Dock set its own rect; `_CGSGetDockRectWithReason` reads it. The Dock imports CoreDrag and LaunchServices for DnD and running-state. The Dock bar is drawn in code (not NIB-driven — see F6.3).

## 3. How geometry, visibility, occlusion, and display changes propagate

**[INFERRED]** from the symbol surface + AppKit method surface:

- Geometry changes: `NSWindow.setFrame:display:animate:` → `_CGSSetWindowTransform` / `_CGSOrderWindow` → WindowServer updates the window's server rect; damage region marked dirty.
- Visibility: `orderFront:`/`orderBack:` → `_CGSOrderWindow`; `setLevel:` → `_CGSSetWindowLevel`; WindowServer re-sorts the window list and re-composites affected regions.
- Occlusion: WindowServer maintains the occlusion tree from the window list + levels + shapes; when a window moves/resizes, WindowServer computes newly-occluded/visible regions and notifies clients with dirty regions (AppKit invalidates corresponding `NSView`s via `setNeedsDisplayInRect:`).
- Display changes: `_CGSDisplayChangedSeed`, `_CGSDisplayMappingChangedSeed`, `_CGSGetDisplaysWithRect` — when a display is added/removed/reconfigured, the seed changes; WindowServer notifies CGS clients; AppKit re-queries `_CGSGetDisplayBounds` and reshapes windows (e.g., zoom-to-screen).

## 4. Events and focus interaction with window state

- Event acquisition: AppKit `-[NSApplication nextEventMatchingMask:untilDate:inMode:dequeue:]` blocks on `_CGSConnectionGetEventQueue` / the CGS event queue (mach datagram from WindowServer). WindowServer timestamps and coalesces events (`_CGSEventQueueGetCoalesceMask`).
- Focus: key-window transitions (`becomeKeyWindow`/`resignKeyWindow`) are negotiated with WindowServer via CPS (`_CPSSetFrontProcessWithOptions` to become frontmost) + CGS (`_CGSGetActiveMenuBarDrawingStyle`, `_CGSSetMenuBarDrawingStyle` for the menu bar). Only the key window gets keyboard events; only the frontmost process gets menu-bar events.
- Tracking rects: WindowServer reports cursor enter/exit/motion for registered `_CGSAddTrackingRect` regions → AppKit delivers `mouseEntered:`/`mouseExited:`/`mouseMoved:` to the right view.

## 5. Public vs private vs IPC-delegated

| Tier | Examples | Who owns |
|---|---|---|
| Public C (CoreGraphics API) | `CGWindow...` (limited); most window ops are private `_CGS*` | CoreGraphics framework |
| Private C (`_CGS*`) | all 287 above | CoreGraphics → WindowServer IPC |
| IPC | mach messages on CGS server port (connection init, request/response) | WindowServer (server) + CGS (client stub) |
| Compositing | WindowServer composites surfaces to display | WindowServer (not reachable via public API) |
| Animation | `_CGSWindowAnimation*`, QuartzCore `CAAnimation` | WindowServer (window-level) + QuartzCore (view/layer-level) |

**There is no public API to WindowServer.** All window-server interaction is via the private `_CGS*` C API. This is the interface MavLinOS's `mv.window` / compositor abstraction must replicate on Linux (X11: `_NET_WM_WINDOW_TYPE`, `_NET_WM_STATE`, `_NET_ACTIVE_WINDOW`, `XRestackWindows`, `XShape`, damage regions; compositor: shadows, animations).

## 6. Dock as evidence of CGS-client responsibilities

The Dock's imported-symbol map (F9) shows its real work:
- Windows/surfaces/spaces: `_CGSAddWindowsToSpaces`, `_CGSGetWorkspaceWindowGroup`, `_CGSAddSurface`, `_CGSSetDockRectWithReason`
- Running applications: LaunchServices `__LS*`, `__kLS*`, `_kCSBackupdKeyIsRunning`
- Drag and drop: CoreDrag `_CoreDrag*`, `_gDockDragCallback`, `_gDockDragWindowCallback`
- Menus: Carbon `_AppendMenuItemTextWithCFString`, `_CreateNewMenu`, etc.
- Inter-process: XPC `_xpc_*`

**Conclusion:** the Dock manages its own tile window, per-Space window sets, drag sessions, and running-state via CGS + LaunchServices + CoreDrag + XPC. Its UI (icons, magnification, indicators) is constructed in code (its NIBs only supply XPC service menus — F6.3). MavLinOS's Dock analogue must therefore be a CGS-client-like component: own an X11 window, track running apps, handle DnD, set its own dock rect equivalent, composite its own surface.

## 7. Linux implementation implications

| CGS/WindowServer concept | Linux (X11/xfwm4) equivalent | Notes |
|---|---|---|
| CGS window (server-side surface) | X11 Window + server-side pixmap/backing store | `mv.window` owns it |
| `_CGSNewWindow`/`_CGSReleaseWindow` | `XCreateWindow`/`XDestroyWindow` | widget layer |
| `_CGSOrderWindow`/levels | `XRestackWindows` + `_NET_WM_STATE`/`_NET_WM_WINDOW_TYPE` | xfwm4 manages; widget requests |
| `_CGSAddSurface`/`_CGSFlushSurface` | window backing store + `XDamage`/composite damage | compositor composites |
| `_CGSAddWindowsToSpaces`/Spaces | virtual desktops (xfwm4 workspaces) | `mv.windows` tracks membership |
| `_CGSAddTrackingRect` | X11 `XSelectInput` motion/enter/leave + `XFixes` | widget tracking |
| `_CGSSetDockRectWithReason` (Dock) | dock/strut (`_NET_WM_STRUT_PARTIAL`) + dock window | Dock analogue owns it |
| `_CGSGetNumberOfDisplays`/`_CGSGetDisplayBounds` | Xinerama/Randr | `mv.displays` |
| WindowServer compositing | xfwm4 compositing (shadows only) | heavy effects off per stack |
| `_CGSWindowAnimation*` | xfwm4 window animations or custom GTK animation | minimize/zoom/sheet |

## 8. Unresolved details

| Detail | Evidence needed |
|---|---|
| CGS server-port mach message formats (request/response ids, argument marshalling) | not in static binaries; requires runtime capture in a booted Mavericks guest or documentation |
| Exact argument order/types of `_CGSNewWindow`, `_CGSOrderWindow`, `_CGSFlushSurface` | Ghidra decompile of AppKit callers (in progress) |
| WindowServer's occlusion/dirty-region notification mechanism to clients | runtime capture |
| Whether CGS uses shared memory (`_CGSShmem*`) for backing stores | symbol present; usage not confirmed |
