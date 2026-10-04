#!/usr/bin/env python3
"""Headless contract tests for mv-quicklook runtime behavior."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-quicklook")
text = open(PATH, encoding="utf-8").read()

checks = [
    ("PDF paths use GLib filename-to-URI conversion",
     "GLib.filename_to_uri(path, None)" in text),
    ("Escape destroys the preview window",
     'if key in ("Escape", "q", "Q"):' in text and "            self.destroy()" in text),
    ("direct CLI enters GTK main loop",
     "    w = Preview(files)\n    Gtk.main()" in text),
]
failed = 0
for name, ok in checks:
    print(("ok - " if ok else "FAIL - ") + name)
    failed += not ok
sys.exit(1 if failed else 0)
