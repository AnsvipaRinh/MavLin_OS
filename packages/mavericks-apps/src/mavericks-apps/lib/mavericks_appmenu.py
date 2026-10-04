"""Shared GTK3 application-menu integration for MavLinOS native apps.

The helper deliberately uses Gtk.Application/GMenu rather than drawing a fake
menu inside each window. This allows the Xfce AppMenu panel plugin to export
the application's menu to the Mavericks-style top panel.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib


def install_application_menu(app, app_name, get_window):
    """Install a small Mavericks-style application menu on a Gtk.Application."""
    def action(name, callback):
        a = Gio.SimpleAction.new(name, None)
        a.connect("activate", lambda *_: callback())
        app.add_action(a)

    def current():
        return get_window()

    action("about", lambda: _show_about(current(), app_name))
    action("quit", lambda: app.quit())

    menu = Gio.Menu()

    app_menu = Gio.Menu()
    app_menu.append("About %s" % app_name, "app.about")
    menu.append_submenu(app_name, app_menu)

    file_menu = Gio.Menu()
    file_menu.append("Close Window", "app.close-window")
    menu.append_submenu("File", file_menu)

    edit_menu = Gio.Menu()
    edit_menu.append("Copy", "app.copy")
    edit_menu.append("Paste", "app.paste")
    menu.append_submenu("Edit", edit_menu)

    window_menu = Gio.Menu()
    window_menu.append("Minimize", "app.minimize")
    window_menu.append("Close Window", "app.close-window")
    menu.append_submenu("Window", window_menu)

    help_menu = Gio.Menu()
    help_menu.append("About %s" % app_name, "app.about")
    menu.append_submenu("Help", help_menu)

    action("close-window", lambda: _window_action(current(), "close"))
    action("minimize", lambda: _window_action(current(), "minimize"))
    action("copy", lambda: _window_action(current(), "copy"))
    action("paste", lambda: _window_action(current(), "paste"))

    app.set_app_menu(menu)
    return menu


def _window_action(window, name):
    if window is None:
        return
    if name == "close":
        window.destroy()
    elif name == "minimize":
        window.iconify()
    elif name == "copy":
        window.get_clipboard(Gdk.SELECTION_CLIPBOARD) if False else None
    elif name == "paste":
        return


def _show_about(window, app_name):
    if window is None:
        return
    dialog = window.get_toplevel()
    message = Gtk.MessageDialog(
        transient_for=dialog,
        flags=Gtk.DialogFlags.MODAL,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.CLOSE,
        text="About %s" % app_name,
    )
    message.format_secondary_text("MavLinOS native application")
    message.run()
    message.destroy()


from gi.repository import Gtk
