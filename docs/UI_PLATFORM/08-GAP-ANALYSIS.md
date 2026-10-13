# H — Gap Analysis: current extraction output vs. the contract

Audited on 2026-10-13 against commit `832cd4eb` (+ in-flight edits to
`nib_geometry.json`). Every finding below is a fact about the repository, with
the file/field that proves it. The extraction is **genuinely advanced** in
tokens of raw geometry; it is **not yet consumable** as an interface platform,
for reasons that are mostly structural rather than missing effort.

Reproduce the machine-readable part at any time:

```bash
python3 tools/uiplatform/validate.py conformance           # human report
python3 tools/uiplatform/validate.py conformance --json    # machine report
```

## H.1 What is already strong (do not rebuild this)

| Asset | Evidence |
|---|---|
| Reproducible offline route from the real installer | `docs/UI_REFERENCE/PROVENANCE.md`: InstallESD → Essentials.pkg → 9 GB system tree, all stdlib/7z/bsdtar |
| Nib geometry decoder | `data/nib_geometry.json`: 1447 nibs, 1353 with views, 608 with window templates, 1425 with outlet connections, 1267 with fonts, 1234 with colours |
| ObjC contract index | `data/ui-api.json`: 3 modules (appkit 1179, finder 658, dock 282 = 2119 classes) with responsibility buckets and method samples |
| Control flags at scale | `data/controls.json`: 14375 cell objects, 38 NS*Cell classes, flag bitfields, key equivalents |
| Palette from AppKit's own colour sections | `data/palette.json`: 275 values, one pinned source (`src:appkit`, sha256 present) |
| Window geometry | `data/windows.json`: 1373 NSWindowTemplate records with style masks and size frequencies |
| Surface inventory | `data/surfaces.json`: 1198 surfaces, required controls, artwork names, 296 with menu items, 11 surface kinds |
| Wording corpus | `data/terminology.json`: 3918 strings across 8 system apps (3062 with clear-English signal) |
| Generated catalog + drift tests | `tools/uiref/render.py`, `tests/uiref/test_catalog.py` (16 checks incl. md5 + docs drift) |
| Runtime probe written and cross-compilable | `tools/uiref/mvprobe.c`: colours, content-rect math, standard button frames, button metrics per control size, font metrics |

## H.2 Findings

Severity: **critical** (blocks the platform), **high** (blocks a whole layer
class), **medium** (forces rework later), **low** (hygiene).

### F-1 — Layer B (interaction system) does not exist in machine-readable form
**Evidence:** `data/behaviors.json` = `{"facts": []}`; no `animation.*` records
anywhere in the repo; no event vocabulary; no state machines.
**Impact:** every renderer must invent focus rules, drag thresholds, menu
validation, interruption behaviour. This is precisely where a themed Linux
desktop diverges from Mavericks, and it is the layer that cannot be recovered
from screenshots.
**Action:** populate `behaviors.json` from the recorded observations
(`docs/MISSION_CONTROL*.md`, `docs/KEYBOARD.md`, `docs/FIDELITY_AUDIT.md` plus
what the guest can still provide) and create `design/animations/` records for
the motions named in `AGENTS.md` §10. Rule: literature-sourced timings are
allowed at `confidence ≤ medium` if the record says so.
**Owner:** extraction agent (facts) + platform (schema consumers).

### F-2 — Metrics, typography and patterns are empty
**Evidence:** `data/metrics.json`, `data/typography.json`, `data/patterns.json`
each contain only a schema header. `catalog/metrics.md`, `typography.md`,
`patterns.md` therefore render as empty tables.
**Impact:** the component records cannot be completed (§C.1) and no renderer
can be pixel-checked. The most valuable single artifact is
`data/uiprobe.json` (already scripted) — it delivers font metrics, standard
button frames, button sizes, content-rect math and the runtime palette in one
run.
**Action:** harvest `uiprobe.json` (continuation plan already written in
`docs/PROGRESS.md`), then emit metrics/typography facts with `deriv` and roles.

