#!/usr/bin/env python3
"""Window geometry inventory from the real Mavericks nib templates.

Every NSWindowTemplate in a compiled nib records the frame the designer used:
the rect, the content rect, minimum/maximum sizes and the style mask. Mavericks
dialogs, sheets and utility panels are shipped that way, so the catalog can
state the real default sizes of windows instead of guessing them.

Style masks are reported as raw integers and as frequency counts of the masks
actually used. Bit names are *not* invented here: only masks that AppKit
itself documents are annotated, everything else stays numeric.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys

# Only the bits that are unambiguous in the public AppKit headers.
KNOWN_BITS = {
    1: "titled",
    2: "closable",
    4: "miniaturizable",
    8: "resizable",
}


def decode_mask(mask):
    return [name for bit, name in KNOWN_BITS.items() if mask & bit]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geometry", help="nib_geometry.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.geometry) as fh:
        data = json.load(fh)

    windows = []
    mask_hist = collections.Counter()
    size_hist = collections.Counter()
    for nib in data.get("nibs", []):
        for w in nib.get("windows", []):
            rect = w.get("rect") or {}
            content = w.get("content_rect") or {}
            mask = w.get("style_mask")
            rec = {
                "nib": nib["path"],
                "class": w.get("class"),
                "title": w.get("title") or "",
                "x": rect.get("x"), "y": rect.get("y"),
                "w": rect.get("w"), "h": rect.get("h"),
                "content_w": content.get("w"), "content_h": content.get("h"),
                "min_w": (w.get("min_size") or {}).get("w"),
                "min_h": (w.get("min_size") or {}).get("h"),
                "style_mask": mask,
                "style_bits": decode_mask(mask) if isinstance(mask, int) else [],
            }
            chrome_h = None
            if rec["w"] and rec["h"] and content.get("h"):
                chrome_h = round(rec["h"] - content["h"], 1)
            rec["chrome_h"] = chrome_h
            windows.append(rec)
            if isinstance(mask, int):
                mask_hist[mask] += 1
            if rec["w"] and rec["h"]:
                size_hist[(int(rec["w"]), int(rec["h"]))] += 1

    chrome_hist = collections.Counter(
        w["chrome_h"] for w in windows if w["chrome_h"] is not None
        and 0 < w["chrome_h"] <= 200)

    out = {
        "count": len(windows),
        "summary": {
            "style_masks": [[m, c, decode_mask(m)] for m, c in mask_hist.most_common(20)],
            "sizes": [[w, h, c] for (w, h), c in size_hist.most_common(30)],
            "chrome_heights": [[h, c] for h, c in chrome_hist.most_common(15)],
        },
        "windows": windows,
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"windows: {len(windows)} templates -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
