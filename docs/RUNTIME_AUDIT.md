# RUNTIME / WAKEUP / LANGUAGE AUDIT — Phase 0.5
# Rule: remove > configure-less > de-poll > replace > rewrite. No mature-subsystem rewrites.

## Persistent daemons (installed desktop, approximate steady-state)

| Component | Lang | Persistent? | Event vs Poll | RAM (est) | Runtime-critical? | Action |
|---|---|---|---|---|---|---|
| Xorg | C | yes | event (epoll/input) | ~60MB | yes | KEEP (no Wayland: Xfce Wayland immature) |
| xfwm4 | C | yes | event | ~20MB | yes | KEEP; compositing minimal (shadows only) |
| xfce4-panel | C | yes | event | ~20MB | yes | KEEP; 6 plugins only, no global-menu |
| xfdesktop | C | yes | event (inotify) | ~15MB | yes | KEEP |
| Plank | Vala/C | yes | event | ~25MB | yes | KEEP; HideMode=1 (hides when idle) |
| xfce4-power-manager | C | yes | event (UPower) | ~10MB | yes | KEEP |
| xfce4-screensaver | C | yes | event | ~10MB | yes | KEEP |
| NetworkManager | C | yes | event (netlink) | ~15MB | yes | KEEP |
| pipewire | C | yes | event (epoll) | ~15MB | yes | KEEP |
| wireplumber | Lua/C | yes | event | ~10MB | yes | KEEP (Lua scripts run at graph change only) |
| upower | C | yes | event (uevent) | ~5MB | no | KEEP (needed by power manager) |
| bluetoothd | C | yes | event | ~5MB | no | KEEP, rfkill-blocked until use |
| lightdm | C | yes | event | ~20MB | yes | KEEP |

## Polling / wakeup sources found and fixed

| Source | Was | Fix | Tier |
|---|---|---|---|
| `powertop --auto-tune` in docs/scripts | modifies PM state | BANNED from measurement; observation only | Tier 1 |
| `reflector.service` at every boot | network + disk on boot | ISO only; installed → weekly timer or OFF | Tier 1 |
| `fstrim.timer` default weekly | fine | KEEP weekly (SSD, negligible) | — |
| `systemd-timesyncd` | polls NTP ~30min | KEEP (tiny; needed for TLS) | — |
| Firefox `sessionstore.interval` 15s | SSD write every 15s | set 60s in user.js/policies.json | Tier 2 |
| Plank HideMode=0 (always visible) | compositing always | HideMode=1 (dodge/autohide) | Tier 2 |
| xfwm4 vblank compositor | GPU wakeups | vblank off + unredirect_overlays | Tier 2 |
| Custom shell-loop helpers | N/A (none shipped) | `mv-power.sh` uses sleep 60 (OK: measurement tool, not daemon) | — |

## Language audit (persistent path only)

- No Java/Python/Perl/Ruby/Node in persistent runtime path. WirePlumber embeds Lua
  but scripts are event-driven (graph change), not polling — acceptable.
- Python present on ISO for installer tooling only (not a daemon).
- `choose-mirror` (bash+curl, oneshot at boot in ISO) — fine.

## Rewrite candidates — verdict

| Candidate | Verdict | Rationale |
|---|---|---|
| NVRAM extractor (`extract-brcmfmac-nvram.sh`) | KEEP as shell | Runs once at first boot; rewrite to C saves nothing |
| `mv-collect.sh` / `mv-power.sh` | KEEP as shell | Diagnostic tools, not daemons; total runtime minutes |
| `mv-experiment.sh` | KEEP as shell | Applies configs; runs rarely |
| Plank settings applier | REMOVED (use static skel files) | No daemon needed; files copied at install |
| Custom thermal daemon | REJECTED | Kernel/TLP sufficient until hardware proves otherwise |
| Custom panel plugin / settings app / lock screen | REJECTED | Theme + stock Xfce = 90%; custom = maintenance cost |
| `choose-mirror` | KEEP | Upstream archiso component; oneshot |

**No custom C/Rust components justified pre-hardware.** All persistent code is
already C/Vala event-driven. Rewrites would save ~0 measurable energy.
Revisit only if `powertop` wakeup audit on hardware shows a specific offender.

---

## AUDIO (HDA / Cirrus CS4208 / PipeWire) — D4, 2026-09-28

Deep Runtime Track D4. Target: MacBook10,1, Cirrus CS4208 on Intel HDA
(PCI 00:1f.3), PipeWire 1.6.9 + WirePlumber 0.5.17, DKMS codec driver
(leifliddy/macbook12-audio-driver r108.g4cdfcdb). Build behavior
empirically verified in the build container (linux-zen-headers
7.2.6.zen2-1 + linux-7.2.6 source) — see RUNTIME_COMPONENT_MAP.md §8.4.

### Runtime map

| Layer | Component | Package | Runs at idle | Wakeup source |
|---|---|---|---|---|
| HDA controller | snd-hda-intel (PCI 00:1f.3) | linux-zen | yes — D3hot via runtime PM | stream start, jack GPIO, power_save timeout |
| Codec driver | snd-hda-codec-cs420x (DKMS, A1534 init) | macbook12-audio-driver | yes — powers with controller | jack GPIO interrupt |
| ALSA | alsa-lib / alsa-utils | alsa-utils | no (libs + on-demand tools) | — |
| UCM | none for CS4208 (no upstream UCM; generic HiFi fallback) | — | — | — |
| Audio server | pipewire + pipewire-alsa + pipewire-pulse | ISO | yes — epoll idle (~15MB) | stream/node events |
| Session manager | wireplumber 0.5.17 | ISO | yes — event-driven Lua (~10MB) | graph changes only |
| Soft-volume rule | 51-macbook-cs4208-softvol.conf (api.alsa.soft-mixer) | macbook12-audio-driver | — | — |
| mv-control sound | pactl get/set-sink-volume, get-sink-mute, get-default-sink, list sinks | mavericks-apps | no — window open only | user action |
| mv-voice | pw-record/parec + pw-play/paplay one-shot | mavericks-apps | no | user action |
| Media keys | XF86Audio* → pactl set-sink-* / mv-music --media-key | mavericks-apps | no | keypress |

