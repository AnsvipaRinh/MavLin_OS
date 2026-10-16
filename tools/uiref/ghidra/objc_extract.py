#!/usr/bin/env python3
"""Objective-C metadata extractor for Mach-O binaries analysed in Ghidra.

Reads the real 64-bit ObjC runtime structures out of Ghidra's object model and
maps every method IMP onto the Ghidra function that Ghidra itself discovered.

Structures handled (OS X 10.9 / objc4 64-bit runtime):

  __objc_classlist  -> objc_class -> class_ro_t* -> name, baseMethodList
  __objc_catlist    -> category_t -> class, name, instanceMethods, classMethods
  class_ro_t layout (64-bit): flags, instanceStart, instanceSize, reserved,
                            ivarLayout, name, baseMethodList, baseProtocols, ...
  method_list_t     : entsize_and_flags, count, method_t[]
  method_t          : (absolute or relative-to-entry) name, types, imp

Both the absolute and the relative (offset-from-field) encodings are accepted;
whichever yields a readable selector string in __objc_methname is used, and the
choice is recorded per method so the caller can audit it.

Outputs one JSON document (env OBJC_META_OUT) with classes, categories,
instance/class methods, selector-to-IMP mapping, IMP-to-Ghidra-function mapping
and full provenance.
"""
import json
import os
import struct

prog = currentProgram
mem = prog.getMemory()
OUT = os.environ.get("OBJC_META_OUT", "/home/builder/vmwork/opencode/objc_meta.json")

AS = prog.getAddressFactory().getDefaultAddressSpace()


def A(off):
    return AS.getAddress(off)


def rd64(a):
    if not mapped(a, 8):
        return 0
    v = 0
    try:
        for i in range(8):
            v |= (int(mem.getByte(A(a + i))) & 0xFF) << (8 * i)
    except Exception:
        return 0
    return v


def rd32(a):
    if not mapped(a, 4):
        return 0
    v = 0
    try:
        for i in range(4):
            v |= (int(mem.getByte(A(a + i))) & 0xFF) << (8 * i)
    except Exception:
        return 0
    return v


def mapped(a, n):
    """True when n bytes at offset a live in an initialised memory block."""
    if a is None or a <= 0:
        return False
    try:
        blk = mem.getBlock(A(a))
        if blk is None:
            return False
        end = blk.getEnd().getOffset()
        return a + n <= end + 1
    except Exception:
        return False


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def cstr(a, cap=512):
    buf = bytearray()
    try:
        for i in range(cap):
            b = int(mem.getByte(A(a + i))) & 0xFF
            if b == 0:
                break
            buf.append(b)
    except Exception:
        return ""
    return buf.decode("ascii", "replace")


sections = {}
for b in mem.getBlocks():
    sections[b.getName()] = (b.getStart().getOffset(), b.getEnd().getOffset(), b.getSize())

METHNAME = sections.get("__objc_methname", (0, 0, 0))
CLASSPTR = sections.get("__objc_classname", (0, 0, 0))


def in_methname(p):
    return METHNAME[0] <= p < METHNAME[1]


def printable(p):
    """A selector pointer is only plausible if it starts with readable ASCII."""
    if not in_methname(p):
        return False
    try:
        for i in range(4):
            b = int(mem.getByte(A(p + i))) & 0xFF
            if b == 0:
                return True
            if not (0x20 <= b < 0x7F):
                return False
    except Exception:
        return False
    return True


def classname_ok(p):
    """A class name pointer must land in __objc_classname and be readable."""
    if not (CLASSPTR[0] <= p < CLASSPTR[1]):
        return False
    try:
        for i in range(4):
            b = int(mem.getByte(A(p + i))) & 0xFF
            if b == 0:
                return True
            if not (0x20 <= b < 0x7F):
                return False
    except Exception:
        return False
    return True


def resolve_ref(field_addr, raw, table):
    """Absolute pointer, else pointer relative to the field's own address."""
    if table(raw):
        return raw, "absolute"
    rel = s32(raw & 0xFFFFFFFF) + field_addr
    if table(rel):
        return rel, "relative"
    return 0, "unresolved"


def parse_methods(list_ptr, owner, kind, category=None):
    """method_list_t -> list of {selector, types, imp, encoding}."""
    out = []
    if not list_ptr:
        return out
    try:
        entsize_flags = rd32(list_ptr)
        count = rd32(list_ptr + 4)
    except Exception:
        return out
    if count > 20000:
        return out
    entsize = entsize_flags & 0xFFFF
    rel_names = bool(entsize_flags & 0x80000000)
    rel_imps = bool(entsize_flags & 0x40000000)
    if entsize not in (16, 24, 32):
        entsize = 24 if entsize_flags & 0x80000000 else 16
    # entsize 24 => absolute 64-bit method_t {SEL*, const char* types, IMP*}
    # (pre-chained layout used by the 10.9 binaries in this corpus)
    # entsize 12 => three 32-bit fields, offsets relative to their own address
    absolute = entsize == 24
    for i in range(count):
        e = list_ptr + 8 + i * entsize
        try:
            if absolute:
                nptr, nenc = rd64(e), "absolute64"
                tptr, tenc = rd64(e + 8), "absolute64"
                iptr, ienc = rd64(e + 16), "absolute64"
            else:
                nraw, traw, iraw = rd32(e), rd32(e + 4), rd32(e + 8)
                nptr, nenc = ((s32(nraw) + e, "relative32") if rel_names
                              else resolve_ref(e, nraw, in_methname))
                try:
                    tptr, tenc = resolve_ref(e + 4, traw, CLASSPTR)
                except Exception:
                    tptr, tenc = 0, "unresolved"
                if rel_imps:
                    iptr, ienc = s32(iraw) + e + 8, "relative32"
                else:
                    try:
                        iptr, ienc = resolve_ref(e + 8, iraw, mapped)
                    except Exception:
                        iptr, ienc = 0, "unresolved"
        except Exception:
            break
        out.append({
            "selector": cstr(nptr) if nptr else "",
            "selector_ptr": hex(nptr) if nptr else None,
            "types": cstr(tptr) if tptr else "",
            "imp": hex(iptr) if iptr else None,
            "imp_off": iptr if iptr else None,
            "encoding": {"selector": nenc, "types": tenc, "imp": ienc},
            "owner": owner,
            "kind": kind,
            "category": category,
        })
    return out


