#!/usr/bin/env python3
"""Headless tests for mv-eject (canonical #14 Power/Shutdown, eject side).

What this suite is really guarding, and why the old implementation got
past the previous gates:

  * The old mv-eject called Gio.UnixMountMonitor.get().get_mounts(), which
    no longer exists in PyGObject (measured 3.56.3 / GLib 2.88: not
    get_mounts, not get_mount_list, not get_mount_for_path). Every run
    died with an AttributeError, so the Finder "Eject" action and
    Super+F4 were dead. These tests parse real /proc/self/mountinfo
    instead and require the resolution layer to be pure Python, so it can
    never depend on a trimmed GObject introspection again.
  * The old fallback shelled out with os.system("umount %r ...") — a
    Python repr pasted into /bin/sh. argv is asserted here.
  * There is no polkit agent and no udisks2 in the ISO, so no privileged
    action could be authorized at all. The packaging gates below are the
    only thing that would have caught it.

Read-only: no mount is unmounted and no device is ejected. The execution
backends are exercised only against an injected fake.

Usage: python3 scripts/test-mv-eject.py
Exit 0 = all tests passed."""
import importlib.util
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless today, but arm the host-display guard so a future GUI path
# dies with HOST-DISPLAY-BLOCKED instead of touching the user's desktop.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

EJECT = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-eject")
MAKEFILE = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile")
PKGS = os.path.join(REPO, "archiso-profile/releng/packages.x86_64")
UCA = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/config/thunar-uca.xml")
KB = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml")
POLKIT_SRC = os.path.join(REPO, "configs/desktop/polkit/polkit-gnome-authentication-agent-1.desktop")
POLKIT_SKEL = os.path.join(REPO, "archiso-profile/releng/airootfs/etc/skel/.config/autostart/polkit-gnome-authentication-agent-1.desktop")

FAILURES = []
PASSED = 0

SAMPLE = """\
25 30 0:21 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw
31 1 259:1 / / rw,relatime - ext4 /dev/nvme0n1p2 rw
40 25 0:44 / /run/media/user/STICK rw,nosuid,nodev,relatime - vfat /dev/sdb1 rw
41 25 0:45 / /run/media/user/BIG\\040DISK rw,relatime - exfat /dev/sdc1 rw
42 40 0:46 /sub /run/media/user/STICK/nested rw,relatime - vfat /dev/sdb1 rw
"""


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


def load():
    spec = importlib.util.spec_from_loader("mv_eject", loader=None)
    mod = importlib.util.module_from_spec(spec)
    with open(EJECT, encoding="utf-8") as fh:
        src = fh.read().replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    exec(compile(src, EJECT, "exec"), mod.__dict__)
    return mod


def test_parse(m):
    entries = m.parse_mountinfo(SAMPLE)
    check("parse: 5 entries", len(entries) == 5, "got %d" % len(entries))
    by_point = {e.mount_point: e for e in entries}
    check("parse: root device resolved",
          by_point["/"].source == "/dev/nvme0n1p2", by_point["/"].source)
    check("parse: vfat mount", by_point["/run/media/user/STICK"].fs_type == "vfat")
    check("parse: exfat device", by_point["/run/media/user/BIG DISK"].source == "/dev/sdc1",
          repr(by_point["/run/media/user/BIG DISK"].source))
    check("parse: nested bind mount keeps its own root",
          by_point["/run/media/user/STICK/nested"].root == "/sub",
          by_point["/run/media/user/STICK/nested"].root)
    check("parse: malformed lines are skipped, not fatal",
          len(m.parse_mountinfo("garbage\n\nbroken - line\n")) == 0)
    check("parse: optional fields tolerated",
          m.parse_mountinfo("7 6 8:1 / /a rw - ext4 /dev/x")[0].mount_point == "/a")


