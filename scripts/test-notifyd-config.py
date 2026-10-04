#!/usr/bin/env python3
"""Validate xfce4-notifyd Mavericks placement and theme."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/desktop/xfce/xfce4-notifyd.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-notifyd.xml",
    ),
]

REQUIRED = [
    'name="theme" type="string" value="Mavericks"',
    'name="position" type="string" value="top-right"',
    'name="expire-timeout" type="int" value="8000"',
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
    errors.append("notifyd mirrors differ")

cs = open(os.path.join(REPO, "scripts/check-sync.sh"), encoding="utf-8").read()
if "xfce4-notifyd.xml" not in cs:
    errors.append("check-sync does not track notifyd")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - notifyd theme Mavericks, top-right, 8s expire")
print("ok - mirrors identical + check-sync pair")
