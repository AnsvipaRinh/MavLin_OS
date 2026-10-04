#!/usr/bin/env python3
"""Validate the MavLinOS global-menu integration contract."""

from pathlib import Path
import xml.etree.ElementTree as ET

PANEL = Path("archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml")
XSETTINGS = Path("archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml")
PACKAGES = Path("archiso-profile/releng/packages.x86_64")
PKGBUILD = Path("packages/vala-panel-appmenu/PKGBUILD")
APPMENU_HELPER = Path("packages/mavericks-apps/src/mavericks-apps/lib/mavericks_appmenu.py")
CALCULATOR = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-calculator")
TEXTEDIT = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-textedit")
FINDER = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns")
NOTES = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-notes")
CALENDAR = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-calendar")
MUSIC = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-music")
PREVIEW = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-preview")
PHOTOS = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-photos")
AIRDROP = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-airdrop")
STICKIES = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-stickies")
REMINDERS = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-reminders")
XFWM = Path("configs/desktop/xfce/xfwm4.xml")
APPLE_PLUGIN = Path("packages/mavericks-apps/src/mavericks-apps/panel/mv-apple.c")
APPLE_DESKTOP = Path("packages/mavericks-apps/src/mavericks-apps/panel/mv-apple.desktop")
APPLE_ICON = Path("packages/mavericks-apps/src/mavericks-apps/icons/mv-apple.svg")
FORCE_QUIT = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-force-quit")
RECENT_ITEMS = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-recent-items")

NATIVE_APPS = {
    "airdrop": "AirDrop",
    "about": "About This Mac",
    "activity": "Activity",
    "calendar": "Calendar",
    "colormeter": "Digital Color Meter",
    "diskutil": "Disk Utility",
    "finder-columns": "Finder",
    "fontbook": "Font Book",
    "console": "Console",
    "dictionary": "Dictionary",
    "notes": "Notes",
    "photos": "Photos",
    "preview": "Preview",
    "reminders": "Reminders",
    "settings": "System Preferences",
    "voice": "Voice Memos",
    "stickies": "Stickies",
    "music": "Music",
    "mail": "Mail",
    "keychain": "Keychain Access",
    "power-ui": "Power",
    "control": "Control Center",
    "notification-center": "Notification Center",
    "textedit": "TextEdit",
}




def check_apple_plugin():
    text = APPLE_PLUGIN.read_text()
    desktop = APPLE_DESKTOP.read_text()
    icon = APPLE_ICON.read_text()
    force_quit = FORCE_QUIT.read_text()
    assert "XFCE_PANEL_PLUGIN_REGISTER(construct)" in text
    assert "About This Mac" in text
    assert "System Preferences" in text
    assert "mv-recent-items" in text
    assert "xfce4-screensaver-command --lock" in text
    assert "signal.SIGKILL" in force_quit
    assert "xdotool" in force_quit
    assert "--onlyvisible" in force_quit
    assert "/proc/%d/comm" in force_quit
    assert "recently-used.xbel" in RECENT_ITEMS.read_text(encoding="utf-8")
    assert "systemctl suspend" in text
    assert "systemctl reboot" in text
    assert "systemctl poweroff" in text
    assert "xfce4-session-logout" in text
    assert "Type=X-XFCE-PanelPlugin" in desktop
    assert "X-XFCE-Internal=false" in desktop
    assert "viewBox=" in icon and "<path" in icon

def check_force_quit():
    force_quit = FORCE_QUIT.read_text(encoding="utf-8")
    assert 'xdotool' in force_quit
    assert '--onlyvisible' in force_quit
    assert 'getwindowpid' in force_quit
    assert 'signal.SIGKILL' in force_quit
    assert 'os.listdir("/proc")' not in force_quit


