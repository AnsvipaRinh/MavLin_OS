# B — Extraction Data Contract

This is the binding contract between the extraction agent and everything that
consumes its output. It is enforced mechanically by
`tools/uiplatform/validate.py` and `tests/uiplatform/test_contract.py`.

## B.1 Storage layout

```
docs/UI_REFERENCE/                      EXTRACTION FACTS (read-only for consumers)
├── meta.json                           capture rules + guest description
├── PROVENANCE.md                       how the guest was produced, hashes
├── captures/index.json                 md5-pinned capture registry (evidence: capture:<id>)
├── data/
│   ├── palette.json                    facts[]  275 AppKit colours
│   ├── metrics.json                    facts[]  @1x geometry metrics        (empty today)
│   ├── typography.json                 facts[]  fonts, sizes, metrics       (empty today)
│   ├── behaviors.json                  facts[]  interaction rules           (empty today)
│   ├── patterns.json                   facts[]  composite widget anatomy   (empty today)
│   ├── nib_geometry.json               raw evidence: 1447 nibs, views, frames, fonts, colours
│   ├── ui-api.json                     raw evidence: ObjC class model per module
│   ├── controls.json                   decoded nib cell objects (bezel flags, key equivalents)
│   ├── assets.json                     asset geometry: 15 582 headers (name/path/px/role)
│   ├── windows.json                    1373 NSWindowTemplate records
│   ├── surfaces.json                   1198 surfaces + required controls + artwork
│   ├── components.json                 15 prefabricated components + coverage report
│   └── terminology.json                Mach-O string corpus (menus, alerts, buttons)
└── catalog/*.md                        generated views (never hand-edit)

docs/UI_PLATFORM/                       CONTRACT + EXAMPLES + AUDIT
├── schemas/*.schema.json               mavlinos.component/1, .animation/1, .behavior/1,
│                                       .asset/1, .design-tokens/1, common
└── examples/*.json                     reference records

design/                                 COMPILED PLATFORM (roadmap phase P1+)
├── tokens/design-tokens.json            generated from facts, never hand-edited
├── components/<id>.json
├── animations/<id>.json
├── behaviors/<id>.json
├── assets/manifest.json + generated artwork
└── surfaces/<id>.json
```

Two rules that sound bureaucratic and save weeks:

* **One record per file, named after its id.** `component.button.push` lives in
  `design/components/component.button.push.json`. No aggregate dumps, no
  "misc.json": an independently addressable resource is independently reviewable.
* **Facts and decisions never share a file.** `docs/UI_REFERENCE/**` holds what
  the original is; `design/**` and this spec hold what we decided to build.
  A reader must always be able to tell the two apart.

## B.2 Identity and naming

| Element | Grammar | Example |
|---|---|---|
| record id | `<kind>.<family>.<name>` (kebab-case, lower-case, `.`-separated, stable forever) | `component.window.traffic-lights` |
| token id | `color.\|font.\|metric.\|duration.\|easing.\|shadow.\|texture.\|asset.` + kebab path | `color.selection.control`, `metric.control.height.regular` |
| animation id | `animation.<family>.<name>` | `animation.window.minimize` |
| behavior id | `behavior.<subject>.<name>` | `behavior.window.drag-by-titlebar` |
| asset id | `asset.<category>.<name>` | `asset.glyph.close` |
| evidence | `src:<source>` \| `capture:<id>` \| `lit:<id>` | `src:uiprobe`, `capture:finder-icon-view`, `lit:mavlinos-hig-windows` |

Ids are **never reused**. A renamed record is a new record; the old one gets
`status: deprecated` and a note pointing at the successor.

## B.3 Common record vocabulary

Every contract-conformant record carries the same honesty fields
(`schemas/common.schema.json`):

