"""Shared GTK3 application-menu integration for MavLinOS native apps.

Uses Gtk.Application/GMenu so the Xfce AppMenu plugin (vala-panel-appmenu)
can export the application's menu to the Mavericks-style top panel.

The exported model follows the macOS 10.9 global menu contract:

    <App Name>   File   Window   Help

where the first submenu is the bold application menu the panel renders in
the menu bar (Apple-like app name on the left, exactly like macOS) and the
remaining submenus are the standard application menus.

Everything here is headless-testable: no widget is realised and no display
is touched, so the suites can build the menus against real Gio.

Why there is no generic Edit menu here: GtkWindow's clipboard actions
(win.cut-clipboard / win.copy-clipboard / win.paste-clipboard) and
GtkEditable's undo/redo are *window-scoped*.  When the menu model is
exported to an external panel the window context is lost and those entries
render inert — shipping them would be fake integration.  The apps that
actually edit text therefore ship their own Edit menu through their
build_<app>_menu() callback (mv-textedit: Undo/Redo/Cut/Copy/Paste;
mv-notes / mv-reminders: Find).  See docs/DECISIONS.md.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk


def install_application_menu(app, app_name, get_window, menu_builder=None):
    """Install a small Mavericks-style application menu on a Gtk.Application."""

    def add_action(name, callback):
        # An app-specific menu_builder may legitimately re-declare an action
        # the shared runner already owns ("quit", "about", ...).  Gio warns
        # loudly and keeps the FIRST registration, silently discarding the
        # app's intent.  Replace instead: the later, more specific
        # registration wins and no GLib warning is emitted.
        if app.lookup_action(name) is not None:
            app.remove_action(name)
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda *_: callback())
        app.add_action(action)

    add_action("about", lambda: _show_about(get_window(), app_name))
    add_action("quit", app.quit)
    add_action("close-window",
               lambda: get_window().destroy() if get_window() else None)
    add_action("minimize",
               lambda: get_window().iconify() if get_window() else None)
    add_action("zoom", lambda: _toggle_zoom(get_window()))

    if menu_builder is not None:
        menu = menu_builder(app, app_name, get_window, add_action)
    else:
        menu = _standard_menu(app, app_name, add_action)

    app.set_app_menu(menu)
    return menu


def _standard_menu(app, app_name, add_action):
    """Mavericks default menu: bold app menu + File / Window / Help."""
    menu = Gio.Menu()

    app_menu = Gio.Menu()
    app_menu.append("About %s" % app_name, "app.about")
    app_menu.append("Quit %s" % app_name, "app.quit")
    menu.append_submenu(app_name, app_menu)

    file_menu = Gio.Menu()
    file_menu.append("Close Window", "app.close-window")
    menu.append_submenu("File", file_menu)

    window_menu = Gio.Menu()
    window_menu.append("Minimize", "app.minimize")
    window_menu.append("Zoom", "app.zoom")
    window_menu.append("Close Window", "app.close-window")
    menu.append_submenu("Window", window_menu)

    help_menu = Gio.Menu()
    help_menu.append("About %s" % app_name, "app.about")
    menu.append_submenu("Help", help_menu)

    return menu


def _toggle_zoom(window):
    if window is None:
        return
    if window.is_maximized():
        window.unmaximize()
    else:
        window.maximize()


def run_application(app_id, app_name, window_factory, argv=None,
                    menu_builder=None):
    """Run a single-window GTK application with global-menu integration.

    window_factory is called when the application is activated. The returned
    Gtk.Window becomes owned by Gtk.Application and is shown once.
    """
    app = Gtk.Application(application_id=app_id)
    state = {"window": None}

    def startup(application):
        install_application_menu(
            application, app_name, lambda: state["window"], menu_builder)

    def activate(application):
        window = state["window"]
        if window is None or not window.get_realized():
            window = window_factory()
            state["window"] = window
            application.add_window(window)

            def on_destroy(_window):
                state["window"] = None

            window.connect("destroy", on_destroy)
        window.show_all()
        window.present()

    app.connect("startup", startup)
    app.connect("activate", activate)
    return app.run(argv)


def _show_about(window, app_name):
    if window is None:
        return
    dialog = Gtk.MessageDialog(
        transient_for=window,
        flags=Gtk.DialogFlags.MODAL,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.CLOSE,
        text="About %s" % app_name,
    )
    dialog.format_secondary_text("MavLinOS native application")
    dialog.run()
    dialog.destroy()
