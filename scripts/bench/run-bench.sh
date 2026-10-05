#!/usr/bin/env bash
# run-bench.sh — thin wrapper for the perf-track benchmark harness.
# Usage: scripts/bench/run-bench.sh [--output PATH] [--repeats N] [--profile NAME] [--scenario NAME]
#
# Host-display isolation (WSLg leak): the bench GUI tiers (G01-G05 and the
# x_server_available probe) map real toplevel windows, so the ambient host
# DISPLAY/WAYLAND_DISPLAY — both forward to the user's Windows desktop — are
# captured+forbidden, a dedicated local Xvfb :97 is pinned, and the fail-loud
# guard (scripts/gui-guard/sitecustomize.py) is armed for every child this
# run launches.  bench.py applies the same isolation itself, so a direct
# `python3 scripts/bench/bench.py` is covered too.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"

source "$REPO/scripts/gui-isolation.sh"
mv_gui_isolate
# Headless host (no Xvfb): mv_gui_pin_display drops DISPLAY and returns 1 —
# keep going, the non-GUI tiers still run and the GUI tiers record no-x-display.
mv_gui_pin_display || true

python3 "$DIR/bench.py" "$@"
