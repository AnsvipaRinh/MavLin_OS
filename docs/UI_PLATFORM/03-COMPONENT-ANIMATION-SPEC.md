# C — Component, State and Animation Specification

## C.1 Component anatomy

```
component.window.traffic-lights
├── geometry
│   ├── coordinate_system        origin: bottom-left | top-left, units: pt, scale: 1
│   ├── variants[]               regular / small / mini / hud / textured
│   │   └── intrinsic, min, max, elastic[], alignment
│   ├── constraints[]            relations valid for every variant and every future size
│   └── layout[]                 named parts + rects + z-order (the "bones")
├── states[]                     normal hover pressed focused selected disabled
│                                inactive-window mixed dragging highlighted open checked
├── visuals
│   ├── background[]             solid | gradient | texture | asset, with token stops
│   ├── border[]                 width/style/radius/inset + token colour
│   ├── shadow[]                 token references
│   ├── glyph[]                  symbol artwork per part, with rects
│   ├── typography[]             token role + colour + alignment + truncation
│   └── per_state{}              overrides per state id
├── behavior                     refs, keyboard[], pointer[], focus, hit_testing
├── animations                   refs + default
├── a11y                         role, title, help, keys
├── bindings                     gtk3 | qt | x11 | native (empty until written)
├── dependencies                 tokens, assets, components, fonts
└── acceptance                   reference evidence + tolerances
```

### C.1.1 Coordinate system (the field that silently breaks ports)

Mavericks (AppKit) is **bottom-left origin, y up**. Linux toolkits are
top-left, y down. Every record declares its origin; the platform converts once,
centrally, in the renderer binding. A geometry value in a record is never
"whatever GTK wants".

### C.1.2 Variants, constraints, layout

* **Variants** exist because Mavericks itself has size classes: regular, small,
  mini (and for chrome: textured, HUD). One variant per authored intrinsic
  size; a component with a single variant must say so explicitly.
* **Constraints** are worth more than measurements: `button_centre_spacing == 20`
  or `height == min(4, height/6)` survive at any scale and any future size.
  Measurements are evidence for a constraint, not a replacement for it.
* **Layout** names the internal parts with z-order. Without it an implementer
  guesses whether the focus ring is inside or outside the border, and whether
  the glyph sits above or below the bevel.

### C.1.3 State model

Mavericks state is **compound**: control state × window state. The contract
therefore declares the states that exist in the original and makes the
cross product explicit in `per_state`:

| State | Applies to | Notes |
|---|---|---|
| `normal` | everything | the drawn default |
| `hover` | buttons, list rows, toolbars, traffic lights, Dock tiles | in Mavericks the *hovered* traffic light changes and the others do not |
| `pressed` | buttons, controls, Dock tiles, traffic lights | transient; cancelled by drag-out |
| `focused` | controls, list rows, text | focus **ring**, not a fill; never animated in 10.9 |
| `selected` | list rows, sidebar items, segmented control | muted blue / graphite accent |
| `disabled` | controls, menu items | label colour changes; the bevel keeps its grey |
| `inactive-window` | everything in a background window | chrome greys out; **glyphs disappear on traffic lights**, selection dims |
| `mixed` | checkboxes | the dash state |
| `dragging` | windows, Dock tiles, list rows | the dragged representation |
| `highlighted` | menus, buttons during tracking | the menu highlight blue |
| `open` | popup buttons, menus, combo boxes | the pressed+open look |
| `checked` | menu items, checkboxes, radios | the check mark |

### C.1.4 Visual layering and override merge

Render order inside a component record (lowest first):

```
background (gradient/texture/asset) → border → shadow → glyph → typography
```

Merge semantics: `base + per_state[state]`, where a scalar field in the override
replaces the base, a list field in the override **replaces** the base list
(no concatenation), and `notes` never render — they document intent for the
implementer. `opacity` and `transform` are the only whole-component overrides.

### C.1.5 Hit testing and focus