| Field | Rule |
|---|---|
| `schema` | `mavlinos.<kind>/<major>`. The doc declares its own contract version. |
| `id`, `title` | stable id, human name |
| `kind` | `measured` \| `derived` \| `literature` \| `inferred` \| `proposed` |
| `confidence` | `high` \| `medium` \| `low` \| `unverified` |
| `evidence` | ≥1 ref when `kind ∈ {measured, derived}` |
| `provenance` | artifact (+sha256 when in git), extractor, guest |
| `status` | `draft` \| `proposed` \| `verified` \| `deprecated` |
| `gaps[]` | `what`, `resolution ∈ {measure-in-guest, capture, research, render-test, decision, deferred-by-owner}`, `blocks[]` |

Semantic rules enforced by the validator:

```
R-EVIDENCE   measured/derived ⇒ evidence[] non-empty
R-EVIDENCE   literature      ⇒ confidence != high
R-VERIFY     status=verified ⇒ kind ∈ {measured, capture-frames}
R-TOLERANCE  animation duration ⇒ duration_tolerance_ms present
R-NOMOTION   animation reduced_motion=substitute ⇒ substitute named
R-REPRO      asset reproduction != no-replacement ⇒ recipe present
R-STATES     component per_state keys ⊆ states[]
R-SM         behavior transitions target declared states
R-TOKENID    token ids carry a type prefix; measured/derived tokens carry evidence
```

## B.4 Per-kind contracts

### B.4.1 Fact records (extraction layer, unchanged shape)

The existing extraction format keeps its shape — `{"schema": ..., "facts": [...]}`
with `id/kind/confidence/evidence` per fact. The contract adds three things the
extraction agent should supply going forward, none of which invalidate existing
files:

1. `deriv` — the formula or reference id for every derived value, so it can be
   re-derived instead of re-measured (already in the capture rules C4).
2. `role` / `group` — a semantic key (`aqua.control.solid`, `window.chrome.titlebar`)
   so consumers address facts by meaning, not by pixel.
3. `evidence` resolution — either `src:<key>` present in a `sources` registry with
   the artifact sha256, or `capture:<id>` present in `captures/index.json`.

**Required additions per file** (see §H for what is missing today):

| File | Must contain | Today |
|---|---|---|
| `metrics.json` | per-component @1x geometry with `deriv` and role | empty |
| `typography.json` | font roles → family/size/ascender/descender/leading/xHeight + Linux substitute | empty |
| `behaviors.json` | one fact per interaction rule (focus, keyboard, window, menu) | empty |
| `patterns.json` | composite anatomy referencing metrics ids | empty |
| `captures/index.json` | md5-pinned entries for every `capture:` id used | empty (0 captures) |
| `assets.json` | rendering + reproduction data per asset | pixel headers only |

### B.4.2 `mavlinos.component/1`

See `schemas/component.schema.json` and the annotated walkthrough in
`07-EXAMPLES.md`. Minimum implementable set:

* `geometry.coordinate_system` (origin, units, scale) — declared, never assumed;
* `geometry.variants[]` (regular/small/mini/hud/textured) with intrinsic/min/max;
* `geometry.constraints[]` — relations that survive any future size;
* `geometry.layout[]` — named rects of the internal parts, with z-order;
* `states[]` — the complete state list;
* `visuals` — background/border/shadow/glyph/typography, all referencing tokens;
* `visuals.per_state` — overrides per state;
* `behavior` — refs + keyboard + pointer + focus + hit testing;
* `animations`, `a11y`, `dependencies`, `acceptance.tolerances`.

### B.4.3 `mavlinos.animation/1`

`duration_ms` + `duration_tolerance_ms` (half a 60 Hz frame = 8 ms default),
easing as a cubic bezier or a token, one entry per animated property, dependency
and stagger relations, interruption policy with the user-visible result of an
interruption, reduced-motion substitute, and `bindings.fallback` for the
platform compromise.

### B.4.4 `mavlinos.behavior/1`

Triggers with guards, preconditions, a state machine (initial state, context,
states with `on:` transitions carrying guards/actions/animations), keyboard and
pointer bindings, side effects, and the error cases with their original results.

### B.4.5 `mavlinos.asset/1`

Guest path + measured `media.px` + `rendering` (mode, cap insets, align,
interpolation) + `reproduction` (method, recipe, generator, output, checks) +
`legal` (Apple bytes never in repo).

