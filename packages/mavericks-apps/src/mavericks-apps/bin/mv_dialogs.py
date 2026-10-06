#!/usr/bin/env python3
"""mv_dialogs — shared Mavericks dialog helpers for mv-* apps.

- alert(): Gtk.MessageDialog with Mavericks conventions — 64px alert icon,
  caller-controlled button order (Cancel left, default right), aqua default
  button (rightmost button when the caller does not override), explicit
  Escape -> Cancel mapping.
- confirm_discard(): 3-button "Save changes?" alert, Mavericks order.
- confirm_delete(): 2-button destructive confirm [Cancel] [Delete].
- entry_dialog(): text-input alert (message + field + live validation).
  Enter confirms, Escape cancels, empty input disables OK unless
  allow_empty=True; a validator(text) -> error-string hook feeds an inline
  hint label. Returns the stripped text, or None when cancelled.
- SheetDialog: modal sheet attached to the parent window's title bar
  (slides down after the first size allocation, matches parent width,
  Enter -> default button, Escape cancels). Falls back to a centered
  modal when window attachment is unavailable.

Keyboard contract (every variant): Escape maps to the cancel-like
response; Enter activates the default button (Mavericks: rightmost unless
the caller overrides); initial focus goes to the text entry (input
dialogs) or the default button.

Error-state contract: a dialog without a message or without buttons is a
caller bug — ValueError, never a rendered broken dialog.

No new dependencies: pure GTK3/PyGObject, on-demand, no daemons.
Installed to /usr/share/mavericks-apps/; apps also import it from bin/
when run from a source checkout (sys.path[0] = bin/).
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

ALERT_ICON_SIZE = 64
SLIDE_FRAMES = 12
SLIDE_INTERVAL_MS = 16
_CANCEL_RESPONSES = (Gtk.ResponseType.CANCEL, Gtk.ResponseType.NO,
                     Gtk.ResponseType.REJECT, Gtk.ResponseType.DELETE_EVENT)


def _enlarge_icon(dialog, size):
    try:
        for child in dialog.get_content_area().get_children():
            if isinstance(child, Gtk.Box):
                for c in child.get_children():
                    if isinstance(c, Gtk.Image):
                        c.set_pixel_size(size)
    except Exception:
        pass


def _map_escape(dialog, cancel_response):
    if cancel_response is None:
        return

    def on_key_press(_w, event):
        if event.keyval == Gdk.KEY_Escape:
            dialog.response(cancel_response)
            return True
        return False

    dialog.connect("key-press-event", on_key_press)


def _validate_alert_args(message, buttons):
    """Error-state contract: a Mavericks alert always has something to say
    and at least one button. Empty/None text or an empty button list is a
    caller bug — fail loud instead of rendering a broken dialog."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError(
            "dialog message must be a non-empty string, got %r" % (message,))
    if not buttons:
        raise ValueError("dialog needs at least one (label, response) button")


def _build_alert(parent, message, secondary=None, msg_type=Gtk.MessageType.INFO,
                 buttons=(("OK", Gtk.ResponseType.OK),), default=None,
                 destructive=False):
    """Build (not run) the Mavericks alert dialog. alert() runs it."""
    _validate_alert_args(message, buttons)
    dlg = Gtk.MessageDialog(
        transient_for=parent, modal=True,
        message_type=msg_type, buttons=Gtk.ButtonsType.NONE, text=message)
    if secondary:
        dlg.format_secondary_text(secondary)
    cancel_like = None
    for label, resp in buttons:
        dlg.add_button(label, resp)
        if resp in _CANCEL_RESPONSES and cancel_like is None:
            cancel_like = resp
    if default is None:
        # Mavericks convention: the rightmost button is the default, so
        # Enter always answers the dialog and focus lands on a button.
        default = buttons[-1][1]
    dlg.set_default_response(default)
    if destructive:
        btn = dlg.get_widget_for_response(buttons[-1][1])
        if btn is not None:
            btn.get_style_context().add_class("destructive-action")
    _enlarge_icon(dlg, ALERT_ICON_SIZE)
    dlg.get_style_context().add_class("mavericks-alert")
    _map_escape(dlg, cancel_like)
    return dlg