def main():
    check_apple_plugin()
    check_force_quit()
    panel = ET.parse(PANEL).getroot()
    plugins = panel.find("./property[@name='plugins']")
    ids = [v.get("value") for v in panel.findall("./property[@name='panels']/property[@name='panel-1']/property[@name='plugin-ids']/value")]
    assert ids == [str(i) for i in range(1, 7)], f"unexpected panel plugin IDs: {ids}"

    entries = {p.get("name"): p for p in plugins}
    assert entries["plugin-1"].get("value") == "mv-apple"
    assert entries["plugin-2"].get("value") == "appmenu"
    assert entries["plugin-3"].get("value") == "separator"
    assert entries["plugin-4"].get("value") == "systray"
    assert entries["plugin-5"].get("value") == "clock"
    assert entries["plugin-6"].get("value") == "power-manager-plugin"
    assert entries["plugin-3"].find("./property[@name='expand']").get("value") == "true"

    xsettings = ET.parse(XSETTINGS).getroot()
    gtk = xsettings.find("./property[@name='Gtk']")
    assert gtk is not None
    settings = {p.get("name"): p.get("value") for p in gtk}
    assert settings["ShellShowsMenubar"] == "true"
    assert settings["ShellShowsAppmenu"] == "true"
    assert settings["Modules"] == "appmenu-gtk-module"

    package_names = set(PACKAGES.read_text(encoding="utf-8").split())
    assert "vala-panel-appmenu" in package_names
    assert "xfce4-genmon-plugin" not in package_names
    assert "appmenu-gtk-module" in package_names
    build = PKGBUILD.read_text(encoding="utf-8")
    assert "-Dxfce=enabled" in build
    assert "-Dregistrar=enabled" in build
    for disabled in ("-Dmate=disabled", "-Dbudgie=disabled", "-Dvalapanel=disabled"):
        assert disabled in build

    xfwm = XFWM.read_text(encoding="utf-8")
    assert 'name="titleless_maximize" type="bool" value="true"' in xfwm

    helper = APPMENU_HELPER.read_text(encoding="utf-8")
    assert "Gtk.Application" in helper
    assert "app.set_app_menu(menu)" in helper
    assert "application.add_window(window)" in helper
    assert "window.present()" in helper
    assert "menu_builder=None" in helper
    finder = FINDER.read_text(encoding="utf-8")
    notes = NOTES.read_text(encoding="utf-8")
    assert "build_finder_menu" in finder
    assert "menu.append_submenu(\"Edit\"" not in finder
    for action in ("Open in Thunar…", "Zoom In", "Zoom Out", "Actual Size", "Back", "Home"):
        assert action in finder, f"Finder menu missing {action}"
    calendar = CALENDAR.read_text(encoding="utf-8")
    assert "build_calendar_menu" in calendar
    for action in ("New Event", "Import…", "Export…", "Month", "Week", "Day", "Today", "Sync EDS"):
        assert action in calendar, f"Calendar menu missing {action}"
    music = MUSIC.read_text(encoding="utf-8")
    assert "build_music_menu" in music
    for action in ("Previous Track", "Play / Pause", "Next Track", "Songs", "Albums", "Artists", "Queue", "Mini Player"):
        assert action in music, f"Music menu missing {action}"
    preview = PREVIEW.read_text(encoding="utf-8")
    assert "build_preview_menu" in preview
    for action in ("Previous Page", "Next Page", "Fullscreen", "Previous File", "Next File",
                   "Text Annotation", "Shape Annotation", "Signature"):
        assert action in preview, f"Preview menu missing {action}"
    control = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-control").read_text(encoding="utf-8")
    power_ui = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-power-ui").read_text(encoding="utf-8")
    photos = PHOTOS.read_text(encoding="utf-8")
    airdrop = AIRDROP.read_text(encoding="utf-8")
    assert "build_photos_menu" in photos
    assert "Gtk.Application(application_id=" in photos
    assert "Gtk.main_quit()" not in photos
    assert "Gtk.main()" not in airdrop
    assert "Gtk.main_quit()" not in airdrop
    assert "run_application(" in airdrop
    assert "Gtk.main()" not in control
    assert "Gtk.main_quit()" not in control
    assert "Gtk.main()" not in power_ui
    assert "Gtk.main_quit()" not in power_ui
    assert "sys.exit(main())" in photos
    for action in ("Import Photos…", "New Album…", "All Photos", "Favorites",
                   "Recently Added", "Start / Stop Slideshow"):
        assert action in photos, f"Photos menu missing {action}"
    stickies = STICKIES.read_text(encoding="utf-8")
    assert "build_stickies_menu" in stickies
    for action in ("New Note", "Print Note…", "Find in Stickies…",
                   "Delete Note", "Collapse / Expand Note"):
        assert action in stickies, f"Stickies menu missing {action}"
    mail = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-mail").read_text(encoding="utf-8")
    assert "build_mail_menu" in mail
    for action in ("Open Mail", "Close Window"):
        assert action in mail, f"Mail menu missing {action}"
    keychain = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-keychain").read_text(encoding="utf-8")
    assert "build_keychain_menu" in keychain
    for action in ("New Password Item", "Password Generator", "Find",
                   "Delete Selected Item", "Lock Keychain Items"):
        assert action in keychain, f"Keychain menu missing {action}"
    reminders = REMINDERS.read_text(encoding="utf-8")
    assert "build_reminders_menu" in reminders
    for action in ("New Task", "New List", "Edit Selected Task",
                   "Toggle Completed", "Delete Selected Task",
                   "Clear Completed", "Find Reminders", "Rename List", "Delete List"):
        assert action in reminders, f"Reminders menu missing {action}"
    assert "build_notes_menu" in notes
    for action in ("New Note", "New Folder", "Export Note…", "Print…", "Find"):
        assert action in notes, f"Notes menu missing {action}"
    textedit = TEXTEDIT.read_text(encoding="utf-8")
    assert 'add_action("about", lambda: None)' not in textedit
    assert "build_textedit_menu" in textedit
    for action in ("New", "Open…", "Save", "Undo", "Redo", "Cut", "Copy", "Paste", "Find", "Bold", "Italic", "Underline"):
        assert action in textedit, f"TextEdit menu missing {action}"
    custom_menu_apps = (finder, notes, calendar, music, preview, photos, stickies, reminders, mail, keychain, textedit)
    for custom_app in custom_menu_apps:
        assert 'add_action("about", lambda: None)' not in custom_app, "custom menu overrides shared About action"
    calculator = CALCULATOR.read_text(encoding="utf-8")
    assert "com.mavlinos.Calculator" in calculator
    assert "install_application_menu" in calculator
    assert "Gtk.main()" not in calculator

    lifecycle_exceptions = {"stickies", "music", "preview", "photos"}
    for command, app_name in NATIVE_APPS.items():
        app = Path(
            "packages/mavericks-apps/src/mavericks-apps/bin/mv-" + command
        ).read_text(encoding="utf-8")
        if command not in lifecycle_exceptions:
            assert "run_application" in app, f"{app_name} does not use the global-menu runner"
        assert "Gtk.main()" not in app, f"{app_name} still owns a private Gtk.main loop"
        assert "Gtk.Application" in app, f"{app_name} does not use Gtk.Application"

    print("OK: global menu integration contract")


if __name__ == "__main__":
    main()
