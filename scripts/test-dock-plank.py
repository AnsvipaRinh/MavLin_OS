#!/usr/bin/env python3
"""Dock (Plank) P0 gate: preferences must actually reach plank.

Plank 0.11.x keeps its preferences in GSettings, NOT in the legacy INI file
``~/.config/plank/dock1/settings``.  This suite locks that fact down:

  * every preference the Dock authority writes must be a real key of
    ``net.launchpad.plank.dock.settings`` with a value the schema accepts
    (enum nicks included — the legacy INI's integer encodings do NOT match
    the GSettings enums, which is how a plausible-looking translation
    silently breaks);
  * the path plank reads must be ``/net/launchpad/plank/docks/dock1/``;
  * the seeder must never touch ``dock-items`` (plank's own runtime state);
  * user customisation through plank's preferences dialog must survive;
  * the legacy INI mirrors must stay byte-identical and carry the warning
    that keeps the dead file from being trusted again;
  * the Dock must ship: Mavericks dock.theme, session autostart that seeds
    before plank starts, Finder/Launchpad/Mission Control/Firefox/Mail/
    System Settings/Terminal/Trash pins, and no leftover second copy of the
    dead INI.

Run: python3 scripts/test-dock-plank.py   (no display required)
"""
import configparser
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps")
LIB = os.path.join(APPS, "lib")
sys.path.insert(0, LIB)

import plank_config as pc  # noqa: E402

GSCHEMA = "/usr/share/glib-2.0/schemas/net.launchpad.plank.gschema.xml"
LEGACY_INI_CFG = os.path.join(REPO, "configs/desktop/plank/dock1-settings")
LEGACY_INI_SKEL = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/settings")
AUTOSTART_CFG = os.path.join(REPO, "configs/desktop/plank/plank.desktop")
AUTOSTART_SKEL = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/autostart/plank.desktop")
LAUNCHER_DIRS = (
    os.path.join(REPO, "configs/desktop/plank/dock1/launchers"),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/plank/dock1/launchers"),
)

errors = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        errors.append(message)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# 1. The GSettings identity plank actually uses
# ---------------------------------------------------------------------------

check(pc.DOCK_SCHEMA == "net.launchpad.plank.dock.settings",
      "dock schema must be net.launchpad.plank.dock.settings")
check(pc.DOCK_PATH == "/net/launchpad/plank/docks/dock1/",
      "dock path must be /net/launchpad/plank/docks/dock1/ (verified from "
      "plank's own dconf dump); got %r" % pc.DOCK_PATH)
check(pc.dock_ref() ==
      "net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/",
      "dock_ref must be schema:path, got %r" % pc.dock_ref())

# ---------------------------------------------------------------------------
# 2. Every preference is a real schema key with a legal value
# ---------------------------------------------------------------------------


def load_schema():
    """{key: {"type": str, "enums": {nick: value}}} from the installed schema."""
    if not os.path.isfile(GSCHEMA):
        return None
    root = ET.parse(GSCHEMA).getroot()
    enum_nicks = {}
    for enum in root.iter("enum"):
        for value in enum.iter("value"):
            enum_nicks[value.get("nick")] = value.get("value")
    keys = {}
    for key in root.iter("key"):
        name = key.get("name")
        kind = key.get("type")
        enums = []
        if key.get("enum"):
            enums = [v.get("nick") for v in key.iter("value")]
        keys[name] = {"type": kind, "enums": enums}
    return {"keys": keys, "enum_values": enum_nicks}


schema = load_schema()
prefs = pc.desired_preferences()
base_prefs = pc.desired_base_preferences()

if schema is None:
    print("SKIP dock-plank: %s absent (plank not installed) — schema-level "
          "assertions skipped" % GSCHEMA)
else:
    for key, value in sorted(prefs.items()):
        spec = schema["keys"].get(key)
        check(spec is not None,
              "plank schema has no key %r — the seeder would fail at runtime"
              % key)
        if spec is None:
            continue
        if spec["enums"]:
            nick = value.strip("'")
            check(nick in spec["enums"],
                  "%s=%s is not one of the schema enum nicks %s"
                  % (key, value, spec["enums"]))
        elif spec["type"] == "i":
            check(re.fullmatch(r"-?\d+", value) is not None,
                  "%s=%s must be an integer for schema type i" % (key, value))
        elif spec["type"] == "b":
            check(value in ("true", "false"),
                  "%s=%s must be a boolean for schema type b" % (key, value))
        elif spec["type"] == "s":
            check(value.startswith("'") and value.endswith("'"),
                  "%s=%s must be a quoted string for schema type s" % (key, value))
    for key in base_prefs:
        check(key in schema["keys"] or key == "enabled-docks",
              "base schema has no key %r" % key)
    print("ok - every Dock preference validated against the installed plank "
          "gschema (%d keys)" % len(prefs))

