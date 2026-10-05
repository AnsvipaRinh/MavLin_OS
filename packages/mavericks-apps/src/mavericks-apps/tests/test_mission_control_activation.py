#!/usr/bin/env python3
"""Headless tests for Mission Control EWMH activation helpers."""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import mission_control as mc


def test_parse_window_id():
    assert mc._parse_window_id("0x1234") == 0x1234
    assert mc._parse_window_id("4660") == 4660
    assert mc._parse_window_id(4660) == 4660
    assert mc._parse_window_id("not-a-window") is None
    assert mc._parse_window_id(None) is None
    print("PASS: test_parse_window_id")


def test_switch_workspace_fallback():
    mc._XLIB_AVAILABLE = False
    completed = MagicMock(returncode=0)
    with patch.object(mc.subprocess, "run", return_value=completed) as run:
        assert mc.switch_workspace(2) is True
        run.assert_called_once()
        assert run.call_args.args[0] == ["wmctrl", "-s", "2"]

    assert mc.switch_workspace(-1) is False
    assert mc.switch_workspace("bad") is False
    print("PASS: test_switch_workspace_fallback")


def test_activate_window_fallback():
    mc._XLIB_AVAILABLE = False
    completed = MagicMock(returncode=0)
    with patch.object(mc.subprocess, "run", return_value=completed) as run:
        assert mc.activate_window("0x1234") is True
        run.assert_called_once()
        assert run.call_args.args[0] == ["wmctrl", "-i", "-a", "0x1234"]

    with patch.object(mc.subprocess, "run", return_value=MagicMock(returncode=1)):
        assert mc.activate_window("0x1234") is False

    assert mc.activate_window("bad") is False
    print("PASS: test_activate_window_fallback")


def test_root_client_message_shape():
    """Verify the EWMH helper sends a 32-bit ClientMessage and flushes it."""
    mc._XLIB_AVAILABLE = True
    disp = MagicMock()
    root = disp.screen.return_value.root
    atom = 42

    with patch.object(mc, "_get_atom", return_value=atom),          patch("Xlib.protocol.event.ClientMessage") as client_message:
        client_message.return_value = "event"
        assert mc._send_root_client_message(disp, "_NET_CURRENT_DESKTOP", [3, 0, 2, 0, 0])
        client_message.assert_called_once_with(
            window=root,
            client_type=atom,
            data=(32, [3, 0, 2, 0, 0]),
        )
        root.send_event.assert_called_once()
        disp.flush.assert_called_once()

    print("PASS: test_root_client_message_shape")


def test_move_window_to_workspace_fallback():
    mc._XLIB_AVAILABLE = False
    completed = MagicMock(returncode=0)
    with patch.object(mc.subprocess, "run", return_value=completed) as run:
        assert mc.move_window_to_workspace("0x1234", 2) is True
        run.assert_called_once()
        assert run.call_args.args[0] == ["wmctrl", "-i", "-r", "0x1234", "-t", "2"]

    assert mc.move_window_to_workspace(-1, 2) is False
    assert mc.move_window_to_workspace("bad", 2) is False
    assert mc.move_window_to_workspace("0x1234", -1) is False
    print("PASS: test_move_window_to_workspace_fallback")


def test_move_window_client_message_shape():
    mc._XLIB_AVAILABLE = True
    disp = MagicMock()
    root = disp.screen.return_value.root
    target = disp.create_resource_object.return_value
    atom = 77

    with patch.object(mc, "_get_atom", return_value=atom),          patch("Xlib.protocol.event.ClientMessage") as client_message:
        client_message.return_value = "event"
        assert mc._move_window_to_workspace_xlib(disp, "0x1234", 3)
        client_message.assert_called_once_with(
            window=target,
            client_type=atom,
            data=(32, [3, 2, 0, 0, 0]),
        )
        root.send_event.assert_called_once()
        disp.flush.assert_called_once()

    print("PASS: test_move_window_client_message_shape")


def test_remove_workspace_rejects_invalid_targets():
    with patch.object(mc, "get_workspaces", return_value={"count": 3, "current": 1}):
        assert mc.remove_workspace(0) is False
        assert mc.remove_workspace(1) is False
        assert mc.remove_workspace(3) is False
    print("PASS: test_remove_workspace_rejects_invalid_targets")


def test_remove_workspace_shifts_windows_then_reduces_count():
    windows = [
        {"win_id": "0x20", "desktop": 1},
        {"win_id": "0x30", "desktop": 2},
        {"win_id": "0x40", "desktop": 3},
    ]
    with patch.object(mc, "get_workspaces", return_value={"count": 4, "current": 0}), \
         patch.object(mc, "enumerate_windows", return_value=windows), \
         patch.object(mc, "move_window_to_workspace", return_value=True) as move, \
         patch.object(mc, "set_workspace_count", return_value=True) as set_count:
        assert mc.remove_workspace(1) is True
        assert [call.args for call in move.call_args_list] == [("0x30", 1), ("0x40", 2)]
        set_count.assert_called_once_with(3)
    print("PASS: test_remove_workspace_shifts_windows_then_reduces_count")


def test_set_workspace_count_fallback():
    mc._XLIB_AVAILABLE = False
    completed = MagicMock(returncode=0)
    with patch.object(mc.subprocess, "run", return_value=completed) as run:
        assert mc.set_workspace_count(4) is True
        run.assert_called_once()
        assert run.call_args.args[0] == ["wmctrl", "-n", "4"]

    assert mc.set_workspace_count(0) is False
    assert mc.set_workspace_count(17) is False
    assert mc.set_workspace_count("bad") is False
    print("PASS: test_set_workspace_count_fallback")


def test_activate_window_invalid_id_does_not_connect():
    with patch.object(mc, "_get_display") as get_display:
        assert mc._activate_window_xlib("not-an-id") is False
        get_display.assert_not_called()
    print("PASS: test_activate_window_invalid_id_does_not_connect")


if __name__ == "__main__":
    tests = [
        test_parse_window_id,
        test_switch_workspace_fallback,
        test_activate_window_fallback,
        test_root_client_message_shape,
        test_move_window_to_workspace_fallback,
        test_move_window_client_message_shape,
        test_set_workspace_count_fallback,
        test_remove_workspace_rejects_invalid_targets,
        test_remove_workspace_shifts_windows_then_reduces_count,
        test_activate_window_invalid_id_does_not_connect,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"FAIL: {test.__name__}: {type(exc).__name__}: {exc}")
            failed += 1

    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    raise SystemExit(1 if failed else 0)
