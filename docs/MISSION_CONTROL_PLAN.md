# Mission Control — Dedicated Window-Overview Layer Plan

**Status:** IMPLEMENTATION — O1/O2 complete; O3 thumbnail backend implemented  
**Date:** 2026-10-05  
**Trigger:** Owner issue #1 — major work starts with DESIGN: target architecture + migration boundary first, implementation after.  
**Baseline:** `packages/mavericks-apps/src/mavericks-apps/bin/mv-mission-control` (wmctrl+rofi) + `configs/profiles/experiments/E-MC-skippy-xd.sh` (skippy-xd one-shot, not in ISO).

---

## 1. Fidelity-Ceiling Evidence: rofi/wmctrl

The current Mission Control path is `mv-mission-control` — a Python script that enumerates windows via `wmctrl -l -x` and renders them as a **text list** inside rofi script mode. The rofi theme (`rofi-mission-control.rasi`) is a flat, modern list with a search bar.

### Concrete Mavericks behaviors rofi/wmctrl cannot do

| # | Mavericks Behavior | rofi/wmctrl capability | Proof |
|---|---|---|---|
| 1 | **Live window thumbnails** — shows actual window content as scaled previews | wmctrl returns text only (id, desktop, class, title). No X11 composite access. rofi renders text strings. | `wmctrl -l -x` output format: `0x04a00003  0  thunar  host  Title`. No pixel data. rofi `element-text` is a string renderer. |
| 2 | **Spatial grid layout** — windows laid out non-overlapping, scaled to fit screen, preserving relative positions | rofi is a vertical list (`listview { lines: 20; columns: 1; }`). No grid layout, no spatial arrangement. | `rofi-mission-control.rasi` line 53: `columns: 1`. No grid mode exists in rofi script mode. |
| 3 | **Open/close animation** — windows fly out from their current positions into the grid; reverse on close | rofi appears/disappears instantly. No window-position awareness, no animation API. | rofi has no concept of source/destination geometry. No X11 window-position query in `mv-mission-control`. |
| 4 | **Workspace thumbnails (Spaces bar)** — workspaces shown as live thumbnails at top of screen | rofi groups windows by text labels ("Desktop 0 ●", "Desktop 1"). No workspace preview. | `mv-mission-control` lines 328-337: workspace headers are text strings. No workspace content capture. |
| 5 | **Drag-and-drop between workspaces** — drag a window thumbnail to another workspace | rofi has no drag-and-drop. wmctrl can move windows (`-t`) but rofi cannot initiate DnD. | rofi script mode has no DnD API. `mv-mission-control` has no DnD handler. |
| 6 | **Live content updates** — thumbnails update in real time (video playback, animations) | rofi list is static while open. No refresh mechanism. | `mv-mission-control` builds the list once at startup. No timer, no X11 damage event subscription. |
| 7 | **Minimized window thumbnails** — minimized windows shown as small previews | wmctrl lists minimized windows as regular text entries. No thumbnail capture possible. | `wmctrl -l` shows minimized windows with same format. No X11 composite = no thumbnail. |
| 8 | **Fullscreen app representation** — fullscreen apps shown as workspace thumbnails | rofi lists fullscreen apps as regular list items. No special handling. | `mv-mission-control` has no fullscreen detection (no `_NET_WM_STATE_FULLSCREEN` check). |
| 9 | **Multi-monitor layout** — overview spans all displays | rofi creates a single window. No multi-monitor awareness. | rofi `window` block has single `width`/`height`. No Xinerama/multi-head support in script mode. |
| 10 | **Mavericks visual styling** — skeuomorphic thumbnails with shadows, reflections, glass | rofi theme is flat modern (rgba whites, `#007aff` blue accent, no textures). | `rofi-mission-control.rasi`: `background: rgba(245,245,245,0.98)`, `accent: #007aff` — flat iOS-style, not Mavericks. |

### skippy-xd ceiling (current E-MC experiment)

skippy-xd can capture thumbnails via XComposite, but:

