#!/usr/bin/env python3
"""Headless tests for mv_desktop_cache (shared .desktop parse cache, P1-L1).

Covers:
- parse: valid entry, Exec % stripping, Hidden/NoDisplay filtering,
  missing Name/Exec rejection
- fingerprint: add/remove/modify each change the key (airtight invalidation)
- cache: hit skips all .desktop reads; miss re-parses and rewrites
- corrupt cache: quarantined (.corrupt-<ts>), treated as miss, cache rebuilt
- integration: mv-launchpad/mv-spotlight load_desktop_apps consume the cache

Usage: python3 scripts/test-mv-desktop-cache.py
Exit 0 = all tests passed."""
import builtins
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")
MOD_PATH = os.path.join(BIN_DIR, "mv_desktop_cache.py")

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def load_app(name):
    return load_module(name, os.path.join(BIN_DIR, name))


DESKTOP_FILE = """[Desktop Entry]
Name=Test App
Exec=testapp %U
Icon=test-icon
Categories=Utility;
"""

DESKTOP_FILE_2 = """[Desktop Entry]
Name=Other App
Exec=otherapp %F
Icon=other-icon
Categories=Network;WebBrowser;
"""


class Sandbox:
    """Isolated HOME + a single fake desktop dir; patches module dirs."""

    def __init__(self, mod):
        self.mod = mod
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.desktop = os.path.join(self.tmp, "applications")
        os.makedirs(self.home)
        os.makedirs(self.desktop)
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.home
        self.old_dirs = mod.desktop_dirs
        mod.desktop_dirs = lambda: [self.desktop]

    def close(self):
        self.mod.desktop_dirs = self.old_dirs
        if self.old_home is not None:
            os.environ["HOME"] = self.old_home
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cache_path(self):
        return os.path.join(self.home, ".cache", "mavericks",
                            "desktop-entries.json")

    def write(self, name, content):
        path = os.path.join(self.desktop, name)
        with open(path, "w") as f:
            f.write(content)
        return path


def test_xdg_application_paths(mod):
    """Desktop discovery must honor XDG_DATA_HOME/XDG_DATA_DIRS precedence."""
    sb = Sandbox(mod)
    old = {key: os.environ.get(key) for key in ("XDG_DATA_HOME", "XDG_DATA_DIRS")}
    try:
        custom_home = os.path.join(sb.tmp, "xdg-home")
        custom_system = os.path.join(sb.tmp, "xdg-system")
        os.makedirs(os.path.join(custom_home, "applications"))
        os.makedirs(os.path.join(custom_system, "applications"))
        os.environ["XDG_DATA_HOME"] = custom_home
        os.environ["XDG_DATA_DIRS"] = custom_system
        dirs = mod.desktop_dirs()
        check("xdg: custom user applications path first",
              dirs[0] == os.path.join(custom_home, "applications"), repr(dirs))
        check("xdg: custom system applications path second",
              dirs[1] == os.path.join(custom_system, "applications"), repr(dirs))
        user = os.path.join(custom_home, "applications", "same.desktop")
        system = os.path.join(custom_system, "applications", "same.desktop")
        with open(user, "w") as f:
            f.write(DESKTOP_FILE)
        with open(system, "w") as f:
            f.write(DESKTOP_FILE_2)
        entries = mod.load_desktop_entries()
        check("xdg: user entry overrides system entry",
              len(entries) == 1 and entries[0]["name"] == "Test App", repr(entries))
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sb.close()


def test_recursive_desktop_ids(mod):
    """Nested application entries use the freedesktop desktop-file ID."""
    sb = Sandbox(mod)
    try:
        nested = os.path.join(sb.desktop, "foo", "bar")
        os.makedirs(nested)
        path = os.path.join(nested, "Nested.desktop")
        with open(path, "w") as f:
            f.write(DESKTOP_FILE)
        entries = mod.load_desktop_entries()
        check("desktop-id: nested entry discovered", len(entries) == 1, repr(entries))
        check("desktop-id: nested path becomes foo-bar.desktop",
              entries[0].get("desktop_id") == "foo-bar.desktop", repr(entries))
    finally:
        sb.close()