# ---------------------------------------------------------------------------
# 3. The seeder must not disturb plank's own runtime state
# ---------------------------------------------------------------------------

check("dock-items" not in prefs,
      "the seeder must not write dock-items: that is plank's runtime list of "
      "live items and writing it would fight the session")
check("enabled-docks" not in prefs,
      "enabled-docks lives on the non-relocatable schema, not the dock one")
for key in prefs:
    check(key != "dock-items", "dock-items must never be seeded")

# ---------------------------------------------------------------------------
# 4. User customisation survives --apply
# ---------------------------------------------------------------------------

# `dconf dump /net/launchpad/plank/` prints section headers RELATIVE to the
# dumped root.  Feeding the absolute form here would hide the exact bug this
# assertion exists for: the parser silently produced /docks/dock1/icon-size/
# and --apply then overwrote whatever the user had customised.
user_db = "\n".join([
    "[docks/dock1]",
    "icon-size=64",
    "theme='Matte'",
])
defined = pc.user_defined_keys(user_db)
check("/net/launchpad/plank/docks/dock1/icon-size/" in defined,
      "user_defined_keys must report a customised icon-size, got %s" % defined)
check("/net/launchpad/plank/docks/dock1/theme/" in defined,
      "user_defined_keys must report a customised theme")
check(len(defined) == 2,
      "user_defined_keys must return exactly the user-set keys, got %s" % defined)
check(pc.user_defined_keys("") == set(),
      "an empty dconf dump must yield no customisation")
check(pc.user_defined_keys("icon-size=64") == set(),
      "keys outside any section must be ignored, not invented")
check(pc.DUMP_ROOT == "/net/launchpad/plank/",
      "the dump root must match the paths the seeder compares against")
check(pc.DUMP_ROOT.endswith("/"),
      "the dump root must keep its trailing slash: `dconf dump` needs the "
      "path to look like a directory, and without it the dump fails, "
      "--apply sees no customisation and overwrites the user's settings")
untouched = [key for key in sorted(prefs) if key not in ("icon-size", "theme")]
for key in untouched:
    check(("/net/launchpad/plank/docks/dock1/%s/" % key) not in defined,
          "%s is absent from the dump and must not be reported as "
          "user-customised" % key)

# ---------------------------------------------------------------------------
# 5. Emitters
# ---------------------------------------------------------------------------

keyfile = pc.keyfile_text()
check(keyfile.count("[net/launchpad/plank/docks/dock1]") == 1,
      "keyfile must declare the dock section exactly once")
for key, value in prefs.items():
    check(("%s=%s" % (key, value)) in keyfile,
          "keyfile missing %s=%s" % (key, value))

commands = pc.gsettings_set_commands()
check(len(commands) == len(prefs) + len(base_prefs),
      "one gsettings command per preference expected")
for argv, _why in commands:
    check(argv[0] == "gsettings" and argv[1] == "set",
          "unexpected command shape %s" % (argv,))
    check(argv[2] in (pc.BASE_SCHEMA, pc.dock_ref()),
          "command targets an unexpected schema: %s" % argv[2])

# ---------------------------------------------------------------------------
# 6. Legacy INI: mirrored, warned-about, and in sync with the authority
# ---------------------------------------------------------------------------

check(os.path.isfile(LEGACY_INI_CFG), "configs legacy INI missing")
check(os.path.isfile(LEGACY_INI_SKEL), "skel legacy INI missing")
if os.path.isfile(LEGACY_INI_CFG) and os.path.isfile(LEGACY_INI_SKEL):
    cfg_bytes = open(LEGACY_INI_CFG, "rb").read()
    skel_bytes = open(LEGACY_INI_SKEL, "rb").read()
    check(cfg_bytes == skel_bytes,
          "legacy INI drifted between configs/ and airootfs/")
    header = read(LEGACY_INI_CFG)
    check("DO NOT EDIT AS AN AUTHORITY" in header,
          "the legacy INI must warn that plank does not read it")
    check("mv-dock-config" in header,
          "the legacy INI must point at the authority (mv-dock-config)")
    check(pc.LEGACY_SECTION in header,
          "legacy INI must keep the [%s] section for existing tooling"
          % pc.LEGACY_SECTION)
    report = pc.compare_with_legacy(LEGACY_INI_CFG)
    check(not report["drift"],
          "legacy INI drifted from the Dock authority: %s" % report["drift"])
    check(not report["unknown"],
          "legacy INI has untranslated keys: %s" % report["unknown"])
    check(any(entry.startswith("auto-pinning=true")
              for entry in report["authority_only"]),
          "auto-pinning must be part of the authority: it cannot be expressed "
          "in the legacy INI, and plank's default happens to be the macOS "
          "behaviour (running apps appear and disappear again)")