| Limitation | Impact |
|---|---|
| No Mavericks visual styling — plain X11 expose with default GTK2 look | Fails Perceptual Fidelity Target (§3.10) |
| No workspace management UI — just shows all windows on current desktop | Cannot replace Spaces bar |
| No animations — windows appear/disappear instantly | Missing signature Mavericks transition |
| No drag-and-drop between workspaces | Cannot move windows via overview |
| AUR-only (`skippy-xd-git`), not in ISO | Not available by default; requires manual install |
| Daemon-based (though one-shot `--expose` works) | §7 prefers one-shot; daemon model risks resident wakeups |
| No hotkey/menu-bar/Dock integration | Standalone tool, not integrated into MavLinOS desktop |
| No Mavericks-style window grouping or labeling | Windows shown without context |

### Conclusion

The rofi/wmctrl path has a **hard fidelity ceiling**: it is fundamentally a text list with no access to window pixels, no spatial layout, no animation, and no workspace model. skippy-xd addresses thumbnails but fails on styling, integration, workspace model, and packaging. Neither can reach the Perceptual Fidelity Target (§3.10) for Mission Control.

---

## 2. GO/NO-GO Verdict

**GO — dedicated overview layer is required.**

Rationale:
- The fidelity ceiling is **structural** (no X11 composite access in wmctrl/rofi), not a matter of configuration or polish.
- skippy-xd is a **partial** solution (thumbnails only) with significant gaps (styling, integration, packaging, workspace model).
- A dedicated layer can be designed from the ground up for Mavericks fidelity, MavLinOS integration, and §7 power constraints.
- The migration can be incremental — rofi fallback preserved at every step.

---

## 3. Target Architecture

### 3.1 Overview

A **one-shot Python/GTK3 overlay** that captures window thumbnails via XComposite and renders them in a full-screen Mavericks-style grid. No daemon, no polling, no resident process. Exits on selection or Escape.

### 3.2 Component stack

```
mv-mc-overview (one-shot Python/GTK3)
├── Window enumeration: EWMH via Gdk (Gdk.Screen.get_default().get_window_stack())
│   fallback: wmctrl -l -x (for workspace assignment)
├── Thumbnail capture: XComposite via ctypes → libXcomposite
│   XCompositeGetWindowPixmap → GdkPixbuf from X11 pixmap
├── Layout engine: pure-Python grid math (testable without X11)
│   - Workspace grouping
│   - Non-overlapping grid with aspect-ratio preservation
│   - Mavericks-style spacing, shadows, labels
├── Rendering: Gtk3 overlay window (full-screen, transparent, decorated=False)
│   - Gtk.DrawingArea with Cairo for custom rendering
│   - OR Gtk.Fixed with Gtk.Image widgets per thumbnail
├── Input: Gtk event handling
│   - Click thumbnail → activate window (wmctrl -i -a or EWMH _NET_ACTIVE_WINDOW)
│   - Arrow keys → navigate grid
│   - Enter → activate selected
│   - Escape → close
│   - Workspace thumbnails → switch workspace
└── Exit: process terminates on selection/Escape (no daemon)
```

### 3.3 Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python3 | Consistent with existing mavericks-apps; GTK3 via PyGObject; ctypes for XComposite |
| X11 access | Gdk (enumeration) + ctypes/libXcomposite (thumbnails) | Gdk already links X11; avoids adding python-xlib dependency |
| Rendering | Gtk.DrawingArea + Cairo | Full control over Mavericks styling (shadows, reflections, glass); no GTK widget constraints |
| Window model | EWMH (_NET_CLIENT_LIST, _NET_WM_NAME, _NET_WM_STATE, _NET_WM_DESKTOP) | Standard X11, no wmctrl dependency for core path |
| Thumbnail capture | XCompositeGetWindowPixmap → Gdk.Pixbuf | Only way to get window content without compositor; used by skippy-xd |
| Workspace model | _NET_WM_DESKTOP per window + _NET_CURRENT_DESKTOP | Standard EWMH; no wmctrl needed |
| Animation | Cairo-based interpolation (thumbnail positions lerp from window screen positions to grid positions) | One-shot animation, no compositor needed; ~150ms |
| Process model | One-shot: enumerate → capture → render → wait for input → activate → exit | §7: no daemon, no polling, no resident wakeups |
| Fallback | mv-mission-control (rofi) if mv-mission-control --native fails or mv-mc-overview unavailable | Preserves current behavior during migration |

