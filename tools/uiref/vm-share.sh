#!/bin/bash
# Build a fresh FAT share image for the Mavericks guest.
#
# Every invocation creates a NEW image with a NEW volume label, so the guest
# mounts fresh and never serves a cached copy of an earlier artifact.  Files
# are given unique names (they carry the build id), so nothing is ever
# overwritten in place.  expect.txt records the md5 of every file; the guest
# runner compares its own md5 against it and refuses to run on a mismatch.
#
# Usage: vm-share.sh <image> <lowercase-label> <file> [<file>...]
# Prints: "<label> <build-id-or-dash>"
set -euo pipefail

img=$1; shift
label=$1; shift
[ $# -ge 1 ] || { echo "usage: vm-share.sh <image> <label> <file>..." >&2; exit 2; }

case "$label" in
  [A-Z]*) echo "label must be lowercase (it is typed into the guest)" >&2; exit 2 ;;
esac

tmp="$img.fat"
rm -f "$img" "$tmp"
truncate -s 64M "$img"
truncate -s 63M "$tmp"
mkfs.vfat -F 32 -n "$label" "$tmp" >/dev/null 2>&1
base=$(basename "$img")
sfdisk "$img" >/dev/null <<EOF
label: dos
unit: sectors

${base}1 : start=2048, size=129024, type=c, bootable
EOF
dd if="$tmp" of="$img" bs=512 seek=2048 conv=notrunc status=none
rm -f "$tmp"

spec="$img@@1048576"
: > /tmp/expect-$$.txt
for f in "$@"; do
  name=$(basename "$f")
  mcopy -o -i "$spec" "$f" "::$name"
  sum=$(md5sum "$f" | cut -d' ' -f1)
  echo "$name $sum" >> /tmp/expect-$$.txt
  printf '%-28s %s\n' "$name" "$sum"
done
mcopy -o -i "$spec" /tmp/expect-$$.txt ::expect.txt
rm -f /tmp/expect-$$.txt

# prove the image itself carries what we think it does
verify=/tmp/verify-$$.txt
: > "$verify"
while read -r name sum; do
  mcopy -o -i "$spec" "::$name" "/tmp/vf-$$-$(basename "$name")" 2>/dev/null || true
  got=$(md5sum "/tmp/vf-$$-$(basename "$name")" 2>/dev/null | cut -d' ' -f1 || echo missing)
  [ "$got" = "$sum" ] || { echo "image verify failed: $name got=$got want=$sum" >&2; exit 1; }
  rm -f "/tmp/vf-$$-$(basename "$name")"
done < <(mcopy -i "$spec" ::expect.txt /dev/stdout 2>/dev/null | tail -n +2 | awk '{print $1, $2}')
rm -f "$verify"

echo "image $img label $label verified"
