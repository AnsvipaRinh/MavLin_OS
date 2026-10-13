# D — MavLinOS UI Platform / SDK Specification

## D.1 Scope and process model

The platform exposes Layer A + Layer B to applications. Its process model
follows the project's power rules (`AGENTS.md` §7):

* **No resident daemon.** Shell services are systemd *user* units that are
  D-Bus-activatable and exit when idle. Widgets are libraries in the
  application's own process. Nothing polls by default; periodic refresh exists
  only while a window is open (Activity Monitor-class surfaces).
* **Data is static.** Tokens/components/animations are files loaded on demand
  and cached by the client library; no database, no watcher.
* **C and Python3 first.** The GTK apps in `packages/mavericks-apps` are
  Python3; the widget library is C (GTK3/Cairo). A QStyle binding is a later,
  optional plane-2 backend.

```
application process                 platform                     system
┌───────────────────────┐   ┌───────────────────────┐   ┌──────────────────┐
│ mv_* app (Python/GTK) │──▶│ libmavui (C, GTK3)    │   │ Xfce/xfwm4/X11   │
│  · widgets            │   │  · token theme engine │──▶│ EWMH, ICCCM      │
│  · mvsdk (Python)     │   │  · MVWindow/controls  │   │ UDisks2/UPower/  │
│  · D-Bus clients      │──▶│ shell services (D-Bus)│──▶│ NetworkManager/  │
└───────────────────────┘   └───────────────────────┘   │ PipeWire/...     │
                                                        └──────────────────┘
```

## D.2 API surface

Each API below states: purpose, form (C symbol / D-Bus name / CLI), the
consumer, and the contract it must honour. `mv_*` = C symbols in `libmavui`,
`Mv.*` = Python bindings, `org.mavericks.*` = D-Bus service names.

### D.2.1 Design tokens API (plane 1)

```
mv_tokens_load(dir)                     -> MvTokenSet*
mv_token_color(set, "color.selection.control", appearance) -> const MvColor*
mv_token_metric(set, "metric.control.height.regular")      -> double
mv_token_font(set, "font.system.regular")                  -> const MvFont*
mv_token_duration(set, "duration.motion.medium")           -> unsigned ms
mv_token_easing(set, "easing.standard")                    -> MvBezier
```

* Contract: values are @1x pt; HiDPI scaling is a renderer concern. A missing
  token is a hard error (never a silent fallback) so drift fails loudly.
* `appearance` selects the blue/graphite variant; unknown appearance = default.

### D.2.2 Theme & appearance API

```
mv_theme_apply(widget, "MavAqua/1.0")    (GtkCssProvider-like)
mv_theme_reload()                        (dev tool; not for apps)
```

Theme files are **generated** from tokens (`A.6`). An app never ships its own
colours or metrics; it selects the platform theme and contributes only
historically accurate extra textures (Calendar leather, Notes paper).

### D.2.3 Component API (plane 2)

Every `component.*` record gets a widget (or a widget configuration):

```
MVWindow, MVPanel, MVSheet, MVDialog, MVAlert
MVToolbar, MVToolbarItem, MVSidebar, MVSplitView, MVTabView, MVBox
MVButton, MVDefaultButton, MVSegmentedControl, MVSwitch, MVCheckbox,
MVRadio, MVPopUpButton, MVSlider, MVStepper, MVProgress, MVSpinner
MVTextField, MVSearchField, MVTextView, MVList, MVSourceList, MVTable
MVMenu, MVMenuBar, MVMenuItem, MVContextMenu
MVNotification, MVPopover, MVQuickLook, MVTrafficLights, MVScroller
```

Contract: each widget is drawn from its component record; behaviour comes from
the referenced `behavior.*` records; state changes emit the shared event ids.
Widgets expose their record id (`mv_widget_component_id()`) so tests and
debugging can assert *which* Mavericks component a surface claims to be.

### D.2.4 Window management API (plane 3 + X11)

```
org.mavericks.Windows
  Rules()              -> per-app window rules (frame style, shadow, level,
                          min size, sticky, fullscreen policy)
  Layout(id, rect)     -> place a window in the Mavericks layout (tiling,
                          cascade, centre)
  Sheet.Attach(parent, sheet) / Sheet.Detach(sheet)
  Space.Move(window, space) / Space.Current()
```

Backed by EWMH/ICCCM plus xfwm4 configuration; rules are data
(`design/behaviors/behavior.window.*` + per-app overrides). Window animations
the compositor cannot do are executed client-side by `MVWindow` (toolbar,
sheets, popovers) or recorded as a documented fallback (genie minimize).

### D.2.5 Animation API (plane 1+2)

```
mv_anim_run(target, "animation.window.minimize", MvAnimFlags)
mv_anim_run_group("minimize", targets)       // shared start + stagger
mv_anim_cancel(target, policy)               // shortest-path | snap | queue
mv_anim_reduced_motion() -> bool             // system setting
```

The engine reads the record; the renderer supplies a per-property interpolator.
If a property is not implemented by the binding, the animation must fail loudly
in development and use `bindings.fallback` in production — never silently
degrade to "nothing happens".

### D.2.6 Interaction & input API

```
mv_focus_set(window) / mv_focus_cycle(window, direction)
mv_event_translate(native_event) -> MvEventId (mv.event.* vocabulary)
mv_pointer_grab(widget, mask, behavior_id)
mv_dnd_begin(widget, payload, MvDndPolicy)
mv_gesture_on(widget, MvGesture{swipe, pinch, rotate, smart-zoom}, behavior_id)
```

