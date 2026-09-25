#!/usr/bin/env bash
# mv-power.sh — read-only power measurement (no state changes)
# Usage: sudo ./mv-power.sh [idle_seconds] [outdir]
# Records: battery discharge, package power, C-state residency, temps.
set -euo pipefail
IDLE="${1:-600}"
OUT="${2:-/var/log/mavericks-power}/$(date +%F_%H%M%S)"
mkdir -p "$OUT"
echo "Sampling ${IDLE}s -> $OUT"
{
echo "kernel: $(uname -r)"
echo "cmdline: $(cat /proc/cmdline)"
tlp-stat -s -c -p 2>/dev/null || true
} > "$OUT/header.txt"

# Battery samples every 60s
(
for ((i=0;i<IDLE/60;i++)); do
  echo "$(date -u +%FT%TZ) $(cat /sys/class/power_supply/BAT*/power_now 2>/dev/null || echo NA) $(cat /sys/class/power_supply/BAT*/energy_now 2>/dev/null || echo NA)"
  sleep 60
done
) > "$OUT/battery.log" &

# turbostat package power + C-states
turbostat --show PkgWatt,PkgTmp,CoreTmp,Pkg%pc2,Pkg%pc3,Pkg%pc6,Pkg%pc7,Pkg%pc8,Pkg%pc9,Pkg%pc10,Bzy_MHz --interval 10 --num_iterations $((IDLE/10)) > "$OUT/turbostat.log" 2>&1 || true
wait
echo "Done: $OUT"
