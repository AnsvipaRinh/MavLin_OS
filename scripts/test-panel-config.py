#!/usr/bin/env python3
"""Validate Mavericks menu-bar panel layout and mirror sync."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/desktop/xfce/xfce4-panel.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-panel.xml",
    ),
]

REQUIRED = [
    'value="mv-apple"',
    'value="appmenu"',
    'value="systray"',
    'value="clock"',
    'value="power-manager-plugin"',
    'name="size" type="uint" value="24"',
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
            errors.append("%s missing %s" % (path, needle))
    if text.count('name="plugin-') < 6:
        errors.append("%s expected 6 plugins" % path)

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("configs ↔ airootfs panel XML drift")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

for path in PATHS:
    print("OK:", path)
print("OK: configs ↔ airootfs panel XML identical")
print("OK: mv-apple + appmenu + clock + power-manager layout")
