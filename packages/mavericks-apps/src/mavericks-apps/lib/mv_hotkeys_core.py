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
      "rofi -show -modi 'spotlight:/usr/bin/mv-spotlight' -theme /usr/share/mavericks-apps/rofi-mavericks.rasi",
      "core", skill="spotlight"),
    A("launchpad", "Launchpad", ["Super"], "l",
      "rofi -show -modi 'launchpad:/usr/bin/mv-launchpad' -theme /usr/share/mavericks-apps/rofi-launchpad.rasi",
      "core", skill="launchpad"),
    A("launchpad-edit", "Launchpad Edit Mode", ["Super", "Shift"], "l",
      "/usr/bin/mv-launchpad-edit", "core", skill="launchpad"),
    A("mission-control", "Mission Control", ["Super"], "Tab",
      "mv-mission-control --native", "core", skill="mission-control"),
    A("mission-control-gui", "Mission Control (Window Overview)", ["Super"], "F3",
      "mv-mc-gui", "core", skill="mission-control"),
    A("quicklook", "Quick Look (Finder Selection)", ["Super", "Shift"], "space",
      "mv-quicklook-thunar", "core", skill="quick-look"),
    A("screenshot-full", "Screenshot: Full Screen", ["Super", "Shift"], "3",
      "mv-shot -m", "core", skill="screenshot"),
    A("screenshot-area", "Screenshot: Selection", ["Super", "Shift"], "4",
      "mv-shot -i -c", "core", skill="screenshot"),
    A("screenshot-interactive", "Screenshot: Interactive Tools", ["Super", "Shift"], "5",
      "mv-shot -i", "core", skill="screenshot"),

    # --- Finder ------------------------------------------------------------
    A("finder", "Finder", ["Super"], "e", "mv-finder-columns",
      "finder", skill="finder"),
    A("finder-columns", "Finder (Browse as Columns)", ["Super", "Shift"], "f",
      "mv-finder-columns", "finder", skill="finder"),
    A("new-folder-desktop", "New Folder on Desktop", ["Primary", "Alt"], "n",
      "mv-newfolder $HOME/Desktop", "finder", skill="finder"),
    A("new-folder-home", "New Folder in Home Folder", ["Super", "Shift"], "n",
      "mv-newfolder $HOME", "finder", skill="finder"),
    A("rename", "Rename", ["Super", "Shift"], "r", "mv-rename",
      "finder", skill="finder"),
    A("get-info", "Get Info", ["Super"], "i", "mv-getinfo $HOME",
      "finder", skill="finder"),
    A("open-with", "Open With", ["Super"], "o", "mv-openwith $HOME",
      "finder", skill="finder"),
    A("move-to-trash", "Move to Trash", ["Super"], "Delete", "mv-trash",
      "finder", skill="finder"),
    A("empty-trash", "Empty Trash", ["Super", "Shift"], "Delete", "trash-empty",
      "finder", skill="finder"),
    A("empty-trash-alt", "Empty Trash (alternate)", ["Super", "Shift"], "e",
      "trash-empty", "finder", skill="finder"),
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
      "system", skill="system", rebindable=False),
    A("lock-screen", "Lock Screen", ["Primary", "Alt"], "l",
      "xfce4-screensaver-command --lock", "system", skill="system",
      rebindable=False),
    A("power-dialog", "Power / Restart / Shut Down…", ["Primary", "Alt"],
      "Escape", "mv-power-ui", "system", skill="system"),
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

    # --- Windows (xfwm4 branch) -------------------------------------------
    A("minimize-window", "Minimise Window (Command-M)", ["Super"], "m",
      "mv-minimize-window", "window", skill="window"),
    A("close-window", "Close Window (Command-W)", ["Super"], "w",
      "mv-close-window", "window", skill="window"),
    A("cycle-windows", "Cycle Windows (Alt-Tab)", ["Alt"], "Tab",
      "cycle_windows_key", "window", skill="application",
      branch=BRANCH_XFWM4, rebindable=False),
    A("cycle-windows-reverse", "Cycle Windows Backwards (Alt-Shift-Tab)",
      ["Alt", "Shift"], "Tab", "cycle_reverse_windows_key", "window",
      skill="application", branch=BRANCH_XFWM4, rebindable=False),
    A("tile-up", "Maximise Window", ["Super"], "Up", "tile_up_key",
      "window", skill="window", branch=BRANCH_XFWM4),
    A("tile-down", "Minimise Window (window manager)", ["Super"], "Down",
      "tile_down_key", "window", skill="window", branch=BRANCH_XFWM4),
    A("tile-left", "Tile Window Left Half", ["Super"], "Left", "tile_left_key",
      "window", skill="window", branch=BRANCH_XFWM4),
    A("tile-right", "Tile Window Right Half", ["Super"], "Right",
      "tile_right_key", "window", skill="window", branch=BRANCH_XFWM4),

    # --- Spaces (xfwm4 branch) --------------------------------------------
    A("workspace-prev", "Move to Previous Space", ["Super", "Alt"], "Left",
      "left_workspace_key", "workspace", skill="workspace",
      branch=BRANCH_XFWM4),
    A("workspace-next", "Move to Next Space", ["Super", "Alt"], "Right",
      "right_workspace_key", "workspace", skill="workspace",
      branch=BRANCH_XFWM4),
    A("workspace-1", "Switch to Space 1", ["Super"], "1", "workspace_1_key",
      "workspace", skill="workspace", branch=BRANCH_XFWM4),
    A("workspace-2", "Switch to Space 2", ["Super"], "2", "workspace_2_key",
      "workspace", skill="workspace", branch=BRANCH_XFWM4),
    A("workspace-3", "Switch to Space 3", ["Super"], "3", "workspace_3_key",
      "workspace", skill="workspace", branch=BRANCH_XFWM4),
    A("workspace-4", "Switch to Space 4", ["Super"], "4", "workspace_4_key",
      "workspace", skill="workspace", branch=BRANCH_XFWM4),

    # --- Hardware function row (protected: not rebindable) -----------------
    A("volume-raise", "Volume Up", [], "XF86AudioRaiseVolume",
      "pactl set-sink-volume @DEFAULT_SINK@ +5%", "keyboard",
      skill="keyboard", protected=True),
    A("volume-lower", "Volume Down", [], "XF86AudioLowerVolume",
      "pactl set-sink-volume @DEFAULT_SINK@ -5%", "keyboard",
      skill="keyboard", protected=True),
    A("volume-mute", "Mute", [], "XF86AudioMute",
      "pactl set-sink-mute @DEFAULT_SINK@ toggle", "keyboard",
      skill="keyboard", protected=True),
    A("media-play", "Play / Pause", [], "XF86AudioPlay",
      "mv-music --media-key playpause", "keyboard", skill="keyboard",
      protected=True),
    A("media-next", "Next Track", [], "XF86AudioNext",
      "mv-music --media-key next", "keyboard", skill="keyboard",
      protected=True),
    A("media-prev", "Previous Track", [], "XF86AudioPrev",
      "mv-music --media-key prev", "keyboard", skill="keyboard",
      protected=True),
    A("media-stop", "Stop", [], "XF86AudioStop",
      "mv-music --media-key stop", "keyboard", skill="keyboard",
      protected=True),
    A("brightness-up", "Brightness Up", [], "XF86MonBrightnessUp",
      "mv-brightness up", "keyboard", skill="keyboard", protected=True),
    A("brightness-down", "Brightness Down", [], "XF86MonBrightnessDown",
      "mv-brightness down", "keyboard", skill="keyboard", protected=True),
]

