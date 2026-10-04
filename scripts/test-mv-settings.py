#!/usr/bin/env python3
"""Headless tests for mv-settings (System Settings launcher).

Previously had ZERO test coverage. Since the 2026-10-05 refactor the pure
sections (PAGES table, page_is_available, filter_pages) import without gi;
this suite blocks `gi` to prove that and pins the table invariants:
unique labels, valid row shape, availability logic, search semantics.
Icon-name existence is checked against our icon theme only when the theme
source tree is present (it is not packaged as a runtime dep here).

Usage: python3 scripts/test-mv-settings.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


class _BlockGi:
    def find_spec(self, name, path=None, target=None):
        if name == "gi" or name.startswith("gi."):
            raise ImportError("blocked by test: %s" % name)
        return None


def load(mod_name, filename, block_gi=True):
    if block_gi:
        sys.meta_path.insert(0, _BlockGi())
    try:
        path = os.path.join(BIN, filename)
        loader = importlib.machinery.SourceFileLoader(mod_name, path)
        spec = importlib.util.spec_from_loader(mod_name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        if block_gi:
            sys.meta_path.remove(sys.meta_path[0])


def main():
    try:
        m = load("mv_settings", "mv-settings")
        ok("mv-settings imports headless (gi blocked)")
    except Exception as e:
        bad("mv-settings imports headless (gi blocked)", repr(e))
        print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
        return 1

    # --- PAGES table contract ---
    rows_ok = all(len(r) == 3 and isinstance(r[0], str) and isinstance(r[1], str)
                  and (r[2] is None or (isinstance(r[2], list) and r[2]
                      and all(isinstance(x, str) for x in r[2])))
                  for r in m.PAGES)
    check("PAGES: (label, icon, argv|None) shape", rows_ok)
    labels = [r[0] for r in m.PAGES]
    check("PAGES: labels unique", len(labels) == len(set(labels)),
          "dupes=%s" % [l for l in set(labels) if labels.count(l) > 1])
    check("PAGES: non-trivial table", len(m.PAGES) >= 15, str(len(m.PAGES)))

    # The About page must chain to mv-about (the app we tested separately).
    about = [r for r in m.PAGES if r[0] == "About"]
    check("PAGES: About -> mv-about", bool(about) and about[0][2] == ["mv-about"],
          str(about))

    # --- page_is_available ---
    check("available: None cmd -> False", m.page_is_available(None) is False)
    check("available: real tool -> True", m.page_is_available(["sh"]) is True)
    check("available: fake tool -> False",
          m.page_is_available(["definitely-not-a-real-binary-42"]) is False)
    check("available: empty list -> False", m.page_is_available([]) is False)

    # --- filter_pages search semantics (case-insensitive substring on label) ---
    check("filter: empty query -> all pages", len(m.filter_pages("")) == len(m.PAGES))
    res = m.filter_pages("network")
    check("filter: 'network' matches Network exactly",
          [r[0] for r in res] == ["Network"], str(res))
    res = m.filter_pages("dis")
    check("filter: case-insensitive substring ('dis' -> Displays)",
          set(r[0] for r in res) >= {"Displays"}, str(res))
    check("filter: nonsense -> empty", m.filter_pages("zzq-no-such-page") == [])

    # --- GUI factory stays lazy ---
    try:
        m.build_settings_class()
        bad("build_settings_class requires gi (lazy)", "worked without gi?!")
    except ImportError:
        ok("build_settings_class requires gi (lazy)")

    # --- icon-name audit vs our Mavericks theme source (hard assertion) ---
    # PAGES must only use icon names shipped by packages/mavericks-theme, so
    # the Settings grid never renders broken/missing images on the ISO.
    icons_root = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/icons")
    if os.path.isdir(icons_root):
        theme_icons = set()
        for _dirpath, _dirs, files in os.walk(icons_root):
            for f in files:
                if f.endswith(".svg"):
                    theme_icons.add(f[:-4])
        missing = sorted({r[1] for r in m.PAGES} - theme_icons)
        check("PAGES: every icon exists in Mavericks theme", not missing,
              "missing=%s" % missing)
    else:
        print("skip - icon-name audit (theme source not found at %s)" % icons_root)

    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
