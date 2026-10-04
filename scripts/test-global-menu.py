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
NATIVE_APPS = {
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


def main():
    panel = ET.parse(PANEL).getroot()
    plugins = panel.find("./property[@name='plugins']")
    ids = [v.get("value") for v in panel.findall("./property[@name='panels']/property[@name='panel-1']/property[@name='plugin-ids']/value")]
    assert ids == [str(i) for i in range(1, 7)], f"unexpected panel plugin IDs: {ids}"

    entries = {p.get("name"): p for p in plugins}
    assert entries["plugin-1"].get("value") == "appmenu"
    assert entries["plugin-2"].get("value") == "separator"
    assert entries["plugin-3"].get("value") == "systray"
    assert entries["plugin-4"].get("value") == "clock"
    assert entries["plugin-5"].get("value") == "actions"
    assert entries["plugin-6"].get("value") == "genmon"
    assert entries["plugin-2"].find("./property[@name='expand']").get("value") == "true"

    xsettings = ET.parse(XSETTINGS).getroot()
    gtk = xsettings.find("./property[@name='Gtk']")
    assert gtk is not None
    settings = {p.get("name"): p.get("value") for p in gtk}
    assert settings["ShellShowsMenubar"] == "true"
    assert settings["ShellShowsAppmenu"] == "true"
    assert settings["Modules"] == "appmenu-gtk-module"

    package_names = set(PACKAGES.read_text(encoding="utf-8").split())
    assert "vala-panel-appmenu" in package_names
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
    calculator = CALCULATOR.read_text(encoding="utf-8")
    assert "com.mavlinos.Calculator" in calculator
    assert "install_application_menu" in calculator
    assert "Gtk.main()" not in calculator

    for command, app_name in NATIVE_APPS.items():
        app = Path(
            "packages/mavericks-apps/src/mavericks-apps/bin/mv-" + command
        ).read_text(encoding="utf-8")
        assert "run_application" in app, f"{app_name} does not use the global-menu runner"
        assert "Gtk.main()" not in app, f"{app_name} still owns a private Gtk.main loop"

    print("OK: global menu integration contract")


if __name__ == "__main__":
    main()