check(prefs.get("auto-pinning") == "true",
      "auto-pinning must stay true: macOS shows running apps in the Dock and "
      "drops them when they quit (measured in test-dock-plank-gui.py); false "
      "would hide every unpinned running app")

parser = configparser.ConfigParser(interpolation=None)
parser.optionxform = str
parser.read(LEGACY_INI_CFG, encoding="utf-8")
check(parser.has_section(pc.LEGACY_SECTION),
      "legacy INI lost its [%s] section" % pc.LEGACY_SECTION)
check(parser.get(pc.LEGACY_SECTION, "Theme") == "Mavericks",
      "legacy INI must still declare Theme=Mavericks (read by other tooling)")

# ---------------------------------------------------------------------------
# 7. The Dock autostart seeds preferences BEFORE plank starts
# ---------------------------------------------------------------------------

check(os.path.isfile(AUTOSTART_CFG), "configs Dock autostart entry missing")
check(os.path.isfile(AUTOSTART_SKEL), "skel Dock autostart entry missing")
if os.path.isfile(AUTOSTART_CFG) and os.path.isfile(AUTOSTART_SKEL):
    check(open(AUTOSTART_CFG, "rb").read() == open(AUTOSTART_SKEL, "rb").read(),
          "Dock autostart drifted between configs/ and airootfs/")
    autostart = read(AUTOSTART_CFG)
    check("Exec=mv-dock-config --apply --launch" in autostart,
          "Dock autostart must seed preferences and then exec plank, got: %s"
          % [line for line in autostart.splitlines()
             if line.startswith("Exec=")])
    check("X-GNOME-Autostart-enabled=true" in autostart,
          "Dock autostart must be enabled")
    check("Terminal=false" in autostart,
          "Dock autostart must not open a terminal")

# ---------------------------------------------------------------------------
# 8. Packaging
# ---------------------------------------------------------------------------

makefile = read(os.path.join(APPS, "Makefile"))
check("lib/plank_config.py" in makefile,
      "Makefile must install the Dock preference authority")
check("bin/mv-dock-config" in makefile,
      "Makefile must install the mv-dock-config entry point")
check("configs/desktop/plank/plank.desktop" in makefile,
      "Makefile must install the Dock autostart into /etc/skel so a plain "
      "pacman install actually starts a Dock")

theme_install = os.path.join(REPO, "packages/mavericks-theme/mavericks-theme.install")
check(os.path.isfile(theme_install), "mavericks-theme.install missing")
if os.path.isfile(theme_install):
    body = read(theme_install)
    check("/etc/skel/.config/plank/dock1/settings" not in body,
          "mavericks-theme.install must not write a second copy of the dead "
          "Plank INI (it fought the mirrored copy and pinned Position=0, "
          "i.e. the TOP edge)")
    check("plank_config" in body or "mv-dock-config" in body,
          "mavericks-theme.install should explain that Dock preferences are "
          "seeded by mv-dock-config now")

theme_pkgbuild = read(os.path.join(REPO, "packages/mavericks-theme/PKGBUILD"))
check("plank" in theme_pkgbuild.split("depends=")[1].split("\n")[0],
      "mavericks-theme must keep depending on plank (it ships dock.theme)")

dock_theme = os.path.join(REPO,
                          "packages/mavericks-theme/src/mavericks-theme/plank/dock.theme")
check(os.path.isfile(dock_theme), "Mavericks plank theme missing")
check(os.path.basename(dock_theme) == "dock.theme",
      "plank themes must be named dock.theme or plank will not load them")

# ---------------------------------------------------------------------------
# 8b. The Mavericks theme must be one plank 0.11 can actually parse
#
# plank reads theme keys straight out of libplank, so the authoritative
# vocabulary is what the binary really looks up.  Keys it does not know are
# dropped without a warning, which is how the Dock ended up rendering as the
# stock theme while the repo carried a "Mavericks glass" file: rgba()/hex
# colour strings, inline "value # comment" annotations, and reflection /
# translucent-shelf / indicator-colour keys that plank 0.11.89 does not have.
# ---------------------------------------------------------------------------

