# UI Platform — Mavericks extraction architecture, data contract & SDK

This directory is the **engineering specification** that turns the Mavericks
ground-truth extraction (`docs/UI_REFERENCE/`) into a reusable, production-grade
Linux desktop interface platform.

It is written for two readers:

1. **the extraction agent** (`docs/UI_REFERENCE/`, claim
   `20261011-1140-opencode-os-ui-reference-capture`) — what its output must
   contain so it can be consumed without a second reverse-engineering pass;
2. **the implementer** — how to draw, drive, animate and integrate every
   Mavericks surface using nothing but this repository.

```
                       REVERSE ENGINEERING          COMPILATION            DELIVERY
   ┌──────────────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐
   │ real OS X 10.9   │   │ UI_REFERENCE │   │ UI_PLATFORM  │   │ renderers + apps   │
   │ (nibs, AppKit,   │──▶│ data/*.json  │──▶│ tokens,      │──▶│ GTK3 theme, mv-*   │
   │  guest captures) │   │ catalog/*.md │   │ components,  │   │ apps, window mgmt, │
   └──────────────────┘   └──────────────┘   │ animations,  │   │ D-Bus services     │
        facts (what is)                      │ behaviors    │   └────────────────────┘
                                             └──────────────┘        (how it runs)
                                                decisions
```

| Directory | Meaning |
|---|---|
| `docs/UI_REFERENCE/` | **Facts.** Data-first catalog extracted from the real 10.9 system. Owned by the extraction agent. Read-only for everyone else. |
| `docs/UI_PLATFORM/` | **This specification.** Architecture, data contract, schemas, examples, acceptance criteria, gap analysis, roadmap. |
| `schemas/` | Versioned JSON Schemas for every platform record (`mavlinos.*`). |
| `examples/` | Reference records, hand-checked against the schemas and the semantic rules. |
| `design/` (repo root) | **Compiled platform output**: `tokens/design-tokens.json` + `manifest.json`. Generated, never hand-edited. |

## Documents

| # | Document | Content |
|---|---|---|
| A | [`01-ARCHITECTURE.md`](01-ARCHITECTURE.md) | Three layers (design system / interaction system / UI platform), four platform planes, technology evaluation, data flow |
| B | [`02-DATA-CONTRACT.md`](02-DATA-CONTRACT.md) | The exact structure, naming, versioning, provenance and evidence rules of every record |
| C | [`03-COMPONENT-ANIMATION-SPEC.md`](03-COMPONENT-ANIMATION-SPEC.md) | Component, state, animation and state-machine representation, merge and rendering semantics |
| D | [`04-SDK-SPEC.md`](04-SDK-SPEC.md) | Application-facing interfaces: tokens, widgets, windows, menus, dialogs, notifications, animation, a11y, integration |
| E | [`05-INTEGRATION.md`](05-INTEGRATION.md) | Strategies A/B/C for making native Linux apps MavLinOS-native, and where frontend replacement is required |
| F | [`06-ACCEPTANCE.md`](06-ACCEPTANCE.md) | Extraction quality and platform acceptance checklist; conformance levels L0–L3 |
| G | [`07-EXAMPLES.md`](07-EXAMPLES.md) | Annotated walkthrough of `examples/*.json` and of a consumer using the SDK |
| H | [`08-GAP-ANALYSIS.md`](08-GAP-ANALYSIS.md) | Current extraction output vs. contract: gaps, incompatibilities, migration plan |
| I | [`09-ROADMAP.md`](09-ROADMAP.md) | Sequenced implementation plan with entry/exit criteria |

## Tooling

```bash
# validate the reference examples (and any new record) against the schemas
python3 tools/uiplatform/validate.py validate [path ...]

# read-only conformance audit of the extraction output
python3 tools/uiplatform/validate.py conformance [--data DIR] [--json]

# compile the Layer A token file + manifest from the extracted palette
python3 tools/uiplatform/tokens.py            # -> design/tokens/design-tokens.json
python3 tools/uiplatform/tokens.py --check    # also fails on extraction drift

# executable reference: does a record actually DRAW from the tokens alone?
python3 tools/uiplatform/validate.py check-deps                     # R-TOKENDEP
python3 tools/uiplatform/render_ref.py --component <record>.json \
                                        --out build/render/out.png --state pressed

# self-tests: does the contract still catch defects?
python3 tests/uiplatform/test_contract.py     # 34 checks
python3 tests/uiplatform/test_tokens.py       # 38 checks
```

All of these run on every commit through `scripts/check-sync.sh` (section "ui data
contract"); the conformance report itself never turns the gate red on its own —
gaps are findings, not failures, while the extraction is in flight.

`tools/uiplatform/validate.py` is stdlib-only (the build container has no
`jsonschema` package). It implements the JSON-Schema subset our schemas use,
plus the semantic rules that cannot be expressed as a schema (evidence
requirements, state lists, transition targets, reproduction recipes).

## Rules that are not negotiable

1. **No Apple bytes in git.** Only derived numbers, our own drawings, our own
   JSON (UI_REFERENCE rule C5, unchanged).
2. **Every number names its evidence.** `src:`, `capture:` or `lit:`. Raw file
   names, screenshots and memory are not evidence.
3. **Nothing is silently approximated.** `kind: inferred` and
   `confidence: unverified` exist precisely so a guess never has to masquerade
   as a measurement. Records with gaps are allowed; records that hide gaps are
   not.
4. **Behaviour is data.** Animations, interactions and window rules live in
   records, not inside one application's code.
5. **One visual language.** Any surface that a Mavericks user would compare
   against the original is judged on the same checklist (§F).
