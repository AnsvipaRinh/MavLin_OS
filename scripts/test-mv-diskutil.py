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
# The GUI section maps real widgets, so it needs the project-pinned Xvfb
# :97 — never the ambient host display (WSLg DISPLAY=:0 / wayland-0 both
# forward to the user's Windows desktop).  gui_display() pins :97 or
# returns None (headless -> GUI section skips) and arms the fail-loud
# guard so no child interpreter can leak onto the host.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

MV_DISPLAY = mv_gui_iso.gui_display()

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


def test_safety_helpers(mv):
    """Erase gating: the only irreversible action must stay conservative."""
    block = {"device": "/dev/sdb1", "fs_type": "exfat", "mount_points": [],
             "size": 100, "label": "STICK"}
    check("safe: unmounted real disk erasable",
          mv.can_erase(block, {"sda1": ["/"]}) == (True, ""))

    mounted = dict(block, mount_points=["/run/media/user/STICK"])
    check("safe: mounted volume refused",
          mv.can_erase(mounted, None) == (False, "mounted"))

    # The property can lag behind a mount another tool just made.
    stale = dict(block)
    check("safe: /proc/mounts catches stale MountPoints",
          mv.can_erase(stale, {"/dev/sdb1": ["/media/x"]}) == (False, "mounted"))

    for dev in ("/dev/loop3", "/dev/zram0", "/dev/sr0", "/dev/ram0",
                "/dev/dm-0"):
        check("safe: %s refused" % dev,
              mv.can_erase(dict(block, device=dev), None)[1] == "virtual-device")

    check("safe: non-device node refused",
          mv.can_erase(dict(block, device="md127"), None)[1] == "not-a-device-node")
    check("safe: no filesystem refused",
          mv.can_erase(dict(block, fs_type=""), None)[1] == "no-filesystem")

    # Whole-disk devices are erasable when unmounted (superfloppy sticks).
    check("safe: whole-disk unmounted erasable",
          mv.can_erase(dict(block, device="/dev/sdc"), None)[0] is True)

    # Protected mount points must never be erased.
    check("safe: protected mount points listed",
          mv.is_protected_mount("/") and mv.is_protected_mount("/boot/efi")
          and mv.is_protected_mount("/home"))
    check("safe: normal mount not protected",
          not mv.is_protected_mount("/run/media/user/STICK"))
    check("safe: /run/media not protected",
          not mv.is_protected_mount("/run/media/mavericks/BACKUP"))