def test_environment_filters(mod):
    """OnlyShowIn/NotShowIn/TryExec must affect application discovery."""
    sb = Sandbox(mod)
    old = {key: os.environ.get(key) for key in ("XDG_CURRENT_DESKTOP", "PATH")}
    try:
        os.environ["XDG_CURRENT_DESKTOP"] = "XFCE"
        sb.write("only-xfce.desktop", DESKTOP_FILE + "OnlyShowIn=XFCE;\n")
        sb.write("only-gnome.desktop", DESKTOP_FILE + "OnlyShowIn=GNOME;\n")
        sb.write("not-xfce.desktop", DESKTOP_FILE + "NotShowIn=XFCE;\n")
        sb.write("not-gnome.desktop", DESKTOP_FILE + "NotShowIn=GNOME;\n")
        sb.write("try-missing.desktop", DESKTOP_FILE + "TryExec=definitely-not-a-real-command-mv;\n")
        entries = mod.load_desktop_entries()
        names = sorted(os.path.basename(e["path"]) for e in entries)
        check("desktop environment: OnlyShowIn match kept",
              "only-xfce.desktop" in names, repr(names))
        check("desktop environment: OnlyShowIn mismatch filtered",
              "only-gnome.desktop" not in names, repr(names))
        check("desktop environment: NotShowIn match filtered",
              "not-xfce.desktop" not in names, repr(names))
        check("desktop environment: NotShowIn mismatch kept",
              "not-gnome.desktop" in names, repr(names))
        check("desktop environment: missing TryExec filtered",
              "try-missing.desktop" not in names, repr(names))

        # Environment-dependent visibility must invalidate an otherwise valid
        # cache entry instead of reusing the previous desktop's filtered list.
        os.environ["XDG_CURRENT_DESKTOP"] = "GNOME"
        entries = mod.load_desktop_entries()
        names = sorted(os.path.basename(e["path"]) for e in entries)
        check("desktop environment: cache invalidates on XDG_CURRENT_DESKTOP",
              "only-xfce.desktop" not in names and "only-gnome.desktop" in names,
              repr(names))

        # TryExec resolution depends on PATH and must invalidate the cache too.
        tryexec_bin = os.path.join(sb.tmp, "tryexec-bin")
        os.makedirs(tryexec_bin)
        tryexec_path = os.path.join(tryexec_bin, "mv-test-tryexec")
        with open(tryexec_path, "w") as fp:
            fp.write("#!/bin/sh\\n")
        os.chmod(tryexec_path, 0o755)
        sb.write("try-present.desktop", DESKTOP_FILE + "TryExec=mv-test-tryexec;\\n")
        os.environ["PATH"] = tryexec_bin
        entries = mod.load_desktop_entries()
        names = [os.path.basename(e["path"]) for e in entries]
        check("desktop environment: TryExec present on PATH kept",
              "try-present.desktop" in names, repr(names))
        os.environ["PATH"] = os.path.join(sb.tmp, "empty-path")
        entries = mod.load_desktop_entries()
        names = [os.path.basename(e["path"]) for e in entries]
        check("desktop environment: cache invalidates on PATH",
              "try-present.desktop" not in names, repr(names))
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sb.close()


def test_parse(mod):
    sb = Sandbox(mod)
    try:
        p = sb.write("ok.desktop", DESKTOP_FILE)
        e = mod._parse_desktop_file(p)
        check("parse: valid entry", e is not None)
        check("parse: name", e and e["name"] == "Test App", repr(e and e["name"]))
        check("parse: exec % stripped", e and e["exec"] == "testapp ",
              repr(e and e["exec"]))
        check("parse: icon", e and e["icon"] == "test-icon", repr(e and e["icon"]))
        check("parse: categories", e and e["categories"] == "Utility;",
              repr(e and e["categories"]))

        p = sb.write("hidden.desktop", DESKTOP_FILE + "Hidden=true\n")
        check("parse: Hidden=true skipped", mod._parse_desktop_file(p) is None)
        p = sb.write("nodisplay.desktop", DESKTOP_FILE + "NoDisplay=true\n")
        check("parse: NoDisplay=true skipped", mod._parse_desktop_file(p) is None)
        p = sb.write("noname.desktop", "[Desktop Entry]\nExec=foo %U\n")
        check("parse: missing Name rejected", mod._parse_desktop_file(p) is None)
        p = sb.write("noexec.desktop", "[Desktop Entry]\nName=Foo\n")
        check("parse: missing Exec rejected", mod._parse_desktop_file(p) is None)
        p = sb.write("dbus.desktop", "[Desktop Entry]\nName=DBus App\nDBusActivatable=true\n")
        dbus_entry = mod._parse_desktop_file(p)
        check("parse: DBusActivatable without Exec kept", dbus_entry is not None, repr(dbus_entry))
        check("parse: DBusActivatable flag retained", dbus_entry and dbus_entry["dbus_activatable"] is True,
              repr(dbus_entry))
        check("parse: DBusActivatable without Exec has empty exec", dbus_entry and dbus_entry["exec"] == "",
              repr(dbus_entry))
        p = sb.write("dbus-false.desktop", "[Desktop Entry]\nName=DBus False\nDBusActivatable=false\n")
        check("parse: DBusActivatable=false still requires Exec", mod._parse_desktop_file(p) is None)
        check("parse: missing file -> None",
              mod._parse_desktop_file(os.path.join(sb.desktop, "nope.desktop")) is None)
    finally:
        sb.close()


