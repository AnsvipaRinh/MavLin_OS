#!/usr/bin/env python3
"""Gate: keyboard-shortcuts integrity for MavLinOS.

Validates three invariants that were broken before this gate existed:

1. NO ORPHAN BINDINGS — every command bound in
   xfce4-keyboard-shortcuts.xml must be resolvable: either a file
   installed by the mavericks-apps package (Makefile install list or
   bin/ directory), an external binary shipped by another ISO package
   (packages.x86_64 allowlist), or a system/Xfce component.
2. NO DOC DRIFT — every binding documented in docs/KEYBOARD.md must
   exist in BOTH XML copies (package config + airootfs skel mirror),
   with matching command; and no XML binding may be missing from the
   doc unless explicitly marked as not globally bound.
3. MIRROR SYNC — both XML copies must contain identical bindings
   (check-sync.sh compares bytes; this compares semantics).

Exit 0 on pass, 1 with a list of failures otherwise.
License: GPL-2.0-or-later.
"""
import os
import re
import sys
from html import unescape
from xml.etree import ElementTree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps")
XML_SRC = os.path.join(APPS, "config/xfce4-keyboard-shortcuts.xml")
XML_MIRROR = os.path.join(
    REPO,
    "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
    "xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml",
)
DOC = os.path.join(REPO, "docs/KEYBOARD.md")
MAKEFILE = os.path.join(APPS, "Makefile")
BIN_DIR = os.path.join(APPS, "bin")
PACKAGES = os.path.join(
    REPO, "archiso-profile/releng/packages.x86_64")

# Commands provided by other ISO packages or the base system — not mv-*.
EXTERNAL_ALLOWED = {
    "rofi", "pactl", "xfce4-terminal", "xfce4-screensaver-command",
    "thunar", "xdg-open", "skippy-xd", "plank", "xfdesktop",
    "trash-put", "trash-empty", "trash-list", "trash-restore",
}


def parse_bindings(path):
    """Return {key: command} for commands/default channel properties."""
    tree = ElementTree.parse(path)
    root = tree.getroot()
    out = {}
    for prop in root.iter("property"):
        if prop.get("name") != "commands":
            continue
        for dflt in prop.findall("property"):
            for leaf in dflt.findall("property"):
                key = unescape(leaf.get("name"))
                out[key] = leaf.get("value")
    return out


def installed_names():
    """Names the mavericks-apps package installs into /usr/bin."""
    names = set()
    mk = open(MAKEFILE, encoding="utf-8").read()
    for f in re.findall(r"bin/([\w.\-]+)", mk):
        names.add(f)
    if os.path.isdir(BIN_DIR):
        names.update(os.listdir(BIN_DIR))
    # explicit non-bin/ installs
    if "mv_desktop_cache.py" in mk:
        names.add("mv_desktop_cache.py")
    if 'mv-hud' in mk:
        names.add("mv-hud")
    return names


def first_token(command):
    """Executable token of a shell command line (strip path, env prefix)."""
    tok = command.strip().split()[0] if command.strip() else ""
    tok = tok.split(";")[0]
    return os.path.basename(tok)


