#!/usr/bin/env python3
"""Validate mv-apple panel plugin is built and installed by Makefile."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)
DESKTOP = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/panel/mv-apple.desktop"
)
SOURCE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/panel/mv-apple.c"
)
if os.path.isfile(SOURCE):
    src = open(SOURCE, encoding="utf-8").read()
    if "gtk_menu_item_new_with_mnemonic(label)" not in src:
        errors.append("Apple menu items must use GTK mnemonic labels")
    if "gtk_menu_item_new_with_label(label)" in src:
        errors.append("Apple menu must not construct labels without mnemonic support")
ICON = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/icons/mv-apple.svg"
)
HELPERS = [
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-force-quit",
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-recent-items",
]
PANEL = [
    os.path.join(REPO, "configs/desktop/xfce/xfce4-panel.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-panel.xml",
    ),
]

errors = []
if not os.path.isfile(SOURCE):
    errors.append("mv-apple.c missing")
if not os.path.isfile(ICON):
    errors.append("mv-apple.svg missing")
if not os.path.isfile(MAKEFILE):
    errors.append("Makefile missing")
else:
    mk = open(MAKEFILE, encoding="utf-8").read()
    for needle in (
        "libmv-apple.so",
        "panel/mv-apple.c",
        "mv-apple.desktop",
        "lib/xfce4/panel/plugins",
        "mv-force-quit",
        "mv-recent-items",
        "mv-apple.svg",
    ):
        if needle not in mk:
            errors.append("Makefile missing %s" % needle)

if not os.path.isfile(DESKTOP):
    errors.append("mv-apple.desktop missing")
else:
    desk = open(DESKTOP, encoding="utf-8").read()
    if "X-XFCE-Module=mv-apple" not in desk:
        errors.append("mv-apple.desktop must set X-XFCE-Module=mv-apple")

for rel in HELPERS:
    if not os.path.isfile(os.path.join(REPO, rel)):
        errors.append("helper missing: %s" % rel)

for path in PANEL:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    if 'value="mv-apple"' not in open(path, encoding="utf-8").read():
        errors.append("%s must reference plugin mv-apple" % path)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - mv-apple.c / desktop / icon present")
print("ok - Makefile builds and installs panel plugin + helpers")
print("ok - panel XML references mv-apple")
