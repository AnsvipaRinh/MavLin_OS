#!/usr/bin/env python3
"""Validate menu-bar clock uses Mavericks-like digital format."""
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
    'name="plugin-5" type="string" value="clock"',
    'name="mode" type="uint" value="2"',
    'name="digital-format" type="string" value="%a %-I:%M %p"',
    'name="tooltip-format" type="string" value="%A, %B %-d, %Y"',
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

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("panel XML mirrors differ")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - clock plugin digital mode (2)")
print("ok - format %a %-I:%M %p (day + 12h time)")
print("ok - tooltip full date")
print("ok - panel mirrors identical")
