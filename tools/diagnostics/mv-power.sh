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

# Battery samples every 60s. Prefer kernel power_now (uW), but also
# capture voltage/current so systems without power_now remain measurable.
(
for ((i=0;i<IDLE/60;i++)); do
  ts="$(date -u +%FT%TZ)"
  status="$(cat /sys/class/power_supply/BAT*/status 2>/dev/null || echo NA)"
  power="$(cat /sys/class/power_supply/BAT*/power_now 2>/dev/null || echo NA)"
  voltage="$(cat /sys/class/power_supply/BAT*/voltage_now 2>/dev/null || echo NA)"
  current="$(cat /sys/class/power_supply/BAT*/current_now 2>/dev/null || echo NA)"
  energy="$(cat /sys/class/power_supply/BAT*/energy_now 2>/dev/null || echo NA)"
  echo "$ts status=$status power_now_uW=$power voltage_now_uV=$voltage current_now_uA=$current energy_now_uWh=$energy"
  sleep 60
done
) > "$OUT/battery.log" &

# turbostat package power + C-states
turbostat --show PkgWatt,PkgTmp,CoreTmp,Pkg%pc2,Pkg%pc3,Pkg%pc6,Pkg%pc7,Pkg%pc8,Pkg%pc9,Pkg%pc10,Bzy_MHz --interval 10 --num_iterations $((IDLE/10)) > "$OUT/turbostat.log" 2>&1 || true
wait
echo "Done: $OUT"
