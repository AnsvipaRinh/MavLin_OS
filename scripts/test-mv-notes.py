#!/usr/bin/env python3
"""Headless tests for mv-notes.

Covers the pure store/logic layer (no GTK widgets are instantiated):
- store round-trip, backup-on-save, corrupt-store quarantine + restore
- Recently Deleted: trash/restore/delete-forever/empty/30-day auto-purge
- folder deletion moves notes to trash
- checklist line toggling, filename sanitization, highlight ranges,
  print pagination, file import, geometry persistence

Usage: python3 scripts/test-mv-notes.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
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

APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-notes")

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


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_notes", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_notes", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


    path = os.path.join(BIN, "mv-notes")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("notes: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("notes: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    mv = load_app()
    check("module imports headless", True)

    with tempfile.TemporaryDirectory() as td:
        store = os.path.join(td, "notes.json")

        data = mv.load_store(store)
        check("missing store -> default", data["folders"] == {"Notes": []}
              and data["trash"] == [])

        n1 = mv.make_note("hello world")
        n2 = mv.make_note("[ ] buy milk\n[x] done", pinned=True)
        data["folders"]["Notes"] = [n1, n2]
        data["folders"]["Work"] = []
        mv.save_store(store, data)
        check("store round-trip", mv.load_store(store)["folders"]["Notes"]
              == [n1, n2])
        mv.save_store(store, data)
        check("backup created on second save", os.path.exists(store + ".bak"))

        with open(store, "w") as f:
            f.write("{not json")
        if os.path.exists(store + ".bak"):
            os.remove(store + ".bak")
        warns = []
        data2 = mv.load_store(store, warns.append)
        check("corrupt store -> fresh default",
              data2["folders"] == {"Notes": []})
        check("corrupt store -> warning emitted", len(warns) == 1)
        check("corrupt store -> quarantine file",
              any(f.startswith("notes.json.corrupt-") for f in os.listdir(td)))

        mv.save_store(store, {"folders": {"Notes": [n1]}, "trash": []})
        mv.save_store(store, {"folders": {"Notes": [n1]}, "trash": []})
        with open(store, "w") as f:
            f.write("garbage{")
        warns = []
        data3 = mv.load_store(store, warns.append)
        check("corrupt store -> backup restored",
              data3["folders"]["Notes"] == [n1])
        check("backup restore -> warning emitted", len(warns) == 1)

        data = {"folders": {"Notes": [n1, n2], "Work": []}, "trash": []}
        check("trash_note moves note",
              mv.trash_note(data, "Notes", n1["id"]))
        check("trashed note absent from folder",
              [n["id"] for n in data["folders"]["Notes"]] == [n2["id"]])
        check("trashed note in trash with deleted_at",
              len(data["trash"]) == 1 and "deleted_at" in data["trash"][0]
              and data["trash"][0]["folder"] == "Notes")

        folder = mv.restore_note(data, n1["id"])
        check("restore_note returns folder", folder == "Notes")
        check("restored note back in folder",
              [n["id"] for n in data["folders"]["Notes"]]
              == [n1["id"], n2["id"]])
        check("trash empty after restore", data["trash"] == [])

        mv.trash_note(data, "Notes", n1["id"])
        check("delete_forever", mv.delete_forever(data, n1["id"]))
        check("delete_forever unknown id is no-op",
              not mv.delete_forever(data, "nope"))
        check("trash empty after delete_forever", data["trash"] == [])

        mv.trash_note(data, "Notes", n1["id"])
        mv.trash_note(data, "Notes", n2["id"])
        mv.empty_trash(data)
        check("empty_trash", data["trash"] == [])

        old = int(time.time()) - 31 * 86400
        recent = int(time.time()) - 5 * 86400
        data["trash"] = [
            {"id": "a", "text": "old", "deleted_at": old},
            {"id": "b", "text": "new", "deleted_at": recent},
        ]
        mv.purge_trash(data)
        check("purge_trash keeps recent, drops >30d",
              [n["id"] for n in data["trash"]] == ["b"])

        data = {"folders": {"Notes": [n1], "Work": [n2]}, "trash": []}
        check("delete_folder", mv.delete_folder(data, "Work"))
        check("delete_folder moves notes to trash",
              data["trash"] == [n2] and "Work" not in data["folders"])
        check("delete_folder recreates Notes when last",
              mv.delete_folder(data, "Notes") is True
              and "Notes" in data["folders"])

        check("toggle [ ] -> [x]",
              mv.toggle_checklist_line("[ ] buy milk") == "[x] buy milk")
        check("toggle [x] -> [ ]",
              mv.toggle_checklist_line("[x] buy milk") == "[ ] buy milk")
        check("toggle preserves indent",
              mv.toggle_checklist_line("  [ ] indented") == "  [x] indented")
        check("toggle non-checklist line is no-op",
              mv.toggle_checklist_line("plain text") == "plain text")
        check("toggle adds missing space",
              mv.toggle_checklist_line("[ ]tight") == "[x] tight")

        check("sanitize_filename strips unsafe chars",
              mv.sanitize_filename('a/b:c*d?') == "a_b_c_d_")
        check("sanitize_filename empty -> note",
              mv.sanitize_filename("") == "note")

        check("highlight_ranges finds all matches",
              mv.highlight_ranges("foo bar foo baz", "foo")
              == [(0, 3), (8, 11)])
        check("highlight_ranges case-insensitive",
              mv.highlight_ranges("Foo foo FOO", "foo")
              == [(0, 3), (4, 7), (8, 11)])
        check("highlight_ranges empty query -> no ranges",
              mv.highlight_ranges("text", "") == [])

        check("paginate splits pages",
              [len(p) for p in mv.paginate("\n".join(str(i) for i in range(10)),
                                           4)] == [4, 4, 2])
        check("paginate empty text -> one blank page",
              mv.paginate("", 10) == [[""]])

        src = os.path.join(td, "import.txt")
        with open(src, "w") as f:
            f.write("imported content")
        check("import_file", mv.import_file(src) == "imported content")

        check("note_title first line",
              mv.note_title({"text": "title\nbody"}) == "title")
        check("note_title empty -> (empty)",
              mv.note_title({"text": "  "}) == "(empty)")
        check("has_checklist detects [ ] and [x]",
              mv.has_checklist("[ ] a") and mv.has_checklist("[x] a")
              and not mv.has_checklist("plain"))

        geo = {"w": 900, "h": 600, "x": 10, "y": 20}
        data = {"folders": {"Notes": []}, "trash": [], "geometry": geo}
        mv.save_store(store, data)
        check("geometry persists",
              mv.load_store(store)["geometry"] == geo)

        check("normalize repairs non-dict store",
              mv._normalize("junk")["folders"] == {"Notes": []})

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
