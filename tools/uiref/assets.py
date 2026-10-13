#!/usr/bin/env python3
"""Decode the pixel geometry of every image asset in the real OS X 10.9 tree.

The skin of Mavericks is fixed by the sizes its own artwork was authored at:
toolbar icons, sidebar art, status bar strips, window buttons and the icon
grid the Finder shows. This tool reads only the *headers* of PNG, JPEG, TIFF,
PDF and icns containers, so the numbers are Apple's own, and never copies the
artwork itself.

Output: data/assets.json - per asset its container format, pixel size, colour
depth, owning bundle and role guess, plus aggregate size histograms (the icon
grid in particular, which tells us exactly which sizes the desktop must ship).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import struct
import sys

EXTS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".tiff": "tiff",
        ".tif": "tiff", ".pdf": "pdf", ".icns": "icns"}
ICNS_TYPES = {b"icp4": 16, b"icp5": 32, b"icp6": 64, b"ic07": 128, b"ic08": 256,
              b"ic09": 512, b"ic10": 1024, b"ic11": 32, b"ic12": 64, b"ic13": 256,
              b"ic04": 16, b"ic05": 32, b"ic14": 512, b"ic04s": 16, b"ic05s": 32,
              b"icsb": 18, b"icsB": 36, b"sb24": 24, b"SB24": 24}
ROLE_HINTS = (("toolbar", "toolbar"), ("sidebar", "sidebar"),
              ("statusbar", "statusbar"), ("status", "statusbar"),
              ("scrollbar", "scrollbar"), ("slider", "control"),
              ("checkbox", "control"), ("radio", "control"),
              ("button", "control"), ("bezel", "control"),
              ("progress", "control"), ("stepper", "control"),
              ("resiz", "control"), ("grow", "control"),
              ("disclosure", "control"), ("segment", "control"),
              ("alert", "dialog"), ("sheet", "dialog"), ("panel", "dialog"),
              ("@2x", "retina"), ("small", "small"), ("menu", "menu"))


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    length, ctype = struct.unpack(">I4s", data[8:16])
    if ctype != b"IHDR":
        return None
    w, h, depth, color = struct.unpack(">IIBB", data[16:26])
    return {"w": w, "h": h, "bit_depth": depth, "color_type": color,
            "has_alpha": color in (4, 6)}


def jpeg_size(data):
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return {"w": w, "h": h}
        i += 2 + seg_len
    return None


def tiff_size(data):
    le = data[:2] == b"II"
    end = "<" if le else ">"
    ifd = struct.unpack(end + "I", data[4:8])[0]
    if ifd + 2 > len(data):
        return None
    count = struct.unpack(end + "H", data[ifd:ifd + 2])[0]
    tags = {}
    for i in range(count):
        off = ifd + 2 + i * 12
        tag, typ = struct.unpack(end + "HH", data[off:off + 4])
        raw = data[off + 8:off + 12]
        if typ == 3:
            # TIFF SHORT lives in the first half of the value field for
            # big-endian files and in the second half for little-endian ones
            sub = raw[0:2] if end == ">" else raw[2:4]
            val = struct.unpack(end + "H", sub)[0] if len(sub) == 2 else 0
        else:
            val = struct.unpack(end + "I", raw)[0]
        tags[tag] = val
    if 256 in tags and 257 in tags:
        return {"w": tags[256], "h": tags[257]}
    return None


def pdf_size(data):
    m = re.search(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)", data[:4096] or data)
    if not m:
        return None
    x0, y0, x1, y1 = (float(g) for g in m.groups())
    return {"w": round(abs(x1 - x0)), "h": round(abs(y1 - y0)), "unit": "pt"}


def icns_sizes(data):
    if data[:4] != b"icns":
        return []
    n = struct.unpack(">I", data[4:8])[0]
    out, off = [], 8
    while off + 8 <= min(n, len(data)):
        typ = data[off:off + 4]
        size = struct.unpack(">I", data[off + 4:off + 8])[0]
        if typ in ICNS_TYPES:
            out.append({"w": ICNS_TYPES[typ], "h": ICNS_TYPES[typ], "icns_type": typ.decode()})
        off += size or 8
    return out


def role_of(name):
    low = name.lower()
    for needle, role in ROLE_HINTS:
        if needle in low:
            return role
    return ""


def scan(root, min_side=0):
    assets = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in ("private", "var", "cache", "Caches")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            fmt = EXTS.get(ext)
            if not fmt:
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "rb") as fh:
                    head = fh.read(65536)
            except OSError:
                continue
            rel = os.path.relpath(path, root)
            bundle = rel.split("/Contents/")[0].split("/")[0]
            base = os.path.splitext(fn)[0]
            common = {"name": base, "path": rel, "format": fmt, "bundle": bundle,
                      "role": role_of(base)}
            if fmt == "png":
                info = png_size(head)
            elif fmt == "jpeg":
                info = jpeg_size(head)
            elif fmt == "tiff":
                info = tiff_size(head)
            elif fmt == "pdf":
                with open(path, "rb") as fh:
                    info = pdf_size(fh.read(8192))
            else:
                info = None
            if info:
                if min_side and min(info.get("w", 0), info.get("h", 0)) < min_side:
                    continue
                assets.append(dict(common, **info))
            if fmt == "icns":
                for info in icns_sizes(head):
                    assets.append(dict(common, **info))
    return assets


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="extracted OS X system tree")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-side", type=int, default=0)
    args = ap.parse_args()

    assets = scan(args.root, args.min_side)

    raster = [a for a in assets if a["format"] in ("png", "jpeg", "tiff")]
    size_hist = collections.Counter(
        a["w"] for a in raster if a.get("w") == a.get("h"))
    icns_hist = collections.Counter()
    for a in assets:
        if a["format"] == "icns" and a.get("w") == a.get("h"):
            icns_hist[a["w"]] += 1
    role_hist = collections.Counter(a["role"] for a in assets if a["role"])

    out = {
        "count": len(assets),
        "summary": {
            "raster": len(raster),
            "vector_pdf": sum(1 for a in assets if a["format"] == "pdf"),
            "icns": sum(1 for a in assets if a["format"] == "icns"),
            "square_px_sizes": dict(sorted(size_hist.items())),
            "icns_grid_sizes": dict(sorted(icns_hist.items())),
            "roles": dict(role_hist.most_common()),
        },
        "assets": assets,
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"assets: {out['count']} ({out['summary']['raster']} raster, "
          f"{out['summary']['vector_pdf']} pdf, {out['summary']['icns']} icns) "
          f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
