#!/usr/bin/env bash
# mv-experiment.sh — one-variable experiment runner with rollback
# Usage: sudo ./mv-experiment.sh <E1..E12|list> [apply|revert|status]
# Profiles live in configs/profiles/experiments/. Kernel cmdline variants
# require editing the bootloader entry + reboot; TLP/sysctl variants apply live.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
EXP_DIR="$REPO/configs/profiles/experiments"
BACKUP_DIR="/var/lib/mavericks-experiments"
mkdir -p "$BACKUP_DIR"

list() { ls "$EXP_DIR"; }

apply() {
  local id="$1"
  case "$id" in
    E1) echo "E1 needs reboot: append 'intel_pstate.no_turbo=1' to bootloader options, reboot, then run tools/diagnostics/mv-power.sh + mv-thermal.sh";;
    E2) echo "E2 needs reboot: REMOVE 'pcie_port_pm=off' from bootloader options, reboot, then run tools/diagnostics/mv-suspend-test.sh 10";;
    E3) echo "E3 needs reboot: append 'nvme_core.default_ps_max_latency_us=0', reboot, then mv-power.sh + mv-suspend-test.sh";;
    E4) echo "E4 needs reboot: replace 'i915.enable_psr=0' with 'i915.enable_psr=1', reboot, check flicker + mv-power.sh";;
    E5) echo "E5 needs reboot: replace with 'i915.enable_psr=2' (only after E4), reboot, same checks";;
    E6) echo "E6 needs reboot: append 'i915.enable_fbc=1', reboot, mv-power.sh 24h stability";;
    E7) echo "E7 needs reboot: append 'i915.enable_guc=2', reboot, check video decode + stability";;
    E8) cp /etc/tlp.d/99-mavericks.conf "$BACKUP_DIR/tlp.conf.bak"; cp "$EXP_DIR/E8-epp.conf" /etc/tlp.d/10-experiment.conf; tlp start; echo "E8 applied. Revert: $0 E8 revert";;
    E9) cp /etc/tlp.d/99-mavericks.conf "$BACKUP_DIR/tlp.conf.bak"; cp "$EXP_DIR/E9-usb-nosuspend.conf" /etc/tlp.d/10-experiment.conf; tlp start; echo "E9 applied. Revert: $0 E9 revert";;
    E11) sysctl -a 2>/dev/null | grep swappiness > "$BACKUP_DIR/sysctl.bak"; sysctl -w vm.swappiness=133; echo "E11 applied (133). Revert: $0 E11 revert";;
    E12) sysctl -a 2>/dev/null | grep dirty_writeback > "$BACKUP_DIR/sysctl.bak"; sysctl -w vm.dirty_writeback_centisecs=3000; echo "E12 applied. Revert: $0 E12 revert";;
    E10) echo "E10: run configs/profiles/experiments/E10-wifi-powersave.sh wlan0 off|on";;
    *) echo "unknown: $id"; list; exit 1;;
  esac
}

revert() {
  local id="$1"
  case "$id" in
    E8|E9) rm -f /etc/tlp.d/10-experiment.conf; tlp start; echo "reverted $id (tlp)";;
    E11) sysctl -w vm.swappiness=60; echo "reverted E11";;
    E12) sysctl -w vm.dirty_writeback_centisecs=500; echo "reverted E12";;
    E1|E2|E3|E4|E5|E6|E7) echo "$id needs reboot: restore bootloader entry to baseline (configs/profiles/baseline.conf), reboot";;
    *) echo "unknown: $id"; exit 1;;
  esac
}

case "${1:-list}" in
  list) list;;
  E*) case "${2:-apply}" in apply) apply "$1";; revert) revert "$1";; status) cat /proc/cmdline; tlp-stat -s -c -p 2>/dev/null | head -30;; esac;;
  *) echo "Usage: $0 <E1..E12|list> [apply|revert|status]"; exit 1;;
esac
