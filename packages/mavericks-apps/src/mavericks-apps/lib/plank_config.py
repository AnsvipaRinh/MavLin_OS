#!/usr/bin/env python3
#  plank_config.py — MavLinOS Dock preference authority (Plank backend).
#
#  WHY THIS FILE EXISTS
#  -------------------
#  Plank 0.11.x does NOT read the legacy INI file
#  ``~/.config/plank/dock1/settings`` any more: it keeps its preferences in
#  GSettings.  Verified on plank 0.11.89 (repo test
#  ``scripts/test-dock-plank.py`` / GUI smoke ``test-dock-plank-gui.py``):
#
#    * with only the INI present, plank reports
#      ``theme='Default'`` and ``zoom-enabled=false`` — the Mavericks glass
#      theme and the zoom/reflection behaviour were silently lost;
#    * writing the same values through GSettings does take effect
#      (``icon-size=48`` -> dock 304x66, ``icon-size=96`` -> dock 604x131).
#
#  The Dock is only a "Mavericks Dock" if the theme, the zoom, the
#  intelligent auto-hide and the macOS pinning behaviour actually reach
#  plank, so this module owns that translation and nothing else does.
#
#  RUNTIME COST (AGENTS.md §7)
#  --------------------------
#  One-shot, event-free, no polling, no resident daemon.  ``--apply`` runs
#  a handful of ``gsettings set`` calls at session start (tens of ms) and
#  exits; plank itself is the only always-on process.
#
#  DESIGN
#  ------
#  ``PREFERENCES`` is the single authority.  The legacy INI
#  (``configs/desktop/plank/dock1-settings``) is *kept* as a human-readable
#  declaration — other tooling reads it — but it is never trusted as an
#  input: ``legacy_translation()`` translates it for cross-checking only and
#  ``compare_with_legacy()`` reports drift.  Legacy enum encodings differ
#  from the GSettings nicks, and several legacy keys have no GSettings
#  counterpart at all, which is precisely the trap this module removes.
#
#  Install: /usr/bin/mv-dock-config (wrapper) +
#  /usr/share/mavericks-apps/plank_config.py.

import argparse
import configparser
import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Plank's GSettings identity.
# ---------------------------------------------------------------------------

DOCK_NAME = "dock1"
#: Relocatable schema for a single dock's preferences.
DOCK_SCHEMA = "net.launchpad.plank.dock.settings"
#: Non-relocatable schema holding the enabled-docks list.
BASE_SCHEMA = "net.launchpad.plank"
#: The relocatable path plank actually uses for dock1.  Verified by dumping
#: the user dconf database while plank was running: plank itself writes
#: ``dock-items`` under ``/net/launchpad/plank/docks/dock1``.  The
#: ``/net/launchpad/plank/dock/settings/`` guess that looks plausible is
#: wrong and silently stores preferences plank never reads.
DOCK_PATH = "/net/launchpad/plank/docks/%s/" % DOCK_NAME

LEGACY_SECTION = "PlankDockPreferences"

#: Candidate locations of the legacy INI (documentation + cross-check only).
LEGACY_INI_CANDIDATES = (
    "/etc/skel/.config/plank/dock1/settings",
    os.path.expanduser("~/.config/plank/dock1/settings"),
)


def dock_ref():
    """Full ``schema:path`` reference plank reads preferences from."""
    return "%s:%s" % (DOCK_SCHEMA, DOCK_PATH)


# ---------------------------------------------------------------------------
# The authority: what the MavLinOS Dock must look like on every session.
#
# Values are GVariant *text* form, i.e. exactly what ``gsettings set`` takes:
# strings and enums are quoted, ints and booleans are bare.
# ---------------------------------------------------------------------------

