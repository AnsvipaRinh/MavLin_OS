#!/usr/bin/env python3
"""Validate the Mavericks icon theme tree (packages/mavericks-theme/.../icons).

Regression gate for the Poppy Tier 2 icon ports (clean-room SVGs) and for the
"plain text path file" defect class: nine scalable action icons and later
48 status/places files were shipped as text files containing relative paths
into an external Poppy-OS-X-Revieve checkout, which cannot exist on an
installed system (cp -r ships them verbatim) and would violate the
clean-room rule (no Poppy asset bytes) if it did.

Checks:
1. Every *.svg in the icon tree parses as XML and has an <svg> root.
2. No icon file references an external checkout path (Poppy-OS-X-Revieve
   substring ban) — catches re-introduced path-file breakage repo-wide.
3. Every symlink resolves to a real file inside the tree.
4. index.theme Directories list matches the directory set on disk
   (no unwired icon dirs, no dead index entries).
5. Required coverage: queued Poppy Tier 2 sets resolve somewhere in the
   tree (status dialogs, panel symbolic, places folders, preferences).

Exit 0 = all checks passed."""
import os
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(
    REPO, "packages/mavericks-theme/src/mavericks-theme/icons")
INDEX = os.path.join(ICONS, "index.theme")

# Icon names required to exist in at least one context dir (Tier 2 ports).
REQUIRED = [
    # 13 — status dialog icons
    "dialog-error", "dialog-information", "dialog-warning",
    "dialog-password", "image-loading",
    # 16 — panel symbolic (volume x4)
    "audio-volume-high-symbolic", "audio-volume-medium-symbolic",
    "audio-volume-low-symbolic", "audio-volume-muted-symbolic",
    # 16 — battery x8
    "battery-full-symbolic", "battery-good-symbolic",
    "battery-low-symbolic", "battery-empty-symbolic",
    "battery-full-charging-symbolic", "battery-good-charging-symbolic",
    "battery-low-charging-symbolic", "battery-empty-charging-symbolic",
    # 16 — network x6
    "network-wireless-signal-excellent-symbolic",
    "network-wireless-signal-good-symbolic",
    "network-wireless-signal-ok-symbolic",
    "network-wireless-signal-weak-symbolic",
    "network-wireless-signal-none-symbolic",
    "network-wired-symbolic",
    # 16 — notifications x2 + shutdown
    "notifications-symbolic", "notifications-disabled-symbolic",
    "system-shutdown-symbolic",
    # 15 — places folders
    "folder", "inode-directory", "folder-documents", "folder-download",
    "folder-music", "folder-pictures", "folder-videos", "folder-templates",
    "folder-publicshare", "folder-remote", "folder-saved-search",
    "folder-recent", "folder-desktop", "user-bookmarks", "folder-online",
    # 14 — preferences
    "preferences-desktop-display", "preferences-desktop-locale",
    "preferences-desktop-wallpaper", "preferences-desktop-notifications",
    "preferences-system-privacy", "preferences-system-time",
    "preferences-system", "preferences-desktop-accessibility",
    "preferences-desktop-online-accounts", "preferences-desktop-font",
]

# Known-broken text-path files still pending replacement in OTHER zones of
# the icon tree (mimetypes/apps/devices 128-256px, not the Tier 2 queues).
# Each entry here must be a file whose content starts with a Poppy checkout
# relative path. Shrink this list as zones get fixed; never grow it.
KNOWN_PENDING = {
    # other zones, pending owners
    "48x48/apps/system-file-manager.svg",
    "48x48/apps/utilities-terminal.svg",
    "256x256/apps/system-file-manager.svg",
    "256x256/apps/utilities-terminal.svg",
    "128x128/devices/drive-harddisk.svg",
    "128x128/apps/org.gnome.Software.svg",
    "128x128/apps/org.gnome.Totem.svg",
    "128x128/apps/system-file-manager.svg",
    "128x128/apps/eog.svg",
    "128x128/apps/office-calendar.svg",
    "128x128/apps/accessories-text-editor.svg",
    "128x128/apps/utilities-terminal.svg",
    "128x128/mimetypes/application-archive.svg",
    "128x128/mimetypes/application-x-deb.svg",
    "128x128/mimetypes/application-x-gzip.svg",
    "128x128/mimetypes/application-x-java.svg",
    "128x128/mimetypes/application-x-rar.svg",
    "128x128/mimetypes/application-xml.svg",
    "128x128/mimetypes/audio-mpeg.svg",
    "128x128/mimetypes/folder-tar.svg",
    "128x128/mimetypes/text-html.svg",
    "128x128/mimetypes/text-markdown.svg",
    "128x128/mimetypes/text-x-c++.svg",
    "128x128/mimetypes/text-x-c.svg",
    "128x128/mimetypes/text-x-generic.svg",
    "128x128/mimetypes/text-x-python.svg",
    "128x128/mimetypes/text-x-script.svg",
    "128x128/mimetypes/video-mp4.svg",
}

errors = []
present = set()


def rel(path):
    return os.path.relpath(path, ICONS)


for root, _dirs, files in os.walk(ICONS):
    for name in files:
        path = os.path.join(root, name)
        r = rel(path)
        if os.path.islink(path):
            target = os.path.realpath(path)
            if not os.path.isfile(target) or not target.startswith(ICONS):
                errors.append("broken symlink: %s" % r)
            else:
                present.add(os.path.splitext(name)[0])
            continue
        if not name.endswith(".svg"):
            continue
        try:
            raw = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as exc:
            errors.append("unreadable %s: %s" % (r, exc))
            continue
        if "Poppy-OS-X-Revieve" in raw:
            if r not in KNOWN_PENDING:
                errors.append(
                    "external-checkout path reference (clean-room/port "
                    "defect, not in KNOWN_PENDING): %s" % r)
            else:
                present.add(os.path.splitext(name)[0])
            continue
        try:
            node = ET.fromstring(raw)
            tag = node.tag.split("}")[-1].lower()
            if tag != "svg":
                raise ValueError("root is <%s>, not <svg>" % tag)
        except (ET.ParseError, ValueError) as exc:
            errors.append("invalid SVG %s: %s" % (r, exc))
            continue
        present.add(os.path.splitext(name)[0])

for r in sorted(KNOWN_PENDING):
    path = os.path.join(ICONS, r)
    if not os.path.isfile(path):
        errors.append("KNOWN_PENDING entry no longer exists (remove it): %s" % r)

missing = [n for n in REQUIRED if n not in present]
for n in missing:
    errors.append("required icon missing from theme: %s" % n)

if not os.path.isfile(INDEX):
    errors.append("index.theme missing")
else:
    listed = set()
    in_dirs = False
    for line in open(INDEX, encoding="utf-8"):
        line = line.strip()
        if line.startswith("Directories="):
            listed = {d for d in line.split("=", 1)[1].split(",") if d}
            in_dirs = True
    if not in_dirs:
        errors.append("index.theme has no Directories line")
    on_disk = set()
    for root, dirs, _files in os.walk(ICONS):
        if root != ICONS:
            for d in dirs:
                on_disk.add(os.path.relpath(os.path.join(root, d), ICONS))
    for d in sorted(listed - on_disk):
        errors.append("index.theme lists nonexistent dir: %s" % d)
    for d in sorted(on_disk - listed):
        errors.append("icon dir not wired into index.theme: %s" % d)

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - all SVGs parse, no external-checkout path files (pending: %d documented)"
      % len(KNOWN_PENDING))
print("ok - index.theme Directories <-> disk dirs consistent")
print("ok - required Tier 2 coverage present (%d names)" % len(REQUIRED))
