#!/usr/bin/env python3
"""Validate lock shortcut + greeter clock format + screensaver package."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = [
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
GREETER = [
    os.path.join(REPO, "configs/desktop/lightdm/lightdm-gtk-greeter.conf"),
    os.path.join(
        REPO, "archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf"
    ),
]
PKGS = os.path.join(REPO, "archiso-profile/releng/packages.x86_64")

errors = []
needle = (
    'name="&lt;Primary&gt;&lt;Alt&gt;l" type="string" '
    'value="xfce4-screensaver-command --lock"'
)
for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    if needle not in open(path, encoding="utf-8").read():
        errors.append("Ctrl+Alt+L lock binding missing in %s" % path)

for path in GREETER:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if "clock-format=%a %-I:%M %p" not in text:
        errors.append("greeter clock-format not Mavericks-style in %s" % path)

pkgs = open(PKGS, encoding="utf-8").read()
if "xfce4-screensaver" not in pkgs:
    errors.append("xfce4-screensaver missing from packages.x86_64")

apple = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/panel/mv-apple.c"
)
if os.path.isfile(apple):
    if "xfce4-screensaver-command --lock" not in open(apple, encoding="utf-8").read():
        errors.append("mv-apple.c lock command drifted")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Ctrl+Alt+L → xfce4-screensaver-command --lock")
print("ok - greeter clock matches menu-bar format")
print("ok - xfce4-screensaver in ISO")
