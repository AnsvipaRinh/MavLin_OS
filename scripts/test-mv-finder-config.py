#!/usr/bin/env python3
"""test-mv-finder-config.py — Finder P0 integration contract (headless).

Covers the Finder integration surfaces that are pure files:
  1. xfconf channel seed configs/desktop/xfce/thunar.xml
     - every property is REAL on Thunar 4.20 (validated against the binary's
       own string table when thunar is installed; frozen list otherwise)
     - every value is a legal enum/bool
     - the airootfs mirror is byte-identical
  2. thunarrc is DEAD CONFIG on Thunar 4.20 (measured 2026-10-06: xfconf is
     the mandatory backend and the INI is never read) — the repo must not
     ship one anywhere, or the next agent will "configure" Finder defaults
     into a file nothing parses (same class as the plank INI bug).
  3. accels.scm (Finder keyboard accelerators)
     - s-expression lines parse; accelerator names parse
     - every accel path is a real Thunar action path (binary/frozen)
     - no window-local binding may use Super+Arrows: the global shortcut
       registry owns them for window tiling and a menu accel cannot win a
       grab the WM already holds.
  4. MIME defaults (mimeapps.list): images+PDF -> mv-preview, text ->
     mv-textedit, folders -> mv-finder; the defaults actually RESOLVE via
     Gio in a synthetic XDG tree built from this repo's own .desktop files.
  5. .desktop MimeType coverage matches the declared defaults.
  6. packages.x86_64 carries the Finder backend stack incl. thunar-volman.

Run: python3 scripts/test-mv-finder-config.py
GUI behaviour of the same config lives in scripts/test-thunar-finder-gui.py
(wired into scripts/check-sync.sh with its own, longer timeout).
"""
import configparser
import os
import re
import shutil
import subprocess
import sys
import tempfile

# GUI isolation guard for headless suites that spawn subprocesses
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
try:
    import mv_gui_iso
    mv_gui_iso.arm_guard()
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THUNAR_XML = os.path.join(REPO, "configs/desktop/xfce/thunar.xml")
THUNAR_XML_MIRROR = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/"
    "xfconf/xfce-perchannel-xml/thunar.xml"
)
ACCELS = os.path.join(REPO, "configs/desktop/thunar/accels.scm")
ACCELS_MIRROR = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/Thunar/accels.scm"
)
MIMEAPPS = os.path.join(REPO, "configs/desktop/mimeapps.list")
MIMEAPPS_MIRROR = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/mimeapps.list"
)
DESKTOP_DIR = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop"
)
PACKAGES = os.path.join(REPO, "archiso-profile/releng/packages.x86_64")

# Frozen from `strings /usr/bin/thunar` (Arch thunar 4.20.10) — used when the
# binary is absent so the suite still enforces the vocabulary, and used when
# the binary IS present so an upstream rename cannot slip through silently.
REAL_PROPERTIES = {
    "last-compact-view-zoom-level", "last-details-view-zoom-level",
    "last-icon-view-zoom-level", "last-menubar-visible",
    "last-separator-position", "last-show-hidden", "last-side-pane",
    "last-sort-column", "last-sort-order", "last-statusbar-visible",
    "last-view", "last-window-height", "last-window-maximized",
    "last-window-width", "misc-case-sensitive", "misc-confirm-move-to-trash",
    "misc-date-custom-style", "misc-date-style", "misc-expandable-folders",
    "misc-folders-first", "misc-horizontal-wheel-navigates",
    "misc-recursive-search", "misc-single-click", "misc-single-click-timeout",
    "misc-volume-management",
}
REAL_ZOOM = {
    "THUNAR_ZOOM_LEVEL_%d_PERCENT" % p
    for p in (25, 38, 50, 62, 75, 100, 125, 150, 175, 200, 250, 300, 400,
              800, 1600)
}
REAL_PANE = {"ThunarShortcutsPane", "ThunarTreePane"}
REAL_VIEW = {"ThunarIconView", "ThunarDetailsView", "ThunarCompactView"}
REAL_DATE = {"THUNAR_DATE_STYLE_" + s for s in (
    "SHORT", "LONG", "ISO", "SIMPLE", "CUSTOM", "CUSTOM_SIMPLE",
    "DDMMYYYY", "MMDDYYYY", "YYYYMMDD")}
