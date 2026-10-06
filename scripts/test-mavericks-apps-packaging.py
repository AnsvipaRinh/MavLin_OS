#!/usr/bin/env python3
"""Validate mavericks-apps desktop launchers against package installation."""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps")
MAKEFILE = os.path.join(ROOT, "Makefile")
BIN = os.path.join(ROOT, "bin")
DESKTOP = os.path.join(ROOT, "desktop")

errors = []

if not os.path.isfile(MAKEFILE):
    errors.append("mavericks-apps Makefile missing")
else:
    makefile = open(MAKEFILE, encoding="utf-8").read()

    # Every shipped mv-* executable source must be represented by the
    # package install loop. Python files with underscores are helper modules
    # and are intentionally handled separately by the Makefile.
    bin_names = sorted(os.listdir(BIN)) if os.path.isdir(BIN) else []
    for name in bin_names:
        path = os.path.join(BIN, name)
        if not os.path.isfile(path) or not name.startswith("mv-"):
            continue
        if name == "mv-hud.c":
            continue
        if name not in makefile:
            errors.append("bin executable not installed by Makefile: %s" % name)

    # Desktop files using a native mv-* command must have that command in the
    # source tree. This prevents a launcher from silently becoming dead after
    # a rename or packaging-list edit.
    if os.path.isdir(DESKTOP):
        for name in sorted(os.listdir(DESKTOP)):
            if not name.endswith(".desktop"):
                continue
            path = os.path.join(DESKTOP, name)
            text = open(path, encoding="utf-8").read()
            match = re.search(r"^Exec=(mv-[A-Za-z0-9_-]+)(?:\s|$)", text, re.MULTILINE)
            if not match:
                continue
            command = match.group(1)
            source = os.path.join(BIN, command)
            built = command == "mv-hud"
            if not built and not os.path.isfile(source):
                errors.append("%s references missing command: %s" % (name, command))
            if command != "mv-hud" and command not in makefile:
                errors.append("%s references command not installed by Makefile: %s" % (name, command))
    else:
        errors.append("desktop directory missing")
        # Keep directory checks explicit so failures are understandable.
        if not os.path.isdir(BIN):
            errors.append("bin directory missing")
        if not os.path.isdir(DESKTOP):
            errors.append("desktop directory missing")

if errors:
    for error in errors:
        print("FAIL - %s" % error)
    sys.exit(1)

print("ok - mavericks-apps executables are covered by Makefile")
print("ok - native desktop Exec=mv-* launchers resolve to packaged commands")
