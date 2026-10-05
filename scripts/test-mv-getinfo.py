#!/usr/bin/env python3
"""Headless tests for mv-getinfo (Finder-like Get Info dialog).

Since the 2026-10-05 lazy-Gtk refactor the pure helpers (format_size,
format_permissions, format_time, get_file_kind) import without PyGObject;
this suite blocks `gi` to prove that and pins their behavior, including the
setuid/setgid/sticky permission bits that the original code rendered wrong.

Usage: python3 scripts/test-mv-getinfo.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import stat
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless app-suite: no window today, but app code and child
# interpreters run with the ambient environment — on WSLg that is
# the user's Windows desktop.  Arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED (oid
# OS-window-leak2) instead of popping a window on the host.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")


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


class _BlockGi:
    def find_spec(self, name, path=None, target=None):
        if name == "gi" or name.startswith("gi."):
            raise ImportError("blocked by test: %s" % name)
        return None


def load(mod_name, filename, block_gi=True):
    if block_gi:
        sys.meta_path.insert(0, _BlockGi())
    try:
        path = os.path.join(BIN, filename)
        loader = importlib.machinery.SourceFileLoader(mod_name, path)
        spec = importlib.util.spec_from_loader(mod_name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        if block_gi:
            sys.meta_path.remove(sys.meta_path[0])


def main():
    try:
        m = load("mv_getinfo", "mv-getinfo")
        ok("mv-getinfo imports headless (gi blocked)")
    except Exception as e:
        bad("mv-getinfo imports headless (gi blocked)", repr(e))
        print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
        return 1

    # --- format_size ---
    check("size: 0 B", m.format_size(0) == "0.0 B", m.format_size(0))
    check("size: 512 B", m.format_size(512) == "512.0 B", m.format_size(512))
    check("size: 1023 B stays bytes", m.format_size(1023).endswith("B")
          and "KB" not in m.format_size(1023), m.format_size(1023))
    check("size: 1 KB", m.format_size(1024) == "1.0 KB", m.format_size(1024))
    check("size: 1536 -> 1.5 KB", m.format_size(1536) == "1.5 KB",
          m.format_size(1536))
    check("size: MB", m.format_size(5 * 1024 * 1024) == "5.0 MB",
          m.format_size(5 * 1024 * 1024))
    check("size: GB", m.format_size(3 * 1024 ** 3) == "3.0 GB",
          m.format_size(3 * 1024 ** 3))
    check("size: TB", m.format_size(2 * 1024 ** 4) == "2.0 TB",
          m.format_size(2 * 1024 ** 4))
    check("size: PB", m.format_size(1024 ** 5) == "1.0 PB",
          m.format_size(1024 ** 5))

    # --- format_permissions: file-type prefixes ---
    check("perm: regular 755", m.format_permissions(stat.S_IFREG | 0o755)
          == "-rwxr-xr-x", m.format_permissions(stat.S_IFREG | 0o755))
    check("perm: dir 755", m.format_permissions(stat.S_IFDIR | 0o755)
          == "drwxr-xr-x", m.format_permissions(stat.S_IFDIR | 0o755))
    check("perm: link 777", m.format_permissions(stat.S_IFLNK | 0o777)
          == "lrwxrwxrwx", m.format_permissions(stat.S_IFLNK | 0o777))
    check("perm: fifo", m.format_permissions(stat.S_IFIFO | 0o644)
          == "prw-r--r--", m.format_permissions(stat.S_IFIFO | 0o644))
    check("perm: sock", m.format_permissions(stat.S_IFSOCK | 0o600)
          == "srw-------", m.format_permissions(stat.S_IFSOCK | 0o600))
    check("perm: blk", m.format_permissions(stat.S_IFBLK | 0o640)
          == "brw-r-----", m.format_permissions(stat.S_IFBLK | 0o640))
    check("perm: chr", m.format_permissions(stat.S_IFCHR | 0o666)
          == "crw-rw-rw-", m.format_permissions(stat.S_IFCHR | 0o666))
    check("perm: 000", m.format_permissions(stat.S_IFREG | 0o000)
          == "----------", m.format_permissions(stat.S_IFREG | 0o000))

    # --- setuid / setgid / sticky (the bug class this refactor fixed) ---
    suid_x = m.format_permissions(stat.S_IFREG | 0o755 | stat.S_ISUID)
    check("perm: setuid+exec -> 's' user slot", suid_x == "-rwsr-xr-x", suid_x)
    suid_nox = m.format_permissions(stat.S_IFREG | 0o644 | stat.S_ISUID)
    check("perm: setuid no-exec -> 'S'", suid_nox == "-rwSr--r--", suid_nox)
    sgid_x = m.format_permissions(stat.S_IFREG | 0o755 | stat.S_ISGID)
    check("perm: setgid+exec -> 's' group slot", sgid_x == "-rwxr-sr-x", sgid_x)
    sgid_nox = m.format_permissions(stat.S_IFREG | 0o664 | stat.S_ISGID)
    check("perm: setgid no-exec -> 'S' group slot", sgid_nox == "-rw-rwSr--",
          sgid_nox)
    sticky_x = m.format_permissions(stat.S_IFDIR | 0o755 | stat.S_ISVTX)
    check("perm: sticky+exec -> 't' other slot", sticky_x == "drwxr-xr-t",
          sticky_x)
    sticky_nox = m.format_permissions(stat.S_IFDIR | 0o754 | stat.S_ISVTX)
    check("perm: sticky no-exec -> 'T'", sticky_nox == "drwxr-xr-T", sticky_nox)
    combo = m.format_permissions(stat.S_IFDIR | 0o755 | stat.S_ISUID
                                 | stat.S_ISGID | stat.S_ISVTX)
    check("perm: all specials at once", combo == "-rwsr-sr-t".replace("-", "d", 1)
          or combo == "drwsr-sr-t", combo)

    # --- format_time: deterministic shape, real epoch semantics ---
    out = m.format_time(0)
    check("time: returns non-empty str", isinstance(out, str) and len(out) > 0,
          repr(out))
    known = int(time.time())
    a = m.format_time(known)
    b = m.format_time(known)
    check("time: same ts -> same string", a == b, "%r vs %r" % (a, b))
    check("time: contains digits", any(c.isdigit() for c in a), a)

    # --- get_file_kind ---
    check("kind: txt -> Text file", m.get_file_kind("/x/y/report.txt") == "Text file",
          m.get_file_kind("/x/y/report.txt"))
    check("kind: png -> Image file", m.get_file_kind("/a/b.PNG") == "Image file",
          m.get_file_kind("/a/b.PNG"))
    check("kind: pdf -> Application file", m.get_file_kind("doc.pdf") == "Application file",
          m.get_file_kind("doc.pdf"))
    check("kind: existing dir -> Folder", m.get_file_kind("/tmp") == "Folder",
          m.get_file_kind("/tmp"))
    kind_unknown = m.get_file_kind("/no/such/weird.zzzq")
    check("kind: unknown ext -> non-empty label",
          isinstance(kind_unknown, str) and len(kind_unknown) > 0, kind_unknown)

    # --- GUI factory stays lazy (must refuse without gi) ---
    try:
        m.build_getinfo_class()
        bad("build_getinfo_class requires gi (lazy)", "worked without gi?!")
    except (ImportError, RuntimeError):
        ok("build_getinfo_class requires gi (lazy)")

    # --- main() without args must exit gracefully with usage error ---
    saved_argv = sys.argv
    try:
        sys.argv = ["mv-getinfo"]
        rc = m.main()
        check("main: no args -> rc 1", rc == 1, repr(rc))
    except Exception as e:
        bad("main: no args -> rc 1", repr(e))
    finally:
        sys.argv = saved_argv

    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
