#!/usr/bin/env python3
"""Headless regression checks for native application-menu actions."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/mavericks-apps/src/mavericks-apps/lib/mavericks_appmenu.py"
TEXT = SOURCE.read_text(encoding="utf-8")
TREE = ast.parse(TEXT)

assert 'add_action("zoom", zoom_window)' in TEXT
assert 'add_action("help", lambda: _show_help(get_window(), app_name))' in TEXT
assert 'help_menu.append("MavLinOS Help", "app.help")' in TEXT
assert 'help_menu.append("About %s" % app_name, "app.about")' not in TEXT

names = {
    node.args[0].value
    for node in ast.walk(TREE)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "add_action"
    and node.args
    and isinstance(node.args[0], ast.Constant)
}
assert "zoom" in names
assert "help" in names

print("test-mavericks-appmenu-actions: passed")
