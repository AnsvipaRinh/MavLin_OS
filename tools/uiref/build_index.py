#!/usr/bin/env python3
"""Build/refresh docs/UI_REFERENCE/captures/index.json from a shots directory.

Usage: build_index.py <shots-dir> [--index <path>]

- md5/size/dimensions for every PNG in the shots dir
- keeps existing descriptions, flags new/changed/removed entries
"""
import argparse, hashlib, json, os, sys
from PIL import Image


def scan(shots):
    out = {}
    for fn in sorted(os.listdir(shots)):
        if not fn.endswith(".png"):
            continue
        p = os.path.join(shots, fn)
        md5 = hashlib.md5(open(p, "rb").read()).hexdigest()
        with Image.open(p) as im:
            w, h = im.size
        out[fn] = {"md5": md5, "size": os.path.getsize(p), "width": w, "height": h}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots")
    ap.add_argument("--index", default=os.path.join(os.path.dirname(__file__), "../../docs/UI_REFERENCE/captures/index.json"))
    a = ap.parse_args()
    index_path = os.path.abspath(a.index)
    old = {}
    if os.path.exists(index_path):
        old = json.load(open(index_path)).get("captures", {})
    fresh = scan(a.shots)
    merged = {}
    for fn, meta in fresh.items():
        if fn in old and old[fn].get("md5") == meta["md5"]:
            e = old[fn]
            e.update(meta)
            e.setdefault("description", "")
        else:
            e = dict(meta)
            e.setdefault("description", "")
            if fn in old:
                print(f"CHANGED: {fn} ({old[fn].get('md5')} -> {meta['md5']})")
        merged[fn] = e
    for fn in old:
        if fn not in fresh:
            print(f"REMOVED (kept? no): {fn}")
    doc = {"schema": "mavlinos.ui-reference-captures/1", "count": len(merged), "captures": merged}
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    json.dump(doc, open(index_path, "w"), indent=2, sort_keys=True)
    missing = [fn for fn, e in merged.items() if not e.get("description")]
    print(f"indexed {len(merged)} captures; {len(missing)} without description")
    return 0


if __name__ == "__main__":
    sys.exit(main())
