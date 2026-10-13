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
        if isinstance(v, dict):
            for k in ("NSString", "NS.string", "NSContents"):
                if k in v:
                    return self.string(v[k])
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
    """NSFont archives as AppKit writes them: NSName (PostScript), NSSize, NSfFlags."""
    cn = class_name(nib, obj)
    if cn and "Font" in str(cn):
        name = nib.string(obj.get("NSFontName") or obj.get("NSFontFamily")
                          or obj.get("NSName"))
        size = number(nib, obj.get("NSFontSize"))
        if size is None:
            size = number(nib, obj.get("NSSize"))
        flags = number(nib, obj.get("NSFontStyleMask"))
        if flags is None:
            flags = number(nib, obj.get("NSfFlags"))
        out.append({"class": cn, "family": name,
                    "size": float(size) if isinstance(size, (int, float)) else None,
                    "style": nib.string(obj.get("NSFontStyleMask")),
                    "flags": int(flags) if isinstance(flags, (int, float)) else None})
    return out


def collect_colors(nib, obj, out, depth=0):
    """NSColor archives: a catalog/name pair for system colours plus the raw
    components, which AppKit stores as NUL-terminated ASCII floats."""
    cn = class_name(nib, obj)
    if cn and "Color" in str(cn):
        space = number(nib, obj.get("NSColorSpace"))
        # In nib archives the components live in a nested NSColor object that the
        # outer record points at (the outer one only carries catalog/name).
        inner = nib.get(obj.get("NSColor")) if "NSColor" in obj else None
        src = inner if isinstance(inner, dict) else obj
        if src is not obj:
            space = number(nib, src.get("NSColorSpace"))
            if space is None:
                space = number(nib, obj.get("NSColorSpace"))
        raw = src.get("NSWhite") or src.get("NSRGB") or src.get("NSComponents")
        if isinstance(raw, bytes):
            # AppKit writes the components as NUL-terminated ASCII floats
            s = raw.decode("ascii", "ignore")
        elif isinstance(raw, str):
            s = raw
        else:
            s = nib.string(raw)
        nums = []
        if s:
            nums = [float(x) for x in
                    re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", s.strip("\x00"))]
        alpha = number(nib, src.get("NSAlpha"))
        if alpha is None:
            alpha = number(nib, src.get("NSAlphaComponent"))
        if alpha is None:
            alpha = number(nib, obj.get("NSAlpha"))
        comps = None
        if len(nums) == 1:
            comps = [nums[0]] * 3
        elif len(nums) >= 3:
            comps = nums[:3]
        entry = {"class": cn, "space": int(space) if space is not None else None,
                 "catalog": nib.string(obj.get("NSCatalogName")),
                 "name": nib.string(obj.get("NSColorName")),
                 "alpha": float(alpha) if isinstance(alpha, (int, float)) else None,
                 "rgb": comps}
        if comps:
            entry["hex"] = "#%02x%02x%02x" % tuple(
                max(0, min(255, round(c * 255))) for c in comps)
        if comps or entry["name"]:
            out.append(entry)
    return out


NUM_KEYS = ("NS.intval", "NS.floatval", "NS.doubleval", "NS.boolval",
            "NS.integerval", "NS.unsignedval", "NS.charval", "NS.int")


def number(nib, v, depth=0):
    """Resolve a keyed-archive scalar (NSNumber wrapper or plain int/float)."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    v = nib.get(v, depth)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, dict):
        for k in NUM_KEYS:
            if k in v:
                x = v[k]
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    return x
                if isinstance(x, bool):
                    return int(x)
    return None


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
    if cn and "Cell" in str(cn) and cn.startswith("NS"):
        # Cell objects carry the control appearance protocol: bezel/flags bitfields,
        # image + alternate image, key equivalent, title, text/background colour.
        rec = {"class": cn}
        for k, v in obj.items():
            if k.startswith("$"):
                continue
            if k in ("NSNormalImage", "NSAlternateImage"):
                s = nib.string(v)
                if s:
                    rec["image" if k == "NSNormalImage" else "alt_image"] = s
            elif k == "NSKeyEquivalent":
                s = nib.string(v)
                if s:
                    rec["key_equiv"] = s
            elif k in ("NSContents", "NSAlternateContents"):
                s = nib.string(v)
                if s and k == "NSContents":
                    rec["title"] = s
                elif s:
                    rec["alt_title"] = s
            elif k == "NSFont":
                collect_fonts(nib, nib.get(v), fonts)
            else:
                num = number(nib, v)
                if num is not None:
                    attrs = rec.setdefault("attrs", {})
                    if len(attrs) < 16:
                        attrs[k] = num
        collect_colors(nib, obj, colors)
        if len(rec) > 1:
            view.setdefault("controls", []).append(rec)
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
            else:
                num = number(nib, v)
                if num is not None:
                    attrs = rec.setdefault("attrs", {})
                    if len(attrs) < 24:
                        attrs[k] = num
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


def collect_menus(nib, obj, out=None, depth=0, parent=None, path=""):
    """Walk NSMenu/NSMenuItem archives into a plain menu tree.

    Menu items are not views, so the geometry pass never saw them; this recovers
    the *structure* of every menu: order, titles, key equivalents, submenus and
    disabled/enabled state - i.e. the behaviour contract of a menu bar.
    """
    if out is None:
        out = []
    if depth > 30:
        return out
    if isinstance(obj, plistlib.UID):
        if not nib.visit(obj.data):
            return out
        obj = nib.get(obj)
    if isinstance(obj, list):
        for it in obj:
            collect_menus(nib, it, out, depth + 1, parent, path)
        return out
    if not isinstance(obj, dict):
        return out
    cn = class_name(nib, obj) or ""
    if "NSMenuItem" in cn:
        # old nibs store the strings under NSTitle/NSKeyEquiv (newer ones use
        # NSMenuItemTitle/NSKeyEquivalent); accept both
        title = nib.string(obj.get("NSTitle") or obj.get("NSMenuItemTitle"))
        equiv = nib.string(obj.get("NSKeyEquiv") or obj.get("NSKeyEquivalent"))
        sub = obj.get("NSMenu") or obj.get("NSSubmenu")
        entry = {"title": title, "key_equivalent": equiv,
                 "separator": bool(nib.string(obj.get("NSIsSeparator"))),
                 "disabled": bool(nib.string(obj.get("NSIsDisabled"))),
                 "action": nib.string(obj.get("NSAction")), "submenu": None}
        out.append(entry)
        if sub is not None:
            child_path = f"{path}/{title}" if title else path
            sub_list = []
            collect_menus(nib, sub, sub_list, depth + 1, title, child_path)
            entry["submenu"] = sub_list
            entry["path"] = child_path
    for v in obj.values():
        if isinstance(v, (dict, list, plistlib.UID)):
            collect_menus(nib, v, out, depth + 1, parent, path)
    return out


def collect_connections(nib, obj, out=None, depth=0):
    """Control wiring: outlets, action selectors and Cocoa bindings.

    Every connection in a nib carries the name the interface was wired under:
    an outlet name, an action selector ("ok:") or a binding label
    ("contentArray: errors") with its key path. That wiring *is* the behaviour
    of the surface, so it is decoded instead of being re-guessed later.
    """
    if out is None:
        out = []
    if depth > 30:
        return out
    if isinstance(obj, plistlib.UID):
        if not nib.visit(obj.data):
            return out
        obj = nib.get(obj, depth)
    if isinstance(obj, list):
        for it in obj:
            collect_connections(nib, it, out, depth + 1)
        return out
    if not isinstance(obj, dict):
        return out
    conns = nib.get(obj.get("NSConnections"))
    if isinstance(conns, dict):
        items = nib.get(conns.get("NS.objects"))
        if isinstance(items, list):
            for it in items:
                rec = nib.get(it)
                if not isinstance(rec, dict):
                    continue
                label = nib.string(rec.get("NSLabel")) or ""
                key_path = nib.string(rec.get("NSKeyPath"))
                binding = nib.string(rec.get("NSBinding"))
                entry = {"label": label}
                if key_path:
                    entry["key_path"] = key_path
                if binding:
                    entry["binding"] = binding
                if label.endswith(":"):
                    entry["kind"] = "action"
                    entry["selector"] = label
                elif binding or key_path:
                    entry["kind"] = "binding"
                else:
                    entry["kind"] = "outlet"
                for side in ("NSSource", "NSDestination"):
                    target = nib.get(rec.get(side))
                    if isinstance(target, dict):
                        cls = class_name(nib, target)
                        if cls:
                            entry[side[2:].lower() + "_class"] = cls
                if len(entry) > 1:
                    out.append(entry)
    for v in obj.values():
        if isinstance(v, (dict, list, plistlib.UID)):
            collect_connections(nib, v, out, depth + 1)
    return out


def parse_nib(path):
    with open(path, "rb") as fh:
        head = fh.read(8)
        if head[:6] != b"bplist":
            return None
        fh.seek(0)
        data = fh.read()
    nib = Nib(data)
    view, fonts, colors, images = {}, [], [], []
    menus = []
    top = nib.plist.get("$top", {})
    root_uid = top.get("root") or top.get("IB.objectdata")
    root = nib.get(root_uid)
    # The IB.objectdata container holds NSVisibleWindows, NSObjectsValues (the
    # view tree), NSConnections (wiring) and NSRoot (the custom class instance).
    walk(nib, root, view, fonts, colors, images)
    if isinstance(root, dict) and "NSRoot" in root:
        walk(nib, root.get("NSRoot"), view, fonts, colors, images)
    # menus first: the geometry walk marks objects as visited, and both passes
    # share that guard so neither can loop forever
    nib.visited.clear()
    connections = collect_connections(nib, root)
    if connections:
        view["connections"] = connections[:400]
    nib.visited.clear()
    collect_menus(nib, root, menus)
    nib.visited.clear()
    rec = {"nib": path, **view}
    if menus:
        rec["menus"] = menus
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
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--locale", nargs="*", default=["English", "en"],
                    help="localizations to keep: layout is identical, only strings differ")
    a = ap.parse_args()
    if os.path.isfile(a.target):
        paths = [a.target]
    else:
        import re as _re
        lproj = _re.compile(r"([A-Za-z-]+)\.lproj$")
        keep = {x.lower() for x in a.locale}
        paths = []
        for base, dirs, files in os.walk(a.target):
            if a.apps and not any(x in base for x in a.apps):
                continue
            m = lproj.search(os.path.basename(base))
            if m and m.group(1).lower() not in keep:
                dirs[:] = []   # localized nibs differ only in strings
                continue
            for f in files:
                if f.endswith(".nib"):
                    paths.append(os.path.join(base, f))
        print(f"selected {len(paths)} nib files")
    out = {"schema": "mavlinos.ui-reference-nib-geometry/1", "nibs": []}
    ok = fail = 0
    root = a.target if os.path.isdir(a.target) else "."
    # nib parsing is CPU bound and one pathological archive must not stall the
    # whole run: parallel workers, each file independent.
    from concurrent.futures import ProcessPoolExecutor, as_completed
    results = []
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(parse_nib, p): p for p in sorted(paths)}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                r = fut.result()
            except Exception as e:  # keep going: one bad nib must not kill the run
                r = None
            if r:
                r.pop("nib", None)
                r["path"] = os.path.relpath(p, root)
                results.append(r)
                ok += 1
            else:
                fail += 1
    results.sort(key=lambda d: d.get("path", ""))
    out["nibs"] = results
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