ACTION_INDEX = {row["action"]: row for row in ACTIONS}
PROTECTED_ACTIONS = frozenset(
    row["action"] for row in ACTIONS if row["protected"] or not row["rebindable"])


def action_ids():
    return [row["action"] for row in ACTIONS]


# ---------------------------------------------------------------------------
# Pure accelerator logic
# ---------------------------------------------------------------------------

_KEY_CHAR_RE = re.compile(r"^[a-z0-9]$")
_KEY_FN_RE = re.compile(r"^[fF]([1-9]|1[0-3])$")
_XF86_RE = re.compile(r"^XF86[A-Za-z0-9_]+$")


def normalize_modifiers(mods):
    """Map aliases to canonical xfconf modifier names and order them."""
    out = set()
    for m in mods:
        key = str(m).strip().lower()
        if key not in MODIFIER_ALIASES:
            raise ValueError("unknown modifier: %s" % m)
        out.add(MODIFIER_ALIASES[key])
    return [m for m in MODIFIER_ORDER if m in out]


def is_valid_key(key):
    if not isinstance(key, str) or not key:
        return False
    if _KEY_CHAR_RE.match(key) or _KEY_FN_RE.match(key):
        return True
    if key in NAMED_KEYS or key in MEDIA_KEYS:
        return True
    return False