PLANK_LIB = None
for candidate in ("/usr/lib/libplank.so.1",
                  "/usr/lib/libplank.so",
                  "/usr/lib/x86_64-linux-gnu/libplank.so.1"):
    if os.path.isfile(candidate):
        PLANK_LIB = candidate
        break

THEME_KEY_PATTERN = re.compile(r"^[A-Z][A-Za-z]+$", re.MULTILINE)
if PLANK_LIB is None:
    print("SKIP dock-plank: libplank not found — theme vocabulary not verified "
          "against the binary")
else:
    strings = subprocess.run(["strings", "-a", PLANK_LIB],
                             stdout=subprocess.PIPE, text=True).stdout
    known_keys = set(THEME_KEY_PATTERN.findall(strings))
    # Keys that only exist for other subsystems and would be a false positive.
    noise = {"LaunchersDir", "PressureReveal"}
    colour_keys = {key for key in known_keys
                   if key.endswith("Color") or key.endswith("Colour")}

    theme = configparser.ConfigParser(interpolation=None, strict=False)
    theme.optionxform = str
    with open(dock_theme, encoding="utf-8") as handle:
        raw_lines = handle.readlines()
    theme.read_string("".join(raw_lines), source=dock_theme)

    check(theme.has_section("PlankTheme"),
          "dock.theme must have a [PlankTheme] group (plank ignores the whole "
          "file without it)")
    check(theme.has_section("PlankDockTheme"),
          "dock.theme must have a [PlankDockTheme] group: paddings, indicator "
          "size, timings and cascade-hide live there, not in [PlankTheme]")

    unknown = []
    bad_colour = []
    for section in theme.sections():
        for key, value in theme.items(section):
            if key in noise or key not in known_keys:
                unknown.append("%s/%s" % (section, key))
            if key in colour_keys and not re.fullmatch(
                    r"\d+(\.\d+)?;;\d+(\.\d+)?;;\d+(\.\d+)?;;\d+(\.\d+)?", value):
                bad_colour.append("%s/%s=%s" % (section, key, value))
    check(not unknown,
          "dock.theme sets keys plank 0.11 does not look up, so they are "
          "silently dropped: %s" % unknown)
    check(not bad_colour,
          "dock.theme colours must be 'r;;g;;b;;a' integers — rgba()/hex "
          "strings are not valid plank syntax: %s" % bad_colour)

    inline_comments = [line.strip() for line in raw_lines
                       if "=" in line and not line.lstrip().startswith("#")
                       and "#" in line.split("=", 1)[1]]
    check(not inline_comments,
          "dock.theme must not put '#' after a value: GKeyFile has no inline "
          "comments, so the comment text becomes part of the value: %s"
          % inline_comments)

    # The Mavericks look that plank 0.11 CAN render: a light metallic shelf
    # with a hairline stroke and no icon drop shadows (Mavericks-era).
    drawing = dict(theme.items("PlankTheme")) if theme.has_section("PlankTheme") else {}
    behaviour = dict(theme.items("PlankDockTheme")) if theme.has_section("PlankDockTheme") else {}
    for key in ("TopRoundness", "BottomRoundness", "LineWidth", "OuterStrokeColor",
                "FillStartColor", "FillEndColor", "InnerStrokeColor"):
        check(key in drawing,
              "[PlankTheme] must define %s (the Mavericks shelf geometry and "
              "metallic gradient)" % key)
    for key in ("HorizPadding", "TopPadding", "BottomPadding", "ItemPadding",
                "IndicatorSize", "IconShadowSize"):
        check(key in behaviour,
              "[PlankDockTheme] must define %s" % key)
    check(float(drawing.get("FillStartColor", "0;;0;;0;;0").split(";;")[0]) >= 150,
          "the Mavericks shelf is a LIGHT metallic gradient; FillStartColor "
          "got %r" % drawing.get("FillStartColor"))
    check(float(behaviour.get("IconShadowSize", "1")) == 0,
          "Mavericks Dock icons carry no drop shadow (IconShadowSize=0), got "
          "%r" % behaviour.get("IconShadowSize"))
    print("ok - Mavericks dock.theme parses as plank 0.11 (%d keys, none "
          "unknown to the binary)" % sum(len(dict(theme.items(s)))
                                          for s in theme.sections()))
    print("ok - documented limit: plank 0.11.89 has no Reflection*/Background*/"
          "IndicatorColor keys, so the macOS reflection and the translucent "
          "shelf cannot come from the plank theme")

