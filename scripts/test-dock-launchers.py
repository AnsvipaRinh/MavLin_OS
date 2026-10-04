#!/usr/bin/env python3
"""Validate default Plank Dock pinned launchers are shipped and consistent."""
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
    "firefox.dockitem": "firefox.desktop",
    "mail.dockitem": "mv-mail.desktop",
    "system-settings.dockitem": "mv-system-settings.desktop",
    "terminal.dockitem": "xfce4-terminal.desktop",
}

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

finder = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-finder.desktop"
)
if not os.path.isfile(finder):
    errors.append("mv-finder.desktop missing (Dock Finder pin would be dead)")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - default Dock launchers present in configs and skel")
print("ok - pins: Finder, Launchpad, Firefox, Mail, System Settings, Terminal")