def test_mounts_parsing(mv):
    V = mv._as_variant
    text = (
        "proc /proc proc rw,nosuid 0 0\n"
        "/dev/sda1 / ext4 rw,relatime 0 0\n"
        "/dev/sdb1 /media/My\\040Stick vfat rw 0 0\n"
        "/dev/sdc /run/media/u/XYZ ext4 rw\n"
        "\n"
    )
    mounts = mv.parse_mounts(text)
    check("mounts: four devices", len(mounts) == 4, repr(sorted(mounts)))
    check("mounts: root device", mounts["/dev/sda1"] == ["/"])
    check("mounts: octal escape decoded",
          mounts["/dev/sdb1"] == ["/media/My Stick"])
    check("mounts: whole-disk mount", mv.device_is_mounted("/dev/sdc", mounts))
    check("mounts: parent covers partition",
          mv.device_is_mounted("/dev/sdb1",
                               {"/dev/sdb": ["/mnt/x"]}))
    check("mounts: unrelated device not mounted",
          not mv.device_is_mounted("/dev/sdz9", mounts))
    check("mounts: empty text", mv.parse_mounts("") == {})
    check("mounts: none text", mv.parse_mounts(None) == {})

    # MountPoints arrives in three different shapes depending on how deep
    # PyGObject unpacked it.  All were seen on a real enumeration run; the
    # list-of-bytes one used to reach the widget layer as "[47, 0]".
    check("mount entry: plain str", mv._decode_mount_entry("/mnt/x") == "/mnt/x")
    check("mount entry: bytes", mv._decode_mount_entry(b"/mnt/y") == "/mnt/y")
    check("mount entry: bytes with NUL",
          mv._decode_mount_entry(b"/mnt/z\x00") == "/mnt/z")
    check("mount entry: list of byte values",
          mv._decode_mount_entry([47, 109, 116, 116, 47, 100]) == "/mtt/d")
    check("mount entry: list with trailing NUL stripped",
          mv._decode_mount_entry([47, 0]) == "/")
    check("mount entry: empty rejected", mv._decode_mount_entry("") is None)
    check("mount entry: NUL-only rejected",
          mv._decode_mount_entry(b"\x00") is None)
    check("mount entry: non-utf8 bytes rejected",
          mv._decode_mount_entry(b"\xff\xfe") is None)
    check("mount entry: junk type rejected",
          mv._decode_mount_entry(object()) is None)

    check("strv: list-of-bytes shape decoded",
          mv._v_strv([[47, 0], [47, 109, 110, 116]]) == ["/", "/mnt"])
    check("strv: mixed shapes", mv._v_strv(["/a", b"/b"]) == ["/a", "/b"])
    check("strv: variant path", mv._v_strv(V([b"/a", "/b"])) == ["/a", "/b"])
    check("strv: junk entries dropped", mv._v_strv([object(), "/a"]) == ["/a"])
    check("strv: none", mv._v_strv(None) == [])

    # The regression that started this: a list-of-byte-values mount point
    # must never become the literal string "[47, 0]".
    check("strv: no list-repr leakage",
          all("[" not in p for p in mv._v_strv([[47, 0]])))


def test_error_classification(mv):
    """Every backend failure must reach the user as a distinct, actionable
    alert — never as a raw GDBus string."""
    cases = [
        ("org.freedesktop.UDisks2.Error.Busy", "Target device is busy",
         "eject", "USB Stick", "The Disk Is Busy", "warning"),
        ("org.freedesktop.UDisks2.Error.NotAuthorized",
         "Not authorized to perform operation", "format", "STICK",
         "Permission Denied", "warning"),
        ("org.freedesktop.DBus.Error.AccessDenied", "Permission denied",
         "unmount", "sda1", "Permission Denied", "warning"),
        ("org.freedesktop.UDisks2.Error.AlreadyMounted", "already mounted",
         "mount", "sda1", "Already Mounted", "info"),
        ("org.freedesktop.UDisks2.Error.NotMounted", "not mounted",
         "unmount", "sdb1", "Not Mounted", "info"),
        ("org.freedesktop.UDisks2.Error.NoSuchDevice", "gone",
         "eject", "USB Stick", "Disk Not Found", "warning"),
        ("org.freedesktop.DBus.Error.NoReply", "no reply",
         "mount", "sdb1", "Storage Service Unresponsive", "warning"),
        ("org.freedesktop.UDisks2.Error.MountedByAnotherUser", "in use",
         "unmount", "sdb1", "Mounted by Another User", "warning"),
        ("org.freedesktop.UDisks2.Error.OptionNotPermitted", "nope",
         "erase", "STICK", "Operation Not Permitted", "warning"),
        ("org.freedesktop.UDisks2.Error.SomethingNew", "weird backend text",
         "mount", "sdb1", "Couldn't Mount sdb1", "error"),
    ]
    seen = set()
    for dbus, msg, action, target, title, level in cases:
        got_title, secondary, got_level = mv.classify_action_error(
            dbus, msg, action, target)
        check("error %s -> %s" % (dbus.split(".")[-1], title),
              got_title == title, "got %r" % got_title)
        check("error %s level %s" % (dbus.split(".")[-1], level),
              got_level == level, "got %r" % got_level)
        check("error %s has advice" % dbus.split(".")[-1],
              bool(secondary) and len(secondary) > 20)
        check("error %s hides raw backend text" % dbus.split(".")[-1],
              dbus not in secondary and "GDBus" not in secondary)
        seen.add(got_title)
    # 10 cases, 9 distinct titles: NotAuthorized and AccessDenied are two
    # spellings of one condition and MUST collapse to the same alert.
    check("error: no duplicate alerts for one condition", len(seen) == 9,
          "%d unique" % len(seen))
    check("error: both permission spellings collapse",
          mv.classify_action_error("org.freedesktop.UDisks2.Error.NotAuthorized",
                                   "Not authorized", "erase", "STICK")[0]
          == mv.classify_action_error("org.freedesktop.DBus.Error.AccessDenied",
                                      "Permission denied", "erase", "STICK")[0])

    # Authorization cancellation is an "info" outcome, not a failure.
    t, s, lvl = mv.classify_action_error(
        "org.freedesktop.DBus.Error.InteractiveAuthorizationRequired",
        "Authentication cancelled", "erase", "STICK")
    check("error: auth cancel is informational",
          lvl == "info" and "ancel" in t + s, "%r/%r" % (t, s))