def normalize_accelerator(accel):
    """Accept a string or dict and return a canonical {'modifiers','key'}.

    Accepted string forms:
      'Super+Shift+3'   'Super + Shift + 3'   '<Super><Shift>3'
      '&lt;Super&gt;&lt;Shift&gt;3' (as stored in the factory XML)
    Case is normalised: letters lowercase, named keys/keysyms exact.
    Raises ValueError with a human message on anything else.

    A dict keeps its modifier ORDER (X11 property names are order-sensitive
    as strings even though the key combination is not); only string input is
    reordered into MODIFIER_ORDER.  Use `modifier_identity()` when two
    combinations must be compared for equality.
    """
    if isinstance(accel, dict):
        mods = []
        for m in accel.get("modifiers") or []:
            if str(m) not in MODIFIER_ORDER:
                raise ValueError("unknown modifier: %r" % m)
            mods.append(str(m))
        key = accel.get("key")
        if not is_valid_key(key):
            raise ValueError("invalid key: %r" % key)
        return {"modifiers": mods, "key": key}

    s = str(accel).strip()
    if not s:
        raise ValueError("empty accelerator")

    unescaped = s.replace("&lt;", "<").replace("&gt;", ">")
    if "<" in unescaped:
        pattern = re.compile(
            r"^<(Primary|Control|Ctrl|Alt|Option|Super|Meta|Shift)>")
        mods = []
        while True:
            m = pattern.match(unescaped)
            if not m:
                break
            mods.append(m.group(1))
            unescaped = unescaped[len(m.group(0)):]
        key = unescaped
        if not key:
            raise ValueError("accelerator has modifiers but no key: %r" % accel)
        if not is_valid_key(key):
            raise ValueError("invalid key: %r" % key)
        return {"modifiers": normalize_modifiers(mods), "key": key}

    parts = [p.strip() for p in s.split("+") if p.strip()]
    if len(parts) == 1:
        # A lone hardware keysym (XF86AudioMute, XF86MonBrightnessUp, …) is
        # a valid accelerator: the function row has no modifiers.
        if _XF86_RE.match(parts[0]) and parts[0] in MEDIA_KEYS:
            return {"modifiers": [], "key": parts[0]}
        raise ValueError(
            "accelerator needs at least one modifier, e.g. Super+Space")
    mods, raw_key = parts[:-1], parts[-1]
    canonical = normalize_modifiers(mods)
    if _XF86_RE.match(raw_key):
        key = raw_key
    elif len(raw_key) == 1 and raw_key.isalnum():
        key = raw_key.lower()
    elif _KEY_FN_RE.match(raw_key):
        key = "F" + _KEY_FN_RE.match(raw_key).group(1)
    elif raw_key in NAMED_KEYS or raw_key in MEDIA_KEYS:
        key = raw_key
    else:
        # Named keys are case-sensitive in X11 but users type them in any
        # case; accept the exact-name lookup case-insensitively.
        lowered = {k.lower(): k for k in NAMED_KEYS}
        if raw_key.lower() in lowered:
            key = lowered[raw_key.lower()]
        else:
            raise ValueError("unrecognised key: %r" % raw_key)
    if not canonical and key not in MEDIA_KEYS:
        raise ValueError(
            "a bare key (%s) would swallow ordinary typing; add a modifier"
            % key)
    return {"modifiers": canonical, "key": key}


