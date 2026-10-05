#!/usr/bin/env python3
"""Validate Super+Shift+Q / Super+Alt+Escape → mv-force-quit binding and packaging."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = [
    os.path.join(
        REPO,
        "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml",
    ),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml",
    ),
]
BIN = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-force-quit"
)
MAKE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)
DOC = os.path.join(REPO, "docs/KEYBOARD.md")

errors = []
needle = (
    'name="&lt;Super&gt;&lt;Shift&gt;q" type="string" value="mv-force-quit"'
)
for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    if needle not in open(path, encoding="utf-8").read():
        errors.append("%s missing Super+Shift+Q → mv-force-quit" % path)

needle2 = (
    'name="&lt;Super&gt;&lt;Alt&gt;Escape" type="string" value="mv-force-quit"'
)
for path in KB:
    if not os.path.isfile(path):
        continue
    if needle2 not in open(path, encoding="utf-8").read():
        errors.append("%s missing Super+Alt+Escape → mv-force-quit" % path)

if not os.path.isfile(BIN):
    errors.append("mv-force-quit binary missing")
if "bin/mv-force-quit" not in open(MAKE, encoding="utf-8").read():
    errors.append("Makefile does not install mv-force-quit")
doc = open(DOC, encoding="utf-8").read()
if "Super+Shift+Q" not in doc or "Force Quit" not in doc:
    errors.append("KEYBOARD.md missing Super+Shift+Q Force Quit")
if "Super+Alt+Escape" not in doc:
    errors.append("KEYBOARD.md missing Super+Alt+Escape")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Shift+Q → mv-force-quit")
print("ok - Super+Alt+Escape → mv-force-quit")
print("ok - mv-force-quit packaged")
print("ok - KEYBOARD.md documents Force Quit")
