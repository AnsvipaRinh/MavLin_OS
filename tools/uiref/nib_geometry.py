#!/usr/bin/env python3
"""nib_geometry.py - extract exact layout/skin facts from compiled .nib files.

Mavericks-era nibs are NSKeyedArchiver binary plists. Geometry lives as
Cocoa string literals ("{{x, y}, {w, h}}"), colors as NSColor archives, fonts as
NSFont archives. This turns all of that into structured facts:

    {
      "nib": "Finder.app/.../FloatingStatusBar.nib",
      "windows": [{"title": "...", "rect": {...}, "style_mask": 15,
                   "min_size": {...}, "class": "NSWindow"}],
      "views":   [{"class": "NSPopUpButton", "frame": {...},
                   "font": {"family": "Lucida Grande", "size": 13.0},
                   "text": "...", "alignment": 2, "cell": "NSMenuCell"}],
      "colors":  [{"role_hint": "window.background", "rgb": [0.8,0.8,0.8],
                   "space": "calibratedRGB", "alpha": 1.0}],
      "images":  ["NSImageName: ToolbarItemBack"]
    }

Usage: nib_geometry.py <nib-or-tree> [--out FILE] [--json]
"""
import argparse, json, os, plistlib, re, sys

RECT_RE = re.compile(r"\{\{(-?[\d.]+), (-?[\d.]+)\}, \{(-?[\d.]+), (-?[\d.]+)\}\}")
SIZE_RE = re.compile(r"\{(-?[\d.]+), (-?[\d.]+)\}")
POINT_RE = re.compile(r"^\{(-?[\d.]+), (-?[\d.]+)\}")
NSRGB_RE = re.compile(r"\{([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+)\}")

GEOM_KEYS = ("Frame", "Rect", "Size", "Point", "Margin", "Insets", "Offset",
             "MinSize", "MaxSize", "CellSize", "ContentRect")


class Nib:
    def __init__(self, data):
        self.plist = plistlib.loads(data)
        self.objects = self.plist.get("$objects", [])
        self.visited = set()

    def visit(self, uid):
        """Cycle guard: every object is decoded at most once."""
        if uid in self.visited:
            return False
        self.visited.add(uid)
        return True

    def get(self, v, depth=0):
        """Resolve a plist value, following UID references (bounded)."""
        if isinstance(v, plistlib.UID):
            if v.data < len(self.objects) and depth < 12:
                return self.objects[v.data]
            return None
        return v

    def string(self, v):
        v = self.get(v)
        if isinstance(v, str):
            return v
        if isinstance(v, dict) and "NSString" in v:
            return self.string(v["NSString"])
        return None

    @staticmethod
    def parse_geom(s, key=""):
        if not s:
            return None
        k = (key or "").lower()
        if k.endswith("size"):
            m = SIZE_RE.match(s)
            if m:
                w, h = float(m.group(1)), float(m.group(2))
                return {"w": w, "h": h, "size": "{w=%g, h=%g}" % (w, h)}
            return None
        if k.endswith("point") or k.endswith("offset") or k.endswith("origin"):
            m = POINT_RE.match(s)
            if m:
                x, y = float(m.group(1)), float(m.group(2))
                return {"x": x, "y": y, "point": "{x=%g, y=%g}" % (x, y)}
            return None
        m = RECT_RE.match(s)
        if m:
            x, y, w, h = (float(g) for g in m.groups())
            return {"x": x, "y": y, "w": w, "h": h,
                    "rect": "{x=%g, y=%g, w=%g, h=%g}" % (x, y, w, h)}
        m = POINT_RE.match(s)
        if m:
            x, y = float(m.group(1)), float(m.group(2))
            return {"x": x, "y": y, "point": "{x=%g, y=%g}" % (x, y)}
        m = SIZE_RE.match(s)
        if m:
            w, h = float(m.group(1)), float(m.group(2))
            return {"w": w, "h": h, "size": "{w=%g, h=%g}" % (w, h)}
        return None