def modifier_identity(modifiers):
    """Order-independent identity of a modifier set (conflict detection)."""
    return tuple(sorted(set(str(m) for m in modifiers)))


def property_accelerator(accel):
    """Accelerator as an Xfce property suffix ('<Super>space')."""
    accel = normalize_accelerator(accel)
    return "".join("<%s>" % m for m in accel["modifiers"]) + accel["key"]


def property_path(branch, accel):
    return "/%s/default/%s" % (branch, property_accelerator(accel))


def property_path_identity(branch, accel):
    """Conflict-detecting twin of property_path: order-insensitive."""
    accel = normalize_accelerator(accel)
    return "/%s/default/%s" % (
        branch,
        "".join("<%s>" % m for m in modifier_identity(accel["modifiers"]))
        + accel["key"])


def display_accelerator(accel):
    """Human/Mavericks rendering: 'Super+Shift+3' (XML-escaped for widgets)."""
    accel = normalize_accelerator(accel)
    labels = [ACCEL_MODIFIER_LABELS[m] for m in accel["modifiers"]]
    if accel["key"] in ("space",):
        labels.append("Space")
    elif _KEY_FN_RE.match(accel["key"]):
        labels.append(accel["key"])
    elif _KEY_CHAR_RE.match(accel["key"]):
        labels.append(accel["key"].upper())
    else:
        labels.append(accel["key"])
    return "+".join(labels)


def action_accelerator(action_id, overrides=None):
    """Effective accelerator of an action: factory, or the user override."""
    row = ACTION_INDEX[action_id]
    override = (overrides or {}).get(action_id)
    if override:
        return normalize_accelerator(override.get("accelerator", {}))
    return {"modifiers": list(row["modifiers"]), "key": row["key"]}


def action_command(action_id, overrides=None):
    row = ACTION_INDEX[action_id]
    override = (overrides or {}).get(action_id)
    if override and override.get("command"):
        return override["command"]
    return row["command"]


def effective_bindings(overrides=None):
    """action id -> {'modifiers','key','command','branch','label',...}."""
    out = {}
    for row in ACTIONS:
        aid = row["action"]
        out[aid] = {
            "action": aid,
            "label": row["label"],
            "group": row["group"],
            "skill": row["skill"],
            "branch": row["branch"],
            "protected": row["protected"] or not row["rebindable"],
            "overridden": bool((overrides or {}).get(aid)),
            "modifiers": action_accelerator(aid, overrides)["modifiers"],
            "key": action_accelerator(aid, overrides)["key"],
            "command": action_command(aid, overrides),
        }
    return out


def detect_conflicts(bindings=None, overrides=None):
    """Pure conflict scan. Returns a sorted list of conflict dicts.

    A conflict is two actions resolving to the same property path (same
    modifiers + key in the same channel branch).  `branch` is part of the
    identity because /commands/default and /xfwm4/default are independent
    namespaces.
    """
    binds = bindings if bindings is not None else effective_bindings(overrides)
    seen = {}
    conflicts = []
    for aid in sorted(binds):
        b = binds[aid]
        path = property_path_identity(
            b["branch"], {"modifiers": b["modifiers"], "key": b["key"]})
        if path in seen:
            conflicts.append({
                "property": path,
                "actions": [seen[path], aid],
                "commands": [binds[seen[path]]["command"], b["command"]],
            })
        else:
            seen[path] = aid
    conflicts.sort(key=lambda c: (c["property"], c["actions"][0], c["actions"][1]))
    return conflicts