def main():
    errors = []

    src = parse_bindings(XML_SRC)
    mirror = parse_bindings(XML_MIRROR)

    # --- 1. mirror semantic sync ---
    for k in sorted(set(src) | set(mirror)):
        if k not in src:
            errors.append("binding %r only in airootfs mirror" % k)
        elif k not in mirror:
            errors.append("binding %r only in package config" % k)
        elif src[k] != mirror[k]:
            errors.append("binding %r differs: %r vs %r"
                          % (k, src[k], mirror[k]))

    # --- 2. no orphan bindings ---
    installed = installed_names()
    pkgs = ""
    if os.path.isfile(PACKAGES):
        pkgs = open(PACKAGES, encoding="utf-8").read()
    for key, cmd in sorted(src.items()):
        exe = first_token(cmd)
        if not exe:
            errors.append("empty command for %r" % key)
            continue
        if exe.startswith("/"):
            exe = os.path.basename(exe)
        if exe in installed:
            continue
        if exe in EXTERNAL_ALLOWED:
            continue
        # xfwm4 built-in actions are values like "tile_up_key" — skip
        if re.match(r"^[a-z_]+$", exe) and exe.endswith("_key"):
            continue
        # external binaries present in the ISO package list
        if re.search(r"^%s$" % re.escape(exe), pkgs, re.M):
            continue
        errors.append("orphan binding: %r -> %r (executable %r is not "
                      "installed by mavericks-apps nor allowed external)"
                      % (key, cmd, exe))

    # --- 3. doc <-> xml consistency ---
    doc = open(DOC, encoding="utf-8").read()
    # rows: | Super+X | Action | Backend |
    # label -> xml key (raw, unescaped form)
    keymap = {
        "Super+Space": "<Super>space", "Super+L": "<Super>l",
        "Super+Tab": "<Super>Tab", "Super+Shift+F": "<Super><Shift>f",
        "Ctrl+Alt+N": "<Primary><Alt>n",
        "Super+Shift+N": "<Super><Shift>n",
        "Super+I": "<Super>i", "Super+O": "<Super>o",
        "Super+Shift+I": "<Super><Shift>i",
        "Super+Shift+O": "<Super><Shift>o",
        "Super+E": "<Super>e",
        "Super+Delete": "<Super>Delete",
        "Super+Shift+Delete": "<Super><Shift>Delete",
        "Super+Comma": "<Super>comma",
        "Super+Shift+C": "<Super><Shift>c",
        "Super+Shift+V": "<Super><Shift>v",
        "Super+Shift+Space": "<Super><Shift>space",
        "Ctrl+Alt+Escape": "<Primary><Alt>Escape",
        "Ctrl+Alt+Delete": "<Primary><Alt>Delete",
        "Ctrl+Alt+L": "<Primary><Alt>l",
        "Ctrl+Alt+T": "<Primary><Alt>t",
        "Ctrl+Alt+C": "<Primary><Alt>c",
        "Super+Q": "<Super>q", "Super+M": "<Super>m",
        "Super+H": "<Super>h", "Super+W": "<Super>w",
        "Super+Shift+3": "<Super><Shift>3",
        "Super+Shift+4": "<Super><Shift>4",
        "Super+Shift+5": "<Super><Shift>5",
        "XF86AudioRaiseVolume": "XF86AudioRaiseVolume",
        "XF86AudioLowerVolume": "XF86AudioLowerVolume",
        "XF86AudioMute": "XF86AudioMute",
        "XF86AudioPlay": "XF86AudioPlay",
        "XF86AudioNext": "XF86AudioNext",
        "XF86AudioPrev": "XF86AudioPrev",
        "XF86AudioStop": "XF86AudioStop",
        "XF86MonBrightnessUp": "XF86MonBrightnessUp",
        "XF86MonBrightnessDown": "XF86MonBrightnessDown",
    }
    doc_keys = set()
    section = ""
    app_level = False
    for line in doc.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            app_level = "not** globally bound" in \
                doc.split("## " + section, 1)[-1][:400] or \
                "still app-level" in section
            continue
        if app_level:
            continue
        m = re.match(r"\|\s*([^|]+?)\s*\|[^|]*\|[^|]*\|", line)
        if not m:
            continue
        label = m.group(1)
        if label in keymap:
            doc_keys.add(keymap[label])
        elif label.startswith("| Shortcut") or set(label) <= set("-: "):
            continue
        elif "+" in label and any(c.isdigit() or c.isalpha() for c in label):
            errors.append("doc row %r has no known binding mapping "
                          "(update keymap or fix the doc)" % label)

    for k in sorted(doc_keys):
        if k not in src:
            errors.append("documented binding %r missing from XML" % k)

    # every XML command binding should be documented (except xfwm4 handled
    # elsewhere; we only parsed commands/default)
    for k in sorted(src):
        if k not in doc_keys:
            errors.append("XML binding %r (%r) undocumented in KEYBOARD.md"
                          % (k, src[k]))

    if errors:
        for e in errors:
            print("FAIL - %s" % e)
        sys.exit(1)

    print("ok - %d bindings, no orphans, doc/XML consistent, mirrors synced"
          % len(src))


if __name__ == "__main__":
    main()
