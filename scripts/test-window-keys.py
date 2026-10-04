#!/usr/bin/env python3
"""Validate Mavericks-like window management Super shortcuts are wired."""
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
REQUIRED = {
    "&lt;Super&gt;q": "mv-quit-app",
    "&lt;Super&gt;m": "mv-minimize-window",
    "&lt;Super&gt;h": "mv-hide-app",
    "&lt;Super&gt;w": "mv-close-window",
}
SCRIPTS = [
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-quit-app",
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-minimize-window",
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-hide-app",
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-close-window",
]

errors = []
for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    for key, cmd in REQUIRED.items():
        needle = 'name="%s" type="string" value="%s"' % (key, cmd)
        if needle not in text:
            errors.append("%s must bind to %s in %s" % (key, cmd, path))

for rel in SCRIPTS:
    if not os.path.isfile(os.path.join(REPO, rel)):
        errors.append("script missing: %s" % rel)

mk = open(
    os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"),
    encoding="utf-8",
).read()
for name in ("mv-quit-app", "mv-minimize-window", "mv-hide-app", "mv-close-window"):
    if name not in mk:
        errors.append("Makefile does not install %s" % name)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Q/M/H/W window shortcuts wired")
print("ok - mv-quit-app / minimize / hide / close scripts present")
print("ok - Makefile installs window helpers")