def test_fingerprint(mod):
    sb = Sandbox(mod)
    try:
        fp0, c0 = mod._fingerprint()
        check("fingerprint: empty dir count 0", c0 == 0, f"count={c0}")
        sb.write("a.desktop", DESKTOP_FILE)
        fp1, c1 = mod._fingerprint()
        check("fingerprint: add changes key", fp1 != fp0)
        check("fingerprint: add changes count", c1 == 1, f"count={c1}")
        sb.write("b.desktop", DESKTOP_FILE_2)
        fp2, c2 = mod._fingerprint()
        check("fingerprint: second add changes key", fp2 != fp1)
        check("fingerprint: count 2", c2 == 2, f"count={c2}")
        # modify in place (dir mtime unchanged on most filesystems within the
        # same tick, so the file mtime_ns term must catch it)
        p = os.path.join(sb.desktop, "a.desktop")
        time.sleep(0.01)
        with open(p, "w") as f:
            f.write(DESKTOP_FILE_2.replace("Other App", "Renamed App"))
        fp3, c3 = mod._fingerprint()
        check("fingerprint: modify changes key", fp3 != fp2)
        check("fingerprint: modify keeps count", c3 == 2, f"count={c3}")
        os.remove(p)
        fp4, c4 = mod._fingerprint()
        check("fingerprint: remove changes key", fp4 != fp3)
        check("fingerprint: remove changes count", c4 == 1, f"count={c4}")
    finally:
        sb.close()


def test_recursive_fingerprint_invalidation(mod):
    """Nested desktop entries must participate in cache invalidation."""
    sb = Sandbox(mod)
    try:
        nested = os.path.join(sb.desktop, "nested")
        os.makedirs(nested)
        path = os.path.join(nested, "nested.desktop")
        with open(path, "w") as f:
            f.write(DESKTOP_FILE)
        fp1, count1 = mod._fingerprint()
        check("recursive fingerprint: nested file counted", count1 == 1)
        os.remove(path)
        fp2, count2 = mod._fingerprint()
        check("recursive fingerprint: nested removal changes key", fp2 != fp1)
        check("recursive fingerprint: nested removal changes count", count2 == 0)
        with open(path, "w") as f:
            f.write(DESKTOP_FILE)
        fp3, count3 = mod._fingerprint()
        check("recursive fingerprint: nested re-add changes key", fp3 != fp2)
        check("recursive fingerprint: nested re-add counted", count3 == 1)
    finally:
        sb.close()


def test_cache_writer_uses_unique_atomic_tempfiles(mod):
    """Cache writes must not share a fixed .tmp path between concurrent writers."""
    source = open(MOD_PATH).read()
    check("cache writer: tempfile module imported", "import tempfile" in source)
    check("cache writer: unique mkstemp", "tempfile.mkstemp" in source)
    check("cache writer: fsync before replace", "os.fsync(cache_file.fileno())" in source)
    check("cache writer: atomic replace", "os.replace(tmp_path, path)" in source)
    check("cache writer: cleanup on failure", "os.unlink(tmp_path)" in source)
    check("cache writer: no fixed tmp path", 'tmp = path + ".tmp"' not in source)