def class_name(nib, obj, depth=0):
    if not isinstance(obj, dict) or depth > 6:
        return None
    cls = obj.get("$class")
    if cls is None:
        return obj.get("$classname")
    target = nib.get(cls)
    if isinstance(target, dict):
        if "$classname" in target:
            return target["$classname"]
        names = target.get("$classnames") or (target.get("$classes") or [None])[0]
        if isinstance(names, (list, tuple)):
            names = names[0] if names else None
        if isinstance(names, str):
            return names
    return None


def collect_fonts(nib, obj, out, depth=0):
    cn = class_name(nib, obj)
    if cn and "Font" in str(cn):
        name = nib.string(obj.get("NSFontName") or obj.get("NSFontFamily"))
        size = nib.string(obj.get("NSFontSize"))
        try:
            size = float(size)
        except (TypeError, ValueError):
            size = None
        out.append({"class": cn, "family": name, "size": size,
                    "style": nib.string(obj.get("NSFontStyleMask"))})
    return out


def collect_colors(nib, obj, out, depth=0):
    cn = class_name(nib, obj)
    if cn and "Color" in str(cn):
        space = nib.string(obj.get("NSColorSpace")) or nib.string(obj.get("NSColorSpaceName"))
        raw = obj.get("NSRGB") or obj.get("NSWhite") or obj.get("NSComponents")
        s = nib.string(raw) if raw is not None else None
        comps = None
        if s:
            m = NSRGB_RE.match(s)
            if m:
                comps = [float(m.group(i)) for i in range(1, 4)]
                alpha = float(m.group(4))
            else:
                m2 = SIZE_RE.match(s)
                if m2:
                    comps = [float(m2.group(1))] * 3
                    alpha = float(m2.group(2))
        if comps:
            hexv = "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in comps)
            out.append({"class": cn, "space": space, "rgb": comps,
                        "alpha": alpha, "hex": hexv})
    return out


def walk(nib, obj, view, fonts, colors, images, depth=0):
    if depth > 60:
        return
    if isinstance(obj, plistlib.UID):
        if not nib.visit(obj.data):
            return
        obj = nib.get(obj, depth)
    if isinstance(obj, list):
        for it in obj:
            walk(nib, it, view, fonts, colors, images, depth + 1)
        return
    if not isinstance(obj, dict):
        return
    cn = class_name(nib, obj)
    if cn and any(k in str(cn) for k in ("NSWindow",)):
        win = {"class": cn}
        for key, tgt in (("title", "NSWindowTitle"), ("rect", "NSWindowRect"),
                         ("min_size", "NSWindowMinSize"), ("max_size", "NSWindowMaxSize"),
                         ("content_rect", "NSWindowContentRect")):
            if tgt in obj:
                if key in ("rect", "min_size", "max_size", "content_rect"):
                    g = Nib.parse_geom(nib.string(obj[tgt]), tgt)
                    if g:
                        win[key] = g
                else:
                    s = nib.string(obj[tgt])
                    if s:
                        win[key] = s
        if "NSWindowStyleMask" in obj:
            v = nib.get(obj["NSWindowStyleMask"])
            if isinstance(v, (int, float)):
                win["style_mask"] = int(v)
        view.setdefault("windows", []).append(win)
    if cn and ("NSView" in str(cn) or cn.startswith("NS") and "Cell" not in str(cn)
               and any(k.endswith(("View", "Control", "Scroller", "TextField", "Button",
                                   "PopUp", "Box", "ScrollView", "TableView",
                                   "OutlineView", "TabView")) for k in [str(cn)])):
        rec = {"class": cn}
        for k, v in obj.items():
            if k.startswith("$"):
                continue
            if any(g.lower() in k.lower() for g in GEOM_KEYS):
                g = Nib.parse_geom(nib.string(v), k)
                if g:
                    rec[k] = g
            elif k in ("NSFont", "NSAttributedStringFont"):
                collect_fonts(nib, nib.get(v), fonts)
            elif k in ("NSKeyEquiv", "NSToolTip", "NSTitle", "NSContents", "NSHeaderCell",
                       "NSPopUpSelection", "NSAlternateContents"):
                s = nib.string(v)
                if s and k == "NSKeyEquiv":
                    rec["key_equiv"] = s
                elif s and k == "NSToolTip":
                    rec["tooltip"] = s
            elif k in ("NSAlignment", "NSTextAlignment"):
                v2 = nib.get(v)
                if isinstance(v2, (int, float)):
                    rec["alignment"] = int(v2)
        view.setdefault("views", []).append(rec)
    collect_fonts(nib, obj, fonts)
    collect_colors(nib, obj, colors)
    img = nib.string(obj.get("NSImageName")) if isinstance(obj, dict) else None
    if img:
        images.append(img)
    for v in obj.values():
        if isinstance(v, (dict, list, plistlib.UID)):
            walk(nib, v, view, fonts, colors, images, depth + 1)
            if len(view.get("views", [])) > 4000:
                return


