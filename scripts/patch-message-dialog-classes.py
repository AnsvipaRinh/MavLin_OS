#!/usr/bin/env python3
"""One-shot patcher: attach the theme's `message` style class to every
Gtk.MessageDialog construction site in mv-* app sources.

Background: the mavericks-theme defines alert-layout styling under
`dialog.message` (see gtk-3.0/_windows.scss). GTK does NOT add a "message"
class to GtkMessageDialog windows automatically, so the styling is inert
until each dialog opts in via get_style_context().add_class("message").

The transformation inserts two statements immediately after each
`<var> = Gtk.MessageDialog(` constructor call:

    <var>.get_style_context().add_class("message")
    # message-dialog alert layout lives in mavericks-theme dialog.message
    <var>.set_default_size(420, -1)

Indentation of the inserted lines matches the assignment line. The script
is idempotent (skips sites already carrying add_class("message")) and
verifies every touched file still compiles; on any failure the file is
restored byte-for-byte from the in-memory original.

Usage:
  python3 scripts/patch-message-dialog-classes.py --dry-run
  python3 scripts/patch-message-dialog-classes.py
Exit 0 = all good (or nothing to do with --dry-run).
"""
import glob
import os
import py_compile
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_BIN = os.path.join(REPO, "packages", "mavericks-apps", "src",
                        "mavericks-apps", "bin")

# `<var> = Gtk.MessageDialog(...` — assignment opening a constructor call.
# Handles both the single-line form (`d = Gtk.MessageDialog(...)`) and the
# multi-line form (trailing open paren). Depth scan finds the real end.
SITE_RE = re.compile(r"^(\s*)(\w+) = Gtk\.MessageDialog\(.*\)*\s*$")
ADOPTED_MARK = 'add_class("message")'


def patch_source(text):
    """Return (new_text, n_sites_patched)."""
    lines = text.split("\n")
    out = []
    patched = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        m = SITE_RE.match(line)
        if not m or "Gtk.MessageDialog" not in line:
            out.append(line)
            i += 1
            continue
        indent, var = m.group(1), m.group(2)
        # scan forward to the end of this constructor call: the closing
        # paren that returns the bracket depth to zero.
        depth = line.count("(") - line.count(")")
        j = i + 1
        while j < len(lines) and depth > 0:
            depth += lines[j].count("(") - lines[j].count(")")
            j += 1
        if depth > 0:
            # unbalanced — do not touch (malformed / continuation oddity)
            out.append(line)
            i += 1
            continue
        block = "\n".join(lines[i:j])
        adopt = '%s%s.get_style_context().add_class("message")' % (indent, var)
        if adopt in block:
            out.extend(lines[i:j])
            i = j
            continue
        # already-adopted site whose add_class sits below the constructor
        # call (the normal patched state): copy through without re-inserting.
        tail = "\n".join(lines[j:min(j + 3, len(lines))])
        if adopt in tail:
            out.extend(lines[i:j])
            i = j
            continue
        out.extend(lines[i:j])
        out.append('%s%s.get_style_context().add_class("message")'
                   % (indent, var))
        out.append("%s# message-dialog alert layout lives in "
                   "mavericks-theme dialog.message" % indent)
        out.append("%s%s.set_default_size(420, -1)" % (indent, var))
        patched += 1
        i = j
    return "\n".join(out), patched


def main():
    dry = "--dry-run" in sys.argv
    files = sorted(glob.glob(os.path.join(APPS_BIN, "mv-*")))
    total_sites = 0
    touched_files = []
    failures = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                orig = f.read()
        except (UnicodeDecodeError, IsADirectoryError):
            continue  # desktop files / dirs / non-python payloads
        if "Gtk.MessageDialog" not in orig:
            continue
        new, n = patch_source(orig)
        if n == 0:
            continue
        total_sites += n
        touched_files.append((path, n))
        if dry:
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            with open(path, "w", encoding="utf-8") as f:
                f.write(orig)
            failures.append("%s: %s" % (os.path.basename(path), e))
    mode = "DRY-RUN" if dry else "PATCHED"
    for path, n in touched_files:
        print("%s %s: %d site(s)" % (mode, os.path.relpath(path, REPO), n))
    print("total sites: %d in %d file(s)" % (total_sites, len(touched_files)))
    if failures:
        print("COMPILE FAILURES (reverted):")
        for f in failures:
            print("  " + f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
