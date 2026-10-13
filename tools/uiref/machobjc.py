#!/usr/bin/env python3
"""machobjc.py - dump the Objective-C class model from a Mach-O dylib/binary.

Pure stdlib parser for 64-bit Mach-O (__DATA/__DATA_CONST + __TEXT): class list,
categories, instance variables and both method lists. That class model *is* the
public contract a UI system is built on: who draws controls, who owns focus,
who reacts to mouse/keyboard. For Mavericks we dump the real AppKit, and the
frameworks our desktop has to interoperate with.

    class Model:
      name, super, ivars[], methods{name, types, kind}, meta (class-level)
      categories (attached via catlist)
    also: protocol list names, and ObjC selectors seen in __objc_methnames

Usage:
    machobjc.py <macho-file> [--out FILE] [--classes-only]
"""
import argparse, json, struct, sys


class MachO:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.buf = fh.read()
        self.sections = {}
        self.parse_header()

    def parse_header(self):
        b = self.buf
        magic = struct.unpack_from("<I", b, 0)[0]
        if magic in (0xFEEDFACF, 0xFEEDFACF):
            self.bits, self.endian = 64, "<"
        elif magic in (0xFEEDFACE,):
            self.bits, self.endian = 32, "<"
        elif magic in (0xCAFEBABE, 0xBEBAFECA):
            # fat binary: take the first x86_64 slice
            n = struct.unpack_from(">I", b, 4)[0]
            off = 0
            for i in range(n):
                cpu, sub, o = struct.unpack_from(">III", b, 8 + i * 20)
                if cpu in (0x01000007, 7):
                    off = o
                    break
            self.buf = b[off:]
            self.parse_header()
            return
        else:
            raise SystemExit(f"unsupported magic {magic:#x}")
        e = self.endian
        ncmds = struct.unpack_from(e + "I", self.buf, 16)[0]
        off = 32 if self.bits == 64 else 28
        for _ in range(ncmds):
            cmd, cmdsize = struct.unpack_from(e + "II", self.buf, off)
            if cmd == 0x19:  # LC_SEGMENT_64
                name = self.buf[off + 8:off + 24].split(b"\0")[0].decode()
                nsects = struct.unpack_from(e + "I", self.buf, off + 64)[0]
                so = off + 72
                for _s in range(nsects):
                    sname = self.buf[so:so + 16].split(b"\0")[0].decode()
                    saddr, ssize = struct.unpack_from(e + "QQ", self.buf, so + 32)
                    foff = struct.unpack_from(e + "I", self.buf, so + 48)[0]
                    self.sections[sname] = (foff, ssize, saddr)
                    so += 80
            off += cmdsize

    def va2off(self, addr):
        """Map a virtual address to a file offset using the section table."""
        for _name, (foff, size, vaddr) in self.sections.items():
            if vaddr <= addr < vaddr + size:
                return foff + (addr - vaddr)
        return None

    def cstr(self, addr):
        p = self.va2off(addr)
        if p is None:
            return None
        end = self.buf.find(b"\0", p)
        return self.buf[p:end if end > 0 else p].decode("utf-8", "replace")

    def data_at(self, section, addr, fmt, count=1):
        base, size = self.sections.get(section)
        if base is None:
            return None
        p = base + (addr - self.section_vmaddr(section))
        try:
            return struct.unpack_from(self.endian + fmt, self.buf, p, count)
        except struct.error:
            return None

    def section_vmaddr(self, name):
        # vmaddr == fileoff for all sections we use, so file offset arithmetic works
        base, _ = self.sections.get(name, (0, 0))
        return base

    def list_at(self, section, addr, ptr_fmt="Q"):
        """Iterate a list of pointers starting at vmaddr."""
        base, size = self.sections.get(section)
        if base is None or addr == 0:
            return []
        out = []
        p = base + addr
        while p < base + size:
            v = struct.unpack_from(self.endian + ptr_fmt, self.buf, p)[0]
            if v == 0:
                break
            out.append(v)
            p += struct.calcsize(ptr_fmt)
        return out


