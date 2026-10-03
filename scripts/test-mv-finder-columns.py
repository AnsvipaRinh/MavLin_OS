#!/usr/bin/env python3
"""Headless tests for mv-finder-columns (Finder column-view companion).

Pure-logic section:
- list_entries: folders first, case-insensitive name order, hidden handling,
  stat sizes, unreadable dir raises OSError

GUI smoke (real GTK, needs display):
- window construction builds one column with the right rows
- keep_depth truncation collapses the chain
- unreadable root shows error state (not a crash)

Usage: python3 scripts/test-mv-finder-columns.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns")

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
IS_ROOT = os.geteuid() == 0


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_finder_columns", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_finder_columns", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def make_tree(base):
    root = os.path.join(base, "root")
    os.makedirs(os.path.join(root, "Zebra"))
    os.makedirs(os.path.join(root, "apple"))
    os.makedirs(os.path.join(root, ".git"))
    for path in (os.path.join(root, "README.md"),
                 os.path.join(root, "banana.txt"),
                 os.path.join(root, "apple", "pie.txt")):
        with open(path, "w") as f:
            f.write("x" * 2048)
    return root


def test_pure(m):
    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        entries = m.list_entries(root)
        names = [e["name"] for e in entries]
        check("columns: folders first",
              names[:2] == ["apple", "Zebra"], str(names))
        check("columns: casefold file order",
              names[2:] == ["banana.txt", "README.md"], str(names))
        check("columns: hidden excluded", ".git" not in names)
        entries = m.list_entries(root, include_hidden=True)
        check("columns: hidden included on request",
              ".git" in [e["name"] for e in entries])
        flags = [e["is_dir"] for e in entries]
        check("columns: is_dir flags",
              flags[:1] == [True] and flags[-1:] == [False], str(flags))
        check("columns: file sizes present",
              all(e["size"] == 2048 for e in entries if not e["is_dir"]))
        check("columns: dir size zero",
              all(e["size"] == 0 for e in entries if e["is_dir"]))

        if not IS_ROOT:
            locked = os.path.join(base, "locked")
            os.makedirs(locked)
            os.chmod(locked, 0o000)
            try:
                m.list_entries(locked)
                bad("columns: unreadable raises OSError")
            except OSError:
                ok("columns: unreadable raises OSError")
            os.chmod(locked, 0o755)
        else:
            print("skip - unreadable dir test (running as root)")


def test_gui(m):
    if not HAS_DISPLAY:
        print("skip - GUI smoke (no display)")
        return
    from gi.repository import GLib, Gtk

    def quiet_destroy(win):
        win.disconnect_by_func(Gtk.main_quit)
        win.destroy()

    def pump():
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)

    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        win = m.ColumnsWindow(root)
        pump()
        check("gui: one column for root", len(win.listboxes) == 1)
        rows = win.listboxes[0].get_children()
        check("gui: rows built", [r.entry["name"] for r in rows] ==
              ["apple", "Zebra", "banana.txt", "README.md"],
              str([r.entry["name"] for r in rows]))

        # navigate into a folder (simulating row activation)
        win.chain.append(os.path.join(root, "apple"))
        win.rebuild_columns()
        pump()
        check("gui: second column added", len(win.listboxes) == 2)
        check("gui: status shows deepest folder", "apple" in win.status_label.get_text())

        # keep_depth truncation
        win.rebuild_columns(keep_depth=1)
        pump()
        check("gui: truncation collapses columns", len(win.listboxes) == 1)
        quiet_destroy(win)

        if not IS_ROOT:
            locked = os.path.join(base, "locked2")
            os.makedirs(locked)
            os.chmod(locked, 0o000)
            win2 = m.ColumnsWindow(locked)
            pump()
            check("gui: unreadable root -> error state",
                  "Could not open" in win2.error_label.get_text())
            quiet_destroy(win2)
            os.chmod(locked, 0o755)


def main():
    m = load_app()
    test_pure(m)
    test_gui(m)
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