def alert(parent, message, secondary=None, msg_type=Gtk.MessageType.INFO,
          buttons=(("OK", Gtk.ResponseType.OK),), default=None,
          destructive=False):
    """Mavericks-style alert. buttons = ordered [(label, response), ...];
    default (aqua) button rightmost unless overridden. Returns response.
    Escape returns the cancel-like response when one exists."""
    dlg = _build_alert(parent, message, secondary=secondary,
                       msg_type=msg_type, buttons=buttons, default=default,
                       destructive=destructive)
    response = dlg.run()
    dlg.destroy()
    return response


def confirm_discard(parent, document_name=None):
    msg = "Save changes before closing?"
    if document_name:
        msg = 'Save changes to "%s" before closing?' % document_name
    return alert(parent, msg,
                 secondary="Your changes will be lost if you don't save them.",
                 msg_type=Gtk.MessageType.WARNING,
                 buttons=[("Don't Save", Gtk.ResponseType.NO),
                          ("Cancel", Gtk.ResponseType.CANCEL),
                          ("Save", Gtk.ResponseType.YES)],
                 default=Gtk.ResponseType.YES)


def confirm_delete(parent, message, secondary, delete_label="Delete"):
    return alert(parent, message, secondary=secondary,
                 msg_type=Gtk.MessageType.WARNING,
                 buttons=[("Cancel", Gtk.ResponseType.CANCEL),
                          (delete_label, Gtk.ResponseType.OK)],
                 default=Gtk.ResponseType.CANCEL, destructive=True)


def _build_entry_dialog(parent, title, label=None, initial="",
                        ok_label="OK", allow_empty=False, validator=None,
                        width_chars=32):
    """Build (not run) the Mavericks text-input alert. Returns
    (dialog, entry, ok_button)."""
    _validate_alert_args(title, [("x", Gtk.ResponseType.OK)])
    dlg = Gtk.MessageDialog(
        transient_for=parent, modal=True,
        message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
        text=title)
    if label:
        dlg.format_secondary_text(label)
    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    ok = dlg.add_button(ok_label, Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)

    entry = Gtk.Entry()
    entry.set_text(initial if isinstance(initial, str) else str(initial))
    entry.set_width_chars(width_chars)
    entry.set_activates_default(True)

    hint = Gtk.Label(label="")
    hint.set_halign(Gtk.Align.START)
    hint.set_line_wrap(True)
    hint.set_no_show_all(True)
    hint.set_max_width_chars(width_chars)

    area = dlg.get_message_area()
    if isinstance(area, Gtk.Box):
        area.set_spacing(8)
    area.pack_start(entry, False, False, 0)
    area.pack_start(hint, False, False, 0)

    def refresh(_entry=None):
        text = entry.get_text().strip()
        error = None
        if not text and not allow_empty:
            error = ""  # empty state: OK disabled, no hint text needed
        elif validator is not None and text:
            try:
                error = validator(text)
            except Exception:
                error = "Invalid input."
        ok.set_sensitive(error is None)
        if error:
            hint.set_text(error)
            hint.show()
        else:
            hint.hide()

    entry.connect("changed", refresh)
    _enlarge_icon(dlg, ALERT_ICON_SIZE)
    dlg.get_style_context().add_class("mavericks-alert")
    _map_escape(dlg, Gtk.ResponseType.CANCEL)
    refresh()
    return dlg, entry, ok