### F-3 — No capture registry, so no capture-scoped evidence
**Evidence:** `captures/index.json` has `count: 0`; all 275 palette facts cite
the single `src:appkit` source; `meta.json` rule C3 expects capture ids.
**Impact:** evidence cannot be scoped to a *state* (hover, inactive, pressed) —
only to a whole artifact. States are the thing theming depends on.
**Action:** add captures with md5 + host timestamp + guest resolution; then
`capture:` evidence can express "this is what hover looked like".

### F-4 — Component records are not implementable records
**Evidence:** `data/components.json` — 15 components, all `measured: false`,
`coverage[].has_runtime == false` for all 15, no `states`, no `visuals`, no
`a11y`, no `dependencies`; `skin.from_nibs` collects *every* frame of the nib
class across the whole system tree without role assignment (e.g. the `box`
record mixes frames from unrelated nibs and other components' views).
**Impact:** an implementer gets a haystack, not a needle. Knowing that 204×197
appears somewhere is not knowing the titled-window toolbar height.
**Action:** adopt `mavlinos.component/1` (schemas/component.schema.json) for the
compiled layer: curate per-variant geometry, assign roles to frames (use the
`surfaces.json` required-control inventory as the filter), declare states, and
let `components.py` remain the *evidence* producer while
`design/components/*.json` becomes the *implementable* product.

### F-5 — Asset records cannot drive rendering
**Evidence:** `data/assets.json` — 15582 records with `path/format/w/h/role`
only: no rendering mode, no cap insets, no hash, no reproduction recipe. Roles
are coarse (`control` 1156, `retina` 2823) and the corpus includes
non-Mavericks bundles (Game Center, App Store, Podcasts).
**Impact:** "15582 assets" is inventory, not a theme. A component cannot be
rebuilt from a bitmap without slice data, and no asset can be regenerated
without the guest.
**Action:** for the subset the platform actually ships (chrome art, toolbar,
sidebar, scrollbars, glyphs, the icon grid), emit `mavlinos.asset/1` records
with measured media + rendering + reproduction, and a generator that produces
the artwork on Linux (favours `derived-from-measurement` /
`clean-room-redraw` recipes).

### F-6 — Window masks contain undocumented bits
**Evidence:** `catalog/windows.md`: masks 128 (8 windows) and 144 (4 windows)
show "(undocumented bits only)"; `chrome_heights` section is empty because every
record has `chrome_h: null`, `content_h: null`, `min_w/min_h: null` (0/1373
records carry them).
**Impact:** the window platform cannot implement a mask it cannot name; window
minimum sizes and chrome height are exactly what a `MVWindow` needs.
**Action:** resolve bit 0x80 and 0x90 against AppKit's
`NSWindowStyleMask` (header/class dump) and record the mapping; derive
`chrome_h` from `contentRectForFrameRect:styleMask:` for each mask in use
(`mvprobe.c` already implements the call with styleMask 7).

### F-7 — Surfaces are an inventory, not assembly rules
**Evidence:** `data/surfaces.json`: 1198 surfaces; `nib_geometry` false for 662
of them; `required_controls` are class+count pairs; no order, spacing,
alignment, or z-index; `menu_items` present in 296.
**Impact:** implementers still invent layout. "Finder window" needs the same
assembly data as "traffic lights": what is above, what is inset, what resizes.
**Action:** add `layout[]`/order fields (the same vocabulary as
`component.geometry.layout`) for the surfaces that ship in MavLinOS; the rest
stay inventory.

### F-8 — Terminology corpus is uncurated
**Evidence:** `data/terminology.json` contains code-signing and symbol noise
(78 % signal) — e.g. `"*Apple Code Signing Certification Authority0"`,
`"ASASASASASASAS…"`.
**Impact:** exact Mavericks wording is a first-class requirement (§F.2.2-11), but
a developer must hunt the corpus to find "Put Back" or an alert's default button
label.
**Action:** classify strings by role (menu title / menu item / alert / button /
tooltip) using the nib menu trees already decoded in `nib_geometry.json`, and
emit a curated wording table per surface. No Apple bytes are committed — these
are short functional strings; the legal review already in `docs/LICENSES.md`
must confirm the policy before they are used verbatim in shipped UI.

### F-9 — ObjC ivar slots decode as bytes
**Evidence:** `data/ui-api.json` — 5576 ivar slots, 4693 not usable names
(values like `"\b\u0001"` are raw slot bytes, not typed names).
**Impact:** the bones layer can say "this class draws" but not "this is the
field it draws from". State machines cannot be derived from it.
**Action:** either decode ivar types from the class's `ivar_getName` equivalent
in the Mach-O metadata (requires the symbol table the current decoder skips) or
mark the field as unavailable and rely on selector-level evidence. Do not
present byte slots as names.

### F-10 — No dependency graph between artifacts
**Evidence:** `components.json` names only `nib`/`api`/`probe` basenames; no
record declares which palette facts, which nibs or which surfaces it used.
**Impact:** changing one artifact silently invalidates consumers; the existing
validator checks internal counts but not provenance closure.
**Action:** adopt the contract's `provenance` + `dependencies` fields (already
in the schemas) for the compiled layer; the conformance tool reports records
whose dependencies are not declared.

