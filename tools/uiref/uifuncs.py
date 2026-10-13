#!/usr/bin/env python3
"""uifuncs.py - read the drawing code of a control and harvest its constants.

A .nib tells us the layout; it does not tell us the colour ramp, the corner
radius or the hit slop a control draws. That lives in the implementation, and
the implementation is reachable: every ObjC method list carries its IMP address,
so for a given `+[Class selector:]` we can

  * find the function body (entry -> next method entry),
  * list the selectors it sends (what the control actually talks to),
  * list the float/double constants it embeds (ramp stops, radii, insets),
  * list the addresses inside AppKit's colour sections it references.

This is how the skin gets its numbers without a single screenshot.

Usage:
    uifuncs.py --dump docs/UI_REFERENCE/data/objc-appkit.json \
               --binary /path/to/AppKit \
               --class NSButtonCell --selector "drawRect:" [--limit 40]
"""
import argparse, json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import machobjc  # noqa: E402


def functions(m):
    """method imp -> (class, selector) from the class dump"""
    return m


def method_body(m, imp, all_imps):
    """Byte range of the function starting at `imp` (bounded by the next method)."""
    nxt = [a for a in all_imps if a > imp]
    end = min(nxt) if nxt else imp + 4096
    # cap runaway ranges: real bodies are small
    end = min(end, imp + 8192)
    p = m.va2off(imp)
    q = m.va2off(end - 1)
    if p is None or q is None or q <= p:
        return b""
    return m.buf[p:q + 1]


def floats(code, limit=24):
    """Plausible float/double constants (floats in .rodata-style immediates)."""
    out = []
    for i in range(0, max(len(code) - 4, 0)):
        v, = struct.unpack_from("<f", code, i)
        a = abs(v)
        if 0.001 <= a <= 4096.0:
            # ignore noise: values that look like ASCII or tiny denormals
            if abs(v) > 0.02 and not (0.2 < a < 0.25):
                out.append((i, round(v, 5)))
    # de-duplicate by value, keep first offset
    seen, uniq = set(), []
    for off, v in out:
        key = round(v, 3)
        if key in seen:
            continue
        seen.add(key)
        uniq.append({"offset": hex(off), "value": v})
        if len(uniq) >= limit:
            break
    return uniq


def ints(code, limit=24):
    """Small immediates that are almost always layout constants."""
    out, seen = [], set()
    for i in range(0, max(len(code) - 4, 0), 1):
        v, = struct.unpack_from("<i", code, i)
        if 0 < v <= 400 and v not in seen and code[i - 1:i] not in (b"\xc7",):
            seen.add(v)
            out.append({"offset": hex(i), "value": v})
        if len(out) >= limit:
            break
    return out


def color_refs(m, code, base_va):
    """Absolute immediates that point into AppKit's colour sections."""
    refs = []
    for name in ("__color", "__color_alpha", "__fullcolor_alph", "__gray",
                 "__gray_alpha", "__mac_color", "__mac_gray"):
        s = m.sections.get(name)
        if not s:
            continue
        _foff, size, vaddr = s
        for i in range(0, len(code) - 8):
            v, = struct.unpack_from("<Q", code, i)
            if vaddr <= v < vaddr + size:
                refs.append({"section": name, "target": hex(v - vaddr)})
        # 32-bit immediates are used more often than 64-bit
        for i in range(0, len(code) - 4):
            v, = struct.unpack_from("<I", code, i)
            if vaddr <= v < vaddr + size:
                refs.append({"section": name, "target": hex(v - vaddr)})
    uniq, seen = [], set()
    for r in refs:
        k = (r["section"], r["target"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq[:32]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True, help="objc model json (objc-appkit.json)")
    ap.add_argument("--binary", required=True)
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--selector", default=None)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-classes", type=int, default=12,
                    help="how many implementors of the selector to analyse")
    ap.add_argument("--out")
    a = ap.parse_args()

    doc = json.load(open(a.dump))
    m = machobjc.MachO(a.binary)
    all_imps = []
    by_class = {}
    for name, c in doc.get("classes", {}).items():
        for meth in c.get("methods", []):
            imp = meth.get("imp")
            if not imp:
                continue
            addr = int(imp, 16)
            all_imps.append(addr)
            by_class.setdefault(name, []).append((meth["selector"], addr))

    results = {}
    if a.selector:
        # a selector is often implemented in a private subclass, so search every
        # class whose method list declares it
        pairs = []
        for cls, meths in by_class.items():
            for s, imp in meths:
                if s == a.selector:
                    pairs.append((cls, s, imp))
        pairs = pairs[:a.max_classes]
    else:
        pairs = [(a.cls, s, imp) for s, imp in by_class.get(a.cls, [])][:a.max_classes]
    for cls, sel, imp in pairs:
        if True:
            body = method_body(m, imp, all_imps)
            if not body:
                continue
            results.setdefault(f"{cls} {s}", {
                "imp": hex(imp), "bytes": len(body),
                "floats": floats(body, a.limit),
                "ints": ints(body, a.limit),
                "colour_refs": color_refs(m, body, imp),
            })
    text = json.dumps({"schema": "mavlinos.ui-functions/1",
                       "binary": a.binary, "class": a.cls,
                       "functions": results}, indent=1, sort_keys=True)
    if a.out:
        json.dump(json.loads(text), open(a.out, "w"), indent=1, sort_keys=True)
        print(f"uifuncs: {len(results)} functions -> {a.out}")
    else:
        print(text[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())