#!/usr/bin/env python3
"""mock-udisks2 — fake org.freedesktop.UDisks2 service for headless tests.

Serves three fake devices (internal SATA with mounted ext4, external
unmounted USB stick, Apple NVMe with HFS+ partition) on a private bus.
Read-only: no real disks involved.

Usage: mock-udisks2.py <bus-address>
Prints READY once the name is owned, serves until terminated.
License: GPL-2.0-or-later."""
import os
import sys
import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

UDISKS_BUS = "org.freedesktop.UDisks2"
BLOCKS_PATH = "/org/freedesktop/UDisks2/block_devices"
MOCK_CALLS = []

PROPS_IFACE = """
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="Set">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="in"/>
    </method>
    <signal name="PropertiesChanged">
      <arg type="s" direction="out"/>
      <arg type="a{sv}" direction="out"/>
      <arg type="as" direction="out"/>
    </signal>
  </interface>
"""

DRIVE_IFACE = """
  <interface name="org.freedesktop.UDisks2.Drive">
    <property name="Vendor" type="s" access="read"/>
    <property name="Model" type="s" access="read"/>
    <property name="Serial" type="s" access="read"/>
    <property name="Size" type="t" access="read"/>
    <property name="ConnectionBus" type="s" access="read"/>
    <property name="Ejectable" type="b" access="read"/>
    <property name="Removable" type="b" access="read"/>
    <property name="Media" type="s" access="read"/>
    <method name="Eject">
      <arg type="a{sv}" direction="in"/>
    </method>
  </interface>
"""

DRIVE_ATA_IFACE = """
  <interface name="org.freedesktop.UDisks2.Drive.Ata">
    <property name="SmartUpdated" type="t" access="read"/>
    <property name="SmartFailing" type="b" access="read"/>
    <property name="SmartPowerOnSeconds" type="t" access="read"/>
    <property name="SmartTemperature" type="d" access="read"/>
    <property name="SmartBadSectors" type="t" access="read"/>
    <method name="SmartGetAttributes">
      <arg type="a{sv}" direction="in"/>
      <arg type="a(sv)" direction="out"/>
    </method>
  </interface>
"""

NVME_IFACE = """
  <interface name="org.freedesktop.UDisks2.NVMe">
    <property name="Model" type="s" access="read"/>
    <property name="Serial" type="s" access="read"/>
    <property name="Firmware" type="s" access="read"/>
  </interface>
"""

BLOCK_IFACE = """
  <interface name="org.freedesktop.UDisks2.Block">
    <property name="IdType" type="s" access="read"/>
    <property name="IdLabel" type="s" access="read"/>
    <property name="IdUUID" type="s" access="read"/>
    <property name="Device" type="ay" access="read"/>
    <property name="Size" type="t" access="read"/>
    <property name="HintPartitionable" type="b" access="read"/>
  </interface>
"""

FS_IFACE = """
  <interface name="org.freedesktop.UDisks2.Filesystem">
    <property name="MountPoints" type="as" access="read"/>
    <method name="Mount">
      <arg type="a{sv}" direction="in"/>
      <arg type="s" direction="out"/>
    </method>
    <method name="Unmount">
      <arg type="a{sv}" direction="in"/>
    </method>
    <method name="Format">
      <arg type="a{sv}" direction="in"/>
    </method>
  </interface>
"""

PARTITION_IFACE = """
  <interface name="org.freedesktop.UDisks2.Partition">
    <property name="Number" type="t" access="read"/>
    <property name="Type" type="s" access="read"/>
    <property name="Offset" type="t" access="read"/>
    <property name="Size" type="t" access="read"/>
    <property name="Name" type="s" access="read"/>
    <property name="Table" type="o" access="read"/>
  </interface>
"""

PARTTABLE_IFACE = """
  <interface name="org.freedesktop.UDisks2.PartitionTable">
    <property name="Type" type="s" access="read"/>
    <property name="Partitions" type="ao" access="read"/>
  </interface>
"""

