#!/usr/bin/env python3
"""Regenerate scripts/contrib/publication-rewrite/03-apple-derived-blob-ids.txt

Computes the exact set of pre-522ab98 (Apple-derived) blob versions of the
three formerly-Apple-derived theme icons (3 scalable SVGs + 27 raster PNGs)
and verifies, for every path, that:

  * the path has exactly TWO historical blob versions
    (one Apple-derived, one generic replacement);
  * the Apple-derived blob differs (sha256) from the generic blob at 522ab98;
  * the generic blob is NOT in the output list (it must survive the rewrite).

Run from the repository root. Exits non-zero on any surprise (a path with
more or fewer than 2 versions, an Apple blob identical to its generic
replacement, or an Apple SVG blob lacking Apple markers).
"""

import hashlib
import subprocess
import sys

BASE = "packages/mavericks-theme/src/mavericks-theme/icons"
SIZES = ["scalable", "16x16", "22x22", "24x24", "32x32",
         "48x48", "64x64", "128x128", "256x256", "512x512"]
NAMES = ["help-about", "preferences-desktop-display", "preferences-desktop-mouse"]
REPLACEMENT_COMMIT = "522ab98"
OUT = "scripts/contrib/publication-rewrite/03-apple-derived-blob-ids.txt"


def shb(*args):
    return subprocess.run(args, capture_output=True).stdout


def main():
    paths = [f"{BASE}/{s}/apps/{n}{'.svg' if s == 'scalable' else '.png'}"
             for s in SIZES for n in NAMES]
    apple_ids = {}
    for p in paths:
        commits = [c for c in shb("git", "log", "--all", "--format=%H",
                                  "--reverse", "--", p).decode().splitlines() if c]
        blobs = {shb("git", "rev-parse", f"{c}:{p}").decode().strip()
                 for c in commits}
        blobs.discard("")
        generic = shb("git", "rev-parse", f"{REPLACEMENT_COMMIT}:{p}").decode().strip()
        pre = blobs - {generic}
        if len(pre) != 1:
            sys.exit(f"UNEXPECTED: {p} has {len(pre)} pre-{REPLACEMENT_COMMIT} "
                     f"versions (expected exactly 1): {pre}")
        apple_id = pre.pop()
        if hashlib.sha256(shb("git", "cat-file", "blob", apple_id)).hexdigest() == \
           hashlib.sha256(shb("git", "cat-file", "blob", generic)).hexdigest():
            sys.exit(f"UNEXPECTED: Apple-derived blob for {p} is identical to the "
                     f"generic replacement — list generation aborted")
        if p.endswith(".svg"):
            content = shb("git", "cat-file", "blob", apple_id).decode("utf-8", "replace")
            if "Apple" not in content and "Mac OS X" not in content:
                sys.exit(f"UNEXPECTED: {p} pre-{REPLACEMENT_COMMIT} SVG lacks "
                         f"Apple markers — refusing to purge a possibly-wrong blob")
        apple_ids[p] = apple_id

    ids = sorted(apple_ids.values())
    header = (
        "# git-filter-repo --strip-blobs-with-id target list\n"
        "# All pre-522ab98 (Apple-derived) blob versions of the 3 formerly-\n"
        "# Apple-derived theme icons: 3 scalable SVGs + 27 raster PNGs.\n"
        "# Each path has exactly 2 historical versions: this Apple-derived\n"
        "# blob (added with the theme) and the generic replacement (commit\n"
        f"# {REPLACEMENT_COMMIT}, which survives — it is NOT in this list).\n"
        "# Regenerate with: python3 scripts/contrib/publication-rewrite/generate-lists.py\n"
        f"# {len(ids)} unique blobs\n"
    )
    with open(OUT, "w") as f:
        f.write(header)
        for b in ids:
            f.write(b + "\n")
    print(f"OK: {len(paths)} paths, {len(ids)} unique Apple-derived blobs -> {OUT}")


if __name__ == "__main__":
    main()
