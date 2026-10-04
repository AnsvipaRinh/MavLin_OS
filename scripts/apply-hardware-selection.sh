#!/usr/bin/env bash
# apply-hardware-selection.sh — compatibility entry point
#
# Hardware selection is now profile-first and self-contained in the installed
# image. Keep this script for existing documentation/user workflows, but do
# not maintain a second hardware/DKMS decision tree here.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: run as root." >&2
  exit 1
fi

SELECTOR="/usr/local/bin/mavericks/mavericks-profile-select.sh"
FIRSTBOOT="/usr/local/bin/mavericks/mavericks-firstboot.sh"

# Source-tree fallback is for development/checkouts only.
if [[ ! -x "$SELECTOR" ]]; then
  SELECTOR="$(cd "$(dirname "$0")" && pwd)/install/mavericks-profile-select.sh"
fi
if [[ ! -x "$FIRSTBOOT" ]]; then
  FIRSTBOOT="$(cd "$(dirname "$0")" && pwd)/install/mavericks-firstboot.sh"
fi

[[ -x "$SELECTOR" ]] || { echo "ERROR: profile selector not found." >&2; exit 1; }
[[ -x "$FIRSTBOOT" ]] || { echo "ERROR: firstboot script not found." >&2; exit 1; }

echo "=== MavLinOS Hardware Profile Selection ==="
"$SELECTOR"
echo
"$FIRSTBOOT"
