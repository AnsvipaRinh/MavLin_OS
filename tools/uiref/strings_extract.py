#!/usr/bin/env python3
"""strings_extract.py - the exact English wording of every surface, from binaries.

In 10.9 the English strings of Apple apps are compiled into the executable, not
shipped as English.lproj. Menu titles, item labels, alert texts and button
captions therefore live in the Mach-O as ASCII / UTF-16 runs. This extracts
them, filters out symbols and paths, and keeps the human-facing vocabulary -
which is precisely the wording a MavLinOS app must reproduce.

Usage:
    strings_extract.py <sys-tree> --out data/terminology.json
                      [--binaries "Finder Dock LoginWindow ..."]
"""
import argparse, json, os, re, sys

ASCII_RUN = re.compile(rb"[\x20-\x7e]{4,}")
UTF16_RUN = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")

# strings that are not user-facing wording
JUNK = re.compile(r"^(?:_|__|[A-Za-z]+[A-Z][a-z]{2,}[A-Z]|v[0-9]|.*\.(?:framework|dylib|app|icns|car|nib|plist)$)")
SYMBOLISH = re.compile(r"^[A-Za-z_][A-Za-z0-9_:]*$")


def looks_like_wording(s):
    if JUNK.search(s):
        return False
    if SYMBOLISH.match(s) and " " not in s:
        return False
    if s.count(" ") == 0 and len(s) < 12:
        return False
    letters = sum(c.isalpha() or c == " " for c in s)
    if letters / max(len(s), 1) < 0.75:
        return False
    if "/" in s or "@" in s or "\\" in s:
        return False
    return True


def extract(path):
    data = open(path, "rb").read()
    out = set()
    for m in ASCII_RUN.finditer(data):
        s = m.group().decode("ascii", "ignore")
        if looks_like_wording(s):
            out.add(s)
    for m in UTF16_RUN.finditer(data):
        s = m.group().decode("utf-16-le", "ignore")
        if looks_like_wording(s):
            out.add(s)
    return out


TARGETS = ["Finder.app", "Dock.app", "SystemUIServer", "Loginwindow.app",
           "System Preferences.prefPane", "TextEdit.app", "Preview.app",
           "Calculator.app", "Stickies.app", "Font Book.app",
           "Digital Color Meter.app", "Keychain Access.app", "Console.app",
           "VoiceMemos.app", "Mission Control.app", "Dictionary.app"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("--out", required=True)
    ap.add_argument("--binaries", nargs="*", default=TARGETS)
    a = ap.parse_args()
    doc = {"schema": "mavlinos.ui-terminology/1", "source": "Mach-O string literals", "apps": {}}
    for target in a.binaries:
        hits = []
        for base, dirs, files in os.walk(a.tree):
            if target not in base:
                continue
            for f in files:
                p = os.path.join(base, f)
                try:
                    if os.path.getsize(p) < 100_000:
                        continue
                except OSError:
                    continue
                with open(p, "rb") as fh:
                    if fh.read(4) not in (b"\xfe\xed\xfa\xce", b"\xcf\xfa\xed\xfe",
                                          b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
                        continue
                try:
                    strings = extract(p)
                except OSError:
                    continue
                if strings:
                    hits.append({"binary": os.path.relpath(p, a.tree),
                                 "strings": sorted(strings)})
            if hits:
                break
        if hits:
            doc["apps"][target] = hits
            print(f"{target}: {sum(len(h['strings']) for h in hits)} strings")
    json.dump(doc, open(a.out, "w"), indent=1, sort_keys=True)
    total = sum(len(h["strings"]) for v in doc["apps"].values() for h in v)
    print(f"terminology: {len(doc['apps'])} binaries, {total} strings -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())