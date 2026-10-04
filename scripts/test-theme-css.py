#!/usr/bin/env python3
"""Headless tests for mavericks-theme GTK3 CSS validity.

Guards against GTK4/dart-sass syntax contamination in the theme's SCSS
sources and compiled gtk.css (regression gate for the abee05b..0.61
@use passthrough bug: libsass cannot parse `@use "x" as *;` and emitted
the lines verbatim, producing ~90 Gtk-WARNING parse errors per app
start).

Checks:
- SCSS sources contain no dart-sass @use / GTK4-only constructs
  (backdrop-filter, prefers-contrast, prefers-reduced-motion,
  prefers-color-scheme, color-mix(), light-dark(), accent-color,
  gtk-icon-palette, font-feature-settings, font-variation-settings)
- sassc compiles gtk-3.0 and gtk-3.20 without error (sassc binary;
  falls back to libsass-python when sassc is absent; skipped only if
  neither is available)
- Compiled CSS contains zero @use/@import lines
- Gtk.CssProvider loads compiled CSS with zero parsing errors
  (skipped if GTK3 introspection absent)

Usage: python3 scripts/test-theme-css.py
Exit 0 = all checks passed."""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme")

FORBIDDEN = [
    "@use ", "backdrop-filter", "prefers-contrast",
    "prefers-reduced-motion", "prefers-color-scheme", "color-mix(",
    "light-dark(", "accent-color", "gtk-icon-palette",
    "font-feature-settings", "font-variation-settings",
    ":focus-visible", ":insensitive", ":horizontal", ":vertical",
    "::selection", "::placeholder", "@media ", "-gtk-icon-transform",
    "gtkalpha(", "@font-face",
]

TARGETS = ["gtk-3.0", "gtk-3.20"]


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def scan_sources():
    import re
    hits = []
    for target in TARGETS:
        d = os.path.join(THEME, target)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".scss"):
                continue
            path = os.path.join(d, fn)
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    code = re.sub(r"/\*.*?\*/", "", line)
                    for pat in FORBIDDEN:
                        if pat in code:
                            hits.append("%s:%d: %s" % (path, i, pat))
    return hits


def compile_target(target, out_path):
    src = os.path.join(THEME, target, "gtk.scss")
    if shutil.which("sassc"):
        r = subprocess.run(
            ["sassc", "-t", "compressed", src, out_path],
            capture_output=True, text=True)
        return r.returncode, (r.stderr.strip()[:200] if r.returncode else "")
    # libsass-python fallback (same engine family as sassc; keeps the
    # compile gate active in environments without the sassc binary)
    try:
        import sass
    except ImportError:
        return None, ""
    try:
        css = sass.compile(filename=src)
    except Exception as e:  # CompileError on SCSS syntax problems
        return 1, str(e)[:200]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(css)
    return 0, ""


def parse_with_gtk(css_path):
    """Returns (raised_error_or_None, signal_error_count)."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    errors = []

    def on_err(provider, section, err):
        errors.append(err.message)

    with open(css_path, "rb") as f:
        data = f.read()
    provider = Gtk.CssProvider()
    provider.connect("parsing-error", on_err)
    try:
        provider.load_from_data(data)
        return None, len(errors)
    except Exception as e:  # GLib.GError on hard parse failure
        return str(e), len(errors)


def main():
    sassc = shutil.which("sassc")
    have_libsass = False
    if not sassc:
        try:
            import sass  # noqa: F401
            have_libsass = True
        except ImportError:
            pass
        if not have_libsass:
            print("SKIP: sassc/libsass not available (compile gate disabled)")

    hits = scan_sources()
    check("scss sources free of @use/GTK4 constructs", not hits,
          "; ".join(hits[:5]))

    compiled = {}
    if sassc or have_libsass:
        for target in TARGETS:
            out = os.path.join(tempfile.mkdtemp(), target + ".css")
            rc, err = compile_target(target, out)
            check("sass compiles %s" % target, rc == 0, err)
            if rc == 0:
                compiled[target] = out

    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
        have_gtk = True
    except Exception:
        have_gtk = False
        print("SKIP: GTK3 introspection not available (parse gate disabled)")

    for target in TARGETS:
        path = compiled.get(target)
        if not path:
            continue
        with open(path, encoding="utf-8") as f:
            css = f.read()
        check("%s: zero @use/@import in compiled css" % target,
              "@use" not in css and "@import" not in css)
        if have_gtk:
            raised, n_err = parse_with_gtk(path)
            check("%s: Gtk.CssProvider loads without error" % target,
                  raised is None, (raised or "")[:200])
            check("%s: zero parsing-error signals" % target, n_err == 0,
                  "%d errors" % n_err)

    print("\n%d checks, %d failures" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
