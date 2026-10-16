# MavlinOS — Project Direction

**Last reviewed: 2026-10-16**

## Mission

MavlinOS is a Linux-based operating-system project whose defining objective is to reproduce the visual identity, interaction model, and everyday user experience of **OS X Mavericks 10.9** as faithfully as technically possible, while retaining a maintainable, capable, and highly optimized Linux foundation.

The target is not a theme that merely resembles Mavericks. It is a coherent system experience: window management, application lifecycle, menu bar, Dock, Finder-like file management, system applications, dialogs, sheets, controls, keyboard and pointer interactions, transitions, animations, persistence, and cross-application consistency.

The Linux implementation should preserve Linux-native system services and application compatibility wherever practical. The user-facing experience should be Mavericks-faithful; the underlying implementation should remain efficient, maintainable, and appropriate for Linux.

## Current development phase: reference reconstruction

**The project is currently in a research-first reverse-engineering phase. It is not a finished or release-ready operating system.**

The immediate objective is to understand the original Mavericks system deeply enough to create an evidence-backed implementation blueprint. Do not begin broad UI implementation based on visual guesses or old prototype assumptions.

The work proceeds through five gates:

1. **Recover the reference system** — inspect real OS X 10.9 application bundles, NIBs, keyed archives, Objective-C metadata, native implementations, and runtime behavior.
2. **Build verified evidence** — preserve binary hashes, tool versions, addresses, source artifacts, runtime captures, confidence, and explicit limitations.
3. **Specify the system** — describe components, geometry, visual tokens, states, transitions, animations, input behavior, persistence, and cross-component contracts.
4. **Select and implement the Linux architecture** — evaluate windowing, rendering, toolkit, compositor, system services, and application integration against the verified specification. Do not assume the old GTK/Xfce prototype is the final architecture.
5. **Optimize and package** — build a lean Linux system, measure resource and power costs, and introduce hardware profiles only where justified by evidence.

A subsystem is not ready for implementation merely because its NIBs or classes have been enumerated. Its important states, transitions, implementation mechanisms, and runtime behavior must be sufficiently understood and documented.

## Verified research foundation (2026-10-16)

The repository now contains a working, reproducible reverse-engineering toolchain:

- **REA 6.4.0** is the primary agent-facing tool for static application-bundle, NIB, and keyed-archive analysis.
- **Ghidra 12.1.2 + PyGhidra + JDK 21** provide headless Mach-O analysis, Objective-C metadata extraction, IMP-to-function mapping, decompilation, and cross-reference investigation. REA's own native provider is not configured; do not claim otherwise.
- **nsinspect / mvprobe** capture live AppKit windows, view hierarchies, controls, menus, and runtime states inside the Mavericks 10.9 QEMU guest.
- Findings are correlated across static NIB evidence, native binary evidence, and runtime observations. These evidence classes must remain distinct.

Initial application results:

- **TextEdit 1.9:** 8 NIBs decoded; native analysis recovered 15 classes, 1 category, and 253/253 methods with selector, IMP, and Ghidra function mapping. The actual ruler implementation was traced to `DocumentWindowController.showRuler:`; the earlier `toggleRuler:` assumption was disproved. Ruler and inspector-bar behavior are controlled through NSTextView.
- **Calculator:** main binary and both relevant calculation plug-ins have been investigated. The main binary contains 217/217 mapped methods; BasicAndSci has 153/153; Hexadecimal has 77/77. Plugin discovery, the `CalculatorView` protocol contract, and mode switching have been reconstructed. Runtime comparison of all modes and some cross-bundle questions remain open.

These are initial, bounded findings—not proof that all of Mavericks has been reconstructed.

## Reference and implementation architecture

```
Original OS X Mavericks 10.9
        |
        v
Reverse engineering
REA + Ghidra/PyGhidra + nsinspect + controlled VM experiments
        |
        v
UI_REFERENCE — evidence-backed facts
        |
        v
UI_PLATFORM — versioned data contracts and implementation specifications
        |
        v
Linux platform architecture and adapters (technology selection still evidence-driven)
        |
        v
MavlinOS applications, desktop shell, system integration, optimized Linux build
```