`behavior.hit_testing` distinguishes `rect`, `alpha` (per-pixel) and `shape`,
and carries `extra_rect` when the interactive area is larger than the visible
frame (AppKit's focus ring is clickable). `behavior.focus.order` declares tab
order participation. Non-focusable components (traffic lights, sidebars) say so.

### C.1.6 Deriving a record from the extraction artifacts

The procedure an implementer (or the extraction agent) follows — this is the
"no undocumented knowledge" path:

1. Identify the component in `ui-api.json` → the ObjC class and its
   responsibility buckets (drawing/geometry/focus/keyboard/mouse/animation).
2. Collect authored frames for its nib classes from `nib_geometry.json`
   (`NSFrame`, `NSFrameSize`, `NSBounds`, `NSBorderRect`).
3. Read bezel/flag bitfields and key equivalents from `controls.json`; map bits
   to appearances **only** after verification against AppKit (record the mapping).
4. Read colours from `palette.json` / `uiprobe.json` (`colors[]`, per-name value)
   and map them to semantic token roles.
5. Read fonts from `typography.json` / `uiprobe.json` (`text.fonts[]`: family,
   pointSize, ascender, descender, leading, xHeight).
6. Read assembly rules from `surfaces.json` (required controls + artwork).
7. Write the record with `kind`/`confidence` per value: measured where an
   artifact backs it, `proposed` where we decided it, `gaps[]` for the rest.

## C.2 Animation specification

### C.2.1 Record semantics

| Field | Meaning |
|---|---|
| `trigger` | the event id (+guard) that starts the animation |
| `from_state` / `to_state` | the component/window states it interpolates between |
| `duration_ms` + `duration_tolerance_ms` | nominal duration and allowed deviation; Mavericks rounded to frames, so values below ~17 ms are not distinct durations |
| `easing` | cubic bezier (4 control points) or a named `easing.*` token, or spring parameters |
| `properties[]` | one entry per interpolated property with `from`, `to`, interpolation type |
| `timing` | delay, group, `depends_on`, `stagger_ms` for lists |
| `interruption` | `shortest-path` (continue from the current value toward the new target), `reverse`, `restart`, `queue`, `snap`, `ignore`, plus `expected_result_when_interrupted` — a sentence an implementer can test against |
| `reduced_motion` | `disable` or `substitute` (must name the substitute) |
| `observed_source` | literature / capture-frames / appkit-runtime / inferred / proposed |
| `bindings.fallback` | the platform compromise, with the reason |

### C.2.2 Timing facts and how they may be established

1. **Runtime reading (best).** AppKit's own animation dictionaries and
   `NSAnimationContext duration` read inside the guest by `mvprobe.dylib` →
   `data/uiprobe.json`. This is a *value* read from the system, not a frame
   count.
2. **Capture sequence.** Screendumps with host timestamps from a *booted desktop*
   guest. TCG is not isochronous (UI_REFERENCE rule C2), so frame counts are
   never durations; host-time deltas between recognizable states are.
3. **Literature.** Documented macOS behaviour; capped at `confidence: medium`
   and marked `kind: literature`.

### C.2.3 Interruption semantics (worked example)

Minimize is `reversible` with policy `shortest-path`: if the user clicks the
Dock tile mid-flight, the animation continues from the current scale/opacity
toward the restored state, never snapping. Retargets are capped
(`max_retargets`); beyond the cap the platform snaps. This is exactly what
makes the difference between "there is an animation" and "it feels like macOS".

## C.3 Behavior and state machines

A `behavior.*` record is a small deterministic machine:

```
idle --pointer.down[hit==titlebar]--> pre-drag
pre-drag --pointer.move[distance>3]--> dragging
pre-drag --pointer.up--> idle                     (no move: a click)
dragging --pointer.move--> dragging               (internal, action only)
dragging --key.down[key==Space]--> dragging       (space switch during drag)
dragging --key.down[key==Escape]--> idle          (restore origin frame)
dragging --pointer.up--> idle                     (commit frame)
```

Rules:

* Guards read only the declared `context`; actions are named effects from a
  fixed vocabulary (the implementer maps names to code per renderer).
* Every state machine declares `errors[]`: what the original does when the
  interaction cannot complete (non-draggable window, pointer released off
  screen, denied volume, invalid drop target).
* Keyboard and pointer bindings are declared in the record, so the global
  shortcut layer (`packages/mavericks-apps` hotkey registry) can be generated
  from data instead of hand-maintained.
* Multiple components may reference the same behaviour (window chrome, panel
  chrome, sheets) — behaviour is written once.

## C.4 What "state" means for the shell, not just widgets

The same state vocabulary covers shell surfaces:

| Surface | States | Notes |
|---|---|---|
| Menu bar | normal, app-active, app-inactive, menu-open, item-highlight | translucent strip; dark variant for fullscreen |
| Dock | normal, magnifying, item-normal/hover/pressed/running/attention | running indicator, bounce for launch |
| Window | normal, key, inactive, minimized, fullscreen, sheet-attached, dragging, resizing | focus/raise rules belong in `behavior.window.*` |
| Notification | presenting, visible, dismissing, history-row | banner vs alert in the panel |
| Spotlight/Launchpad/Mission Control | opening, open, searching, closing | plane-3 services with their own animation groups |
