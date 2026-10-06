#!/usr/bin/env python3
"""Test suite for mv_dialogs (Global Dialogs, canonical #20).

Headless section (always runs):
- py_compile of the module
- module surface contract: alert / confirm_discard / confirm_delete /
  entry_dialog / SheetDialog exist with the documented signatures
- error-state contract: empty message / empty buttons raise ValueError
  (source-level, no widgets needed)

GUI smoke (real GTK on the pinned Xvfb :97, skipped headless):
- alert(): default falls back to the rightmost button, destructive class,
  mavericks-alert theme class, Escape -> cancel-like response
- confirm_discard()/confirm_delete(): Mavericks button order + defaults
- entry_dialog(): empty input disables OK, validator drives an inline hint
  and OK sensitivity, Enter returns the text, Escape/Cancel returns None
- SheetDialog: rightmost-button default fallback, suggested-action styling,
  Enter -> default response, Escape -> CANCEL, focus goes to the first
  entry (input sheets) or the default button, delete-event == cancel,
  parentless sheet centers instead of attaching

Usage: python3 scripts/test-mv-dialogs.py
Exit 0 = all tests passed (GUI section skipped when headless)."""
import inspect
import os
import py_compile
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv_dialogs.py")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the Windows desktop).  gui_display() pins the
# dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for children.
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


def import_module():
    sys.path.insert(0, os.path.dirname(MODULE_PATH))
    import mv_dialogs
    return mv_dialogs


# ---------------------------------------------------------------- headless
def headless_suite():
    py_compile.compile(MODULE_PATH, doraise=True)
    ok("py_compile mv_dialogs.py")

    m = import_module()
    for fn in ("alert", "confirm_discard", "confirm_delete",
               "entry_dialog", "SheetDialog"):
        check("surface: %s exists" % fn, hasattr(m, fn))
    for internal in ("_build_alert", "_build_entry_dialog",
                     "_validate_alert_args"):
        check("internal hook: %s exists (testability)" % internal,
              hasattr(m, internal))

    # Error-state contract without touching widgets: the validator must be
    # a module-level callable that rejects empty/None messages and empty
    # button lists before any GTK call.
    v = m._validate_alert_args
    for msg in (None, "", "   \t "):
        try:
            v(msg, [("OK", 1)])
            bad("error-state: rejects %r message" % (msg,))
        except ValueError:
            ok("error-state: rejects %r message" % (msg,))
    try:
        v("Message", [])
        bad("error-state: rejects empty button list")
    except ValueError:
        ok("error-state: rejects empty button list")
    v("Message", [("OK", 1)])  # must not raise
    ok("error-state: accepts valid args")

    # Keyboard-contract source markers (GUI section exercises the real
    # behavior; this keeps headless CI honest when GTK is unavailable).
    src = open(MODULE_PATH, encoding="utf-8").read()
    check("contract: Escape mapping present",
          "KEY_Escape" in src and "_map_escape" in src)
    check("contract: Enter/default fallback present",
          "buttons[-1][1]" in src and "_ensure_default" in src)
    check("contract: sheet focus policy present",
          "_focus_initial" in src and "activates_default" in src)

    # Signature stability for consumers (mv-textedit, mv-diskutil).
    sig = inspect.signature(m.alert)
    for param in ("parent", "message", "secondary", "msg_type", "buttons",
                  "default", "destructive"):
        check("alert() signature keeps %r" % param, param in sig.parameters)
    esig = inspect.signature(m.entry_dialog)
    for param in ("parent", "title", "label", "initial", "ok_label",
                  "allow_empty", "validator"):
        check("entry_dialog() signature has %r" % param,
              param in esig.parameters)
    init = inspect.signature(m.SheetDialog.__init__)
    check("SheetDialog.__init__ keeps parent param", "parent" in init.parameters)


# -------------------------------------------------------------------- GUI
def key_event(keyval):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.keyval = keyval
    return ev