OBJMANAGER_IFACE = """
  <interface name="org.freedesktop.DBus.ObjectManager">
    <method name="GetManagedObjects">
      <arg type="a{oa{sa{sv}}}" direction="out"/>
    </method>
    <signal name="InterfacesAdded">
      <arg type="o" direction="out"/>
      <arg type="a{sa{sv}}" direction="out"/>
    </signal>
    <signal name="InterfacesRemoved">
      <arg type="o" direction="out"/>
      <arg type="as" direction="out"/>
    </signal>
  </interface>
"""

SATA = "/org/freedesktop/UDisks2/drives/Samsung_SSD_850_250GB_S123456789"
USB = "/org/freedesktop/UDisks2/drives/Generic_Flash_Disk_ABCDEF"
NVME = "/org/freedesktop/UDisks2/drives/Apple_SSD_SM0256L_0000"
SDA = "/org/freedesktop/UDisks2/block_devices/sda"
SDA1 = "/org/freedesktop/UDisks2/block_devices/sda1"
SDB = "/org/freedesktop/UDisks2/block_devices/sdb"
SDB1 = "/org/freedesktop/UDisks2/block_devices/sdb1"
SDC = "/org/freedesktop/UDisks2/block_devices/sdc"
SDD = "/org/freedesktop/UDisks2/block_devices/sdd"
SDD1 = "/org/freedesktop/UDisks2/block_devices/sdd1"
NVME0N1 = "/org/freedesktop/UDisks2/block_devices/nvme0n1"
NVME0N1P1 = "/org/freedesktop/UDisks2/block_devices/nvme0n1p1"

# /dev/sdc: a filesystem written straight onto a whole disk with no
# partition table at all (supertypes: /dev/sdX), so it has NO
# Partition.Table link and used to vanish from the sidebar.  Its UDisks2
# path is derived from the device basename like the real daemon does.
def block_path(device):
    return BLOCKS_PATH + "/" + os.path.basename(device)


SCD_PATH = block_path("/dev/sdc")

MOCK_CALLS = []


def s(v):
    return GLib.Variant("s", v)


def t(v):
    return GLib.Variant("t", v)


def b(v):
    return GLib.Variant("b", v)


def d(v):
    return GLib.Variant("d", v)


def ay(v):
    return GLib.Variant("ay", v.encode())


def as_(v):
    return GLib.Variant("as", v)


def _opts(params):
    """Decode an a{sv} options dict from a method call.

    A method with a single a{sv} input unpacks straight to the dict. GLib
    already unwraps nested Variants of simple types, so values are either
    plain Python values or Variants depending on the type.
    """
    unpacked = params.unpack()
    raw = unpacked[0] if isinstance(unpacked, tuple) else unpacked
    return {k: (v.unpack() if hasattr(v, "unpack") else v)
            for k, v in raw.items()}