def check_overrides(overrides=None):
    """Validate a whole override table. Returns list of error strings."""
    errors = []
    for aid in sorted(overrides or {}):
        if aid not in ACTION_INDEX:
            errors.append("unknown action: %s" % aid)
            continue
        if ACTION_INDEX[aid]["protected"] or not ACTION_INDEX[aid]["rebindable"]:
            errors.append("action %s is protected and cannot be overridden" % aid)
            continue
        try:
            accel = normalize_accelerator((overrides[aid] or {}).get(
                "accelerator", {}))
        except ValueError as exc:
            errors.append("action %s: %s" % (aid, exc))
            continue
        if accel["key"] in SPECIAL_KEYS:
            errors.append(
                "action %s: hardware key %s is reserved" % (aid, accel["key"]))
    for conflict in detect_conflicts(overrides=overrides):
        errors.append(
            "conflicting bindings for %s: %s"
            % (" / ".join(conflict["actions"]), conflict["property"]))
    return errors


# ---------------------------------------------------------------------------
# Factory XML: render + parse + drift detection
# ---------------------------------------------------------------------------

_XML_HEADER = ('<?xml version="1.0" ?>\n'
               '<channel name="xfce4-keyboard-shortcuts" version="1.0">\n')


def render_xml(actions=None):
    """Generate the factory xfconf XML from the registry.

    Used by `mv-hotkeys render-xml` and by the test suite to prove the
    packaged XML is exactly what the registry describes.
    """
    rows = actions if actions is not None else ACTIONS
    out = [_XML_HEADER]
    for branch in BRANCHES:
        out.append('  <property name="%s" type="empty">\n' % branch)
        out.append('    <property name="default" type="empty">\n')
        for row in rows:
            if row["branch"] != branch:
                continue
            out.append(
                '      <property name="%s" type="string" value="%s"/>\n'
                % (xml_escape(property_accelerator(row)),
                   xml_escape(row["command"])))
        out.append('    </property>\n')
        out.append('  </property>\n')
    out.append('</channel>\n')
    return "".join(out)


