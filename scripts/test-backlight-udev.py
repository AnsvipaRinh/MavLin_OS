#!/usr/bin/env python3
"""Validate backlight udev uaccess rules are shipped and mirrored."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/udev/90-mavericks-backlight.rules"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/udev/rules.d/90-mavericks-backlight.rules",
    ),
]

errors = []
texts = []
for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    texts.append(text)
    if 'SUBSYSTEM=="backlight"' not in text or 'TAG+="uaccess"' not in text:
        errors.append("%s must TAG backlight with uaccess" % path)
    if "kbd_backlight" not in text:
        errors.append("%s should cover kbd_backlight LEDs" % path)

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("backlight udev rule mirrors differ")

sync = open(os.path.join(REPO, "scripts/check-sync.sh"), encoding="utf-8").read()
if "90-mavericks-backlight.rules" not in sync:
    errors.append("check-sync PAIRS missing backlight udev pair")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - backlight udev uaccess rules present and mirrored")
print("ok - check-sync tracks the pair")
