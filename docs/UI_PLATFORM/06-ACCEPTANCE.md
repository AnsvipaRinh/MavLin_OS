# F — Extraction Quality and Acceptance Criteria

Two checklists: one for the **extraction output** (is the package usable?), one
for a **realised surface** (is it Mavericks?). Both are mechanical: each item is
answerable with a command, a file path or a rendered comparison.

## F.1 Extraction output — completeness (what the extraction agent must deliver)

### F.1.1 Layer A — design system

- [ ] `metrics.json`: @1x geometry for every component family, each value with
      `deriv` or evidence; roles keyed semantically (`window.chrome.titlebar`,
      `control.height.regular`, …).
- [ ] `typography.json`: every font role (system, menu, menu bar, label, control,
      status, tooltip, window title) with family, point size, ascender,
      descender, leading, xHeight **and** the Linux substitute + package.
- [ ] `palette.json`: semantic role per colour (`aqua.control.solid`,
      `window.background`, `selection.control`, `traffic.*`, …), alpha per value.
- [ ] `assets.json`: for every asset used by a shipped surface: `rendering`
      (mode, cap insets, align, interpolation) and `reproduction` (method +
      recipe). Raw header inventories do not satisfy this.
- [ ] Icon grid: the full Mavericks size set
      (16/18/32/36/64/128/256/512/1024 — already measured) is emitted by the
      icon generator.
- [ ] `surfaces.json`: assembly data (order, spacing, alignment) in addition to
      required-control inventory; ≥ 90 % of the 1198 surfaces with geometry.
- [ ] `windows.json`: every style-mask bit named or explicitly marked
      "undocumented, unused"; chrome height derived from
      `contentRectForFrameRect:styleMask:` for each mask in use.

### F.1.2 Layer B — interaction system

- [ ] `behaviors.json`: one machine-readable fact per interaction rule:
      focus, keyboard equivalents, menu validation, window lifecycle, drag
      start/move/drop, double-click semantics, fullscreen transition, sheet
      behaviour, scroll behaviour.
- [ ] Animation records for every significant motion, each with trigger,
      from/to, duration **+ tolerance**, easing, properties, interruption and
      reduced-motion rules (§C.2).
- [ ] `captures/index.json`: md5-pinned entries for every `capture:<id>` used;
      host-timestamped sequences for any timing fact (never TCG frame counts).
- [ ] `data/uiprobe.json` harnessed: runtime colours, standard button frames,
      button metrics per control size, content-rect math per styleMask, font
      metrics — the artifact `components.py` already expects.

### F.1.3 Contracts and hygiene

- [ ] Every record satisfies L0/L1 (`validate.py validate`) and passes the
      semantic rules (`tests/uiplatform/test_contract.py`).
- [ ] Every fact carries `kind` + `confidence`; no `literature` at high
      confidence; no `measured` without evidence.
- [ ] Every gap is a `gaps[]` entry with a `resolution` — "hardware required" is
      never a resolution for a software gap.
- [ ] No Apple bytes anywhere in git; every committed asset has a reproduction
      recipe (`R-REPRO`).
- [ ] `catalog/*.md` regenerated and drift-checked (already enforced by
      `tests/uiref/test_catalog.py`).
- [ ] `design/tokens/design-tokens.json` regenerated from the facts
      (`tools/uiplatform/tokens.py --check` exits 0); every derived token cites a
      registered source, every proposed token documents itself.

**Extraction exit criterion:** every in-scope Mavericks surface named in
`AGENTS.md` §13.2 has at least an L2 component/behaviour record set, and every
remaining gap is listed with a resolution. Without that, the extraction is not
handover-ready.

## F.2 Realised surface — acceptance (what an implementer must prove)

For each app/surface (mirrors `AGENTS.md` §13.3, applied to the platform):

### F.2.1 Visual

1. Geometry within **±1 px** of the record's @1x values (rendered on a 1:1
   display, no scaling in the guest).