def test_cache_hit_skips_reads(mod):
    sb = Sandbox(mod)
    try:
        sb.write("a.desktop", DESKTOP_FILE)
        sb.write("b.desktop", DESKTOP_FILE_2)
        entries = mod.load_desktop_entries()
        check("cache: first call parses", len(entries) == 2, f"n={len(entries)}")
        check("cache: cache file written", os.path.isfile(sb.cache_path()))

        real_open = builtins.open
        reads = []

        def tracking_open(path, *a, **k):
            if str(path).endswith(".desktop"):
                reads.append(str(path))
            return real_open(path, *a, **k)

        builtins.open = tracking_open
        try:
            entries2 = mod.load_desktop_entries()
        finally:
            builtins.open = real_open
        check("cache: hit skips all .desktop reads", not reads, f"reads={reads}")
        check("cache: hit returns same entries", entries2 == entries)
    finally:
        sb.close()


def test_locale_invalidation(mod):
    """Localized desktop names must refresh when the active locale changes."""
    sb = Sandbox(mod)
    old = {key: os.environ.get(key) for key in ("LANGUAGE", "LC_MESSAGES", "LANG")}
    try:
        for key in old:
            os.environ.pop(key, None)
        sb.write("localized.desktop", """[Desktop Entry]
Name=English App
Name[ru]=Русское приложение
Name[en]=English App
Exec=testapp
""")
        os.environ["LANGUAGE"] = "en"
        entries = mod.load_desktop_entries()
        check("locale: English name cached", entries[0]["name"] == "English App",
              repr(entries))
        os.environ["LANGUAGE"] = "ru"
        entries = mod.load_desktop_entries()
        check("locale: change invalidates cache",
              entries[0]["name"] == "Русское приложение", repr(entries))
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sb.close()


def test_fingerprint_tracks_replacement_metadata(mod):
    """File replacement metadata must invalidate the desktop cache."""
    source = open(MOD_PATH).read()
    check("fingerprint: ctime tracked", "st.st_ctime_ns" in source)
    check("fingerprint: inode tracked", "st.st_ino" in source)


def test_cache_invalidation(mod):
    sb = Sandbox(mod)
    try:
        sb.write("a.desktop", DESKTOP_FILE)
        entries = mod.load_desktop_entries()
        check("invalidation: baseline 1 entry", len(entries) == 1)
        # modify content -> must re-parse
        p = os.path.join(sb.desktop, "a.desktop")
        time.sleep(0.01)
        with open(p, "w") as f:
            f.write(DESKTOP_FILE_2)
        entries = mod.load_desktop_entries()
        check("invalidation: modify re-parses",
              len(entries) == 1 and entries[0]["name"] == "Other App",
              repr(entries))
        # add file -> must appear
        sb.write("b.desktop", DESKTOP_FILE)
        entries = mod.load_desktop_entries()
        check("invalidation: add re-parses", len(entries) == 2, f"n={len(entries)}")
        # remove file -> must disappear
        os.remove(os.path.join(sb.desktop, "b.desktop"))
        entries = mod.load_desktop_entries()
        check("invalidation: remove re-parses", len(entries) == 1, f"n={len(entries)}")
    finally:
        sb.close()


def test_missing_cache_is_not_quarantined(mod):
    """A first-run cache miss must not create a fake corrupt-cache artifact."""
    sb = Sandbox(mod)
    try:
        cache = sb.cache_path()
        check("missing: cache initially absent", not os.path.exists(cache))
        data = mod._read_json_safe(cache)
        check("missing: returns cache miss", data is None)
        parent = os.path.dirname(cache)
        leftovers = [f for f in os.listdir(parent)] if os.path.isdir(parent) else []
        check("missing: no quarantine artifact", leftovers == [], repr(leftovers))
    finally:
        sb.close()