def test_formatters(mv):
    check("size: TB", mv.human_size(2 * 10 ** 12) == "2.00 TB")
    check("size: GB", mv.human_size(250059350016) == "250.1 GB")
    check("size: MB", mv.human_size(5 * 10 ** 6) == "5.0 MB")
    check("size: none", mv.human_size(None) == "—")

    check("duration: days", mv.human_duration(360000) == "4d 4h")
    check("duration: hours", mv.human_duration(36000) == "10h 0m")
    check("duration: minutes", mv.human_duration(600) == "10m")
    check("duration: seconds", mv.human_duration(9) == "9s")
    check("duration: none", mv.human_duration(None) == "—")

    check("smart summary: none",
          mv.smart_summary(None) == ("Not Available", "unknown"))
    check("smart summary: failing",
          mv.smart_summary({"failing": True, "updated": 1})[0] == "Failed")
    check("smart summary: failing is critical",
          mv.smart_summary({"failing": True, "updated": 1})[1] == "critical")
    check("smart summary: not checked",
          mv.smart_summary({"failing": False, "updated": 0})[0] == "Not Checked")
    check("smart summary: verified",
          mv.smart_summary({"failing": False, "updated": 5}) == ("Verified", "ok"))

    rows = mv.smart_rows({"failing": False, "updated": 5, "temperature": 300.0,
                          "power_on_seconds": 36000, "bad_sectors": 0})
    labels = [r[0] for r in rows]
    check("smart rows: labels", labels == ["S.M.A.R.T. Status", "Temperature",
                                          "Power-On Time", "Bad Sectors"],
          repr(labels))
    check("smart rows: temperature in C", rows[1][1] == "27 °C", rows[1][1])
    check("smart rows: power-on as duration", rows[2][1] == "10h 0m", rows[2][1])
    check("smart rows: none -> empty", mv.smart_rows(None) == [])

    attrs = [("194", {"name": "Temperature_Celsius", "value": "30",
                      "pretty": "27", "worst": "30"}),
             ("5", {"name": "Reallocated_Sector_Ct", "pretty": "0"})]
    arows = mv.smart_attribute_rows(attrs)
    check("smart attrs: two rows", len(arows) == 2, repr(arows))
    check("smart attrs: id + name", arows[0][0] == "194 Temperature_Celsius",
          arows[0][0])
    check("smart attrs: pretty value", arows[0][1] == "27")
    check("smart attrs: falls back to value",
          mv.smart_attribute_rows([("9", {"name": "X", "value": "42"})])[0][1] == "42")
    check("smart attrs: limit honoured",
          len(mv.smart_attribute_rows(attrs * 20, limit=5)) == 5)
    check("smart attrs: garbage tolerated",
          mv.smart_attribute_rows([("junk", None), (None,)]) == [])


