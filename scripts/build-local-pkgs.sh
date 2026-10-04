#!/usr/bin/env bash
# build-local-pkgs.sh — build repo-local packages into a pacman repo for the ISO.
# Usage: ./scripts/build-local-pkgs.sh [outdir]
# Requires: base-devel, pacman. Run on Arch (root not required for makepkg).
set -euo pipefail
OUT="${1:-/tmp/mavericks-repo}"
mkdir -p "$OUT"
# Default set: packages consumed by the ISO / installed system.
# epiphany-mavericks-theme is DEFERRED (Firefox ESR is the browser) — build only with --all.
PKGS="mavericks-apps mavericks-theme macbook12-audio-driver vala-panel-appmenu"
[[ "${2:-}" == "--all" ]] && PKGS="$PKGS epiphany-mavericks-theme"
for pkg in $PKGS; do
  dir="packages/$pkg"
  [[ -f "$dir/PKGBUILD" ]] || { echo "skip $pkg (no PKGBUILD)"; continue; }
  echo "=== building $pkg ==="
  # -f: rebuilds are idempotent (re-run safe). WARNING: never rm -rf
  # packages/*/src — for these packages it holds TRACKED sources that
  # share makepkg's default $srcdir name, not just build residue.
  (cd "$dir" && makepkg -sf --noconfirm --skipchecksums 2>/dev/null || makepkg -sf --noconfirm)
  cp "$dir"/*.pkg.tar.zst "$OUT/" 2>/dev/null || true
done
(cd "$OUT" && repo-add mavericks.db.tar.gz *.pkg.tar.zst)
echo "Repo at $OUT. Add to archiso pacman.conf:"
echo "  [mavericks]"
echo "  SigLevel = Optional TrustAll"
echo "  Server = file://$OUT"