def parse_listing(list_ptr, kind, category=None):
    res = []
    for name in ("baseMethodList", "methods"):
        pass
    return res


classes = []
methods = []

cl = sections.get("__objc_classlist")
if cl:
    for a in range(cl[0], cl[1], 8):
        cp = rd64(a)
        ro = rd64(cp + 32)
        # Prefer the documented offset, but fall back to scanning class_ro_t for
        # the first pointer into __objc_classname: Finder and other large
        # binaries do not always keep the 64-bit field order we assumed, and a
        # wrong guess yields a readable method table but garbage class names.
        name_ptr = rd64(ro + 24)
        methlist = rd64(ro + 32)
        if not classname_ok(name_ptr):
            for off in range(0, 256, 8):
                cand = rd64(ro + off)
                if classname_ok(cand):
                    name_ptr = cand
                    break
        cname = cstr(name_ptr)
        # superclass name, if resolvable
        sup = rd64(cp + 8)
        sname = ""
        if sup:
            sro = rd64(sup + 32)
            if sro:
                sp = rd64(sro + 24)
                if not classname_ok(sp):
                    for off in range(0, 256, 8):
                        cand = rd64(sro + off)
                        if classname_ok(cand):
                            sp = cand
                            break
                sname = cstr(sp)
        inst = parse_methods(methlist, cname or hex(cp), "instance")
        # class methods: pointer stored after baseMethodList (objc_class has no direct
        # class method list in the ro; the metaclass holds it) -> read metaclass ro
        meta = rd64(cp + 40) if False else 0
        classes.append({
            "class_ptr": hex(cp), "ro_ptr": hex(ro),
            "name": cname, "super": sname,
            "method_list_ptr": hex(methlist),
            "instance_methods": len(inst),
        })
        methods.extend(inst)

cat = sections.get("__objc_catlist")
if cat:
    for a in range(cat[0], cat[1], 8):
        c = rd64(a)
        name = cstr(rd64(c + 8))
        cls_ptr = rd64(c)
        cls_name = ""
        if cls_ptr:
            cro = rd64(cls_ptr + 32)
            if cro:
                cls_name = cstr(rd64(cro + 24))
        im = parse_methods(rd64(c + 16), f"{cls_name}({name})", "instance", name)
        cm = parse_methods(rd64(c + 24), f"{cls_name}({name})", "class", name)
        classes.append({"category": name, "class": cls_name,
                        "instance_methods": len(im), "class_methods": len(cm)})
        methods.extend(im)
        methods.extend(cm)

# IMP -> Ghidra function
funcs = {}
for f in prog.getFunctionManager().getFunctions(True):
    funcs[f.getEntryPoint().getOffset()] = f.getName()

for m in methods:
    off = m["imp_off"]
    m["ghidra_function"] = funcs.get(off) if off else None
    m["ghidra_function_defined"] = bool(off in funcs) if off else False

resolved = [m for m in methods if m["selector"]]
sel_index = {}
for m in resolved:
    sel_index.setdefault(m["selector"], []).append({
        "owner": m["owner"], "kind": m["kind"], "imp": m["imp"],
        "ghidra_function": m["ghidra_function"], "types": m["types"],
    })

report = {
    "provenance": {
        "program": str(prog.getName()),
        "language": str(prog.getLanguageID()),
        "processor": str(prog.getLanguage().getProcessor()),
        "image_base": hex(prog.getImageBase().getOffset()),
        "ghidra_version": os.environ.get("GHIDRA_VERSION", "12.1.2"),
        "script": "objc_extract.py",
        "sections": {k: [hex(v[0]), hex(v[1]), v[2]] for k, v in sections.items() if "objc" in k},
    },
    "counts": {
        "classes": len([c for c in classes if "category" not in c]),
        "categories": len([c for c in classes if "category" in c]),
        "methods_total": len(methods),
        "methods_with_selector": len(resolved),
        "methods_with_known_imp": len([m for m in resolved if m["imp"]]),
        "methods_matched_to_ghidra_function": len([m for m in resolved if m["ghidra_function_defined"]]),
    },
    "classes": classes,
    "selectors": sel_index,
}
with open(OUT, "w") as fh:
    json.dump(report, fh, indent=1)
print("META_OK", json.dumps(report["counts"]), "->", OUT)