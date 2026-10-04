#!/usr/bin/env python3
"""Validate desktop + greeter wallpaper paths point at packaged asset."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(
    REPO, "packages/mavericks-theme/src/mavericks-theme/wallpapers/mavericks-desktop.png"
)
DESKTOP = [
    os.path.join(REPO, "configs/desktop/xfce/xfce4-desktop.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-desktop.xml",
    ),
]
GREETER = [
    os.path.join(REPO, "configs/desktop/lightdm/lightdm-gtk-greeter.conf"),
    os.path.join(
        REPO, "archiso-profile/releng/airootfs/etc/lightdm/lightdm-gtk-greeter.conf"
    ),
]
EXPECTED = "/usr/share/backgrounds/mavericks/mavericks-desktop.png"

errors = []
if not os.path.isfile(ASSET):
    errors.append("theme wallpaper asset missing: %s" % ASSET)

for path in DESKTOP + GREETER:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if EXPECTED not in text:
        errors.append("%s does not reference %s" % (path, EXPECTED))
    if "mavericks-wave.jpg" in text:
        errors.append("%s still references missing mavericks-wave.jpg" % path)

pkg = open(
    os.path.join(REPO, "packages/mavericks-theme/PKGBUILD"), encoding="utf-8"
).read()
if "/usr/share/backgrounds/mavericks" not in pkg:
    errors.append("PKGBUILD does not install backgrounds/mavericks")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - asset mavericks-desktop.png present")
print("ok - desktop + greeter use %s" % EXPECTED)
print("ok - no stale mavericks-wave.jpg refs")