def test_corrupt_cache(mod):
    sb = Sandbox(mod)
    try:
        sb.write("a.desktop", DESKTOP_FILE)
        mod.load_desktop_entries()
        cache = sb.cache_path()
        check("corrupt: cache exists", os.path.isfile(cache))
        with open(cache, "w") as f:
            f.write("{not valid json")
        entries = mod.load_desktop_entries()
        check("corrupt: miss re-parses", len(entries) == 1, f"n={len(entries)}")
        check("corrupt: cache rebuilt valid", os.path.isfile(cache))
        leftovers = [f for f in os.listdir(os.path.dirname(cache))
                     if f.startswith("desktop-entries.json.corrupt-")]
        check("corrupt: corrupt file quarantined", len(leftovers) == 1,
              f"leftovers={leftovers}")
        # quarantined file must not be silently lost: it still exists
        check("corrupt: quarantine preserved",
              os.path.isfile(os.path.join(os.path.dirname(cache), leftovers[0])))
        # and the rebuilt cache works as a hit
        entries2 = mod.load_desktop_entries()
        check("corrupt: rebuilt cache hits", entries2 == entries)
    finally:
        sb.close()


def test_integration(mod):
    if BIN_DIR not in sys.path:
        sys.path.insert(0, BIN_DIR)
    # The apps do `import mv_desktop_cache`; register the test's module
    # object in sys.modules so the Sandbox patch applies to the apps too.
    sys.modules["mv_desktop_cache"] = mod
    sb = Sandbox(mod)
    try:
        sb.write("aaa.desktop", DESKTOP_FILE)
        sb.write("bbb.desktop", DESKTOP_FILE_2)
        # duplicate stem in a second dir must NOT happen (single dir here),
        # but Hidden filtering must apply through the apps
        sb.write("hidden.desktop", DESKTOP_FILE + "Hidden=true\n")

        sb.write("dbus.desktop", """[Desktop Entry]
Name=DBus App
DBusActivatable=true
Icon=applications-system
""")

        cached_entries = mod.load_desktop_entries()
        dbus_entries = [e for e in cached_entries if e.get("desktop_id") == "dbus.desktop"]
        check("integration: DBus-activatable entry reaches cache", len(dbus_entries) == 1,
              repr(dbus_entries))
        check("integration: DBus-activatable flag survives cache",
              dbus_entries and dbus_entries[0].get("dbus_activatable") is True,
              repr(dbus_entries))
        check("integration: DBus-activatable entry keeps empty Exec",
              dbus_entries and dbus_entries[0].get("exec") == "", repr(dbus_entries))

        lp = load_app("mv-launchpad")
        apps = lp.load_desktop_apps()
        names = sorted(a["name"] for a in apps)
        check("launchpad: apps via cache", names == ["Other App", "Test App"],
              f"names={names}")
        # hidden.desktop (Name=Test App) must be filtered: exactly one
        # "Test App" entry remains, from aaa.desktop
        check("launchpad: hidden filtered",
              sum(1 for a in apps if a["name"] == "Test App") == 1,
              repr([a for a in apps if a["name"] == "Test App"]))
        check("launchpad: sorted by name",
              [a["name"] for a in apps] == names)
        check("launchpad: canonical desktop IDs",
              {a["id"] for a in apps} == {"aaa.desktop", "bbb.desktop"},
              repr({a["id"] for a in apps}))

        sp = load_app("mv-spotlight")
        sapps = sp.load_desktop_apps()
        check("spotlight: apps via cache",
              sorted(a["name"] for a in sapps) == ["Other App", "Test App"],
              repr(sapps))
        check("spotlight: source field",
              all(a["source"] == "app" for a in sapps))
        check("spotlight: categories kept",
              {a["categories"] for a in sapps} == {"Utility;", "Network;WebBrowser;"},
              repr({a["categories"] for a in sapps}))

        # dedup: same stem in a later dir is skipped (user overrides system)
        mod.desktop_dirs = lambda: [sb.desktop, sb.desktop]
        apps = lp.load_desktop_apps()
        check("launchpad: dedup by stem", len(apps) == 2, f"n={len(apps)}")
    finally:
        sb.close()


def main():
    mod = load_module("mv_desktop_cache", MOD_PATH)
    test_xdg_application_paths(mod)
    test_parse(mod)
    test_environment_filters(mod)
    test_recursive_desktop_ids(mod)
    test_fingerprint(mod)
    test_cache_writer_uses_unique_atomic_tempfiles(mod)
    test_recursive_fingerprint_invalidation(mod)
    test_cache_hit_skips_reads(mod)
    test_cache_invalidation(mod)
    test_locale_invalidation(mod)
    test_missing_cache_is_not_quarantined(mod)
    test_corrupt_cache(mod)
    test_integration(mod)
    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        for name, detail in FAILURES:
            print(f"  FAIL: {name} {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
