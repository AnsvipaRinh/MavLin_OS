# MavlinOS Architecture

**Status: target architecture and research pipeline.** This document supersedes the earlier Xfce/GTK3 implementation diagram as the statement of the intended product architecture. Existing prototype code remains in the repository, but it does not lock the final technology choices.

See [Project Direction](docs/PROJECT_DIRECTION.md) for the mission, phase gates, and current research status.

## 1. Product architecture

MavlinOS separates the user-facing Mavericks experience from the Linux implementation beneath it.

```
┌──────────────────────────────────────────────────────────────┐
│                  MAVERICKS-FAITHFUL UI / UX                  │
│ Finder · Dock · menu bar · windows · dialogs · system apps   │
│ controls · typography · states · animations · interactions  │
├──────────────────────────────────────────────────────────────┤
│                    MAVLINOS UI PLATFORM                      │
│ Design system · interaction system · reusable UI contracts  │
│ component model · state machines · application integration   │
├──────────────────────────────────────────────────────────────┤
│                 LINUX DESKTOP INTEGRATION                    │
│ Windowing · rendering · input · shell · app adapters         │
│ system services · file/network/power/media integration       │
├──────────────────────────────────────────────────────────────┤
│                  LINUX USERSPACE / KERNEL                    │
│ Linux applications and APIs · system services · drivers     │
└──────────────────────────────────────────────────────────────┘
```

The top layers reproduce the original user experience. The lower layers use Linux-native mechanisms wherever they provide a sound, efficient implementation.

## 2. Evidence-to-implementation pipeline

The implementation architecture is derived from the original system, not invented independently.

```
OS X Mavericks 10.9 reference
        |
        v
REA — NIBs, keyed archives, bundles, connections
        |
Ghidra + PyGhidra — Mach-O, Objective-C, IMPs, native methods
        |
nsinspect — live AppKit windows, views, controls, menus, states
        v
UI_REFERENCE — provenance-backed facts and measurements
        |
        v
UI_PLATFORM — schemas, visual contracts, behavior models, SDK
        |
        v
Linux platform evaluation -> implementation -> validation
        |
        v
Optimized MavlinOS build
```

### Evidence layers

- **Static resource evidence:** NIBs, keyed archives, object graphs, connections, strings, assets metadata.
- **Native implementation evidence:** Mach-O structure, Objective-C classes/selectors/IMPs, decompilation, call relationships.
- **Runtime evidence:** live AppKit hierarchy, window geometry, controls, menu states, interaction outcomes.
- **Derived specifications:** components, tokens, state machines, animation contracts, application integration requirements.

These evidence classes remain distinct. Every derived claim records provenance, target hashes, tool versions, confidence, and unresolved limitations.

## 3. UI platform layers

### Design system

Defines the visual language: colors, typography, dimensions, materials, gradients, shadows, control appearances, icon metrics, and visual states.

### Interaction system

Defines input and behavior: focus, keyboard and pointer semantics, hit regions, drag-and-drop, state transitions, timing, animation, accessibility, and persistence.

### UI platform

Defines reusable system surfaces and application contracts: windows, controls, menus, dialogs, sheets, notifications, toolbars, sidebars, application lifecycle, and system integration.

The versioned data contracts and acceptance rules are in [docs/UI_PLATFORM](docs/UI_PLATFORM/README.md).

## 4. Linux implementation strategy

The final Linux implementation stack is intentionally **not frozen**.

Candidates must be evaluated against:
- Fidelity to the recovered Mavericks behavior and visual measurements.
- Integration with Linux-native applications and services.
- Runtime footprint, wakeups, memory use, responsiveness, and power consumption.
- Accessibility, input methods, multi-display support, and application compatibility.
- Maintainability, upstream health, licensing, and reproducible packaging.

The earlier Arch/Xfce/GTK3 implementation is a prototype and source of reusable experiments—not a mandatory final design. Avoid selecting a toolkit or desktop environment merely because it is already present in the repository.

Keep system backends Linux-native where practical. Implement adapters or replace application frontends where required to achieve a coherent user experience.

## 5. Hardware strategy

The product is a Linux OS, not a single-device distribution. Maintain a generic core and optional hardware profiles.

MacBook10,1 remains a useful reference profile for hardware-specific validation, but it must not dictate the generic architecture. Hardware-dependent choices belong in isolated profiles and must be supported by actual measurements and validation.

## 6. Development stages

1. **Reference reconstruction:** inspect original applications, frameworks, system processes, resources, and runtime behavior.
2. **Evidence consolidation:** validate facts and connect NIB, native, and runtime observations.
3. **Specification:** complete reusable visual, interaction, component, and system contracts.
4. **Platform selection:** benchmark and evaluate Linux windowing/rendering/toolkit choices.
5. **Implementation:** build the shell, system surfaces, applications, and integration against those contracts.
6. **Optimization and delivery:** measure, tune, package, and validate the resulting Linux system.

## 7. Existing prototype code

The repository retains earlier packages, configurations, scripts, and experiments, including GTK/Xfce surfaces, Mission Control, Launchpad, and MacBook-specific work. Treat these as historical implementation material. Reuse them only after checking whether they satisfy the current specification and architecture.

Do not infer that an item is part of the final system merely because it exists or has previously been marked implemented.
