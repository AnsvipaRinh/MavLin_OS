#!/usr/bin/env python3
"""objc_index.py - turn a raw ObjC class dump into a compact, semantic UI index.

The raw dumps (hundreds of MB of selectors) are regenerable and stay out of git.
What we commit is the *index* an implementer needs: which class owns which
responsibility, and which selectors define the contract we must honour.

Responsibility buckets (a class is filed under every bucket it contributes to):

  geometry   frames, rects, insets, layout, autosizing
  focus      first responder, key window, focus ring
  keyboard   keyDown:, interpretKeyEvents:, insertText:, flagsChanged:
  mouse      mouseDown:, hitTest:, tracking areas, cursor updates
  drawing    drawRect:, drawView:, backing, layer, appearance
  animation  animation:, NSAnimationContext, startAnimation:
  window     window chrome, style mask, tabbing, ordering
  control    widget type, cell, target/action, enabled state
  menu       menu item, key equivalent, validation
  text       text, font, paragraph, line breaking
  dragdrop   dragging, pasteboard, drop targets

Usage:
    objc_index.py --dump docs/UI_REFERENCE/data/objc-appkit.json \
                  --name appkit --out docs/UI_REFERENCE/data/ui-api.json
"""
import argparse, json, os, re, sys

BUCKETS = {
    "geometry": r"(Frame|Rect|Inset|Size|Layout|Auto[sr]izing|Constraint|spacing|padding)",
    "focus": r"(firstResponder|keyWindow|makeKey|becomeKey|focusRing|Focus|canBecomeKey)",
    "keyboard": r"(keyDown|keyUp|flagsChanged|interpretKeyEvents|insertText|cancelOperation|performKeyEquivalent|keyboard)",
    "mouse": r"(mouseDown|mouseUp|mouseDragged|mouseMoved|rightMouse|hitTest|trackingArea|setCursor|mouseExited|mouseEntered|acceptsFirstMouse)",
    "drawing": r"(drawRect|drawView|drawBaseline|drawBorder|displayIfNeeded|setWantsLayer|layer|backing|appearance|invalidate)",
    "animation": r"(animation|animate|startAnimation|stopAnimation|NSAnimationContext|setFrameRate|display:)",
    "window": r"(window|Tabbing|styleMask|titlebar|contentRect|miniaturize|zoom|orderFront|orderBack|sheet|attachedSheet)",
    "control": r"(widgetType|Cell|target|action|isEnabled|setEnabled|controlSize|sendAction|performClick)",
    "menu": r"(menuItem|keyEquivalent|Menu|validateMenuItem|performKeyEquivalent)",
    "text": r"(stringValue|setStringValue|font|textColor|textAlignment|lineBreakMode|paragraph|attributedString|insertionPoint)",
    "dragdrop": r"(dragging|pasteboard|dropTarget|readableFileTypes|writeObjects|NSDragging)",
}

COMPILED = {k: re.compile(v, re.I) for k, v in BUCKETS.items()}
SEL_MAX = 12  # per bucket, enough to be useful without bloating the index


def index_classes(doc):
    classes = doc.get("classes", {})
    out = {}
    for name, c in classes.items():
        buckets = {}
        for sel in (m["selector"] for m in c.get("methods", [])):
            for bucket, rx in COMPILED.items():
                if rx.search(sel):
                    buckets.setdefault(bucket, []).append(sel)
        ivars = [i["name"] for i in c.get("ivars", [])]
        entry = {"super": c.get("super"), "method_count": len(c.get("methods", []))}
        if ivars:
            entry["ivars"] = ivars[:24]
        for bucket, sels in buckets.items():
            uniq = sorted(set(sels))
            entry.setdefault("responsibilities", {})[bucket] = {
                "count": len(uniq),
                "sample": uniq[:SEL_MAX],
            }
        out[name] = entry
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    doc = json.load(open(a.dump))
    idx = index_classes(doc)
    full = os.path.join(a.out)
    if os.path.exists(full):
        existing = json.load(open(full))
    else:
        existing = {"schema": "mavlinos.ui-api-index/1", "modules": {}}
    existing.setdefault("modules", {})[a.name] = {
        "binary": doc.get("binary"),
        "class_count": len(idx),
        "classes": idx,
    }
    total = sum(len(v["classes"]) for v in existing["modules"].values())
    existing["class_count"] = total
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(existing, open(a.out, "w"), indent=1, sort_keys=True)
    size = os.path.getsize(a.out) // 1024
    print(f"ui-api: +{a.name} ({len(idx)} classes) total={total} -> {a.out} ({size} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())