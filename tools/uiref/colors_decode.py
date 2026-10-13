#!/usr/bin/env python3
"""colors_decode.py - the authentic Mavericks palette, straight out of AppKit.

10.9 draws its skeuomorphic controls procedurally, and the colour ramps live in
dedicated Mach-O sections of AppKit:

    __color        solid colours
    __gray         grayscale ramp (window/toolbar surfaces, text)
    __mac_color    legacy "Mac OS" colour tables
    __color_alpha  translucent colours
    __gray_alpha / __fullcolor_alph / __mac_gray

Each entry is four 32-bit ARGB words. Decoding them gives us the exact greys and
tints AppKit mixes - the numbers our own theme must reproduce - without reading
a single screenshot.

Usage:
    colors_decode.py <AppKit-binary> --out docs/UI_REFERENCE/data/palette.json
                     [--per-section 60]
"""
import argparse, json, os, struct, sys

SECTIONS = ("__color", "__color_alpha", "__fullcolor_alph", "__gray",
            "__gray_alpha", "__mac_color", "__mac_gray")

ROLE_HINT = {
    "__color": "aqua.control.solid",
    "__color_alpha": "aqua.control.translucent",
    "__fullcolor_alph": "aqua.fullcolor",
    "__gray": "aqua.gray.ramp",
    "__gray_alpha": "aqua.gray.translucent",
    "__mac_color": "legacy.macos.colour",
    "__mac_gray": "legacy.macos.gray",
}


def sections(path):
    e = "<"
    buf = open(path, "rb").read()
    magic = struct.unpack_from("<I", buf, 0)[0]
    if magic in (0xCAFEBABE, 0xBEBAFECA):
        n = struct.unpack_from(">I", buf, 4)[0]
        for i in range(n):
            cpu, sub, o = struct.unpack_from(">III", buf, 8 + i * 20)
            if cpu in (0x01000007, 7):
                return sections_from(buf[o:])
        return {}
    return sections_from(buf)


def sections_from(buf):
    out = {}
    ncmds = struct.unpack_from("<I", buf, 16)[0]
    off = 32
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", buf, off)
        if cmd == 0x19:  # LC_SEGMENT_64
            nsects = struct.unpack_from("<I", buf, off + 64)[0]
            so = off + 72
            for _s in range(nsects):
                sname = buf[so:so + 16].split(b"\0")[0].decode()
                saddr, ssize = struct.unpack_from("<QQ", buf, so + 32)
                foff = struct.unpack_from("<I", buf, so + 48)[0]
                out[sname] = (foff, ssize)
                so += 80
        off += cmdsize
    return out, buf


def decode_section(buf, foff, size, header_records=1):
    colors = []
    for i in range(header_records, size // 16):
        # records are four 32-bit words whose bytes are R,G,B,A in memory order
        r, g, b, al = struct.unpack_from("<4B", buf, foff + i * 16)
        alpha = al
        red, green, blue = r, g, b
        if alpha == 0:
            continue
        colors.append((red, green, blue, alpha))
    return colors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-section", type=int, default=60)
    a = ap.parse_args()

    secs, buf = sections(a.binary)
    facts = []
    for name in SECTIONS:
        if name not in secs:
            continue
        foff, size = secs[name]
        cols = decode_section(buf, foff, size)
        hist = {}
        for r, g, b, al in cols:
            hist[(r, g, b, al)] = hist.get((r, g, b, al), 0) + 1
        for (r, g, b, al), n in sorted(hist.items(), key=lambda kv: -kv[1])[:a.per_section]:
            facts.append({
                "id": f"appkit.{name.strip('_')}.{r:02x}{g:02x}{b:02x}.a{al:02x}",
                "role": ROLE_HINT[name],
                "hex": "#%02x%02x%02x" % (r, g, b),
                "alpha": round(al / 255.0, 3),
                "value": n,
                "unit": "px",
                "kind": "measured",
                "confidence": "high",
                "evidence": "src:appkit",
                "notes": f"occurrences in the {name} ramp ({a.binary})",
            })
        print(f"{name}: {len(hist)} distinct colours")
    import hashlib
    digest = hashlib.sha256(open(a.binary, "rb").read()).hexdigest()
    doc = {"schema": "mavlinos.ui-reference/1", "facts": facts,
           "sources": {"appkit": {"kind": "mach-o",
                                       "path": os.path.basename(a.binary),
                                       "section": "colour tables",
                                       "sha256": digest}}}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(doc, open(a.out, "w"), indent=1, sort_keys=True)
    print(f"palette: {len(facts)} colours -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())