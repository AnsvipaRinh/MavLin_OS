#!/usr/bin/env python3
"""Validate Mavericks window chrome: left traffic lights + centred title.

Cheap static half only. The behaviour that matters — that the traffic lights
exist at all, in the right order, and that each one closes / minimises /
maximises a real window — is measured by
``scripts/test-window-management-gui.py``, which starts the real xfwm4 on the
pinned Xvfb. That distinction is not cosmetic: this file passed for a long time
while 40 of the theme's button pixmaps were undecodable and a focused title bar
had no close button, because asserting the *text* ``button_layout=CHM|`` says
nothing about the artwork.
"""
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
    # false, not true: macOS 10.9 zoom fills the screen and KEEPS the title bar.
    # With titleless_maximize=true the measured maximised window had no frame at
    # all (frame == client, dx=dy=0) — no title bar, so no traffic lights, so it
    # could not be closed from its own chrome.
    'name="titleless_maximize" type="bool" value="false"',
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
print("ok - Mavericks theme; zoom keeps the title bar (titleless_maximize=false)")
print("ok - xfwm4 mirrors identical")
