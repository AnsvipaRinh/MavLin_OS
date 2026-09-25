#!/usr/bin/env bash
# mv-collect.sh — read-only hardware bring-up collector
# Collects everything, changes nothing. No powertop --auto-tune, no sysctl writes.
# Usage: sudo ./mv-collect.sh [outdir]
# Output: <outdir>/TIMESTAMP/{*.txt,*.log}
set -euo pipefail
OUT="${1:-/var/log/mavericks-bringup}/$(date +%F_%H%M%S)"
mkdir -p "$OUT"
say() { echo "== $*"; }
run() { echo "\$ $*" >> "$OUT/commands.log"; "$@" >> "$OUT/commands.log" 2>&1 || echo "(exit $?)"; }
runsh() { echo "\$ $*" >> "$OUT/commands.log"; bash -c "$*" >> "$OUT/commands.log" 2>&1 || echo "(exit $?)"; }

say "Writing to $OUT"
{
echo "date: $(date -u +%FT%TZ)"
echo "kernel: $(uname -r)"
echo "cmdline: $(cat /proc/cmdline)"
} > "$OUT/header.txt"

# 1 Boot
run systemd-analyze
run systemd-analyze blame --no-pager
run journalctl -b -p err --no-pager
run dmesg -T

# 2 DMI / PCI / USB
run dmidecode -s system-product-name
run dmidecode -s system-version
run lspci -nn
run lsusb -t
run lsusb -v

# 3 Display
run xrandr --query 2>/dev/null || echo "no X"
run cat /sys/class/drm/card0-eDP-1/modes 2>/dev/null || true
run cat /sys/module/i915/parameters/enable_psr 2>/dev/null || true
run cat /sys/module/i915/parameters/enable_fbc 2>/dev/null || true
run cat /sys/module/i915/parameters/enable_guc 2>/dev/null || true

# 4 Input
run libinput list-devices 2>/dev/null || true
runsh "dmesg -T | grep -iE 'applespi|spi|input' | head -50"
run ls /sys/bus/spi/devices/ 2>/dev/null || true
runsh "cat /proc/interrupts | grep -i spi || echo '(no spi irq)'"

# 5 Wi-Fi / BT
run lspci -nn -d 14e4:
runsh "dmesg -T | grep -iE 'brcm|wl|firmware' | head -40"
run iw dev
run nmcli general status 2>/dev/null || true
run nmcli device status 2>/dev/null || true
run bluetoothctl show 2>/dev/null || true
runsh "dmesg -T | grep -iE 'bluetooth|btusb|hci' | head -20"

# 6 Audio
run lspci -nn | grep -i audio
runsh "dmesg -T | grep -iE 'snd|hda|cirrus|cs42' | head -40"
run aplay -l
run arecord -l
run wpctl status 2>/dev/null || true

# 7 NVMe
run nvme list
run nvme smart-log /dev/nvme0 2>/dev/null || true
run cat /sys/module/nvme_core/parameters/default_ps_max_latency_us 2>/dev/null || true
run cat /sys/module/pcie_aspm/parameters/policy 2>/dev/null || true

# 8 Battery
run upower -i /org/freedesktop/UPower/devices/battery_BAT0 2>/dev/null || true
run cat /sys/class/power_supply/BAT*/uevent 2>/dev/null || true
run acpi -b 2>/dev/null || true

# 9 CPU/HWP
run lscpu
for f in scaling_driver scaling_governor energy_performance_preference; do
  echo "--- cpu0/$f"; cat /sys/devices/system/cpu/cpu0/cpufreq/$f 2>/dev/null || echo MISSING
done > "$OUT/cpu-hwp.txt"
run cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
run cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost 2>/dev/null || true
run turbostat --show Busy%,Bzy_MHz,PkgTmp,PkgWatt --interval 2 --num_iterations 5 2>&1 || true

# 10 zram/VM
run swapon --show
run zramctl
run cat /proc/swaps
run sysctl vm.swappiness vm.page-cluster vm.vfs_cache_pressure vm.dirty_writeback_centisecs 2>/dev/null || true

# 11 Power (observation only — NO --auto-tune)
run powertop --time=20 --csv="$OUT/powertop.csv" 2>&1 || true

# 12 Suspend readiness (no actual suspend here)
run cat /sys/power/state
run cat /sys/power/mem_sleep
run cat /sys/power/disk 2>/dev/null || true

say "Done: $OUT"
ls -la "$OUT"