def test_escapes(m):
    check("escapes: octal space decoded", m.unescape_mountinfo("/a\\040b") == "/a b")
    check("escapes: backslash decoded", m.unescape_mountinfo("a\\134b") == "a\\b")
    check("escapes: tab + newline decoded",
          m.unescape_mountinfo("a\\011b\\012c") == "a\tb\nc")


def test_resolution(m):
    entries = m.parse_mountinfo(SAMPLE)
    check("resolve: exact mount point",
          m.resolve_target(entries, "/run/media/user/STICK").fs_type == "vfat")
    check("resolve: longest prefix wins (nested over parent)",
          m.resolve_target(entries,
                           "/run/media/user/STICK/nested/deep/file").mount_point
          == "/run/media/user/STICK/nested")
    check("resolve: directory inside a mount resolves",
          m.resolve_target(entries, "/run/media/user/STICK/sub").mount_point
          == "/run/media/user/STICK")
    check("resolve: device file argument resolves",
          m.resolve_target(entries, "/dev/sdb1").mount_point
          == "/run/media/user/STICK")
    check("resolve: path with a space resolves",
          m.resolve_target(entries, "/run/media/user/BIG DISK").fs_type == "exfat")
    # The root-swallows-everything trap: a non-existent path used to match
    # '/' and be politely refused instead of reporting "no mount found".
    check("resolve: unmatched path is NOT the root filesystem",
          m.resolve_target(entries, "/nonexistent-xyz-123") is None)
    check("resolve: / still resolves to /",
          m.resolve_target(entries, "/").mount_point == "/")
    check("resolve: trailing slash tolerated",
          m.resolve_target(entries, "/run/media/user/STICK/").mount_point
          == "/run/media/user/STICK")


def test_plan(m):
    entries = m.parse_mountinfo(SAMPLE)
    stick = [e for e in entries if e.mount_point == "/run/media/user/STICK"][0]

    steps, reason = m.eject_plan(stick, has_udisks_fs=True, drive_ejectable=True)
    check("plan: udisks unmount then real eject",
          [s[0] for s in steps] == ["udisks-unmount", "udisks-eject"],
          str([s[0] for s in steps]))
    check("plan: nothing refused when allowed", reason is None, str(reason))

    steps, _ = m.eject_plan(stick, has_udisks_fs=True, drive_ejectable=False)
    check("plan: non-ejectable drive unmounts only",
          [s[0] for s in steps] == ["udisks-unmount"])

    steps, _ = m.eject_plan(stick, has_udisks_fs=False, drive_ejectable=False)
    check("plan: falls back to umount when udisks knows nothing",
          [s[0] for s in steps] == ["umount"])

    steps, _ = m.eject_plan(stick, has_udisks_fs=False, drive_ejectable=True)
    check("plan: ejectable drive still ejected after umount",
          [s[0] for s in steps] == ["umount", "udisks-eject"])

    root = [e for e in entries if e.mount_point == "/"][0]
    steps, reason = m.eject_plan(root, True, True)
    check("plan: refuses the root filesystem", steps == [] and "system mount" in reason,
          str(reason))

    proc_m = m.MountEntry(1, 0, "0:21", "/", "/proc", ["rw"], "proc", "proc", ["rw"])
    steps, reason = m.eject_plan(proc_m, True, True)
    check("plan: refuses pseudo filesystems", steps == [] and "cannot be ejected" in reason,
          str(reason))

    boot = m.MountEntry(2, 1, "8:1", "/", "/boot", ["rw"], "ext4", "/dev/sda1", ["rw"])
    steps, reason = m.eject_plan(boot, True, True)
    check("plan: refuses /boot", steps == [], str(reason))


def test_umount_argv(m):
    check("umount: plain argv, no shell string",
          m.umount_args("/run/media/user/My Stick") == ["umount", "/run/media/user/My Stick"])
    check("umount: lazy variant",
          m.umount_args("/media/x", lazy=True) == ["umount", "-l", "/media/x"])
    check("umount: a quote in the path is just an argument",
          m.umount_args("/media/it's; rm -rf /")[-1] == "/media/it's; rm -rf /")
    check("umount: no os.system in executable code",
          "os.system" not in executable_source())