### 3.4 Performance budget (§7 compliance)

| Metric | Budget | Justification |
|---|---|---|
| Idle CPU | 0% | Process exits after selection/Escape |
| Idle memory | 0 MB | No resident process |
| Open latency | < 500ms for 12 windows | One-shot XComposite capture + GTK render |
| Thumbnail memory | ~80 MB peak (12 windows × ~6 MB pixbuf) | Acceptable for one-shot; freed on exit |
| Wakeups | 0 at idle | No timers, no polling, no D-Bus signals |
| Animation | 150ms, 60fps Cairo | Brief CPU spike during transition only |

### 3.5 Thumbnail capture strategy

1. **Redirect window** (XCompositeRedirectWindow) — required for off-screen windows
2. **Get pixmap** (XCompositeGetWindowPixmap) — returns X11 pixmap ID
3. **Convert to GdkPixbuf** — via `Gdk.pixbuf_get_from_surface()` or Cairo X11 surface
4. **Scale** — preserve aspect ratio, fit within grid cell
5. **Cache** — keep in memory for session duration (no disk cache needed for one-shot)

**Minimized windows**: XComposite cannot capture minimized windows. Fallback: show placeholder with window title + icon (same as current rofi behavior). This is a known limitation to document.

**Windows on other workspaces**: XComposite can capture windows on other workspaces if they are mapped. Unmapped windows (on inactive workspaces) need the workspace-visit approach (like current `run_native_expose`) OR accept that only current-workspace windows show thumbnails. **Design decision**: capture current workspace via XComposite; for other workspaces, use the ephemeral workspace-visit approach (switch → capture → switch back) with a timeout. This is a P1 refinement — P0 can show current workspace only.

---

## 4. Migration Boundary + Compatibility

### 4.1 What is preserved

| Component | Status | Notes |
|---|---|---|
| `mv-mission-control` (rofi script mode) | **Preserved as fallback** | Remains in ISO; used when mv-mc-overview fails or is absent |
| `rofi-mission-control.rasi` | **Preserved** | Still used by rofi fallback path |
| `wmctrl` + `xorg-xprop` in ISO | **Preserved** | Used by fallback path and by mv-mc-overview for activation |
| `skippy-xd` E-MC experiment | **Retired after migration** | Superseded by mv-mc-overview; E-MC config kept for reference |
| Super+Tab hotkey binding | **Preserved** | Binding target changes from `mv-mission-control --native` to `mv-mc-overview` with fallback |

### 4.2 Migration phases

```
Phase A (current):  Super+Tab → mv-mission-control --native
                      → tries skippy-xd (if installed) → falls back to rofi

Phase B (migration): Super+Tab → mv-mc-overview
                      → if mv-mc-overview fails → mv-mission-control --native
                      → if that fails → rofi script mode

Phase C (complete):  Super+Tab → mv-mc-overview
                      → if mv-mc-overview fails → mv-mission-control (rofi only)
                      → skippy-xd E-MC retired
```

### 4.3 Compatibility contract

- `mv-mc-overview` must exit 0 on successful activation, non-zero on failure/cancel.
- On non-zero exit, the hotkey binding falls back to `mv-mission-control --native`.
- `mv-mc-overview` must not leave windows in a broken state (no partial activation).
- `mv-mc-overview` must work on Xvfb (for testing) and on real X11 with xfwm4.

---

## 5. Ordered Objective Sequence

Each objective is independently testable. Do not proceed to N+1 until N passes its acceptance criteria.

### O1: Read-only window enumeration

**Goal:** List all windows with metadata (id, title, class, workspace, geometry, minimized state) without any UI.

**Implementation:** Python module using Gdk EWMH + fallback to wmctrl.

**Acceptance criteria:**
  
- [ ] Returns list of all mapped windows across all workspaces  
- [ ] Each window has: X11 id, title, WM_CLASS, workspace number, geometry (x, y, w, h), minimized flag  
- [ ] Works on Xvfb with 3+ test windows  
- [ ] Works headless (unit test with mocked Gdk)  
- [ ] No UI rendered, no windows activated  

**Test:** `scripts/test-mc-overview-enumerate.py` — creates Xvfb, opens test windows, verifies enumeration.

