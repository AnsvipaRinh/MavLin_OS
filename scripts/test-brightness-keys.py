#!/usr/bin/env python3
"""Validate mv-brightness helper and XF86MonBrightness key bindings."""
import os
import py_compile
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-brightness"
)
MAKEFILE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)
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

errors = []
if not os.path.isfile(SCRIPT):
    errors.append("mv-brightness script missing")
else:
    try:
        py_compile.compile(SCRIPT, doraise=True)
    except py_compile.PyCompileError as exc:
        errors.append("mv-brightness syntax: %s" % exc)

if not os.path.isfile(MAKEFILE) or "mv-brightness" not in open(MAKEFILE, encoding="utf-8").read():
    errors.append("Makefile does not install mv-brightness")

for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if 'name="XF86MonBrightnessUp" type="string" value="mv-brightness up"' not in text:
        errors.append("XF86MonBrightnessUp not bound in %s" % path)
    if 'name="XF86MonBrightnessDown" type="string" value="mv-brightness down"' not in text:
        errors.append("XF86MonBrightnessDown not bound in %s" % path)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - mv-brightness helper present and compiles")
print("ok - Makefile installs mv-brightness")
print("ok - XF86MonBrightnessUp/Down bound to mv-brightness")
