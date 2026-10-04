#!/usr/bin/env python3
"""Validate Mavericks window chrome: left traffic lights + centered title."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/desktop/xfce/xfwm4.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfwm4.xml",
    ),
]

REQUIRED = [
    'name="button_layout" type="string" value="CHM|"',
    'name="title_alignment" type="string" value="center"',
    'name="double_click_action" type="string" value="maximize"',
    'name="theme" type="string" value="Mavericks"',
    'name="titleless_maximize" type="bool" value="true"',
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
    errors.append("xfwm4.xml mirrors differ")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - button_layout CHM| (close/hide/max left)")
print("ok - title_alignment center")
print("ok - double_click_action maximize")
print("ok - Mavericks theme + titleless maximize")
print("ok - xfwm4 mirrors identical")
