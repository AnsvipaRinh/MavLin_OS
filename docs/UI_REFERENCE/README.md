# UI Reference — OS X Mavericks 10.9 ground truth

**Purpose:** an evidence-backed, data-first reconstruction of the real Mavericks UI/UX. This catalog is the reference source for future MavlinOS implementation specifications. It is incomplete by design while reverse engineering continues; gaps and uncertainty must remain visible.

## Evidence policy

The reference is reconstructed from original application bundles, compiled NIBs, keyed archives, Mach-O binaries, Objective-C metadata, framework data, and controlled runtime observations in the Mavericks VM.

Screenshots and OCR are not the primary extraction method. They may supplement a specific visual measurement or runtime behavior that cannot be established structurally or through instrumentation.

Keep evidence classes distinct:

- **[NIB]** static interface-resource facts: objects, connections, selectors, bindings, geometry, and menu definitions.
- **[BIN]** native binary facts: Objective-C classes, categories, methods, IMP addresses, decompilation, and references.
- **[RT]** runtime facts: actual AppKit windows, views, controls, menus, states, and interaction outcomes.
- **[INFERRED]** a reasoned interpretation that still needs verification.

A selector string is not proof that a method exists. A NIB connection is not proof that an action executes in a particular runtime state. A decompiler hypothesis is not a runtime observation.

## Current toolchain

| Tool | Role | Status |
|---|---|---|
| REA 6.4.0 | Primary agent-facing static analysis of application bundles, NIBs, keyed archives, object graphs, connections, and selectors | Operational; verified on TextEdit and Calculator |
| Ghidra 12.1.2 + PyGhidra + JDK 21 | Mach-O analysis, Objective-C metadata, selector/IMP/function mapping, decompilation, and native implementation investigation | Operational; reproducible headless scripts in `tools/uiref/ghidra/` |
| nsinspect | Live AppKit window/view/menu/control inspection inside the Mavericks guest | Operational for tested application states |
| mvprobe | Runtime probe and supporting measurements | Operational for tested probes |
| Existing catalog tools | Normalize, validate, and render evidence-backed reference data | Retained where they cover a demonstrated gap |

REA's native provider is **not** configured. Do not claim that REA itself performs the Ghidra disassembly/decompilation. The verified workflow uses REA for static bundle/NIB work and Ghidra/PyGhidra for native code.

See [rea-toolchain.md](rea-toolchain.md) for exact commands, versions, capabilities, and limitations.

## Current verified application findings

### TextEdit 1.9

- REA decoded 8 NIBs and recovered interface object/connection inventories.
- Ghidra/PyGhidra recovered 15 classes, 1 category, and 253/253 methods with selector, IMP, and Ghidra function mapping.
- `toggleRuler:` is a NIB selector string, not a method implemented by TextEdit.
- The actual ruler path is `DocumentWindowController.showRuler:` -> user defaults -> `NSTextView.setRulerVisible:`.
- The formatting inspector bar is controlled through `NSTextView.setUsesInspectorBar:`; no separate `NSRulerView` implementation was found in this application.
- Rich/plain conversion and its information-loss sheet have been traced in native code.

Full report: [native-findings.md](native-findings.md).

### Calculator

- Main binary: 217/217 methods mapped.
- `BasicAndSci.calcview`: 153/153 methods mapped.
- `Hexadecimal.calcview`: 77/77 methods mapped.
- Plugin loading, the `CalculatorView` protocol contract, view injection, and mode switching have been investigated.
- Runtime comparison of all modes and remaining cross-bundle details are still open.

Full report: [native-findings.md](native-findings.md) and [rea-findings.md](rea-findings.md).

## Data catalog

The `data/` directory contains structured reference records such as:
- components, controls, windows, surfaces, and NIB geometry;
- palette, typography, theme, assets metadata, and terminology;
- behavior and UI API inventories.

The `catalog/` directory contains generated human-readable views. Do not hand-edit generated catalog files; update their source data and run the documented generator and validators.

## Reproducible tooling

- `tools/uiref/` — REA workflows, evidence extraction, runtime instrumentation, and catalog generation.
- `tools/uiref/ghidra/` — reusable headless PyGhidra Objective-C extraction and decompilation scripts.
- `tests/uiref/` and native/REA evidence tests — validation of provenance, mappings, completeness, and report consistency.

Large raw analysis projects and full dumps may remain in the persistent analysis workspace. Commit compact evidence summaries, scripts, hashes, and reproducible instructions.

## Next research targets

The reference is not complete. Priority areas include Finder, Dock, System Preferences, window management, menu bar, dialogs and sheets, shared AppKit behavior, system processes, and state/animation transitions. Do not mark a subsystem complete merely because its resources or classes have been enumerated.
