#!/usr/bin/env python3
"""Decompile selected functions, dump callers/callees, and follow xrefs.

Targets are given as OBJC_DECOMPILE_TARGETS="0x100006be0,showRuler:" pairs.
Output: JSON report (OBJC_DECOMPILE_OUT) plus one .c file per function next to
it, so the decompilation can be read directly and re-checked.
"""
import json
import os

from ghidra.app.decompiler import DecompInterface
from ghidra.program.model.symbol import SourceType
from ghidra.util.task import ConsoleTaskMonitor

prog = currentProgram
OUT = os.environ.get("OBJC_DECOMPILE_OUT", "/home/builder/vmwork/opencode/objc_decompile.json")
STAMP = os.environ.get("OBJC_DECOMPILE_STAMP", "textedit")

# name -> address, from objc_extract output, injected by the caller as JSON
INDEX = json.loads(os.environ["OBJC_DECOMPILE_INDEX"])

ifc = DecompInterface()
ifc.openProgram(prog)
monitor = ConsoleTaskMonitor()

fm = prog.getFunctionManager()
rm = prog.getReferenceManager()


def callers_of(addr):
    out = []
    try:
        refs = list(rm.getReferencesTo(addr))
    except Exception:
        refs = []
    for ref in refs:
        try:
            f = fm.getFunctionContaining(ref.getFromAddress())
            out.append({
                "from": str(ref.getFromAddress()),
                "from_offset": hex(ref.getFromAddress().getOffset()),
                "type": str(ref.getReferenceType()),
                "function": f.getName() if f else None,
            })
        except Exception:
            continue
    return out


def callees_of(func):
    out = []
    called = func.getCalledFunctions(monitor)
    for c in called:
        out.append({"name": c.getName(), "entry": hex(c.getEntryPoint().getOffset())})
    return sorted(out, key=lambda x: x["name"] or "")


def callee_names_by_selector(func):
    """Resolve call targets back to ObjC selectors when possible."""
    res = []
    for c in func.getCalledFunctions(monitor):
        entry = c.getEntryPoint().getOffset()
        hit = INDEX.get("by_imp", {}).get(hex(entry))
        res.append({
            "function": c.getName(),
            "entry": hex(entry),
            "selector": hit.get("selector") if hit else None,
            "owner": hit.get("owner") if hit else None,
        })
    return sorted(res, key=lambda x: (x["selector"] or "", x["function"] or ""))


report = {"program": str(prog.getName()), "ghidra": "12.1.2", "functions": []}

for key in ("showRuler:", "showRulerDelayed:", "toggleRich:",
            "updateForRichTextAndRulerState:", "toggleRichWithNewFileType:",
            "toggleRichWillLoseInformation", "isRichText",
            "convertTextForRichTextState:removeAttachments:"):
    entries = INDEX.get("selectors", {}).get(key)
    if not entries:
        report["functions"].append({"selector": key, "status": "not-found"})
        continue
    for e in entries:
        entry_off = int(e["imp"], 16)
        addr = prog.getAddressFactory().getDefaultAddressSpace().getAddress(entry_off)
        func = fm.getFunctionAt(addr)
        entry = {"selector": key, "owner": e.get("owner"), "kind": e.get("kind"),
                 "imp": e["imp"], "ghidra_function": e.get("ghidra_function"),
                 "types": e.get("types")}
        if func is None:
            entry["status"] = "no-ghidra-function"
            report["functions"].append(entry)
            continue
        res = ifc.decompileFunction(func, 120, monitor)
        df = getattr(res, "decompiledFunction", None)
        if df is not None:
            code = df.getC()
            path = os.path.join(os.path.dirname(OUT), f"{STAMP}_{key.replace(':', '_').replace('/', '_')}.c")
            with open(path, "w") as fh:
                fh.write(code)
            entry["decompiled"] = code
            entry["status"] = "ok"
            entry["file"] = os.path.basename(path)
        else:
            entry["status"] = "decompile-failed"
        entry["callers"] = callers_of(entry_off)
        entry["callees"] = callee_names_by_selector(func)
        report["functions"].append(entry)

with open(OUT, "w") as fh:
    json.dump(report, fh, indent=1)
ok = len([f for f in report["functions"] if f.get("status") == "ok"])
print("DECOMPILE_OK", ok, "of", len(report["functions"]), "->", OUT)