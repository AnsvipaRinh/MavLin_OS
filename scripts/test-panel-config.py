#!/usr/bin/env python3
"""Validate Mavericks menu-bar panel layout and mirror sync.

Gates the panel layout contract plus the two properties that make xfce4-panel
stop rewriting our own config on first boot:
  * plugin order  mv-apple | appmenu | separator(expand) | systray | clock |
    power-manager-plugin   (Apple + global menu left, status area right)
  * channel configver      (without it the panel runs its xfconf migration on
                            EVERY first boot and rewrites the skel file)
See scripts/test-menu-bar-p0.py for the deeper menu-bar contract (live clock
properties, Apple menu items, appmenu wiring, menu-bar styling).
"""
import os
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(REPO, "configs/desktop/xfce/xfce4-panel.xml")
AIROOTFS = os.path.join(
    REPO,
    "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
    "xfce-perchannel-xml/xfce4-panel.xml",
)
PATHS = [PANEL, AIROOTFS]

REQUIRED = [
    'value="mv-apple"',
    'value="appmenu"',
    'value="systray"',
    'value="clock"',
    'value="power-manager-plugin"',
    'name="size" type="uint" value="24"',
]

# xfce4-panel 4.20 writes configver=2; ship it so no migration runs.
REQUIRED_CHANNEL = {"configver": "2"}
# panel-1 geometry: 24px tall, TOP edge, full width, never auto-hidden.
# p=11 == SNAP_POSITION_N (top) in panel/panel-window.c enum _SnapPosition;
# p=8 is SNAP_POSITION_SW, i.e. the bottom edge — which is where the menu bar
# actually rendered until this contract pinned it.
REQUIRED_PANEL = {
    "position": "p=11;x=0;y=0",
    "size": "24",
    "length": "100",
    "autohide-behavior": "0",
}

errors = []
texts = []
for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    texts.append(text)
    for needle in REQUIRED:
        if needle not in text:
            errors.append("%s missing %s" % (path, needle))
    if text.count('name="plugin-') < 6:
        errors.append("%s expected 6 plugins" % path)

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("configs ↔ airootfs panel XML drift")

# Structural assertions (a text search would pass on a comment).
for path in PATHS:
    if not os.path.isfile(path):
        continue
    try:
        root = ET.fromstring(open(path, encoding="utf-8").read())
    except ET.ParseError as exc:
        errors.append("%s is not valid XML: %s" % (path, exc))
        continue
    for name, want in REQUIRED_CHANNEL.items():
        node = root.find("./property[@name='%s']" % name)
        if node is None:
            errors.append("%s missing channel property %s" % (path, name))
        elif node.get("value") != want:
            errors.append("%s %s=%s, expected %s"
                          % (path, name, node.get("value"), want))
    panel1 = root.find("./property[@name='panels']/property[@name='panel-1']")
    if panel1 is None:
        errors.append("%s missing panel-1" % path)
        continue
    for name, want in REQUIRED_PANEL.items():
        node = panel1.find("./property[@name='%s']" % name)
        if node is None:
            errors.append("%s panel-1 missing %s" % (path, name))
        elif node.get("value") != want:
            errors.append("%s panel-1 %s=%s, expected %s"
                          % (path, name, node.get("value"), want))
    ids = [v.get("value") for v in
           panel1.findall("./property[@name='plugin-ids']/value")]
    if ids != [str(i) for i in range(1, 7)]:
        errors.append("%s unexpected plugin ids: %s" % (path, ids))
    sep = None
    for p in root.findall("./property[@name='plugins']/property"):
        if p.get("name") == "plugin-3":
            sep = p
    expand = (sep.find("./property[@name='expand']")
              if sep is not None else None)
    if sep is None or sep.get("value") != "separator":
        errors.append("%s plugin-3 must be the expanding separator" % path)
    elif expand is None or expand.get("value") != "true":
        errors.append("%s plugin-3 expand must be true (status area right)"
                      % path)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

for path in PATHS:
    print("OK:", path)
print("OK: configs ↔ airootfs panel XML identical")
print("OK: mv-apple + appmenu + clock + power-manager layout")
print("OK: panel 24px, TOP edge (p=11), always visible, length 100%")
print("OK: configver=2 (no per-boot xfconf migration)")
