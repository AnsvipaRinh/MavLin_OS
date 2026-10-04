#!/usr/bin/env python3
"""Validate Ctrl+Alt+T launches xfce4-terminal and Dock pin exists."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
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
DOCK = [
    os.path.join(REPO, "configs/desktop/plank/dock1/launchers/terminal.dockitem"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/launchers/"
        "terminal.dockitem",
    ),
]

errors = []
needle = 'name="&lt;Primary&gt;&lt;Alt&gt;t" type="string" value="xfce4-terminal"'
for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    if needle not in open(path, encoding="utf-8").read():
        errors.append("Ctrl+Alt+T must launch xfce4-terminal in %s" % path)

for path in DOCK:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if "xfce4-terminal.desktop" not in text:
        errors.append("%s must pin xfce4-terminal.desktop" % path)

pkgs = open(
    os.path.join(REPO, "archiso-profile/releng/packages.x86_64"), encoding="utf-8"
).read()
if "xfce4-terminal" not in pkgs:
    errors.append("xfce4-terminal missing from packages.x86_64")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Ctrl+Alt+T → xfce4-terminal")
print("ok - Dock pins Terminal")
print("ok - xfce4-terminal in ISO package list")
