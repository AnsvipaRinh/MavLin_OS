#!/usr/bin/env python3
"""Gate: every Gtk.MessageDialog construction site in mv-* app sources must
adopt the theme's `message` style class, so the Mavericks alert layout
(dialog.message in mavericks-theme _windows.scss) actually applies.

GTK does not add a "message" class to GtkMessageDialog windows on its own;
each site must call get_style_context().add_class("message"). This gate
parses all Python mv-* sources under packages/mavericks-apps bin/, finds
`<var> = Gtk.MessageDialog(` assignments (single- or multi-line calls), and
requires the matching adopt line within 3 lines after the constructor call.

Pure static analysis — no gi/GTK needed, runs anywhere.

Usage:
  python3 scripts/test-message-dialog-adoption.py
Exit 0 = all sites adopted; exit 1 = orphan dialogs found.
"""
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_BIN = os.path.join(REPO, "packages", "mavericks-apps", "src",
                        "mavericks-apps", "bin")

SITE_RE = re.compile(r"^(\s*)(\w+) = Gtk\.MessageDialog\(.*\)*\s*$")


def scan_file(path):
    """Return list of (lineno, varname) for un-adopted dialog sites."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return []  # shell/C/desktop payload, not python
    if "Gtk.MessageDialog" not in text:
        return []
    lines = text.split("\n")
    orphans = []
    i = 0
    while i < len(lines):
        m = SITE_RE.match(lines[i])
        if not m or "Gtk.MessageDialog" not in lines[i]:
            i += 1
            continue
        indent, var = m.group(1), m.group(2)
        depth = lines[i].count("(") - lines[i].count(")")
        j = i + 1
        while j < len(lines) and depth > 0:
            depth += lines[j].count("(") - lines[j].count(")")
            j += 1
        if depth > 0:  # unbalanced parens — malformed, flag it
            orphans.append((i + 1, var + " (unbalanced constructor)"))
            i += 1
            continue
        adopt = '%s%s.get_style_context().add_class("message")' % (indent, var)
        tail = "\n".join(lines[j:min(j + 3, len(lines))])
        if adopt not in tail:
            orphans.append((i + 1, var))
        i = j
    return orphans


def main():
    files = sorted(glob.glob(os.path.join(APPS_BIN, "mv-*")))
    total_sites = 0
    failures = []
    counted_orphans = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        n_sites = None  # counted below via the same walk used for adoption
        # count sites properly via the same walk used for adoption
        lines = text.split("\n")
        cnt = 0
        i = 0
        while i < len(lines):
            m = SITE_RE.match(lines[i])
            if not m or "Gtk.MessageDialog" not in lines[i]:
                i += 1
                continue
            cnt += 1
            depth = lines[i].count("(") - lines[i].count(")")
            j = i + 1
            while j < len(lines) and depth > 0:
                depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            i = max(j, i + 1)
        total_sites += cnt
        for lineno, var in scan_file(path):
            failures.append("%s:%d: dialog '%s' missing add_class(\"message\")"
                            % (os.path.relpath(path, REPO), lineno, var))
            counted_orphans += 1
    ok = not failures
    print(("ok" if ok else "FAIL") + " - %d MessageDialog sites, %d adopted, "
          "%d orphan(s)" % (total_sites, total_sites - counted_orphans,
                            counted_orphans))
    for f in failures:
        print("  " + f)
    print("\n%d checks, %d failures" % (1, 0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
