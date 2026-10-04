#!/usr/bin/env bash
# apply-hardware-selection.sh — compatibility entry point
#
# Hardware selection is profile-first and self-contained in the installed
# image. This script remains for existing documentation/user workflows.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: run as root." >&2
  exit 1
fi

SELECTOR="/usr/local/bin/mavericks/mavericks-profile-select.sh"
FIRSTBOOT="/usr/local/bin/mavericks/mavericks-firstboot.sh"

# Development checkout fallback only (installed systems use /usr/local paths).
if [[ ! -x "$SELECTOR" ]]; then
  SELECTOR="$(cd "$(dirname "$0")" && pwd)/../archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-profile-select.sh"
fi
if [[ ! -x "$FIRSTBOOT" ]]; then
  FIRSTBOOT="$(cd "$(dirname "$0")" && pwd)/../archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-firstboot.sh"
fi

[[ -x "$SELECTOR" ]] || { echo "ERROR: profile selector not found." >&2; exit 1; }
[[ -x "$FIRSTBOOT" ]] || { echo "ERROR: firstboot script not found." >&2; exit 1; }

echo "=== MavLinOS hardware profile selection ==="
"$SELECTOR" "$@"
echo
echo "=== Running firstboot (idempotent) ==="
"$FIRSTBOOT"
echo
echo "Done. Reboot recommended if this was the first run."