def test_error_classification(m):
    check("error: busy reads as busy",
          "in use" in m.classify_error(Exception(
              "GDBus.Error: Device or resource busy")))
    check("error: polkit denial never leaks GDBus text",
          m.classify_error(Exception(
              "GDBus.Error:org.freedesktop.DBus.Error.NotAuthorized: "
              "Rejected send message")) == "policy does not allow ejecting this volume",
          m.classify_error(Exception(
              "GDBus.Error:org.freedesktop.DBus.Error.NotAuthorized: "
              "Rejected send message")))
    check("error: InvalidArgs reported as its first line",
          m.classify_error(Exception(
              "GDBus.Error:org.freedesktop.DBus.Error.InvalidArgs: Type of "
              "message, \"()\", does not match expected type \"(a{sv})\" (16)")
          ).startswith("GDBus.Error"))


def executable_source():
    """Only the strings and attributes that actually run.

    The module docstring quotes the dead APIs on purpose (it is the record
    of what was broken), and a docstring is an ordinary string Constant in
    the AST, so the docstrings are skipped explicitly. Grepping the raw
    file would report every one of them as live code.
    """
    import ast
    with open(EJECT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    parts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                parts.append(node.value)
        elif isinstance(node, ast.Attribute):
            parts.append(node.attr)
    return "\n".join(parts)


def test_no_deprecated_gio(m):
    code = executable_source()
    # The specific API whose absence broke the old implementation.
    check("source: no UnixMountMonitor call at all",
          "UnixMountMonitor" not in code,
          "the trimmed-introspection call is back")
    check("source: no async unmount with no main loop",
          "unmount_with_operation" not in code)
    check("source: no get_mounts() on a monitor",
          "get_mounts" not in code and "get_mount_list" not in code)
    check("source: uses /proc/self/mountinfo for resolution",
          "/proc/self/mountinfo" in code)


def test_variant_decoding(m):
    """UDisks2 hands back NUL-terminated byte arrays; every path lookup
    silently missed until the terminator was stripped."""
    check("variant: str passthrough", m._as_text("/media/x") == "/media/x")
    check("variant: bytes decoded", m._as_text(b"/media/x") == "/media/x")
    check("variant: byte-array ints decoded and NUL-stripped",
          m._as_text([47, 109, 116, 100, 0]) == "/mtd")
    check("variant: nested (ay) unwrapped",
          m._as_text([[47, 109, 116, 100, 0]]) == "/mtd")
    check("variant: (aay) becomes a list",
          m._as_text_list([[47, 109, 116, 100, 0], [47, 0]]) == ["/mtd", "/"])
    check("variant: None stays None", m._as_text(None) is None)
    check("variant: empty list is empty, not a crash",
          m._as_text_list(None) == [])


def test_execution_with_fake(m):
    """Run the real eject_one() against injected fakes — no mount touched."""
    entries = m.parse_mountinfo(SAMPLE)
    calls = []

    class FakeUDisks:
        def __init__(self, *a, **kw):
            pass

        def fs_for_mount_point(self, mp):
            return "/org/freedesktop/UDisks2/block_devices/sdb1"

        def block_for_device(self, dev):
            return "/org/freedesktop/UDisks2/block_devices/sdb1"

        def drive_for_block(self, blk):
            return "/org/freedesktop/UDisks2/drives/Generic_Flash"

        def drive_is_ejectable(self, drive):
            return True

        def unmount(self, fs):
            calls.append(("unmount", fs))

        def eject(self, drive):
            calls.append(("eject", drive))

    seq = {"n": 0}

    def fake_read(path=None):
        # First read resolves, the post-check read sees it gone.
        seq["n"] += 1
        if seq["n"] == 1:
            return entries
        return [e for e in entries
                if e.mount_point != "/run/media/user/STICK"]

    m.UDisks = FakeUDisks
    m.read_mountinfo = fake_read
    rc, message = m.eject_one("/run/media/user/STICK")
    check("execute: udisks unmount called", ("unmount",
          "/org/freedesktop/UDisks2/block_devices/sdb1") in calls, str(calls))
    check("execute: drive eject called", ("eject",
          "/org/freedesktop/UDisks2/drives/Generic_Flash") in calls, str(calls))
    check("execute: reports success", rc == 0 and "Ejected" in message, message)

    calls.clear()
    m.UDisks = FakeUDisks
    seq["n"] = 0
    rc, message = m.eject_one("/nonexistent-xyz-123")
    check("execute: unknown target is an error, not a silent root refusal",
          rc == 1 and "No mount found" in message, message)


def test_cli(m):
    r = subprocess.run([sys.executable, EJECT], capture_output=True, text=True)
    check("cli: no arguments is a usage error", r.returncode == 1, r.stdout)
    r = subprocess.run([sys.executable, EJECT, "--status", "/"],
                       capture_output=True, text=True, timeout=30)
    check("cli: --status exits 0", r.returncode == 0, r.stderr)
    check("cli: --status reports mountinfo", "mountinfo:" in r.stdout, r.stdout)
    check("cli: --status reports the polkit/udisks backend line",
          "udisks2:" in r.stdout or "umount(8):" in r.stdout, r.stdout)
    r = subprocess.run([sys.executable, EJECT, "--dry-run", "/"],
                       capture_output=True, text=True, timeout=30)
    check("cli: refuses the root filesystem", r.returncode == 1
          and "system mount" in r.stderr, r.stderr)


def test_packaging():
    mk = open(MAKEFILE, encoding="utf-8").read()
    check("packaging: Makefile installs mv-eject", "bin/mv-eject" in mk)
    pkgs = open(PKGS, encoding="utf-8").read()
    # Without these two the eject and power paths are unauthenticated dead
    # ends: no agent can grant org.freedesktop.login1.power-off and no
    # UDisks2 object exists to eject through.
    check("packaging: polkit in ISO", "\npolkit\n" in "\n" + pkgs + "\n")
    check("packaging: polkit-gnome agent in ISO",
          "\npolkit-gnome\n" in "\n" + pkgs + "\n")
    check("packaging: udisks2 in ISO", "\nudisks2\n" in "\n" + pkgs + "\n")
    for path, label in ((POLKIT_SRC, "configs source"),
                        (POLKIT_SKEL, "airootfs skel")):
        check("packaging: polkit autostart exists (%s)" % label,
              os.path.isfile(path))
    src = open(POLKIT_SRC, encoding="utf-8").read()
    check("packaging: autostart points at the real agent binary",
          "Exec=/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1" in src)
    check("packaging: autostart is limited to XFCE",
          "OnlyShowIn=XFCE;" in src)
    check("packaging: autostart is hidden", "NoDisplay=true" in src)
    check("packaging: mirrors are byte-identical",
          open(POLKIT_SRC, "rb").read() == open(POLKIT_SKEL, "rb").read())
    uca = open(UCA, encoding="utf-8").read()
    check("packaging: Eject action wired to mv-eject",
          "<command>mv-eject \"%f\"</command>" in uca)
    kb = open(KB, encoding="utf-8").read()
    check("packaging: Super+F4 still binds mv-eject",
          'name="&lt;Super&gt;F4" type="string" value="mv-eject"' in kb)
    check("packaging: no shell-out via os.system in executable code",
          "os.system" not in executable_source())
    check("packaging: eject does not reach for pkexec/sudo",
          "pkexec" not in executable_source()
          and "sudo" not in executable_source())


def main():
    print("=== mv-eject ===")
    m = load()
    test_parse(m)
    test_escapes(m)
    test_resolution(m)
    test_plan(m)
    test_umount_argv(m)
    test_error_classification(m)
    test_no_deprecated_gio(m)
    test_variant_decoding(m)
    test_execution_with_fake(m)
    test_cli(m)
    test_packaging()
    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())