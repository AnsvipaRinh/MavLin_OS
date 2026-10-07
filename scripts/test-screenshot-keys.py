#!/usr/bin/env python3
"""Validate Screenshot keyboard bindings (Super+Shift+3/4/5).

Claim: Grok — Super+Shift+5 label said Interactive Tools but was bound to
mv-shot -i (same as region without clipboard). Lock the triad so the
registry, factory XML, skel mirror and KEYBOARD.md cannot drift apart.
"""
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
SHOT = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-shot"
)
MAKE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)

NEEDLES = [
    'name="<Super><Shift>3" type="string" value="mv-shot -m"',
    'name="<Super><Shift>4" type="string" value="mv-shot -i -c"',
    'name="<Super><Shift>5" type="string" value="mv-shot --toolbar"',
]
# Shift+5 must never fall back to bare region select.
FORBIDDEN_SHIFT5 = [
    'name="<Super><Shift>5" type="string" value="mv-shot -i"',
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
    for n in FORBIDDEN_SHIFT5:
        if n in text:
            errors.append("%s still binds Shift+5 to mv-shot -i" % path)

if not os.path.isfile(SHOT):
    errors.append("mv-shot binary missing")
else:
    body = open(SHOT, encoding="utf-8").read()
    if "--toolbar" not in body:
        errors.append("mv-shot does not implement --toolbar")
    if 'arg == "--toolbar"' not in body and 'opts["toolbar"]' not in body:
        errors.append("mv-shot --toolbar flag not wired in argv parser")

if not os.path.isfile(MAKE) or "mv-shot" not in open(MAKE, encoding="utf-8").read():
    errors.append("Makefile does not install mv-shot")

doc = open(DOC, encoding="utf-8").read() if os.path.isfile(DOC) else ""
for label in (
    "Super+Shift+3",
    "Super+Shift+4",
    "Super+Shift+5",
    "mv-shot -m",
    "mv-shot -i -c",
    "mv-shot --toolbar",
):
    if label not in doc:
        errors.append("KEYBOARD.md missing %s" % label)

# Registry part (multi-part core) must list the toolbar command.
part02 = os.path.join(
    REPO,
    "packages/mavericks-apps/src/mavericks-apps/lib/_core_part_02.txt",
)
if os.path.isfile(part02):
    p2 = open(part02, encoding="utf-8").read()
    if "screenshot-interactive" not in p2:
        errors.append("_core_part_02 missing screenshot-interactive")
    if '"mv-shot --toolbar"' not in p2:
        errors.append("_core_part_02 screenshot-interactive not bound to --toolbar")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Shift+3 → mv-shot -m (full screen)")
print("ok - Super+Shift+4 → mv-shot -i -c (selection + clipboard)")
print("ok - Super+Shift+5 → mv-shot --toolbar (interactive tools)")
print("ok - Shift+5 is not bare mv-shot -i")
print("ok - mv-shot implements --toolbar")
print("ok - KEYBOARD.md documents the triad")