def password_dialog(parent, title, label=None, ok_label="OK"):
    """Mavericks-style password prompt. Returns text or None on cancel."""
    _validate_alert_args(title, [("Cancel", Gtk.ResponseType.CANCEL),
                                 (ok_label, Gtk.ResponseType.OK)])
    dlg = Gtk.MessageDialog(
        transient_for=parent, modal=True,
        message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
        text=title)
    if label:
        dlg.format_secondary_text(label)
    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dlg.add_button(ok_label, Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)
    entry = Gtk.Entry()
    entry.set_visibility(False)
    entry.set_invisible_char("●")
    entry.set_activates_default(True)
    area = dlg.get_message_area()
    if isinstance(area, Gtk.Box):
        area.set_spacing(8)
    area.pack_start(entry, False, False, 0)
    _enlarge_icon(dlg, ALERT_ICON_SIZE)
    dlg.get_style_context().add_class("mavericks-alert")
    _map_escape(dlg, Gtk.ResponseType.CANCEL)
    dlg.show_all()
    entry.grab_focus()
    response = dlg.run()
    value = entry.get_text()
    dlg.destroy()
    return value if response == Gtk.ResponseType.OK and value else None


def entry_dialog(parent, title, label=None, initial="", ok_label="OK",
                 allow_empty=False, validator=None, width_chars=32):
    """Mavericks-style text-input alert. validator(text) -> error string or
    None; the OK button stays disabled while input is empty (unless
    allow_empty) or invalid, with the error shown as an inline hint.
    Returns the stripped text on OK, None on Cancel/Escape."""
    dlg, entry, _ok = _build_entry_dialog(
        parent, title, label=label, initial=initial, ok_label=ok_label,
        allow_empty=allow_empty, validator=validator,
        width_chars=width_chars)
    dlg.show_all()
    entry.select_region(0, -1)
    entry.grab_focus()
    response = dlg.run()
    text = entry.get_text().strip()
    dlg.destroy()
    return text if response == Gtk.ResponseType.OK else None