# ---------------------------------------------------------------------------
# 9. Pins: Finder, Launchpad, Mission Control, Firefox, Mail, Settings,
#    Terminal, Trash — in both launcher sets, with live targets
# ---------------------------------------------------------------------------

PINS = {
    "finder.dockitem": "mv-finder.desktop",
    "launchpad.dockitem": "mv-launchpad.desktop",
    "mission-control.dockitem": "mv-mission-control.desktop",
    "firefox.dockitem": "firefox.desktop",
    "mail.dockitem": "mv-mail.desktop",
    "system-settings.dockitem": "mv-system-settings.desktop",
    "terminal.dockitem": "xfce4-terminal.desktop",
    "trash.dockitem": None,
}
for launcher_dir in LAUNCHER_DIRS:
    check(os.path.isdir(launcher_dir),
          "dock launcher dir missing: %s" % launcher_dir)
    if not os.path.isdir(launcher_dir):
        continue
    for name, desktop in PINS.items():
        path = os.path.join(launcher_dir, name)
        check(os.path.isfile(path), "missing %s in %s" % (name, launcher_dir))
        if not os.path.isfile(path):
            continue
        body = read(path)
        if desktop is None:
            check("Launcher=docklet://trash" in body,
                  "%s must use the plank trash docklet" % name)
        else:
            check("Launcher=file:///usr/share/applications/%s" % desktop in body,
                  "%s must point at %s" % (name, desktop))

if all(os.path.isdir(d) for d in LAUNCHER_DIRS):
    first = sorted(os.listdir(LAUNCHER_DIRS[0]))
    second = sorted(os.listdir(LAUNCHER_DIRS[1]))
    check(first == second,
          "dock pin sets drifted: %s vs %s" % (first, second))
    for name in sorted(set(first) & set(second)):
        a = open(os.path.join(LAUNCHER_DIRS[0], name), "rb").read()
        b = open(os.path.join(LAUNCHER_DIRS[1], name), "rb").read()
        check(a == b, "dock pin content drift for %s" % name)

# Every pin must have a live target, or plank silently drops it.
packages_list = read(os.path.join(REPO,
                                  "archiso-profile/releng/packages.x86_64"))
for name, desktop in PINS.items():
    if desktop is None:
        continue
    if desktop in PINS.values() and desktop.startswith("mv-"):
        target = os.path.join(APPS, "desktop", desktop)
        check(os.path.isfile(target),
              "%s targets %s which mavericks-apps does not install"
              % (name, desktop))
    elif desktop == "firefox.desktop":
        check(re.search(r"^firefox$", packages_list, re.M) is not None,
              "firefox.dockitem has no firefox package in packages.x86_64")

# ---------------------------------------------------------------------------
# 10. Module hygiene
# ---------------------------------------------------------------------------

proc = subprocess.run([sys.executable, "-m", "py_compile",
                       os.path.join(LIB, "plank_config.py")],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
check(proc.returncode == 0, "plank_config.py does not compile: %s"
      % proc.stderr)
wrapper = os.path.join(APPS, "bin", "mv-dock-config")
check(os.access(wrapper, os.X_OK), "bin/mv-dock-config must be executable")
proc = subprocess.run([sys.executable, wrapper, "--print"],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
check(proc.returncode == 0,
      "mv-dock-config --print must work from the repo tree: %s" % proc.stderr)
check("Mavericks" in proc.stdout, "mv-dock-config --print must show the theme")
proc = subprocess.run([sys.executable, wrapper, "--check-legacy",
                       "--legacy-ini", LEGACY_INI_CFG],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
check(proc.returncode == 0,
      "mv-dock-config --check-legacy must pass: %s\n%s"
      % (proc.stdout, proc.stderr))

# ---------------------------------------------------------------------------

if errors:
    for error in errors:
        print("FAIL - %s" % error)
    print("FAIL - dock P0: %d of %d assertions failed" % (len(errors), checks))
    sys.exit(1)

print("ok - dock P0: %d assertions" % checks)
print("ok - plank preferences go through GSettings %s (not dock1/settings)"
      % pc.dock_ref())
print("ok - Mavericks dock.theme + Finder/Launchpad/Mission Control/Firefox/"
      "Mail/Settings/Terminal/Trash pins")
sys.exit(0)