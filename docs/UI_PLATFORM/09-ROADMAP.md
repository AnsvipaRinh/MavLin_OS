# I — Implementation Roadmap

Sequence for turning the extraction into a working MavLinOS desktop platform.
Phases are ordered by dependency, not by ambition. Each phase has an entry
condition, the work, an exit test, and the repo paths it touches. Phase names
(P1…) refer to this document; they do not renumber `AGENTS.md` §11 phases.

```
P0  contract + conformance tooling            [DONE - this change]
P1  harvest the runtime probe (uiprobe)       <- single highest-value act
P2  compile the design system (design/**)
P3  interaction records (Layer B)
P4  widget library + generators (plane 2)
P5  shell services (plane 3) + SDK (plane 4)
P6  application migration (A/B/C) per §E
P7  visual regression harness (F.4) in CI
```

## P0 — Contract and conformance tooling (done)

**Entry:** none. **Work:** this specification (A–I), `schemas/`,
`examples/`, `tools/uiplatform/validate.py`, `tests/uiplatform/test_contract.py`.
**Exit:** `python3 tests/uiplatform/test_contract.py` passes (33 checks) and
`validate.py conformance` produces a deterministic report over the live
extraction data. **Touches:** `docs/UI_PLATFORM/**`, `tools/uiplatform/**`,
`tests/uiplatform/**`.

## P1 — Harvest the runtime probe (highest value, unblocks A and B)

**Entry:** none (script already written and cross-compilable).
**Work:**

1. Boot the **full installer** (Utilities → Terminal route already written in
   `docs/PROGRESS.md` step 1).
2. `DYLD_INSERT_LIBRARIES=mvprobe.dylib MVPROBE_OUT=/tmp/probe.json /usr/bin/true`
   inside the guest; pull `/tmp/probe.json` out over the slirp HTTP channel
   (`tools/uiref/http_collect.py`).
3. Emit `docs/UI_REFERENCE/data/uiprobe.json` (`mavlinos.uiprobe/1`).
4. Finish the desktop install so captures become possible at all.

**Exit:** `components.py --probe uiprobe.json` flips every component's coverage
to `111`; `metrics.json`/`typography.json` gain facts from `uiprobe`
(`window.contentRectMath`, `window.standardButtons`, `controls.buttonMetrics`,
`text.fonts`).
**Owner:** extraction agent. **Blocked by:** guest reach; must not be replaced by
guessing (F-2).

## P2 — Compile the design system

**Entry:** P1 (or partial: palette + nib geometry + windows are already usable).
**Work:**

1. `tools/uiplatform/tokens.py` → `design/tokens/design-tokens.json` from
   palette/typography/metrics/uiprobe + the documented decisions in
   `docs/VISUAL_STYLE_GUIDE.md` (marked `kind: proposed`).
2. `design/components/*.json` for the ~28 components the platform ships:
   curated variants, states, per-state visuals, constraints, layout (use
   `surfaces.json` to filter the frame haystack, F-4).
3. `design/assets/manifest.json` + artwork generators for the shipped subset
   (chrome art, toolbar, sidebar, scrollbar, glyphs, icon grid) — F-5.
4. `design/surfaces/*.json` for the surfaces that ship (assembly data) — F-7.
5. `design/manifest.json` (B.7) with counts, statuses and the gap list.

**Exit:** every record passes L0–L2; `validate.py validate design/` is clean;
the manifest's gap list matches `08-GAP-ANALYSIS.md` minus the closed items.
**Touches:** new `design/**`, `tools/uiplatform/**`.

**Status 2026-10-13 (phase started):** the token compiler + manifest are
delivered (`tools/uiplatform/tokens.py` → `design/tokens/design-tokens.json`,
`design/manifest.json`; 22 tokens: 3 derived from the extracted palette, 19
proposed MavLinOS decisions; 38 compiler tests pass). Still open in this phase:
the curated `design/components/*.json`, the asset generator and the surface
assembly records.

## P3 — Interaction records (Layer B)

