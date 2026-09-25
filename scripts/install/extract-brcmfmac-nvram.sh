#!/usr/bin/env bash
# extract-brcmfmac-nvram.sh — first-boot NVRAM provisioning for BCM43602 (MacBook10,1)
# Status: IMPLEMENTED + UNVALIDATED (needs hardware: verify 5GHz + signal)
# The BCM43602 needs per-board radio calibration (brcmfmac43602-pcie.txt).
# Without it: no 5GHz, weak signal, placeholder MAC. Source: extract from macOS
# firmware (IO80211Family.kext) OR use community template, then set macaddr=.
# This script checks state and installs a template if missing; it does NOT
# fabricate calibration data — replace template with extracted file when available.
set -euo pipefail
FW_DIR="/usr/lib/firmware/brcm"
TXT="$FW_DIR/brcmfmac43602-pcie.txt"
IFACE="$(ls /sys/class/net/ 2>/dev/null | grep -E '^wl' | head -1 || true)"
MAC="$(cat "/sys/class/net/$IFACE/address" 2>/dev/null || echo "02:00:00:00:00:00")"

echo "=== brcmfmac NVRAM check ==="
echo "iface: ${IFACE:-none}  mac: $MAC"
if [[ -f "$TXT" ]]; then
  echo "OK: $TXT exists ($(wc -c < "$TXT") bytes). Verify 5GHz + signal on hardware."
  exit 0
fi
echo "MISSING: $TXT — installing placeholder template (REPLACE with extracted Apple NVRAM)."
mkdir -p "$FW_DIR"
cat > "$TXT" <<EOF
# PLACEHOLDER — replace with Apple-extracted brcmfmac43602-pcie.txt for MacBook10,1
# Source: /System/Library/Extensions/IO80211Family.kext/.../AirPortBrcmNIC.kext/... (macOS)
# See: https://github.com/Dunedan/mbp-2016-linux (NVRAM extraction docs)
# Status: UNVALIDATED
macaddr=$MAC
ccode=X0
EOF
chmod 644 "$TXT"
echo "Wrote placeholder $TXT. Next: brcmfmac feature_disable/roamoff are EXPERIMENTS (E10 family), not baseline."
echo "If 5GHz missing or signal weak after replacing with real NVRAM, test:"
echo "  options brcmfmac feature_disable=0x82000 roamoff=1"
