# Contributing to MavlinOS

MavlinOS is a Linux-based operating-system project targeting faithful reproduction of the complete OS X Mavericks 10.9 UI/UX on an optimized Linux foundation.

**Current phase: research-first reverse engineering and specification.** The project is not yet a stable, installable OS release. The most useful contributions now produce reliable evidence and implementation-ready specifications rather than approximate visual substitutes.

Read [the current project direction](docs/PROJECT_DIRECTION.md) before starting.

## High-priority contribution areas

- Reverse-engineering original Mavericks application bundles, NIBs, keyed archives, Mach-O binaries, Objective-C implementations, and runtime behavior.
- Extending verified REA and Ghidra/PyGhidra workflows.
- Investigating Finder, Dock, System Preferences, window management, menus, dialogs, sheets, and shared system behavior.
- Correlating static resource, native binary, and runtime evidence.
- Building state machines, interaction contracts, component specifications, and validation tests.
- Improving reproducibility, provenance, automation, and evidence quality.

Implementation work is welcome when it follows a sufficiently grounded UI_PLATFORM contract or closes a clearly defined tooling gap.

## Toolchain

Use the existing toolchain before introducing another one:

- REA 6.4.0 for static bundle, NIB, and keyed-archive analysis.
- Ghidra 12.1.2 + PyGhidra + JDK 21 for native Mach-O and Objective-C analysis.
- nsinspect/mvprobe for live AppKit runtime observation in the Mavericks VM.
- Existing UI_REFERENCE/UI_PLATFORM schemas and tests for evidence and contract validation.

See [REA toolchain instructions](docs/UI_REFERENCE/rea-toolchain.md).

## Evidence and quality requirements

Every substantive finding must identify:
- The source application/framework and target binary.
- Binary SHA256 where applicable.
- Tool and version.
- NIB object, class, selector, method, IMP, address, or runtime capture identity.
- Evidence category: static resource, native binary, runtime, or inference.
- Confidence, limitations, and unresolved questions.

Do not infer runtime behavior from selector strings or static metadata alone. Do not use screenshots/OCR as the primary source of structural facts. Preserve raw evidence and make extraction reproducible.

## Repository coordination

Before editing, read:
- `AGENTS.md`
- `docs/COORDINATION.md`
- `.agents/README.md` and active claims

Respect path claims, shared-worktree safety rules, and existing validation gates. Do not overwrite another agent's work. Never use destructive Git operations against a shared worktree.

## Technology and implementation choices

The final Linux distribution, toolkit, compositor, window manager, and rendering architecture are intentionally not frozen. The earlier Arch/Xfce/GTK3 code is retained as a prototype and may be reused after evaluation; it is not a binding product requirement.

Do not add heavyweight runtimes, persistent daemons, or frequent polling without a measured need. Do not optimize by guesswork; record benchmarks and trade-offs.

## Licensing and reference material

Do not commit or redistribute proprietary Apple binaries, decompiled Apple source, fonts, sounds, or artwork. Commit only permitted derived facts, measurements, metadata, original implementation code, and appropriately licensed assets. Record provenance and licensing for reused components.

## Contribution workflow

1. Read the project direction and coordination rules.
2. Check claims, current findings, open issues, and existing tooling.
3. Select a bounded research or specification objective.
4. Claim the relevant paths before editing.
5. Use existing tools and preserve reproducible evidence.
6. Validate scripts, schemas, evidence mappings, and affected tests.
7. Update the relevant findings/specifications and progress log.
8. Commit a coherent, reviewed change according to repository coordination rules.

Do not mark a subsystem complete because its NIBs were decoded or its classes enumerated. Completion requires sufficient visual, structural, native, and runtime understanding of its important states and transitions.
