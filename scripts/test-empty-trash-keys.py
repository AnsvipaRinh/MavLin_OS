#!/usr/bin/env python3
"""Validate Empty Trash keyboard bindings match KEYBOARD.md."""
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
DOC = os.path.join(REPO, "docs/KEYBOARD.md")

NEEDLES = [
    'name="&lt;Super&gt;&lt;Shift&gt;Delete" type="string" value="trash-empty"',
    'name="&lt;Super&gt;&lt;Shift&gt;e" type="string" value="trash-empty"',
]

errors = []
for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    for n in NEEDLES:
        if n not in text:
            errors.append("%s missing %s" % (path, n))

doc = open(DOC, encoding="utf-8").read()
for label in ("Super+Shift+Delete", "Super+Shift+E", "Empty Trash"):
    if label not in doc:
        errors.append("KEYBOARD.md missing %s" % label)

cs = open(os.path.join(REPO, "scripts/check-sync.sh"), encoding="utf-8").read()
if "99-mavericks-power.conf" not in cs:
    errors.append("check-sync does not track tlp power conf")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Shift+Delete → trash-empty")
print("ok - Super+Shift+E → trash-empty")
print("ok - KEYBOARD.md documents Empty Trash")
print("ok - power conf in check-sync")
