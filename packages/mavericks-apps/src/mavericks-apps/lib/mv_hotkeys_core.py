#!/usr/bin/env python3
"""mv_hotkeys_core — the MavLinOS global keyboard shortcut layer core.

Design (P0 #23, AGENTS.md §6 "Keyboard shortcut architecture"):

  * ONE authoritative registry (`ACTIONS`) maps a conceptual action id to
    its Mavericks-style accelerator, the command it runs, the Xfce channel
    branch it lives in and the System Settings skill group it is shown
    under.  The registry is the source of truth: the packaged
    `xfce4-keyboard-shortcuts.xml` is checked against it (drift detection)
    and can be regenerated from it.
  * USER OVERRIDES live in `~/.config/mfkeys/overrides.json` (a small JSON
    file, not a second copy of the defaults).  Only the actions the user
    actually changed are recorded, so the shipped XML stays the pristine
    factory state and `reset` is always possible.
  * APPLICATION is via `xfconf-query` on the live channel, so a rebind
    takes effect immediately without restarting anything.  This repo runs
    a real xfconf on the default system profile, so the channel must NOT
    be unloaded by mistake.
  * NOTHING here is a daemon: every entry point is a one-shot CLI call.
  * Standard Linux shortcuts and the hardware function row are PROTECTED:
    rebinding them is refused unless `--force` is given, so the layer can
    never swallow Ctrl+Alt+T, Alt+Tab, brightness or audio keys.

Origin: architecture, action registry layout, conflict/protection model and
the CLI surface (`list/show/set/reset/verify/export/import`) were produced
by Qwen Code (qwen3.8-flash) driven through
`scripts/qwen-integration/qwen-web-worker.py` on 2026-10-06; its delivered
`mv-hotkeys` draft is kept in git history.  This module supersedes it after
review: the accelerator model was changed from "action -> xfconf property
name" (which cannot express a rebind, since the key *is* part of the
property name) to "action -> modifiers + key + command" (see
docs/DECISIONS.md), protected hardware keys were completed, and XML
rendering/drift detection was added.

Pure logic (registry, override merging, accelerator parsing/formatting,
conflict detection, XML rendering/parsing) is importable headless — no gi,
no GTK, no xfconf.  License: GPL-2.0-or-later.
"""
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET

CHANNEL = "xfce4-keyboard-shortcuts"
DEFAULT_OVERRIDES_PATH = os.path.expanduser("~/.config/mfkeys/overrides.json")
# MV_HOTKEYS_OVERRIDES lets tests (and a temporary session) redirect the
# override file without touching the user's real one.
OVERRIDES_PATH = os.environ.get("MV_HOTKEYS_OVERRIDES",
                                DEFAULT_OVERRIDES_PATH)
FACTORY_XML_CANDIDATES = [
    "/usr/share/mavericks-apps/xfce4-keyboard-shortcuts.xml",
]
# Repo-relative fallback (running straight from a checkout).
FACTORY_XML_CANDIDATES.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                 "config", "xfce4-keyboard-shortcuts.xml"))

BRANCH_COMMANDS = "commands"
BRANCH_XFWM4 = "xfwm4"
BRANCHES = (BRANCH_COMMANDS, BRANCH_XFWM4)

# Modifier canonical order used by xfconf: <Primary><Alt><Super><Shift>.
# Secondary is accepted and preserved but not offered by the GUI (it needs
# the raw keysym, which the registry deliberately does not model).
MODIFIER_ORDER = ("Primary", "Alt", "Super", "Shift")
MODIFIER_ALIASES = {
    "ctrl": "Primary", "control": "Primary", "primary": "Primary",
    "alt": "Alt", "option": "Alt", "opt": "Alt",
    "super": "Super", "win": "Super", "windows": "Super", "meta": "Super",
    "cmd": "Super", "command": "Super",
    "shift": "Shift",
}
MODIFIER_LABELS = {
    "Primary": "Ctrl", "Alt": "Alt", "Super": "Super", "Shift": "Shift",
}
ACCEL_MODIFIER_LABELS = {
    "Primary": "Ctrl", "Alt": "Alt", "Super": "Super", "Shift": "Shift",
}

# Named keys offered by the recorder / renderer.  Keysym names are
# case-sensitive in X11, which is why this table exists.
NAMED_KEYS = (
    "space", "Tab", "Return", "Escape", "Delete", "Home", "End",
    "Up", "Down", "Left", "Right", "Prior", "Next",
    "comma", "period", "slash", "backslash", "minus", "equal", "semicolon",
    "apostrophe", "grave", "bracketleft", "bracketright",
    "Insert", "Menu", "Pause",
) + tuple("F%d" % n for n in range(1, 13))
MEDIA_KEYS = (
    "XF86AudioRaiseVolume", "XF86AudioLowerVolume", "XF86AudioMute",
    "XF86AudioPlay", "XF86AudioNext", "XF86AudioPrev", "XF86AudioStop",
    "XF86MonBrightnessUp", "XF86MonBrightnessDown",
)
SPECIAL_KEYS = tuple(x for x in MEDIA_KEYS)


