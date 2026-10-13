#!/usr/bin/env python3
"""Resolve the Mavericks theme from the nibs themselves: colours and typography.

Each nib references Apple's system colours by catalog name and stores the
components next to them, so the catalog can state the real values of
controlColor, windowBackgroundColor, gridColor and friends - and the real font
of every control that ships with the system.

Output: data/theme.json with
  * system_colors - name -> {hex, rgb, space, uses, apps}
  * fonts        - family/size/flags -> use count, plus per-family size histogram
  * summary      - the numbers an implementer needs first
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

TOP_FONTS = 40
TOP_COLORS = 40


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geometry", help="nib_geometry.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.geometry) as fh:
        data = json.load(fh)

    colors = collections.defaultdict(lambda: {
        "hex": collections.Counter(), "space": collections.Counter(),
        "alpha": collections.Counter(), "apps": collections.Counter(), "uses": 0})
    fonts = collections.Counter()
    font_families = collections.defaultdict(collections.Counter)
    font_flags = collections.Counter()

    for nib in data.get("nibs", []):
        app = nib.get("app") or os.path.basename(nib.get("path", "?"))
        for c in nib.get("colors", []):
            key = c.get("name") or (c.get("catalog") + " " if c.get("catalog") else "") or c.get("hex")
            if not key:
                continue
            rec = colors[key]
            rec["uses"] += 1
            rec["apps"][app] += 1
            if c.get("hex"):
                rec["hex"][c["hex"]] += 1
            if c.get("space") is not None:
                rec["space"][c["space"]] += 1
            if c.get("alpha") is not None:
                rec["alpha"][c["alpha"]] += 1
        for f in nib.get("fonts", []):
            if not f.get("family"):
                continue
            fonts[(f["family"], f.get("size"), f.get("flags"))] += 1
            if f.get("size") is not None:
                font_families[f["family"]][f["size"]] += 1
            if f.get("flags") is not None:
                font_flags[f["flags"]] += 1

    out_colors = []
    ranked = sorted(colors.items(), key=lambda kv: -kv[1]["uses"])[:TOP_COLORS]
    for name, rec in ranked:
        out_colors.append({
            "id": f"color.{name.replace(' ', '-')}",
            "name": name,
            "hex": rec["hex"].most_common(1)[0][0] if rec["hex"] else None,
            "variants": rec["hex"].most_common(4),
            "space": rec["space"].most_common(1)[0][0] if rec["space"] else None,
            "alpha": rec["alpha"].most_common(1)[0][0] if rec["alpha"] else None,
            "uses": rec["uses"],
            "apps": [a for a, _ in rec["apps"].most_common(6)],
        })

    out_fonts = []
    for (family, size, flags), count in fonts.most_common(TOP_FONTS):
        out_fonts.append({
            "id": f"font.{family}-{size}-{flags}",
            "family": family,
            "size": size,
            "flags": flags,
            "uses": count,
        })

    sizes = {f: dict(sorted(c.items())) for f, c in
             sorted(font_families.items(), key=lambda kv: -sum(kv[1].values()))[:12]}

    out = {
        "system_colors": out_colors,
        "fonts": out_fonts,
        "font_sizes_by_family": sizes,
        "summary": {
            "color_names": len(colors),
            "font_variants": len(fonts),
            "distinct_sizes": sorted({f[1] for f in fonts if f[1] is not None}),
            "style_flags": [[f, c] for f, c in font_flags.most_common(10)],
        },
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"theme: {len(out_colors)} system colours, {len(out_fonts)} font variants "
          f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
