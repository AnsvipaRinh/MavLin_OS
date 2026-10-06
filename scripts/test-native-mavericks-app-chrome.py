#!/usr/bin/env python3
"""Static regression contract for native Mavericks window chrome."""
import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "packages", "mavericks-apps", "src", "mavericks-apps", "bin")
APPS = ("mv-airdrop", "mv-music", "mv-notes", "mv-photos", "mv-textedit")
failures = []
for app in APPS:
    with open(os.path.join(BIN, app), encoding="utf-8") as fh:
        source = fh.read()
    if "self.set_decorated(True)" not in source:
        failures.append("%s: missing native decoration" % app)
    if "Gtk.HeaderBar" in source or "set_titlebar(" in source:
        failures.append("%s: GTK CSD/HeaderBar remains" % app)
if failures:
    for failure in failures:
        print("FAIL - " + failure)
    raise SystemExit(1)
print("ok - all %d audited apps use native Mavericks window chrome" % len(APPS))
