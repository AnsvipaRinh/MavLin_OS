#!/usr/bin/env bash
# run-bench.sh — thin wrapper for the perf-track benchmark harness.
# Usage: scripts/bench/run-bench.sh [--output PATH] [--repeats N] [--profile NAME] [--scenario NAME]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/bench.py" "$@"
