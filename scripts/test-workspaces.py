#!/usr/bin/env python3
"""Validate 4 Spaces + Super+1..4 workspace switching."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XFW = [
    os.path.join(REPO, "configs/desktop/xfce/xfwm4.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfwm4.xml",
    ),
]
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
for path in XFW:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if 'name="workspace_count" type="int" value="4"' not in text:
        errors.append("%s must set workspace_count=4" % path)

for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    for i in range(1, 5):
        needle = (
            'name="&lt;Super&gt;%d" type="string" value="workspace_%d_key"' % (i, i)
        )
        if needle not in text:
            errors.append("%s missing Super+%d" % (path, i))

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - workspace_count=4")
print("ok - Super+1..4 → workspace_N_key")
