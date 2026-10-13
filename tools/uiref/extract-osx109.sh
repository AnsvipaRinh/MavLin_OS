#!/usr/bin/env bash
# extract-osx109.sh - get a readable OS X 10.9 Mavericks system tree on Linux,
# then run the UI ground-truth extractors over it. No macOS, no VM, no GUI.
#
# Inputs:  a "OS X Mavericks Install DVD.dmg" (App Store image) or an already
#          downloaded InstallESD.dmg.
# Outputs: a directory tree with the real /System of 10.9 + docs/UI_REFERENCE/data/*
#
# Why this route: the install DVD's visible volume is only a stub (1185 files);
# the actual system payload is Essentials.pkg inside InstallESD.dmg. Reading it
# offline is both faster and far more reproducible than driving an installer UI.
#
# Usage:
#   extract-osx109.sh <installer.dmg|InstallESD.dmg> <workdir>
set -euo pipefail

IN="${1:?usage: extract-osx109.sh <installer.dmg|InstallESD.dmg> <workdir>}"
WORK="${2:?workdir}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
TOOLS="$REPO/tools/uiref"
mkdir -p "$WORK"

need() { command -v "$1" >/dev/null || { echo "missing tool: $1" >&2; exit 1; }; }
need 7z; need bsdtar

ESD="$WORK/InstallESD.dmg"
if [[ "$IN" == *InstallESD.dmg ]]; then
  cp -f "$IN" "$ESD"
else
  # 1. pull InstallESD.dmg out of the installer volume inside the DVD image
  tmp="$WORK/stub"
  rm -rf "$tmp"; mkdir -p "$tmp"
  dmg2img -i "$IN" -o "$WORK/installer.raw"
  7z e "$WORK/installer.raw" -o"$tmp" "*/SharedSupport/InstallESD.dmg" -y >/dev/null
  mv "$tmp"/*.dmg "$ESD"
  rm -rf "$tmp" "$WORK/installer.raw"
fi

# 2. HFSX payload of the ESD -> directory tree (no intermediate copies)
mkdir -p "$WORK/esd"
7z x "$ESD" -o"$WORK/esd" -y >/dev/null
ROOT="$WORK/esd/OS X Install ESD"

# 3. Essentials.pkg (flat xar) -> Payload (bzip2 cpio) -> real /System tree
if [[ ! -d "$WORK/sys/System" ]]; then
  mkdir -p "$WORK/esdpkg" "$WORK/sys"
  bsdtar -xf "$ROOT/Packages/Essentials.pkg" -C "$WORK/esdpkg"
  bsdtar -xf "$WORK/esdpkg/Payload" -C "$WORK/sys"
fi
# Packages are no longer needed once the tree is out.
rm -f "$WORK/esdpkg/Payload" "$WORK/esdpkg/Bom"

# 4. ground truth out of the tree
python3 "$TOOLS/extract_nibs.py"    nibs    --volume "$WORK/sys" \
        --out "$REPO/docs/UI_REFERENCE/data/components.json"
python3 "$TOOLS/extract_nibs.py"    assets  --volume "$WORK/sys" \
        --out "$WORK/skin" --jobs 4
python3 "$TOOLS/extract_nibs.py"    strings --volume "$WORK/sys" \
        --out "$REPO/docs/UI_REFERENCE/data/terminology.json"

echo "system tree: $WORK/sys"
echo "skin extracts: $WORK/skin"