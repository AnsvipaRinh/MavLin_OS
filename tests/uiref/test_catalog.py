#!/usr/bin/env python3
"""Validator for docs/UI_REFERENCE.

A fact is only allowed to exist if it is evidence-backed. This test fails when:
  * data/*.json is malformed or a fact lacks required fields
  * fact ids collide across data files
  * an `evidence` value names a capture missing from captures/index.json
    or missing from disk (md5 mismatch)
  * measured/derived facts have no evidence
  * literature facts claim high confidence
  * palette hexes are not 6-digit hex
  * a fact id is not rendered into its catalog page (docs drift)
Exit code 0 = catalog is coherent.
"""
import json, os, re, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "../../docs/UI_REFERENCE")
DATA = os.path.join(REF, "data")
CAPTURES = os.path.join(REF, "captures")
CATALOG = os.path.join(REF, "catalog")

REQUIRED = ("id", "kind", "confidence")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def main():
    errors = []

    index_path = os.path.join(CAPTURES, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else {"captures": {}}

    for fn, e in index.get("captures", {}).items():
        p = os.path.join(CAPTURES, fn)
        if not os.path.exists(p):
            errors.append(f"index references missing file: {fn}")
            continue
        md5 = hashlib.md5(open(p, "rb").read()).hexdigest()
        if md5 != e.get("md5"):
            errors.append(f"md5 mismatch for {fn} (edited capture?)")

    sources = {}
    for cand in ("sources.json", "palette.json", "metrics.json", "typography.json",
                 "behaviors.json", "patterns.json"):
        p = os.path.join(DATA, cand)
        if os.path.exists(p):
            sources.update(json.load(open(p)).get("sources", {}))

    ids = {}
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(DATA, fn)))
        for f in d.get("facts", []):
            fid = f.get("id")
            for k in REQUIRED:
                if k not in f:
                    errors.append(f"{fn}: fact {fid} missing field {k}")
            if fid in ids:
                errors.append(f"duplicate fact id: {fid} in {fn} and {ids[fid]}")
            ids[fid] = fn
            ev = f.get("evidence")
            if f.get("kind") in ("measured", "derived") and not ev:
                errors.append(f"{fn}: {fid} is {f.get('kind')} but has no evidence")
            if ev:
                if ev.startswith("src:"):
                    key = ev[4:]
                    if key not in sources:
                        errors.append(f"{fn}: {fid} evidence '{ev}' is not in any sources registry")
                elif ev not in index.get("captures", {}):
                    errors.append(f"{fn}: {fid} evidence '{ev}' not in captures/index.json")
            if f.get("kind") == "literature" and f.get("confidence") == "high":
                errors.append(f"{fn}: {fid} literature cannot be high confidence")
            if fn == "palette.json":
                if not HEX_RE.match(str(f.get("hex", ""))):
                    errors.append(f"palette.json: {fid} bad hex {f.get('hex')}")

    # component library: every component must name its classes and must appear in
    # the coverage report (so "what is still unmeasured" is always answerable)
    comp_path = os.path.join(DATA, "components.json")
    if os.path.exists(comp_path):
        comp = json.load(open(comp_path))
        cov = {c["component"] for c in comp.get("coverage", [])}
        for c in comp.get("components", []):
            if c["id"] not in cov:
                errors.append(f"components.json: {c['id']} missing from coverage report")
            if not c.get("bones", {}).get("contract"):
                errors.append(f"components.json: {c['id']} has no ObjC contract")
    api_path = os.path.join(DATA, "ui-api.json")
    api = json.load(open(api_path)) if os.path.exists(api_path) else {}
    api_classes = {name for mod in api.get("modules", {}).values()
                   for name in mod.get("classes", {})}
    comp_path2 = os.path.join(DATA, "components.json")
    if os.path.exists(comp_path2):
        for c in json.load(open(comp_path2)).get("components", []):
            for entry in c.get("bones", {}).get("contract", []):
                if entry["class"] not in api_classes:
                    errors.append(f"components.json: {c['id']} references class "
                                  f"{entry['class']} absent from ui-api.json")

    # ui-api index must stay in sync with the dumps it was built from
    if api:
        for mod, body in api.get("modules", {}).items():
            if body.get("class_count") != len(body.get("classes", {})):
                errors.append(f"ui-api.json: {mod} class_count mismatch")

    # coverage: every fact id appears in a catalog page
    cat_files = {}
    for fn in sorted(os.listdir(CATALOG)):
        if fn.endswith(".md"):
            cat_files[fn] = open(os.path.join(CATALOG, fn)).read()
    catalog_text = "\n".join(cat_files.values())
    stem = {"metrics.json": "metrics.md", "palette.json": "palette.md",
            "typography.json": "typography.md", "behaviors.json": "behaviors.md",
            "patterns.json": "patterns.md"}
    for fid, fn in ids.items():
        page = stem.get(fn)
        if page and page in cat_files and fid not in cat_files[page]:
            errors.append(f"docs drift: {fid} from {fn} not rendered into catalog/{page}")

    # theme layer: colours/fonts must agree with nib_geometry and be rendered
    th_path = os.path.join(DATA, "theme.json")
    if os.path.exists(th_path):
        th = json.load(open(th_path))
        geo = json.load(open(os.path.join(DATA, "nib_geometry.json")))
        named = sum(1 for n in geo.get("nibs", []) for c in n.get("colors", [])
                    if c.get("name"))
        if th["summary"]["color_names"] < 1:
            errors.append("theme.json: no system colour names resolved")
        if not th.get("fonts"):
            errors.append("theme.json: no fonts resolved from nibs")
        page = cat_files.get("theme.md", "")
        for c in th["system_colors"][:5]:
            if f"| {c['name']} |" not in page:
                errors.append(f"catalog/theme.md missing colour {c['name']}")
        if named and th["summary"]["color_names"] > named:
            errors.append("theme.json: more colour names than nib records")


    # window templates: counts must reconcile and the page must show the real masks
    win_path = os.path.join(DATA, "windows.json")
    if os.path.exists(win_path):
        win = json.load(open(win_path))
        if win.get("count") != len(win.get("windows", [])):
            errors.append("windows.json: count does not match windows array")
        geo_count = sum(len(n.get("windows", []))
                        for n in json.load(open(os.path.join(DATA, "nib_geometry.json")))
                        .get("nibs", []))
        if win.get("count") != geo_count:
            errors.append(f"windows.json: {win.get('count')} != nib_geometry {geo_count}")
        page = cat_files.get("windows.md", "")
        for mask, count, _bits in win.get("summary", {}).get("style_masks", [])[:5]:
            if f"| {mask} | {count} |" not in page:
                errors.append(f"catalog/windows.md does not show mask {mask}")


    # asset geometry: the decoded inventory must reconcile with itself and the
    # icon grid the desktop ships must be visible in the rendered page
    ast_path = os.path.join(DATA, "assets.json")
    if os.path.exists(ast_path):
        ast = json.load(open(ast_path))
        if ast.get("count") != len(ast.get("assets", [])):
            errors.append("assets.json: count does not match assets array")
        bad = [a.get("path") for a in ast.get("assets", [])
               if not a.get("format") or not a.get("path")]
        if bad:
            errors.append(f"assets.json: {len(bad)} assets without format/path")
        page = cat_files.get("assets.md", "")
        for px in ast.get("summary", {}).get("icns_grid_sizes", {}):
            if f"| {px} |" not in page:
                errors.append(f"catalog/assets.md does not show icon size {px}")


    # control appearance protocol: cells must reconcile with nib_geometry, and the
    # generated page must actually show them (fails if a rebuild loses data)
    ctl_path = os.path.join(DATA, "controls.json")
    geo_path = os.path.join(DATA, "nib_geometry.json")
    if os.path.exists(ctl_path) and os.path.exists(geo_path):
        ctl = json.load(open(ctl_path))
        geo = json.load(open(geo_path))
        raw_cells = sum(len(n.get("controls", [])) for n in geo.get("nibs", []))
        if ctl.get("cells") != raw_cells:
            errors.append(f"controls.json: cells {ctl.get('cells')} != nib_geometry {raw_cells}")
        declared = sum(c["instances"] for c in ctl.get("classes", []))
        if declared != ctl.get("cells"):
            errors.append(f"controls.json: instances {declared} != cells {ctl.get('cells')}")
        ctl_ids = [c["id"] for c in ctl.get("classes", [])]
        if len(set(ctl_ids)) != len(ctl_ids):
            errors.append("controls.json: duplicate control ids")
        page = cat_files.get("controls.md", "")
        missing = [c["class"] for c in ctl.get("classes", [])
                   if c["class"] not in page]
        if missing:
            errors.append(f"catalog/controls.md missing classes: {missing[:5]}")


    if errors:
        print("UI_REFERENCE VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"ui-reference catalog OK: {len(ids)} facts, {len(index.get('captures', {}))} captures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