def parse_objc(m):
    e = m.endian
    classes = {}
    for cls_addr in m.list_at("__DATA_CONST", m.classes_vaddr):
        # struct objc_class (64-bit): isa, super, cache, vtable, data(+ro bits)
        v = m.buf
        base = m.section_vmaddr("__DATA_CONST")
        p = base + cls_addr
        isa, sup, cache, vtable, data = struct.unpack_from(e + "QQQQQ", m.buf, p)
        rp = base + (data & ~0x7)
        class_ro = struct.unpack_from(e + "IIII", m.buf, rp)  # flags, instStart, instSize, (res)
        name_addr = class_ro[3]
        # proper layout on x86_64: flags, instanceStart, instanceSize, reserved,
        # ivarLayout, name, baseMethods, baseProtocols, ivars, weakIvarLayout, baseProperties
        (_flags, _is, _isz, _res, _ivl, name_addr, methods_addr,
         _protos, _ivars, _weak, _props) = struct.unpack_from(e + "IIIIIIIIIII", m.buf, rp)
        name = m.cstr(name_addr)
        sup_name = None
        if sup:
            srp = base + (struct.unpack_from(e + "Q", m.buf, base + sup + 32)[0] & ~0x7)
            sup_name = m.cstr(struct.unpack_from(e + "I", m.buf, srp + 24)[0])
        methods = []
        for lst in (methods_addr, 0):
            if not lst:
                continue
            mp = base + lst
            cnt = struct.unpack_from(e + "I", m.buf, mp + 24)[0]
            off = mp + 28
            for _ in range(min(cnt, 4000)):
                namep, typesp, imp = struct.unpack_from(e + "QQQ", m.buf, off)
                methods.append({"selector": m.cstr(namep), "types": m.cstr(typesp)})
                off += 24
        classes[name or hex(cls_addr)] = {
            "super": sup_name, "ro_addr": hex(cls_addr),
            "methods": methods,
        }
    return classes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("--out")
    ap.add_argument("--classes-only", action="store_true")
    a = ap.parse_args()
    m = MachO(a.binary)
    # __objc_classlist lives in __DATA_CONST (64-bit) or __DATA
    for sect in ("__DATA_CONST", "__DATA"):
        if sect in m.sections:
            m.classes_sect = sect
            break
    m.classes_vaddr = 0
    # find classlist address: it is the only __objc_* pointer array; locate by
    # scanning section headers is avoided - use LC_DATA_IN_CODE style trick:
    # instead scan __DATA_CONST for the first 8 bytes pointing to a plausible
    # objc_class is fragile; instead rely on dyld's __objc_classlist symbol.
    classes = scan_classlist(m)
    doc = {"schema": "mavlinos.objc-model/1", "binary": a.binary,
           "class_count": len(classes), "classes": classes}
    text = json.dumps(doc, indent=1, sort_keys=True)
    if a.out:
        open(a.out, "w").write(text)
        print(f"objc-model: {len(classes)} classes -> {a.out}")
    else:
        print(text[:4000])
    return 0


def scan_classlist(m):
    """Read __objc_classlist straight out of the section table."""
    for sect in ("__objc_classlist", "__objc_catlist"):
        pass
    if "__objc_classlist" not in m.sections:
        return {}
    foff, size, vaddr = m.sections["__objc_classlist"]
    classes = {}
    n = size // 8
    for i in range(n):
        cls_addr = struct.unpack_from(m.endian + "Q", m.buf, foff + i * 8)[0]
        if not cls_addr:
            continue
        info = read_class(m, cls_addr)
        if info:
            classes[info["name"]] = info
    return classes


def read_class(m, cls_addr):
    """Decode struct objc_class + its class_ro (x86_64 layout)."""
    e = m.endian
    p = m.va2off(cls_addr)
    if p is None:
        return None
    try:
        isa, sup, cache, vtable, data = struct.unpack_from(e + "QQQQQ", m.buf, p)
    except struct.error:
        return None
    rp = m.va2off(data & ~0x7)
    if rp is None:
        return None
    try:
        # 64-bit class_ro_t: 4x u32 header, then 7 pointers (ivarLayout, name,
        # baseMethods, baseProtocols, ivars, weakIvarLayout, baseProperties)
        _hdr = struct.unpack_from(e + "IIII", m.buf, rp)
        ivl, name_addr, methods_addr, protos, ivars, weak, props = struct.unpack_from(
            e + "7Q", m.buf, rp + 16)
    except struct.error:
        return None
    name = m.cstr(name_addr)
    if not name:
        return None
    sup_name = None
    if sup:
        sp = m.va2off(sup + 32)
        if sp is not None:
            try:
                sdata = struct.unpack_from(e + "Q", m.buf, sp)[0] & ~0x7
                srp = m.va2off(sdata)
                if srp is not None:
                    sup_name = m.cstr(struct.unpack_from(e + "I", m.buf, srp + 24)[0])
            except struct.error:
                pass
    methods = []
    if methods_addr:
        mp = m.va2off(methods_addr)
        if mp is not None:
            try:
                # method_list_t: entsize_and_flags u32, count u32, then entries
                cnt = struct.unpack_from(e + "I", m.buf, mp + 4)[0]
                off = mp + 8
                for _ in range(min(cnt, 5000)):
                    n, t, imp = struct.unpack_from(e + "QQQ", m.buf, off)
                    sel = m.cstr(n)
                    if sel:
                        # keep the IMP address: it is the entry into the code that
                        # actually implements the behaviour (drawing, layout,
                        # hit-testing) - the anchor for constant extraction
                        methods.append({"selector": sel, "types": m.cstr(t),
                                        "imp": hex(imp)})
                    off += 24
            except struct.error:
                pass
    ivars_out = []
    if ivars:
        ip = m.va2off(ivars)
        if ip is not None:
            try:
                cnt = struct.unpack_from(e + "I", m.buf, ip + 4)[0]
                off = ip + 8
                for _ in range(min(cnt, 300)):
                    off2 = struct.unpack_from(e + "I", m.buf, off)[0]
                    nam = m.cstr(off2)
                    if nam:
                        ivars_out.append({"name": nam,
                                          "type": m.cstr(struct.unpack_from(e + "I", m.buf, off + 4)[0])})
                    off += 32
            except struct.error:
                pass
    return {"name": name, "super": sup_name, "methods": methods, "ivars": ivars_out}


if __name__ == "__main__":
    sys.exit(main())