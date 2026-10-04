#!/usr/bin/env python3
"""Static guardrails for the read-only power diagnostics."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COLLECT = (ROOT / "tools/diagnostics/mv-collect.sh").read_text()
POWER = (ROOT / "tools/diagnostics/mv-power.sh").read_text()

def require(text, *needles):
    for needle in needles:
        assert needle in text, "missing: %s" % needle

require(
    COLLECT,
    "systemctl --user list-timers --all",
    "systemctl --user list-units --type=service --state=running",
    "/proc/interrupts",
    "/proc/softirqs",
    "runtime_status",
    "runtime_active_time",
    "runtime_suspended_time",
    "i915_psr_status",
    "i915_fbc_status",
    "pw-top -b -n 1",
)

require(
    POWER,
    "power_now",
    "voltage_now",
    "current_now",
    "energy_now",
    "PkgWatt",
    "Pkg%pc10",
)

for path in (ROOT / "tools/diagnostics").glob("*.sh"):
    text = path.read_text()
    forbidden = ("sysctl -w", "powertop --auto-tune", "tee -a /sys/")
    for token in forbidden:
        assert token not in text, "%s contains forbidden write: %s" % (path, token)

print("OK: power diagnostic guardrails")
