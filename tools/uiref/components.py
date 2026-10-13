#!/usr/bin/env python3
"""components.py - assemble the Mavericks component library from extracted truth.

This is the artifact an implementer actually uses: for every UI component we
ship as a "prefabricated skin+bone" piece, it merges

  * skin   geometry from nibs (frames/sizes), colors/fonts from nibs and probe
  * bones  the ObjC contract from ui-api.json (who draws it, focus, keyboard,
           mouse, animation, appearance)
  * rule   what a surface must contain (surfaces.json)

into one JSON per component, plus a coverage report showing which components
still lack measurements (so the next capture round is targeted, not random).

Usage:
    components.py --nib docs/UI_REFERENCE/data/nib_geometry.json \
                  --api  docs/UI_REFERENCE/data/ui-api.json \
                  --probe docs/UI_REFERENCE/data/uiprobe.json \
                  --out  docs/UI_REFERENCE/data/components.json
"""
import argparse, json, os, sys
from collections import defaultdict

# component -> (ObjC classes that own it, nib classes that instantiate it)
CATALOG_SPEC = {
    "window.chrome": {
        "title": "Standard window (titled, closable, miniaturizable, resizable)",
        "classes": ["NSWindow", "NSPanel", "NSWindowContentView"],
        "nib_classes": ["NSWindowTemplate", "NSView"],
        "bones": ["first responder", "key window", "style mask", "content rect math",
                  "standard buttons", "resize increments", "tabbing"],
    },
    "window.traffic_lights": {
        "title": "Close / minimize / zoom buttons",
        "classes": ["NSButton", "NSButtonCell", "NSSwitch", "NSImageButton"],
        "nib_classes": ["NSButton", "NSButtonCell", "NSSwitch"],
        "bones": ["hit area", "hover/press states", "role glyph", "click action"],
    },
    "toolbar": {
        "title": "Window toolbar with items and overflow",
        "classes": ["NSToolbar", "NSToolbarItem", "NSToolbarItemView", "NSSegmentedControl"],
        "nib_classes": ["NSToolbar", "NSToolbarItem"],
        "bones": ["item order", "overflow menu", "separators", "drag to reorder",
                  "display mode (default/expanded/icon-only)"],
    },
    "source_list": {
        "title": "Sidebar source list (Favorites/Devices/places)",
        "classes": ["NSOutlineView", "NSTableView", "NSScroller", "NSTableHeaderView"],
        "nib_classes": ["NSOutlineView", "NSTableView", "NSTableColumn"],
        "bones": ["selection", "group disclosure", "row height", "icons per row",
                  "keyboard navigation"],
    },
    "list_view": {
        "title": "Table list view with columns",
        "classes": ["NSTableView", "NSTableColumn", "NSTableHeaderView"],
        "nib_classes": ["NSTableView", "NSTableColumn"],
        "bones": ["row height", "column resize/reorder", "selection", "sort indicator",
                  "alternating rows"],
    },
    "scroll_view": {
        "title": "Scroll view with scrollers",
        "classes": ["NSScrollView", "NSScroller", "NSClipView"],
        "nib_classes": ["NSScrollView", "NSScroller"],
        "bones": ["scroller metrics", "aqua scroller variants", "scrolling actions"],
    },
    "text_field": {
        "title": "Text field (label and editable)",
        "classes": ["NSTextField", "NSTextFieldCell", "NSTextView", "NSFieldEditor"],
        "nib_classes": ["NSTextField", "NSTextFieldCell"],
        "bones": ["font", "alignment", "line break", "editable flag", "bezel",
                  "placeholder colour"],
    },
    "button": {
        "title": "Push button (default, momentary, checkbox, radio, switch)",
        "classes": ["NSButton", "NSButtonCell", "NSSwitch", "NSPopUpButton"],
        "nib_classes": ["NSButton", "NSButtonCell", "NSSwitch", "NSRadioButton"],
        "bones": ["widget type", "bezel style", "target/action", "key equivalent",
                  "mixed state", "highlight"],
    },
    "pop_up_button": {
        "title": "Popup button and menu",
        "classes": ["NSPopUpButton", "NSPopUpButtonCell", "NSMenu", "NSMenuItem"],
        "nib_classes": ["NSPopUpButton", "NSPopUpButtonCell", "NSMenu"],
        "bones": ["menu construction", "item state", "separators", "tracking"],
    },
    "menu_bar": {
        "title": "System menu bar and application menus",
        "classes": ["NSMenu", "NSMenuItem", "NSApplication", "NSMenuWindow"],
        "nib_classes": ["NSMenu", "NSMenuItem"],
        "bones": ["menu titles", "key equivalents", "validation", "tracking cycle"],
    },
    "progress_indicator": {
        "title": "Indeterminate/determinate progress",
        "classes": ["NSProgressIndicator"],
        "nib_classes": ["NSProgressIndicator"],
        "bones": ["animation cadence", "spinning geometry"],
    },
    "image_view": {
        "title": "Image view with scaling",
        "classes": ["NSImageView", "NSImage"],
        "nib_classes": ["NSImageView"],
        "bones": ["scaling modes", "image names from nib", "flipped"],
    },
    "box": {
        "title": "Group box / separators",
        "classes": ["NSBox", "NSSeparator", "NSScrollView"],
        "nib_classes": ["NSBox"],
        "bones": ["title position", "border type", "fill"],
    },
    "split_view": {
        "title": "Split view panes",
        "classes": ["NSSplitView", "NSSplitViewDivider"],
        "nib_classes": ["NSSplitView", "NSSplitViewSubview"],
        "bones": ["divider thickness", "collapse behaviour"],
    },
    "tab_view": {
        "title": "Tab view",
        "classes": ["NSTabView", "NSTabViewItem"],
        "nib_classes": ["NSTabView", "NSTabViewItem"],
        "bones": ["tab metrics", "selection", "delegate"],
    },
}