def test_volume_naming(mv):
    block = {"label": "Macintosh HD", "fs_type": "hfsplus", "device": "/dev/nvme0n1p1"}
    check("volume name: label + fs",
          mv.volume_display_name(block) == "Macintosh HD (hfsplus)")
    check("volume name: fs only",
          mv.volume_display_name({"fs_type": "btrfs"}) == "btrfs")
    check("volume name: device fallback",
          mv.volume_display_name({"device": "/dev/sdb1"}) == "/dev/sdb1")
    check("volume name: empty",
          mv.volume_display_name({}) == "Volume")


def test_orphan_attachment(mv):
    """Whole-disk filesystems used to vanish from the sidebar because
    UDisks2 has no block->drive link; they must now stay visible under an
    explicit group instead of being attributed to a guessed parent."""
    superfloppy = {"device": "/dev/sdc", "partition_table": "",
                   "partition_number": 0, "fs_type": "exfat"}
    zpool = {"device": "/dev/sdb", "partition_table": "",
             "partition_number": 0, "fs_type": "zfs"}

    attached, unattached = mv.attach_orphan_blocks([], [superfloppy, zpool])
    check("orphan: no drive guessing", attached == 0)
    check("orphan: whole-disk volumes surfaced", len(unattached) == 2,
          repr([b["device"] for b in unattached]))
    check("orphan: flagged whole_disk",
          all(b.get("whole_disk") is True for b in unattached))

    # A block with a partition-table link is a normal partition: untouched.
    part = {"device": "/dev/sdb1", "partition_table": "/d/usb",
            "partition_number": 1, "fs_type": "vfat"}
    _a, un = mv.attach_orphan_blocks([], [part])
    check("orphan: real partitions are not orphans", un == [])

    # A block device with no filesystem is a partition table, not a volume:
    # it must not be listed as an unattached volume.
    table = {"device": "/dev/sdd", "partition_table": "", "partition_number": 0,
             "fs_type": ""}
    _a2, un2 = mv.attach_orphan_blocks([], [table])
    check("orphan: filesystem-less block not a volume", un2 == [])

    group = mv.unattached_drive([superfloppy, zpool])
    check("orphan: synthetic group holds them",
          group["synthetic"] is True and len(group["blocks"]) == 2)
    check("orphan: synthetic group has empty drive path", group["path"] == "")
    check("orphan: synthetic group is not a physical disk",
          group["ejectable"] is False and group["nvme"] is False
          and group["media"] == "")
    check("orphan: synthetic group size is the volume sum",
          group["size"] == 0, repr(group["size"]))