### B.4.6 `mavlinos.design-tokens/1`

`appearance[]` (blue/graphite), `generated_from.inputs`, and a token map where
every entry carries `type`, `value` (+ `unit`), optional `variants` per
appearance/scale, and `linux_substitute` when the original resource is not
redistributable.

## B.5 Versioning and migration policy

* Schema id = `mavlinos.<kind>/<major>`. Within a major: additive only
  (new optional fields, new enum members are appended, never renumbered).
* Breaking change = new major + a migration table in `02-DATA-CONTRACT.md`
  and a `docs/DECISIONS.md` entry.
* Existing extraction files are **not** rewritten: the contract accepts them as
  they are (`kind`/`confidence`/`evidence` already match) and adds fields the
  extraction agent produces incrementally.
* Legacy `kind: literature` in old files gains two siblings (`inferred`,
  `proposed`) so a guess never needs to pretend to be a measurement again.
* `evidence` values that are raw capture file names (the old validator accepted
  them) are grandfathered; new records use `capture:<id>`.

## B.6 Conformance levels

| Level | Meaning | How it is proven |
|---|---|---|
| **L0 schema-valid** | parses, required fields present, types/enums/patterns OK | `validate.py validate` |
| **L1 evidence-backed** | every measured/derived value resolves to a registered source or capture | `validate.py validate` + sources/capture registry check |
| **L2 implementable** | complete field set for the kind (states, variants, rendering, reproduction, dependencies closed) | `validate.py conformance` + §F checklist per component |
| **L3 validated** | the rendering matches the original within the record's tolerances | render test: golden-capture diff + geometry/colour/font metrics (§F.4) |

A record may live at L0–L2 with gaps. Only L3 records are allowed to claim
`status: verified`.

## B.7 Machine-readable manifests

`design/` carries a manifest (`mavlinos.manifest/1`,
`schemas/manifest.schema.json`) so consumers resolve dependencies without
reading every record. The first compiled manifest
(`design/manifest.json`) lists, per class, which records are derived from
evidence, which are proposals, and which are still unverified gaps — so "what is
not real yet" is answerable with one command:

```json
{
  "schema": "mavlinos.manifest/1",
  "counts": {"tokens": 22},
  "status": {"derived": ["color.window.background", "color.text.primary",
                          "color.control.background.solid"],
             "proposed": ["metric.menubar.height", "font.system.size", "..."]},
  "gaps": [{"record": "color.traffic.close", "what": "Placeholder until uiprobe ..."}]
}
```

## B.9 The token compiler (first consumer of this contract)

```bash
python3 tools/uiplatform/tokens.py            # writes design/tokens + design/manifest.json
python3 tools/uiplatform/tokens.py --check     # additionally fails on extraction drift
```

It maps the extracted palette to semantic token ids and proves the mechanism that
keeps the platform honest:

* a value read from a palette fact is emitted as `kind: derived`,
  `confidence: medium`, with that fact's `evidence` in the record (the colour is
  measured; the *role assignment* is a decision and stays at medium);
* every MavLinOS decision is emitted as `kind: proposed` with a note that says
  so, and with `confidence: unverified` while it is a placeholder;
* a palette fact it references that no longer exists makes the generator exit
  non-zero — extraction drift breaks the build instead of producing a stale
  theme;
* the output is byte-deterministic, so `design/**` can be committed and diffed.

## B.8 Validation commands and CI wiring

```bash
python3 tools/uiplatform/validate.py validate                      # L0+L1 for every record
python3 tools/uiplatform/validate.py conformance --json             # L2 audit of extraction output
python3 tests/uiplatform/test_contract.py                           # contract self-test (can fail)
python3 tools/lint-tests.py --strict                                # no always-true assertions in tests
```

CI wiring is deliberately **not** done in this change: `scripts/check-sync.sh`
and `.github/workflows/**` are protected files (`.agents/protected.txt`). The
roadmap (phase P5) records the exact two-line addition; until then the checks
run as plain commands and in `tests/uiplatform/test_contract.py`.
