#!/usr/bin/env python3
"""terminology.py - pull the exact user-visible wording of every surface.

`.strings` files are binary plists inside the 10.9 tree; English ones give the
literal menu titles, item labels, alerts and button captions the real system
shows. That wording is part of the contract a MavLinOS app must reproduce, so it
belongs in the catalog next to geometry and behaviour.

Usage:
    terminology.py <sys-tree> [--out data/terminology.json] [--apps Finder Dock ...]
"""
import argparse, json, os, plistlib, sys


def parse_strings_text(text):
    """Parse NeXTSTEP/ASCII and old-style .strings payloads."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("/*"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().strip('"')
        val = val.strip().rstrip(";").strip()
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1]
        if key and val:
            out[key] = val
    return out


def is_english(base):
    return os.path.basename(base).lower() in ("en.lproj", "english.lproj")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("--out", required=True)
    ap.add_argument("--apps", nargs="*", default=[])
    ap.add_argument("--max-per-app", type=int, default=4000)
    a = ap.parse_args()

    out = {"schema": "mavlinos.ui-terminology/1", "source": a.tree, "apps": {}}
    seen = {}
    for base, dirs, files in os.walk(a.tree):
        parts = os.path.relpath(base, a.tree).split(os.sep)
        app = None
        for p in parts:
            if p.endswith(".app") or p.endswith(".prefPane") or p.endswith(".framework") or p.endswith(".bundle"):
                app = p
                break
        if app is None:
            continue
        if a.apps and not any(x.lower() in app.lower() for x in a.apps):
            continue
        if not is_english(base) and ".lproj" in base:
            continue
        for f in files:
            if f.lower() != "strings":
                continue
            p = os.path.join(base, f)
            d = None
            try:
                raw = open(p, "rb").read()
            except OSError:
                continue
            if raw[:6] == b"bplist":
                try:
                    d = plistlib.loads(raw)
                except Exception:
                    d = None
            else:
                # 10.9 English .strings are usually NeXTSTEP/ASCII or UTF-16
                for enc in ("utf-16", "utf-8", "latin-1"):
                    try:
                        text = raw.decode(enc)
                    except Exception:
                        continue
                    if "\x00" in text[:200] and enc != "latin-1":
                        continue
                    d = parse_strings_text(text)
                    if d:
                        break
            if not isinstance(d, dict):
                continue
            bucket = out["apps"].setdefault(app, {})
            name = os.path.relpath(p, a.tree)
            clean = {}
            for k, v in d.items():
                if not isinstance(k, str):
                    continue
                if isinstance(v, str) and v.strip():
                    clean[k] = v
                elif isinstance(v, (int, float, bool)):
                    clean[k] = v
                elif isinstance(v, list):
                    clean[k] = [x for x in v if isinstance(x, (str, int, float))][:8]
            if clean:
                bucket[name] = clean
                seen[app] = seen.get(app, 0) + len(clean)
    for app in out["apps"]:
        if seen.get(app, 0) > a.max_per_app:
            out["apps"][app] = {k: dict(list(v.items())[:a.max_per_app])
                                for k, v in list(out["apps"][app].items())[:40]}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
    total = sum(len(v) for app in out["apps"].values() for v in app.values())
    print(f"terminology: {len(out['apps'])} apps, {total} entries -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())