### F-11 — No compiled design-system layer at all
**Evidence:** no `design/` tree; `packages/mavericks-theme` is authored SCSS/CSS
by hand; `docs/VISUAL_STYLE_GUIDE.md` states decisions (24 px menu bar, 22–26 px
controls, 2–4 px radii, #6f8fbd selection) that exist nowhere in machine-readable
form; `tools/uiref/theme.py` (untracked, in progress) resolves colours and fonts
from nibs but has no consumer.
**Impact:** the theme and the extracted truth can drift apart with nothing to
detect it.
**Action:** generate `design/tokens/design-tokens.json` from the facts
(palette/typography/metrics/uiprobe) and have the theme generators consume it;
drift becomes a failing check rather than a visual opinion.

## H.3 Format incompatibilities with the contract

| Existing thing | Contract position | Migration |
|---|---|---|
| `data/*.json` `facts[]` with `kind/confidence/evidence` | **compatible**; `kind` gains `inferred`, `proposed` | none |
| palette `sources` inside the file | contract wants a sources registry with sha256 | keep as is; add `captures/index.json` entries when captures appear |
| `evidence` raw file names | contract wants `src:`/`capture:`/`lit:` | grandfathered; new records use the typed form |
| `components.json` (extraction view) | contract wants `mavlinos.component/1` | keep `components.py` output as evidence; add `design/components/*.json` as the implementable product; `components.py --out` can later write both |
| `windows.json` `style_bits` strings | contract needs named bits or explicit "undocumented" | resolve F-6, then record the mapping |
| `ui-api.json` ivars | contract's `provenance` forbids invented names | mark as unavailable (F-9) |
| terminology strings | contract needs role-classified wording | curate into a wording table (F-8) |

No existing file needs to be rewritten or moved to satisfy the contract. The
migration is **additive and staged**: populate → curate → compile → validate.

## H.4 What this audit deliberately did not do

* It did not measure anything in the guest (no guest is running).
* It did not verify Mavericks behaviour claims: `docs/FIDELITY_AUDIT.md` and
  the `catalog/` files are project statements, not measurements, and are
  treated as such here.
* It did not touch the extraction agent's paths (`docs/UI_REFERENCE/**`,
  `tools/uiref/**`, `tests/uiref/**`) — claim `20261013-1130-opencode-ui-platform-spec`
  covers only `docs/UI_PLATFORM/**`, `tools/uiplatform/**`,
  `tests/uiplatform/**` and doc appends.
