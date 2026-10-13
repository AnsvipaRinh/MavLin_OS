# A — Architecture: Design System / Interaction System / UI Platform

## A.1 What we are actually building

MavLinOS is not "a Linux desktop with a Mavericks theme". The target is the
Mavericks *interface system*: the same visual language, the same interaction
rules, the same system-wide behaviours, running on Linux — with native Linux
applications and Linux backends underneath.

That forces a separation that a theme cannot provide:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ LAYER C — MAVLINOS UI PLATFORM (what an application sees)                 │
│   tokens API · widget library · window/menu/dialog services · animation   │
│   engine · integration SDK · a11y · icon/font services                    │
├───────────────────────────────────────────────────────────────────────────┤
│ LAYER B — INTERACTION SYSTEM (how the interface behaves: data)            │
│   behavior.* records (state machines, keyboard, pointer, drag&drop)       │
│   animation.* records (durations, easing, interruption, reduced motion)   │
│   event vocabulary · window lifecycle · focus rules                        │
├───────────────────────────────────────────────────────────────────────────┤
│ LAYER A — DESIGN SYSTEM (what the interface looks like: data)             │
│   component.* records (geometry, states, visuals, layout)                  │
│   asset.* records (artwork with rendering + reproduction recipes)          │
│   design tokens (colour, font, metric, duration, easing, shadow, texture) │
├───────────────────────────────────────────────────────────────────────────┤
│ SOURCE — ground truth extracted from OS X 10.9 (docs/UI_REFERENCE)        │
└───────────────────────────────────────────────────────────────────────────┘
              │                        │                        │
        ┌─────▼─────┐            ┌─────▼─────┐            ┌─────▼──────┐
        │ GTK3/Cairo│            │ xfwm4/X11 │            │ D-Bus      │
        │ renderer  │            │ compositor│            │ services   │
        └───────────┘            └───────────┘            └────────────┘