The UI platform separates:
- **Design system:** palette, typography, metrics, assets, visual states.
- **Interaction system:** input semantics, focus, keyboard/pointer behavior, state machines, transitions, animations.
- **UI platform:** reusable windows, controls, menus, dialogs, application integration, and system-wide contracts.

See [UI Reference](UI_REFERENCE/README.md) and [UI Platform](UI_PLATFORM/README.md).

## Tooling policy

Use the strongest existing tool before writing custom analysis code:

| Investigation | Primary instrument |
|---|---|
| Application bundles, NIBs, keyed archives, static UI connections | REA |
| Mach-O, Objective-C metadata, IMPs, decompilation, call analysis | Ghidra + PyGhidra scripts |
| Live AppKit windows, views, menus, controls, runtime state | nsinspect / mvprobe in the Mavericks VM |
| Evidence contracts, validation, catalog generation | Existing MavlinOS schemas and tools |

Custom tools remain appropriate where they cover a demonstrated gap—for example, live AppKit inspection. Do not create another NIB parser or native analyzer without first proving that REA and the installed native toolchain cannot provide the required capability.

## Technical principles

- Evidence before implementation; distinguish static facts, runtime facts, inferences, and unresolved questions.
- Every material finding retains provenance, target binary SHA256, tool/version, addresses or object identity, confidence, and limitations.
- Never promote a selector string, NIB connection, or decompiler hypothesis into a runtime-confirmed behavior without verification.
- Preserve reproducibility and raw evidence; commit compact summaries and scripts rather than unnecessary generated dumps.
- Keep the final Linux base, toolkit, compositor, window manager, and rendering architecture open until evaluated against fidelity, performance, maintainability, and compatibility requirements.
- Optimize by measurement, not assumptions. Avoid unnecessary daemons, polling, heavyweight runtimes, and duplicated system services.
- Do not redistribute Apple proprietary binaries, source code, fonts, or artwork. Record provenance and licensing; use independently created or appropriately licensed implementation assets.

## Hardware strategy

The product is a Linux OS, not a MacBook-only distribution. Keep a generic system core separate from optional hardware profiles. MacBook10,1 may be used as a reference/validation profile, but it does not define the product or constrain the entire architecture.

## Research roadmap

1. Complete the current application investigations and validate runtime state coverage.
2. Reverse-engineer major system surfaces and shared infrastructure: Finder, Dock, System Preferences, window management, menu bar, dialogs, sheets, and system services.
3. Build connected component, behavior, and dependency maps across applications and frameworks.
4. Close the UI_REFERENCE and UI_PLATFORM evidence/specification gaps.
5. Evaluate Linux implementation architectures only after the relevant specifications are mature.
6. Implement, integrate, benchmark, and package the optimized Linux system.

The detailed subsystem queue and evidence status belong in [docs/PROGRESS.md](PROGRESS.md) and the relevant UI reference reports.

## Repository contents and status

This repository contains historical Linux desktop prototypes alongside the newer reverse-engineering infrastructure and UI specifications. The earlier GTK/Xfce implementation, Mission Control prototype, MacBook-specific experiments, and their documentation are retained as project history and reusable material; they must not be mistaken for the final MavlinOS architecture or for a complete OS release.

There is currently **no stable installation image or production release**. Status claims must be tied to tests and evidence, not to the presence of a package, mock, or prototype.

## Start here

- [Project direction](PROJECT_DIRECTION.md)
- [UI reference and evidence](UI_REFERENCE/README.md)
- [REA toolchain](UI_REFERENCE/rea-toolchain.md)
- [Native reverse-engineering findings](UI_REFERENCE/native-findings.md)
- [REA/NIB findings](UI_REFERENCE/rea-findings.md)
- [UI platform architecture and contracts](UI_PLATFORM/README.md)
- [Agent coordination](COORDINATION.md)
- [Progress log](PROGRESS.md)
- [Reverse-engineering tools](../tools/uiref/)
