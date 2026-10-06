#!/usr/bin/env python3
"""Headless contract tests for shared dialogs in the application menu."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/mavericks-apps/src/mavericks-apps/lib/mavericks_appmenu.py"


def source():
    return SOURCE.read_text(encoding="utf-8")


def tree():
    return ast.parse(source())


def test_shared_dialog_import():
    text = source()
    assert "from mv_dialogs import alert" in text
    assert "/usr/share/mavericks-apps" in text


def test_no_stock_message_dialog():
    assert "Gtk.MessageDialog" not in source()


def test_about_action_uses_shared_alert():
    calls = [
        node for node in ast.walk(tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "alert"
    ]
    assert calls, "Application menu About must use the shared Mavericks alert"


def test_about_keeps_app_name_and_native_identity():
    text = source()
    assert '"About %s" % app_name' in text
    assert 'secondary="MavLinOS native application"' in text


if __name__ == "__main__":
    tests = [obj for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
    print("test-mavericks-appmenu-dialogs: %d/%d passed" % (len(tests), len(tests)))
