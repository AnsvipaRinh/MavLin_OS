#!/usr/bin/env bash
# make-demo-home.sh — build a deterministic demo HOME for the visual demo.
#
# The demo session (run-demo.sh) runs the REAL MavLinOS session components
# (xfwm4 + xfdesktop + xfce4-panel + plank + mv-* apps, Mavericks theme)
# against an isolated Xvfb, with HOME pointed at a generated directory.
# This script fills that directory:
#   * product session config: copied from the ISO skel (archiso-profile) —
#     the same files a real user gets on first boot;
#   * minimal, documented demo overrides (see OVERRIDES below);
#   * temporary demo content (folders/files to look at in Finder).
#
# Everything here is disposable demo data; no product file is modified.
# License: GPL-2.0-or-later.
set -euo pipefail

DEMO_ROOT="${1:?usage: make-demo-home.sh <demo-root> <repo-root>}"
REPO="${2:?usage: make-demo-home.sh <demo-root> <repo-root>}"

HOME_DIR="$DEMO_ROOT/home"
PREFIX="$DEMO_ROOT/prefix"
SKEL="$REPO/archiso-profile/releng/airootfs/etc/skel"
WALLPAPER="$PREFIX/usr/share/backgrounds/mavericks/mavericks-desktop.png"

rm -rf "$HOME_DIR"
mkdir -p "$HOME_DIR"

# ---------------------------------------------------------------- skel copy
cp -r "$SKEL/." "$HOME_DIR/"
mkdir -p "$HOME_DIR/.config/xfce4/xfconf/xfce-perchannel-xml"
# skel only carries a subset of xfconf channels; configs/desktop holds the rest
for f in xfce4-desktop.xml; do
    [ -f "$SKEL/.config/xfce4/xfconf/xfce-perchannel-xml/$f" ] || \
        cp "$REPO/configs/desktop/xfce/$f" \
           "$HOME_DIR/.config/xfce4/xfconf/xfce-perchannel-xml/$f"
done

# ------------------------------------------------------------- OVERRIDES
XFCONF="$HOME_DIR/.config/xfce4/xfconf/xfce-perchannel-xml"

# 1. panel: drop the appmenu (global menu) plugin — vala-panel-appmenu is
#    not buildable in this container (no valac/meson); everything else is
#    the product panel (mv-apple Apple menu, systray, clock, power).
python3 - "$XFCONF/xfce4-panel.xml" <<'EOF'
import re, sys
p = sys.argv[1]
s = open(p).read()
s = s.replace('        <value type="int" value="2"/>\n', '')
s = re.sub(r'    <property name="plugin-2" type="string" value="appmenu"/>\n', '', s)
open(p, 'w').write(s)
EOF

# 2. wallpaper: point at the staged current-theme wallpaper (demo prefix)
sed -i "s|<property name=\"image-path\" type=\"string\" value=\"[^\"]*\"/>|<property name=\"image-path\" type=\"string\" value=\"$WALLPAPER\"/>|" \
    "$XFCONF/xfce4-desktop.xml"
# cover every monitor-name layout Xvfb may present (monitor0 / monitorVNStr)
python3 - "$XFCONF/xfce4-desktop.xml" "$WALLPAPER" <<'EOF'
import sys, xml.etree.ElementTree as ET
p, wall = sys.argv[1], sys.argv[2]
t = ET.parse(p); r = t.getroot()
screen = r.find("./property[@name='backdrop']/property[@name='screen0']")
for mon in ("monitor0", "monitorVNStr"):
    m = screen.find(f"./property[@name='{mon}']")
    if m is None:
        m = ET.SubElement(screen, "property", {"name": mon, "type": "empty"})
    ws = m.find("./property[@name='workspace0']")
    if ws is None:
        ws = ET.SubElement(m, "property", {"name": "workspace0", "type": "empty"})
    ip = ws.find("./property[@name='image-path']")
    if ip is None:
        ip = ET.SubElement(ws, "property", {"name": "image-path", "type": "string"})
    ip.set("value", wall)
    for k, v in (("image-style", "5"), ("color-style", "0")):
        e = ws.find(f"./property[@name='{k}']")
        if e is None:
            e = ET.SubElement(ws, "property", {"name": k, "type": "int"})
        e.set("value", v)
t.write(p, encoding="UTF-8", xml_declaration=True)
EOF

