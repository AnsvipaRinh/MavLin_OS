#!/usr/bin/env python3
"""Validate the authoritative GTK font settings stay Mavericks-consistent."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "configs/desktop/xfce/settings.ini",
    "archiso-profile/releng/airootfs/etc/skel/.config/gtk-3.0/settings.ini",
]
errors = []
for rel in FILES:
    path = os.path.join(REPO, rel)
    if not os.path.isfile(path):
        errors.append("missing GTK settings: %s" % rel)
        continue
    text = open(path, encoding="utf-8").read()
    if "gtk-font-name=Lucida Grande 11" not in text:
        errors.append("%s must use Lucida Grande 11" % rel)
    if "gtk-font-name=San Francisco 11" in text:
        errors.append("%s still contains obsolete San Francisco font" % rel)
if errors:
    for error in errors:
        print("FAIL - %s" % error)
    sys.exit(1)
print("ok - global GTK font is Lucida Grande 11 in authoritative and skel settings")