### Idle-component table (connected-idle, zero streams)

| Component | Runs at idle? | Wakeup source | HW counter to check |
|---|---|---|---|
| pipewire daemon | yes | D-Bus/pipewire socket events (epoll) | `pw-top` — no RUNNING nodes; `pw-dump` node count |
| wireplumber | yes | graph-change events only | `pw-top` — no activity; no timers in `wpctl status` |
| snd-hda-intel controller | yes (D3hot) | stream start, jack GPIO, 1s power_save timeout | `/sys/bus/pci/devices/0000:00:1f.3/power/runtime_status` → `suspended`; `/sys/module/snd_hda_intel/parameters/power_save` → 1 |
| CS4208 codec | yes (with controller) | jack GPIO interrupt | `/proc/asound/card0/codec#0` → `Power: setting=D3`, clock gate on |
| mv-control / mv-voice | no | — | zero processes (`pgrep -f mv-control mv-voice` empty) |
| pactl sites | no | — | no periodic subprocess (`refresh_all` 30s never touches sound — verified) |

### DSP / clock-gating on this path

No DSP work on this path. HDAudio is not a DSP-based bus: CS4208 init is
replayed as a verb sequence by the DKMS codec driver (setup_a1534 /
play_a1534, reverse-engineered from macOS), streams are plain DMA over the
HDA link, and the codec's internal DSP core is unused. Power gating happens
at the HDA controller level only: `snd-hda-intel power_save` (1s timeout)
+ controller runtime PM (`power_save_controller`), both owned by TLP in the
frozen baseline. The codec powers down with the controller; jack detection
is a GPIO interrupt that wakes the controller from D3hot.

### pactl sites — disposition (R1/R2 flag CLOSED)

All pactl usage in our stack is event-driven (keypress, user action, window
open). Re-verified in the current tree (after 14c8009/143e9b2): the mv-control
30s `refresh_all` touches only Wi-Fi/Bluetooth/power-mode/DND — never the
sound section. No audio polling exists or is planned.

| Site | Trigger | Verdict |
|---|---|---|
| mv-control get_volume / get_mute | window open (build_sound_section) | on-demand, OK |
| mv-control refresh_output_devices | window open | on-demand, OK |
| mv-control set-sink-volume / set-sink-mute / set-default-sink | slider / combo user action | on-demand, OK |
| XF86AudioRaiseVolume / LowerVolume / Mute (xfce4-keyboard-shortcuts.xml) | keypress | on-demand, OK |
| mv-about `pactl info \| grep 'Server Name'` | window open | on-demand, OK |
| mv-voice pw-record/parec + pw-play/paplay | one-shot record/play | on-demand, OK |

### DKMS build defect (macbook12-audio-driver) — evidence

The package's DKMS build path is broken at install time (empirically
verified in the build container, linux-zen-headers 7.2.6.zen2-1):

1. `dkms install` runs `make -C /usr/lib/modules/<ver>/build M=<srcroot>
   modules` (dkms.conf MAKE[0]) — the DKMS source tree has **no root
   Makefile** (Makefile_cirrus/Makefile_cs420x are in-tree kbuild files).
   Build fails: `Makefile: No such file or directory`.
2. Even with a Makefile, the driver needs kernel-internal HDA headers
   (sound/hda/common/hda_local.h, hda_auto_parser.h, hda_jack.h,
   sound/hda/codecs/generic.h) — **linux-zen-headers ships zero .h files
   under sound/hda/** (verified: 0 headers in the headers build tree).
   External-module builds are impossible without the full kernel source.
3. The upstream manual flow (prepare.cirrus.driver.sh) handles this by
   downloading the kernel source tarball and patching in-tree — the working
   install path needs network at install time.

**The driver source itself compiles cleanly against the target kernel**
(verified: external build of patch_cirrus/cs420x.c + A1534 headers against
linux-7.2.6 source + linux-zen-headers 7.2.6.zen2-1 → snd-hda-codec-cs420x.ko
builds, 1.75MB, GPL, alias hdaudio:v10134208). The defect is purely in the
DKMS packaging, not the driver code.

**Disposition:** package kept in the local repo for the manual build flow;
NOT added to ISO packages.x86_64 (post_install would fail `dkms install` and
break pacstrap). Follow-up: track tanisperez/macbook12-audio-driver (6.17+
support + working DKMS via PRE_BUILD kernel-source download) as the
replacement pin — separate packaging track with its own validation.

### TLP interaction (no double-tuning)

TLP 1.9.1 defaults: SOUND_POWER_SAVE_ON_AC=1, SOUND_POWER_SAVE_ON_BAT=1,
SOUND_POWER_SAVE_CONTROLLER=Y — audio power save is already enabled on AC
and battery. The former modprobe `power_save=1 power_save_controller=Y`
lines were redundant (same values); removed in D4 (888e0ff). TLP owns audio
PM in the frozen baseline. HW item: listen for audio glitches (pops/clicks)
with power_save=1 on CS4208; if present, raise the timeout or disable on
BAT with evidence (NEEDS_HARDWARE_TEST.md §Audio power/idle).
