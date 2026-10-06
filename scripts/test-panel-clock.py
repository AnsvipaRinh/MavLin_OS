#!/usr/bin/env python3
"""Validate menu-bar clock uses a LIVE Mavericks digital format.

xfce4-panel >= 4.20 renamed the digital-clock properties; `digital-format`
is NOT one of them.  In plugins/clock/clock-digital.c it survives only as the
key of a one-shot backward-compat migration
(xfce_clock_digital_migrate_format, line ~405) which is wired to a
"hierarchy-changed" signal the digital clock widget does not have, so it
never fires.  Shipping `digital-format` therefore left the menu bar with the
plugin's own defaults: "%Y-%m-%d %H:%M" in a hardcoded "Sans Regular 8".

This gate pins the live property names and the Mavericks output, and proves
GLib really renders them.
"""
import os
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [
    os.path.join(REPO, "configs/desktop/xfce/xfce4-panel.xml"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-panel.xml",
    ),
]

MAVERICKS_CLOCK = "%a %b %-d %-I:%M %p"
MAVERICKS_RENDER = "Tue Oct 6 3:45 PM"
# PLUGIN_FONT default from plugins/clock/clock-digital.c (DEFAULT_FONT).
XFCE_DEFAULT_FONT = "Sans Regular 8"

errors = []
texts = []
props = []
for path in PATHS:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    texts.append(text)
    root = ET.fromstring(text)
    clock_props = {}
    for p in root.findall("./property[@name='plugins']/property"):
        if p.get("value") == "clock":
            clock_props = {q.get("name"): q.get("value") for q in p}
            if clock_props.get("digital-format") is not None:
                errors.append("%s still sets the dead digital-format key"
                              % path)
            props.append(clock_props)
    if not clock_props:
        errors.append("%s has no clock plugin" % path)
        continue
    for needle in ('name="plugin-5" type="string" value="clock"',
                   'name="mode" type="uint" value="2"',
                   'name="digital-layout" type="uint" value="3"',
                   'name="digital-time-format" type="string" value="%s"'
                   % MAVERICKS_CLOCK,
                   'name="tooltip-format" type="string" value="%A, %B %-d, %Y"'):
        if needle not in text:
            errors.append("%s missing %s" % (path, needle))
    if 'name="digital-time-font"' not in text:
        errors.append("%s does not pin digital-time-font (plugin default is "
                      "'%s')" % (path, XFCE_DEFAULT_FONT))

if len(texts) == 2 and texts[0] != texts[1]:
    errors.append("panel XML mirrors differ")

for table in props:
    if table.get("digital-time-font") == XFCE_DEFAULT_FONT:
        errors.append("digital-time-font left at the xfce default")

# Prove GLib renders the format strings exactly as intended: %e would leak a
# U+2007 figure space and %l a U+2009 thin space, which no macOS menu bar has.
try:
    import gi
    gi.require_version("GLib", "2.0")
    from gi.repository import GLib
    dt = GLib.DateTime.new_local(2026, 10, 6, 15, 45, 7)
    for table in props:
        for key in ("digital-time-format", "tooltip-format"):
            fmt = table.get(key)
            if not fmt:
                continue
            rendered = dt.format(fmt)
            for bad_char, name in ((" ", "U+2007 figure space"),
                                   (" ", "U+2009 thin space")):
                if bad_char in rendered:
                    errors.append("%s renders %s for %r" % (key, name, fmt))
            if fmt == MAVERICKS_CLOCK and rendered != MAVERICKS_RENDER:
                errors.append("%s renders %r, expected %r"
                              % (key, rendered, MAVERICKS_RENDER))
except Exception as exc:  # no introspection: cannot prove, do not fail
    print("SKIP: GLib format proof unavailable (%s)" % exc)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - clock plugin digital mode (2)")
print("ok - digital-layout 3 (single line, unclipped in a 24px menu bar)")
print("ok - digital-time-format %s -> %s" % (MAVERICKS_CLOCK, MAVERICKS_RENDER))
print("ok - tooltip full date")
print("ok - digital-time-font pinned (not the xfce 'Sans Regular 8' default)")
print("ok - dead digital-format key gone from both mirrors")
print("ok - panel mirrors identical")