### O2: Layout model (grid math)

**Goal:** Pure-Python layout engine that computes non-overlapping thumbnail positions given window list + screen dimensions.

**Implementation:** `mv_mc_layout.py` — no X11 dependency, fully unit-testable.

**Acceptance criteria:**  
- [ ] Given N windows + screen size, produces N non-overlapping rectangles  
- [ ] Rectangles preserve window aspect ratios  
- [ ] Windows grouped by workspace (workspace sections stacked vertically)  
- [ ] Active workspace rendered first (top)  
- [ ] Empty workspaces shown as placeholder rectangles  
- [ ] Layout adapts to screen size (more windows → smaller thumbnails)  
- [ ] Deterministic output for same input  

**Test:** `scripts/test-mc-layout.py` — 20+ unit tests with various window counts, screen sizes, workspace configurations.

### O3: Thumbnail capture

**Goal:** Capture window content as GdkPixbuf via XComposite.

**Implementation:** ctypes → libXcomposite + libX11, convert X11 pixmap to GdkPixbuf.

**Acceptance criteria:**  
- [x] Captures a mapped window's content as a pixbuf  
- [x] Returns correct dimensions matching window size  
- [x] Handles 16/24/32-bit XImage channel layouts; alpha is intentionally flattened to RGB  
- [x] Graceful failure for minimized/unmapped windows (returns None → placeholder)  
- [ ] Works on Xvfb (XComposite available) — hardware/CI validation still required  
- [x] No window state modification (XCompositeNameWindowPixmap + XGetImage are read-only)  

**Test:** `scripts/test-mc-thumbnail.py` — Xvfb + test window, capture, verify pixbuf dimensions.

### O4: Focus/activation

**Goal:** Activate a window by X11 id (focus + raise + switch workspace if needed).

**Implementation:** EWMH `_NET_ACTIVE_WINDOW` ClientMessage + wmctrl fallback.

**Acceptance criteria:**  
- [ ] Activating a window on current workspace focuses it  
- [ ] Activating a window on another workspace switches to that workspace first  
- [ ] Activation works for minimized windows (unminimize + focus)  
- [ ] No-op for already-active window  
- [ ] Returns success/failure  

**Test:** `scripts/test-mc-activate.py` — Xvfb + test windows, activate, verify focus.

### O5: Workspace model

**Goal:** Show workspace thumbnails at top; clicking one switches workspace.

**Implementation:** EWMH `_NET_CURRENT_DESKTOP` + `_NET_NUMBER_OF_DESKTOPS`; workspace thumbnails via same XComposite capture.

**Acceptance criteria:**  
- [ ] Shows all workspaces as thumbnails at top of overview  
- [ ] Active workspace highlighted  
- [ ] Clicking workspace thumbnail switches to it  
- [ ] Empty workspaces shown as empty placeholders  
- [ ] Workspace count matches wmctrl -d  

**Test:** `scripts/test-mc-workspaces.py` — Xvfb + multiple workspaces, verify switching.

### O6: Transitions (animation)

**Goal**: Animate thumbnails from window screen positions to grid positions on open; reverse on close.

**Implementation:** Cairo interpolation over 150ms; each thumbnail's start position = window's actual screen position, end position = grid cell.

**Acceptance criteria:**  
- [ ] On open, thumbnails animate from window positions to grid positions  
- [ ] Animation completes in 150ms ± 20ms  
- [ ] On close (Escape), thumbnails animate back to window positions  
- [ ] Animation is smooth (no visible jank on Xvfb)  
- [ ] No animation if reduced-motion preference set  

**Test:** `scripts/test-mc-animation.py` — verify animation timing and positions (mocked time).

### O7: Input handling

**Goal:** Full keyboard + mouse input for overview navigation.

**Implementation:** Gtk event handlers on overlay window.

**Acceptance criteria:**  
- [ ] Mouse click on thumbnail → activate window, close overview  
- [ ] Arrow keys → move selection highlight between thumbnails  
- [ ] Enter → activate selected thumbnail  
- [ ] Escape → close overview without activating  
- [ ] Tab → cycle through thumbnails  
- [ ] Click on workspace thumbnail → switch workspace, stay in overview  
- [ ] Click on empty area → close overview  
- [ ] Selection highlight visible and follows Mavericks style  