def A(action, label, modifiers, key, command, group, skill="system",
      branch=BRANCH_COMMANDS, protected=False, rebindable=True):
    """Registry row. `modifiers` is a list of canonical modifier names."""
    return {
        "action": action,
        "label": label,
        "modifiers": list(modifiers),
        "key": key,
        "command": command,
        "group": group,
        "skill": skill,
        "branch": branch,
        "protected": bool(protected),
        "rebindable": bool(rebindable and not protected),
    }


# ---------------------------------------------------------------------------
# The registry.  Keep in sync with config/xfce4-keyboard-shortcuts.xml —
# `mv-hotkeys verify --xml <path>` fails the build if they drift.
# ---------------------------------------------------------------------------
ACTIONS = [
    # --- Core Mavericks surfaces -------------------------------------------
    A("spotlight", "Spotlight Search", ["Super"], "space",
      "/usr/bin/mv-spotlight-gui",
      "core", skill="spotlight"),
    A("launchpad", "Launchpad", ["Super"], "l",
      "/usr/bin/mv-launchpad-gui",
      "core", skill="launchpad"),
    A("launchpad-edit", "Launchpad Edit Mode", ["Super", "Shift"], "l",
      "/usr/bin/mv-launchpad-edit", "core", skill="launchpad"),
    A("mission-control", "Mission Control", ["Super"], "Tab",
      "mv-mission-control --native", "core", skill="mission-control"),
    A("mission-control-gui", "Mission Control (Window Overview)", ["Super"], "F3",
      "mv-mc-gui", "core", skill="mission-control"),
    A("quicklook", "Quick Look", ["Super", "Shift"], "space",
      "mv-quicklook-thunar", "core", skill="finder"),
    A("screenshot-full", "Screenshot: Full Screen", ["Super", "Shift"], "3",
      "mv-shot -m", "core", skill="screenshot"),
    A("screenshot-area", "Screenshot: Selection", ["Super", "Shift"], "4",
      "mv-shot -i -c", "core", skill="screenshot"),
    A("screenshot-interactive", "Screenshot: Interactive Tools", ["Super", "Shift"], "5",
      "mv-shot -i", "core", skill="screenshot"),

    # --- Finder ------------------------------------------------------------
    A("finder", "Finder", ["Super"], "e",
      "mv-finder-columns", "finder", skill="finder"),
    A("finder-columns", "Finder (Browse as Columns)", ["Super", "Shift"], "f",
      "mv-finder-columns", "finder", skill="finder"),
    A("new-folder-desktop", "New Folder on Desktop", ["Primary", "Alt"], "n",
      "mv-newfolder $HOME/Desktop", "finder", skill="finder"),
    A("new-folder-home", "New Folder in Home", ["Super", "Shift"], "n",
      "mv-newfolder $HOME", "finder", skill="finder"),
    A("rename", "Rename", ["Super", "Shift"], "r",
      "mv-rename", "finder", skill="finder"),
    A("get-info", "Get Info", ["Super"], "i",
      "mv-getinfo $HOME", "finder", skill="finder"),
    A("open-with", "Open With", ["Super"], "o",
      "mv-openwith $HOME", "finder", skill="finder"),
    A("move-to-trash", "Move to Trash", ["Super"], "Delete",
      "mv-trash", "finder", skill="finder"),
    A("empty-trash", "Empty Trash", ["Super", "Shift"], "Delete", "mv-empty-trash",
      "finder", skill="finder"),
    A("empty-trash-alt", "Empty Trash (alternate)", ["Super", "Shift"], "e",
      "mv-empty-trash", "finder", skill="finder"),
    A("airdrop", "AirDrop", ["Super", "Shift"], "a", "mv-airdrop",
      "finder", skill="finder"),
    A("eject", "Eject", ["Super"], "F4", "mv-eject", "finder", skill="finder"),

    # --- System ------------------------------------------------------------
    A("settings", "System Settings", ["Super"], "comma", "mv-settings",
      "system", skill="system"),
    A("control-center", "Control Center", ["Super", "Shift"], "c",
      "mv-control", "system", skill="system"),
    A("notification-center", "Notification Center", ["Super", "Shift"], "v",
      "mv-notification-center", "system", skill="system"),
    A("calendar", "Calendar", ["Primary", "Alt"], "c", "mv-calendar",
      "system", skill="system"),
    A("terminal", "Terminal", ["Primary", "Alt"], "t", "xfce4-terminal",
      "system", skill="system", protected=True),
    A("lock-screen", "Lock Screen", ["Primary", "Alt"], "l",
      "xfce4-screensaver-command --lock", "system", skill="system",
      protected=True),
    A("power-dialog", "Power / Restart / Shut Down…", ["Primary", "Alt"], "Escape",
      "mv-power-ui", "system", skill="system"),
    A("log-out", "Log Out…", ["Primary", "Alt"], "Delete",
      "mv-power-ui logout", "system", skill="system"),

    # --- Application -------------------------------------------------------
    A("quit-app", "Quit Application", ["Super"], "q", "mv-quit-app",
      "application", skill="application"),
    A("force-quit", "Force Quit Applications…", ["Super", "Shift"], "q",
      "mv-force-quit", "application", skill="application"),
    A("force-quit-dialog", "Force Quit (Command-Option-Escape)",
      ["Super", "Alt"], "Escape", "mv-force-quit",
      "application", skill="application"),
    A("hide-app", "Hide Application", ["Super"], "h", "mv-hide-app",
      "application", skill="application"),

    # --- Window management -------------------------------------------------
    A("minimize-window", "Minimise Window", ["Super"], "m",
      "mv-minimize-window", "window", skill="window"),
    A("close-window", "Close Window", ["Super"], "w",
      "mv-close-window", "window", skill="window"),
    A("cycle-windows", "Cycle Windows", ["Alt"], "Tab",
      "cycle_windows_key", "window", skill="window",
      branch=BRANCH_XFWM4, protected=True),
    A("cycle-windows-reverse", "Cycle Windows Backwards", ["Alt", "Shift"], "Tab",
      "cycle_reverse_windows_key", "window", skill="window",
      branch=BRANCH_XFWM4, protected=True),
    A("tile-up", "Maximise Window", ["Super"], "Up",
      "tile_up_key", "window", skill="window", branch=BRANCH_XFWM4),
    A("tile-down", "Minimise Window (wm)", ["Super"], "Down",
      "tile_down_key", "window", skill="window", branch=BRANCH_XFWM4),
    A("tile-left", "Tile Window Left Half", ["Super"], "Left",
      "tile_left_key", "window", skill="window", branch=BRANCH_XFWM4),
    A("tile-right", "Tile Window Right Half", ["Super"], "Right",
      "tile_right_key", "window", skill="window", branch=BRANCH_XFWM4),
    # macOS Command-` cycles the windows of the frontmost application.  xfwm4
    # already implements it as switch_window_key; before this it was unbound, so
    # the closest thing to a Command-Tab-style window switch only reached across
    # applications (Alt-Tab).  xfwm4's own key handler runs it, so it
    # costs no resident process.
    A("cycle-app-windows", "Cycle Windows of This Application", ["Super"], "grave",
      "switch_window_key", "window", skill="window", branch=BRANCH_XFWM4),
    A("fullscreen", "Full Screen", ["Super", "Primary"], "f",
      "fullscreen_key", "window", skill="window", branch=BRANCH_XFWM4),

    # --- Spaces ------------------------------------------------------------
    A("workspace-prev", "Move to Previous Space", ["Super", "Alt"], "Left",
      "left_workspace_key", "spaces", skill="spaces", branch=BRANCH_XFWM4),
    A("workspace-next", "Move to Next Space", ["Super", "Alt"], "Right",
      "right_workspace_key", "spaces", skill="spaces", branch=BRANCH_XFWM4),
    A("workspace-1", "Switch to Space 1", ["Super"], "1",
      "workspace_1_key", "spaces", skill="spaces", branch=BRANCH_XFWM4),
    A("workspace-2", "Switch to Space 2", ["Super"], "2",
      "workspace_2_key", "spaces", skill="spaces", branch=BRANCH_XFWM4),
    A("workspace-3", "Switch to Space 3", ["Super"], "3",
      "workspace_3_key", "spaces", skill="spaces", branch=BRANCH_XFWM4),
    A("workspace-4", "Switch to Space 4", ["Super"], "4",
      "workspace_4_key", "spaces", skill="spaces", branch=BRANCH_XFWM4),

    # --- Hardware function row (protected) ---------------------------------
    A("volume-raise", "Volume Up", [], "XF86AudioRaiseVolume",
      "pactl set-sink-volume @DEFAULT_SINK@ +5%",
      "hardware", skill="hardware", protected=True),
    A("volume-lower", "Volume Down", [], "XF86AudioLowerVolume",
      "pactl set-sink-volume @DEFAULT_SINK@ -5%",
      "hardware", skill="hardware", protected=True),
    A("volume-mute", "Mute", [], "XF86AudioMute",
      "pactl set-sink-mute @DEFAULT_SINK@ toggle",
      "hardware", skill="hardware", protected=True),
    A("media-play", "Play / Pause", [], "XF86AudioPlay",
      "mv-music --media-key playpause",
      "hardware", skill="hardware", protected=True),
    A("media-next", "Next Track", [], "XF86AudioNext",
      "mv-music --media-key next",
      "hardware", skill="hardware", protected=True),
    A("media-prev", "Previous Track", [], "XF86AudioPrev",
      "mv-music --media-key prev",
      "hardware", skill="hardware", protected=True),
    A("media-stop", "Stop", [], "XF86AudioStop",
      "mv-music --media-key stop",
      "hardware", skill="hardware", protected=True),
    A("brightness-up", "Brightness Up", [], "XF86MonBrightnessUp",
      "mv-brightness up", "hardware", skill="hardware", protected=True),
    A("brightness-down", "Brightness Down", [], "XF86MonBrightnessDown",
      "mv-brightness down", "hardware", skill="hardware", protected=True),
]
