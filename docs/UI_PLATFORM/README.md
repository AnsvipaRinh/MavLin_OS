# UI Platform — evidence-backed Mavericks UI/UX implementation contracts

The UI Platform is the specification layer that turns the reference facts in [UI_REFERENCE](../UI_REFERENCE/README.md) into a reusable Linux desktop interface architecture.

**Current status:** the contracts, schemas, examples, validation tools, and initial architecture are established. The reference reconstruction is still in progress. This is an implementation blueprint under development, not evidence that the complete Linux UI has already been built.

## Purpose

The platform must represent both halves of the Mavericks experience:

1. **Visual identity:** palette, typography, geometry, materials, gradients, shadows, control rendering, and visual states.
2. **Interaction mechanics:** focus, input semantics, keyboard/pointer behavior, state machines, transitions, animations, persistence, and system integration.

The resulting contracts should let implementation agents reproduce a subsystem without repeating the reverse-engineering work or filling missing behavior with guesses.

## Evidence-to-platform flow

```
Real OS X Mavericks 10.9
        |
        v
REA + Ghidra/PyGhidra + nsinspect
        |
        v
UI_REFERENCE — static, native, and runtime evidence
        |
        v
UI_PLATFORM — versioned contracts, schemas, examples, acceptance rules
        |
        v
Linux architecture evaluation and implementation
        |
        v
Optimized MavlinOS system
```

The final renderer, toolkit, compositor, window manager, and Linux distribution are not locked by this specification. Existing GTK/Xfce prototypes are reusable material, not a binding technology decision.

## Three specification layers

- **Design System:** tokens and rules for colors, typography, spacing, surfaces, controls, assets, and visual states.
- **Interaction System:** event semantics, focus, keyboard/pointer input, state transitions, animation, timing, accessibility, and persistence.
- **UI Platform:** reusable windows, controls, menus, dialogs, sheets, notifications, application-facing APIs, and system integration.

The platform is organized into architecture, data contract, component/animation specification, SDK, integration, acceptance, examples, gap analysis, and roadmap documents.

## Directory structure

| Directory | Purpose |
|---|---|
| `schemas/` | Versioned JSON Schemas for platform records |
| `examples/` | Reference records validated against schemas and semantic rules |
| `../UI_REFERENCE/` | Source evidence; facts and provenance, not implementation guesses |
| `../../design/` | Compiled platform output, generated from validated source data |
| `../../tools/uiplatform/` | Validation, conformance, token generation, and reference rendering |
| `../../tests/uiplatform/` | Contract, token, and rendering validation |

## Reproducible tooling

```bash
python3 tools/uiplatform/validate.py validate [path ...]
python3 tools/uiplatform/validate.py conformance [--data DIR] [--json]
python3 tools/uiplatform/tokens.py
python3 tools/uiplatform/tokens.py --check
python3 tools/uiplatform/validate.py check-deps
python3 tools/uiplatform/render_ref.py --component <record>.json \
  --out build/render/out.png --state pressed
python3 tests/uiplatform/test_contract.py
python3 tests/uiplatform/test_tokens.py
```

## Non-negotiable rules

1. Every factual value must point to evidence and provenance.
2. Keep static NIB, native binary, runtime, and inferred evidence distinguishable.
3. Missing evidence must remain an explicit gap; never silently approximate.
4. Behavior is represented as data and state transitions, not hidden in one application's implementation.
5. One coherent visual and interaction language must span the system.
6. No proprietary Apple binaries, code, fonts, or artwork are to be redistributed.
7. Do not start broad implementation of a subsystem until its specification is sufficiently grounded and its acceptance criteria are testable.

## Current research-to-implementation gate

The next priority is to expand the reference beyond TextEdit and Calculator to Finder, Dock, System Preferences, shared window management, menus, dialogs, sheets, and system-level behavior. The UI Platform should evolve as those facts become available. Technology selection and full implementation follow the evidence, not the other way around.
