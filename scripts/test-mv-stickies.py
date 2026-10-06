#!/usr/bin/env python3
"""Headless tests for mv-stickies.

Pure-logic section (no GTK widgets, no user store touched):
- color normalization/validation (#rrggbb, named colors, garbage)
- geometry clipping and store normalization (junk entries, bad types)
- store load/save round-trip, backup, quarantine of corrupt files
- pagination and note-title derivation

GUI smoke (real GTK, skipped headless):
- construction, default yellow note
- text edit persists to store; color change persists; headerbar title
- Ctrl+N new note, Delete confirm-destroy, Ctrl+P print-op setup
- collapse toggle persists; search window filter/jump/close
- relaunch guard (no duplicate notes); restore from store on launch
- last-window-destroy quits the app (main_quit)

Usage: python3 scripts/test-mv-stickies.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-stickies")

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
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_stickies", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_stickies", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_pure(m):
    check("normalize_color hex", m.normalize_color("#ff0000") == "#ff0000",
          m.normalize_color("#ff0000"))
    check("normalize_color named", m.normalize_color("red") == "#ff0000",
          m.normalize_color("red"))
    check("normalize_color rgb()",
          m.normalize_color("rgb(255,0,0)") == "#ff0000",
          m.normalize_color("rgb(255,0,0)"))
    check("normalize_color short hex",
          m.normalize_color("#f00") == "#ff0000", m.normalize_color("#f00"))
    check("normalize_color garbage",
          m.normalize_color("not-a-color") == m.DEFAULT_COLOR,
          m.normalize_color("not-a-color"))
    check("normalize_color empty",
          m.normalize_color("") == m.DEFAULT_COLOR)
    check("normalize_color non-str",
          m.normalize_color(None) == m.DEFAULT_COLOR
          and m.normalize_color(42) == m.DEFAULT_COLOR)

    check("clip_int normal", m._clip_int(50, 0, 100, 7) == 50)
    check("clip_int low", m._clip_int(-5, 0, 100, 7) == 0)
    check("clip_int high", m._clip_int(500, 0, 100, 7) == 100)
    check("clip_int junk", m._clip_int("x", 0, 100, 7) == 7)
    check("clip_int none", m._clip_int(None, 0, 100, 7) == 7)

    norm = m._normalize({"stickies": [
        {"id": "a", "text": "hi", "color": "red"},
        "junk",
        {"id": 5, "x": "bad", "w": 10, "h": 99999, "text": 42,
         "color": "garbage", "collapsed": "yes"},
    ]})
    check("normalize keeps dict entries", len(norm["stickies"]) == 2,
          str(len(norm["stickies"])))
    check("normalize defaults", norm["stickies"][0]["x"] == 100
          and norm["stickies"][0]["collapsed"] is False)
    check("normalize clips geometry", norm["stickies"][1]["w"] == 120
          and norm["stickies"][1]["h"] == 4096)
    check("normalize fixes text", norm["stickies"][1]["text"] == "")
    check("normalize fixes color",
          norm["stickies"][1]["color"] == m.DEFAULT_COLOR)
    check("normalize coerces collapsed",
          norm["stickies"][1]["collapsed"] is True)
    check("normalize non-dict", m._normalize("junk") == {"stickies": []})
    check("normalize missing list",
          m._normalize({}) == {"stickies": []})

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "stickies.json")
        data = {"stickies": [{"id": "a", "text": "one"}]}
        m.save_store(path=path, data=data)
        check("save creates file", os.path.exists(path))
        expected = m._normalize(data)
        check("load round-trip", m.load_store(path=path) == expected,
              str(m.load_store(path=path)))
        check("no backup on first save", not os.path.exists(path + ".bak"))
        m.save_store(path=path, data=data)
        check("save writes backup", os.path.exists(path + ".bak"))

        os.remove(path + ".bak")
        with open(path, "w") as f:
            f.write("{not json")
        warns = []
        loaded = m.load_store(path=path, on_warn=warns.append)
        check("corrupt quarantined", len(warns) == 1
              and "quarantined" in warns[0], str(warns))
        check("corrupt fresh store", loaded == {"stickies": []})
        leftovers = [f for f in os.listdir(tmp) if f.startswith("stickies")]
        check("corrupt file moved away", "stickies.json" not in leftovers,
              str(leftovers))

        with open(path + ".bak", "w") as f:
            f.write('{"stickies": [{"id": "b", "text": "from bak"}]}')
        with open(path, "w") as f:
            f.write("corrupt again")
        warns2 = []
        loaded2 = m.load_store(path=path, on_warn=warns2.append)
        check("backup restored", loaded2["stickies"][0]["id"] == "b",
              str(loaded2))
        check("backup restore warned", len(warns2) == 1
              and "backup" in warns2[0], str(warns2))

        check("missing file empty",
              m.load_store(path=os.path.join(tmp, "none.json"))
              == {"stickies": []})

        lock = os.path.join(tmp, "instance.lock")
        with mock.patch.object(m, "LOCK", lock):
            check("lock acquired", m.acquire_lock() is True)
            check("lock holds pid",
                  open(lock).read().strip() == str(os.getpid()))
            check("lock blocks second instance",
                  m.acquire_lock() is False)
            with open(lock, "w") as f:
                f.write("999999")
            check("lock stale taken over", m.acquire_lock() is True)
            with open(lock, "w") as f:
                f.write("not-a-pid")
            check("lock junk taken over", m.acquire_lock() is True)

    check("paginate splits", m.paginate("a\nb\nc", 2) == [["a", "b"], ["c"]])
    check("paginate exact", m.paginate("a\nb", 2) == [["a", "b"]])
    check("paginate empty", m.paginate("", 2) == [[""]])
    check("paginate long lines untouched",
          m.paginate("x" * 500, 42) == [["x" * 500]])

    check("title first line", m._note_title("hello\nworld") == "hello")
    check("title blank", m._note_title("   \n ") == "Sticky")
    check("title truncates", m._note_title("x" * 100) == "x" * 40)


def key_event(keyval, ctrl=False):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.keyval = keyval
    if ctrl:
        ev.state = Gdk.ModifierType.CONTROL_MASK
    return ev


def read_store(m, path):
    import json
    with open(path) as f:
        return json.load(f)


def test_gui(m):
    if not HAS_DISPLAY:
        print("SKIP - GUI smoke (no display)")
        return
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk

    with tempfile.TemporaryDirectory() as tmp:
        store_path = os.path.join(tmp, "stickies.json")
        with mock.patch.object(m, "STORE", store_path):
            app = m.StickiesApp()
            app.startup()
            Gtk.main_iteration_do(False)
            check("fresh launch one note", len(app.stickies) == 1,
                  str(len(app.stickies)))
            note = app.stickies[0]
            check("default color", note.color == m.DEFAULT_COLOR,
                  note.color)
            check("default text", note.text == "")

            note.buf.set_text("hello world")
            data = read_store(m, store_path)
            check("text persists", data["stickies"][0]["text"] == "hello world",
                  data["stickies"][0]["text"])
            check("title updates", note.hb.get_title() == "hello world",
                  note.hb.get_title())

            rgba = Gdk.RGBA()
            rgba.parse("#ff0000")
            note.color_btn.set_rgba(rgba)
            note.color_btn.emit("color-set")
            check("color change applied", note.color == "#ff0000", note.color)
            data = read_store(m, store_path)
            check("color persists", data["stickies"][0]["color"] == "#ff0000",
                  data["stickies"][0]["color"])

            note.emit("key-press-event", key_event(Gdk.KEY_n, ctrl=True))
            Gtk.main_iteration_do(False)
            check("ctrl+n new note", len(app.stickies) == 2,
                  str(len(app.stickies)))

            with mock.patch.object(m.Gtk, "MessageDialog") as MD:
                MD.return_value.run.return_value = Gtk.ResponseType.OK
                note.emit("key-press-event", key_event(Gdk.KEY_Delete))
            Gtk.main_iteration_do(False)
            check("delete confirm removes note", len(app.stickies) == 1,
                  str(len(app.stickies)))
            check("delete persists", len(read_store(m, store_path)["stickies"]) == 1)

            note = app.stickies[0]
            note.collapse_btn.clicked()
            check("collapse flag", note.collapsed is True)
            check("collapse hides editor", not note.sw.get_visible())
            data = read_store(m, store_path)
            check("collapse persists", data["stickies"][0]["collapsed"] is True,
                  str(data["stickies"][0].get("collapsed")))
            note.collapse_btn.clicked()
            check("expand restores", note.collapsed is False
                  and note.sw.get_visible())

            app.startup()
            check("relaunch no duplicates", len(app.stickies) == 1,
                  str(len(app.stickies)))

            m.cairo = mock.MagicMock()
            with mock.patch.object(m.Gtk, "PrintOperation") as PO:
                note.print_note(None)
                check("print op run", PO.return_value.run.called)
                args = PO.return_value.run.call_args[0]
                check("print dialog action",
                      args[0] == Gtk.PrintOperationAction.PRINT_DIALOG,
                      str(args))

            note.buf.set_text("alpha beta")
            app.create_sticky()
            app.stickies[-1].buf.set_text("gamma delta")
            app.open_search()
            sw = app.search_win
            check("search window open", sw is not None)
            check("search lists all", len(sw.store) == 2, str(len(sw.store)))
            sw.entry.set_text("gamma")
            rows = [sw.store[i][0] for i in range(len(sw.store))]
            check("search filters", len(rows) == 1 and "gamma" in rows[0],
                  str(rows))
            target = app.stickies[-1]
            with mock.patch.object(target, "present") as P:
                sw.on_jump(sw.tv, Gtk.TreePath.new_from_indices([0]), None)
                check("search jump presents note", P.called)
            sw.entry.emit("key-press-event", key_event(Gdk.KEY_Escape))
            Gtk.main_iteration_do(False)
            check("search escape closes", app.search_win is None)

            with mock.patch.object(m.Gtk, "main_quit") as Q:
                for s in list(app.stickies):
                    s.destroy()
                Gtk.main_iteration_do(False)
                check("last window quits app", Q.called)
            check("stickies list empty", len(app.stickies) == 0,
                  str(len(app.stickies)))

            restore = {"stickies": [{
                "id": "rest1", "x": 55, "y": 66, "w": 311, "h": 222,
                "text": "restored note", "color": "#00ff00",
                "collapsed": True}]}
            m.save_store(path=store_path, data=restore)
            app2 = m.StickiesApp()
            app2.startup()
            Gtk.main_iteration_do(False)
            check("restore one note", len(app2.stickies) == 1,
                  str(len(app2.stickies)))
            r = app2.stickies[0]
            check("restore text", r.text == "restored note", r.text)
            check("restore color", r.color == "#00ff00", r.color)
            check("restore geometry", (r.x, r.y) == (55, 66),
                  str((r.x, r.y)))
            check("restore collapsed", r.collapsed is True)
            check("restore title", r.hb.get_title() == "restored note",
                  r.hb.get_title())


def test_portable(m):
    """Headless guarantees introduced by the lazy-Gtk port."""
    check("module imports without gi", hasattr(m, "HAS_GTK"))
    if not m.HAS_GTK:
        for factory in ("build_stickynote_class", "build_searchwindow_class"):
            try:
                getattr(m, factory)()
                bad(factory + " raises without gi", "no exception")
            except RuntimeError:
                ok(factory + " raises without gi")
        rc = None
        real_stdout = sys.stdout
        sys.stdout = __import__("io").StringIO()
        try:
            rc = m.main()
        finally:
            sys.stdout = real_stdout
        check("main() exits non-zero headless", rc == 1, str(rc))
    else:
        ok("gi present: factories callable")


    path = os.path.join(BIN, "mv-stickies")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("stickies: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("stickies: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    m = load_app()
    test_pure(m)
    test_portable(m)
    test_gui(m)
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
