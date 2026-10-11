#!/usr/bin/env python3
"""Manage UI reference facts in docs/UI_REFERENCE/data/*.json.

Usage:
  measure.py add <file> <id> <value> [--kind measured] [--evidence cap.png]
              [--confidence high] [--unit pt] [--notes "..."] [--deriv "..."]
  measure.py set <file> <id> <value> [--field value] [--key k]   # update existing
  measure.py rm  <file> <id>
  measure.py get <id>            # searches all files
  measure.py list [file]
"""
import argparse, json, os, sys

DATA = os.path.join(os.path.dirname(__file__), "../../docs/UI_REFERENCE/data")


def path_for(file):
    if not file.endswith(".json"):
        file += ".json"
    return os.path.join(DATA, file)


def load(p):
    if not os.path.exists(p):
        return {"facts": []}
    d = json.load(open(p))
    d.setdefault("facts", [])
    return d


def find(p, fid):
    for i, f in enumerate(load(p)["facts"]):
        if f["id"] == fid:
            return i, f
    return None, None


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "rm"):
        p = sub.add_parser(name); p.add_argument("file"); p.add_argument("id")
        if name == "add":
            p.add_argument("value", type=float)
            p.add_argument("--kind", default="measured",
                           choices=["measured", "derived", "literature", "design"])
            p.add_argument("--evidence"); p.add_argument("--confidence", default="high",
                           choices=["high", "medium", "low"])
            p.add_argument("--unit", default="pt"); p.add_argument("--notes", default="")
            p.add_argument("--deriv", default="")
    p = sub.add_parser("set"); p.add_argument("file"); p.add_argument("id")
    p.add_argument("value", type=float, nargs="?"); p.add_argument("--kind")
    p.add_argument("--evidence"); p.add_argument("--confidence"); p.add_argument("--unit")
    p.add_argument("--notes"); p.add_argument("--deriv")
    p = sub.add_parser("get"); p.add_argument("id")
    p = sub.add_parser("list"); p.add_argument("file", nargs="?")
    a = ap.parse_args()

    if a.cmd == "get":
        for fn in sorted(os.listdir(DATA)):
            if not fn.endswith(".json"):
                continue
            _, f = find(os.path.join(DATA, fn), a.id)
            if f:
                print(json.dumps(f, indent=2, sort_keys=True))
                return 0
        print("not found:", a.id)
        return 1

    if a.cmd == "list":
        files = [a.file] if a.file else [f[:-5] for f in sorted(os.listdir(DATA)) if f.endswith(".json")]
        for fn in files:
            d = load(path_for(fn))
            print(f"== {fn} ({len(d['facts'])})")
            for f in d["facts"]:
                print(f"  {f['id']:<48} {f.get('value')} {f.get('unit','')} [{f.get('kind')}/{f.get('confidence')}] {f.get('evidence','')}")
        return 0

    p = path_for(a.file)
    d = load(p)
    if a.cmd == "add":
        i, _ = find(p, a.id)
        fact = {"id": a.id, "value": a.value, "unit": a.unit, "kind": a.kind,
                "confidence": a.confidence, "notes": a.notes}
        if a.evidence:
            fact["evidence"] = a.evidence
        if a.deriv:
            fact["deriv"] = a.deriv
        if i is None:
            d["facts"].append(fact)
        else:
            print("exists, use set:", a.id)
            return 1
    elif a.cmd == "set":
        i, f = find(p, a.id)
        if i is None:
            print("not found:", a.id)
            return 1
        for k in ("value", "kind", "confidence", "unit", "notes", "evidence", "deriv"):
            v = getattr(a, k, None)
            if v is not None:
                f[k] = v
    elif a.cmd == "rm":
        i, _ = find(p, a.id)
        if i is None:
            print("not found:", a.id)
            return 1
        d["facts"].pop(i)
    json.dump(d, open(p, "w"), indent=2, sort_keys=True)
    print("saved", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