```

**Why the split matters commercially**, not just conceptually: the same
`component.button.push` record must be drawable by GTK3 CSS + Cairo, by a native
C tool, by the window manager's chrome code and by the icon generator, without
any of them re-declaring what a push button looks like. If the definition lives
in a renderer, every new surface drifts — which is exactly how a Mavericks
Finder ends up next to a Linux-looking Settings dialog.

## A.2 Layer A — Mavericks Design System

### A.2.1 Contents

| Group | Records | Notes |
|---|---|---|
| Components | `component.*` | one record per Mavericks UI piece, every state, every variant |
| Artwork | `asset.*` | icons, chrome art, glyphs, textures — each with rendering + reproduction |
| Tokens | `design-tokens.json` | colour (per appearance: blue/graphite), font, metric, duration, easing, shadow, texture |
| Surfaces | `surface.*` | assembly rules: which controls a real window/dialog/panel contains and in what order |
| Windows | `window.*` | authored window geometry: designer rects, style masks, size frequencies |

### A.2.2 The compiled form is what implementers use

Extraction artifacts (nib frames, palette ramps, Mach-O strings) are *evidence*.
The implementable form is the compiled design system:

```
docs/UI_REFERENCE/data/*.json   →   design/tokens/design-tokens.json              (A)
                                     design/components/*.json                     (A+B per component)
                                     design/animations/*.json                    (B)
                                     design/behaviors/*.json                     (B)
                                     design/assets/manifest.json                 (A + generated art)
```

`design/` is a build tree: generated from the contract-conformant records, and
consumed by every renderer. A renderer that needs a colour, a size, a curve or a
duration reads a token id; it never hardcodes the value. This is the mechanism
that keeps 20 apps coherent.

### A.2.3 Asset handling (the legal constraint that shapes the design)

Assets are the one place where the original artwork cannot be redistributed.
The contract (`asset.schema.json`) therefore requires three things for every
asset:

* `media.px` — the measured pixel facts of the original (traceable to a guest path);
* `rendering` — how a renderer must stretch/tile/slice it (cap insets, align, interpolation);
* `reproduction` — a recipe executable on Linux: `clean-room-redraw`,
  `derived-from-measurement`, `trace-vector-pdf`, `generator`, or an explicit
  `no-replacement` plus a gap.

An asset without a reproduction recipe is **not shippable**. This is what turns
"we have 15 582 measured bitmaps" into "we can rebuild the theme without the
guest".

## A.3 Layer B — Mavericks Interaction System

Layer B is the part every themed Linux port skips, and the part users notice
first: the traffic lights gain glyphs on hover, the minimize animation is a
genie, a dragged window travels with the pointer 1:1, sheets slide out of the
title bar, the Dock magnifies, Launchpad tiles stagger.

Contents:

| Group | Records |
|---|---|
| Window behaviour | `behavior.window.*` — activate, drag, resize, minimize/zoom, fullscreen transition, stacking, occlusion-drag, sheet attach/detach, window tabbing |
| Control behaviour | `behavior.control.*` — press/release semantics, keyboard activation, focus ring, disabled/inactive rules, segmented control tracking, slider drag |
| Menus | `behavior.menu.*` — menu bar tracking cycle, context menu invocation, validation, key equivalents, menu item state |
| Dock / shell | `behavior.dock.*`, `behavior.shell.*` — magnification, running indicators, Mission Control/Spotlight/Launchpad invocation, desktop click-through |
| Drag & drop | `behavior.dnd.*` — spring-loaded folders, drag-to-trash, move/copy modifier semantics, drop validation |
| Text & selection | `behavior.text.*`, `behavior.selection.*` — double/triple click, word selection, field editing, selection colours |
| Animations | `animation.*` — every significant motion as a declarative record |

### A.3.1 The animation record is a reproducibility contract

`animation.window.minimize` (see `../examples/animation.window.minimize.json`)
fixes: trigger, from/to state, duration + tolerance, easing, the interpolated
properties, dependency/stagger relations, interruption policy including what the
user sees if they interrupt, the reduced-motion substitute, and — mandatory —
the platform fallback when the window system cannot do it.

A video or the phrase "smoothly expands" is explicitly **not** acceptable
input; the contract says so and the acceptance checklist (§F) enforces it.

### A.3.2 Event vocabulary

Behaviours and animations share one event id space so they compose:

```
mv.event.pointer.down | mv.event.pointer.up | mv.event.pointer.move | mv.event.pointer.drag
mv.event.key.down     | mv.event.key.up     | mv.event.wheel
mv.event.window.activate | mv.event.window.deactivate | mv.event.window.move
mv.event.window.minimize.requested | mv.event.window.zoom.requested
mv.event.window.fullscreen.enter | mv.event.window.fullscreen.exit
mv.event.app.launch | mv.event.app.terminate | mv.event.app.activate
mv.event.menu.open | mv.event.menu.close | mv.event.dialog.present
mv.event.dnd.enter | mv.event.dnd.drop | mv.event.dnd.exit
```

Renderer backends translate native events (X11/XCB, GDK, or the compositor's
protocol) into these ids; behaviour records never mention X11.

## A.4 Layer C — MavLinOS UI Platform (four planes)

Layer C is deliberately **not** one monolith. Four planes, each independently
maintainable and independently replaceable:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ PLANE 4 — INTEGRATION   libmavui SDK: menu bar registration, dialogs,    │
│        notifications, quick look, theming, session, MIME, D-Bus names    │
│        Languages: C (gtk3), Python3 (mv-* apps), CLI (shell integration) │
├──────────────────────────────────────────────────────────────────────────┤
│ PLANE 3 — SHELL        D-Bus services, on-demand activated:              │
│        mv.menubar · mv.notifications · mv.quicklook · mv.spotlight       │
│        · mv.launchpad · mv.missioncontrol · mv.windows · mv.iconlookup   │
│        · mv.fonts · mv.settings (no resident daemons; see §A.5)          │
├──────────────────────────────────────────────────────────────────────────┤
│ PLANE 2 — WIDGETS      libmavui: GTK3 widget set drawn from component    │
│        records + the Aqua token theme engine (Cairo custom drawing)      │
│        · MVWindow (chrome, sheets, toolbar) · MVButton · MVList          │
│        · MVSidebar · MVToolbar · MVDialog · MVNotification · MVPopover   │
├──────────────────────────────────────────────────────────────────────────┤
│ PLANE 1 — DATA         design/tokens/*, design/components/*,             │
│        design/animations/*, design/behaviors/*, design/assets/*         │
│        (pure data, no code, no toolkit dependency)                       │
└──────────────────────────────────────────────────────────────────────────┘
```

| Plane | Depends on | May be replaced by | Cost of getting it wrong |
|---|---|---|---|
| 1 Data | nothing | — | every surface drifts |
| 2 Widgets | 1 | another toolkit binding (Qt, EFL) | one toolkit's look breaks |
| 3 Shell | 1, 2 | systemd user units, another service bus | shell behaviours diverge |
| 4 Integration | 1–3 | — | apps stay "Linux apps in a costume" |

### A.4.1 Distinguish these five things (they are not the same)

1. **Visual components** — component records + drawings (plane 1/2).
2. **Behavioural components** — behavior records + the state machines that run
   them (plane 1/2).
3. **System services** — the processes that own shared state: menu bar,
   notification history, quick look, window rules (plane 3).
4. **Application-facing interfaces** — stable APIs/SDK (plane 4).
5. **Platform-specific implementations** — X11/EWMH specifics, xfwm4 rules,
   renderer bindings (plane 2/3, isolated behind the binding layer).

## A.5 Technology evaluation (Linux)

Criteria: visual fidelity to Mavericks, ability to reproduce Mavericks
*behaviour*, runtime cost on a fanless Core M, portability, ecosystem, and how
much of the stack we would have to own.

| Option | Fidelity | Behaviour | Cost | Verdict |
|---|---|---|---|---|
| **GTK3 + Cairo + custom widgets (libmavui)** | high (full control of drawing, theming, metrics) | high (client-side widgets, sheets, popovers, drag) | low–medium | **Primary.** Already the project's base (Xfce, Thunar, GTK apps); keeps the power baseline; no new runtime besides our libs |
| Qt (Qt5/Qt6 + QStyle) | high | high | medium | **Secondary binding only.** Not in the base image; a QStyle binding is worth it later if a Qt app must be Strategy-A integrated |
| X11 + xfwm4 (baseline compositor) | medium | medium | very low | **Keep.** Heavy compositing off (power baseline). Chrome and client-side animation come from widgets; window effects are limited — see compromises |
| picom-class compositor for effects | high | high | medium–high (GPU wakeups) | Deferred: requires a documented power experiment; would be opt-in, never default |
| Custom compositor / Wayland protocol | ceiling | ceiling | very high | **No.** Not justified before the widget layer exists; Wayland binding stays an option behind plane 2's interface |
| Custom toolkit from scratch | ceiling | ceiling | very high | **No.** Reinvents text layout, input methods, a11y — exactly the "no unnecessary reinvention" trap |
| Electron/web view | low | medium | very high (memory, battery) | **Excluded** per AGENTS.md §4/§7 |

**Documented compromises (recorded in `docs/DECISIONS.md`, not silently
simplified):**

| Mavericks behaviour | Linux baseline | What we ship |
|---|---|---|
| Genie/suck minimize effect | xfwm4 has no window warp | cross-fade + scale toward the Dock tile; effect recorded in `bindings.fallback` of the animation record |
| Window shade/zoom with live shadow | X11 shadows are compositor-drawn | widget-drawn shadow inside the frame; compositor shadow disabled for our windows |
| Mission Control window exposé | xfwm4 has none; skippy-xd experiment | plane-3 service over X11 window enumeration |
| Global (system-wide) application menu | Xfce has no global menu | plane-3 menu bar service fed by plane-4 registration; falls back to in-window menus |

## A.6 Rendering independence

One data set, many renderers. The rule:

```
component record (geometry/states/visuals/typography/assets)
        │
        ├── generator ──▶ GTK3 CSS + Cairo drawing code        (planes 1→2)
        ├── generator ──▶ xfwm4 theme (titlebar, buttons)     (planes 1→2)
        ├── generator ──▶ plank/dock theme + icons            (planes 1→2)
        └── generator ──▶ native C/GTK app code, Qt QStyle    (plane 2, optional)
```

Every generator reads the same token ids. A drift test (`tools/uiplatform`
conformance + the theme generators' output hash) fails the build when a
renderer stops matching the records. This is what makes "replace the backend,
keep the look" possible.

## A.7 Data flow and ownership

```
extraction agent                 platform owner                  renderers/apps
docs/UI_REFERENCE/**      →      design/** (contract-conformant) → packages/**, configs/**
  facts + evidence                 + tokens + generated art        theme, widgets, apps
  (read-only for others)           (this spec's contract)          (tests: check-sync, lab harness)
```

Ownership boundaries are enforced by claims (`docs/COORDINATION.md` R1): the
extraction agent owns `docs/UI_REFERENCE/**`, `tools/uiref/**`,
`tests/uiref/**`; the platform owns `docs/UI_PLATFORM/**`,
`tools/uiplatform/**`, `tests/uiplatform/**` and (once roadmap phase P2
starts) `design/**` and `packages/mavui*/**`.

## A.8 How the twelve principles are satisfied

| Principle | Mechanism |
|---|---|
| Separation of concerns | planes 1–4 + record kinds |
| Backend independence | records never reference an app; surfaces reference components |
| Rendering independence | tokens/records + per-renderer bindings/generators |
| Reusability | one record, N consumers; no per-app re-declaration |
| Consistency | single token source + drift tests + §F checklist per surface |
| Extensibility | additive schemas, versioned `schema` ids, deprecation policy |
| Traceability | `provenance` + `evidence` + gaps on every record |
| Reproducibility | extractor named per record, asset recipes, generator-based build |
| Practical implementation | GTK3/D-Bus/X11 stack already in the base image |
| Fidelity | compromises are recorded, never silent (`bindings.fallback`) |
| Performance | no resident daemons, on-demand services, event-driven; see §A.5 |
| No reinvention | reuse Thunar/GVfs, UDisks2, NetworkManager, PipeWire, libnotify, Poppler, GStreamer, plank, xfwm4, plocate |