PREFERENCES = (
    # key, value, why (kept inline so the Dock's intent stays auditable)
    ("theme", "'Mavericks'",
     "Mavericks glass dock theme (plank/dock.theme): translucent metallic "
     "fill, reflection, item shadows, Mavericks indicator geometry"),
    ("icon-size", "48",
     "retina 2304x1440 panel: 48px icons match the Mavericks default "
     "proportion without inflating the always-on draw area"),
    ("zoom-enabled", "true",
     "cursor magnification is the core macOS Dock affordance"),
    ("zoom-percent", "150",
     "Mavericks-era magnification depth (1.5x), not the Linux default"),
    ("hide-mode", "'intelligent'",
     "macOS auto-hide: the Dock leaves when nothing overlaps it and returns "
     "on approach"),
    ("hide-delay", "0",
     "macOS shows the Dock immediately, with no reveal lag"),
    ("unhide-delay", "0",
     "same, for the return direction"),
    ("position", "'bottom'",
     "macOS keeps the Dock on the bottom edge"),
    ("alignment", "'center'",
     "centred on the display, as on macOS"),
    ("items-alignment", "'center'",
     "the icon group stays centred; plank has no per-section right-align, "
     "so the Trash cannot hug the right edge as it does on macOS "
     "(documented known gap, not a silent omission)"),
    ("offset", "0",
     "flush with the screen edge, no gap"),
    ("monitor", "''",
     "no monitor constraint: the Dock follows the default display"),
    ("show-dock-item", "false",
     "macOS has no 'Windows' menu in the Dock; windows are reached through "
     "Mission Control instead"),
    ("pressure-reveal", "false",
     "touch pressure reveal is not a macOS behaviour"),
    ("lock-items", "false",
     "the macOS Dock is rearrangeable by drag"),
    ("tooltips-enabled", "true",
     "macOS labels Dock icons on hover"),
    ("auto-pinning", "true",
     "macOS shows every running application in the Dock and removes it again "
     "when it quits — it does not become a permanent pin. plank's "
     "auto-pinning is the same thing: the item appears while the window is "
     "open and is dropped from dock-items when it closes (measured: an "
     "unpinned app grew the dock 424px -> 484px). Setting this false — the "
     "intuitive 'macOS never auto-pins' reading — was tried first and "
     "measurably WRONG: the Dock then only ever showed what was pinned, so "
     "running apps were invisible. Do not flip it without measuring."),
    ("pinned-only", "false",
     "running-but-unpinned applications stay visible, like macOS"),
    ("current-workspace-only", "false",
     "applications from other Spaces remain in the Dock, like macOS"),
)

#: Preferences that live on the non-relocatable schema.
BASE_PREFERENCES = (
    ("enabled-docks", "['%s']" % DOCK_NAME,
     "dock1 is the only dock"),
)

# ---------------------------------------------------------------------------
# Legacy INI -> GSettings translation (cross-check only, never an input).
# ---------------------------------------------------------------------------

def _as_bool(value):
    return str(value).strip().lower()


def _as_gstring(value):
    """GVariant string form (quoted) — Theme, and any other text key."""
    return "'%s'" % str(value).strip()


def _as_raw(value):
    """Pass through unchanged — integer keys stay bare."""
    return str(value).strip()


def _as_monitor(value):
    """plank's legacy -1 meant 'no monitor constraint'; GSettings uses ''."""
    stripped = str(value).strip()
    return "''" if stripped in ("", "-1") else "'%s'" % stripped


#: Legacy key -> (gsettings key, converter)
LEGACY_PLAIN = {
    "Theme": ("theme", _as_gstring),
    "IconSize": ("icon-size", _as_raw),
    "ZoomEnabled": ("zoom-enabled", _as_bool),
    "ZoomPercent": ("zoom-percent", _as_raw),
    "HideDelay": ("hide-delay", _as_raw),
    "UnhideDelay": ("unhide-delay", _as_raw),
    "ShowDockItem": ("show-dock-item", _as_bool),
    "PressureReveal": ("pressure-reveal", _as_bool),
    "Offset": ("offset", _as_raw),
    "Monitor": ("monitor", _as_monitor),
    "LockItems": ("lock-items", _as_bool),
    "TooltipsEnabled": ("tooltips-enabled", _as_bool),
}

#: Legacy integer enums -> GSettings enum nicks.  The numeric encodings
#: differ between plank's INI and its GSettings enums, so they are spelled
#: out instead of computed.
LEGACY_ENUMS = {
    "HideMode": {
        0: "'none'", 1: "'intelligent'", 2: "'auto'",
        3: "'dodge-maximized'", 4: "'window-dodge'", 5: "'dodge-active'",
    },
    "Position": {0: "'top'", 1: "'bottom'", 2: "'left'", 3: "'right'"},
    "Alignment": {0: "'fill'", 1: "'start'", 2: "'end'", 3: "'center'"},
}

