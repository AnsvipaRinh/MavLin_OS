"""Shared GTK3 application-menu integration for MavLinOS native apps.

Uses Gtk.Application/GMenu so the Xfce AppMenu plugin can export the
application's menu to the Mavericks-style top panel.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk


def install_application_menu(app, app_name, get_window, menu_builder=None):
    """Install a small Mavericks-style application menu on a Gtk.Application."""

    def add_action(name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda *_: callback())
        app.add_action(action)

    add_action("about", lambda: _show_about(get_window(), app_name))
    add_action("quit", app.quit)
    add_action("close-window",
               lambda: get_window().destroy() if get_window() else None)
    add_action("minimize",
               lambda: get_window().iconify() if get_window() else None)

    if menu_builder is not None:
        menu = menu_builder(app, app_name, get_window, add_action)
    else:
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
        window_menu.append("Close Window", "app.close-window")
        menu.append_submenu("Window", window_menu)

        help_menu = Gio.Menu()
        help_menu.append("About %s" % app_name, "app.about")
        menu.append_submenu("Help", help_menu)

    app.set_app_menu(menu)
    return menu


def run_application(app_id, app_name, window_factory, argv=None):
    """Run a single-window GTK application with global-menu integration.

    window_factory is called when the application is activated. The returned
    Gtk.Window becomes owned by Gtk.Application and is shown once.
    """
    app = Gtk.Application(application_id=app_id)
    state = {"window": None}

    def startup(application):
        install_application_menu(
            application, app_name, lambda: state["window"])

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
