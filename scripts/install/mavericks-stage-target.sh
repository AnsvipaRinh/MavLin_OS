#!/usr/bin/env bash
# Stage the MavLinOS post-install runtime into an already-installed target.
# Run from the live ISO after the target filesystem has been mounted.
set -euo pipefail

TARGET_ROOT="${1:-}"
if [[ -z "$TARGET_ROOT" || ! -d "$TARGET_ROOT" ]]; then
  echo "Usage: $0 /mnt" >&2
  exit 2
fi
TARGET_ROOT="$(realpath "$TARGET_ROOT")"
if [[ "$TARGET_ROOT" == "/" ]]; then
  echo "Refusing to stage into the live root filesystem; pass the mounted target root." >&2
  exit 2
fi

SRC_BIN="/usr/local/bin/mavericks"
SRC_PROFILES="/usr/local/share/mavericks/profiles"
DST_BIN="$TARGET_ROOT/usr/local/bin/mavericks"
DST_PROFILES="$TARGET_ROOT/usr/local/share/mavericks/profiles"

[[ -d "$SRC_BIN" ]] || { echo "ERROR: live ISO runtime missing: $SRC_BIN" >&2; exit 1; }
[[ -d "$SRC_PROFILES" ]] || { echo "ERROR: live ISO profiles missing: $SRC_PROFILES" >&2; exit 1; }

install -d "$DST_BIN" "$DST_PROFILES"
cp -a "$SRC_BIN/." "$DST_BIN/"
cp -a "$SRC_PROFILES/." "$DST_PROFILES/"
chmod 0755 "$DST_BIN/mavericks-firstboot.sh" "$DST_BIN/mavericks-profile-select.sh"

echo "[mavericks-stage] staged post-install runtime into $TARGET_ROOT"
echo "[mavericks-stage] next: arch-chroot $TARGET_ROOT /usr/local/bin/mavericks/mavericks-firstboot.sh"
