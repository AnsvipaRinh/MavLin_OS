#!/usr/bin/env python3
"""Render docs/UI_REFERENCE/catalog/*.md from docs/UI_REFERENCE/data/*.json.

Idempotent: run after every data change; the repo copy is generated output.
"""
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



if __name__ == "__main__":
    sys.exit(main())