# 3. xsettings: 96 DPI for the 1680x1050 demo display (product value 192 is
#    the provisional Retina-panel setting for the real MacBook10,1 screen).
sed -i 's|<property name="DPI" type="int" value="192"/>|<property name="DPI" type="int" value="96"/>|' \
    "$XFCONF/xsettings.xml"

# 3b. panel: snap to the TOP edge (Mavericks menu bar position).  The skel
#     value p=8 lands on the bottom edge with xfce4-panel 4.20.x in this
#     environment; p=1 is top-center (verified live on the demo display).
sed -i 's|<property name="position" type="string" value="p=8;x=0;y=0"/>|<property name="position" type="string" value="p=1;x=0;y=0"/>|' \
    "$XFCONF/xfce4-panel.xml"

# 4. plank: always visible for deterministic screenshots (product skel uses
#    intellihide HideMode=1, which cannot be forced open by remote control)
sed -i 's/^HideMode=1$/HideMode=0/' "$HOME_DIR/.config/plank/dock1/settings"

# 5. Finder sidebar bookmarks (Places the demo Finder should show)
mkdir -p "$HOME_DIR/.config/gtk-3.0"
cat > "$HOME_DIR/.config/gtk-3.0/bookmarks" <<EOF
file://$HOME_DIR/Documents
file://$HOME_DIR/Pictures
file://$HOME_DIR/Projects
file://$HOME_DIR/Downloads
file://trash:///
EOF

# 6. desktop icons: no removable-device icons on the demo desktop (the WSLg
#    host exposes its own volumes, which would show up as stray "101 …"/
#    "758 …" icons). Product skel enables them for the real machine.
sed -i 's|<property name="show-removable" type="bool" value="true"/>|<property name="show-removable" type="bool" value="false"/>|' \
    "$XFCONF/xfce4-desktop.xml"
sed -i 's|<property name="show-filesystem" type="bool" value="false"/>|<property name="show-filesystem" type="bool" value="false"/>|' \
    "$XFCONF/xfce4-desktop.xml"

# ------------------------------------------------------- demo content tree
mkdir -p "$HOME_DIR"/{Documents,Pictures/Screenshots,Music,Movies,Downloads,Projects/mavlinos,Desktop}
cp "$WALLPAPER" "$HOME_DIR/Pictures/mavericks-desktop.png"

cat > "$HOME_DIR/Documents/MavLinOS Project Brief.md" <<'EOF'
# MavLinOS — Linux for the MacBook 12"

MavLinOS is a Mavericks-era (OS X 10.9) desktop experience for Linux,
targeting the MacBook (Retina, 12-inch, Early 2017).

- Xfce + X11 backend, GTK3 Mavericks theme, plank dock, global menu bar
- 40+ Mavericks-style applications (Finder, Spotlight, Launchpad,
  Mission Control, Notes, Calendar, …) on mature Linux backends
- Built as a bootable Arch Linux ISO for real hardware
EOF

cat > "$HOME_DIR/Documents/Q4 Roadmap.txt" <<'EOF'
Q4 ROADMAP (excerpt)
====================
1. Finder column view parity
2. Mission Control dedicated overview layer (issue #1)
3. Power baseline validation on hardware
4. ISO release candidate
EOF

cat > "$HOME_DIR/Documents/Meeting Notes 2026-10-01.md" <<'EOF'
# Meeting Notes — 2026-10-01

Attendees: core team

- Reviewed Mission Control fidelity ceiling evidence
- Agreed: dedicated GTK overlay + XComposite thumbnails
- Next demo: visual walkthrough for prospective contributors
EOF

cat > "$HOME_DIR/Projects/notes.txt" <<'EOF'
Demo project scratchpad.
The Finder window you are looking at is the real MavLinOS Finder:
Thunar with the Mavericks theme, custom context actions, bookmarks
and Finder-style keyboard shortcuts.
EOF

cat > "$HOME_DIR/Projects/mavlinos/hello.c" <<'EOF'
#include <stdio.h>
int main(void) { puts("Hello from MavLinOS"); return 0; }
EOF

cat > "$HOME_DIR/Projects/mavlinos/README.md" <<'EOF'
# mavlinos demo repo
Scratch files used by the visual demo session.
EOF

echo "ok - demo home ready at $HOME_DIR"
