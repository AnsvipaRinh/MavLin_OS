#!/usr/bin/env python3
"""Propose a palette from a capture: dominant colors via quantization.

Usage: extract_palette.py <capture.png> [--colors 12] [--json]

Output is a *proposal*; curated values are written by hand into data/palette.json,
keeping the semantic role names (window background, toolbar, sidebar, selection...).
"""
import argparse, json, os, sys
from PIL import Image

SYSROOT = os.path.dirname(__file__)
DATA = os.path.join(SYSROOT, "../../docs/UI_REFERENCE/data")


def dominant(path, n):
    im = Image.open(path).convert("RGB")
    q = im.quantize(colors=n, method=Image.Quantize.FASTOCTREE)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    out = []
    for cnt, idx in counts:
        r, g, b = pal[idx * 3:idx * 3 + 3]
        out.append({"count": cnt, "hex": "#%02x%02x%02x" % (r, g, b), "rgb": [r, g, b]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--colors", type=int, default=12)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = dominant(a.capture, a.colors)
    if a.json:
        print(json.dumps(rows, indent=2))
        return 0
    print("#count   hex      rgb")
    for r in rows:
        print(f"{r['count']:>8}  {r['hex']}  {r['rgb']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