def build_mock_objects():
    return [
        (SATA, {
            "org.freedesktop.UDisks2.Drive": {
                "Vendor": s("Samsung"), "Model": s("SSD 850 250GB"),
                "Serial": s("S123456789"), "Size": t(250059350016),
                "ConnectionBus": s("ata"), "Ejectable": b(False),
                "Removable": b(False), "Media": s("ssd"),
            },
            "org.freedesktop.UDisks2.Drive.Ata": {
                "SmartUpdated": t(1758800000), "SmartFailing": b(False),
                "SmartPowerOnSeconds": t(36000), "SmartTemperature": d(300),
                "SmartBadSectors": t(0),
            },
        }, {
            ("org.freedesktop.UDisks2.Drive", "Eject"):
                lambda p, inv: inv.return_dbus_error(
                    "org.freedesktop.UDisks2.Error.Failed", "not ejectable"),
            ("org.freedesktop.UDisks2.Drive.Ata", "SmartGetAttributes"):
                lambda p, inv: inv.return_value(GLib.Variant("(a(sv))", ([
                    ("194", GLib.Variant("a{sv}", {
                        "name": s("Temperature_Celsius"), "value": s("30"),
                        "pretty": s("27"), "worst": s("30"),
                        "threshold": s("0"), "flags": t(1), "updated": t(1)})),
                    ("5", GLib.Variant("a{sv}", {
                        "name": s("Reallocated_Sector_Ct"), "value": s("100"),
                        "pretty": s("0"), "worst": s("100"),
                        "threshold": s("10"), "flags": t(1), "updated": t(1)})),
                ],))),
        }),
        (USB, {
            "org.freedesktop.UDisks2.Drive": {
                "Vendor": s("Generic"), "Model": s("Flash Disk"),
                "Serial": s("ABCDEF"), "Size": t(16013942784),
                "ConnectionBus": s("usb"), "Ejectable": b(True),
                "Removable": b(True), "Media": s("flash-sd"),
            },
        }, {
            ("org.freedesktop.UDisks2.Drive", "Eject"):
                lambda p, inv: (MOCK_CALLS.append(("eject", USB)),
                                inv.return_value(None))[1],
        }),
        (NVME, {
            "org.freedesktop.UDisks2.Drive": {
                "Vendor": s("Apple"), "Model": s("SSD SM0256L"),
                "Serial": s("0000"), "Size": t(256060514304),
                "ConnectionBus": s("nvme"), "Ejectable": b(False),
                "Removable": b(False), "Media": s("ssd"),
            },
            "org.freedesktop.UDisks2.NVMe": {
                "Model": s("APPLE SSD SM0256J"), "Serial": s("0000"),
                "Firmware": s("1.0.0"),
            },
        }, {}),
        (SDA, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s(""), "IdLabel": s(""), "IdUUID": s(""),
                "Device": ay("/dev/sda"), "Size": t(250059350016),
                "HintPartitionable": b(True),
            },
            "org.freedesktop.UDisks2.PartitionTable": {
                "Type": s("gpt"), "Partitions": as_([SDA1]),
            },
        }, {}),
        (SDA1, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s("ext4"), "IdLabel": s("rootfs"),
                "IdUUID": s("11111111-2222-3333-4444-555555555555"),
                "Device": ay("/dev/sda1"), "Size": t(249000000000),
                "HintPartitionable": b(False),
            },
            "org.freedesktop.UDisks2.Partition": {
                "Number": t(1),
                "Type": s("0FC63DAF-8483-4772-8E79-3D69D8477DE4"),
                "Offset": t(1048576), "Size": t(249000000000),
                "Name": s("Linux filesystem"), "Table": s(SATA),
            },
            "org.freedesktop.UDisks2.Filesystem": {
                "MountPoints": as_(["/"]),
            },
        }, {
            ("org.freedesktop.UDisks2.Filesystem", "Mount"):
                lambda p, inv: inv.return_dbus_error(
                    "org.freedesktop.UDisks2.Error.AlreadyMounted",
                    "Device /dev/sda1 is already mounted at /"),
            ("org.freedesktop.UDisks2.Filesystem", "Unmount"):
                lambda p, inv: (MOCK_CALLS.append(("unmount", SDA1)),
                                inv.return_value(None))[1],
        }),
        (SDB, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s(""), "IdLabel": s(""), "IdUUID": s(""),
                "Device": ay("/dev/sdb"), "Size": t(16013942784),
                "HintPartitionable": b(True),
            },
            "org.freedesktop.UDisks2.PartitionTable": {
                "Type": s("msdos"), "Partitions": as_([SDB1]),
            },
        }, {}),
        (SDB1, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s("vfat"), "IdLabel": s("USBSTICK"),
                "IdUUID": s("ABCD-1234"), "Device": ay("/dev/sdb1"),
                "Size": t(15999999999), "HintPartitionable": b(False),
            },
            "org.freedesktop.UDisks2.Partition": {
                "Number": t(1), "Type": s("0x0c"), "Offset": t(2048),
                "Size": t(15999999999), "Name": s(""), "Table": s(USB),
            },
            "org.freedesktop.UDisks2.Filesystem": {
                "MountPoints": as_([]),
            },
        }, {
            ("org.freedesktop.UDisks2.Filesystem", "Mount"):
                lambda p, inv: (MOCK_CALLS.append(("mount", SDB1)),
                                inv.return_value(GLib.Variant("(s)", ("/media/USBSTICK",))))[1],
            ("org.freedesktop.UDisks2.Filesystem", "Unmount"):
                lambda p, inv: (MOCK_CALLS.append(("unmount", SDB1)),
                                inv.return_value(None))[1],
            # A method taking a single a{sv} argument unpacks to the dict
            # itself, NOT a one-tuple (unlike Mount, whose a{sv} is followed
            # by the out arg s).  Unpacking [0] here would raise and leave
            # the invocation unanswered -> client timeout.
            ("org.freedesktop.UDisks2.Filesystem", "Format"):
                lambda p, inv: (MOCK_CALLS.append(
                    ("format", SDB1, _opts(p))), inv.return_value(None))[1],
        }),
        # /dev/sdd: a partition table plus a partition that is busy, so the
        # unmount error path (the case a user hits with an open file) is
        # reachable in tests.
        (SDD, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s(""), "IdLabel": s(""), "IdUUID": s(""),
                "Device": ay("/dev/sdd"), "Size": t(80000000000),
                "HintPartitionable": b(True),
            },
            "org.freedesktop.UDisks2.PartitionTable": {
                "Type": s("gpt"), "Partitions": as_([SDD1]),
            },
        }, {}),
        (SDD1, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s("btrfs"), "IdLabel": s("BACKUP"),
                "IdUUID": s("DDDD-1111"), "Device": ay("/dev/sdd1"),
                "Size": t(40000000000), "HintPartitionable": b(False),
            },
            "org.freedesktop.UDisks2.Partition": {
                "Number": t(1), "Type": s("0fc63daf-8483-4772-8e79-3d69d8477de4"),
                "Offset": t(1048576), "Size": t(40000000000),
                "Name": s("Backup"), "Table": s(USB),
            },
            "org.freedesktop.UDisks2.Filesystem": {
                "MountPoints": as_([]),
            },
        }, {
            ("org.freedesktop.UDisks2.Filesystem", "Mount"):
                lambda p, inv: inv.return_value(
                    GLib.Variant("(s)", ("/run/media/mavericks/BACKUP",))),
            ("org.freedesktop.UDisks2.Filesystem", "Unmount"):
                lambda p, inv: inv.return_dbus_error(
                    "org.freedesktop.UDisks2.Error.Busy",
                    "Target device is busy"),
        }),
        # Whole-disk filesystem on /dev/sdc: no PartitionTable, no
        # Partition, unmounted, erasable.  UDisks2 gives no block->drive
        # link for it, so the old enumeration dropped it from the sidebar
        # entirely; it must now surface in the OTHER VOLUMES group.
        (SCD_PATH, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s("ext4"), "IdLabel": s("SCRATCH"),
                "IdUUID": s("CCCC-2222"), "Device": ay("/dev/sdc"),
                "Size": t(64000000000), "HintPartitionable": b(False),
            },
            "org.freedesktop.UDisks2.Filesystem": {
                "MountPoints": as_([]),
            },
        }, {
            ("org.freedesktop.UDisks2.Filesystem", "Mount"):
                lambda p, inv: inv.return_value(
                    GLib.Variant("(s)", ("/run/media/mavericks/SCRATCH",))),
            ("org.freedesktop.UDisks2.Filesystem", "Unmount"):
                lambda p, inv: inv.return_value(None),
            ("org.freedesktop.UDisks2.Filesystem", "Format"):
                lambda p, inv: (MOCK_CALLS.append(
                    ("format", SCD_PATH, _opts(p))), inv.return_value(None))[1],
        }),
        (NVME0N1, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s(""), "IdLabel": s(""), "IdUUID": s(""),
                "Device": ay("/dev/nvme0n1"), "Size": t(256060514304),
                "HintPartitionable": b(True),
            },
            "org.freedesktop.UDisks2.PartitionTable": {
                "Type": s("gpt"), "Partitions": as_([NVME0N1P1]),
            },
        }, {}),
        (NVME0N1P1, {
            "org.freedesktop.UDisks2.Block": {
                "IdType": s("hfsplus"), "IdLabel": s("Macintosh HD"),
                "IdUUID": s("AAAA-BBBB-CCCC"),
                "Device": ay("/dev/nvme0n1p1"), "Size": t(255000000000),
                "HintPartitionable": b(False),
            },
            "org.freedesktop.UDisks2.Partition": {
                "Number": t(1),
                "Type": s("48465300-0000-11AA-AA11-00306543ECAC"),
                "Offset": t(125829120), "Size": t(255000000000),
                "Name": s("Macintosh HD"), "Table": s(NVME),
            },
            "org.freedesktop.UDisks2.Filesystem": {
                "MountPoints": as_([]),
            },
        }, {
            ("org.freedesktop.UDisks2.Filesystem", "Mount"):
                lambda p, inv: (MOCK_CALLS.append(("mount", NVME0N1P1)),
                                inv.return_value(GLib.Variant("(s)", ("/mnt/macintosh-hd",))))[1],
        }),
    ]