REAL_SEARCH = {"THUNAR_RECURSIVE_SEARCH_ALWAYS", "THUNAR_RECURSIVE_SEARCH_LOCAL",
               "THUNAR_RECURSIVE_SEARCH_NEVER"}
REAL_SORT_COLUMN = {"THUNAR_COLUMN_" + s for s in (
    "NAME", "SIZE", "SIZE_IN_BYTES", "TYPE", "DATE_MODIFIED")}
REAL_SORT_ORDER = {"GTK_SORT_ASCENDING", "GTK_SORT_DESCENDING"}

# Accel paths from `strings /usr/bin/thunar` (Thunar 4.20.10).
REAL_ACCEL_PATHS = {
    "<Actions>/ThunarStandardView/back", "<Actions>/ThunarStandardView/forward",
    "<Actions>/ThunarStandardView/rename",
    "<Actions>/ThunarWindow/search", "<Actions>/ThunarWindow/open-parent",
    "<Actions>/ThunarWindow/show-hidden", "<Actions>/ThunarWindow/zoom-in",
    "<Actions>/ThunarWindow/zoom-out", "<Actions>/ThunarWindow/zoom-reset",
    "<Actions>/ThunarWindow/view-as-icons",
    "<Actions>/ThunarWindow/view-as-detailed-list",
    "<Actions>/ThunarWindow/view-as-compact-list",
}

# Global Super-grabs the shortcut layer already owns (window tiling): a
# Thunar-local menu accelerator bound to any of these would be dead on the
# installed system because xfwm4's grab wins.
GLOBAL_SUPER_KEYS_BANNED = {"<Super>Up", "<Super>Down", "<Super>Left",
                            "<Super>Right"}

MIME_DEFAULTS_WANT = {
    "inode/directory": "mv-finder.desktop",
    "inode/mount-point": "mv-finder.desktop",
    "x-directory/normal": "mv-finder.desktop",
    "application/pdf": "mv-preview.desktop",
    "image/png": "mv-preview.desktop",
    "image/jpeg": "mv-preview.desktop",
    "image/gif": "mv-preview.desktop",
    "image/bmp": "mv-preview.desktop",
    "image/webp": "mv-preview.desktop",
    "image/tiff": "mv-preview.desktop",
    "image/svg+xml": "mv-preview.desktop",
    "image/x-icon": "mv-preview.desktop",
    "image/x-xpixmap": "mv-preview.desktop",
    "text/plain": "mv-textedit.desktop",
    "text/markdown": "mv-textedit.desktop",
    "application/json": "mv-textedit.desktop",
    "application/x-shellscript": "mv-textedit.desktop",
    "text/x-log": "mv-textedit.desktop",
}

PASS = 0
FAILS = []


def ok(msg):
    global PASS
    PASS += 1
    print("ok - %s" % msg)


def fail(msg):
    FAILS.append(msg)
    print("FAIL - %s" % msg)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def binary_strings_props():
    """Live property vocabulary from the installed thunar, else None."""
    exe = shutil.which("thunar")
    if not exe:
        return None
    try:
        out = subprocess.run(["strings", exe], capture_output=True,
                             text=True, timeout=20).stdout
    except Exception:
        return None
    props = set()
    for line in out.splitlines():
        line = line.strip()
        if re.fullmatch(r"(last|misc)-[a-z0-9-]+", line):
            props.add(line)
        # some properties surface only through their GObject notify signal
        for m in re.finditer(r"notify::((?:last|misc)-[a-z0-9-]+)", line):
            props.add(m.group(1))
    return props or None


def binary_strings_accel_paths():
    exe = shutil.which("thunar")
    if not exe:
        return None
    try:
        out = subprocess.run(["strings", exe], capture_output=True,
                             text=True, timeout=20).stdout
    except Exception:
        return None
    paths = set(re.findall(r"<Actions>/[A-Za-z0-9_-]+/[a-z0-9-]+", out))
    return paths or None


