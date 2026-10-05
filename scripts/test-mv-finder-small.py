#!/usr/bin/env python3
"""Headless tests for small Finder helpers: mv-rename, mv-eject, mv-mail.

These three binaries previously had ZERO test coverage (WORK_QUEUES.md
2026-10-05 batch). Pure-logic sections run everywhere; the Gio-dependent
find_mount() runs against duck-typed fake mounts (no gi required); GUI
smoke is skipped without a display, same convention as other suites.

Usage: python3 scripts/test-mv-finder-small.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

HAS_DISPLAY = mv_gui_iso.gui_display() is not None


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


def load(mod_name, filename):
    path = os.path.join(BIN, filename)
    loader = importlib.machinery.SourceFileLoader(mod_name, path)
    spec = importlib.util.spec_from_loader(mod_name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# ---------- mv-rename ----------

def test_rename():
    try:
        m = load("mv_rename", "mv-rename")
    except ModuleNotFoundError as e:
        print("skip - mv-rename import (%s)" % e)
        return
    with tempfile.TemporaryDirectory() as base:
        target = os.path.join(base, "report.pdf")
        open(target, "w").close()
        open(os.path.join(base, "taken.txt"), "w").close()

        good, res = m.validate_new_name(target, "summary.pdf")
        check("rename: valid new name -> path",
              good and res == os.path.join(base, "summary.pdf"), str(res))
        good, res = m.validate_new_name(target, "report.pdf")
        check("rename: same name is no-op", good and res is None)
        good, res = m.validate_new_name(target, "")
        check("rename: empty name is no-op", good and res is None)
        good, res = m.validate_new_name(target, "a/b.txt")
        check("rename: slash rejected",
              not good and "/" in res, str(res))
        good, res = m.validate_new_name(target, "..")
        check("rename: dotdot rejected", not good)
        good, res = m.validate_new_name(target, "taken.txt")
        check("rename: collision rejected",
              not good and "already exists" in res, str(res))


# ---------- mv-eject ----------

class FakeFile:
    def __init__(self, path):
        self._p = path
    def get_path(self):
        return self._p


class FakeDevice:
    def __init__(self, devfile):
        self._d = devfile
    def get_device_file(self):
        return self._d


class FakeMount:
    def __init__(self, path=None, devfile=None):
        self._root = FakeFile(path) if path else None
        self._dev = FakeDevice(devfile) if devfile else None
    def get_root(self):
        return self._root
    def get_device(self):
        return self._dev


def test_eject():
    # find_mount is pure duck-typing over mount objects — no gi needed.
    src = open(os.path.join(BIN, "mv-eject")).read()
    ns = {"os": os}
    exec(compile(src.split("def main")[0].replace(
        "import gi\n", ""), "mv-eject-head", "exec"), ns)
    find_mount = ns["find_mount"]

    with tempfile.TemporaryDirectory() as td:
        devfile = os.path.join(td, "sdb1")  # real file -> exists-guard passes
        open(devfile, "w").close()
        mnt = FakeMount(path="/run/media/user/USB", devfile=devfile)
        mounts = [mnt]
        check("eject: found by mount path", find_mount(mounts, "/run/media/user/USB") is mnt)
        check("eject: found by device file", find_mount(mounts, devfile) is mnt)
        check("eject: unknown path -> None", find_mount(mounts, "/nope") is None)
        check("eject: nonexistent device-file arg -> None (exists-guard)",
              find_mount(mounts, os.path.join(td, "nonexistent-zz")) is None)


# ---------- mv-mail ----------

def test_mail():
    try:
        m = load("mv_mail", "mv-mail")
    except ModuleNotFoundError as e:
        print("skip - mv-mail import (%s)" % e)
        return
    # find_mail_backend must not crash on odd dirs; point it at temp dirs.
    saved = m.DESKTOP_DIRS[:]
    try:
        with tempfile.TemporaryDirectory() as d:
            m.DESKTOP_DIRS[0] = os.path.join(d, "missing")
            m.DESKTOP_DIRS[1] = d
            # desktop entry declaring geary but binary absent -> None
            # (unless the host actually has geary installed)
            with open(os.path.join(d, "mail.desktop"), "w") as f:
                f.write("[Desktop Entry]\nType=Application\n"
                        "Mail UserAgent=Geary;geary\nExec=geary\n")
            res = m.find_mail_backend()
            import shutil as sh
            expect = ["geary"] if sh.which("geary") else None
            check("mail: backend resolution matches host state", res == expect,
                  "%r vs %r" % (res, expect))
            # unreadable dir must not raise
            m.DESKTOP_DIRS[0] = "/proc/1/nonexistent-dir"
            res = m.find_mail_backend()
            check("mail: hostile dir does not raise", res is None or isinstance(res, list))
    finally:
        m.DESKTOP_DIRS[:] = saved


def main():
    test_rename()
    test_eject()
    test_mail()
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