2. Colour within **ΔE ≤ 2.0** of the record's token values, per state.
3. Font family/size/metrics as recorded; substitution recorded and visible in
   the font panel.
4. All declared states exist and differ from each other: normal, hover, pressed,
   focused, disabled, selected, **inactive-window**.
5. Transitions between states are instantaneous as in Mavericks (no fade where
   the original has none).
6. Two apps open simultaneously look like one OS (no mixed visual language).

### F.2.2 Behavioural

7. Keyboard navigation and the declared key equivalents work; Escape/Enter/
   Cancel behave as recorded.
8. Mouse semantics: click vs drag vs double-click thresholds as recorded.
9. Focus and raise order follow `behavior.window.activate`.
10. Animations replay with the recorded duration ± tolerance, interruption and
    reduced-motion behaviour; a disabled-animation path is usable.
11. Error/empty/unavailable states exist and use Mavericks wording
    (`terminology.json`).

### F.2.3 Integration

12. Uses platform dialogs/notifications/menus/quick look — no stock GTK dialog.
13. Registers with the menu bar service and the session service.
14. MIME associations and open-with go through the platform services.

### F.2.4 Resource behaviour

15. Startup cost measured (`/usr/bin/time -v` or the lab harness): no new
    resident daemon; idle wakeups and RSS within `docs/MEMORY_BUDGET.md`.
16. No polling without a documented reason; refresh only while a window is open.

### F.2.5 Tests that can fail

17. Launch smoke under Xvfb (`scripts/check-sync.sh` contract) — the app must
    actually render without errors.
18. Unit/behaviour tests for the state machines, run headless.
19. Visual regression: golden-capture diff within tolerance (see F.4).

## F.3 Status vocabulary for realised surfaces

`NOT_STARTED · AUDIT_REQUIRED · IN_PROGRESS · PARTIALLY_IMPLEMENTED ·
IMPLEMENTED_HARDWARE_VALIDATION_REQUIRED · VERIFIED · HARDWARE_BLOCKED ·
DEFERRED · EXCLUDED` (`AGENTS.md` §13.4). Records use the same vocabulary via
`status`, so a surface and its data can be compared directly.

## F.4 Visual regression methodology

1. **Reference scenarios** — a fixed list (defined in F.5), each rendered in the
   guest at 1600×900 @1x with the guest clock pinned, and on Linux under
   `Xvfb :97` at the same DPI.
2. **Capture** — guest: HMP `screendump` (host-timestamped). Linux: Xvfb +
   `import`/`xwd` + Pillow, same window geometry, same DPI, animations off
   (`mv_anim_reduced_motion()`) for deterministic snapshots, and separately with
   animations on for timing checks.
3. **Compare** — per-scenario masks: geometry ±1 px, colour ΔE ≤ 2.0 per
   declared region, and a full-image perceptual diff (< 2 % changed pixels)
   with a per-scenario region of interest taken from the component records.
4. **Timing** — animation durations measured from the *platform* side
   (property values sampled at known host time), not from frame counts.
5. **Report** — `tools/uiplatform/difftest.py` (roadmap P4) writes
   `docs/UI_PLATFORM/reports/<scenario>.md` with the numbers, so a regression
   is a failing number, not an opinion.

## F.5 Reference scenarios (minimum set)

| # | Scenario | Proves |
|---|---|---|
| 1 | Desktop: menu bar + Dock + one window | system-wide coherence |
| 2 | Finder icon view / list view | the hardest surface, first |
| 3 | Window states: active, inactive, hover traffic lights, pressed | state model |
| 4 | Dialog + sheet | dialog system |
| 5 | Context menu + menu bar menu | menu system and exact wording |
| 6 | Spotlight open with results | search surface |
| 7 | Launchpad grid | grid + stagger animation |
| 8 | Mission Control overview | window management |
| 9 | Notification banner + panel | notification system |
| 10 | Quick Look preview | preview pipeline |
| 11 | System Settings pane | settings coherence |
| 12 | Small controls: buttons/checkboxes/sliders/segmented in all sizes | control size classes |
