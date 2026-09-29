# HW_BROWSER_MATRIX — 4-mode browser/video validation plan

> Hardware validation plan for MacBook10,1. All 4 modes use identical workload,
> identical metrics, identical measurement commands. Run on target hardware only.
> Pre-hardware state: all modes are PREPARED, not run.

## 1. Modes

| Mode | Description | Use case |
|---|---|---|
| **M1: Firefox-vanilla** | Firefox ESR, no uBO, no SponsorBlock | Baseline: worst-case page load |
| **M2: Firefox+uBO+SB** | Firefox ESR + uBlock Origin + SponsorBlock | General browsing with blocking |
| **M3: Firefox→ytplayer hybrid** | Firefox for browsing, mv-ytplayer for video | Recommended daily workflow |
| **M4: ytplayer-direct** | mv-ytplayer only (no Firefox) | Video-only, minimal overhead |

## 2. Identical workload (all modes)

### 2.1 Test clips

Use the same 3 YouTube clips for all modes:

| Clip | Duration | Purpose |
|---|---|---|
| A: Big Buck Bunny 1080p | 10 min | Standard test clip, widely available |
| B: Sintel 1080p | 15 min | Longer duration, different codec profile |
| C: Tears of Steel 1080p | 12 min | Higher motion, different codec profile |

### 2.2 Test procedure (per mode, per clip)

1. Boot MacBook10,1, log in, wait 2 min for idle
2. Start measurement (see §3)
3. Open clip in the mode's player
4. Play for 5 min (or full duration if shorter)
5. Close player, wait for return-to-idle (see §4)
6. Stop measurement
7. Record all metrics

### 2.3 Test order

Run modes in order M1 → M2 → M3 → M4, with 5 min idle between modes.
Run each clip once per mode. 3 clips × 4 modes = 12 runs total.

## 3. Metrics (identical for all modes)

### 3.1 Measurement commands

```bash
# CPU + GPU + RSS (run in terminal, 1 sample/sec for 10 min)
# Replace <mode> and <clip> with actual values
for i in $(seq 1 600); do
  echo "$(date +%s) $(grep 'cpu ' /proc/stat | awk '{print $2+$3+$4+$5+$6+$7+$8+$9+$10+$11}') $(cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj 2>/dev/null || echo 0) $(ps -eo rss,comm | grep -E 'firefox|mpv' | awk '{sum+=$1} END {print sum}')" >> /tmp/hw-matrix-<mode>-<clip>.log
  sleep 1
done

# Dropped frames (mpv only, M3/M4)
# Add to mpv command: --msg-level=all=stats
# Parse stderr for "dropped frames"

# Wakeups (run in terminal)
powertop --html=/tmp/hw-matrix-<mode>-<clip>.html --time=600

# Temperature + frequency (run in terminal)
for i in $(seq 1 600); do
  echo "$(date +%s) $(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -1) $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 0)" >> /tmp/hw-matrix-<mode>-<clip>-thermal.log
  sleep 1
done

# Battery discharge (run before and after)
cat /sys/class/power_supply/BAT0/energy_now
cat /sys/class/power_supply/BAT0/power_now
```

### 3.2 Metric definitions

| Metric | Unit | Source | Notes |
|---|---|---|---|
| CPU usage | % | /proc/stat delta | Average over 5-min playback |
| GPU usage | % | intel_gpu_top (if available) | May not be available; record N/A. **intel-gpu-tools is in the ISO for exactly this metric** (KEEP reason, C2 P1-O1: referenced by this HW procedure + DEPENDENCY_AUDIT.md:21) |
| RSS | KB | ps | Peak RSS during playback |
| Dropped frames | count | mpv OSD/stats | M3/M4 only; M1/M2 N/A |
| Wakeups | count/sec | powertop | Average over 5-min playback |
| Temperature | °C | /sys/class/thermal | Peak during playback |
| Frequency | kHz | /sys/devices/system/cpu | Average during playback |
| Discharge rate | µW | /sys/class/power_supply/BAT0 | Average over 5-min playback |
| Time-to-idle | sec | wall clock | From player close to <1% CPU |

## 4. Return-to-idle definition

Return-to-idle = time from player close to ALL of:
- CPU < 1% (5-sec average)
- No firefox/mpv processes running
- No new wakeups in powertop
- Battery discharge rate within 10% of pre-test idle baseline

Target: < 2 sec for M4 (ytplayer-direct), < 5 sec for M3 (hybrid), < 10 sec for M1/M2.

## 5. Mode-specific commands

### M1: Firefox-vanilla

```bash
firefox "https://www.youtube.com/watch?v=<clip-id>"
# Close after 5 min: killall firefox
```

### M2: Firefox+uBO+SB

```bash
# uBO + SponsorBlock pre-installed via policies.json
firefox "https://www.youtube.com/watch?v=<clip-id>"
# Close after 5 min: killall firefox
```

### M3: Firefox→ytplayer hybrid

```bash
# 1. Open Firefox, navigate to YouTube clip
firefox "https://www.youtube.com/watch?v=<clip-id>"
# 2. Click "Watch efficiently" bookmarklet (sends URL to mv-ytplayer)
# 3. mv-ytplayer opens mpv with optimal stream
# 4. After playback, close mpv, return to Firefox
```

### M4: ytplayer-direct

```bash
mv-ytplayer "https://www.youtube.com/watch?v=<clip-id>"
# mpv closes after playback (one-shot)
```

## 6. Decision criteria

### 6.1 Codec validation (all modes)

- [ ] mpv `--hwdec=auto` reports HW decode active (not SW fallback)
- [ ] Chosen format is avc1/vp09/hev1 (not av01)
- [ ] No dropped frames during 5-min playback
- [ ] CPU < 30% during HW decode playback

### 6.2 Power/thermal validation (all modes)

- [ ] Battery discharge rate: M4 < M3 < M2 < M1 (expected ordering)
- [ ] Temperature: no throttling during 5-min playback
- [ ] Frequency: stays at or near base frequency (no turbo needed for HW decode)

### 6.3 Return-to-idle validation (all modes)

- [ ] M4: < 2 sec
- [ ] M3: < 5 sec
- [ ] M1/M2: < 10 sec

### 6.4 Codec policy validation (M3/M4)

- [ ] avc1 preferred when available
- [ ] vp09 used when avc1 unavailable
- [ ] hev1 used when avc1/vp09 unavailable
- [ ] AV1 only as last resort (branch 5)
- [ ] Update `configs/mv-ytplayer/codec-policy.conf` if measurements show different optimal order

## 7. NO-CONCLUSION note

Final codec choice and power/thermal validation come from these measurements on
MacBook10,1, NOT from host bench. The host-SW numbers in VIDEO_PIPELINE.md are a
ceiling, not a target. This matrix is the measurement plan to validate on hardware.

## 8. Pre-hardware state

- All 4 modes are PREPARED (commands ready, metrics defined)
- No measurements have been run (no hardware)
- Codec policy is a starting point based on Gen9.5 HW availability
- See docs/NEEDS_HARDWARE_TEST.md for the full HW validation checklist
