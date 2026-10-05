#!/usr/bin/env python3
"""Validate Super+Delete (mv-trash) and Super+F4 (mv-eject) bindings + packaging."""
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
TRASH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-trash"
)
EJECT = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-eject"
)
MAKE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)
PKGS = os.path.join(REPO, "archiso-profile/releng/packages.x86_64")
DOC = os.path.join(REPO, "docs/KEYBOARD.md")

errors = []
for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if 'name="&lt;Super&gt;Delete" type="string" value="mv-trash"' not in text:
        errors.append("%s missing Super+Delete → mv-trash" % path)
    if 'name="&lt;Super&gt;F4" type="string" value="mv-eject"' not in text:
        errors.append("%s missing Super+F4 → mv-eject" % path)

if not os.path.isfile(TRASH):
    errors.append("mv-trash script missing")
else:
    body = open(TRASH, encoding="utf-8").read()
    if "trash-put" not in body:
        errors.append("mv-trash must call trash-put")

if not os.path.isfile(EJECT):
    errors.append("mv-eject missing")

mf = open(MAKE, encoding="utf-8").read()
if "bin/mv-trash" not in mf:
    errors.append("Makefile does not install mv-trash")

pkgs = open(PKGS, encoding="utf-8").read()
if "trash-cli" not in pkgs:
    errors.append("trash-cli missing from packages.x86_64")
if "xdotool" not in pkgs:
    errors.append("xdotool missing from packages.x86_64 (mv-trash fallback)")

doc = open(DOC, encoding="utf-8").read()
if "Super+Delete" not in doc or "Super+F4" not in doc:
    errors.append("KEYBOARD.md missing Super+Delete or Super+F4")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Delete → mv-trash")
print("ok - Super+F4 → mv-eject")
print("ok - mv-trash packaged in Makefile")
print("ok - trash-cli + xdotool in ISO")