**Test:** `scripts/test-mc-input.py` — Xvfb + simulated events (XTEST via xdotool), verify behavior.

### O8: Desktop integration

**Goal:** Wire mv-mc-overview into MavLinOS desktop (hotkey, menu bar, Dock).

**Implementation:** Update `xfce4-keyboard-shortcuts.xml`, add menu bar item, add Dock launcher.

**Acceptance criteria:**  
- [ ] Super+Tab invokes mv-mc-overview  
- [ ] Menu bar has Mission Control item (or is accessible via Control Center)  
- [ ] Dock has Mission Control launcher  
- [ ] Fallback to mv-mission-control works if mv-mc-overview fails  
- [ ] No conflict with existing Super+Tab binding  

**Test:** `scripts/test-mc-integration.py` — verify binding, fallback, no conflicts.

### O9: Visual polish (Mavericks fidelity)

**Goal:** Apply Mavericks visual language to overview.

**Implementation:** Cairo rendering with Mavericks-style shadows, glass, reflections, workspace labels.

**Acceptance criteria:**  
- [ ] Thumbnails have Mavericks-style drop shadows  
- [ ] Workspace labels use Mavericks font and styling  
- [ ] Background is Mavericks-style translucent dark (not flat white)  
- [ ] Selection highlight uses Mavericks blue  
- [ ] Spacing and proportions match Mavericks  
- [ ] No flat/modern styling remnants  

**Test:** Visual inspection + screenshot comparison (manual, documented in NEEDS_HARDWARE_TEST.md).

### O10: Retire rofi path

**Goal:** Remove rofi fallback, make mv-mc-overview the sole Mission Control path.

**Implementation:** Update hotkey binding, remove skippy-xd E-MC, update docs.

**Acceptance criteria:**  
- [ ] Super+Tab invokes mv-mc-overview only  
- [ ] mv-mission-control (rofi) removed from ISO OR kept as emergency fallback only  
- [ ] skippy-xd E-MC experiment retired  
- [ ] APPS.md updated  
- [ ] No regression: Mission Control still works  

**Test:** Full regression — `scripts/check-sync.sh` green.

---

## 6. Rollback / Fallback Strategy

### 6.1 Fallback chain (during migration)

```
Super+Tab pressed
  → try mv-mc-overview
    → success: done
    → failure: try mv-mission-control --native
      → success: done
      → failure: try rofi script mode (mv-mission-control)
        → success: done
        → failure: show error notification
```

### 6.2 Rollback triggers

- mv-mc-overview crashes on open → automatic fallback to rofi path
- mv-mc-overview produces visual artifacts → revert hotkey binding to `mv-mission-control --native`
- mv-mc-overview causes X11 instability → remove from ISO, restore rofi-only path

### 6.3 Rollback procedure

1. Revert hotkey binding: `xfconf-query -c xfce4-keyboard-shortcuts -p /commands/default/<Super>Tab -s "mv-mission-control --native"`
2. Remove mv-mc-overview from ISO packages list
3. Restore mv-mission-control as primary path
4. Document rollback reason in DECISIONS.md

### 6.4 skippy-xd retirement

- E-MC experiment config kept in `configs/profiles/experiments/` for reference
- skippy-xd removed from any ISO package list (it was never in default ISO)
- E-MC section in NEEDS_HARDWARE_TEST.md marked as SUPERSEDED

---

## 7. Test Strategy

### 7.1 Headless testing (Xvfb)

All tests use `scripts/gui-isolation.sh` discipline:
- `source scripts/gui-isolation.sh`
- `mv_gui_isolate` — capture host display as FORBIDDEN
- `mv_gui_pin_display` — pin to Xvfb :97
- Tests create their own test windows on Xvfb
- `mv_gui_report` — verify 0 host-display violations

### 7.2 Test windows

Tests create real X11 windows using `xterm` or a minimal GTK test app:
```bash
xterm -geometry 80x24+100+100 &
xterm -geometry 80x24+300+200 &
# ... etc
```

### 7.3 Test files

