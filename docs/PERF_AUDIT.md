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

## Phase-B dispositions (2026-09-27, commits on master)

| ID | Disposition | Commit | Notes |
|---|---|---|---|
| S-01 | **FIXED** | 14c8009 | `nmcli dev wifi list` was a physical rescan every 5 s via `refresh_all` (plus 2–3 s one-shots after actions). Now NM D-Bus signal-driven (wireless device `PropertiesChanged`, `AccessPointAdded/Removed`, AP `PropertiesChanged`, `DeviceAdded/Removed`) with 1 s debounce + 2 s min interval, 30 s fallback poll, window-open refresh, manual Refresh button. Rescan frequency while Control Center open: 0.2 Hz → signals + 0.033 Hz fallback (≥83% reduction). Behavior preserved: same list fields, same connect/disconnect/password flow, refresh on open. |
| S-02 | **FIXED** | bfebe9b | Follow mode spawned `journalctl` every 2 s. Now a persistent `journalctl -f -n 0` subprocess read via GLib IO watch (event-driven, zero polling); kernel source (dmesg cannot follow) falls back to a 5 s poll. Live-tail UX preserved: entries append live, search filters without requery, Pause/Ctrl+L toggle follow, cleanup on destroy. |
| S-03 | **FIXED** | 143e9b2 | Audit said "3.3 Hz poll"; in fact both 300 ms timers were one-shot (handler returns False) — but `_refresh_backend` did 3 synchronous MPRIS round-trips (≤2 s each) in the UI thread. Fetch now runs in a worker thread on its own session-bus connection, results marshalled via `GLib.idle_add`; mini player same. Initial refresh 300 ms → 1 s; `_kick_playback` retry 900 ms → 2 s. Now-playing freshness preserved (`on_change` → immediate refresh on track/status change). |
| S-04 | **FIXED** | 5330d93 | Colormeter tick 100 ms → 200 ms (10 Hz → 5 Hz while window open, x11 backend only). 5 Hz remains smooth under the loupe. |
| S-05 | **ACCEPTED** (no change) | — | Activity Monitor 2 s refresh is pure `/proc` reads (no subprocess, verified), window-open-only — allowed by AGENTS.md §7. |
| S-06 | **FIXED** | 14c8009 | Audit said "2 s poll"; steady state was already 5 s via `refresh_all` (the 2 s timers are event-driven one-shots after BT actions — kept for UX). Wi-Fi removal from `refresh_all` did not affect BT. Steady state now ≥5 s per spec. |
| S-07 | **ACCEPTED** (misdiagnosis) | — | Audit claimed "1 Hz UPower reads"; the 1 Hz ticker is the shutdown/restart **countdown** UI (`_tick` → label update only) and must stay 1 Hz for a smooth countdown. UPower is read **once** at window open (`query_capabilities` + `query_battery` in `__init__`). No repeating UPower poll exists to relax. |
| S-08 | **ACCEPTED** (no change) | — | TextEdit autosave 30 s is window-open-only, same class as Firefox sessionstore (60 s, already fixed Phase 0.5). SSD write every 30 s while editing is acceptable. |
| S-09 | **FIXED** | 8211b9f | Autostart entry removed. `mv-notify-send` remains on-demand (callers: mv-airdrop, mv-notification-center); verified it still logs + forwards when invoked. |
| S-10 | **FIXED** (wired) | b9d16ba | Verdict: WIRE, not remove. Added genmon as panel plugin-7 (command `mv-hud`, 5 s) in both xfce4-panel.xml mirrors. One-shot C tool matches §7 (no daemon, no polling loop); xfce4-genmon-plugin was already in the ISO list; Makefile already builds/installs mv-hud. Cost: one short-lived C process per 5 s. |
| S-11 | **FIXED** | edd2eec | mv-about `self.tv` assignment moved before `select_path`. Empirical tree-wide sweep (headless launch of every mv-*) found 6 more startup crashes, all fixed: mv-diskutil (`pack_empty_state` wrong receiver), mv-mail + mv-photos (invalid GTK3 CSS `text-transform`/`text-align` killed the whole stylesheet), mv-power-ui (`Gtk.WindowTypeHint` is GTK4; correct is `Gdk.WindowTypeHint`), mv-textedit (`SearchContext.new(self.buffer)` before `self.buffer` exists). Additionally unmasked in mv-control (fixed in 14c8009): `pack_start` on `Gtk.ListBox`, and `refresh_power_mode`'s `set_active` firing `changed` during init → modal `dialog.run()` blocked startup forever. Post-fix sweep: zero tracebacks. |
| S-12 | **ACCEPTED** (no change) | — | Extensionless launchers are a deliberate convention (all 37 mv-* tools, Makefile install loop keys on it, tests load via importlib path). Renaming risks breaking tooling that keys on extensionless names for zero runtime gain; the "audit/repair risk" is mitigated by this disposition + the fact that check-sync gates `py_compile` via shebang gating. |

