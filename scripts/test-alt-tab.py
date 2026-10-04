#!/usr/bin/env python3
"""Validate Alt+Tab window cycle; Super+Tab remains Mission Control."""
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

errors = []
for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if (
        'name="&lt;Alt&gt;Tab" type="string" value="cycle_windows_key"'
        not in text
    ):
        errors.append("%s missing Alt+Tab cycle" % path)
    if (
        'name="&lt;Alt&gt;&lt;Shift&gt;Tab" type="string" value="cycle_reverse_windows_key"'
        not in text
    ):
        errors.append("%s missing Alt+Shift+Tab reverse" % path)
    if "Super&gt;Tab" in text:
        if "cycle_windows" in text.split("Super&gt;Tab")[1][:120]:
            errors.append("Super+Tab must not be cycle_windows")
    if "mv-mission-control" not in text and "mission-control" not in text:
        errors.append("%s Super+Tab Mission Control missing" % path)

a = open(os.path.join(REPO, "configs/desktop/xfce/xfwm4.xml"), encoding="utf-8").read()
b = open(
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfwm4.xml",
    ),
    encoding="utf-8",
).read()
if a != b:
    errors.append("xfwm4 mirrors still differ")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Alt+Tab → cycle_windows_key")
print("ok - Alt+Shift+Tab → reverse")
print("ok - Super+Tab stays Mission Control")
print("ok - xfwm4 mirrors identical")
