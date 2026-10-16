# MavlinOS

**A research-driven Linux operating-system project targeting the visual identity and complete user experience of OS X Mavericks 10.9.**

MavlinOS aims to reproduce Mavericks as a coherent desktop system—not merely apply a macOS-like theme—while retaining a capable, maintainable, and highly optimized Linux foundation.

> **Project status · 16 October 2026:** active reference reconstruction and reverse engineering. This repository is not yet a stable, installable OS release.

## What we are building

The target is the complete everyday Mavericks experience:

- Window chrome, focus, stacking, resizing, minimizing, zooming, and desktop/window management.
- Menu bar, application menus, Dock, application switching, and system-wide interaction patterns.
- Finder-like file management, navigation, sidebars, toolbars, dialogs, sheets, and context menus.
- System applications, preference panes, notifications, Quick Look, and other shared desktop surfaces.
- Accurate visual language, typography, geometry, control states, transitions, and animations.
- Linux-native system services and application compatibility beneath a consistent Mavericks-faithful UI.

The project is not defined by one Linux distribution, desktop environment, toolkit, or target laptop. Those implementation choices must be evaluated against the recovered reference, performance, maintainability, and compatibility requirements.

## Current phase: reverse-engineer first

We are reconstructing the original OS X Mavericks 10.9 implementation before committing to a final Linux UI architecture.

```
Mavericks 10.9 reference
  -> REA: application bundles, NIBs, keyed archives, connections
  -> Ghidra/PyGhidra: Mach-O, Objective-C metadata, native implementations
  -> nsinspect: live AppKit hierarchy and runtime behavior
  -> UI_REFERENCE: provenance-backed findings and measurements
  -> UI_PLATFORM: reusable component, state, behavior, and SDK contracts
  -> Linux architecture, implementation, optimization, packaging
```

This research-first sequence prevents a superficial visual imitation from being mistaken for a faithful UI/UX implementation.

## Verified foundation

As of 2026-10-16:

| Area | Verified result |
|---|---|
| Static UI analysis | REA 6.4.0 successfully decodes real Mavericks NIBs and keyed archives; it is the primary static reverse-engineering tool. |
| Native analysis | Ghidra 12.1.2 + PyGhidra + JDK 21 successfully analyze real Mavericks Mach-O binaries and recover Objective-C methods and implementations. |
| Runtime inspection | nsinspect/mvprobe capture live AppKit windows, views, controls, menus, and runtime states in a macOS 10.9 QEMU guest. |
| TextEdit | 8 NIBs decoded; 15 classes, 1 category, and 253/253 native methods mapped. Ruler/inspector-bar implementation traced to NSTextView behavior. |
| Calculator | Main binary: 217/217 methods; BasicAndSci plug-in: 153/153; Hexadecimal plug-in: 77/77. Plug-in loading and view-switching contract investigated. |
| Evidence model | Static NIB, native binary, and runtime findings are cross-referenced without treating one evidence class as another. |

These are initial application-level results. They do not mean that Finder, Dock, WindowServer behavior, System Preferences, or the complete Mavericks desktop have already been reconstructed.

## Development roadmap

1. Complete and validate the current TextEdit/Calculator investigations.
2. Reverse-engineer Finder, Dock, System Preferences, window management, menus, dialogs, sheets, and shared system behavior.
3. Build a connected map of applications, frameworks, classes, methods, controls, states, transitions, and dependencies.
4. Complete evidence-backed UI_REFERENCE records and UI_PLATFORM implementation contracts.
5. Evaluate the Linux desktop architecture against those contracts.
6. Implement the system, integrate Linux applications and services, optimize resource use, and produce reproducible builds.

## Repository map

- `docs/PROJECT_DIRECTION.md` — authoritative project mission, current phase, architecture, and roadmap.
- `docs/UI_REFERENCE/` — extracted reference data, provenance, REA results, runtime captures, and native findings.
- `docs/UI_PLATFORM/` — schemas and specifications for turning reference evidence into a reusable Linux UI platform.
- `tools/uiref/` — REA workflows, Ghidra/PyGhidra scripts, runtime instrumentation, and evidence extraction.
- `tools/uiplatform/` — UI platform validation and generation tools.
- `packages/`, `configs/`, `scripts/` — earlier Linux prototypes, experiments, and reusable implementation material.

## Engineering principles

- Evidence before implementation; no guessing from screenshots as the primary method.
- REA first for static NIB/archive analysis; Ghidra for native code; nsinspect for live AppKit.
- Preserve provenance, binary hashes, tool versions, confidence, and limitations.
- Keep visual design, interaction behavior, and platform integration as explicit, testable contracts.
- Do not lock the final Linux toolkit or desktop stack prematurely.
- Optimize through measurement; avoid unnecessary background work and heavyweight dependencies.
- Do not redistribute proprietary Apple binaries, code, fonts, or artwork.

## Getting involved

The most valuable contributions at this stage are reproducible reverse-engineering, evidence validation, subsystem research, behavior/state modeling, and specification work. Implementation contributions should target documented contracts rather than inventing approximate behavior.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/COORDINATION.md](docs/COORDINATION.md).

---

**MavlinOS is intended to feel like Mavericks in everyday use while remaining Linux underneath.**
