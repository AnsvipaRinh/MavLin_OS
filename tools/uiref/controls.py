#!/usr/bin/env python3
"""Aggregate nib cell objects into the control appearance protocol.

Every NSControlCell in a compiled Mavericks nib stores the drawing parameters
that decide how the widget looks: bezel/flags bitfields, image and alternate
image, title, key equivalent, text and background colour. This tool folds the
14375 decoded cells of the real system tree into per-class distributions, so an
implementer can reproduce the widgets without ever seeing a screenshot.

Pure fact layer: values are reported exactly as they appear in the archives,
with the occurrence count, and no name is invented for an unknown bit.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

FLAG_KEYS = ("NSButtonFlags", "NSButtonFlags2", "NSCellFlags", "NSCellFlags2",
             "NSScale", "NSAlign", "NSStyle", "NSBorderStyle", "NSTag",
             "NSBackgroundColor", "NSTextColor", "NSDrawsBackground")
TOP_N = 8


def collect(nibs):
    per_class = collections.defaultdict(lambda: {
        "instances": 0,
        "flags": collections.defaultdict(collections.Counter),
        "titles": collections.Counter(),
        "alt_titles": collections.Counter(),
        "key_equivalents": collections.Counter(),
        "images": collections.Counter(),
        "apps": collections.Counter(),
    })
    for nib in nibs:
        app = nib.get("app") or os.path.basename(nib.get("path", "?"))
        for cell in nib.get("controls", []):
            cls = cell.get("class")
            if not cls:
                continue
            rec = per_class[cls]
            rec["instances"] += 1
            rec["apps"][app] += 1
            for key, val in (cell.get("attrs") or {}).items():
                if key in FLAG_KEYS:
                    rec["flags"][key][val] += 1
            for field, sink in (("title", "titles"), ("alt_title", "alt_titles"),
                                ("key_equiv", "key_equivalents"), ("image", "images")):
                if cell.get(field):
                    rec[sink][cell[field]] += 1
    return per_class


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geometry", help="nib_geometry.json produced by nib_geometry.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-instances", type=int, default=1)
    args = ap.parse_args()

    with open(args.geometry) as fh:
        data = json.load(fh)
    per_class = collect(data.get("nibs", []))

    classes = []
    total = 0
    for name, rec in sorted(per_class.items()):
        if rec["instances"] < args.min_instances:
            continue
        total += rec["instances"]
        classes.append({
            "id": f"control.{name}",
            "class": name,
            "instances": rec["instances"],
            "apps": [a for a, _ in rec["apps"].most_common(8)],
            "flags": {k: [[int(v), c] for v, c in counter.most_common(TOP_N)]
                      for k, counter in sorted(rec["flags"].items())},
            "titles": [t for t, _ in rec["titles"].most_common(10)],
            "alt_titles": [t for t, _ in rec["alt_titles"].most_common(5)],
            "key_equivalents": [t for t, _ in rec["key_equivalents"].most_common(10)],
            "images": [t for t, _ in rec["images"].most_common(10)],
        })

    out = {"count": len(classes), "cells": total, "classes": classes}
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"controls: {len(classes)} cell classes, {total} instances -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