# ---------------------------------------------------------------- thunar.xml
import xml.etree.ElementTree as ET  # noqa: E402


def check_thunar_xml():
    if not os.path.isfile(THUNAR_XML):
        fail("thunar.xml source of truth missing")
        return
    try:
        root = ET.fromstring(read(THUNAR_XML))
    except ET.ParseError as e:
        fail("thunar.xml does not parse: %s" % e)
        return
    if root.tag != "channel" or root.get("name") != "thunar":
        fail("thunar.xml must be channel name=thunar")
        return
    live = binary_strings_props()
    seen = {}
    for prop in root.iter("property"):
        name = prop.get("name")
        ptype = prop.get("type")
        value = prop.get("value")
        if not name or not ptype:
            fail("thunar.xml property without name/type: %r" % name)
            continue
        if live is not None and name not in live:
            fail("thunar.xml property %r is not a real Thunar property "
                 "(not in `strings %s`)" % (name, shutil.which("thunar")))
            continue
        if name not in REAL_PROPERTIES:
            fail("thunar.xml property %r not in the known Thunar vocabulary"
                 % name)
            continue
        seen[name] = value

    enum_checks = [
        ("last-view", REAL_VIEW), ("last-side-pane", REAL_PANE),
        ("last-icon-view-zoom-level", REAL_ZOOM),
        ("last-details-view-zoom-level", REAL_ZOOM),
        ("last-compact-view-zoom-level", REAL_ZOOM),
        ("misc-date-style", REAL_DATE),
        ("misc-recursive-search", REAL_SEARCH),
        ("last-sort-column", REAL_SORT_COLUMN),
        ("last-sort-order", REAL_SORT_ORDER),
    ]
    for name, allowed in enum_checks:
        if name in seen and seen[name] not in allowed:
            fail("thunar.xml %s=%r is not a legal value" % (name, seen[name]))
    for name, value in seen.items():
        if name.startswith("misc-") and name not in (
                "misc-date-style", "misc-recursive-search"):
            if value not in ("true", "false"):
                fail("thunar.xml bool %s=%r must be true/false" % (name, value))

    # Finder coherence contract
    want = {
        "last-view": "ThunarIconView",
        "last-icon-view-zoom-level": "THUNAR_ZOOM_LEVEL_150_PERCENT",
        "last-side-pane": "ThunarShortcutsPane",
        "last-statusbar-visible": "true",
        "last-show-hidden": "false",
        "misc-single-click": "false",
        "misc-horizontal-wheel-navigates": "true",
        "misc-volume-management": "true",
    }
    for name, value in want.items():
        if seen.get(name) != value:
            fail("thunar.xml %s must be %s (got %r) — Finder default"
                 % (name, value, seen.get(name)))
    ok("thunar.xml: %d properties, all real, all legal values" % len(seen))

    if os.path.isfile(THUNAR_XML_MIRROR):
        if read(THUNAR_XML) == read(THUNAR_XML_MIRROR):
            ok("thunar.xml mirror byte-identical")
        else:
            fail("thunar.xml mirror drift (configs vs airootfs skel)")
    else:
        fail("thunar.xml mirror missing: %s" % THUNAR_XML_MIRROR)

    if live is not None:
        missing = {n for n in seen if n not in live}
        if not missing:
            ok("every seeded property exists in the installed thunar binary")


# ------------------------------------------------------------------ thunarrc
def check_thunarrc_banned():
    hits = []
    for base in ("configs", "archiso-profile/releng/airootfs/etc/skel"):
        for dirpath, _dirnames, filenames in os.walk(os.path.join(REPO, base)):
            for fn in filenames:
                if fn == "thunarrc":
                    hits.append(os.path.join(dirpath, fn))
    if hits:
        fail("thunarrc is dead config on Thunar 4.20 (xfconf is the only "
             "backend; measured 2026-10-06) — remove: %s" % hits)
    else:
        ok("no dead thunarrc shipped anywhere")


# ----------------------------------------------------------------- accels.scm
ACCEL_LINE = re.compile(
    r'^\(gtk_accel_path "([^"]+)" "([^"]+)"\)$')


