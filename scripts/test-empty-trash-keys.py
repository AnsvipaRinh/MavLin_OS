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

# Empty Trash is no longer bound straight to `trash-empty`: that is
# immediate, silent and irreversible, and both hotkeys reached it with no
# confirmation at all. They now go through mv-empty-trash, which shows
# Finder's "Are you sure you want to permanently erase the items in the
# Trash?" alert with Cancel as the default action. `--yes` is the only
# non-interactive escape and it is not bound to a key.
NEEDLES = [
    'name="&lt;Super&gt;&lt;Shift&gt;Delete" type="string" value="mv-empty-trash"',
    'name="&lt;Super&gt;&lt;Shift&gt;e" type="string" value="mv-empty-trash"',
]
FORBIDDEN = [
    'value="trash-empty"',
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
    for n in FORBIDDEN:
        if n in text:
            errors.append("%s still binds %s (no confirmation)" % (path, n))

doc = open(DOC, encoding="utf-8").read()
for label in ("Super+Shift+Delete", "Super+Shift+E", "Empty Trash",
              "mv-empty-trash", "asks first"):
    if label not in doc:
        errors.append("KEYBOARD.md missing %s" % label)

cs = open(os.path.join(REPO, "scripts/check-sync.sh"), encoding="utf-8").read()
if "99-mavericks-power.conf" not in cs:
    errors.append("check-sync does not track tlp power conf")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Shift+Delete → mv-empty-trash (confirms first)")
print("ok - Super+Shift+E → mv-empty-trash (confirms first)")
print("ok - raw trash-empty is no longer bound to a key")
print("ok - KEYBOARD.md documents Empty Trash")
print("ok - power conf in check-sync")
