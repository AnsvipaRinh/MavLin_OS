#!/usr/bin/env python3
"""Validate mavericks_appmenu.py is shipped to /usr/share/mavericks-apps via Makefile."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)
MODULE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/lib/mavericks_appmenu.py"
)
SAMPLE_APPS = [
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-about",
    "packages/mavericks-apps/src/mavericks-apps/bin/mv-settings",
]

errors = []
if not os.path.isfile(MODULE):
    errors.append("lib/mavericks_appmenu.py missing")
else:
    text = open(MODULE, encoding="utf-8").read()
    if "install_application_menu" not in text and "run_application" not in text:
        errors.append("module lacks expected API")

if not os.path.isfile(MAKEFILE):
    errors.append("Makefile missing")
else:
    mk = open(MAKEFILE, encoding="utf-8").read()
    if "lib/mavericks_appmenu.py" not in mk:
        errors.append("Makefile does not install lib/mavericks_appmenu.py")
    if "share/mavericks-apps/mavericks_appmenu.py" not in mk:
        errors.append("Makefile must install to share/mavericks-apps/mavericks_appmenu.py")

for rel in SAMPLE_APPS:
    path = os.path.join(REPO, rel)
    if not os.path.isfile(path):
        errors.append("missing %s" % rel)
        continue
    text = open(path, encoding="utf-8").read()
    if "/usr/share/mavericks-apps" not in text:
        errors.append("%s does not set sys.path to /usr/share/mavericks-apps" % rel)
    if "mavericks_appmenu" not in text:
        errors.append("%s does not import mavericks_appmenu" % rel)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - mavericks_appmenu.py present")
print("ok - Makefile installs to /usr/share/mavericks-apps/")
print("ok - sample apps import via that path")
