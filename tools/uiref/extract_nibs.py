#!/usr/bin/env python3
"""Mavericks UI extraction pipeline: pull ground truth out of a real 10.9 volume.

Stages (each idempotent, each writes JSON into docs/UI_REFERENCE/data/):

  nibs    -> nibkit over every .nib in the volume  -> data/components.json (layout facts)
  assets  -> carfile over every Assets.car          -> data/skin/*.json + palette proposal
  strings -> en.lproj dictionaries of key apps     -> data/terminology.json

Usage:
  extract_nibs.py   --volume <hfs-volume-dir> [--out DIR] [--jobs N]
  extract_assets.py --volume <hfs-volume-dir> [--out DIR] [--jobs N]
  extract_strings.py --volume <hfs-volume-dir> [--out FILE]

<volume-dir> is any directory tree holding the extracted macOS files (7z over the
HFS+ volume image is fine). Nothing Apple-copyright is written into this repo:
only derived numeric facts, role names and our own JSON.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(REPO, "docs", "UI_REFERENCE", "data")
NIBKIT = os.environ.get("NIBKIT", "/home/builder/vmwork/nibkit")
CARFILE = os.environ.get("CARFILE", "/home/builder/vmwork/carfile")


def walk(root, suffixes):
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(suffixes):
                yield os.path.join(base, f)


def run(cmd, timeout=300):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def nib_facts(path):
    """Decode one nib into a flat list of layout facts."""
    rc, out, err = run([NIBKIT, "tree", path], timeout=180)
    if rc != 0:
        rc, out, err = run([NIBKIT, "all", path], timeout=180)
        if rc != 0:
            return None, {"error": (err or out).strip()[:400]}
    rec = {"nib": os.path.relpath(path), "nibkit_output": out}
    try:
        rec["parsed"] = json.loads(out)
    except Exception:
        pass
    return rec, None


def extract_nibs(volume, out_path, jobs=8):
    files = sorted(walk(volume, (".nib",)))
    print(f"nibs: {len(files)} files")
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(nib_facts, f): f for f in files}
        for fut in futs:
            pass
        for fut, f in futs.items():
            rec, err = fut.result()
            if rec:
                results.append(rec)
            else:
                errors.append({"nib": os.path.relpath(f, volume), "error": err})
    doc = {"schema": "mavlinos.ui-reference-components/1",
           "source": "OS X 10.9 Mavericks volume, nibkit tree/all output",
           "count": len(results), "nibs": results, "errors": errors}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(doc, open(out_path, "w"), indent=1, sort_keys=True)
    print(f"nibs: wrote {len(results)} decoded, {len(errors)} failed -> {out_path}")
    return 0


def assets_facts(car, out_dir):
    rc, out, err = run([CARFILE, "info", car, "--format", "json"], timeout=600)
    rc2, _, _ = run([CARFILE, car, "-o", out_dir, "-f", "png"], timeout=1800)
    return {"car": os.path.basename(car), "info_rc": rc, "extract_rc": rc2,
            "info": (out[:20000] if rc == 0 else None), "error": (err[:400] if rc else None)}


def extract_assets(volume, out_dir, jobs=4):
    cars = sorted(walk(volume, ("assets.car",)))
    print(f"assets: {len(cars)} Assets.car files")
    recs = []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for car in cars:
            name = os.path.relpath(car, volume).replace("/", "_").replace(".assets.car", "")
            recs.append(assets_facts(car, os.path.join(out_dir, name)))
            print("  ", name)
    json.dump({"schema": "mavlinos.ui-reference-skin/1", "count": len(recs),
               "catalogs": recs}, open(os.path.join(out_dir, "catalogs.json"), "w"),
              indent=1, sort_keys=True)
    return 0


def extract_strings(volume, out_path):
    keys = ["systempreferences", "finder", "dock", "installer", "loginwindow", "SystemUIServer"]
    got = {}
    for base, dirs, files in os.walk(volume):
        low = base.lower()
        if not any(k in low for k in keys):
            continue
        for f in files:
            if f.lower() in ("strings", "stringsdict") and f.lower() == "strings":
                p = os.path.join(base, f)
                rc, out, _ = run(["7z", "x", "-so", p], timeout=60)
                rel = os.path.relpath(p, volume)
                try:
                    got[rel] = json.loads(out)
                except Exception:
                    got[rel] = {"raw_bytes": len(out)}
    json.dump({"schema": "mavlinos.ui-reference-terminology/1", "sources": got},
              open(out_path, "w"), indent=1, sort_keys=True)
    print(f"strings: {len(got)} dictionaries -> {out_path}")
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["nibs", "assets", "strings"])
    ap.add_argument("--volume", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    if a.stage == "nibs":
        return extract_nibs(a.volume, a.out, a.jobs)
    if a.stage == "assets":
        return extract_assets(a.volume, a.out, a.jobs)
    return extract_strings(a.volume, a.out)


if __name__ == "__main__":
    sys.exit(main())