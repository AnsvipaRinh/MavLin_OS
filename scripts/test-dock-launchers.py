#!/usr/bin/env python3
"""Validate default Plank Dock pinned launchers are shipped and consistent.

Scope: WHICH launchers are pinned and whether every copy agrees.
HOW the pinned preferences actually reach plank is a different question and
is covered by scripts/test-dock-plank.py (+ its GUI smoke) — plank 0.11 reads
GSettings, not the dock1/settings INI next to these pins.

Claim: Grok — trash.dockitem (docklet://trash) was printed as present but
never asserted; a missing Trash pin is exactly the Mavericks Dock gap listed
in NEEDS_HARDWARE_TEST.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/desktop/plank/dock1/launchers"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/launchers",
    ),
]
REQUIRED = {
    "finder.dockitem": "mv-finder.desktop",
    "launchpad.dockitem": "mv-launchpad.desktop",
    "mission-control.dockitem": "mv-mission-control.desktop",
    "firefox.dockitem": "firefox.desktop",
    "mail.dockitem": "mv-mail.desktop",
    "system-settings.dockitem": "mv-system-settings.desktop",
    "terminal.dockitem": "xfce4-terminal.desktop",
}
# Trash is a plank docklet, not a .desktop pin.
TRASH_ITEM = "trash.dockitem"
TRASH_LAUNCHER = "Launcher=docklet://trash"

errors = []
for path in PATHS:
    if not os.path.isdir(path):
        errors.append("dock launchers dir missing: %s" % path)
        continue
    for name, desktop in REQUIRED.items():
        fpath = os.path.join(path, name)
        if not os.path.isfile(fpath):
            errors.append("missing %s in %s" % (name, path))
            continue
        text = open(fpath, encoding="utf-8").read()
        if "Launcher=file:///usr/share/applications/%s" % desktop not in text:
            errors.append(
                "%s must point at %s (in %s)" % (name, desktop, path)
            )
    trash_path = os.path.join(path, TRASH_ITEM)
    if not os.path.isfile(trash_path):
        errors.append("missing %s in %s" % (TRASH_ITEM, path))
    else:
        trash_text = open(trash_path, encoding="utf-8").read()
        if TRASH_LAUNCHER not in trash_text:
            errors.append(
                "%s must contain %s (in %s)" % (TRASH_ITEM, TRASH_LAUNCHER, path)
            )

finder = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-finder.desktop"
)
if not os.path.isfile(finder):
    errors.append("mv-finder.desktop missing (Dock Finder pin would be dead)")

# Every mv-* pin must resolve to a desktop file mavericks-apps installs,
# otherwise plank silently drops the pin (it did exactly that for a missing
# target during the Dock P0 audit).
desktop_dir = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop"
)
for name, desktop in REQUIRED.items():
    if not desktop.startswith("mv-"):
        continue
    if not os.path.isfile(os.path.join(desktop_dir, desktop)):
        errors.append("%s pins %s, which mavericks-apps does not install"
                      % (name, desktop))

mission_control = os.path.join(desktop_dir, "mv-mission-control.desktop")
if not os.path.isfile(mission_control):
    errors.append("mv-mission-control.desktop missing (Dock Mission Control "
                  "pin would be dead)")
else:
    body = open(mission_control, encoding="utf-8").read()
    if "Exec=mv-mission-control --native" not in body:
        errors.append("mv-mission-control.desktop must open the window "
                      "overview from the Dock (Exec=mv-mission-control "
                      "--native)")
    if "\nIcon=" not in body:
        errors.append("mv-mission-control.desktop must carry an icon")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - default Dock launchers present in configs and skel")
print("ok - pins: Finder, Launchpad, Mission Control, Firefox, Mail, "
      "System Settings, Terminal")
print("ok - Trash docklet (docklet://trash) present in configs and skel")
