#!/usr/bin/env python3
"""Headless tests for mv-finder-search (Finder recursive search).

Pure-logic section (no GTK widgets, no live search):
- relevance ladder (exact/prefix/word-start/substring/none)
- case-insensitive matching, dotfile visibility conventions
- walk_results: nested + folder matches, hidden handling, result cap,
  unreadable dirs reported as skipped, symlinked dirs not followed
- parse_plocate_output: root filtering, basename-match filtering,
  hidden filtering, dedupe, cap
- choose_backend: plocate only for whole-home roots with binary present
- sort_results: folders first, case-insensitive name order
- format_size / file_kind labels

GUI smoke (real GTK, needs display):
- window construction with root + initial state
- full pipeline debounce -> worker thread -> idle apply (pumped main ctx)
- empty state on no results, skipped-dirs infobar reveal
- Escape clears query first, destroys window second
- Ctrl+F focuses the search entry

Usage: python3 scripts/test-mv-finder-search.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-search")

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
    loader = importlib.machinery.SourceFileLoader("mv_finder_search", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_finder_search", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def make_tree(base):
    """Sample tree:
       root/Reports/q1.txt        root/notes.md
       root/Photos/cat.png        root/.hidden/secret.txt
       root/docs/readme.txt       root/docs/notes-file.txt
       root/my-notes-dir/x.txt    root/link -> root/docs (symlink)
    """
    root = os.path.join(base, "root")
    os.makedirs(os.path.join(root, "Reports"))
    os.makedirs(os.path.join(root, "Photos"))
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, ".hidden"))
    os.makedirs(os.path.join(root, "my-notes-dir"))
    for path, content in (
            (os.path.join(root, "Reports", "q1.txt"), "q"),
            (os.path.join(root, "notes.md"), "n"),
            (os.path.join(root, "Photos", "cat.png"), "c"),
            (os.path.join(root, ".hidden", "secret.txt"), "s"),
            (os.path.join(root, ".secret-notes.txt"), "h"),
            (os.path.join(root, "docs", "readme.txt"), "r"),
            (os.path.join(root, "docs", "notes-file.txt"), "f"),
            (os.path.join(root, "my-notes-dir", "x.txt"), "x"),
    ):
        with open(path, "w") as f:
            f.write(content)
    os.symlink(os.path.join(root, "docs"), os.path.join(root, "link"))
    return root


def test_pure(m):
    # --- rank ladder ---
    check("rank: exact", m.rank_match("notes.md", "notes.md") == 0)
    check("rank: prefix", m.rank_match("not", "notes.md") == 1)
    check("rank: word-start", m.rank_match("file", "notes-file.txt") == 2)
    check("rank: word-start after dot", m.rank_match("png", "cat.png") == 2)
    check("rank: substring", m.rank_match("otes", "notes.md") == 3)
    check("rank: none", m.rank_match("zzz", "notes.md") == -1)
    check("rank: empty query never matches", m.rank_match("", "anything") == -1)
    check("rank: case-insensitive", m.rank_match("NOTES", "notes.md") == 1)

    # --- visibility ---
    check("visible: plain file", m.visible_entry("a.txt", False))
    check("visible: dotfile hidden by default", not m.visible_entry(".git", False))
    check("visible: dotfile with dot query", m.visible_entry(".git", True))
    check("auto_hidden: plain query", m.auto_hidden("abc") is False)
    check("auto_hidden: dot query", m.auto_hidden(".git") is True)

    # --- format_size ---
    check("size: bytes", m.format_size(0) == "0 B")
    check("size: kb", m.format_size(2048) == "2.0 KB")
    check("size: mb", m.format_size(5 * 1024 * 1024) == "5.0 MB")

    # --- file_kind ---
    check("kind: folder", m.file_kind("x", True) == "Folder")
    check("kind: png", m.file_kind("cat.png", False) == "PNG image")
    check("kind: pdf", m.file_kind("doc.pdf", False) == "PDF document")
    check("kind: txt", m.file_kind("notes.txt", False) == "Plain text document")
    check("kind: unknown ext", m.file_kind("data.xyz123", False) == "Document")

    # --- walk_results ---
    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        results, skipped = m.walk_results(root, "notes")
        names = sorted(r["name"] for r in results)
        check("walk: finds nested + root matches (incl. folder name)",
              names == ["my-notes-dir", "notes-file.txt", "notes.md"], str(names))
        check("walk: path contains but basename lacks -> still matched only by name",
              all(r["name"] != "x.txt" for r in results))
        check("walk: no skipped in readable tree", skipped == [])
        check("walk: paths under root",
              all(r["path"].startswith(root) for r in results))

        results, _ = m.walk_results(root, "notes.md")
        check("walk: exact single hit", [r["name"] for r in results] == ["notes.md"])

        # folder match: searching a dir name returns the dir itself
        results, _ = m.walk_results(root, "reports")
        check("walk: folder itself matches", any(
            r["is_dir"] and r["name"] == "Reports" for r in results))

        # hidden not searched by default
        results, _ = m.walk_results(root, "secret")
        check("walk: hidden excluded by default", results == [])
        # hidden searched with dot query
        results, _ = m.walk_results(root, ".hidden")
        check("walk: hidden dir found via dot query", any(
            r["name"] == ".hidden" for r in results))
        results, _ = m.walk_results(root, ".secret-notes")
        check("walk: hidden file found via dot query", any(
            r["name"] == ".secret-notes.txt" for r in results))

        # symlinked dir: matched by its own name, contents not followed
        results, _ = m.walk_results(root, "link")
        check("walk: symlink dir matched", any(r["name"] == "link" for r in results))
        check("walk: symlink dir not traversed", not any(
            os.sep + "link" + os.sep in r["path"] for r in results))

        # empty query matches nothing (search is name-driven)
        results, _ = m.walk_results(root, "")
        check("walk: empty query matches nothing", results == [])

        # cap
        for i in range(10):
            with open(os.path.join(root, "match%d.txt" % i), "w") as f:
                f.write("x")
        results, _ = m.walk_results(root, "match", max_results=4)
        check("walk: result cap respected", len(results) == 4)

        # unreadable dir -> skipped list (perms are advisory to root)
        if not IS_ROOT:
            locked = os.path.join(root, "locked")
            os.makedirs(locked)
            with open(os.path.join(locked, "match-inside.txt"), "w") as f:
                f.write("x")
            os.chmod(locked, 0o000)
            results, skipped = m.walk_results(root, "match")
            check("walk: unreadable dir skipped", locked in skipped,
                  str(skipped))
            check("walk: unreadable dir contents not listed", not any(
                "match-inside" in r["path"] for r in results))
            os.chmod(locked, 0o755)

    # --- parse_plocate_output ---
    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        lines = "\n".join([
            os.path.join(root, "notes.md"),
            os.path.join(root, "docs", "notes-file.txt"),
            os.path.join(root, "my-notes-dir", "x.txt"),   # basename no match
            os.path.join(root, ".hidden", "notes.md.bak"),  # hidden
            os.path.join(root, "Reports", "q1.txt"),        # no match at all
            "/etc/passwd",                                  # outside root
            os.path.join(root, "notes.md"),                 # duplicate
        ])
        parsed = m.parse_plocate_output(lines, root, "notes")
        names = sorted(r["name"] for r in parsed)
        check("plocate: basename matches kept",
              names == ["notes-file.txt", "notes.md"], str(names))
        check("plocate: outside root dropped",
              all(r["path"].startswith(root) for r in parsed))
        check("plocate: hidden dropped", all(
            "/.hidden/" not in r["path"] for r in parsed))
        check("plocate: no basename match dropped",
              all(r["name"] not in ("x.txt", "q1.txt") for r in parsed))
        check("plocate: dedupe",
              len(parsed) == len(set(r["path"] for r in parsed)))
        capped = m.parse_plocate_output(lines, root, "notes", max_results=1)
        check("plocate: cap", len(capped) == 1)

    # --- choose_backend ---
    home = os.path.expanduser("~")
    check("backend: home with plocate binary",
          m.choose_backend(home, home, "/usr/bin/plocate") == "plocate")
    check("backend: non-home always walk",
          m.choose_backend("/tmp", home, "/usr/bin/plocate") == "walk")
    check("backend: home without plocate binary",
          m.choose_backend(home, home, "") == "walk")

    # --- sort_results ---
    ordered = m.sort_results([
        {"is_dir": False, "name": "b.txt"},
        {"is_dir": True, "name": "zed"},
        {"is_dir": False, "name": "Apple"},
        {"is_dir": True, "name": "Beta"},
    ])
    check("sort: folders first then casefold",
          [r["name"] for r in ordered] == ["Beta", "zed", "Apple", "b.txt"])

    # --- zoom ladder ---
    check("zoom: default is ladder start", m.ZOOM_DEFAULT == m.ZOOM_LADDER[0])
    check("zoom: step up", m.zoom_step(16, +1) == 22)
    check("zoom: step down", m.zoom_step(22, -1) == 16)
    check("zoom: clamp at top", m.zoom_step(48, +1) == 48)
    check("zoom: clamp at bottom", m.zoom_step(16, -1) == 16)
    check("zoom: unknown size snaps near default",
          m.zoom_step(999, +1) == 22 and m.zoom_step(999, -1) == 16)


class FakeEvent:
    def __init__(self, keyval, state=0):
        self.keyval = keyval
        self.state = state


def test_gui(m):
    if not HAS_DISPLAY:
        print("skip - GUI smoke (no display)")
        return
    from gi.repository import GLib, Gdk, Gtk
    FinderSearchWindow = m.build_search_window_class()

    def pump(win, seconds=3.0):
        ctx = GLib.MainContext.default()
        deadline = time.time() + seconds
        while time.time() < deadline and win.state != "done":
            ctx.iteration(False)
            time.sleep(0.01)

    with tempfile.TemporaryDirectory() as base:
        root = make_tree(base)
        win = FinderSearchWindow(root)
        check("gui: window constructed", win.get_title() == "Search")
        check("gui: idle empty state", "Type to search" in win.empty_label.get_text())

        win.entry.set_text("notes")
        win.start_search()
        pump(win)
        check("gui: search completes", win.state == "done")
        check("gui: result count", len(win.store) == 3, str(len(win.store)))
        rows = [(win.store[i][1], win.store[i][2]) for i in range(len(win.store))]
        check("gui: rows populated",
              rows == [("my-notes-dir", "Folder"),
                       ("notes-file.txt", "Plain text document"),
                       ("notes.md", "Plain text document")], str(rows))

        win.apply_results("zzz", win.generation, [], [])
        check("gui: no-results empty state",
              "No results" in win.empty_label.get_text())

        win.apply_results("notes", win.generation, [],
                          ["/some/locked/dir", "/another/locked"])
        check("gui: skipped dirs reveal infobar", win.infobar.get_revealed())

        # Escape: clears query first, destroys window second
        destroyed = []
        win.connect("destroy", lambda *_: destroyed.append(True))
        win.disconnect_by_func(Gtk.main_quit)  # tests run outside Gtk.main()
        esc = FakeEvent(Gdk.keyval_from_name("Escape"))
        check("gui: escape handled",
              win.on_key_press(win, esc) is True)
        check("gui: escape clears text first", win.entry.get_text() == "")
        win.on_key_press(win, esc)
        check("gui: second escape destroys window", bool(destroyed))

        # Ctrl+F focuses the search entry
        win2 = FinderSearchWindow(root)
        ctrl_f = FakeEvent(Gdk.keyval_from_name("f"),
                           Gdk.ModifierType.CONTROL_MASK)
        check("gui: ctrl+f handled", win2.on_key_press(win2, ctrl_f) is True)

        # Zoom keyboard: Ctrl+= / Ctrl+- / Ctrl+0 (Finder app-level convention)
        zoom_in = FakeEvent(Gdk.keyval_from_name("equal"),
                            Gdk.ModifierType.CONTROL_MASK)
        zoom_out = FakeEvent(Gdk.keyval_from_name("minus"),
                             Gdk.ModifierType.CONTROL_MASK)
        zoom_norm = FakeEvent(Gdk.keyval_from_name("0"),
                              Gdk.ModifierType.CONTROL_MASK)
        win2.entry.set_text("notes")
        win2.start_search()
        pump(win2)
        rows_before = len(win2.store)
        size_before = win2.store[0][0].get_width() if rows_before else 0
        win2.on_key_press(win2, zoom_in)
        check("gui: ctrl+= zooms in", win2.icon_size == 22)
        check("gui: zoom rebuilds pixbufs", rows_before and
              win2.store[0][0].get_width() > size_before)
        check("gui: zoom preserves rows", len(win2.store) == rows_before)
        win2.on_key_press(win2, zoom_out)
        check("gui: ctrl+- zooms out", win2.icon_size == 16)
        win2.on_key_press(win2, zoom_norm)
        check("gui: ctrl+0 resets zoom", win2.icon_size == m.ZOOM_DEFAULT)
        win2.disconnect_by_func(Gtk.main_quit)
        win2.destroy()


def test_portable(m):
    """Headless portability contract: module and pure logic work without gi."""
    try:
        import gi  # noqa: F401
        has_gi = True
    except ImportError:
        has_gi = False
    check("portable: build_search_window_class exists",
          callable(getattr(m, "build_search_window_class", None)))
    if not has_gi:
        try:
            m.build_search_window_class()
            bad("portable: factory raises cleanly without gi")
        except Exception:
            ok("portable: factory raises cleanly without gi")
        check("portable: icon_for folder without gi",
              m.icon_for("anything", True) == "folder")
        check("portable: load_icon_pixbuf None without gi",
              m.load_icon_pixbuf("folder", 16) is None)
    else:
        print("skip - no-gi branch checks (gi present)")


def main():
    m = load_app()
    test_pure(m)
    test_portable(m)
    test_gui(m)
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
