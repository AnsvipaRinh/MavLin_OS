#!/usr/bin/env python3
"""Headless tests for mv-diskutil against a mock UDisks2 service.

Read-only: no real disks are touched. The mock (scripts/mock-udisks2.py)
serves three fake devices (internal SATA with mounted ext4, external
unmounted USB stick, Apple NVMe with HFS+ partition) on a private bus.

Usage:
  dbus-run-session -- python3 scripts/test-mv-diskutil.py
  python3 scripts/test-mv-diskutil.py   (auto-spawns a private dbus-daemon)

Exit 0 = all tests passed."""
import os
import shutil
import subprocess
import sys
import importlib.util
import importlib.machinery

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless app-suite: no window today, but app code and child
# interpreters run with the ambient environment — on WSLg that is
# the user's Windows desktop.  Arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED (oid
# OS-window-leak2) instead of popping a window on the host.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

APP_PATH = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-diskutil")
MOCK_PATH = os.path.join(REPO, "scripts/mock-udisks2.py")

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


def run_portable_tests(mv):
    """Unit tests for the pure property parsers. These exercise the exact
    code paths used by enumerate_devices() without needing gi or a DBus
    daemon, so they run on any host."""
    V = mv._as_variant

    # module imports headless at all
    check("portable: module has shim", hasattr(mv, "_ShimVariant"))
    check("portable: lazy gio gate", callable(mv._gio))

    # --- drive parsing -------------------------------------------------
    drive_ifaces = {
        mv.IFACE_DRIVE: {
            "Model": V("SSD 850 250GB"),
            "Vendor": V("Samsung"),
            "Serial": V("S123456789"),
            "Size": V(250059350016),
            "ConnectionBus": V("sata"),
            "Ejectable": V(False),
            "Removable": V(False),
            "Media": V("solid-state"),
        },
        mv.IFACE_DRIVE_ATA: {
            "SmartUpdated": V(1759489000),
            "SmartFailing": V(False),
            "SmartPowerOnSeconds": V(36000000),
            "SmartTemperature": V(300.0),
            "SmartBadSectors": V(0),
        },
    }
    d = mv._drive_from_path("/org/freedesktop/UDisks2/drives/Samsung", drive_ifaces)
    check("portable: drive model", d["model"] == "SSD 850 250GB")
    check("portable: drive size int", d["size"] == 250059350016)
    check("portable: drive not nvme", d["nvme"] is False)
    check("portable: drive smart parsed", d["smart"] is not None)
    check("portable: drive smart temp", d["smart"]["temperature"] == 300.0)
    check("portable: drive smart failing", d["smart"]["failing"] is False)
    check("portable: drive no-iface -> None",
          mv._drive_from_path("/x", {}) is None)

    nvme_ifaces = dict(drive_ifaces)
    nvme_ifaces[mv.IFACE_DRIVE] = dict(drive_ifaces[mv.IFACE_DRIVE],
                                       ConnectionBus=V("nvme"))
    nvme_ifaces[mv.IFACE_NVME] = {}
    dn = mv._drive_from_path("/x", nvme_ifaces)
    check("portable: nvme flagged", dn["nvme"] is True)

    # --- block parsing --------------------------------------------------
    block_ifaces = {
        mv.IFACE_BLOCK: {
            "Device": V(b"/dev/sdb1\x00"),
            "Size": V(31000000000),
            "IdType": V("vfat"),
            "IdLabel": V("USBSTICK"),
            "IdUUID": V("ABCD-1234"),
        },
        mv.IFACE_FS: {"MountPoints": V([b"/media/USBSTICK"])},
        mv.IFACE_PARTITION: {
            "Number": V(1), "Type": V("c"),
            "Offset": V(1048576), "Table": V("/org/.../drives/Generic"),
        },
    }
    b = mv._block_from_path("/y", block_ifaces)
    check("portable: block device stripped", b["device"] == "/dev/sdb1")
    check("portable: block fs", b["fs_type"] == "vfat")
    check("portable: block uuid", b["uuid"] == "ABCD-1234")
    check("portable: block mount decoded",
          b["mount_points"] == [b"/media/USBSTICK"], repr(b["mount_points"]))
    check("portable: block partition number", b["partition_number"] == 1)
    check("portable: block no-iface -> None",
          mv._block_from_path("/y", {}) is None)

    # unmounted filesystem (no MountPoints key value set)
    b2 = mv._block_from_path("/y", {
        mv.IFACE_BLOCK: {"Device": V("/dev/sdc1"), "Size": V(1),
                         "IdType": V("ext4")},
    })
    check("portable: block str device", b2["device"] == "/dev/sdc1")
    check("portable: block no fs -> empty mounts", b2["mount_points"] == [])

    # --- helpers --------------------------------------------------------
    check("portable: human_size GB", mv.human_size(250059350016) == "250.1 GB")
    check("portable: human_size MB", mv.human_size(5 * 10 ** 6) == "5.0 MB")
    check("portable: human_size bytes", mv.human_size(999) == "999 bytes")
    check("portable: temp plain float",
          abs(mv.smart_temperature_c(300.0) - 26.85) < 0.01)
    check("portable: temp variant duck-type",
          abs(mv.smart_temperature_c(V(300.0)) - 26.85) < 0.01)
    check("portable: temp None", mv.smart_temperature_c(None) is None)

    # --- accessor coverage on every parser type -------------------------
    sv = mv._ShimVariant(True)
    check("portable: shim bool", sv.get_boolean() is True)
    sv = mv._ShimVariant(42)
    check("portable: shim uint64", sv.get_uint64() == 42)
    sv = mv._ShimVariant(["a", "b"])
    check("portable: shim strv", sv.get_strv() == ["a", "b"])
    sv = mv._ShimVariant(b"raw")
    check("portable: shim bytes", sv.get_data_as_bytes().get_data() == b"raw")

    # _v_* tolerate both wrapped and raw values
    check("portable: _v_str wrapped", mv._v_str(V("x")) == "x")
    check("portable: _v_str raw", mv._v_str("x") == "x")
    check("portable: _v_str none", mv._v_str(None) == "")
    check("portable: _v_int wrapped", mv._v_int(V(7)) == 7)
    check("portable: _v_bool wrapped", mv._v_bool(V(False)) is False)
    check("portable: _v_bytes str", mv._v_bytes("abc") == b"abc")
    check("portable: _v_strv wrapped", mv._v_strv(V(["z"])) == ["z"])

    # live DBus path must fail loudly (not silently) without gi
    if mv.GLib is False:
        try:
            mv.enumerate_devices()
            check("portable: enumerate raises without gi", False,
                  "no exception")
        except mv._NoGio:
            check("portable: enumerate raises without gi", True)
    else:
        ok("portable: gi present, skipping _NoGio assertion")