def test_nvme_sysfs(mv):
    """Apple S3X telemetry: UDisks2 exposes no SMART for NVMe, so the
    S3X section read from sysfs must work pre-hardware against a fake tree."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ctrl = os.path.join(tmp, "class/nvme/nvme0")
        hwmon = os.path.join(ctrl, "hwmon/hwmon3")
        os.makedirs(hwmon)
        for name, value in (("model", "APPLE SSD SM0256G\n"),
                            ("firmware_rev", "2A.101\n"),
                            ("serial", "0123456789AB\n"),
                            ("state", "live\n"),
                            ("critical_warning", "0\n")):
            with open(os.path.join(ctrl, name), "w") as fh:
                fh.write(value)
        with open(os.path.join(hwmon, "temp1_input"), "w") as fh:
            fh.write("31315\n")
        with open(os.path.join(hwmon, "temp1_crit"), "w") as fh:
            fh.write("36815\n")

        data = mv.read_nvme_telemetry(tmp)
        check("nvme: controller found", data is not None)
        if data:
            check("nvme: model", data["model"] == "APPLE SSD SM0256G",
                  data["model"])
            check("nvme: firmware", data["firmware"] == "2A.101")
            check("nvme: serial", data["serial"] == "0123456789AB")
            check("nvme: state live", data["state"] == "live")
            check("nvme: no critical warning", data["critical_warning"] == 0)
            check("nvme: temperature C", abs(data["temperature_c"] - 31.315) < 0.001,
                  repr(data["temperature_c"]))
            check("nvme: critical temperature",
                  abs(data["temperature_critical_c"] - 36.815) < 0.001)
            check("nvme: health verified",
                  mv.nvme_health_text(data) == ("Verified", "ok"))
            rows = mv.nvme_rows(data)
            labels = [r[0] for r in rows]
            check("nvme: rows cover identity+health",
                  {"Model", "Firmware", "Serial", "Connection",
                   "Controller State", "Health", "Temperature",
                   "Temperature Critical"} <= set(labels), repr(labels))

            # device/hwmon layout (kernel-dependent path)
            alt = os.path.join(tmp, "alt/nvme/nvme1/device/hwmon/hwmon4")
            os.makedirs(alt)
            with open(os.path.join(tmp, "alt/nvme/nvme1/model"), "w") as fh:
                fh.write("APPLE SSD SM0512F")
            with open(os.path.join(alt, "temp1_input"), "w") as fh:
                fh.write("30000\n")
            with open(os.path.join(tmp, "alt/nvme/nvme1/critical_warning"),
                      "w") as fh:
                fh.write("1\n")
            alt_data = mv.read_nvme_telemetry(
                tmp, controller=os.path.join(tmp, "alt/nvme/nvme1"))
            check("nvme: device/hwmon layout supported",
                  alt_data and abs(alt_data["temperature_c"] - 30.0) < 0.001,
                  repr(alt_data))
            check("nvme: critical warning surfaces",
                  mv.nvme_health_text(alt_data)[0] == "Critical Warning",
                  mv.nvme_health_text(alt_data)[0])

    check("nvme: absent -> None",
          mv.read_nvme_telemetry("/nonexistent-sysfs-root") is None)
    check("nvme: health text none",
          mv.nvme_health_text(None) == ("Not Available", "unknown"))
    check("nvme: state not live is critical",
          mv.nvme_health_text({"state": "offline"})[1] == "critical")
    check("nvme: rows none", mv.nvme_rows(None) == [])


def test_erase_filesystem_choices(mv):
    """The offered filesystem list must exist and default sensibly."""
    check("erase: list non-empty", len(mv.ERASE_FILESYSTEMS) > 0)
    check("erase: defaults in list",
          mv.ERASE_DEFAULT_REMOVABLE in mv.ERASE_FILESYSTEMS
          and mv.ERASE_DEFAULT_INTERNAL in mv.ERASE_FILESYSTEMS)
    check("erase: removable default is cross-platform",
          mv.ERASE_DEFAULT_REMOVABLE == "exfat")
    check("erase: ntfs not offered (no helper guaranteed)",
          "ntfs" not in mv.ERASE_FILESYSTEMS)
    check("erase: no duplicates", len(set(mv.ERASE_FILESYSTEMS))
          == len(mv.ERASE_FILESYSTEMS))


def test_error_parts(mv):
    class FakeError(Exception):
        def __init__(self, remote, message):
            super().__init__(message)
            self.remote_error = remote
            self.message = message

    name, msg = mv._error_parts(
        FakeError("org.freedesktop.UDisks2.Error.Busy", "Target device is busy"))
    check("error parts: remote name", name == "org.freedesktop.UDisks2.Error.Busy")
    check("error parts: message", msg == "Target device is busy")

    name, msg = mv._error_parts(Exception("plain failure"))
    check("error parts: plain exception", name == "" and "plain failure" in msg)


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
          b["mount_points"] == ["/media/USBSTICK"], repr(b["mount_points"]))
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


def test_gui_smoke(mv):
    """GUI smoke on the pinned Xvfb :97 (never the host display).

    Devices are injected, so the real widgets are exercised with no
    UDisks2 on the bus — the same code path a headless CI box can run.
    """
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    if not MV_DISPLAY:
        print("ok - gui smoke skipped (no isolated display available)")
        return
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (gtk init failed on %s)" % MV_DISPLAY)
        return

    drive = {
        "kind": "drive", "path": "/drives/Test_SSD", "model": "Test SSD",
        "vendor": "Test", "serial": "SN1", "size": 250059350016,
        "connection_bus": "sata", "ejectable": False, "removable": False,
        "media": "ssd", "nvme": False, "firmware": "",
        "smart": {"updated": 1758800000, "failing": False,
                  "power_on_seconds": 36000, "temperature": 300.0,
                  "bad_sectors": 0},
        "blocks": [{
            "kind": "block", "path": "/blocks/sda1", "device": "/dev/sda1",
            "size": 249000000000, "fs_type": "ext4", "label": "rootfs",
            "uuid": "UUID-1", "mount_points": [], "partition_number": 1,
            "partition_type": "0fc63daf", "partition_offset": 1048576,
            "partition_table": "/drives/Test_SSD", "partition_name": "",
            "partitionable": False, "partition_table_type": "",
        }],
    }
    external = {
        "kind": "drive", "path": "/drives/USB", "model": "USB Stick",
        "vendor": "Generic", "serial": "U1", "size": 16013942784,
        "connection_bus": "usb", "ejectable": True, "removable": True,
        "media": "flash-sd", "nvme": False, "firmware": "", "smart": None,
        "blocks": [{
            "kind": "block", "path": "/blocks/sdb1", "device": "/dev/sdb1",
            "size": 15999999999, "fs_type": "exfat", "label": "STICK",
            "uuid": "U-1", "mount_points": ["/run/media/u/STICK"],
            "partition_number": 1, "partition_type": "0x0c",
            "partition_offset": 2048, "partition_table": "/drives/USB",
            "partition_name": "", "partitionable": False,
            "partition_table_type": "",
        }],
    }
    synthetic = {
        "kind": "drive", "path": "", "synthetic": True,
        "model": mv.UNATTACHED_GROUP, "vendor": "", "serial": "",
        "size": 64000000000, "connection_bus": "", "ejectable": False,
        "removable": True, "media": "", "nvme": False, "firmware": "",
        "smart": None,
        "blocks": [{
            "kind": "block", "path": "/blocks/sdc", "device": "/dev/sdc",
            "size": 64000000000, "fs_type": "ext4", "label": "SCRATCH",
            "uuid": "S-1", "mount_points": [], "partition_number": 0,
            "partition_type": "", "partition_offset": 0, "partition_table": "",
            "partition_name": "", "partitionable": False,
            "partition_table_type": "",
        }],
    }

    DiskUtilWindow = mv.build_diskutil_class()
    w = DiskUtilWindow(devices=[drive, external, synthetic], conn=object())
    try:
        for _ in range(5):
            Gtk.main_iteration_do(False)

        check("gui: window constructs", w is not None)
        check("gui: title", w.get_title() == "Disk Utility")

        labels = []

        def walk(widget):
            if isinstance(widget, Gtk.Label):
                labels.append(widget.get_text())
            if isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    walk(child)
        walk(w)

        check("gui: internal group header", "INTERNAL" in labels)
        check("gui: external group header", "EXTERNAL" in labels)
        check("gui: unattached group header",
              mv.UNATTACHED_GROUP.upper() in labels)
        check("gui: ejectable indicator shown", "USB Stick" in labels)
        check("gui: mount point subtitle shown", "/run/media/u/STICK" in labels)

        selectable = [r for r in w.listbox.get_children()
                      if getattr(r, "mv_kind", None)]
        check("gui: sidebar rows are selectable", len(selectable) == 6,
              "%d rows" % len(selectable))

        # Drive selection renders the S.M.A.R.T. summary.
        w.selected = ("drive", drive["path"])
        w.rebuild_detail()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        drive_labels = []
        walk(w.detail)
        drive_labels = list(labels)
        check("gui: drive detail shows model", "Test SSD" in drive_labels)
        # Regression guard: rebuild_detail used to dispatch through
        # self.detail (a Gtk.Box) instead of the window, so selecting ANY
        # row raised AttributeError and the detail pane never rendered.
        check("gui: drive detail renders without AttributeError",
              any("Capacity" in t for t in drive_labels), repr(drive_labels))
        check("gui: drive detail shows SMART verified", "Verified" in drive_labels)
        check("gui: drive detail has S.M.A.R.T. Status row",
              "S.M.A.R.T. Status" in drive_labels)
        check("gui: no raw GDBus text in the UI",
              not any("GDBus" in t for t in drive_labels))

        # Volume selection: mounted volume offers Unmount, no Erase.
        w.selected = ("block", external["blocks"][0]["path"])
        w.rebuild_detail()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        labels.clear()
        walk(w.detail)
        check("gui: mounted volume shows mount point",
              "/run/media/u/STICK" in labels)
        check("gui: mounted volume refuses erase with a reason",
              any("Erasing is unavailable" in t for t in labels),
              repr(labels[-3:]))

        # Unmounted volume: Erase must be offered.
        w.selected = ("block", synthetic["blocks"][0]["path"])
        w.rebuild_detail()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        labels.clear()
        walk(w.detail)
        check("gui: unmounted volume detail renders",
              "SCRATCH (ext4)" in labels and "Not Mounted" in labels,
              repr(labels[:6]))
        check("gui: unmounted volume offers Mount", "Mount" in labels)
        check("gui: unmounted volume offers Erase", "Erase…" in labels,
              repr(labels))

        # Synthetic group selection renders the group header, not a disk.
        w.selected = ("drive", synthetic["path"])
        w.rebuild_detail()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        labels.clear()
        walk(w.detail)
        check("gui: synthetic group detail explains itself",
              any("written directly to a whole disk" in t for t in labels))

        # No-hardware fallback: UDisks2 missing must render, not crash.
        w.error = "not-available"
        w.selected = None
        w.rebuild_detail()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        labels.clear()
        walk(w.detail)
        check("gui: fallback shows Storage Service Unavailable",
              "Storage Service Unavailable" in labels)
        check("gui: fallback offers GNOME Disks handoff",
              any("GNOME Disks" in t for t in labels))

        w.error = None
        w.selected = None
        w.rebuild_detail()
        for _ in range(5):
            Gtk.main_iteration_do(False)
        labels.clear()
        walk(w.detail)
        check("gui: empty selection is instructional",
              "Select a disk or volume" in labels)

        # Escape clears selection instead of destroying the window.
        from gi.repository import Gdk
        event = Gdk.EventKey()
        event.type = Gdk.EventType.KEY_PRESS
        event.keyval = Gdk.keyval_from_name("Escape")
        event.state = 0
        w.selected = ("drive", drive["path"])
        w.on_key_press(w, event)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui: Escape clears selection", w.selected is None)
        check("gui: window survives Escape", w.get_realized() is not None)

        # Ctrl-R refresh path runs (with an injected bus it must not hang).
        event.keyval = Gdk.keyval_from_name("r")
        event.state = Gdk.ModifierType.CONTROL_MASK
        try:
            w.on_key_press(w, event)
        except Exception as exc:
            check("gui: ctrl-r handled", False, str(exc))
        else:
            check("gui: ctrl-r handled", True)

        check("gui: unsubscribe is wired",
              hasattr(w, "_sub_id") and w._sub_id is None)
    finally:
        try:
            w.destroy()
        except Exception:
            pass


def _native_chrome_contract():
    bin_name = "mv-diskutil"
    path = os.path.join(BIN, bin_name)
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("diskutil: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("diskutil: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)


def main():
    _native_chrome_contract()
    # Portable section: pure parser unit tests run on ANY host.
    mv = load_app()
    run_portable_tests(mv)
    test_safety_helpers(mv)
    test_mounts_parsing(mv)
    test_error_classification(mv)
    test_formatters(mv)
    test_volume_naming(mv)
    test_orphan_attachment(mv)
    test_nvme_sysfs(mv)
    test_erase_filesystem_choices(mv)
    test_error_parts(mv)

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
        SDD1 = "/org/freedesktop/UDisks2/block_devices/sdd1"
        SDC = "/org/freedesktop/UDisks2/block_devices/sdc"

        devices, err = mv.enumerate_devices()
        check("enumerate: no error", err is None, "err=%r" % err)
        # 3 physical drives + the synthetic OTHER VOLUMES group holding
        # the whole-disk filesystem (/dev/sdc) that UDisks2 links to
        # nothing.
        check("enumerate: 3 drives + 1 volume group", len(devices) == 4,
              "got %d" % len(devices))
        check("enumerate: one synthetic group",
              sum(1 for d in devices if d.get("synthetic")) == 1)
        scratch_group = [d for d in devices if d.get("synthetic")]
        check("enumerate: group holds /dev/sdc",
              scratch_group and any(b["device"] == "/dev/sdc"
                                    for b in scratch_group[0]["blocks"]))

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
            check("usb: two partitions", len(usb["blocks"]) == 2,
                  "got %d" % len(usb["blocks"]))
            children = {b["device"]: b for b in usb["blocks"]}
            blk = children.get("/dev/sdb1")
            if blk:
                check("usb partition: vfat", blk["fs_type"] == "vfat")
                check("usb partition: unmounted", blk["mount_points"] == [])
            backup = children.get("/dev/sdd1")
            check("usb: second partition present", backup is not None)
            if backup:
                check("usb p2: btrfs", backup["fs_type"] == "btrfs")

            # /dev/sdd is a partition table, not a volume.
            check("whole-disk: partition table not listed as a volume",
                  "/dev/sdd" not in children)

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

        # Non-ejectable drive must produce the backend's own error, which
        # classify_action_error then turns into a friendly alert.
        try:
            mv.eject_drive(conn, SATA)
            check("eject non-ejectable: raises", False, "no error")
        except GLib.Error as e:
            dbus_name, message = mv._error_parts(e)
            title, secondary, level = mv.classify_action_error(
                dbus_name, message, "eject", "SSD 850 250GB")
            check("eject non-ejectable: friendly error",
                  title != "Disk Utility Error" and secondary,
                  "%r / %r" % (title, secondary))
            check("eject non-ejectable: no raw DBus leak",
                  "org.freedesktop" not in secondary)

        # Busy volume: the exact case that used to surface as a raw
        # GDBus string in a stock MessageDialog.
        try:
            mv.unmount_filesystem(conn, SDD1)
            check("busy unmount: raises", False, "no error")
        except GLib.Error as e:
            dbus_name, message = mv._error_parts(e)
            title, secondary, level = mv.classify_action_error(
                dbus_name, message, "unmount", "BACKUP")
            check("busy unmount: classified as busy",
                  title == "The Disk Is Busy", title)
            check("busy unmount: actionable advice",
                  "in use" in secondary and "Close any files" in secondary,
                  secondary)
            check("busy unmount: warning level", level == "warning")

        # Erase: destructive backend call must reach UDisks2 with options.
        mounts = {"/dev/sda1": ["/"]}
        scratch = None
        for d in devices:
            for b in d["blocks"]:
                if b["device"] == "/dev/sdc":
                    scratch = b
        check("erase: whole-disk volume passes the gate",
              scratch is not None and mv.can_erase(scratch, mounts)[0] is True)
        if scratch:
            try:
                mv.format_filesystem(conn, scratch["path"], "NEWVOL", "exfat")
                check("erase: Format reaches UDisks2", True)
            except GLib.Error as e:
                check("erase: Format reaches UDisks2", False, str(e))
        check("erase: mounted root is refused",
              mv.can_erase(
                  {"device": "/dev/sda1", "fs_type": "ext4",
                   "mount_points": ["/"]}, mounts)[1] == "mounted")

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

    # GUI smoke last: it needs the pinned Xvfb and must never touch the
    # host display (the guard is armed at import time above).
    test_gui_smoke(mv)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
