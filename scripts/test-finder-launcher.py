#!/usr/bin/env python3
"""Validate Finder launch paths point at the column-view Finder UI."""
import configparser
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-finder.desktop"
)
SHORTCUT_PATHS = [
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
MIMEAPPS_PATHS = [
    os.path.join(REPO, "configs/desktop/mimeapps.list"),
    os.path.join(
        REPO, "archiso-profile/releng/airootfs/etc/skel/.config/mimeapps.list"
    ),
]

cfg = configparser.ConfigParser(interpolation=None, strict=False)
cfg.optionxform = str
with open(DESKTOP, encoding="utf-8") as fh:
    cfg.read_file(fh)

entry = cfg["Desktop Entry"]
errors = []

if entry.get("Type") != "Application":
    errors.append("Finder desktop entry must be an Application")
if entry.get("Name") != "Finder":
    errors.append("Finder desktop entry must be named Finder")

exec_line = entry.get("Exec", "")
if not exec_line.startswith("mv-finder-columns"):
    errors.append(
        "Finder desktop entry must launch mv-finder-columns, got: %s" % exec_line
    )
if exec_line.split() and exec_line.split()[0] == "thunar":
    errors.append("Finder desktop entry must not launch plain Thunar")

mime = entry.get("MimeType", "")
for need in ("inode/directory", "inode/mount-point"):
    if need not in mime:
        errors.append("Finder desktop MimeType must include %s" % need)

target = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns"
)
if not os.path.isfile(target):
    errors.append("mv-finder-columns implementation is missing")

needle_ok = 'name="&lt;Super&gt;&lt;Shift&gt;f" type="string" value="mv-finder-columns"'
needle_bad = 'name="&lt;Super&gt;&lt;Shift&gt;f" type="string" value="thunar"'
needle_e = 'name="&lt;Super&gt;e" type="string" value="mv-finder-columns"'
for path in SHORTCUT_PATHS:
    if not os.path.isfile(path):
        errors.append("keyboard shortcuts file missing: %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if needle_bad in text:
        errors.append("Super+Shift+F still launches plain thunar in %s" % path)
    if needle_ok not in text:
        errors.append(
            "Super+Shift+F must launch mv-finder-columns in %s" % path
        )
    if needle_e not in text:
        errors.append("Super+E must launch mv-finder-columns in %s" % path)

for path in MIMEAPPS_PATHS:
    if not os.path.isfile(path):
        errors.append("mimeapps.list missing: %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if "inode/directory=mv-finder.desktop" not in text:
        errors.append(
            "mimeapps.list must default inode/directory to mv-finder.desktop (%s)"
            % path
        )
    if "inode/directory=thunar.desktop" in text:
        errors.append("mimeapps.list must not prefer thunar.desktop for directories")

if errors:
    for error in errors:
        print("FAIL - %s" % error)
    sys.exit(1)

print("ok - Finder desktop entry launches mv-finder-columns")
print("ok - Finder desktop MimeType covers directories")
print("ok - mv-finder-columns implementation exists")
print("ok - Super+Shift+F keyboard shortcut launches mv-finder-columns")
print("ok - mimeapps.list defaults directories to Finder")
print("ok - Super+E keyboard shortcut launches mv-finder-columns")