#: Legacy keys with no GSettings counterpart.  plank ignores them at runtime
#: because they are theme-side or GUI-only; keep the list explicit so the
#: difference is a decision, not a mystery.
LEGACY_DROPPED = {
    "CascadeHide": "cascading hide is theme-side in plank 0.11 (see dock.theme)",
    "UrgentHueShift": "no net.launchpad.plank.dock.settings key; it lives in dock.theme",
    "IconZoom": "theme-side: dock.theme IconZoom",
    "PressToScroll": "no GSettings key in plank 0.11.89",
    "ScrollBubbles": "no GSettings key in plank 0.11.89",
}


def desired_preferences():
    """Authoritative dock preferences as ``{key: gvariant text}``."""
    prefs = {}
    for key, value, _why in PREFERENCES:
        prefs[key] = value
    return prefs


def desired_base_preferences():
    return {key: value for key, value, _why in BASE_PREFERENCES}


def preference_notes():
    notes = {}
    for key, _value, why in PREFERENCES:
        notes[key] = why
    for key, _value, why in BASE_PREFERENCES:
        notes[key] = why
    return notes


def read_legacy_ini(path):
    """Parse the legacy INI into ``{key: raw string}`` (``{}`` if absent).

    Option case is preserved: the legacy keys are CamelCase
    (``ZoomEnabled``), and configparser's default lowercasing would make
    every translation rule miss.
    """
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return {}
    if not parser.has_section(LEGACY_SECTION):
        return {}
    return dict(parser.items(LEGACY_SECTION))


def find_legacy_ini(repo_root=None):
    """First existing legacy INI, repo copy included so tests can read it."""
    if repo_root:
        candidate = os.path.join(repo_root, "configs/desktop/plank/dock1-settings")
        if os.path.isfile(candidate):
            return candidate
    for candidate in LEGACY_INI_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def legacy_translation(raw):
    """Translate legacy INI keys to GSettings keys.

    Returns ``(translated, dropped, unknown)``; ``dropped`` and ``unknown``
    are ``{legacy key: reason}`` so callers can report the difference
    instead of pretending it does not exist.
    """
    translated = {}
    dropped = {}
    unknown = {}
    for legacy_key, raw_value in raw.items():
        if legacy_key in LEGACY_PLAIN:
            gkey, convert = LEGACY_PLAIN[legacy_key]
            translated[gkey] = convert(raw_value)
        elif legacy_key in LEGACY_ENUMS:
            table = LEGACY_ENUMS[legacy_key]
            try:
                index = int(raw_value.strip())
            except ValueError:
                unknown[legacy_key] = "non-integer value %r" % raw_value
                continue
            if index in table:
                translated[_gsettings_key(legacy_key)] = table[index]
            else:
                unknown[legacy_key] = "value %d outside %s" % (index, sorted(table))
        elif legacy_key in LEGACY_DROPPED:
            dropped[legacy_key] = LEGACY_DROPPED[legacy_key]
        else:
            unknown[legacy_key] = "no translation rule"
    return translated, dropped, unknown


def _gsettings_key(legacy_key):
    return {
        "HideMode": "hide-mode",
        "Position": "position",
        "Alignment": "alignment",
    }[legacy_key]


def compare_with_legacy(path=None):
    """Compare the authority with the legacy INI declaration.

    Returns ``{"drift": [...], "authority_only": [...], "dropped": [...],
    "unknown": {...}}``.  Only ``drift`` is a failure: the authority is a
    strict superset (the GSettings keys the INI format cannot express) and
    some legacy keys are theme-side, so "extra" is information, not rot.
    """
    ini_path = path or find_legacy_ini()
    result = {"path": ini_path, "drift": [], "authority_only": [],
              "dropped": [], "unknown": {}}
    if not ini_path or not os.path.isfile(ini_path):
        result["drift"].append(
            "legacy INI not found (looked in %s)" % ", ".join(LEGACY_INI_CANDIDATES))
        return result
    raw = read_legacy_ini(ini_path)
    if not raw:
        result["drift"].append("legacy INI %s has no [%s] section"
                               % (ini_path, LEGACY_SECTION))
        return result

    translated, dropped, unknown = legacy_translation(raw)
    prefs = desired_preferences()
    notes = preference_notes()

    for gkey, value in sorted(translated.items()):
        if gkey not in prefs:
            result["drift"].append("%s: INI asks for %s but the Dock authority "
                                   "has no such key" % (gkey, value))
        elif prefs[gkey] != value:
            result["drift"].append("%s: INI %s != authority %s"
                                   % (gkey, value, prefs[gkey]))

    for gkey in sorted(set(prefs) - set(translated)):
        result["authority_only"].append(
            "%s=%s (%s)" % (gkey, prefs[gkey], notes.get(gkey, "")))
    for legacy_key, reason in sorted(dropped.items()):
        result["dropped"].append("%s — %s" % (legacy_key, reason))
    result["unknown"] = unknown
    return result