**Host-measurability note:** all S-01/S-02/S-03/S-04/S-10 effects are
GUI-tier or call-frequency changes — not host-measurable (no X
interaction in harness, and per-call costs do not change). See
`docs/BENCHMARKS.md` phase-B change log for the honest delta table
(run-to-run variance on this shared WSL2 host dwarfs the before/after
delta; stable CPU scenarios S15/S16 moved ≤0.8%).

## Phase-D dispositions (2026-09-27, commits on master)

| ID | Disposition | Commit | Notes |
|---|---|---|---|
| D-01 TOOLING | **FIXED** | c359ab0 | S02/S03 display-leak: children inherited the host Wayland env → 23 GTK apps × 5 s mainloop kills (127 s S03 wall). `headless_env()` pins `GDK_BACKEND=x11` + strips DISPLAY. S02 −11%, S03 median −20%, mainloop-reached 23→0; before/after pairs comparable across host display states. |
| D-02 HYGIENE | **FIXED** | 2ae61e6 | 20 provably-unused imports removed across 15 apps (AST audit: zero refs, no star-imports, no `__all__`, no dynamic usage). Host-measurable effect ≈ 0 (removed gi modules already loaded by Gtk — consistent with the phase-C import breakdown); cold-target effect per the D-03 proxy. 1233/1233 green. |
| D-03 MEASUREMENT | **PROXY ADOPTED** | — | Cold-import approximation without root: `fadvise(DONTNEED)` eviction of the 113 libs mapped by the import, interleaved 5-rep warm/cold. Cold Gtk import +0.21 s (+63%) warm→cold on this host. Caveats: best-effort eviction, WSL page cache ≠ NVMe, python/libc stay warm. Not a watt predictor; quantifies the cold-target tier. |
| D-04 BROWSER | **HW-DEFERRED** | ec4dad4 | No browser on host (9 names checked: firefox, firefox-esr, epiphany, icecat, chromium, google-chrome, brave, edge, web — none found; offline discipline, no install). S14 skip reason records the exact absence. HW will show: headless startup + file:// page-load wall, HD615 render behavior. |

**Host-measurability note (phase D):** the only host-measurable wins are
harness comparability (D-01) and the S02/S03 import-path reduction it
exposed (−11%/−20%). D-02's warm-host effect is ≈ 0 by construction; its
value is cold-target, quantified via D-03. Everything else the track touched
in phases B–D remains GUI-tier or call-frequency (see phase-B note above).

## Phase-E re-audit (2026-09-27, commits on master)

> Criteria: `docs/PERF_CRITERIA.md`. Full re-audit with the GUI tier now
> measurable (X server on :0). Every suspect carries a P-label + the
> measurement that justifies it.

### Suspect table with P-labels

