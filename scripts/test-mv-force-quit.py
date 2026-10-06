#!/usr/bin/env python3
"""Headless contract tests for the Mavericks Force Quit dialog."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/mavericks-apps/src/mavericks-apps/bin/mv-force-quit"


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


def test_error_path_uses_shared_alert():
    calls = [
        node for node in ast.walk(tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "alert"
    ]
    assert calls, "Force Quit must use the shared Mavericks alert"


def test_error_alert_is_error_type():
    text = source()
    assert "msg_type=Gtk.MessageType.ERROR" in text
    assert "Could not force quit process %d" in text


def test_force_quit_still_uses_sigkill():
    assert "os.kill(pid, signal.SIGKILL)" in source()


def test_dialog_keeps_cancel_and_force_quit_actions():
    text = source()
    assert 'self.add_button("Cancel", Gtk.ResponseType.CANCEL)' in text
    assert 'self.add_button("Force Quit", Gtk.ResponseType.OK)' in text


def main():
    tests = [obj for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
    print("test-mv-force-quit: %d/%d passed" % (len(tests), len(tests)))


if __name__ == "__main__":
    main()
