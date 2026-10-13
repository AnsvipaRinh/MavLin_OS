#!/usr/bin/env python3
"""surfaces.py - build the surface inventory and the assembly rules from real nibs.

A .nib name *is* a surface name: "OpenPanel", "FloatingStatusBar",
"BrowserToolbar", "QuotaPanel", "SheetView" ... Apple's own file naming tells us
exactly which windows, sheets, panels, toolbars and popovers each application is
supposed to have. Combined with the controls each nib instantiates, this becomes
the rule set an implementer follows when wrapping any Linux backend:

    surface "OpenPanel" of Finder needs
      controls: NSTableView, NSPopUpButton, NSButton, NSBrowserView...
      geometry: window frame + column frames (from nib geometry)

Usage:
    surfaces.py <sys-tree> --geometry docs/UI_REFERENCE/data/nib_geometry.json \
               --out docs/UI_REFERENCE/data/surfaces.json
"""
import argparse, json, os, re, sys
from collections import defaultdict

# nib names that are pure plumbing, not user-visible surfaces
NOISE = re.compile(r"^(MainMenu|WindowController|Rez|Agent|MenuItem)$")


def app_of(path):
    for part in path.split(os.sep):
        if part.endswith((".app", ".prefPane", ".framework", ".bundle", ".xpc")):
            return part
    return None


def classify(nib_name):
    n = nib_name
    for kind, pat in (("open_panel", r"Open|Picker"),
                      ("save_panel", r"Save|Export"),
                      ("sheet", r"Sheet|Alert|Confirm|Progress|SaveChanges"),
                      ("toolbar", r"Toolbar|StatusBar|Bar"),
                      ("panel", r"Panel|Prefs|Preference|Settings|Inspector|Info"),
                      ("menu", r"Menu|MainMenu"),
                      ("window", r"Window|Browser|Outline|Column"),
                      ("popover", r"Popover|PopUp|Popup"),
                      ("cell", r"Cell|Row|Item$"),
                      ("view", r"View|Controller|Table|Outline|Scroll|Field")):
        if re.search(pat, n, re.I):
            return kind
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("--geometry", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    geo = json.load(open(a.geometry))
    by_path = {n["path"]: n for n in geo.get("nibs", [])}

    surfaces = defaultdict(lambda: {"nib": None, "path": None, "windows": [],
                                    "views": [], "menus": [], "kinds": set(),
                                    "classes": defaultdict(int)})
    for rel, nib in by_path.items():
        app = app_of(rel) or "System"
        name = os.path.basename(rel).replace(".nib", "")
        if NOISE.match(name):
            continue
        key = f"{app}/{name}"
        s = surfaces[key]
        s["path"] = rel
        s["kinds"].add(classify(name))
        s["windows"] = nib.get("windows", [])
        s.setdefault("menus", []).extend(nib.get("menus", []))
        for v in nib.get("views", []):
            cls = v.get("class")
            if cls:
                s["classes"][cls] += 1

    out = []
    for key, s in sorted(surfaces.items()):
        app, name = key.split("/", 1)
        controls = [{"class": c, "count": n} for c, n in
                    sorted(s["classes"].items(), key=lambda kv: -kv[1])[:14]]
        win = s["windows"][0] if s["windows"] else {}
        menus = []
        for it in s["menus"]:
            if it.get("title") and not it.get("separator"):
                menus.append({"title": it["title"],
                              "key_equivalent": it.get("key_equivalent") or None,
                              "action": it.get("action") or None,
                              "disabled": bool(it.get("disabled")),
                              "submenu": (it.get("submenu") or [])[:0] or None})
        out.append({
            "id": f"surface.{app}.{name}",
            "menu_items": menus[:120],
            "application": app,
            "surface": name,
            "kind": sorted(s["kinds"])[0] if s["kinds"] else "other",
            "evidence": {"nib": s["path"], "nib_geometry": bool(s["windows"])},
            "window": {"rect": win.get("rect"), "title": win.get("title"),
                       "style_mask": win.get("style_mask")} if win else None,
            "required_controls": controls,
        })

    doc = {"schema": "mavlinos.ui-surfaces/1",
           "description": "Surface inventory derived from the real 10.9 nib names and "
                          "their instantiated controls. This is the assembly rule set: "
                          "wrapping a Linux backend means providing exactly these pieces.",
           "count": len(out), "surfaces": out}
    json.dump(doc, open(a.out, "w"), indent=1, sort_keys=True)
    kinds = defaultdict(int)
    for s in out:
        kinds[s["kind"]] += 1
    print(f"surfaces: {len(out)} ({dict(sorted(kinds.items()))}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())