def gui_suite():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GLib
    m = import_module()

    parent = Gtk.Window()  # never shown: transient_for accepts unmapped

    # --- alert(): build + introspect --------------------------------
    dlg = m._build_alert(
        parent, "Erase “Data”?", secondary="All data will be erased.",
        msg_type=Gtk.MessageType.WARNING,
        buttons=[("Cancel", Gtk.ResponseType.CANCEL),
                 ("Erase", Gtk.ResponseType.OK)],
        destructive=True)
    dlg.show_all()
    btn = dlg.get_widget_for_response(Gtk.ResponseType.OK)
    check("alert: default falls back to rightmost button",
          btn is not None and btn.get_property("has-default"))
    check("alert: destructive class on action button",
          btn.get_style_context().has_class("destructive-action"))
    check("alert: mavericks-alert theme class",
          dlg.get_style_context().has_class("mavericks-alert"))
    Gtk.main_iteration_do(False)

    # Escape -> cancel-like response without a real keyboard
    GLib.timeout_add(150, lambda: dlg.emit("key-press-event",
                                           key_event(Gdk.KEY_Escape)) or False)
    check("alert: Escape returns cancel response",
          dlg.run() == Gtk.ResponseType.CANCEL)
    dlg.destroy()

    # Error-state contract on the real builder too
    try:
        m._build_alert(parent, "", buttons=[("OK", Gtk.ResponseType.OK)])
        bad("alert: empty message raises")
    except ValueError:
        ok("alert: empty message raises")

    # --- confirm_discard(): Mavericks 3-button order -----------------
    dd = m._build_alert(
        parent, "Save changes?", secondary="s", msg_type=Gtk.MessageType.WARNING,
        buttons=[("Don't Save", Gtk.ResponseType.NO),
                 ("Cancel", Gtk.ResponseType.CANCEL),
                 ("Save", Gtk.ResponseType.YES)],
        default=Gtk.ResponseType.YES)
    dd.show_all()
    order = []
    box = [c for c in dd.get_action_area().get_children()]
    for b in box:
        r = None
        for resp in (Gtk.ResponseType.NO, Gtk.ResponseType.CANCEL,
                     Gtk.ResponseType.YES):
            if dd.get_widget_for_response(resp) is b:
                r = resp
                break
        order.append(r)
    check("confirm_discard order: Don't Save, Cancel, Save",
          order == [Gtk.ResponseType.NO, Gtk.ResponseType.CANCEL,
                    Gtk.ResponseType.YES],
          detail="got %r" % (order,))
    sbtn = dd.get_widget_for_response(Gtk.ResponseType.YES)
    check("confirm_discard: Save is the default",
          sbtn.get_property("has-default"))
    dd.destroy()

    # --- confirm_delete(): Cancel default + destructive ---------------
    cd = m._build_alert(
        parent, "Delete this note?", secondary="gone",
        msg_type=Gtk.MessageType.WARNING,
        buttons=[("Cancel", Gtk.ResponseType.CANCEL),
                 ("Delete", Gtk.ResponseType.OK)],
        default=Gtk.ResponseType.CANCEL, destructive=True)
    cd.show_all()
    check("confirm_delete: Cancel is the default",
          cd.get_widget_for_response(Gtk.ResponseType.CANCEL)
          .get_property("has-default"))
    check("confirm_delete: Delete is destructive",
          cd.get_widget_for_response(Gtk.ResponseType.OK)
          .get_style_context().has_class("destructive-action"))
    cd.destroy()

    # --- entry_dialog(): empty/validator/keyboard contract ------------
    def validator(text):
        return None if "/" not in text else "Name cannot contain '/'"

    dlg, entry, okbtn = m._build_entry_dialog(
        parent, "Rename folder", label="Enter a new name:",
        initial="", validator=validator)
    dlg.show_all()
    check("entry: empty input disables OK (empty state)",
          not okbtn.get_sensitive())
    entry.set_text("notes.txt")
    check("entry: valid input enables OK", okbtn.get_sensitive())
    entry.set_text("ba/d")
    check("entry: validator error disables OK", not okbtn.get_sensitive())
    entry.set_text("   ")
    check("entry: OK insensitive on whitespace-only input",
          not okbtn.get_sensitive())
    entry.set_text("notes.txt")

    # keyboard: Escape -> None (handler sits on the dialog itself)
    GLib.timeout_add(150, lambda: dlg.emit("key-press-event",
                                           key_event(Gdk.KEY_Escape)) or False)
    dlg.run()
    dlg.destroy()

    # full entry_dialog() lifecycle. The Enter path is Entry-internal
    # (activates_default -> window default activation), so verify the
    # wiring and drive the same default activation Enter would trigger.
    saved = {}
    orig_build = m._build_entry_dialog

    def patched_build(*a, **kw):
        dlg, entry, okbtn = orig_build(*a, **kw)
        saved["dlg"] = dlg
        saved["entry"] = entry
        saved["ok"] = okbtn

        def accept():
            saved["wired"] = (saved["entry"].get_activates_default(),
                              saved["ok"].get_property("has-default"))
            saved["dlg"].activate_default()
            return False
        GLib.timeout_add(250, accept)
        return dlg, entry, okbtn
    m._build_entry_dialog = patched_build
    try:
        result = m.entry_dialog(parent, "Folder name", initial="Work")
    finally:
        m._build_entry_dialog = orig_build
    check("entry_dialog: entry activates default on Enter (wiring)",
          saved.get("wired") == (True, True),
          detail="got %r" % (saved.get("wired"),))
    check("entry_dialog: default activation returns the text",
          result == "Work", detail="got %r" % (result,))

    def cancel_build(*a, **kw):
        dlg, entry, okbtn = orig_build(*a, **kw)
        GLib.timeout_add(200, lambda: dlg.emit(
            "key-press-event", key_event(Gdk.KEY_Escape)) or False)
        return dlg, entry, okbtn
    m._build_entry_dialog = cancel_build
    try:
        result_cancel = m.entry_dialog(parent, "Folder name", initial="Work")
    finally:
        m._build_entry_dialog = orig_build
    check("entry_dialog: Escape returns None", result_cancel is None)

    # --- SheetDialog ---------------------------------------------------
    sheet = m.SheetDialog(parent)
    sheet.set_sheet_title("Erase")
    sheet.add_content(Gtk.Label(label="Erase the disk?"))
    sheet.add_button("Cancel", Gtk.ResponseType.CANCEL)
    sheet.add_button("Erase", Gtk.ResponseType.OK)
    sheet._ensure_default()
    check("sheet: default falls back to rightmost button",
          sheet._default_response == Gtk.ResponseType.OK)
    check("sheet: default button gets suggested-action (aqua)",
          sheet._buttons[Gtk.ResponseType.OK].get_style_context()
          .has_class("suggested-action"))
    sheet.show_all()
    Gtk.main_iteration_do(False)

    GLib.timeout_add(150, lambda: sheet.emit("key-press-event",
                                             key_event(Gdk.KEY_Return))
                      or False)
    check("sheet: Enter returns the default response",
          sheet.run() == Gtk.ResponseType.OK)
    sheet.destroy()

    # Escape on a fresh sheet
    s2 = m.SheetDialog(parent)
    s2.add_button("Close", Gtk.ResponseType.CLOSE)
    s2.show_all()
    GLib.timeout_add(150, lambda: s2.emit("key-press-event",
                                          key_event(Gdk.KEY_Escape)) or False)
    check("sheet: Escape returns CANCEL", s2.run() == Gtk.ResponseType.CANCEL)
    s2.destroy()

    # Focus contract: entry wins over buttons
    s3 = m.SheetDialog(parent)
    name_entry = Gtk.Entry()
    s3.add_content(name_entry)
    s3.add_button("Cancel", Gtk.ResponseType.CANCEL)
    s3.add_button("OK", Gtk.ResponseType.OK)
    focus_report = {}

    def probe_focus():
        focus_report["w"] = s3.get_focus()
        focus_report["activ"] = name_entry.get_activates_default()
        s3.emit("key-press-event", key_event(Gdk.KEY_Escape))
        return False
    GLib.timeout_add(250, probe_focus)
    s3.run()
    check("sheet: focus goes to the first entry",
          focus_report.get("w") is name_entry)
    check("sheet: entry activates the default button on Enter",
          focus_report.get("activ") is True)
    s3.destroy()

    # Focus contract without an entry: default button focused
    s4 = m.SheetDialog(parent)
    s4.add_content(Gtk.Label(label="plain"))
    s4.add_button("No", Gtk.ResponseType.NO)
    s4.add_button("Yes", Gtk.ResponseType.YES)
    focus4 = {}

    def probe4():
        focus4["w"] = s4.get_focus()
        s4.emit("key-press-event", key_event(Gdk.KEY_Escape))
        return False
    GLib.timeout_add(250, probe4)
    s4.run()
    check("sheet: without entry the default button gets focus",
          focus4.get("w") is s4._buttons[Gtk.ResponseType.YES])
    s4.destroy()

    # delete-event (WM close) == cancel
    s5 = m.SheetDialog(parent)
    s5.add_button("Close", Gtk.ResponseType.CLOSE)
    import gi as _gi
    _gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk as _Gdk
    GLib.timeout_add(150, lambda: (s5.emit("delete-event",
                                           _Gdk.Event.new(
                                               _Gdk.EventType.DELETE)))
                      or False)
    check("sheet: window close returns CANCEL",
          s5.run() == Gtk.ResponseType.CANCEL)
    s5.destroy()

    # Parentless sheet: must not attach, must not crash, centered
    s6 = m.SheetDialog(None)
    s6.set_sheet_title("Standalone")
    s6.add_content(Gtk.Label(label="no parent"))
    s6.add_button("OK", Gtk.ResponseType.OK)
    check("sheet: parentless does not attach", s6._attached is False)
    GLib.timeout_add(250, lambda: s6.emit("key-press-event",
                                          key_event(Gdk.KEY_Escape)) or False)
    check("sheet: parentless run + Escape works",
          s6.run() == Gtk.ResponseType.CANCEL)
    s6.destroy()


def main():
    headless_suite()
    if HAS_DISPLAY:
        gui_suite()
    else:
        print("SKIP GUI smoke (headless)")
    print("passed %d, failed %d" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
