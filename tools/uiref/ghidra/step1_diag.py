#!/usr/bin/env python3
"""Objective-C metadata probe for a Mach-O binary analysed in Ghidra.

Run headless:
  pyghidraRun --headless <projdir> <proj> -process <prog> -postScript step1_diag.py

Writes a JSON probe to OUT (env var or default path). Everything is read from
Ghidra's own object model (Memory / SymbolTable / FunctionManager), never from
a hand-rolled Mach-O parser, so the probe reflects whatever Ghidra actually
understood about the file.
"""
import json
import os

prog = currentProgram
mem = prog.getMemory()
OUT = os.environ.get("OBJC_DIAG_OUT", "/home/builder/vmwork/opencode/objc_diag.json")

sections = {}
for b in mem.getBlocks():
    sections[b.getName()] = (b.getStart().getOffset(), b.getEnd().getOffset(), b.getSize())


AS = prog.getAddressFactory().getDefaultAddressSpace()


def A(off):
    """Address from a 64-bit offset (Ghidra Java ints overflow above 2 GiB)."""
    return AS.getAddress(off)


def rd64(addr):
    v = 0
    for i in range(8):
        v |= (int(mem.getByte(A(addr + i))) & 0xFF) << (8 * i)
    return v


def cstr(addr, cap=256):
    buf = bytearray()
    try:
        for i in range(cap):
            b = int(mem.getByte(A(addr + i))) & 0xFF
            if b == 0:
                break
            buf.append(b)
    except Exception:
        return ""
    return buf.decode("ascii", "replace")


out = {"program": str(prog.getName()),
       "language": str(prog.getLanguageID()),
       "processor": str(prog.getLanguage().getProcessor()),
       "image_base": hex(prog.getImageBase().getOffset()),
       "objc_sections": {k: [hex(v[0]), hex(v[1]), v[2]] for k, v in sections.items() if "objc" in k}}

# --- selectors: every unique name in __objc_methname -----------------------
mn = sections.get("__objc_methname")
selectors = []
if mn:
    cur = bytearray()
    for a in range(mn[0], mn[1]):
        byte = int(mem.getByte(A(a))) & 0xFF
        if byte == 0:
            if cur:
                selectors.append(cur.decode("ascii", "replace"))
            cur = bytearray()
        else:
            cur.append(byte)
out["selector_count"] = len(selectors)
out["selectors_sample"] = selectors[:50]

# --- class list ------------------------------------------------------------
cl = sections.get("__objc_classlist")
classes = []
if cl:
    for a in range(cl[0], cl[1], 8):
        cp = rd64(a)
        rec = {"class_ptr": hex(cp), "isa": hex(rd64(cp)), "super_ptr": hex(rd64(cp + 8))}
        ro = rd64(cp + 32)          # class_ro_t* / class_rw_t* in objc_class slot 4
        rec["ro_ptr"] = hex(ro)
        # class_ro_t: flags(4) instStart(4) instSize(4) reserved(4) ivars methods protocols
        #              properties ivarlayout name weakClassLayout baseProperties
        rec["ro_name"] = cstr(rd64(ro + 56)) if ro else ""
        rec["methods_ptr"] = hex(rd64(ro + 24)) if ro else ""
        rec["name"] = cstr(rd64(cl[0] + 0))  # placeholder, overwritten below
        rec.pop("name")
        classes.append(rec)
out["classes"] = classes
out["class_count"] = len(classes)

# --- function inventory ----------------------------------------------------
fns = []
for f in prog.getFunctionManager().getFunctions(True):
    fns.append((f.getName(), f.getEntryPoint().getOffset()))
out["function_count"] = len(fns)

KEYS = ("toggleRuler", "toggleRich", "Inspector", "Ruler", "ruler", "stylePopup", "makeRich")
out["target_functions"] = sorted((n, hex(o)) for n, o in fns if any(k in n for k in KEYS))

with open(OUT, "w") as fh:
    json.dump(out, fh, indent=1)
print("DIAG_OK", out["class_count"], "classes", out["selector_count"], "selectors",
      out["function_count"], "functions ->", OUT)