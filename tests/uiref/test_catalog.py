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
                if ev not in index.get("captures", {}):
                    errors.append(f"{fn}: {fid} evidence '{ev}' not in captures/index.json")
            if f.get("kind") == "literature" and f.get("confidence") == "high":
                errors.append(f"{fn}: {fid} literature cannot be high confidence")
            if fn == "palette.json":
                if not HEX_RE.match(str(f.get("hex", ""))):
                    errors.append(f"palette.json: {fid} bad hex {f.get('hex')}")

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

    if errors:
        print("UI_REFERENCE VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"ui-reference catalog OK: {len(ids)} facts, {len(index.get('captures', {}))} captures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