**Entry:** P0 (schemas), ideally P1 for measured timings.
**Work:** `design/behaviors/*.json` for window lifecycle, drag, resize,
minimize/zoom/fullscreen, sheet attach, focus/raise, menu tracking and
validation, context menus, selection, drag & drop, scrolling, Dock interactions;
`design/animations/*.json` for minimize/restore, genie fallback, sheet
presentation, popover, Launchpad stagger, Mission Control, notification
banner, toolbar show/hide, fullscreen transition, Dock magnification; the event
vocabulary from §A.3.2 as a machine-readable list.
**Exit:** every behaviour/animation record has an interruption and
reduced-motion rule and a fallback where the compositor cannot help; negative
tests in the contract suite cover the rules; each record that claims a timing
names literature or a capture (F-1, F-3).
**Touches:** `design/behaviors/**`, `design/animations/**`.

## P4 — Widget library and generators (plane 2)

**Entry:** P2 for the components being built.
**Work:**

1. `packages/mavui` (C, GTK3 + Cairo): `MVWindow` (chrome, traffic lights,
   toolbar, sheets, shadow policy), `MVButton` family, `MVList`/`MVSourceList`,
   `MVToolbar`, `MVDialog`/`MVSavePanel`/`MVOpenPanel`, `MVNotification`,
   `MVPopover`, `MVScroller`, `MVQuickLook`.
2. Token theme engine (`mv_tokens_*`) + generated GTK3 CSS from
   `design/tokens/`; xfwm4/plank generators from the same tokens.
3. Renderers bind `bindings.gtk3` per component; unknown tokens and
   unimplemented animated properties fail loudly.
4. Performance gate: startup + idle RSS + wakeups per widget set, measured in
   the lab harness, recorded in `docs/BENCHMARKS.md` / `docs/MEMORY_BUDGET.md`.

**Exit:** F.2 checklist passes for the widget gallery; a screenshot of the
gallery matches the reference scenarios 1 and 3 within tolerance.
**Touches:** `packages/mavui/**`, `packages/mavericks-theme/**` (generated
output), `tools/uiplatform/**` (generators), `tests/**`.

## P5 — Shell services and SDK (planes 3–4)

**Entry:** P2/P3 data, P4 widgets for the surfaces the services present.
**Work:** D-Bus services (`org.mavericks.MenuBar`, `.Notifications`,
`.Windows`, `.Icons`, `.App`, `.Dialogs`, `.QuickLook`) as on-demand systemd
user units; `mvsdk` Python bindings and `mv-app` CLI; menu bar replacing the
xfce4-panel plugin; Notification Centre; Spotlight/Launchpad as plane-3
frontends over the existing backends (Strategy C); Mission Control over X11
enumeration.
**Exit:** D.3 contract satisfied by at least two applications; no new resident
daemon in `docs/PERSISTENT_SERVICES_AUDIT.md`; `scripts/check-sync.sh` extended
by the two lines noted in B.8 (protected-file claim required).

## P6 — Application migration

**Entry:** P4 widgets, P5 services.
**Work:** migrate `mv-*` apps (Strategy A), Thunar (Finder, Strategy B+C),
browser (B, limited), the rofi surfaces (C), xfce4-notifyd presentation (B/C),
remaining P1 apps from `AGENTS.md` §10. One app at a time, each accepted per
§F.2 and recorded in `docs/APPS.md`.
**Exit:** no in-scope surface below `IMPLEMENTED_HARDWARE_VALIDATION_REQUIRED`
without a recorded reason (AGENTS.md §13).

## P7 — Visual regression and CI

**Entry:** P4 widgets + a rendering surface that can be captured headless.
**Work:** `tools/uiplatform/difftest.py` (F.4): reference scenarios 1–12, guest
goldens captured with host timestamps, Linux captures under Xvfb :97, region
masks from the component records, tolerances per record; hook into
`scripts/check-sync.sh` and a workflow (protected files → claim first).
**Exit:** a deliberate 2 px geometry change or a wrong disabled colour fails CI.

## P8 — Optional bindings (only if a consumer appears)

Qt `MavStyle` QStyle binding, second theme variant (graphite already a token
dimension), HiDPI-specific token scale sets for the 2304×1440 panel
(hardware validation of the scale rules, not of the design).

## Cross-cutting rules

* Every phase ends with `docs/DECISIONS.md` + `docs/PROGRESS.md` entries in the
  same commit, `tests/` green, tree clean (AGENTS.md §8).
* Nothing in P2–P6 ships a hardcoded colour, metric, duration or string that the
  design system already defines.
* Hardware-dependent items stay in `docs/NEEDS_HARDWARE_TEST.md`; a software gap
  never gets labelled "hardware required".
