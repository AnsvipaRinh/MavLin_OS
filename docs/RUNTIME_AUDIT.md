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