def nib_index(nib_doc):
    """class name -> {frames: [...], count: n, nibs: [...]}"""
    idx = defaultdict(lambda: {"frames": [], "fonts": [], "colors": [], "nibs": [], "count": 0})
    for nib in nib_doc.get("nibs", []):
        path = nib.get("path", "")
        for v in nib.get("views", []):
            cls = v.get("class")
            if not cls:
                continue
            e = idx[cls]
            e["count"] += 1
            if len(e["nibs"]) < 8:
                e["nibs"].append(path)
            for k in ("NSFrame", "NSFrameSize", "NSCellSize", "NSBounds", "NSBorderRect"):
                if k in v:
                    e["frames"].append({"key": k, **v[k]})
            if v.get("font"):
                e["fonts"].append(v["font"])
        for f in nib.get("fonts", []):
            if f.get("family"):
                e = idx["__font__"]
                if len(e["fonts"]) < 12:
                    e["fonts"].append({k: f.get(k) for k in ("class", "family", "size")})
        for c in nib.get("colors", []):
            e = idx["__color__"]
            if len(e["colors"]) < 12:
                e["colors"].append({k: c.get(k) for k in ("class", "hex", "alpha", "space")})
    return idx


def api_index(api_doc):
    return api_doc.get("modules", {})


def bones_for(api, classnames, bones):
    """Map the named UI responsibilities to concrete selectors in our dump."""
    res = []
    for cn in classnames:
        for mod in api.values():
            c = mod["classes"].get(cn)
            if not c:
                continue
            entry = {"class": cn, "super": c.get("super"), "method_count": c.get("method_count")}
            resp = c.get("responsibilities", {})
            entry["selectors"] = {b: resp[b]["sample"] for b in resp}
            if c.get("ivars"):
                entry["ivars"] = c["ivars"][:16]
            res.append(entry)
            break
    return {"contract": res, "expected_bones": bones}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nib", required=True)
    ap.add_argument("--api", required=True)
    ap.add_argument("--probe")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    nibs = nib_index(json.load(open(a.nib)))
    api = api_index(json.load(open(a.api)))
    probe = json.load(open(a.probe)) if a.probe and os.path.exists(a.probe) else {}

    palette = {c["name"]: c["value"] for c in probe.get("colors", [])}
    fonts = probe.get("text", {}).get("fonts", [])
    window_probe = probe.get("window", {})

    comps = []
    coverage = []
    for cid, spec in sorted(CATALOG_SPEC.items()):
        skin_nib = []
        for cls in spec["nib_classes"]:
            e = nibs.get(cls)
            if e and e["count"]:
                skin_nib.append({
                    "nib_class": cls, "occurrences": e["count"],
                    "sample_nibs": e["nibs"][:4],
                    "frames": e["frames"][:12],
                    "fonts": e["fonts"][:6],
                })
        comp = {
            "id": cid,
            "title": spec["title"],
            "bones": bones_for(api, spec["classes"], spec["bones"]),
            "skin": {"from_nibs": skin_nib},
            "measured": False,
        }
        if palette:
            comp["skin"]["system_colors"] = dict(list(palette.items())[:8])
        if fonts and "text" in cid or "text" in " ".join(spec["classes"]):
            comp["skin"]["fonts"] = fonts[:8]
        if "window" in cid and window_probe:
            comp["skin"]["runtime"] = window_probe
        comps.append(comp)
        coverage.append({"component": cid,
                         "has_nib_geometry": bool(skin_nib),
                         "has_api_contract": bool(comp["bones"]["contract"]),
                         "has_runtime": bool(comp["skin"].get("runtime") or comp["skin"].get("system_colors"))})

    doc = {"schema": "mavlinos.ui-components/1",
           "source": {"nib": os.path.basename(a.nib), "api": os.path.basename(a.api),
                      "probe": os.path.basename(a.probe) if probe else None},
           "count": len(comps), "components": comps, "coverage": coverage}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(doc, open(a.out, "w"), indent=1, sort_keys=True)
    full = sum(1 for c in coverage if c["has_nib_geometry"] and c["has_api_contract"] and c["has_runtime"])
    print(f"components: {len(comps)} built, {full} fully evidenced -> {a.out}")
    for c in coverage:
        flags = "".join(k[5] for k in ("has_nib_geometry", "has_api_contract", "has_runtime"))
        if flags != "111":
            print(f"  {c['component']:<26} {flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())