# G — Reference Examples

The files in `examples/` are the normative worked examples. They are validated
on every test run:

```bash
python3 tools/uiplatform/validate.py validate
python3 tests/uiplatform/test_contract.py
```

| File | What it demonstrates |
|---|---|
| `component.button.push.json` | a full control: variants, constraints, layout, states, per-state visuals, behaviour, a11y, gaps |
| `component.window.traffic-lights.json` | a multi-part chrome component with the inactive-window trap |
| `animation.window.minimize.json` | a declarative animation with tolerance, interruption, reduced motion and platform fallback |
| `behavior.window.drag-by-titlebar.json` | an interaction as a state machine with errors |
| `asset.toolbar.background.json` | an asset record: measured media + rendering + reproduction + legal |
| `design-tokens.json` | the compiled token file with blue/graphite variants and Linux substitutions |

## G.1 `component.button.push` — reading it

```jsonc
"geometry": {
  "coordinate_system": {"origin": "bottom-left", "units": "pt", "scale": 1},
  "variants": [
    {"id": "regular", "intrinsic": {"w": 68, "h": 22}, "min": {"w": 24, "h": 22},
     "max": {"w": 400, "h": 22}, "elastic": ["w"], "alignment": "center"},
    {"id": "small",   "intrinsic": {"w": 60, "h": 20}},
    {"id": "mini",    "intrinsic": {"w": 52, "h": 16}}
  ],
  "constraints": [
    {"expr": "height == 22 || height == 20 || height == 16 (no other heights exist)"},
    {"expr": "corner_radius == min(4, height/6)"},
    {"expr": "label_baseline == height/2 + 1"}
  ],
  "layout": [
    {"part": "bevel",       "rect": {"x": 0, "y": 0, "w": 68, "h": 22}, "z": 0},
    {"part": "label",       "rect": {"x": 8, "y": 3, "w": 52, "h": 16}, "z": 1},
    {"part": "focus_ring",  "rect": {"x": -3, "y": -3, "w": 74, "h": 28}, "z": 2}
  ]
}
```

Points to notice:

* the three size classes are *declared*, and the constraints say which heights
  may exist at all — a renderer that produces a 24 px push button is wrong by
  contract;
* `focus_ring` is drawn **outside** the frame and `hit_testing.extra_rect`
  says the ring is clickable — the detail most ports miss;
* `per_state.disabled` explains that Mavericks does **not** fade the whole
  control: only the label colour changes. Anticipating the wrong instinct is
  part of the record's job.

The same record with `kind: measured`, `confidence: high` and
`status: verified` becomes the moment the render test in §F.4 passes.

## G.2 `animation.window.minimize` — reading it

```jsonc
"duration_ms": 350, "duration_tolerance_ms": 30,
"easing": {"type": "bezier", "points": [0.25, 0.1, 0.25, 1.0]},
"properties": [
  {"path": "window/opacity", "from": 1, "to": 0},
  {"path": "window/scale",   "from": 1, "to": 0.08},
  {"path": "window/anchor",  "from": "window-frame-centre", "to": "dock-tile-centre"}
],
"interruption": {"policy": "shortest-path", "reversal": "reversible", "max_retargets": 2,
                 "expected_result_when_interrupted": "..."},
"reduced_motion": {"policy": "substitute", "substitute": "animation.window.minimize-instant"},
"bindings": {"fallback": {"what": "cross-fade + scale to the Dock tile corner",
                          "reason": "xfwm4 cannot warp the window surface"}}
```

The record is honest about its own evidence (`kind: literature`,
`confidence: low`) and states the platform fallback in the record instead of
letting a renderer invent one. Anything "smoothly expands" is rejected by the
contract, not by taste.

## G.3 `behavior.window.drag-by-titlebar` — reading it

The state machine in §C.3 shows the minimum viable set: idle → pre-drag →
dragging, with the drag threshold, the Cmd-drag of an occluded window, the
Space-during-drag space switch, Escape restore, and two `errors[]` entries
(non-draggable window; pointer released off-screen keeps the window clamped
on-screen). An implementer needs no other source.

## G.4 `asset.toolbar.background` — reading it

```jsonc
"media":    {"format": "png", "px": {"w": 320, "h": 44}, "bits": 32, "alpha": true},
"rendering": {"mode": "nine-slice-h", "cap_insets": {"x": 0, "y": 0, "w": 320, "h": 12}},
"reproduction": {"method": "derived-from-measurement",
                 "recipe": "44 pt strip, 1 px top highlight at 35 % white, ..."},
"legal": {"apple_bytes_in_repo": false}
```

The measured `media` values come from the real 10.9 resource (320×44 PNG,
`GameKit.framework`), and the record says plainly that the cap insets and the
reproduction recipe are MavLinOS engineering until measured — with the
measurement listed as a gap that blocks the chrome components.

## G.5 `design-tokens.json` — reading it

```jsonc
"appearance": ["blue", "graphite"],
"tokens": {
  "color.window.background":  {"type": "color", "value": "#ffffff", "alpha": 1,
                               "evidence": ["src:appkit"], "kind": "derived",
                               "confidence": "high"},
  "color.selection.control":  {"type": "color", "value": "#6f8fbd",
                               "variants": {"blue": "#6f8fbd", "graphite": "#8e8e93"}},
  "font.system.family":       {"type": "font", "value": "Lucida Grande",
                               "linux_substitute": {"value": "Cantarell",
                                                     "reason": "licensed Apple artwork",
                                                     "package": "cantarell-fonts"}},
  "metric.menubar.height":    {"type": "metric", "value": 24, "unit": "pt",
                               "kind": "proposed", "confidence": "medium"}
}
```

Three kinds of token coexist deliberately: derived-from-evidence, proposed
(MavLinOS decision), and substituted (Linux reality). A consumer cannot tell
the truth from a guess by accident — `kind` and `confidence` say it.

## G.6 Consuming the platform (target code)

```python
# an mv-* app: no literal colour, metric, font or duration anywhere
import mvsdk as mv

win = mv.Window(component="component.window.chrome", appearance="blue")
win.set_toolbar(mv.Toolbar(items=[mv.ToolbarItem(icon=mv.icon("toolbar.new-folder"),
                                                 label=mv.string("New Folder"))]))
btn = mv.PushButton(label=mv.string("Save"), component="component.button.push",
                    default=True)
btn.on("activate", lambda: win.save())
win.present(sheet=confirm_sheet)                      # Mavericks sheet
mv.notify(app_id="mv-finder", title=mv.string("Copy complete"), body=path)
mv.anim.run(win, "animation.window.minimize")        # named, not hardcoded
mv.font_for("menu")                                   # Lucida Grande substitute
```

```c
/* GTK3/Cairo renderer binding: draws the component from the record */
MvTokenSet *t = mv_tokens_load(MV_TOKENS_DIR);
cairo_set_source_rgb(cr, mv_token_color(t, "color.control.background.top")->rgb);
mv_draw_bevel(cr, rect, mv_token_metric(t, "metric.control.radius"),
              MV_STATE_PRESSED, t);
```

And the flow the app never sees: `plocate`/GVfs → result records → `mvsdk` →
`MVList` — Strategy C with the backend swappable behind the contract.
