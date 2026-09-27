# PERF AUDIT — static analysis of polling / timers / watchers (phase A)

> Companion to `docs/PERF_METHODOLOGY.md` + `docs/BENCHMARKS.md`.
> Static audit only — nothing here is a change. Ranked suspects feed phase B.
> Audit date: 2026-09-27. Scope: `packages/mavericks-apps/src`, `tools/`,
> `scripts/`, `configs/`, `archiso-profile/` skel configs.

## Ranked suspects

| ID | Severity | Location | Finding | Cost class |
|---|---|---|---|---|
| S-01 | **HIGH** | `packages/mavericks-apps/src/mavericks-apps/bin/mv-control:150,231,238,266` (Wi-Fi list refresh, 2–3 s) + `:63` (refresh_all, 5 s) | `refresh_wifi_list` spawns `nmcli -t -f SSID,SECURITY,SIGNAL,ACTIVE dev wifi list` — **each call triggers a physical Wi-Fi rescan**. While Control Center is open, the Wi-Fi chip rescans every 2–3 s. | Host: 0.0075 s/call (no Wi-Fi device). Target: BCM43602 rescan = device wakeups + RF energy. Measured proxy S18. |
| S-02 | MEDIUM | `mv-console:204` (`tick` → `reload()` → `subprocess.run(journalctl …)`) | Follow mode spawns a **journalctl subprocess every 2 s** while Console is open with follow enabled. | Subprocess spawn + journal scan per tick. Fix: `journalctl --follow` persistent process or ≥5 s interval. |
| S-03 | MEDIUM | `mv-music:925` (`timeout_add(300, _refresh_backend)`), `:1423,:1441` (900 ms `_kick_playback` retry) | 3.3 Hz D-Bus property polling while Music is open; 900 ms retry loop while backend unavailable. `_refresh_backend` does synchronous D-Bus calls in the UI thread (`:1225+`). | ~3 wakeups/s + UI-thread blocking risk. |
| S-04 | MEDIUM | `mv-colormeter:22` (`TICK_MS = 100`), `:442` | 10 Hz screen sampling while Digital Color Meter is open. | 10 wakeups/s + X11 screen reads. Fix: 250–500 ms. |
| S-05 | LOW | `mv-activity:96` (`timeout_add_seconds(2, refresh)`) | 2 s /proc polling while Activity Monitor is open. No subprocess — pure `/proc` reads. | Acceptable per AGENTS.md §7 (refresh only while window open); could be 5 s. |
| S-06 | LOW | `mv-control:301,377,387,397` (BT list, 2 s) | D-Bus `GetManagedObjects` poll for Bluetooth — no rescan, but still 0.5 Hz wakeups while open. | Low; event-driven (BlueZ InterfaceAdded/Removed) would eliminate. |
| S-07 | LOW | `mv-power-ui:458` (`timeout_add_seconds(1, _tick)`) | 1 Hz UPower D-Bus reads while Power UI open. | Low; 2–5 s sufficient for power telemetry. |
| S-08 | LOW | `mv-textedit:101` (`AUTOSAVE_INTERVAL = 30` s) | Autosave writes file every 30 s while TextEdit open. | Small periodic SSD write; same class as Firefox sessionstore (already set to 60 s). |
| S-09 | HYGIENE | `archiso-profile/releng/airootfs/etc/skel/.config/autostart/mv-notify-send.desktop` + `bin/mv-notify-send` | `mv-notify-send` is **on-demand** (forwards to `notify-send` and exits) but is autostarted → pointless login-time spawn + empty notification at every login. | One wasted process + one spurious notification per login. **Fix: remove autostart entry.** |
| S-10 | HYGIENE | `bin/mv-hud.c` + no `genmon` reference in skel panel config | `mv-hud` (C one-shot energy/thermal HUD for genmon) is **not wired into the panel** — dead code unless invoked manually. | Zero runtime cost (good), but the intended HUD surface does not exist. **Fix: wire into panel or drop.** |
| S-11 | CORRECTNESS | `mv-about:138` (`on_select`: `AttributeError: 'About' object has no attribute 'tv'`) | Found via S03: a selection callback fires during init before `self.tv` exists; app prints traceback but keeps running `Gtk.main()`. Same callback-fires-during-init pattern likely affects other GTK apps. | Not a perf bug, but a startup crash that users will see. Phase B should audit init callbacks tree-wide. |
| S-12 | TOOLING | all of `bin/mv-*` | App launchers are **extensionless** — any `*.py`-keyed tooling (linters, greps, some editors) silently misses them. | No runtime cost; audit/repair risk. |

## System-level timers (measured, not suspects)

| Timer | Frequency | Verdict |
|---|---|---|
| `mv-calendar-check.timer` | every 5 min (`OnCalendar=*:0/5`) | KEEP — user timer, tiny |
| `mv-reminders-check.timer` | hourly | KEEP |
| `mv-timemachine-check.timer` | hourly | KEEP |
| `fstrim.timer` | weekly | KEEP (SSD) |
| Firefox `sessionstore.interval` | 60 s (`configs/firefox/user.js:32`) | KEEP (already fixed in Phase 0.5) |
| Plank `HideMode=1` | — | KEEP (dodge when idle) |

## Clean bills (explicitly checked, no polling found)

- `while True` / `while 1`: only algorithmic loops (`mv-notes:65` string search,
  `mv-photos:101` JPEG parser) — one-shot, not daemon loops.
- `GFileMonitor` / inotify in custom code: **none** (Thunar's internal
  inotify is upstream, event-driven).
- Subprocess-per-keystroke: **none** (no `search-changed` → subprocess
  pattern in any mv-* app; Spotlight query is a separate one-shot tool).
- Thumbnailers: none configured in `thunarrc` — nothing to tune.
- Custom autostart entries: only `plank` + `mv-notify-send` (see S-09).
- xfwm4 vblank compositor: already off (Phase 0.5, RUNTIME_AUDIT.md).

## Notes for phase B

1. S-01 is the only HIGH: on the target, Wi-Fi rescan every 2–3 s while
   Control Center is open directly fights the power baseline (BCM43602
   wakeups). Signal-driven refresh (NetworkManager D-Bus) is the fix shape.
2. S-02/S-03 are "window-open-only" polls — allowed by AGENTS.md §7 but
   candidates for interval increases or signal-driven redesign.
3. S-09 is a one-line deletion; do it first.
4. S-11 correctness bug should be fixed before hardware bring-up so the
   first-boot screenshot set is clean.