def parse_nib(path):
    with open(path, "rb") as fh:
        head = fh.read(8)
        if head[:6] != b"bplist":
            return None
        fh.seek(0)
        data = fh.read()
    nib = Nib(data)
    view, fonts, colors, images = {}, [], [], []
    top = nib.plist.get("$top", {})
    root_uid = top.get("root") or top.get("IB.objectdata")
    root = nib.get(root_uid)
    # The IB.objectdata container holds NSVisibleWindows, NSObjectsValues (the
    # view tree), NSConnections (wiring) and NSRoot (the custom class instance).
    walk(nib, root, view, fonts, colors, images)
    if isinstance(root, dict) and "NSRoot" in root:
        walk(nib, root.get("NSRoot"), view, fonts, colors, images)
    rec = {"nib": path, **view}
    if fonts:
        rec["fonts"] = fonts
    if colors:
        rec["colors"] = colors
    if images:
        rec["images"] = sorted(set(images))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--out")
    ap.add_argument("--all-locales", action="store_true",
                    help="keep localized copies instead of deduplicating by content hash")
    ap.add_argument("--apps", nargs="*", default=[],
                    help="only nibs below these app/framework names")
    a = ap.parse_args()
    if os.path.isfile(a.target):
        paths = [a.target]
    else:
        paths = []
        for base, dirs, files in os.walk(a.target):
            if a.apps and not any(x in base for x in a.apps):
                continue
            for f in files:
                if f.endswith(".nib"):
                    paths.append(os.path.join(base, f))
    if not a.all_locales and not os.path.isfile(a.target):
        # Nibs are duplicated per language; identical bytes carry identical
        # layout facts, so keep one representative (English preferred).
        import hashlib
        seen, uniq = {}, []
        for p in sorted(paths, key=lambda s: ("English.lproj" not in s, s)):
            try:
                h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            except OSError:
                continue
            if h in seen:
                continue
            seen[h] = p
            uniq.append(p)
        paths = uniq
        print(f"deduped {len(seen)} unique nibs")
    out = {"schema": "mavlinos.ui-reference-nib-geometry/1", "nibs": []}
    ok = fail = 0
    for p in sorted(paths):
        try:
            r = parse_nib(p)
        except Exception as e:  # keep going: one bad nib must not kill the run
            r = None
            err = str(e)[:120]
        if r:
            r.pop("nib")
            r["path"] = os.path.relpath(p, a.target if os.path.isdir(a.target) else ".")
            out["nibs"].append(r)
            ok += 1
        else:
            fail += 1
    out["decoded"] = ok
    out["failed"] = fail
    text = json.dumps(out, indent=1, sort_keys=True)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w").write(text)
        print(f"nib-geometry: {ok} decoded, {fail} failed -> {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())