def parse_accel(name):
    """Return the set of modifier tokens + key token, or None."""
    m = re.fullmatch(r"<([^>]+)>(\w+)", name)
    if m:
        mods = {x.strip() for x in m.group(1).split(",") if x.strip()}
        return mods, m.group(2)
    if re.fullmatch(r"\w+", name):
        return set(), name
    return None


def check_accels():
    if not os.path.isfile(ACCELS):
        fail("accels.scm source of truth missing")
        return
    lines = [ln.strip() for ln in read(ACCELS).splitlines()
             if ln.strip() and not ln.strip().startswith(";")]
    paths = {}
    for ln in lines:
        m = ACCEL_LINE.fullmatch(ln)
        if not m:
            fail("accels.scm line is not a valid accel binding: %r" % ln)
            continue
        path, accel = m.group(1), m.group(2)
        parsed = parse_accel(accel)
        if parsed is None:
            fail("accels.scm accelerator %r does not parse" % accel)
            continue
        mods, key = parsed
        if "Super" not in mods and accel != "Return":
            # window-local plain/Ctrl bindings would shadow app defaults;
            # this file exists specifically for the Cmd-like Super layer
            fail("accels.scm %s: %r — only Super-modified (Cmd-like) "
                 "bindings plus Return belong here" % (path, accel))
        paths[path] = accel

    live_paths = binary_strings_accel_paths()
    for path in paths:
        if path not in REAL_ACCEL_PATHS:
            fail("accels.scm path %r is not a Thunar action accel path" % path)
        elif live_paths is not None and path not in live_paths:
            fail("accels.scm path %r missing from installed thunar binary"
                 % path)
    banned_here = [a for a in paths.values()
                   if a in GLOBAL_SUPER_KEYS_BANNED]
    if banned_here:
        fail("accels.scm binds %s — the global registry owns Super+Arrows "
             "for tiling; a menu accel cannot win that grab" % banned_here)

    want = {
        "<Actions>/ThunarStandardView/back": "<Super>bracketleft",
        "<Actions>/ThunarStandardView/forward": "<Super>bracketright",
        "<Actions>/ThunarWindow/search": "<Super>f",
        "<Actions>/ThunarStandardView/rename": "Return",
    }
    for path, accel in want.items():
        if paths.get(path) != accel:
            fail("accels.scm %s must be %s (got %r) — Finder Cmd+[ / Cmd+] / "
                 "Cmd+F / Return-renames" % (path, accel, paths.get(path)))
    if len(paths) == len(want):
        ok("accels.scm: %d Finder bindings, paths real, no grab conflicts"
           % len(paths))

    if os.path.isfile(ACCELS_MIRROR):
        if read(ACCELS) == read(ACCELS_MIRROR):
            ok("accels.scm mirror byte-identical")
        else:
            fail("accels.scm mirror drift (configs vs airootfs skel)")
    else:
        fail("accels.scm mirror missing: %s" % ACCELS_MIRROR)

    # global-registry cross-check: Super+bracket/f must not be double-bound
    shortcuts_xml = os.path.join(
        REPO, "packages/mavericks-apps/src/mavericks-apps/config/"
        "xfce4-keyboard-shortcuts.xml")
    if os.path.isfile(shortcuts_xml):
        text = read(shortcuts_xml)
        for tok in ("Super&gt;bracketleft", "Super&gt;bracketright",
                    "Super&gt;f<"):
            if tok.replace("&gt;", ">") in text.replace("&gt;", ">"):
                fail("global registry also binds %s — double grab" % tok)