def _xml_attr(value):
    return (value.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


def parse_xml_bindings(xml_text):
    """XML text -> {'/commands/default/<accel>': command, ...}."""
    root = ET.fromstring(xml_text)
    bindings = {}
    for branch in BRANCHES:
        container = root.find("property[@name='%s']" % branch)
        if container is None:
            continue
        default = container.find("property[@name='default']")
        if default is None:
            continue
        for prop in default.findall("property"):
            name = prop.get("name")
            value = prop.get("value")
            if name is None:
                continue
            bindings[canonical_property(
                "/%s/default/%s" % (branch, name))] = value
    return bindings


def registry_bindings():
    """Registry -> {canonical property path: command, ...}."""
    return {
        property_path_identity(row["branch"], row): row["command"]
        for row in ACTIONS
    }


def xml_escape(name):
    return (name.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


def canonical_property(path):
    """Order-insensitive canonical form of an Xfce property path.

    Xfce writes modifiers in the order <Primary><Alt><Super><Shift>, but any
    order parses to the same key combination.  Comparing canonically keeps
    verify/drift detection from flagging a pure ordering difference as a
    missing binding.
    """
    parts = path.split("/")
    if len(parts) < 4:
        return path
    try:
        accel = normalize_accelerator(parts[-1])
    except ValueError:
        return path
    return "/".join(parts[:-1] + [property_path_identity(parts[-2], accel)
                                  .split("/")[-1]])


def compare_bindings(expected, actual):
    """Diff two property->command maps. Returns a list of problem strings.

    Both sides are canonicalised first, so a modifier-order difference is not
    reported as drift.
    """
    expected = {canonical_property(k): v for k, v in expected.items()}
    actual = {canonical_property(k): v for k, v in actual.items()}
    problems = []
    for path in sorted(set(expected) | set(actual)):
        want, have = expected.get(path), actual.get(path)
        if want == have:
            continue
        if want is None:
            problems.append("unexpected binding: %s = %s" % (path, have))
        elif have is None:
            problems.append("missing binding: %s = %s" % (path, want))
        else:
            problems.append(
                "binding differs: %s = %r (registry says %r)" % (path, have, want))
    return problems


def resolve_factory_xml():
    env = os.environ.get("MV_HOTKEYS_FACTORY_XML")
    candidates = ([env] if env else []) + FACTORY_XML_CANDIDATES
    for candidate in candidates:
        path = os.path.realpath(candidate)
        if os.path.isfile(path):
            return path
    return None


# ---------------------------------------------------------------------------
# Overrides file (small, additive, user-owned)
# ---------------------------------------------------------------------------

def load_overrides(path=None):
    path = path or OVERRIDES_PATH
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    bindings = data.get("bindings") if isinstance(data, dict) else None
    return bindings if isinstance(bindings, dict) else {}


def save_overrides(overrides, path=None):
    path = path or OVERRIDES_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"version": 1, "bindings": overrides}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def set_override(action_id, accelerator, command=None, overrides=None,
                 path=None):
    overrides = dict(overrides if overrides is not None
                     else load_overrides(path))
    row = ACTION_INDEX[action_id]
    if row["protected"] or not row["rebindable"]:
        raise PermissionError(
            "action %s is protected (%s) and cannot be rebound"
            % (action_id, row["label"]))
    accel = normalize_accelerator(accelerator)
    if accel["key"] in SPECIAL_KEYS:
        raise PermissionError(
            "hardware key %s is reserved for the function row" % accel["key"])
    entry = {"accelerator": accel}
    if command:
        entry["command"] = command
    overrides[action_id] = entry
    errors = check_overrides(overrides)
    if errors:
        raise ValueError("; ".join(errors))
    save_overrides(overrides, path)
    return overrides


def clear_override(action_id, overrides=None, path=None):
    overrides = dict(overrides if overrides is not None
                     else load_overrides(path))
    overrides.pop(action_id, None)
    save_overrides(overrides, path)
    return overrides


def clear_override_all(path=None):
    """Drop every user override and restore factory state live."""
    overrides = load_overrides(path)
    changed = list(overrides)
    for action_id in changed:
        _steps, overrides = reset_action(action_id, overrides, path)
    if not changed:
        save_overrides({}, path)
    return overrides


# ---------------------------------------------------------------------------
# Live channel access (xfconf-query).  One-shot, no daemon.
# ---------------------------------------------------------------------------

class XfconfUnavailable(RuntimeError):
    """xfconf-query missing or the channel is not running."""


def _run(args, timeout=5):
    cmd = ["xfconf-query", "-c", CHANNEL] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise XfconfUnavailable("xfconf-query not found")
    except subprocess.TimeoutExpired:
        raise XfconfUnavailable("xfconf-query timed out")
    if proc.returncode != 0:
        raise XfconfUnavailable(proc.stderr.strip() or "xfconf-query failed")
    return proc.stdout


def live_available():
    try:
        _run(["-l"], timeout=5)
    except XfconfUnavailable:
        return False
    return True


def live_raw():
    """Live properties keyed by their RAW X property path.

    Writes must use these exact strings; X treats the property name as an
    opaque string, so the order-insensitive canonical form is only for
    comparisons.
    """
    text = _run(["-l", "-v"])  # -v: without it xfconf-query prints names only
    out = {}
    for line in text.splitlines():
        # `-v` output is column-padded, not "key = value": split on the first
        # run of whitespace.  Values may themselves contain spaces.
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        path, value = parts
        if "/default/" in path:
            out[path.strip()] = value.strip()
    return out


def live_list():
    """Live properties keyed by canonical (order-insensitive) path."""
    return {canonical_property(p): v for p, v in live_raw().items()}


def live_get(path):
    try:
        return _run(["-p", path, "-g"]).strip()
    except XfconfUnavailable:
        return None


def live_set(path, value):
    # -n creates the property when the accelerator is brand new and -t pins
    # the type; without both, xfconf-query refuses to add a key that does not
    # exist yet.
    _run(["-p", path, "-s", value, "-n", "-t", "string"])


def live_remove(path):
    _run(["-p", path, "-r"])


def _stale_paths(row, overrides, live):
    """Candidate old property paths for an action, filtered to bindings
    that actually belong to that action (never collateral damage).

    Returns RAW (writable) X property paths; `live` is keyed by raw path.
    """
    factory = {"modifiers": list(row["modifiers"]), "key": row["key"]}
    target_raw = property_path(row["branch"],
                               action_accelerator(row["action"], overrides))
    target_id = canonical_property(target_raw)
    wanted_commands = {row["command"],
                       action_command(row["action"], overrides)}
    found = []
    seen_ids = {target_id}
    for raw, value in sorted(live.items()):
        ident = canonical_property(raw)
        if ident in seen_ids or raw == target_raw:
            continue
        if value in wanted_commands and ident == canonical_property(
                property_path(row["branch"], factory)):
            seen_ids.add(ident)
            found.append(raw)
    override = (overrides or {}).get(row["action"])
    if override:
        try:
            raw = property_path(
                row["branch"],
                normalize_accelerator(override.get("accelerator", {})))
        except ValueError:
            raw = None
        if raw and raw != target_raw and \
                canonical_property(raw) not in seen_ids and \
                live.get(raw) in wanted_commands:
            seen_ids.add(canonical_property(raw))
            found.append(raw)
    return found


def apply_action(action_id, overrides=None, path=None, force=False):
    """Make the live channel match the effective binding for one action.

    Returns a list of human-readable steps (what was removed/set).
    """
    overrides = overrides if overrides is not None else load_overrides(path)
    row = ACTION_INDEX[action_id]
    accel = action_accelerator(action_id, overrides)
    command = action_command(action_id, overrides)
    target = property_path(row["branch"], accel)
    steps = []

    errors = check_overrides(overrides)
    if errors:
        raise ValueError("; ".join(errors))

    live_raw_map = live_raw()
    live_by_id = {canonical_property(p): v for p, v in live_raw_map.items()}
    target_id = canonical_property(target)
    occupant = live_by_id.get(target_id)
    if occupant is not None and occupant != command and not force:
        owner = None
        for other in ACTIONS:
            other_target = property_path(
                other["branch"],
                action_accelerator(other["action"], overrides))
            if canonical_property(other_target) == target_id:
                owner = other["action"]
                break
        raise ValueError(
            "%s is already bound to %s%s — use --force to replace"
            % (display_accelerator(accel), occupant,
               "" if owner is None else " (%s)" % owner))

    for stale in _stale_paths(row, overrides, live_raw_map):
        live_remove(stale)
        steps.append("removed %s" % stale)
    if live_by_id.get(target_id) != command:
        live_set(target, command)
        steps.append("set %s = %s" % (target, command))
    else:
        steps.append("%s already current" % target)
    return steps


def reset_action(action_id, overrides=None, path=None):
    """Restore factory state: drop the override AND clean the live channel.

    Stale paths are computed while the override is still known, otherwise the
    rebind the user made would be invisible here and left behind in xfconf as
    an orphan property.
    """
    previous = overrides if overrides is not None else load_overrides(path)
    overrides = clear_override(action_id, previous, path)
    steps = []
    try:
        row = ACTION_INDEX[action_id]
        live = live_raw()
        factory = {"modifiers": list(row["modifiers"]), "key": row["key"]}
        factory_raw = property_path(row["branch"], factory)
        override = (previous or {}).get(action_id)
        stale = []
        if override:
            try:
                override_raw = property_path(
                    row["branch"],
                    normalize_accelerator(override.get("accelerator", {})))
            except ValueError:
                override_raw = None
            if override_raw and override_raw != factory_raw and \
                    live.get(override_raw) in (row["command"],
                                               action_command(action_id,
                                                             previous)):
                stale.append(override_raw)
        stale += [p for p in _stale_paths(row, {}, live)
                  if p not in stale]
        for stale_path in stale:
            live_remove(stale_path)
            steps.append("removed %s" % stale_path)
        target = property_path(row["branch"], row)
        live_after = {canonical_property(p): v for p, v in live_list().items()}
        if live_after.get(canonical_property(target)) != row["command"]:
            live_set(target, row["command"])
            steps.append("set %s = %s" % (target, row["command"]))
    except XfconfUnavailable as exc:
        steps.append("xfconf unavailable (%s); factory XML left unchanged"
                     % exc)
    return steps, overrides


def apply_all(overrides=None, path=None, force=False):
    overrides = overrides if overrides is not None else load_overrides(path)
    steps = []
    for row in ACTIONS:
        steps.append("%s: %s" % (row["action"],
                                 "; ".join(apply_action(
                                     row["action"], overrides, path, force))))
    return steps


def verify(overrides=None, live=None):
    """Compare the live channel (or a supplied map) with the registry.

    Returns a list of problems; empty means the layer is consistent.
    """
    if live is None:
        live = live_list()
    binds = effective_bindings(overrides)
    expected = {
        property_path_identity(
            b["branch"], {"modifiers": b["modifiers"], "key": b["key"]}):
        b["command"]
        for b in binds.values()
    }
    return compare_bindings(expected, live)


def export_table(overrides=None):
    overrides = overrides if overrides is not None else load_overrides()
    binds = effective_bindings(overrides)
    rows = []
    for aid in action_ids():
        b = binds[aid]
        rows.append({
            "action": aid,
            "label": b["label"],
            "group": b["group"],
            "skill": b["skill"],
            "accelerator": display_accelerator(
                {"modifiers": b["modifiers"], "key": b["key"]}),
            "property": property_path_identity(
                b["branch"], {"modifiers": b["modifiers"], "key": b["key"]}),
            "command": b["command"],
            "protected": b["protected"],
            "overridden": b["overridden"],
        })
    return rows


def import_table(rows, overrides=None, path=None):
    """Apply an export table. Rebindable rows are written as overrides."""
    overrides = dict(overrides if overrides is not None
                     else load_overrides(path))
    rejected = []
    for row in rows:
        aid = row.get("action")
        if aid not in ACTION_INDEX:
            rejected.append("unknown action: %r" % aid)
            continue
        if ACTION_INDEX[aid]["protected"] or not ACTION_INDEX[aid]["rebindable"]:
            if row.get("accelerator") and normalize_accelerator(
                    row["accelerator"]) != {
                        "modifiers": list(ACTION_INDEX[aid]["modifiers"]),
                        "key": ACTION_INDEX[aid]["key"]}:
                rejected.append(
                    "protected action %s left at factory (%s)"
                    % (aid, display_accelerator(
                        {"modifiers": ACTION_INDEX[aid]["modifiers"],
                         "key": ACTION_INDEX[aid]["key"]})))
            continue
        factory = {"modifiers": list(ACTION_INDEX[aid]["modifiers"]),
                   "key": ACTION_INDEX[aid]["key"]}
        if row.get("accelerator"):
            try:
                accel = normalize_accelerator(row["accelerator"])
            except ValueError as exc:
                rejected.append("action %s: %s" % (aid, exc))
                continue
            if accel != factory:
                overrides[aid] = {"accelerator": accel}
                if row.get("command") and row["command"] != ACTION_INDEX[aid]["command"]:
                    overrides[aid]["command"] = row["command"]
            else:
                overrides.pop(aid, None)
        elif row.get("command") and row["command"] != ACTION_INDEX[aid]["command"]:
            overrides[aid] = {"accelerator": factory,
                              "command": row["command"]}
    errors = check_overrides(overrides)
    if errors:
        raise ValueError("; ".join(errors))
    save_overrides(overrides, path)
    return overrides, rejected


def load_skills():
    """System Settings skill groups. Falls back to a built-in table."""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        "/usr/share/mavericks-apps/hotkeys/skills.json",
        os.path.join(module_dir, os.pardir, "config", "hotkeys", "skills.json"),
    )
    fallback = [{"id": "system", "label": "System", "icon": "preferences-system",
                 "description": ""}]
    path = next((candidate for candidate in candidates
                 if os.path.isfile(candidate)), None)
    if not path:
        return fallback
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return fallback
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        return fallback
    known = {row["skill"] for row in ACTIONS}
    return [s for s in skills if s.get("id") in known] or fallback