# ---------------------------------------------------------------------------
# Emission: gsettings command lines and the dconf keyfile equivalent.
# ---------------------------------------------------------------------------

def gsettings_set_commands(prefs=None):
    """``[(argv, why)]`` — one command per preference."""
    prefs = desired_preferences() if prefs is None else prefs
    notes = preference_notes()
    commands = [("gsettings", "set", BASE_SCHEMA, key, value) for key, value in
                sorted(desired_base_preferences().items())]
    for key, value in prefs.items():
        commands.append(("gsettings", "set", dock_ref(), key, value))
    return [(argv, notes.get(argv[-2], "")) for argv in commands]


def keyfile_text(prefs=None):
    """dconf ``local.d`` keyfile equivalent of the same preferences."""
    prefs = desired_preferences() if prefs is None else prefs
    notes = preference_notes()
    lines = [
        "# MavLinOS Dock (Plank) defaults — generated by",
        "# /usr/share/mavericks-apps/plank_config.py (keyfile_text).",
        "# Do not hand-edit: regenerate instead.",
        keyfile_section(),
    ]
    for key, value in sorted(prefs.items()):
        lines.append("%s=%s" % (key, value))
        if notes.get(key):
            lines.append("# %s" % notes[key])
    return "\n".join(lines) + "\n"


def keyfile_section():
    """dconf keyfile section header for the dock's relocatable path.

    dconf keyfiles spell relocatable GSettings paths as ``[/a/b/c]`` — the
    same path plank reports in its own ``dconf dump`` of the user database.
    """
    return "[%s]" % DOCK_PATH.strip("/")


# ---------------------------------------------------------------------------
# Talking to GSettings.
# ---------------------------------------------------------------------------

def _run(argv, env=None, check=False):
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError("%s failed (%d): %s" %
                           (" ".join(argv), proc.returncode,
                            (proc.stderr or proc.stdout).strip()))
    return proc


def gsettings_available():
    for tool in ("gsettings", "dconf"):
        if not _which(tool):
            return False
    return True


def _which(tool):
    for directory in os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep):
        candidate = os.path.join(directory, tool)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _which(tool):
    for directory in os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep):
        candidate = os.path.join(directory, tool)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def user_defined_keys(dump_text, base="/net/launchpad/plank/"):
    """Parse ``dconf dump`` output into absolute user key paths.

    ``dconf dump /net/launchpad/plank/`` prints section headers *relative to
    the dumped root* (``[docks/dock1]``), so ``base`` has to be prepended —
    comparing the raw headers against ``/net/launchpad/plank/docks/dock1/…``
    silently never matches and ``--apply`` then overwrites user customisation.

    Only the *user* database is consulted, which is what makes ``--apply``
    safe: a key the user changed through plank's own preferences dialog is
    present here and is therefore never overwritten.
    """
    keys = set()
    section = None
    for line in (dump_text or "").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip("/")
            section = base + header + "/" if header else base
            continue
        if not line or "=" not in line or section is None:
            continue
        keys.add("%s%s/" % (section, line.split("=", 1)[0].strip()))
    return keys


#: Root the seeder dumps, and the prefix ``dconf dump`` output is relative to.
DUMP_ROOT = "/net/launchpad/plank/"


def read_user_database(env=None):
    proc = _run(("dconf", "dump", DUMP_ROOT), env=env)
    return proc.stdout if proc.returncode == 0 else ""


def apply_preferences(env=None, force=False, dry_run=False):
    """Seed the Dock preferences plank actually reads.

    Keys the user has already customised are preserved unless ``force`` is
    given.  Returns ``(applied, skipped, failed)`` key lists.
    """
    prefs = desired_preferences()
    base = desired_base_preferences()
    existing = set() if force else user_defined_keys(read_user_database(env),
                                                      base=DUMP_ROOT)

    applied, skipped, failed = [], [], []
    for schema, mapping in ((BASE_SCHEMA, base), (dock_ref(), prefs)):
        for key, value in sorted(mapping.items()):
            full = DUMP_ROOT if schema == BASE_SCHEMA else DOCK_PATH
            if "%s%s/" % (full, key) in existing:
                skipped.append(key)
                continue
            argv = ("gsettings", "set", schema, key, value)
            if dry_run:
                applied.append(key)
                continue
            proc = _run(argv, env=env)
            if proc.returncode == 0:
                applied.append(key)
            else:
                failed.append("%s (%s)" % (key, (proc.stderr or "").strip()))
    return applied, skipped, failed