| ID | Location | Finding | P-label | Measurement |
|---|---|---|---|---|
| S-01 | `mv-control:63,82` | Wi-Fi refresh timers | **P2** | Fixed in phase B (signal-driven + 30 s fallback). Window-open-only. |
| S-02 | `mv-console:464` | Follow mode timer | **P2** | Fixed in phase B (persistent `journalctl -f` + IO watch). Window-open-only. |
| S-03 | `mv-music:953,1469` | Backend refresh + retry timers | **P2** | Fixed in phase B (off-thread MPRIS). 1 s refresh, 2 s retry. Window-open-only. |
| S-04 | `mv-colormeter:441` | Screen sampling timer | **P2** | Fixed in phase B (100 ms → 200 ms). 5 Hz is smooth under loupe. Window-open-only. |
| S-05 | `mv-activity:96` | Activity refresh timer | **P2** | 2 s pure `/proc` reads, window-open-only. Allowed by AGENTS.md §7. |
| S-06 | `mv-control:389,465,475,485` | BT refresh timers | **P2** | Fixed in phase B (5 s steady state + event-driven one-shots). Window-open-only. |
| S-07 | `mv-power-ui:458` | Countdown tick | **P2** | 1 Hz countdown UI (must stay 1 Hz for smooth countdown). UPower read once at open. |
| S-08 | `mv-textedit:101` | Autosave timer | **P2** | 30 s autosave, window-open-only. Same class as Firefox sessionstore (60 s). |
| S-09 | autostart/mv-notify-send | Autostart entry | **IGNORE** | Fixed in phase B (entry removed). On-demand tool. |
| S-10 | `bin/mv-hud.c` | HUD not wired | **IGNORE** | Fixed in phase B (wired into panel genmon). One-shot C tool. |
| S-11 | `mv-about:138` + 6 more | Startup crashes | **IGNORE** | Fixed in phase B (7 startup crashes fixed). Zero tracebacks post-fix. |
| S-12 | all `bin/mv-*` | Extensionless launchers | **IGNORE** | Deliberate convention (37 tools). No runtime cost. |
| E-01 | `mv-diskutil` G02 | 996 KB RSS growth over 20 cycles | **P2** | One-time GTK/UDisks2 caching, not a linear leak. Inconsistent across runs (0 KB in repeat). Plateaus after initial allocation. |
| E-02 | `mv-dictionary:506` | Search debounce timer | **P2** | 300 ms debounce (UX-needed). No backend cost per tick. |
| E-03 | `mv-mail:72` | Launch timer | **P2** | 100 ms one-shot (launch geary). No repeating cost. |
| E-04 | `mv-notes:582` | Refresh timer | **P2** | Window-open-only. No backend cost. |
| E-05 | `mv-photos:1064` | Slideshow timer | **P2** | User-controlled (3 s interval). Window-open-only. |
| E-06 | `mv-voice:200,602,697` | Animation timers | **P2** | 60/100/200 ms UI animation (cassette, level meter, playback). Window-open-only. |
| E-07 | `mv-preview:41` | Quit timer | **IGNORE** | 100 ms one-shot (headless test). No repeating cost. |
| E-08 | `mv-shot:147` | Timeout timer | **IGNORE** | One-shot screenshot timeout. No repeating cost. |
| E-09 | `mv-diskutil` sync D-Bus | UDisks2 `call_sync` | **P2** | Action handlers (mount/unmount/eject), not timers. Window-open-only. |
| E-10 | `mv-control` sync D-Bus | NM/BlueZ `call_sync` | **P2** | Refresh functions called from timers (5 s). Window-open-only. |
| E-11 | `mv-keychain` sync D-Bus | Secret `get_sync` | **P2** | Action handlers (load/unlock). Window-open-only. |
| E-12 | all apps | `while True` loops | **IGNORE** | Only mv-notes:65 (string search) + mv-photos:101 (JPEG parser). One-shot algorithmic. |
| E-13 | all apps | GFileMonitor/inotify | **IGNORE** | None found in custom code. |
| E-14 | autostart | Autostart entries | **IGNORE** | Only plank (KEEP — dock). mv-notify-send removed in S-09. |

### GUI-tier measurements (G01-G05, X server on :0)

| Scenario | Metric | Value | P-label | Threshold |
|---|---|---|---|---|
| G01 | window create/show/hide/destroy | 3.6-3.9 ms median | **P2** | — |
| G02 | memory growth (20 cycles) | 0-4 KB (except E-01) | **P2** | <100 KB |
| G03 | event-loop latency p50/p99 | 1.5/2.6 ms | **P2** | <5/20 ms |
| G04 | notification logging (50x) | 0.13-0.48 s | **P2** | — |
| G05 | startup-to-first-draw | 0.24-0.30 s | **P2** | <0.5 s |

### Re-audit verdict

**0 P0, 0 P1 suspects.** All suspects are P2 (below host drift band,
cosmetic, accepted-with-reason) or IGNORE (synthetic-only, no user-visible
path). The performance track has reached its stopping criteria
(`docs/PERF_CRITERIA.md`): no interactive latency regression, no background
wakeup/rescan class, no crash/leak with growth >threshold, no startup >0.5 s
cold-proxy-measured, no timer faster than UX needs with backend cost.
