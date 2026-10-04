#!/usr/bin/env python3
"""Headless/static contract tests for Notification Center behavior."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notification-center")
src = open(path, encoding="utf-8").read()

checks = [
    ("valid executable shebang", src.startswith("#!/usr/bin/env python3\n")),
    ("notification rows are activatable", 'row.set_activatable(True)' in src),
    ("notification URL handler exists", "def on_notification_activate" in src),
    ("URL regex excludes whitespace correctly", 'r"https?://[^\\s<>]+"' in src),
    ("URL targets use xdg-open", '["xdg-open", target]' in src),
    ("desktop-entry hint uses gtk-launch", '["gtk-launch", desktop_id]' in src),
    ("desktop-entry hint is validated", 're.fullmatch(r"[A-Za-z0-9._-]+", desktop_id)' in src),
    ("desktop-entry hint uses argv rather than shell", 'subprocess.Popen(\\n                    ["gtk-launch", desktop_id]' in src),
    ("uses X11 monitor geometry", "get_monitor_workarea" in src),
    ("right-aligns panel", "workarea.x + workarea.width - width" in src),
    ("fills monitor workarea height", "self.resize(width, workarea.height)" in src),
    ("borderless panel", "set_decorated(False)" in src),
    ("not a taskbar application", "set_skip_taskbar_hint(True)" in src),
    ("DND property is created when absent", '"--create", "--type", "bool"' in src),
    ("opening center does not overwrite existing DND", 'if result.returncode == 0:\n            return result.stdout.strip() == "true"' in src),
    ("DND state is read back", '"/do-not-disturb"]' in src),
]
failed = 0
for name, ok in checks:
    print(("ok - " if ok else "FAIL - ") + name)
    failed += not ok
sys.exit(1 if failed else 0)
