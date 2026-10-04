#!/usr/bin/env python3
"""mv_dialogs — shared Mavericks dialog helpers for mv-* apps.

- alert(): Gtk.MessageDialog with Mavericks conventions — 64px alert icon,
  caller-controlled button order (Cancel left, default right), aqua default
  button, explicit Escape -> Cancel mapping.
- confirm_discard(): 3-button "Save changes?" alert, Mavericks order.
- confirm_delete(): 2-button destructive confirm [Cancel] [Delete].
- SheetDialog: modal sheet attached to the parent window's title bar
  (slides down, matches parent width, Escape cancels). Falls back to a
  centered modal if window attachment is unavailable.

No new dependencies: pure GTK3/PyGObject, on-demand, no daemons.
Installed to /usr/lib/mavericks-apps/; apps also import it from bin/ when
run from a source checkout (sys.path[0] = bin/).
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


def alert(parent, message, secondary=None, msg_type=Gtk.MessageType.INFO,
          buttons=(("OK", Gtk.ResponseType.OK),), default=None,
          destructive=False):
    """Mavericks-style alert. buttons = ordered [(label, response), ...];
    default (aqua) button rightmost. Returns response."""
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
    if default is not None:
        dlg.set_default_response(default)
    if destructive:
        btn = dlg.get_widget_for_response(buttons[-1][1])
        if btn is not None:
            btn.get_style_context().add_class("destructive-action")
    _enlarge_icon(dlg, ALERT_ICON_SIZE)
    dlg.get_style_context().add_class("mavericks-alert")
    _map_escape(dlg, cancel_like)
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


class SheetDialog(Gtk.Window):
    """Mavericks-style sheet attached to the parent's title bar.

    Usage:
        sheet = SheetDialog(parent)
        sheet.set_sheet_title("First Aid")
        sheet.add_content(widget)
        sheet.add_button("Close", Gtk.ResponseType.CLOSE)
        response = sheet.run()
        sheet.destroy()
    """

    def __init__(self, parent):
        super().__init__()
        self._parent = parent
        self._response = Gtk.ResponseType.NONE
        self._default_response = None
        self._attached = False
        self._buttons = {}
        self.set_decorated(False)
        self.set_modal(True)
        self.set_transient_for(parent)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_style_context().add_class("sheet")
        try:
            self.set_attached_to(parent)
            self._attached = True
        except Exception:
            pass

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
        btn.connect("clicked", self._on_button_clicked, response)
        self._buttons[response] = btn
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

    def _on_button_clicked(self, _btn, response):
        self._response = response
        Gtk.main_quit()

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
        if p is None or not p.get_realized():
            return
        self.set_default_size(p.get_allocated_width(), -1)
        if self._attached:
            self.move(0, self._titlebar_height())
        else:
            self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

    def _slide_in(self, target_y):
        try:
            height = self.get_allocated_height()
            start_y = target_y - height
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
        self.show_all()
        self._place()
        if self._attached:
            self._slide_in(self._titlebar_height())
        self.present()
        Gtk.main()
        return self._response

    def _on_key_press(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self._response = Gtk.ResponseType.CANCEL
            Gtk.main_quit()
            return True
        if (event.keyval == Gdk.KEY_Return
                and self._default_response is not None):
            self._response = self._default_response
            Gtk.main_quit()
            return True
        return False
