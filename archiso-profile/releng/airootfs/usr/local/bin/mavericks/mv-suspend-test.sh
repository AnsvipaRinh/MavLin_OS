#!/usr/bin/env bash
# mv-suspend-test.sh — 10-cycle suspend/resume (baseline must have pcie_port_pm=off)
# Usage: sudo ./mv-suspend-test.sh [cycles]
# Logs NVMe health, FS errors, device return after each cycle.
set -euo pipefail
CYCLES="${1:-10}"
LOG="/var/log/mavericks-suspend-$(date +%F_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "Suspend test: $CYCLES cycles. Baseline: $(cat /proc/cmdline)"
for ((i=1;i<=CYCLES;i++)); do
  echo "=== Cycle $i/$(date) ==="
  nvme list 2>&1 | head -5 || echo "NVME MISSING BEFORE SUSPEND"
  rtcwake -m mem -s 15 || { echo "rtcwake failed"; systemctl suspend; sleep 20; }
  sleep 10
  echo "--- after resume ---"
  nvme list 2>&1 | head -5 || echo "NVME MISSING AFTER RESUME (FAIL)"
  dmesg -T | tail -30 | grep -iE "nvme|pcie|error|fail|timeout" || echo "(no errors in tail)"
  xrandr --query 2>/dev/null | head -5 || echo "(no X)"
  nmcli device status 2>/dev/null | head -8 || true
done
echo "Log: $LOG"
