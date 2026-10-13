#!/usr/bin/env python3
"""Render docs/UI_REFERENCE/catalog/*.md from docs/UI_REFERENCE/data/*.json.

Idempotent: run after every data change; the repo copy is generated output.
"""
import collections
import json, os, sys

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "../../docs/UI_REFERENCE/data")
CAT = os.path.join(HERE, "../../docs/UI_REFERENCE/catalog")


def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return {}
    return json.load(open(p))


def table(facts, cols=("id", "value", "unit", "kind", "confidence", "evidence", "notes")):
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = []
    for f in facts:
        vals = []
        for c in cols:
            v = f.get(c, "")
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            vals.append(str(v if v != "" else "-"))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([head, sep] + rows)


def render_palette(d):
    f = d.get("facts", [])
    by_role = {}
    for e in f:
        by_role.setdefault(e.get("role", "other"), []).append(e)
    lines = ["# Palette (generated)", ""]
    lines.append("All values sampled @1x from the captures named in `evidence`. Roles are semantic: use the role, not the pixel.",
                 )
    lines.append("")
    for role, items in sorted(by_role.items()):
        lines.append(f"## {role}")
        lines.append("")
        lines.append(table(items, ("id", "hex", "alpha", "surface", "evidence", "confidence", "notes")))
        lines.append("")
    return "\n".join(lines)


def render_generic(d, title, note=""):
    f = d.get("facts", [])
    by_group = {}
    for e in f:
        by_group.setdefault(e.get("group", "other"), []).append(e)
    lines = [f"# {title} (generated)", ""]
    if note:
        lines += [note, ""]
    lines.append(table(f, ("id", "group", "value", "unit", "kind", "confidence", "evidence", "notes")))
    lines.append("")
    for g, items in sorted(by_group.items()):
        lines.append(f"## {g}")
        lines.append("")
        lines.append(table(items, ("id", "value", "unit", "kind", "confidence", "evidence", "deriv", "notes")))
        lines.append("")
    return "\n".join(lines)


def main():
    os.makedirs(CAT, exist_ok=True)
    out = {
        "palette.md": render_palette(load("palette.json")),
        "controls.md": render_controls(load("controls.json")),
        "assets.md": render_assets(load("assets.json")),
        "windows.md": render_windows(load("windows.json")),
        "metrics.md": render_generic(load("metrics.json"), "Metrics",
                                     "@1x pixel/point values. `derived` facts show their formula in `deriv`."),
        "typography.md": render_generic(load("typography.json"), "Typography",
                                        "System font of the guest is Lucida Grande (licensed, NOT redistributed). "
                                        "The substitution table maps each role to the MavLinOS open font choice."),
        "behaviors.md": render_generic(load("behaviors.json"), "Behaviors",
                                       "Interaction rules: keyboard, focus, animation timing, window behaviour. "
                                       "timings marked `literature` are documented macOS behaviour, not measured in emulation."),
        "patterns.md": render_generic(load("patterns.json"), "Patterns",
                                      "Composite widget/panel anatomy (cross-references metrics.json)."),
    }
    for name, text in out.items():
        p = os.path.join(CAT, name)
        with open(p, "w") as fh:
            fh.write(text.rstrip() + "\n")
        print("wrote", os.path.relpath(p, HERE))
    return 0


def render_assets(data):
    """Pixel geometry of Apple's own artwork: icon grid, chrome art, retina pairs."""
    s = data["summary"]
    out = ["# Asset geometry (pixel sizes decoded from the real 10.9 artwork)", "",
           f"Assets inspected: **{data['count']}** "
           f"({s['raster']} raster, {s['vector_pdf']} PDF, {s['icns']} icns).",
           "Only container headers were read; no artwork is stored or copied.", "",
           "## Icon grid (from icns headers)", "",
           "| px | icons |", "|---|---|"]
    for px, n in sorted((int(k), v) for k, v in s["icns_grid_sizes"].items()):
        out.append(f"| {px} | {n} |")
    out += ["", "These are the sizes the Finder icon views and the Dock must ship.",
            "", "## Roles", "", "| role | assets |", "|---|---|"]
    for role, n in list(s["roles"].items()):
        out.append(f"| {role} | {n} |")
    out += ["", "## Window chrome and toolbar artwork", "",
            "| asset | bundle | px |", "|---|---|---|"]
    chrome = [a for a in data["assets"]
              if a.get("role") in ("toolbar", "sidebar", "statusbar", "scrollbar", "control")
              and a["format"] in ("png", "tiff", "jpeg", "pdf")
              and (a.get("w") or 0) >= 16 and "@2x" not in a["name"]]
    seen = set()
    for a in sorted(chrome, key=lambda x: (-(x.get("w") or 0), x["name"]))[:60]:
        key = (a["name"], a["w"], a["h"])
        if key in seen:
            continue
        seen.add(key)
        unit = "pt" if a["format"] == "pdf" else "px"
        out.append(f"| {a['name']} | {a['bundle']} | {a['w']}×{a['h']} {unit} |")
    out.append("")
    return "\n".join(out)


def render_controls(data):
    """Control appearance protocol: cell classes, flag bitfields, key equivalents."""
    out = ["# Control appearance protocol (decoded from compiled nib cell objects)", "",
           f"Cells decoded from the real OS X 10.9 system tree: **{data['cells']}** "
           f"instances across **{data['count']}** NS*Cell classes.", "",
           "Flag values are reported exactly as stored in the archives. No bit name is",
           "invented here: implementers must map a bitfield to a bezel appearance only",
           "after verifying it against AppKit itself, then record the mapping here.", ""]
    for c in sorted(data["classes"], key=lambda x: -x["instances"]):
        out.append(f"## {c['class']} — {c['instances']} instances")
        out.append(f"* apps: {', '.join(c['apps'][:6])}")
        for key, vals in sorted(c.get("flags", {}).items()):
            pretty = ", ".join(f"`{v}`x{n}" for v, n in vals[:6])
            out.append(f"* {key}: {pretty}")
        if c.get("titles"):
            out.append(f"* titles: {', '.join(repr(t) for t in c['titles'][:8])}")
        if c.get("key_equivalents"):
            out.append(f"* key equivalents: "
                       f"{', '.join(repr(k) for k in c['key_equivalents'][:8])}")
        out.append("")
    return "\n".join(out)


def render_windows(data):
    """Window geometry as the designers shipped it: rects, masks, content sizes."""
    s = data["summary"]
    out = ["# Window geometry from real nib templates", "",
           f"NSWindowTemplate records decoded: **{data['count']}**.", "",
           "## Style masks in use", "",
           "| mask | count | documented bits |", "|---|---|---|"]
    for m, c, bits in s["style_masks"]:
        out.append(f"| {m} | {c} | {', '.join(bits) or '(undocumented bits only)'} |")
    out += ["", "## Most frequent window sizes", "", "| w | h | count |", "|---|---|---|"]
    for w, h, c in s["sizes"]:
        out.append(f"| {w} | {h} | {c} |")
    if s["chrome_heights"]:
        out += ["", "## Titlebar height implied by rect vs content rect", "",
                "| delta | count |", "|---|---|"]
        for h, c in s["chrome_heights"]:
            out.append(f"| {h} | {c} |")
    out += ["", "## Template classes", "", "| class | count |", "|---|---|"]
    classes = collections.Counter(w["class"] for w in data["windows"] if w.get("class"))
    for cls, c in classes.most_common(10):
        out.append(f"| {cls} | {c} |")
    out.append("")
    return "\n".join(out)



if __name__ == "__main__":
    sys.exit(main())
