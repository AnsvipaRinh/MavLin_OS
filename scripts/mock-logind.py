#!/usr/bin/env python3
"""mock-logind — fake org.freedesktop.login1 service for headless tests.

Serves Can*/Suspend/Reboot/PowerOff on a private bus. Capability values are
configured via environment:
  MOCK_LOGIND_CAN_SUSPEND  = yes|no|challenge   (default yes)
  MOCK_LOGIND_CAN_REBOOT    = yes|no|challenge   (default yes)
  MOCK_LOGIND_CAN_POWEROFF  = yes|no|challenge   (default yes)
  MOCK_LOGIND_FAIL_ACTIONS = 1                  → action calls raise an error
  MOCK_LOGIND_CALLS_FILE   = path               → append received action calls

Prints READY once the name is owned, serves until terminated.
Read-only: no real power actions are performed.
License: GPL-2.0-or-later."""
import os
import sys

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

BUS_NAME = "org.freedesktop.login1"
CALLS_FILE = os.environ.get("MOCK_LOGIND_CALLS_FILE", "")
FAIL_ACTIONS = os.environ.get("MOCK_LOGIND_FAIL_ACTIONS", "") == "1"

CAPS = {
    "CanSuspend": os.environ.get("MOCK_LOGIND_CAN_SUSPEND", "yes"),
    "CanReboot": os.environ.get("MOCK_LOGIND_CAN_REBOOT", "yes"),
    "CanPowerOff": os.environ.get("MOCK_LOGIND_CAN_POWEROFF", "yes"),
}

MANAGER_IFACE = """
  <node>
  <interface name="org.freedesktop.login1.Manager">
    <method name="CanSuspend">
      <arg type="s" direction="out"/>
    </method>
    <method name="CanReboot">
      <arg type="s" direction="out"/>
    </method>
    <method name="CanPowerOff">
      <arg type="s" direction="out"/>
    </method>
    <method name="Suspend">
      <arg type="b" direction="in"/>
    </method>
    <method name="Reboot">
      <arg type="b" direction="in"/>
    </method>
    <method name="PowerOff">
      <arg type="b" direction="in"/>
    </method>
  </interface>
  </node>
"""


def record(action):
    if CALLS_FILE:
        with open(CALLS_FILE, "a") as fh:
            fh.write(action + "\n")


def on_method_call(_conn, _sender, _path, _iface, method, params, invocation):
    if method in CAPS:
        invocation.return_value(GLib.Variant("(s)", (CAPS[method],)))
        return
    if method in ("Suspend", "Reboot", "PowerOff"):
        if FAIL_ACTIONS:
            invocation.return_error_literal(
                Gio.dbus_error_quark(), Gio.DBusError.FAILED,
                "mock-logind: action disabled for testing")
            return
        record(method)
        invocation.return_value(None)
        return
    invocation.return_error_literal(
        Gio.dbus_error_quark(), Gio.DBusError.UNKNOWN_METHOD,
        "no such method: %s" % method)


def main():
    if len(sys.argv) < 2:
        print("usage: mock-logind.py <bus-address>", file=sys.stderr)
        return 2
    addr = sys.argv[1]
    flags = (Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
             Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)
    conn = Gio.DBusConnection.new_for_address_sync(addr, flags, None, None)
    Gio.bus_own_name_on_connection(
        conn, BUS_NAME, Gio.BusNameOwnerFlags.NONE, None, None)
    conn.register_object(
        "/org/freedesktop/login1",
        Gio.DBusNodeInfo.new_for_xml(MANAGER_IFACE).lookup_interface(
            "org.freedesktop.login1.Manager"),
        on_method_call, None, None)
    print("READY", flush=True)
    GLib.MainLoop().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