def ensure_bus():
    addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if addr:
        return addr, None
    proc = subprocess.Popen(
        ["dbus-daemon", "--session", "--print-address=1", "--fork", "--nopidfile"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    addr = proc.stdout.readline().strip()
    return addr, proc


def start_mock(addr):
    proc = subprocess.Popen([sys.executable, MOCK_PATH, addr],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True)
    line = proc.stdout.readline().strip()
    if line != "READY":
        proc.kill()
        raise RuntimeError("mock failed to start: %r" % line)
    return proc


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_diskutil", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_diskutil", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def main():
    # Portable section: pure parser unit tests run on ANY host.
    mv = load_app()
    run_portable_tests(mv)

    # Integration section: needs PyGObject + a DBus daemon + the mock service.
    try:
        import gi
    except ImportError:
        print("SKIP - integration section (no PyGObject on this host)")
        print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
        return 1 if FAILURES else 0
    if not shutil.which("dbus-daemon"):
        print("SKIP - integration section (no dbus-daemon on this host)")
        print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
        return 1 if FAILURES else 0

    gi.require_version("GLib", "2.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import GLib, Gio

    addr, _bus_proc = ensure_bus()
    mock = start_mock(addr)
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = addr
    try:
        SATA = "/org/freedesktop/UDisks2/drives/Samsung_SSD_850_250GB_S123456789"
        USB = "/org/freedesktop/UDisks2/drives/Generic_Flash_Disk_ABCDEF"
        SDA1 = "/org/freedesktop/UDisks2/block_devices/sda1"
        SDB1 = "/org/freedesktop/UDisks2/block_devices/sdb1"

        devices, err = mv.enumerate_devices()
        check("enumerate: no error", err is None, "err=%r" % err)
        check("enumerate: 3 drives", len(devices) == 3, "got %d" % len(devices))

        by_model = {d["model"]: d for d in devices}
        sata = by_model.get("SSD 850 250GB")
        usb = by_model.get("Flash Disk")
        nvme = by_model.get("SSD SM0256L")
        check("enumerate: sata drive present", sata is not None)
        check("enumerate: usb drive present", usb is not None)
        check("enumerate: nvme drive present", nvme is not None)

        if sata:
            check("sata: not removable", sata["removable"] is False)
            check("sata: 1 partition child", len(sata["blocks"]) == 1,
                  "got %d" % len(sata["blocks"]))
            if sata["blocks"]:
                blk = sata["blocks"][0]
                check("sata partition: ext4", blk["fs_type"] == "ext4")
                check("sata partition: mounted at /", blk["mount_points"] == ["/"])
                check("sata partition: uuid",
                      blk["uuid"] == "11111111-2222-3333-4444-555555555555")
                check("sata partition: device", blk["device"] == "/dev/sda1")
            check("sata: smart not failing",
                  sata["smart"] and sata["smart"]["failing"] is False)
            check("sata: smart temp 300K",
                  sata["smart"] and sata["smart"]["temperature"] == 300.0)
            check("sata: not nvme", sata["nvme"] is False)

        if usb:
            check("usb: removable", usb["removable"] is True)
            check("usb: ejectable", usb["ejectable"] is True)
            check("usb: 1 partition child", len(usb["blocks"]) == 1)
            if usb["blocks"]:
                blk = usb["blocks"][0]
                check("usb partition: vfat", blk["fs_type"] == "vfat")
                check("usb partition: unmounted", blk["mount_points"] == [])

        if nvme:
            check("nvme: flagged", nvme["nvme"] is True)
            check("nvme: apple model", "Apple" in nvme["vendor"])
            check("nvme: 1 partition child", len(nvme["blocks"]) == 1)
            if nvme["blocks"]:
                check("nvme partition: hfsplus",
                      nvme["blocks"][0]["fs_type"] == "hfsplus")

        conn = mv.get_connection()
        try:
            mp = mv.mount_filesystem(conn, SDB1)
            check("mount: returns mount point", mp == "/media/USBSTICK",
                  "got %r" % mp)
        except GLib.Error as e:
            check("mount: returns mount point", False, str(e))

        try:
            mv.mount_filesystem(conn, SDA1)
            check("mount already-mounted: raises", False, "no error raised")
        except GLib.Error:
            check("mount already-mounted: raises", True)

        try:
            mv.unmount_filesystem(conn, SDA1)
            check("unmount: ok", True)
        except GLib.Error as e:
            check("unmount: ok", False, str(e))

        try:
            mv.eject_drive(conn, USB)
            check("eject: ok", True)
        except GLib.Error as e:
            check("eject: ok", False, str(e))

        try:
            attrs = mv.smart_get_attributes(conn, SATA)
            check("smart attrs: 2 entries", len(attrs) == 2, "got %d" % len(attrs))
            check("smart attrs: id 194", attrs[0][0] == "194")
            check("smart attrs: name",
                  attrs[0][1]["name"] == "Temperature_Celsius")
        except GLib.Error as e:
            check("smart attrs: 2 entries", False, str(e))

        check("helpers: human_size", mv.human_size(250059350016) == "250.1 GB",
              mv.human_size(250059350016))
        check("helpers: temp c",
              abs(mv.smart_temperature_c(GLib.Variant("d", 300)) - 26.85) < 0.01)
    finally:
        mock.terminate()
        mock.wait(timeout=5)

    proc2 = subprocess.Popen(
        ["dbus-daemon", "--session", "--print-address=1", "--fork", "--nopidfile"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    addr2 = proc2.stdout.readline().strip()
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = addr2
    devices2, err2 = mv.enumerate_devices()
    check("absent: empty list", devices2 == [])
    check("absent: not-available", err2 == "not-available", "got %r" % err2)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