# --------------------------------------------------------------- mime default
def check_mime_defaults():
    if not os.path.isfile(MIMEAPPS):
        fail("mimeapps.list source of truth missing")
        return
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(MIMEAPPS, encoding="utf-8")
    if not cp.has_section("Default Applications"):
        fail("mimeapps.list lacks [Default Applications]")
        return
    got = dict(cp.items("Default Applications"))
    for mime, desktop in MIME_DEFAULTS_WANT.items():
        if got.get(mime) != desktop:
            fail("mimeapps.list default %s must be %s (got %r)"
                 % (mime, desktop, got.get(mime)))
    ok("mimeapps.list: %d Finder defaults present" % len(MIME_DEFAULTS_WANT))

    if not os.path.isfile(MIMEAPPS_MIRROR) or \
            read(MIMEAPPS) != read(MIMEAPPS_MIRROR):
        fail("mimeapps.list mirror drift (configs vs airootfs skel)")
    else:
        ok("mimeapps.list mirror byte-identical")

    # .desktop coverage: every referenced desktop file must exist and
    # declare the types it is made default for
    for desktop, mimes in (
            ("mv-finder.desktop", ["inode/directory"]),
            ("mv-preview.desktop", ["application/pdf", "image/png"]),
            ("mv-textedit.desktop", ["text/plain", "application/json",
                                     "application/x-shellscript"]),
    ):
        path = os.path.join(DESKTOP_DIR, desktop)
        if not os.path.isfile(path):
            fail("%s missing in package desktop dir" % desktop)
            continue
        entry = read(path)
        m = re.search(r"^MimeType=(.*)$", entry, re.M)
        declared = set((m.group(1).strip().rstrip(";").split(";")
                        if m else []))
        for mime in mimes:
            if mime not in declared:
                fail("%s does not declare MimeType=%s but is its default"
                     % (desktop, mime))
        m2 = re.search(r"^Exec=(.*)$", entry, re.M)
        if not m2 or not m2.group(1).strip():
            fail("%s has no Exec" % desktop)
    ok("desktop entries declare the types they default for")


def check_gio_resolution():
    """Prove the defaults actually resolve, in a synthetic XDG tree built
    from this repo's own files (no installed-system state involved)."""
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
    except (ImportError, ValueError):
        print("SKIP - Gio not importable (headless host)")
        return
    tmp = tempfile.mkdtemp(prefix="mv-mime-")
    apps = os.path.join(tmp, "applications")
    os.makedirs(apps)
    for desktop in ("mv-finder.desktop", "mv-preview.desktop",
                    "mv-textedit.desktop"):
        shutil.copy(os.path.join(DESKTOP_DIR, desktop),
                    os.path.join(apps, desktop))
    cfg = os.path.join(tmp, "config")
    os.makedirs(cfg)
    shutil.copy(MIMEAPPS, os.path.join(cfg, "mimeapps.list"))
    probe = r"""
import json, os, sys
import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio
res = {}
for mime in sys.argv[1:]:
    app = Gio.AppInfo.get_default_for_type(mime, False)
    res[mime] = app.get_id() if app else None
print(json.dumps(res))
"""
    env = dict(os.environ)
    env.update({
        "XDG_DATA_HOME": tmp,
        "XDG_CONFIG_HOME": cfg,
        "XDG_DATA_DIRS": "",
        "XDG_CONFIG_DIRS": "",
    })
    r = subprocess.run([sys.executable, "-c", probe] + sorted(MIME_DEFAULTS_WANT),
                       capture_output=True, text=True, env=env, timeout=30)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode != 0:
        fail("Gio resolution probe failed: %s" % r.stderr.strip()[:200])
        return
    import json
    got = json.loads(r.stdout)
    bad = {m: v for m, v in got.items()
           if v != MIME_DEFAULTS_WANT[m]}
    if bad:
        fail("Gio resolves wrong defaults: %s (want e.g. image/png -> "
             "mv-preview.desktop)" % bad)
    else:
        ok("Gio resolves all %d defaults to the Mavericks apps (live "
           "Gio lookup, repo's own desktop files)" % len(got))


# ------------------------------------------------------------------ packaging
def check_packages():
    text = read(PACKAGES)
    for pkg in ("thunar", "thunar-archive-plugin", "thunar-volman", "gvfs",
                "trash-cli"):
        if not re.search(r"^%s$" % re.escape(pkg), text, re.M):
            fail("packages.x86_64 missing %s" % pkg)
    ok("package list: thunar + volman + gvfs + trash-cli present")


def main():
    check_thunar_xml()
    check_thunarrc_banned()
    check_accels()
    check_mime_defaults()
    check_gio_resolution()
    check_packages()
    print()
    if FAILS:
        print("FAILED: %d checks" % len(FAILS))
        return 1
    print("PASSED: %d checks" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
