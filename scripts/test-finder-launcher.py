#!/usr/bin/env python3
"""Validate the installed Finder desktop entry points at the Finder UI."""
import configparser
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-finder.desktop"
)

cfg = configparser.ConfigParser(interpolation=None, strict=False)
cfg.optionxform = str
with open(DESKTOP, encoding="utf-8") as fh:
    cfg.read_file(fh)

entry = cfg["Desktop Entry"]
errors = []

if entry.get("Type") != "Application":
    errors.append("Finder desktop entry must be an Application")
if entry.get("Name") != "Finder":
    errors.append("Finder desktop entry must be named Finder")

exec_line = entry.get("Exec", "")
if not exec_line.startswith("mv-finder-columns "):
    errors.append(
        "Finder desktop entry must launch mv-finder-columns, got: %s" % exec_line
    )
if exec_line.split() and exec_line.split()[0] == "thunar":
    errors.append("Finder desktop entry must not launch plain Thunar")

target = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns"
)
if not os.path.isfile(target):
    errors.append("mv-finder-columns implementation is missing")

if errors:
    for error in errors:
        print("FAIL - %s" % error)
    sys.exit(1)

print("ok - Finder desktop entry launches mv-finder-columns")
print("ok - mv-finder-columns implementation exists")
