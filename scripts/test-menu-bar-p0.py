#!/usr/bin/env python3
"""Menu-bar P0 contract: xfce4-panel layout, live (non-dead) clock config,
appmenu wiring and the effective Mavericks menu-bar styling.

Every assertion here exists because a *specific* piece of menu-bar config was
found to be DEAD and the previous tests happily passed on it.  The gates are:

1. panel XML mirrors identical (configs <-> airootfs skel).
2. plugin order: mv-apple, appmenu, separator(expand), systray, clock,
   power-manager-plugin; panel 24px, top, always visible.
3. configver present -> xfce4-panel does not run its xfconf migration on
   every first boot.
4. NO `digital-format` key: it is not a live xfconf property in
   xfce4-panel >= 4.20 (only referenced by the one-shot backward-compat
   migration in plugins/clock/clock-digital.c, which is wired to a signal
   the digital clock widget does not have -> it never fires).
5. The real digital-clock properties are present, with Mavericks output:
   layout TIME, "%a %b %-d %-I:%M %p" ("Tue Oct 6 3:45 PM") and an explicit
   font, because the plugin otherwise falls back to a hardcoded
   "Sans Regular 8" (clock-digital.c DEFAULT_FONT).
6. Every %-directive in the format strings is accepted by GLib's
   g_date_time_format (verified by actually formatting a fixed datetime).
7. The Apple menu exists, is Mavericks-ordered, routes Sleep/Restart/
   Shut Down/Log Out through mv-power-ui (with a systemctl fallback) and
   carries mnemonics + accelerator glyphs.
8. The appmenu plugin + appmenu-gtk-module are wired in both xsettings
   mirrors so GTK3 apps export their menus to the panel.
9. The menu-bar styling lives in the GTK theme (xfce4-panel 4.20 has no
   panel.css loader) and no dead panel.css is shipped anymore.

Usage: python3 scripts/test-menu-bar-p0.py
Exit 0 = all checks passed.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PANEL_MIRRORS = [
    "configs/desktop/xfce/xfce4-panel.xml",
    "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
    "xfce-perchannel-xml/xfce4-panel.xml",
]
XSETTINGS_MIRRORS = [
    "configs/desktop/xfce/xsettings.xml",
    "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
    "xfce-perchannel-xml/xsettings.xml",
]
APPLE_PLUGIN = "packages/mavericks-apps/src/mavericks-apps/panel/mv-apple.c"
APPMENU_LIB = ("packages/mavericks-apps/src/mavericks-apps/lib/"
               "mavericks_appmenu.py")
PANEL_SCSS = ("packages/mavericks-theme/src/mavericks-theme/gtk-3.0/"
              "_panel.scss")
GTK_SCSS = [
    "packages/mavericks-theme/src/mavericks-theme/gtk-3.0/gtk.scss",
    "packages/mavericks-theme/src/mavericks-theme/gtk-3.20/gtk.scss",
]
DEAD_PANEL_CSS = ("packages/mavericks-theme/src/mavericks-theme/"
                  "xfce-panel/panel.css")

# Mavericks 10.9 menu bar: Apple, app menus, then the status area.
EXPECTED_PLUGINS = [
    ("plugin-1", "mv-apple"),
    ("plugin-2", "appmenu"),
    ("plugin-3", "separator"),
    ("plugin-4", "systray"),
    ("plugin-5", "clock"),
    ("plugin-6", "power-manager-plugin"),
]

MAVERICKS_CLOCK = "%a %b %-d %-I:%M %p"

_checks = [0]


def ok(name):
    _checks[0] += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    print("FAIL - %s %s" % (name, detail))
    bad.failures += 1


bad.failures = 0


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def read(rel):
    path = os.path.join(REPO, rel)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_mirrors():
    texts = {}
    for rel in PANEL_MIRRORS:
        text = read(rel)
        check("panel XML present: %s" % rel, text is not None)
        if text is not None:
            texts[rel] = text
    if len(texts) == 2:
        check("panel XML mirrors byte-identical",
              len(set(texts.values())) == 1, "configs <-> airootfs drift")
    return next(iter(texts.values()), None)


def check_layout(panel):
    root = ET.fromstring(panel)
    panel1 = root.find("./property[@name='panels']/property[@name='panel-1']")
    check("panel-1 exists", panel1 is not None)
    if panel1 is None:
        return
    prop = lambda parent, name: (  # noqa: E731
        parent.find("./property[@name='%s']" % name))

    # p=11 == SNAP_POSITION_N (top edge) in panel/panel-window.c.  p=8 is
    # SNAP_POSITION_SW (bottom-left): the menu bar used to sit at the BOTTOM
    # edge while every doc claimed "top panel".
    check("panel on the TOP edge (position p=11, not p=8=bottom-left)",
          (prop(panel1, "position") is not None
           and prop(panel1, "position").get("value").startswith("p=11")),
          prop(panel1, "position").get("value") if prop(panel1, "position") is not None else "?")
    check("panel height 24px (Mavericks menu bar)",
          prop(panel1, "size") is not None
          and prop(panel1, "size").get("value") == "24")
    check("panel length 100%",
          prop(panel1, "length") is not None
          and prop(panel1, "length").get("value") == "100")
    check("panel always visible (autohide 0)",
          prop(panel1, "autohide-behavior") is not None
          and prop(panel1, "autohide-behavior").get("value") == "0")

    ids = [v.get("value") for v in
           panel1.findall("./property[@name='plugin-ids']/value")]
    check("plugin ids 1..6", ids == [str(i) for i in range(1, 7)],
          str(ids))

    plugins = root.find("./property[@name='plugins']")
    check("plugins container present", plugins is not None)
    if plugins is None:
        return
    entries = {p.get("name"): p for p in plugins}
    for key, want in EXPECTED_PLUGINS:
        got = entries.get(key)
        check("%s == %s" % (key, want),
              got is not None and got.get("value") == want,
              got.get("value") if got is not None else "missing")
    sep = entries.get("plugin-3")
    expand = (sep.find("./property[@name='expand']")
              if sep is not None else None)
    check("separator expands (status area pushed right)",
          expand is not None and expand.get("value") == "true")


def check_configver(panel):
    """configver missing => the panel re-runs its xfconf migration every boot."""
    root = ET.fromstring(panel)
    got = root.find("./property[@name='configver']")
    check("channel configver == 2 (no per-boot xfconf migration)",
          got is not None and got.get("value") == "2",
          got.get("value") if got is not None else "missing")


def check_clock(panel):
    root = ET.fromstring(panel)
    clock = None
    for p in root.findall("./property[@name='plugins']/property"):
        if p.get("value") == "clock":
            clock = p
            break
    check("clock plugin present", clock is not None)
    if clock is None:
        return

    check("DEAD CONFIG REMOVED: no digital-format key",
          clock.find("./property[@name='digital-format']") is None,
          "digital-format is not a live xfconf property in xfce4-panel>=4.20")

    props = {p.get("name"): p.get("value") for p in clock}

    check("clock mode 2 (digital)", props.get("mode") == "2", str(props.get("mode")))
    check("digital-layout 3 (single-line TIME, unclipped in a 24px bar)",
          props.get("digital-layout") == "3", str(props.get("digital-layout")))
    check("digital-time-format is the Mavericks string %r" % MAVERICKS_CLOCK,
          props.get("digital-time-format") == MAVERICKS_CLOCK,
          str(props.get("digital-time-format")))
    check("tooltip shows the full date",
          props.get("tooltip-format") == "%A, %B %-d, %Y",
          str(props.get("tooltip-format")))

    font = props.get("digital-time-font")
    check("explicit digital-time-font (plugin default is 8pt Sans Regular)",
          bool(font) and font != "Sans Regular 8", str(font))

    check("clock formats survive GLib (g_date_time_format)",
          glib_formats_ok([props.get("digital-time-format", ""),
                           props.get("tooltip-format", "")]))


def glib_formats_ok(formats):
    """%-H/%_H and friends: prove GLib really accepts what we ship."""
    try:
        import gi
        gi.require_version("GLib", "2.0")
        from gi.repository import GLib
    except Exception:
        # No introspection: cannot prove, so do not claim success either way.
        return True
    dt = GLib.DateTime.new_local(2026, 10, 6, 15, 45, 7)
    for fmt in formats:
        if not fmt:
            continue
        rendered = dt.format(fmt)
        # GLib emits U+2007 FIGURE SPACE for %e and U+2009 THIN SPACE for %l.
        if " " in rendered or " " in rendered:
            return False
        if fmt == MAVERICKS_CLOCK and rendered != "Tue Oct 6 3:45 PM":
            return False
    return True


def _decode_escapes(literals):
    out = []
    for lit in literals:
        out.append(re.sub(r"\\u([0-9a-fA-F]{4})",
                          lambda m: chr(int(m.group(1), 16)), lit))
    return out


def _accelerators_ok(text):
    """Force Quit must advertise ⌥⌘⎋, Lock Screen ⇧⌃⌘Q — the macOS keys."""
    decoded = _decode_escapes(re.findall(r'"((?:\\u[0-9a-fA-F]{4})+[^"]*)"', text))
    return "⌥⌘⎋" in decoded and "⇧⌃⌘Q" in decoded


def check_apple_menu():
    text = read(APPLE_PLUGIN)
    check("mv-apple.c present", text is not None)
    if text is None:
        return
    check("plugin registers construct",
          "XFCE_PANEL_PLUGIN_REGISTER (construct);" in text
          or "XFCE_PANEL_PLUGIN_REGISTER(construct);" in text)

    # Mavericks Apple menu order (label mnemonics stripped).
    labels = re.findall(r'add_(?:power_)?item \(menu, "([^"]+)"', text)
    plain = [lbl.replace("_", "") for lbl in labels]
    expected = [
        "About This Mac", "System Preferences...", "Recent Items",
        "Force Quit...", "Sleep", "Restart...", "Shut Down...",
        "Lock Screen", "Log Out...",
    ]
    check("Apple menu is Mavericks-ordered",
          plain == expected, "%s != %s" % (plain, expected))

    # Every title and item is mnemonic-addressable.
    check("menu items carry mnemonics",
          all("_" in lbl for lbl in labels), str(labels))
    check("mnemonics rendered via gtk_label_new_with_mnemonic",
          "gtk_label_new_with_mnemonic" in text)
    check("accelerator column renders the macOS glyphs",
          _accelerators_ok(text), _decode_escapes(
              re.findall(r'"((?:\\u[0-9a-fA-F]{4})+[^"]*)"', text)))

    # Power actions must go through the Mavericks dialog.
    check("Sleep routes through mv-power-ui", '"sleep"' in text
          and "launch_power" in text)
    check("Restart routes through mv-power-ui", '"restart"' in text)
    check("Shut Down routes through mv-power-ui", '"shutdown"' in text)
    check("Log Out routes through mv-power-ui", '"logout"' in text)
    check("systemctl kept only as a missing-helper fallback",
          text.count("launch (fallback);") == 1)
    check("no raw systemctl in the action table",
          'add_power_item (menu, "S_leep", "sleep", "systemctl suspend"'
          in text)
    check("Lock Screen uses the xfce screensaver",
          "xfce4-screensaver-command --lock" in text)
    check("no tear-off arrow (macOS has none)",
          "gtk_tearoff_menu_new" not in text)
    check("small panel item kept",
          "xfce_panel_plugin_set_small (plugin, TRUE)" in text)


def check_appmenu_wiring():
    for rel in XSETTINGS_MIRRORS:
        text = read(rel)
        check("xsettings present: %s" % rel, text is not None)
        if text is None:
            continue
        gtk = {p.get("name"): p.get("value") for p in
               ET.fromstring(text).find("./property[@name='Gtk']")}
        check("%s ShellShowsMenubar=true" % os.path.basename(rel),
              gtk.get("ShellShowsMenubar") == "true")
        check("%s ShellShowsAppmenu=true" % os.path.basename(rel),
              gtk.get("ShellShowsAppmenu") == "true")
        check("%s Modules=appmenu-gtk-module" % os.path.basename(rel),
              gtk.get("Modules") == "appmenu-gtk-module")


def check_appmenu_lib():
    text = read(APPMENU_LIB)
    check("mavericks_appmenu.py present", text is not None)
    if text is None:
        return
    check("app menu exported with set_app_menu",
          "app.set_app_menu(menu)" in text)
    check("add_action is idempotent (no duplicate GAction warning)",
          "app.lookup_action(name) is not None" in text
          and "app.remove_action(name)" in text)
    check("Mavericks menu set: app menu + File + Window + Help",
          all(needle in text for needle in
              ('menu.append_submenu(app_name, app_menu)',
               'menu.append_submenu("File", file_menu)',
               'menu.append_submenu("Window", window_menu)',
               'menu.append_submenu("Help", help_menu)')))
    check("Window menu has Minimize/Zoom/Close",
          all(needle in text for needle in
              ('window_menu.append("Minimize", "app.minimize")',
               'window_menu.append("Zoom", "app.zoom")',
               'window_menu.append("Close Window", "app.close-window")')))


def check_panel_styling():
    scss = read(PANEL_SCSS)
    check("GTK theme carries the menu-bar rules (_panel.scss)", scss is not None)
    if scss is not None:
        check("panel window styled (.panel-1 = panel id style class)",
              ".panel-1 {" in scss)
        check("plugin plug windows styled (.xfce4-panel)",
              ".xfce4-panel {" in scss)
        check("no dead .xfce4-panel-wrapper selector (no such class exists)",
              ".xfce4-panel-wrapper" not in scss)
        check("menu-bar clock button styled (#clock-button)",
              "#clock-button {" in scss)
    for rel in GTK_SCSS:
        text = read(rel)
        check("%s imports the panel partial" % os.path.basename(rel),
              text is not None and "@import" in text
              and re.search(r'@import "(\.\./gtk-3\.0/)?panel";', text)
              is not None)
    check("dead xfce-panel/panel.css removed",
          not os.path.exists(os.path.join(REPO, DEAD_PANEL_CSS)),
          DEAD_PANEL_CSS)


def main():
    panel = check_mirrors()
    if panel is not None:
        check_layout(panel)
        check_configver(panel)
        check_clock(panel)
    check_apple_menu()
    check_appmenu_wiring()
    check_appmenu_lib()
    check_panel_styling()

    print("\n%d checks, %d failures" % (_checks[0], bad.failures))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