IFACE_XML = {
    "org.freedesktop.UDisks2.Drive": DRIVE_IFACE,
    "org.freedesktop.UDisks2.Drive.Ata": DRIVE_ATA_IFACE,
    "org.freedesktop.UDisks2.NVMe": NVME_IFACE,
    "org.freedesktop.UDisks2.Block": BLOCK_IFACE,
    "org.freedesktop.UDisks2.Filesystem": FS_IFACE,
    "org.freedesktop.UDisks2.Partition": PARTITION_IFACE,
    "org.freedesktop.UDisks2.PartitionTable": PARTTABLE_IFACE,
}



def main():
    if len(sys.argv) < 2:
        print("usage: mock-udisks2.py <bus-address>", file=sys.stderr)
        return 2
    addr = sys.argv[1]
    flags = (Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
             Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)
    conn = Gio.DBusConnection.new_for_address_sync(addr, flags, None, None)
    Gio.bus_own_name_on_connection(conn, UDISKS_BUS,
                                   Gio.BusNameOwnerFlags.NONE, None, None)

    def make_method_call(path, props, methods):
        def dispatch(connection, sender, obj_path, iface, method,
                     parameters, invocation):
            if iface == "org.freedesktop.DBus.Properties":
                if method == "GetAll":
                    name = parameters.get_child_value(0).get_string()
                    invocation.return_value(
                        GLib.Variant("(a{sv})", (props.get(name, {}),)))
                    return True
                if method == "Get":
                    name = parameters.get_child_value(0).get_string()
                    prop = parameters.get_child_value(1).get_string()
                    if prop in props.get(name, {}):
                        invocation.return_value(
                            GLib.Variant("(v)", (props[name][prop],)))
                    else:
                        invocation.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            "no such property %s" % prop)
                    return True
            handler = methods.get((iface, method))
            if handler is None:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod", method)
                return True
            try:
                handler(parameters, invocation)
            except Exception as exc:
                # A raising handler must still answer: an unanswered
                # invocation blocks the client until its call timeout.
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Failed", "mock handler: %s" % exc)
            return True

        def on_method_call(*args):
            return dispatch(*args)

        return on_method_call

    for path, props, methods in build_mock_objects():
        for iface in props:
            xml = "<node>%s%s</node>" % (PROPS_IFACE, IFACE_XML[iface])
            info = Gio.DBusNodeInfo.new_for_xml(xml).lookup_interface(iface)
            conn.register_object(path, info,
                                 make_method_call(path, props, methods),
                                 None, None)

    def on_root_call(connection, sender, obj_path, iface, method,
                     parameters, invocation):
        if method == "GetManagedObjects":
            data = {path: props for path, props, _ in build_mock_objects()}
            invocation.return_value(
                GLib.Variant("(a{oa{sa{sv}}})", (data,)))
            return True
        invocation.return_dbus_error(
            "org.freedesktop.DBus.Error.UnknownMethod", method)
        return True

    root_info = Gio.DBusNodeInfo.new_for_xml(
        "<node>%s</node>" % OBJMANAGER_IFACE).lookup_interface(
        "org.freedesktop.DBus.ObjectManager")
    conn.register_object("/org/freedesktop/UDisks2", root_info,
                         on_root_call, None, None)
    print("READY", flush=True)
    GLib.MainLoop().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
