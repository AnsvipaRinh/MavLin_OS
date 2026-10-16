# REA as the primary reverse-engineering toolchain

**Status: ADOPTED.** REA (`rea-agents@6.4.0`, morluto/rea, MIT) is the default
first instrument for static reverse engineering in MavLinOS. Custom static
analysis is written only for capabilities REA demonstrably does not provide.

## Installation (verified 2026-10-16)

- Location: `/home/builder/.local/npm-global/lib/node_modules/rea-agents/`
  (`mcpName: io.github.morluto/rea`, repository `morluto/rea`).
- CLI: `rea` on PATH via `/home/builder/.local/npm-global/bin`.
- `rea doctor` was initially run before native tooling was installed: at that point Hopper/Ghidra/IDA were absent. **Ghidra 12.1.2 was subsequently installed and verified**; see the native-tier section below. REA's own native provider remains unconfigured (`provider_unavailable`). MCP skill registration was not performed as part of the initial audit.
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
| `inspect-native-dispatch-metadata` | Mach-O ObjC | **REA provider unavailable**; equivalent native analysis is operational through the documented Ghidra/PyGhidra workflow |
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

## Native tier — OPERATIONAL (Ghidra 12.1.2 + PyGhidra)

Installed and verified: `ghidra 12.1.2` at `/opt/ghidra`, `jdk21-openjdk` with
`archlinux-java set java-21-openjdk` (Ghidra 12.1.x requires JDK 21; the default
JDK 27 on this host is not accepted). PyGhidra is installed into Ghidra's own
venv (`/home/builder/.config/ghidra/ghidra_12.1.2_DEV/venv`), so headless
Python scripts work.

REA's own native tier still reports `provider_unavailable` — it needs
Hopper/Ghidra/IDA wired through its provider config, which is separate from
having Ghidra installed. Verified REA commands remain the agent-facing
interface for NIB/artifact work; for disassembly, decompilation, call graphs and
xrefs the documented workflow below is the supported path.

Workflow, scripts in `tools/uiref/ghidra/`, findings in
`docs/UI_REFERENCE/native-findings.md`:

```bash
export GHIDRA_INSTALL_DIR=/opt/ghidra
/opt/ghidra/support/analyzeHeadless /home/builder/ghidra_proj <proj> -import <macho> -overwrite
/opt/ghidra/support/pyghidraRun --headless /home/builder/ghidra_proj <proj> -process <name>   -postScript tools/uiref/ghidra/objc_extract.py      # classes/methods/IMPs
OBJC_DECOMPILE_INDEX=... /opt/ghidra/support/pyghidraRun --headless ...   -postScript tools/uiref/ghidra/objc_decompile.py    # decompile + callers/callees
DEC_ADDRS=0x... /opt/ghidra/support/pyghidraRun --headless ...   -postScript tools/uiref/ghidra/decompile_addrs.py  # ad-hoc addresses
```

Gotchas that cost real time and are now encoded in the scripts: Ghidra's
PyGhidra provider is separate from `-script` (use `pyghidraRun`); addresses
above 2 GiB overflow Java ints (use the address-space factory, not `toAddr`);
`program.getBytes` does not exist (use `memory.getByte`); and 10.9 binaries use
**absolute 24-byte** `method_t` entries, not the later 32-bit relative form.

**Verified update — 2026-10-16:** the native tier is operational. TextEdit and Calculator main/plugin binaries have been analyzed with the reusable PyGhidra scripts. Calculator coverage includes the main binary (217/217 methods), BasicAndSci (153/153), and Hexadecimal (77/77). REA's own native provider still reports `provider_unavailable`; do not describe Ghidra as an active REA provider. The direct headless Ghidra workflow is the supported native path. Remaining work: AppKit/framework analysis, Calculator runtime comparison across modes, and optional investigation of whether REA's provider interface can be connected to Ghidra without duplicating the working pipeline.

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
