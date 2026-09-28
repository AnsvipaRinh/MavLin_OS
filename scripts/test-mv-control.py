#!/usr/bin/env python3
"""Headless tests for mv-control.

Pure-logic / scheduling section (no GTK widgets, no display required):
- pack_row dispatch: Gtk.ListBox.add vs Box.pack_start
- Wi-Fi refresh scheduling constants (fallback >= 30s, debounce, min interval)
- NM signal debounce: bursts collapse to one pending refresh
- min-interval: refresh skipped when called too soon after the last one
- refresh_all no longer polls the Wi-Fi list (S-01) but still polls BT (S-06)
- NM D-Bus signal subscription covers the expected signal set
- destroy unsubscribes signals and removes pending timers

GUI smoke (display only, skipped headless):
- construction, Wi-Fi/BT sections, refresh button, connect flow

Usage: python3 scripts/test-mv-control.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import time
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-control")

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_control", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_control", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class FakeListBox:
    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)


class FakeBox:
    def __init__(self):
        self.packed = []

    def pack_start(self, *args):
        self.packed.append(args)


def bare_window(m):
    w = m.ControlCenter.__new__(m.ControlCenter)
    w._nm_bus = None
    w._wifi_signal_subs = []
    w._wifi_fallback_id = None
    w._wifi_pending = None
    w._wifi_last_refresh = 0.0
    return w


def test_pure(m):
    with mock.patch.object(m.Gtk, "ListBox", FakeListBox):
        lb = FakeListBox()
        m.pack_row(lb, "row")
        check("pack_row listbox uses add", lb.added == ["row"])
    bx = FakeBox()
    m.pack_row(bx, "row")
    check("pack_row box uses pack_start", len(bx.packed) == 1)

    check("wifi fallback poll >= 30s", m.WIFI_FALLBACK_POLL_S >= 30,
          m.WIFI_FALLBACK_POLL_S)
    check("wifi debounce >= 1s", m.WIFI_REFRESH_DEBOUNCE_S >= 1,
          m.WIFI_REFRESH_DEBOUNCE_S)
    check("wifi min interval >= 2s", m.WIFI_REFRESH_MIN_INTERVAL_S >= 2,
          m.WIFI_REFRESH_MIN_INTERVAL_S)

    w = bare_window(m)
    w.refresh_wifi_list = mock.Mock()
    w._on_nm_wifi_signal()
    check("nm signal schedules debounce", w._wifi_pending is not None)
    pending = w._wifi_pending
    w._on_nm_wifi_signal()
    w._on_nm_wifi_signal()
    check("signal burst collapses to one refresh",
          w._wifi_pending == pending)

    w._wifi_signal_refresh()
    check("debounced refresh fires", w.refresh_wifi_list.call_count == 1)
    check("pending cleared after fire", w._wifi_pending is None)

    w._wifi_last_refresh = time.monotonic()
    w._wifi_signal_refresh()
    check("min interval suppresses rapid refresh",
          w.refresh_wifi_list.call_count == 1)
    w._wifi_last_refresh = 0.0
    w._wifi_signal_refresh()
    check("refresh fires after min interval",
          w.refresh_wifi_list.call_count == 2)

    w2 = bare_window(m)
    w2.refresh_wifi_list = mock.Mock()
    w2._wifi_fallback_tick()
    check("fallback tick refreshes list", w2.refresh_wifi_list.call_count == 1)

    w3 = bare_window(m)
    w3.wifi_switch = mock.Mock()
    w3.bt_switch = mock.Mock()
    w3.dnd_switch = mock.Mock()
    w3.refresh_wifi_list = mock.Mock()
    w3.refresh_bt_list = mock.Mock()
    w3.refresh_output_devices = mock.Mock()
    w3.refresh_power_mode = mock.Mock()
    w3.get_wifi_enabled = lambda: True
    w3.get_bt_enabled = lambda: False
    w3.get_dnd = lambda: False
    w3.refresh_all()
    check("refresh_all skips wifi list (S-01)",
          w3.refresh_wifi_list.call_count == 0)
    check("refresh_all skips BT list when BT off",
          w3.refresh_bt_list.call_count == 0)
    check("refresh_all skips output devices",
          w3.refresh_output_devices.call_count == 0)
    check("refresh_all keeps wifi switch state",
          w3.wifi_switch.set_active.called)

    w3b = bare_window(m)
    w3b.bt_switch = mock.Mock()
    w3b.refresh_bt_list = mock.Mock()
    w3b.get_bt_enabled = lambda: True
    w3b.refresh_all()
    check("refresh_all polls BT list when BT on",
          w3b.refresh_bt_list.call_count == 1)

    check("refresh_all interval >= 30s", m.REFRESH_ALL_INTERVAL_S >= 30,
          m.REFRESH_ALL_INTERVAL_S)

    w4 = bare_window(m)
    bus = mock.Mock()
    bus.signal_subscribe.side_effect = lambda *a: len(
        w4._wifi_signal_subs) + 1
    with mock.patch.object(m.Gio, "bus_get_sync", return_value=bus):
        w4._subscribe_nm_wifi_signals()
    check("nm bus resolved", w4._nm_bus is bus)
    ifaces = {c[0][1] for c in bus.signal_subscribe.call_args_list}
    members = {c[0][2] for c in bus.signal_subscribe.call_args_list}
    check("subscribes wireless PropertiesChanged",
          "org.freedesktop.NetworkManager.Device.Wireless" in ifaces
          and "PropertiesChanged" in members)
    check("subscribes AccessPoint add/remove",
          "AccessPointAdded" in members and "AccessPointRemoved" in members)
    check("subscribes device add/remove",
          "DeviceAdded" in members and "DeviceRemoved" in members)
    check("subscribes AP PropertiesChanged",
          "org.freedesktop.NetworkManager.AccessPoint" in ifaces)

    w5 = bare_window(m)
    w5._nm_bus = mock.Mock()
    w5._wifi_signal_subs = [11, 12]
    w5._wifi_fallback_id = 99
    w5._wifi_pending = 50
    w5._refresh_all_id = 77
    with mock.patch.object(m.GLib, "source_remove") as sr:
        w5.on_destroy(None)
    check("destroy unsubscribes nm signals",
          w5._nm_bus.signal_unsubscribe.call_count == 2)
    removed = {c[0][0] for c in sr.call_args_list}
    check("destroy removes fallback + pending + refresh_all timers",
          {99, 50, 77} <= removed, removed)

    w6 = bare_window(m)
    fake_bus = mock.Mock()
    fake_msg = mock.Mock()
    fake_bus.send_message_with_reply_sync.return_value = fake_msg
    fake_msg.get_body.return_value = {
        "/org/bluez/hci0": {"org.bluez.Adapter1": {}},
        "/org/bluez/hci0/dev_11": {"org.bluez.Device1": {"Name": "Test"}},
    }
    with mock.patch.object(m.Gio, "bus_get_sync", return_value=fake_bus):
        result = w6._bluez_get_objects()
    check("_bluez_get_objects returns body", result is not None)
    check("_bluez_get_objects has adapter",
          any("org.bluez.Adapter1" in v for v in result.values()))
    w6b = bare_window(m)
    with mock.patch.object(m.Gio, "bus_get_sync", side_effect=Exception("no bus")):
        check("_bluez_get_objects handles error",
              w6b._bluez_get_objects() is None)


def test_gui_smoke(m):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gtk
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        return
    w = m.ControlCenter()
    try:
        for _ in range(5):
            Gtk.main_iteration_do(False)
        check("gui constructs", True)
        check("gui wifi listbox present", w.wifi_listbox is not None)
        check("gui fallback timer armed", w._wifi_fallback_id is not None)
        w.refresh_wifi_list()
        check("gui manual refresh works", True)
    finally:
        try:
            w.destroy()
        except Exception:
            pass


def main():
    m = load_app()
    test_pure(m)
    test_gui_smoke(m)
    print("passed: %d, failed: %d" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