| File | Objective | Type |
|---|---|---|
| `scripts/test-mc-enumerate.py` | O1 | Unit + integration |
| `scripts/test-mc-layout.py` | O2 | Unit (no X11) |
| `scripts/test-mc-thumbnail.py` | O3 | Integration (Xvfb) |
| `scripts/test-mc-activate.py` | O4 | Integration (Xvfb) |
| `scripts/test-mc-workspaces.py` | O5 | Integration (Xvfb) |
| `scripts/test-mc-animation.py` | O6 | Unit (mocked time) |
| `scripts/test-mc-input.py` | O7 | Integration (Xvfb + xdotool) |
| `scripts/test-mc-integration.py` | O8 | Integration (Xvfb) |
| `scripts/test-mc-visual.py` | O9 | Manual (screenshot) |

### 7.4 CI integration

- All tests wired into `scripts/check-sync.sh`
- Tests run on Xvfb :97 (never host display)
- Guard violations = test failure
- Tests must pass before commit

### 7.5 No host windows guarantee

- `gui-isolation.sh` guard aborts any process that touches host display
- Tests use dedicated Xvfb display `:97`
- `mv_gui_report` verifies 0 violations
- WSLg host display `:0` is FORBIDDEN

---

## 8. Hardware-Validation Items

These items **cannot** be validated pre-hardware and must be tested on MacBook10,1:

| # | Item | Why hardware needed |
|---|---|---|
| H1 | Thumbnail fidelity on 2304×1440 HiDPI | Xvfb does not test HiDPI rendering, scaling, or font clarity |
| H2 | Animation performance on Intel HD 615 | Xvfb has no GPU; real GPU needed to measure frame times |
| H3 | XComposite behavior with xfwm4 on real hardware | xfwm4 may handle window redirection differently under load |
| H4 | Workspace switching with real xfwm4 workspace count | Xvfb workspace behavior may differ from production xfwm4 |
| H5 | Multi-monitor layout (if external display connected) | Xvfb is single-head; real multi-monitor needed |
| H6 | Window activation with real applications (Firefox, Thunar, etc.) | Test windows (xterm) may not exercise all EWMH paths |
| H7 | Thumbnail capture of hardware-accelerated windows | Xvfb has no GPU acceleration; real GL windows may fail capture |
| H8 | Power impact of overview open/close | Real battery + RAPL measurements needed |
| H9 | Interaction with real Dock (plank) and menu bar | Xvfb does not run plank or menu bar |
| H10 | Force Touch trackpad gestures (if mapped to Mission Control) | No trackpad hardware in test environment |

---

## 9. Dependencies

### 9.1 New packages (ISO)

| Package | Purpose | Repository |
|---|---|---|
| `python-gobject` | GTK3 bindings | Arch core (already present) |
| `libxcomposite` | XComposite extension | Arch core (already present) |
| `libxrender` | XRender extension | Arch core (already present) |

No new AUR dependencies. All required libraries are in Arch core.

### 9.2 Existing packages (already in ISO)

- `wmctrl` — window enumeration fallback + activation
- `xorg-xprop` — window property queries
- `xdotool` — test input simulation
- `rofi` — fallback path

### 9.3 Python modules (stdlib + PyGObject)

- `ctypes` — libXcomposite/libX11 bindings
- `gi.repository.Gdk` — X11 enumeration
- `gi.repository.Gtk` — overlay UI
- `gi.repository.GdkPixbuf` — thumbnail handling
- `gi.repository.cairo` — custom rendering

---

## 10. Summary

| Aspect | Decision |
|---|---|
| Verdict | **GO** — dedicated layer needed |
| Architecture | One-shot Python/GTK3 overlay with XComposite thumbnails |
| Fallback | mv-mission-control (rofi) preserved during migration |
| Migration | 3 phases (A→B→C), rofi fallback at every step |
| skippy-xd | Retired after migration complete |
| Test strategy | Xvfb :97 + gui-isolation.sh, 9 test files |
| HW-validation | 10 items (HiDPI, GPU, real xfwm4, multi-monitor, power) |
| Power budget | 0 idle CPU, 0 idle memory, one-shot process |
| Objectives | 10 ordered objectives, each independently testable |

---

*This plan is the design baseline for the Mission Control dedicated overview layer. Implementation begins at O1 after this document is committed.*
