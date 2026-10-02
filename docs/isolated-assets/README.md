# Isolated assets — provenance note

**Status (2026-10-03, user decision D1):** this directory previously
held three Apple-derived SVG originals
(`help-about.svg`, `preferences-desktop-display.svg`,
`preferences-desktop-mouse.svg`) that were isolated from the
`mavericks-theme` icon set by the OS-4a license audit (commit `522ab98`).

They have been **removed from the public tree** and must **not be
published**: they contain explicit Apple logo vector paths and
"Mac OS X 10.9 Mavericks" text (Apple copyright/trademark material,
classified NON-redistributable in `docs/LICENSES.md` §6).

**What the UI uses instead:** the theme ships purpose-built generic
replacement icons at the same icon names
(`packages/mavericks-theme/src/mavericks-theme/icons/{scalable,16x16,
22x22,24x24,32x32,48x48,64x64,128x128,256x256,512x512}/apps/`)
since commit `522ab98` — original skeuomorphic designs, no Apple
artwork. No functional dependency on the removed originals exists.

**History:** pre-`522ab98` commits still contain the Apple-derived
versions (both the theme-tree paths and this directory). The
publication history rewrite therefore includes a targeted purge:

- `--path docs/isolated-assets/ --invert-paths` (this directory's
  contents removed from all history),
- `--replace-text` neutralization of the Apple SVG vector strings in
  old theme-tree SVG versions,
- `--strip-blobs-with-id` of the 54 pre-`522ab98` PNG blob IDs
  (rasterizations of the Apple-derived SVGs).

Exact rules and the dry-run verification procedure:
`scripts/contrib/publication-rewrite/` (see `docs/RELEASE_READINESS.md`
§3.1). Do not re-add Apple-derived assets under any path.
