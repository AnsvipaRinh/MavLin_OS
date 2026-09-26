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
import subprocess
import sys
import importlib.util
import importlib.machinery

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    addr, _bus_proc = ensure_bus()
    mock = start_mock(addr)
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = addr
    try:
        import gi
        gi.require_version("GLib", "2.0")
        gi.require_version("Gio", "2.0")
        from gi.repository import GLib, Gio

        mv = load_app()

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
