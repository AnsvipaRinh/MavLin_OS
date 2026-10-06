#!/usr/bin/env python3
"""Validate mv-desktop-* scripts exist and are executable."""
import os
import sys
import stat

# Bootstrap host-display guard (windowless suite)
try:
    from mv_gui_iso import arm_guard
    arm_guard()
except ImportError:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = [
    "mv-change-wallpaper",
    "mv-desktop-cleanup",
    "mv-desktop-sort",
    "mv-desktop-paste",
]

errors = []
for script in SCRIPTS:
    path = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin", script)
    if not os.path.isfile(path):
        errors.append("missing script: %s" % path)
    else:
        mode = os.stat(path).st_mode
        if not (mode & stat.S_IXUSR):
            errors.append("not executable: %s" % path)

# Check menu.xml
menu_path = os.path.join(REPO, "configs/desktop/xfce/menu.xml")
if not os.path.isfile(menu_path):
    errors.append("missing menu.xml: %s" % menu_path)
else:
    try:
        import xml.etree.ElementTree as ET
        ET.parse(menu_path)
    except ET.ParseError as e:
        errors.append("menu.xml invalid XML: %s" % e)
    else:
        menu_text = open(menu_path, encoding="utf-8").read()
        if "<item name=\"Show Desktop\">" not in menu_text:
            errors.append("menu.xml missing Show Desktop item")
        if "<command>wmctrl -k on</command>" not in menu_text:
            errors.append("Show Desktop must use wmctrl -k on")
        if "xfce4-popup-applicationsmenu -p" in menu_text:
            errors.append("Show Desktop must not launch the applications menu")

# Check xfce4-desktop.xml has icon grid settings
desktop_path = os.path.join(REPO, "configs/desktop/xfce/xfce4-desktop.xml")
if os.path.isfile(desktop_path):
    text = open(desktop_path, encoding="utf-8").read()
    for needle in [
        'name="sort-column"',
        'name="sort-order"',
        'name="icon-size"',
    ]:
        if needle not in text:
            errors.append("xfce4-desktop.xml missing: %s" % needle)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - all desktop menu scripts exist and are executable")
print("ok - menu.xml valid XML")
print("ok - xfce4-desktop.xml has icon grid settings")