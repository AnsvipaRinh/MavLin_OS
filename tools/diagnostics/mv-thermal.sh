#!/usr/bin/env bash
# mv-thermal.sh — sustained-load thermal behavior (read-only except load itself)
# Usage: sudo ./mv-thermal.sh [seconds]
set -euo pipefail
DUR="${1:-60}"
OUT="/var/log/mavericks-thermal-$(date +%F_%H%M%S).log"
exec > >(tee -a "$OUT") 2>&1
echo "Thermal test ${DUR}s. Workers: $(nproc)"
stress-ng --cpu "$(nproc)" --timeout "${DUR}s" &
LOAD_PID=$!
turbostat --show Busy%,Bzy_MHz,PkgTmp,CoreTmp,PkgWatt,GFX%Throttle --interval 2 --num_iterations $((DUR/2)) || true
wait $LOAD_PID
echo "Done: $OUT"