class SheetDialog(Gtk.Window):
    """Mavericks-style sheet attached to the parent's title bar.

    Usage:
        sheet = SheetDialog(parent)
        sheet.set_sheet_title("First Aid")
        sheet.add_content(widget)
        sheet.add_button("Close", Gtk.ResponseType.CLOSE)
        response = sheet.run()
        sheet.destroy()

    Keyboard contract: Escape -> CANCEL; Enter -> default response (the
    rightmost button when set_default_response() was not called); initial
    focus goes to the first text entry in the content, else the default
    button. Without a parent the sheet centers on screen instead of
    attaching.
    """

    def __init__(self, parent):
        super().__init__()
        self._parent = parent
        self._response = Gtk.ResponseType.NONE
        self._default_response = None
        self._attached = False
        self._buttons = {}
        self._button_order = []
        self._slide_hid = None
        self.set_decorated(False)
        self.set_modal(True)
        self.set_transient_for(parent)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_style_context().add_class("sheet")
        try:
            self.set_attached_to(parent)
            # set_attached_to(None) clears attachment without raising
            self._attached = parent is not None
        except Exception:
            self._attached = False

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bar.get_style_context().add_class("sheet-titlebar")
        self._title_label = Gtk.Label(label="")
        self._title_label.set_halign(Gtk.Align.CENTER)
        self._title_label.set_hexpand(True)
        bar.pack_start(self._title_label, True, True, 0)
        outer.pack_start(bar, False, False, 0)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._content.get_style_context().add_class("sheet-content")
        outer.pack_start(self._content, True, True, 0)

        self._action = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._action.get_style_context().add_class("dialog-action-area")
        self._action.pack_start(Gtk.Label(label=""), True, True, 0)
        outer.pack_start(self._action, False, False, 0)

        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event", self._on_delete_event)
        if parent is not None:
            try:
                parent.connect("size-allocate", self._on_parent_resize)
            except Exception:
                pass

    def set_sheet_title(self, text):
        self._title_label.set_text(text)

    def add_content(self, widget, expand=True, fill=True, padding=0):
        self._content.pack_start(widget, expand, fill, padding)

    def add_button(self, label, response):
        btn = Gtk.Button(label=label)
        btn.set_can_default(True)
        btn.connect("clicked", self._on_button_clicked, response)
        self._buttons[response] = btn
        self._button_order.append(response)
        self._action.pack_start(btn, False, False, 0)
        return btn

    def set_default_response(self, response):
        self._default_response = response
        self._apply_default_style()

    def _apply_default_style(self):
        for btn in self._buttons.values():
            btn.get_style_context().remove_class("suggested-action")
        btn = self._buttons.get(self._default_response)
        if btn is not None:
            btn.get_style_context().add_class("suggested-action")
            try:
                # Gtk.Window default machinery so a focused Gtk.Entry with
                # activates_default triggers this button on Enter.
                self.set_default(btn)
            except Exception:
                pass

    def _ensure_default(self):
        """Mavericks convention: rightmost button is the default when the
        caller did not choose one — Enter always answers the sheet."""
        if self._default_response is None and self._button_order:
            self.set_default_response(self._button_order[-1])

    def _first_entry(self):
        found = []

        def walk(w):
            if found:
                return
            if isinstance(w, Gtk.Entry):
                found.append(w)
                return
            if isinstance(w, Gtk.Container):
                for child in w.get_children():
                    walk(child)

        walk(self._content)
        return found[0] if found else None

    def _focus_initial(self):
        """Focus contract: text input wins over buttons (macOS sheets with
        a name field focus the field); otherwise the default button."""
        entry = self._first_entry()
        if entry is not None:
            try:
                entry.set_activates_default(True)
            except Exception:
                pass
            entry.grab_focus()
        else:
            btn = self._buttons.get(self._default_response)
            if btn is not None:
                btn.grab_focus()

    def _on_button_clicked(self, _btn, response):
        self._response = response
        Gtk.main_quit()

    def _finish(self, response):
        self._response = response
        Gtk.main_quit()

    def _on_delete_event(self, _w, _event):
        # Window-manager close == cancel, same as Escape.
        self._finish(Gtk.ResponseType.CANCEL)
        return True

    def _on_parent_resize(self, _parent, _alloc):
        self._place()

    def _titlebar_height(self):
        p = self._parent
        if p is None:
            return 0
        try:
            tb = p.get_titlebar()
            return tb.get_allocated_height() if tb is not None else 0
        except Exception:
            return 0

    def _place(self):
        p = self._parent
        if p is None:
            self.set_position(Gtk.WindowPosition.CENTER)
            return
        if not p.get_realized():
            return
        self.set_default_size(p.get_allocated_width(), -1)
        if self._attached:
            self.move(0, self._titlebar_height())
        else:
            self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

    def _on_first_allocate(self, _w, alloc):
        if self._slide_hid is not None:
            try:
                self.disconnect(self._slide_hid)
            except Exception:
                pass
            self._slide_hid = None
        if not self._attached:
            return
        target_y = self._titlebar_height()
        start_y = target_y - alloc.height
        self.move(0, start_y)
        self._animate_slide(start_y, target_y)

    def _animate_slide(self, start_y, target_y):
        try:
            state = {"frame": 0}

            def tick():
                state["frame"] += 1
                t = state["frame"] / float(SLIDE_FRAMES)
                if t >= 1.0:
                    self.move(0, target_y)
                    return False
                eased = 1.0 - (1.0 - t) ** 2
                self.move(0, int(start_y + (target_y - start_y) * eased))
                return True

            GLib.timeout_add(SLIDE_INTERVAL_MS, tick)
        except Exception:
            pass

    def run(self):
        self._ensure_default()
        if self._attached:
            # Slide only after the first size allocation: the height is
            # unknown before mapping, so the animation starts from above
            # the parent's title bar with the real sheet height.
            self._slide_hid = self.connect_after(
                "size-allocate", self._on_first_allocate)
        self.show_all()
        self._place()
        self._focus_initial()
        self.present()
        Gtk.main()
        return self._response

    def _on_key_press(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self._finish(Gtk.ResponseType.CANCEL)
            return True
        if (event.keyval == Gdk.KEY_Return
                and self._default_response is not None):
            self._finish(self._default_response)
            return True
        return False