Trackpad gestures map onto the declared `behavior.*` records; ordinary Linux
shortcuts keep working (`AGENTS.md` §6 keyboard layer), and Command-like
modifier mapping is a central layer, not per-app.

### D.2.7 Menu API

```
org.mavericks.MenuBar
  Register(app_menu)     -> app name + menu tree + validation owners
  SetStatus(items)       -> right side: clock, volume, battery, spotlight, ...
  Open(app), Close(app), Highlight(item)
```

Menu trees are data (from `surfaces.json` + `terminology.json` — the exact
English strings already extracted for 3910 items). When no global menu bar is
available the same tree renders inside the window (documented fallback).

### D.2.8 Dialog API

```
MVAlert, MVSheet, MVOpenPanel, MVSavePanel, MVSettingsPanel, MVColorPanel,
MVFontPanel, MVPrintPanel
org.mavericks.Dialogs.Open(path, options) -> uri[] | cancel
```

One implementation for the whole system (GTK's stock dialogs are the exact
"Linux-looking dialog next to Mavericks chrome" failure mode). Panels are
plane-3 services when shared (file chooser needs session state), in-process
widgets otherwise.

### D.2.9 Notification API

```
org.mavericks.Notifications
  Notify(app_id, replaces_id, title, body, actions[], image, timeout_ms)
  History(since) / Clear(app_id)
  Dismiss(id)
```

Rendered by one surface (banner + panel). Backends already exist
(libnotify/xfce4-notifyd); the platform owns the *Mavericks* presentation and
history, per `AGENTS.md` §10.3 (no second daemon).

### D.2.10 Icon & asset API

```
org.mavericks.Icons
  Lookup(name, px) -> uri           (icon theme + generated Mavericks art)
  Render(asset_id, px) -> surface   (cap insets, tiling, align applied)
```

Consumes `asset.*` records and the generated artwork; the icon theme is emitted
with the full Mavericks grid (16/18/32/36/64/128/256/512/1024 — the sizes
already measured in `assets.json`).

### D.2.11 Typography API

```
mv_font_for(role) -> family, size_pt, ascender, descender, leading, xHeight
mv_font_substitute(role) -> the Linux package + family actually installed
```

Roles come from `typography.json` / `uiprobe.json`; substitutes are explicit
(`font.*.linux_substitute`), never implicit "whatever fontconfig picks".

### D.2.12 Layout API

```
mv_layout_grid(widget, {h, v}, gap)          Mavericks standard spacing
mv_layout_align_rect(rect, alignment, insets)
mv_layout_baseline(widgets[])                shared text baseline
```

Standard spacing is tokenised (`metric.layout.*`); no app invents padding.

### D.2.13 Accessibility API

```
mv_a11y_set_role(widget, "AXButton") / mv_a11y_set_title(widget, text)
mv_a11y_set_help(widget, text) / mv_a11y_set_shortcut(keys)
```

The `a11y` block of every component record is the contract; GTK's ATK bridge
carries it. Orca must be able to operate the platform, so a11y is a
first-class field, not a follow-up.

### D.2.14 Application integration API

```
org.mavericks.App
  Register(app_id, name, icon, menu, categories)   // desktop integration
  Launch(desktop_id, uris[], options)                // Mavericks launch behaviour
  OpenWith(uri) -> candidates                        // uses MIME + mv-* handlers
  QuickLook(uri)                                     // plane-3 quick look
  SetBadge(app_id, text)                             // Dock badge
  Session.Save()/Restore()                           // session restore
CLI: mv-app register | launch | open-with | quicklook | badge
```

## D.3 Integration contract a Mavericks-native app must satisfy

| Area | Contract |
|---|---|
| Window | `MVWindow` chrome, `MVToolbar`, traffic lights from the component records, sheet support, correct inactive-window state |
| Menus | app menu registered with the menu bar service; standard menu items with the exact Mavericks wording (from `terminology.json`) and key equivalents |
| Dialogs | only `MVAlert`/`MVSheet`/`MVOpenPanel`…; no stock GTK dialog |
| Notifications | only `org.mavericks.Notifications` |
| Icons/fonts | icon lookup service + `mv_font_for`; no ad-hoc icons for system concepts |
| Focus | honours `mv_focus_*`, participates in the app/window switching rules |
| Animation | named records; no ad-hoc timing constants |
| Session | registers with the session service; exits cleanly on SIGTERM |
| Errors/empty states | documented in `behavior.*` `errors[]`; never a bare GTK error box |
| Cost | no resident daemon, no polling without a documented reason |

## D.4 Extensibility and deprecation

* New component kinds are additive: add records, add a widget, add generators.
  Existing records are untouched.
* APIs are versioned by the service interface revision
  (`org.mavericks.MenuBar` r1, r2…); a breaking change adds a method set, never
  removes one.
* A deprecated record keeps its id with `status: deprecated` and a successor
  pointer; generators warn when a deprecated record is consumed.

## D.5 What the SDK deliberately does **not** do

* It does not reimplement file operations, storage, network or media. Those
  stay with the mature Linux backends (GVfs, UDisks2, NetworkManager,
  PipeWire, Poppler, GStreamer).
* It does not provide a widget toolkit for arbitrary application UI; it provides
  the Mavericks component set plus the standard GTK containers.
* It does not own the compositor. Window behaviour goes through EWMH/xfwm4;
  effects beyond that are an explicit, documented compromise.
