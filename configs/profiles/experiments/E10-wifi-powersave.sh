#!/usr/bin/env bash
# E10 — Wi-Fi power save toggle. Baseline: driver/NM default (observe first).
# Observe: iw dev wlan0 get power_save
# Variant A (disable): iw dev wlan0 set power_save off
# Variant B (enable): iw dev wlan0 set power_save on
# NM per-connection: nmcli c modify <ssid> 802-11-wireless.powersave 2|3
set -euo pipefail
IFACE="${1:-wlan0}"; MODE="${2:-off}"
iw dev "$IFACE" set power_save "$MODE"
iw dev "$IFACE" get power_save