def read_back(env=None):
    """Current effective preference values as ``{key: text}``."""
    values = {}
    for key in sorted(desired_preferences()):
        proc = _run(("gsettings", "get", dock_ref(), key), env=env)
        if proc.returncode == 0:
            values[key] = proc.stdout.strip()
    return values


def verify(env=None):
    """Return the list of preferences that do not match the authority."""
    current = read_back(env)
    wanted = desired_preferences()
    problems = []
    for key, value in sorted(wanted.items()):
        actual = current.get(key)
        if actual is None:
            problems.append("%s: unreadable via gsettings" % key)
        elif actual != value:
            problems.append("%s: %s != %s" % (key, actual, value))
    return problems


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def _launch(argv):
    """Run plank after the preferences are in place."""
    plank = _which("plank")
    if plank is None:
        sys.stderr.write("mv-dock-config: plank is not installed; nothing to launch\n")
        return 127
    os.execv(plank, [plank] + argv)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mv-dock-config",
        description="MavLinOS Dock (Plank) preference seeder — plank reads "
                    "GSettings, not ~/.config/plank/dock1/settings.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true",
                         help="seed the preferences plank reads (skips keys "
                              "the user customised)")
    action.add_argument("--force", action="store_true",
                         help="apply every key, overwriting user customisation")
    action.add_argument("--print", dest="show", action="store_true",
                         help="print the authoritative preferences")
    action.add_argument("--keyfile", action="store_true",
                         help="print the equivalent dconf local.d keyfile")
    action.add_argument("--verify", action="store_true",
                         help="report preferences that do not match")
    action.add_argument("--check-legacy", action="store_true",
                        help="report drift against the legacy INI declaration")
    parser.add_argument("--dry-run", action="store_true",
                        help="with --apply/--force: report, change nothing")
    parser.add_argument("--legacy-ini", help="path to the legacy INI to check")
    parser.add_argument("--launch", nargs="*", default=None, metavar="PLANK_ARG",
                        help="apply, then exec plank (session autostart path)")
    args = parser.parse_args(argv)

    if args.show:
        for key, value, why in PREFERENCES:
            print("%-24s %s" % (key, value))
            print("%-24s   # %s" % ("", why))
        return 0
    if args.keyfile:
        sys.stdout.write(keyfile_text())
        return 0
    if args.check_legacy:
        report = compare_with_legacy(args.legacy_ini)
        for line in report["drift"]:
            print("drift: %s" % line)
        for line in report["authority_only"]:
            print("authority-only (INI cannot express it): %s" % line)
        for line in report["dropped"]:
            print("theme-side (no GSettings key): %s" % line)
        for key, reason in sorted(report["unknown"].items()):
            print("untranslated: %s (%s)" % (key, reason))
        print("ok - legacy INI agrees with the Dock authority"
              if not report["drift"] else "FAIL - legacy INI drifted")
        return 0 if not report["drift"] else 1
    if args.verify:
        if not gsettings_available():
            print("SKIP mv-dock-config --verify (no gsettings/dconf on this host)")
            return 0
        problems = verify()
        for line in problems:
            print("FAIL - %s" % line)
        if not problems:
            print("ok - plank preferences match the MavLinOS Dock authority")
        return 0 if not problems else 1
    if args.apply or args.force:
        if not gsettings_available():
            print("SKIP mv-dock-config --apply (no gsettings/dconf on this host)")
            return 0
        applied, skipped, failed = apply_preferences(force=args.force,
                                                     dry_run=args.dry_run)
        print("mv-dock-config: %d applied, %d user-customised (preserved), %d failed"
              % (len(applied), len(skipped), len(failed)))
        for item in failed:
            print("mv-dock-config: FAILED %s" % item)
        if failed:
            return 1
        if args.launch is not None:
            return _launch(args.launch)
        return 0
    if args.launch is not None:
        return _launch(args.launch)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())