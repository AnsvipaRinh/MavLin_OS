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

# Mavericks Dock ends with Trash (Plank trash docklet)
for path in PATHS:
    if not os.path.isdir(path):
        continue
    trash = os.path.join(path, "trash.dockitem")
    if not os.path.isfile(trash):
        errors.append("missing trash.dockitem in %s" % path)
        continue
    text = open(trash, encoding="utf-8").read()
    if "Launcher=docklet://trash" not in text:
        errors.append("trash.dockitem must use docklet://trash in %s" % path)

finder = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-finder.desktop"
)
if not os.path.isfile(finder):
    errors.append("mv-finder.desktop missing (Dock Finder pin would be dead)")

cfg_dir, skel_dir = PATHS[0], PATHS[1]
if os.path.isdir(cfg_dir) and os.path.isdir(skel_dir):
    cfg_files = sorted(os.listdir(cfg_dir))
    skel_files = sorted(os.listdir(skel_dir))
    if cfg_files != skel_files:
        errors.append(
            "launcher set drift: configs=%s skel=%s" % (cfg_files, skel_files)
        )
    for name in set(cfg_files) & set(skel_files):
        a = open(os.path.join(cfg_dir, name), "rb").read()
        b = open(os.path.join(skel_dir, name), "rb").read()
        if a != b:
            errors.append("content drift for %s (configs != airootfs)" % name)

pkgbuild = os.path.join(REPO, "packages/mavericks-theme/PKGBUILD")
if not os.path.isfile(pkgbuild):
    errors.append("mavericks-theme PKGBUILD missing")
else:
    pb = open(pkgbuild, encoding="utf-8").read()
    if "configs/desktop/plank/dock1/launchers" not in pb:
        errors.append("PKGBUILD does not source configs/desktop dock launchers")
    if "etc/skel/.config/plank/dock1/launchers" not in pb:
        errors.append("PKGBUILD does not install dock launchers into /etc/skel")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - default Dock launchers present in configs and skel (byte-identical)")
print("ok - pins: Finder, Launchpad, Firefox, Mail, System Settings, Terminal, Trash")
print("ok - mavericks-theme PKGBUILD ships pins to /etc/skel (pacman installs)")
