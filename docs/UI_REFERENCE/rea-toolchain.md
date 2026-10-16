# REA as the primary reverse-engineering toolchain

**Status: ADOPTED.** REA (`rea-agents@6.4.0`, morluto/rea, MIT) is the default
first instrument for static reverse engineering in MavLinOS. Custom static
analysis is written only for capabilities REA demonstrably does not provide.

## Installation (verified 2026-10-16)

- Location: `/home/builder/.local/npm-global/lib/node_modules/rea-agents/`
  (`mcpName: io.github.morluto/rea`, repository `morluto/rea`).
- CLI: `rea` on PATH via `/home/builder/.local/npm-global/bin`.
- `rea doctor`: node healthy; **no Hopper, no Ghidra, no IDA** on this host
  (all three report `missing_analysis_engine`). MCP skill not registered
  (`rea setup` not run — deliberate: no blind config changes).
- Disk: REA itself is small (npm package); analysis outputs live under
  `/home/builder/vmwork/opencode/` (persistent, never `/tmp`).

## What works here (verified by execution, not by reading docs)

| Command | Target | Result |
|---|---|---|
| `decode-interface-builder <app>` | TextEdit 1.9, Calculator (10.9) | 8 / 4+ NIBs decoded: objects, connections, 108 / 52 selectors, control inventory, geometry (`NSFrame`), all with per-artifact SHA256 |
| `inspect-keyed-archive` | NIB archives | same engine as above (spot-checked) |
| `inspect-artifact` | .app bundles | bundle digest + graph (verified) |
| `analyze` / `inspect` | apps | **blocked** (needs provider) |
| `inspect-plist` | Info.plist | **blocked** (needs macOS native utils) |
| `inspect-macho` | Mach-O | **blocked** (needs macOS native utils) |
| `inspect-native-dispatch-metadata` | Mach-O ObjC | **blocked** (needs Hopper/Ghidra/IDA) |
| `decompile`, `function`, `trace-*` (native), `xrefs` | binaries | **blocked** (needs provider) |
| `inspect-binary-layout` | Mach-O | **blocked** (wants pwntools-ELF; ELF-only anyway) |
| `observe-native-*` (LLDB) | processes | **blocked** (needs macOS) |

Capability caps found by testing: `decode-interface-builder --max-documents`
is server-capped at 64 — analyse large bundles via minimal copies (English +
`Base.lproj` only) or per-file `inspect-keyed-archive`.

## Invocation per task class

- **NIB structure, actions, selectors, geometry:** `rea decode-interface-builder
  <minimal .app copy> --format json`. Always record `evidence_id`,
  `target_sha256`, provider id/version. Summaries (not 25 MB raw dumps) go to
  `docs/UI_REFERENCE/runtime/raw/rea/`.
- **Which NIB defines a runtime-observed object:** match class names +
  `NSFrame` geometry + connection selectors against `nsinspect` captures.
- **Menu commands → implementation selectors:** runtime capture gives the item
  title + enabled/state; REA NIB selectors give the implementation name
  (e.g. menu `Show Ruler` → `toggleRuler:`, `Make Rich Text` → `toggleRich:`).
- **Mach-O ObjC classes/methods:** REA cannot do this here — use repo
  `tools/uiref/machobjc.py` / `objc_index.py` (retained, no equivalent).
- **Live windows/views/menus/geometry:** REA cannot do this anywhere — use
  `nsinspect` (retained; different problem from static analysis).
- **Disassembly / decompile / call graphs / xrefs:** unavailable until a
  provider is installed (see below). Do not hand-roll a disassembler;
  record the need and use NIB + runtime evidence meanwhile.
- **Unsupported format / failed analysis:** record command, exit code,
  `code`/`category` (`provider_unavailable`, `capability_unavailable`,
  `unsupported_provider`), and the exact remediation string. Never present
  a blocked command's absence of output as a finding.

## Unlocking the native tier (explicit next step, not attempted)

Install Ghidra 12.1.x + set `GHIDRA_INSTALL_DIR` (+ raise
`REA_GHIDRA_STARTUP_TIMEOUT_MS` for large binaries). Caveats found by
inspection: only JDK 27 is installed and Ghidra 12.1.x wants JDK 17–21, so a
compatible JDK is needed too (~500 MB download + JDK). Decide on disk budget
first; until then the NIB + runtime tiers carry the work.

## Tool audit (custom tools vs REA)

| Tool | Verdict |
|---|---|
| `nsinspect` (live NSWindow/NSView/menu extraction) | **RETAIN** — no REA equivalent exists or can exist (live AppKit runtime) |
| `mvprobe` (runtime probe) | **RETAIN** — same reason |
| `tools/uiref/machobjc.py`, `objc_index.py` (Mach-O ObjC metadata) | **RETAIN** — REA needs a provider for this here |
| `tools/uiref/nib_geometry.py`, NIB stages of `extract_nibs.py` | **SUPERSEDED** for decoding — REA returns the same facts + connections + provenance; keep only for offline/host-side diffing if a gap is proven |
| `strings_extract.py` | **RETAIN for now** — REA string search needs a provider; re-audit after Ghidra |
| New custom static parsers/analyzers | **FORBIDDEN** until REA + existing tools are proven insufficient for the task |

## Evidence rules

Every REA-derived finding keeps: binary SHA256, format/arch, REA version,
command + provider id/version, evidence_id, selector/symbol identity,
artifact path + archive SHA256, and a link to the runtime/NIB observation it
supports or contradicts. Static findings are NEVER promoted to runtime facts;
the mapping docs state both sides explicitly.
