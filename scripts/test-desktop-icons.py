#!/usr/bin/env python3
"""Validate xfce4-desktop enables Mavericks-like desktop icons."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/desktop/xfce/xfce4-desktop.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-desktop.xml",
    ),
]

REQUIRED = [
    'name="show-home" type="bool" value="true"',
    'name="show-trash" type="bool" value="true"',
    'name="show-removable" type="bool" value="true"',
    'name="show-filesystem" type="bool" value="false"',
    'name="style" type="int" value="2"',
    "mavericks-desktop.png",
]

errors = []
texts = []
for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    texts.append(text)
    for needle in REQUIRED:
        if needle not in text:
            errors.append("%s missing: %s" % (path, needle))

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("xfce4-desktop.xml mirrors differ")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - desktop icons enabled (Home/Trash/removable)")
print("ok - filesystem root icon hidden")
print("ok - wallpaper path preserved")
print("ok - configs ↔ airootfs mirrors identical")
