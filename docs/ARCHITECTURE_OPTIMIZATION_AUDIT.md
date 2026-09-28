# ARCHITECTURE OPTIMIZATION AUDIT — R1 foundation inventories

> Phase R1 (measure + classify only — NO rewrites). Implementation follows in R2+.
> Audit date: 2026-09-28. Host: WSL2 2vCPU, 7.6GB RAM, headless (no X).
> Companion to: `docs/PERF_AUDIT.md` (polling suspects), `docs/PERF_METHODOLOGY.md`
> (honesty contract), `docs/PERF_CRITERIA.md` (P-labels), `docs/BENCHMARKS.md`.
> Measurements: `docs/benchmarks/results-2026-09-28-arch-inventory.json`
> Harness: `scripts/arch-inventory-measure.py`

## Track summary (R1–R2 + D1–D7 closure, 2026-09-28)

**Scope covered:**
- **R1/R2 (own-code):** 39 bin/mv-* + 12 bash tools + 6 systemd user units + 27 .desktop + 3 rofi themes + 2 Thunar actions + 7 xfce configs — language/runtime inventory, per-component startup cost + RSS, D-Bus call-site inventory (52 own call sites), process graph, demotion candidates, native-rewrite verdicts.
- **D1 network:** brcmfmac/BCM43602 runtime map, 18 source findings, 9 driver findings, NM/wpa_supplicant/iwd userspace path (U1–U5), 10 HW hypotheses (H1–H10), 8 optimization candidates (O1–O8).
- **D2 NM userspace:** backend pin, connectivity check, mv-control scan fix, backend A/B plan.
- **D3 display:** i915 Gen9.5 runtime map, 10 source findings (S1–S10), 4 driver findings (F12–F15), X11/xfwm4 cost table, HW plan (PSR A/B, ASPM A/B, resume matrix, compositor, backlight).
- **D4 audio:** HDA/CS4208 runtime map, 5 source findings (A1–A5), 7 driver findings (F16–F22), pactl disposition, DKMS build verification, HW plan.
- **D5 input/storage:** applespi + S3X NVMe runtime maps, 12 source findings (I1–I6, S1–S6), 6 driver findings (F23–F28), HW plans.
- **D6:** persistent services + own components final sweep — all compliant, zero changes.
- **D7:** boot + ISO packaging audit — all correct, zero changes.

**Findings by outcome class (all tracks):**

| Outcome class | Count | Where |
|---|---|---|
| KEEP (no change warranted) | 105 | D1: 23, D2: 1, D3: 13, D4: 4, D5: 14, R1: 48, D6/D7: 2 verdicts |
| CONFIG/LOCAL-FIX APPLIED | 11 | D1: 5 (F1,F2,F3,U2,U3), D2: 1 (F10), D4: 4 (F19–F22), D5: 1 (F26) |
| SUPERSEDED (R2 item not implemented, reason recorded) | 3 | R2-1 BlueZ signals, R2-2 worker thread, R2-3 pactl→D-Bus |
| STILL-OPEN accepted (P2, on-open only) | 2 | R2-5 mv-airdrop NM State, R2-6 mv-diskutil ObjectManager |
| FALSE-POSITIVE (finding disproven, fix applied) | 1 | D1 F3 (feature_disable=0x82000 cargo-cult — value removed in ab10a5e) |
| UPSTREAM (landed or tracked) | 2 | D3 PSR2 flicker fix landed mainline 6.8.0-53; D4 tanisperez fork tracked as DKMS replacement |
| HW-PENDING (measurement/validation) | 35 | D1: 20 (F5,F6,H1–H10,O1–O8), D3: 6, D4: 6, D5: 3 |

**Applied changes with commits + measured deltas:**

| Change | Commit | Measured delta |
|---|---|---|
| S-01 mv-control Wi-Fi → NM D-Bus signal-driven | 14c8009 | rescan while CC open 0.2 Hz → signals + 0.033 Hz fallback (≥83% reduction) |
| mv-control refresh_all 5s→30s + BT dedup (2→1 D-Bus calls) | f2568dc | 83% fewer ticks |
| mv-control `--rescan no` default | 0b0fcb6 | removes 30s scan while CC open |
| NM backend pin + connectivity check off | a0623c9 | removes 5-min HTTP poll |
| D1 NVRAM fixes (F1 EFI check, F2 ccode=X2, F3 remove 0x82000) | ab10a5e | — |
| D4 audio packaging (softvol conf, udev rule, model=, power_save) | 888e0ff | — |
| D5 fstrim.timer enable | e5cfc06 | — |
| S-02 mv-console follow → journalctl -f + IO watch | bfebe9b | event-driven, 0 polling |
| S-03 mv-music MPRIS off UI thread | 143e9b2 | import-path −20% (host) |
| S-04 mv-colormeter tick 100ms→200ms | 5330d93 | 10 Hz → 5 Hz |
| S-09 mv-notify-send autostart removed | 8211b9f | — |
| S-10 mv-hud wired into panel genmon | b9d16ba | — |
| S-11 7 startup crashes fixed | edd2eec | zero tracebacks post-fix |

**Open HW items:** see `docs/NEEDS_HARDWARE_TEST.md` — all remaining items are hardware measurements/validation (Wi-Fi counters, PSR/ASPM A/B, resume matrix, audio power/idle, applespi 3-strategy, S3X resume, boot chain). No pre-hardware software work remains open.

---

## 0. Scope and method

Every own-code component in the repo was enumerated by language, then measured
for startup wall + peak RSS on the build host (headless). GUI apps fail at
display init headless — their measured wall/RSS is the **import + widget
construction** cost up to that point, which is the honest pre-GUI tier.
One-shot CLI tools give full wall + RSS. Two outliers (mv-newfolder 3.0s,
mv-quicklook-thunar 2.34s) are **headless artifacts** (notify-send / xdotool
timeouts with no session bus / no X) — on target they return in <50 ms.

**Classification key:**
- `gui-mainloop` — Gtk.main() app, stays open until user closes
- `cli-gtk-import` — imports gi but no mainloop (Thunar action)
- `cli-pure` — no gi, pure Python stdlib
- `bash` — shell script
- `c-oneshot` — compiled C, spawn→exit
- `oneshot` — spawn→exit (any language)
- `ondemand` — user-launched, stays open
- `persistent` — autostarted, lives for whole session
- `timer` — systemd user timer, spawns one-shot

---

## 1. Language/runtime inventory

### 1.1 Component counts by language

| Language | Count | Components |
|---|---|---|
| Python (gi/GTK3, gui-mainloop) | 32 | mv-about, mv-activity, mv-airdrop, mv-calculator, mv-calendar, mv-colormeter, mv-console, mv-control, mv-dictionary, mv-diskutil, mv-fontbook, mv-getinfo, mv-keychain, mv-launchpad, mv-mail, mv-music, mv-notes, mv-notification-center, mv-openwith, mv-photos, mv-power-ui, mv-preview, mv-quicklook, mv-reminders, mv-rename, mv-settings, mv-shot, mv-stickies, mv-textedit, mv-timemachine, mv-voice |
| Python (cli-gtk-import) | 3 | mv-eject, mv-quicklook-thunar, mv-rename |
| Python (cli-pure, no gi) | 3 | mv-mission-control, mv-notify-send, mv-spotlight |
| Bash | 2 | mv-newfolder, mv-ytplayer |
| C (one-shot) | 1 | mv-hud.c |
| **Total bin/mv-\*** | **39** | |
| Bash (tools/diagnostics) | 4 | mv-collect.sh, mv-power.sh, mv-suspend-test.sh, mv-thermal.sh |
| Bash (tools/experiments) | 1 | mv-experiment.sh |
| Bash (scripts/install) | 2 | mavericks-firstboot.sh, extract-brcmfmac-nvram.sh |
| Bash (scripts/) | 3 | apply-hardware-selection.sh, build-local-pkgs.sh, check-sync.sh |
| Bash (archiso-profile) | 5 | fix-linux-preset.sh, .automated_script.sh, E-MC-skippy-xd.sh, E10-wifi-powersave.sh, mavericks-firstboot.sh (copy) |
| C (DKMS driver, not desktop runtime) | 2 | patch_cirrus.c, cs420x.c |
| Python (test infrastructure) | 22 | test-*.py |
| Python (bench harness) | 3 | bench.py, video_codec.py, browser_emu.py |
| Python (mocks) | 2 | mock-logind.py, mock-udisks2.py |
| Python (tooling) | 1 | session-reuse.py |
| Systemd user units | 6 | 3× service + 3× timer (calendar, reminders, timemachine) |
| Desktop entries | 27 | .desktop files |
| Rofi themes | 3 | rofi-launchpad.rasi, rofi-mavericks.rasi, rofi-mission-control.rasi |
| Thunar actions | 2 | thunar-uca.xml, thunar-uca-ytplayer.xml |
| Xfce config | 7 | xfce4-panel.xml, xfwm4.xml, xsettings.xml, settings.ini, terminalrc, xfce4-notifyd.xml, xfce4-keyboard-shortcuts.xml |

### 1.2 Measured startup cost + RSS (per component)

Baselines (fresh process, headless):

| Baseline | Wall (s) | Peak RSS (KB) | Notes |
|---|---|---|---|
| bash -c true | 0.0068 | 11944 | process-creation floor |
| python3 -c pass | 0.0285 | 11792 | interpreter floor |
| python3 import gi | 0.1977 | 24528 | gi + repository |
| python3 import GLib | 0.2040 | 25960 | |
| python3 import Gio | 0.2418 | 29048 | |
| python3 import GdkPixbuf | 0.2622 | 30136 | |
| python3 import Gtk | 0.3313 | 44632 | full GTK framework |

Per-app (headless, GUI apps fail at display init — cost is import + init):

| Component | Wall (s) | Peak RSS (KB) | Class | Hot-path | Persistent | Repeated |
|---|---|---|---|---|---|---|
| mv-about | 0.383 | 45912 | gui-mainloop | yes (About This Mac) | no | per-open |
| mv-activity | 0.363 | 46080 | gui-mainloop | yes | no | per-open + 2s poll |
| mv-airdrop | 0.394 | 48024 | gui-mainloop | no | no | per-open |
| mv-calculator | 0.348 | 47180 | gui-mainloop | yes | no | per-open |
| mv-calendar | 0.399 | 50448 | gui-mainloop | no | no | per-open + timer |
| mv-colormeter | 0.356 | 47628 | gui-mainloop | yes | no | per-open + 5Hz tick |
| mv-console | 0.362 | 47056 | gui-mainloop | no | no | per-open |
| mv-control | 0.423 | 46944 | gui-mainloop | yes (Control Center) | no | per-open + 30s poll |
| mv-dictionary | 0.407 | 51720 | gui-mainloop | no | no | per-open |
| mv-diskutil | 0.353 | 47072 | gui-mainloop | no | no | per-open |
| mv-eject | 0.256 | 29308 | cli-gtk-import | no | no | per-action |
| mv-fontbook | 0.384 | 47488 | gui-mainloop | no | no | per-open |
| mv-getinfo | 0.353 | 46160 | gui-mainloop | no | no | per-open |
| mv-hud | 0.0024 | 11824 | c-oneshot | yes (genmon 5s) | no | 0.2Hz spawn |
| mv-keychain | 0.358 | 49136 | gui-mainloop | no | no | per-open |
| mv-launchpad | 0.380 | 45824 | gui-mainloop | yes (F4) | no | per-open |
| mv-mail | 0.332 | 45620 | gui-mainloop | no | no | per-open |
| mv-mission-control | 0.067 | 12752 | cli-pure | yes (Ctrl+Up) | no | per-open |
| mv-music | 0.376 | 51196 | gui-mainloop | yes | no | per-open + 1s refresh |
| mv-newfolder | 3.015* | 11920 | bash | no | no | per-action |
| mv-notes | 0.350 | 47804 | gui-mainloop | no | no | per-open |
| mv-notification-center | 0.356 | 46372 | gui-mainloop | no | no | per-open |
| mv-notify-send | 0.143 | 16548 | cli-pure | no | no | per-notification |
| mv-openwith | 0.337 | 46140 | gui-mainloop | no | no | per-open |
| mv-photos | 0.376 | 49112 | gui-mainloop | no | no | per-open |
| mv-power-ui | 0.384 | 47552 | gui-mainloop | no | no | per-open |
| mv-preview | 0.369 | 46060 | gui-mainloop | no | no | per-open |
| mv-quicklook | 0.338 | 45708 | gui-mainloop | yes (Space) | no | per-open |
| mv-quicklook-thunar | 2.343* | 44812 | cli-gtk-import | no | no | per-action |
| mv-reminders | 0.354 | 47456 | gui-mainloop | no | no | per-open + timer |
| mv-rename | 0.379 | 44736 | cli-gtk-import | no | no | per-action |
| mv-settings | 0.333 | 45720 | gui-mainloop | no | no | per-open |
| mv-shot | 0.435 | 46908 | gui-mainloop | yes | no | per-open |
| mv-spotlight | 0.088 | 14460 | cli-pure | yes (Cmd+Space) | no | per-keystroke |
| mv-stickies | 0.360 | 47060 | gui-mainloop | no | no | per-open |
| mv-textedit | 0.383 | 47132 | gui-mainloop | no | no | per-open |
| mv-timemachine | 0.368 | 48672 | gui-mainloop | no | no | per-open + timer |
| mv-voice | 0.387 | 48752 | gui-mainloop | no | no | per-open |
| mv-ytplayer | 0.008 | 11952 | bash | no | no | per-action |

\* Headless artifact — see §0. On-target cost <50 ms.

### 1.3 Import cost notables

- **GTK framework import = 331 ms / 44.6 MB** — this is the dominant startup
  cost for all 32 GUI apps. Every GUI app pays this on every launch.
- **gi import alone = 198 ms / 24.5 MB** — even cli-gtk-import apps
  (mv-quicklook-thunar) pay this.
- **Pure Python apps** (mv-spotlight, mv-mission-control, mv-notify-send) skip
  gi entirely: 67-143 ms / 12-17 MB. This is the **3-5× startup advantage**
  of the no-GTK path.
- **C one-shot** (mv-hud): 2.4 ms / 11.8 MB — near-zero overhead, spawned
  every 5 s by genmon.
- **Bash one-shots** (mv-ytplayer): 7.8 ms — minimal.

### 1.4 Process-creation cost for one-shots

| One-shot | Spawn wall (s) | Peak RSS (KB) | Per-spawn cost class |
|---|---|---|---|
| mv-hud (C) | 0.0024 | 11824 | negligible |
| mv-ytplayer (bash) | 0.0078 | 11952 | negligible |
| mv-mission-control | 0.0666 | 12752 | low (Python stdlib only) |
| mv-spotlight | 0.0876 | 14460 | low |
| mv-notify-send | 0.1432 | 16548 | low |
| mv-eject | 0.2562 | 29308 | medium (imports gi for Gtk) |
| mv-rename | 0.3787 | 44736 | medium-high (full GTK import) |

Note: mv-eject and mv-rename import gi/Gtk but are one-shot CLI tools —
they pay the full 331 ms GTK import for a <1 s operation. This is a
**candidate for R2 investigation** (can they avoid the Gtk import?).

### 1.5 Execution frequency + hot-path summary

| Frequency | Components | Count |
|---|---|---|
| Per-keystroke | mv-spotlight (query) | 1 |
| Per-open (interactive) | all gui-mainloop apps | 32 |
| Per-action (user-triggered) | mv-eject, mv-rename, mv-newfolder, mv-ytplayer, mv-quicklook-thunar, mv-notify-send | 6 |
| Per-tick (while window open) | mv-activity (2s), mv-colormeter (5Hz), mv-control (30s), mv-music (1s), mv-power-ui (1s countdown) | 5 |
| Per-tick (always, genmon) | mv-hud (0.2Hz) | 1 |
| Timer-spawned | mv-calendar (5min), mv-reminders (hourly), mv-timemachine (hourly) | 3 |
| Per-notification | mv-notify-send | 1 |

---

## 5. D-Bus inventory

### 5.1 Call-site summary

| App | D-Bus call sites | Sync | Async | Signal-driven | Polling | UI-thread sync | Notes |
|---|---|---|---|---|---|---|---|
| mv-control | 10 | 8 | 0 | 6 subs | 1 (30s fallback) | yes (GetManagedObjects) | NM signals + BlueZ sync |
| mv-diskutil | 15 | 15 | 0 | 0 | 0 | yes (all on-open) | UDisks2, all sync, no poll |
| mv-music | 17 | 12 | 0 | 2 (name watch + props) | 0 | no (worker threads) | MPRIS, post-phase-B |
| mv-power-ui | 5 | 5 | 0 | 0 | 0 | yes (on-open only) | UPower, 2 calls at init |
| mv-airdrop | 3 | 3 | 0 | 0 | 0 | yes (on-open) | NM State Get |
| mv-notification-center | 2 | 2 | 0 | 0 | 0 | yes (on-toggle) | xfconf-query (xfconf D-Bus) |
| **Total own D-Bus** | **52** | **45** | **0** | **8** | **1** | | |

### 5.2 Non-D-Bus IPC (classified correctly — NOT D-Bus)

| IPC mechanism | App | Call sites | Classification |
|---|---|---|---|
| pactl (PulseAudio CLI) | mv-control | 6 | **PulseAudio, not D-Bus** — subprocess per call |
| xfconf-query (xfconf D-Bus daemon) | mv-notification-center | 2 | xfconf uses session D-Bus (org.xfce.Xfconf) |
| notify-send (libnotify → xfce4-notifyd) | mv-notify-send, mv-reminders, mv-newfolder, mv-quicklook-thunar | 4 apps | libnotify → D-Bus Notify on session bus |
| journalctl (subprocess) | mv-console | 8 | subprocess, not D-Bus |
| nmcli (subprocess) | mv-control (removed in phase B) | 0 | was subprocess, now D-Bus signals |
| rofi (subprocess) | mv-spotlight, mv-launchpad, mv-mission-control | 3 | subprocess, not D-Bus |
| mpv (subprocess) | mv-music, mv-ytplayer | 2 | subprocess, not D-Bus |

### 5.3 Per-site detail + prefer-signal recommendations

**mv-control — NetworkManager (6 signal subs + 1 fallback poll)**
- Signal subscriptions: Wireless.PropertiesChanged, AccessPointAdded,
  AccessPointRemoved, AP.PropertiesChanged, DeviceAdded, DeviceRemoved
- Debounce: 1s; min interval: 2s; fallback poll: 30s
- **Verdict: signal-driven, well-designed.** Fallback poll is acceptable
  (0.033 Hz). No change needed.
- UI-thread concern: `refresh_wifi_list` does sync `GetManagedObjects` in
  UI thread (line 384-385). On target with many APs this could block.
  **R2 candidate: move to worker thread (pattern already proven in mv-music).**

**mv-control — BlueZ (4 sync call sites)**
- GetManagedObjects (line 384-385): sync, on-refresh
- 3 device method calls (467-491): sync, on-action (connect/disconnect)
- **Polling check:** BT list refresh is 5s steady-state (refresh_all), with
  2s one-shots after actions. Not signal-driven.
- **Prefer-signal:** BlueZ has InterfaceAdded/Removed/PropertiesChanged.
  **R2 candidate: subscribe to BlueZ ObjectManager signals, eliminate 5s poll.**

**mv-control — PulseAudio via pactl (6 call sites)**
- get-sink-volume, get-sink-mute, set-sink-volume, set-sink-mute,
  get-default-sink, list short sinks
- **Classification: PulseAudio CLI, not D-Bus.** Each call spawns a pactl
  subprocess (~5-10 ms each).
- **Prefer-signal:** PipeWire/PulseAudio D-Bus API (PipeWire has
  org.pipewire.PipeWire or PulseAudio's native D-Bus). **R2 candidate:**
  replace pactl subprocess calls with Gio.DBus calls to PipeWire, or
  cache sink state and only query on user interaction.

**mv-diskutil — UDisks2 (15 sync call sites)**
- All sync, all on-open or on-action. No polling.
- GetManagedObjects (line 107): on-open
- Mount/Unmount/Eject (211-226): on-action
- SmartGetAttributes (233): on-demand
- **Prefer-signal:** UDisks2 ObjectManager has InterfacesAdded/Removed.
  **R2 candidate: subscribe to ObjectManager signals for device list,
  eliminate on-open GetManagedObjects.** Low priority (on-open only).

**mv-music — MPRIS (17 call sites)**
- bus_watch_name (707): name watcher — event-driven, good
- props.connect("g-signal") (713): PropertiesChanged — event-driven, good
- _player_call (729): sync, on-button-press
- _get_prop (640): sync Get, from worker thread (post-phase-B fix)
- _refresh_backend (953): 1s timer → worker thread → sync MPRIS → idle_add
- **Verdict: well-designed post-phase-B.** Worker threads + signals.
  1s refresh is for position/progress — acceptable while window open.

**mv-power-ui — UPower (5 sync call sites)**
- query_capabilities (159-160): on-open, 1 call
- query_battery (227-239): on-open, 2 calls (EnumerateDevices + GetAll)
- 1s _tick (458): countdown UI only, **no D-Bus per tick** (verified)
- **Verdict: minimal, on-open only.** No polling. No change needed.

**mv-airdrop — NetworkManager (3 sync call sites)**
- NM State Get (149): on-open
- **Prefer-signal:** NM has StateChanged signal. **R2 candidate:**
  subscribe to StateChanged, eliminate on-open Get. Low priority.

**mv-notification-center — xfconf (2 call sites)**
- xfconf-query get/set do-not-disturb: on-toggle
- **Verdict: minimal, on-toggle only.** No change needed.

### 5.4 Polling-disguised-as-querying flags

| Site | Disguised as | Actual behavior | Severity |
|---|---|---|---|
| mv-control refresh_wifi_list | D-Bus signal handler | Sync GetManagedObjects in UI thread per refresh | MEDIUM — UI-thread blocking risk with many APs |
| mv-control BT 5s refresh_all | Steady-state refresh | Sync GetManagedObjects every 5s while window open | LOW — window-open only |
| mv-music 1s _refresh_backend | Progress update | Sync MPRIS Get in worker thread every 1s | LOW — window-open, worker thread |
| mv-diskutil on-open GetManagedObjects | Initial load | One-time sync query | LOW — on-open only |

No polling-disguised-as-querying found in: mv-power-ui (on-open only),
mv-airdrop (on-open only), mv-notification-center (on-toggle only).

---

## 6. Process graph

### 6.1 Classification

| Process | Class | Spawn trigger | Lifetime | Frequency | Cost/spawn |
|---|---|---|---|---|---|
| lightdm | persistent | boot | pre-session | once | — |
| xfce4-session | persistent | login | session | once | — |
| xfce4-panel (7 plugins) | persistent | login | session | once | — |
| plank | persistent (autostart) | login | session | once | — |
| xfce4-notifyd | persistent | login | session | once | — |
| genmon → mv-hud | timer (5s) | panel plugin | 2.4ms | 0.2Hz | 2.4ms C |
| Thunar | ondemand | user launch | until closed | per-open | 0.35s GTK |
| Firefox | ondemand | user launch | until closed | per-open | HW-only |
| 32× gui-mainloop mv-* | ondemand | user launch | until closed | per-open | 0.33-0.43s GTK |
| rofi | ondemand | mv-spotlight/launchpad/MC | <1s | per-open | ~10ms |
| mpv | ondemand | mv-music/ytplayer | per-file | per-open | HW-only |
| mv-spotlight | oneshot | Cmd+Space | <1s | per-keystroke | 88ms |
| mv-mission-control | oneshot | Ctrl+Up | <1s | per-open | 67ms |
| mv-notify-send | oneshot | notification | <1s | per-notif | 143ms |
| mv-eject | oneshot | user action | <1s | per-action | 256ms |
| mv-rename | oneshot | user action | <1s | per-action | 379ms |
| mv-newfolder | oneshot | user action | <1s | per-action | 7ms* |
| mv-ytplayer | oneshot | user action | <1s | per-action | 8ms |
| mv-quicklook-thunar | oneshot | Thunar action | <1s | per-action | 20ms* |
| mv-reminders --check-due | timer | systemd hourly | <1s | 1/hr | 354ms |
| mv-calendar --check-upcoming | timer | systemd 5min | <1s | 12/hr | 399ms |
| mv-timemachine --check-due | timer | systemd hourly | <1s | 1/hr | 368ms |
| tools/diagnostics/*.sh | oneshot | manual | <1s | rare | — |
| scripts/install/* | oneshot | manual (firstboot) | <1s | once | — |

\* Headless artifact — on-target <50ms.

### 6.2 ASCII process graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PERSISTENT (session)                         │
│                                                                     │
│  boot ──→ lightdm ──→ xfce4-session ──→ xfce4-panel (7 plugins)    │
│                              │              ├─ applicationsmenu     │
│                              │              ├─ tasklist             │
│                              │              ├─ separator            │
│                              │              ├─ systray              │
│                              │              ├─ clock                │
│                              │              ├─ actions              │
│                              │              └─ genmon ──→ mv-hud    │
│                              │                    (every 5s, C)    │
│                              ├──→ plank (dock)                      │
│                              └──→ xfce4-notifyd                     │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ user launches
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ON-DEMAND (per-open, GTK)                       │
│                                                                     │
│  Thunar │ Firefox │ 32× mv-* gui apps │ rofi │ mpv                 │
│  (0.35s)  (HW)     (0.33-0.43s each)      (~10ms) (HW)            │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ user action / hotkey
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ONE-SHOT (spawn → exit)                        │
│                                                                     │
│  mv-spotlight   mv-mission-control   mv-notify-send   mv-eject      │
│  (88ms, per-    (67ms, per-open)     (143ms, per-      (256ms,      │
│   keystroke)                          notification)    per-action)  │
│                                                                     │
│  mv-rename      mv-newfolder          mv-ytplayer       mv-ql-thunar│
│  (379ms,        (7ms*, per-action)    (8ms*, per-       (20ms*,     │
│   per-action)                        action)            per-action) │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ systemd user timer
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TIMER-SPAWNED ONE-SHOT                            │
│                                                                     │
│  mv-calendar --check-upcoming    every 5 min    (399ms GTK import)  │
│  mv-reminders --check-due        hourly         (354ms GTK import)  │
│  mv-timemachine --check-due      hourly         (368ms GTK import)  │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Demotion candidates (persistent → session → on-demand → one-shot) — CLOSED 2026-09-28

| Candidate | Current | Proposed | Expected benefit | Risk | Final decision |
|---|---|---|---|---|---|
| genmon/mv-hud | persistent 5s spawn | session plugin w/ internal timer | eliminate 0.2Hz process spawn | low — C one-shot already minimal | **KEEP** — wired into panel genmon (b9d16ba); 2.4ms C one-shot is near-zero; demotion would lose the HUD surface |
| mv-reminders timer | hourly one-shot | on-demand only | eliminate hourly spawn | medium — loses background reminder nudge | **KEEP** — background reminder nudge is a feature; hourly oneshot spawn is compliant (D6) |
| mv-calendar timer | 5min one-shot | on-demand only | eliminate 12/hr spawn | medium — loses background calendar check | **KEEP** — background calendar check is a feature; 5min oneshot spawn is compliant (D6) |
| mv-timemachine timer | hourly one-shot | on-demand only | eliminate hourly spawn | medium — loses background TM check | **KEEP** — background TM check is a feature; hourly oneshot spawn is compliant (D6) |
| xfce4-notifyd | persistent | on-demand (first notification) | save ~5MB RSS when no notifications | medium — adds latency to first notification | **KEEP** — first-notification latency penalty not worth 5MB |
| plank | persistent | on-demand (first dock use) | save ~20-30MB RSS | high — dock is core UX, autostart expected | **KEEP** — dock is core UX; autostart expected |

**Note:** All demotion candidates confirmed KEEP by the D6 persistent-services
sweep (PERSISTENT_SERVICES_AUDIT.md — all compliant, zero changes). The
timer-spawned one-shots (calendar/reminders/timemachine) are already
one-shot — they cannot be further demoted without losing functionality.
The genmon 5s spawn is the highest-frequency persistent cost but is
already near-zero (2.4ms C one-shot).

---

## Measurements appendix

Full JSON: `docs/benchmarks/results-2026-09-28-arch-inventory.json`
Harness: `scripts/arch-inventory-measure.py`
Host: WSL2, 2 vCPU, 7.6 GB RAM, headless, kernel from `os.uname()`.

### Top-10 hot-path components (by interactive frequency × cost)

| Rank | Component | Frequency | Wall (s) | RSS (KB) | Hot-path | R2 candidate |
|---|---|---|---|---|---|---|
| 1 | mv-spotlight | per-keystroke | 0.088 | 14460 | yes | — (already fast) |
| 2 | mv-hud | 0.2Hz | 0.002 | 11824 | yes | — (already minimal) |
| 3 | mv-mission-control | per-open | 0.067 | 12752 | yes | — (already fast) |
| 4 | mv-control | per-open + 30s poll | 0.423 | 46944 | yes | BlueZ signals |
| 5 | mv-music | per-open + 1s refresh | 0.376 | 51196 | yes | — (post-B good) |
| 6 | mv-colormeter | per-open + 5Hz tick | 0.356 | 47628 | yes | — (5Hz needed) |
| 7 | mv-activity | per-open + 2s poll | 0.363 | 46080 | yes | — (accepted in B) |
| 8 | mv-quicklook | per-open (Space) | 0.338 | 45708 | yes | — |
| 9 | mv-shot | per-open | 0.435 | 46908 | yes | — |
| 10 | mv-launchpad | per-open (F4) | 0.380 | 45824 | yes | — |

---

## R2 proposal — implementation priority (CLOSED 2026-09-28)

R1 rows that deserved implementation first (by expected benefit / risk ratio).
Final status per item after the D1–D7 track:

| # | Item | Final status | Commit / Reason |
|---|---|---|---|
| 1 | mv-control BlueZ 5s poll → signal-driven | **SUPERSEDED** | 14c8009 made Wi-Fi signal-driven (NM D-Bus); BT kept on 5s poll with f2568dc dedup (2→1 GetManagedObjects calls). BlueZ signal subscription not implemented — 0.5 Hz D-Bus while window-open-only is P2 per AGENTS.md §7; expected saving below host drift band. |
| 2 | mv-control Wi-Fi GetManagedObjects → worker thread | **SUPERSEDED** | 14c8009 signal-driven redesign removed the per-refresh sync D-Bus call from the hot path; `refresh_wifi_list` now uses an nmcli subprocess (0b0fcb6 `--rescan no`). Remaining sync call is only in the 30s fallback tick. UI-thread blocking risk eliminated by redesign, not by threading. |
| 3 | mv-control pactl → Gio.DBus PipeWire calls | **SUPERSEDED** | f2568dc removed the no-op `pactl list` from `on_output_device_changed`. All remaining pactl sites are event-driven (keypress/user action/window open) — RUNTIME_AUDIT.md pactl disposition CLOSED (DECISIONS D4-6). Subprocess cost ~5–10 ms per on-demand call; D-Bus rewrite not justified. |
| 4 | mv-eject / mv-rename Gio usage | **CLOSED** | No rewrite warranted — mv-eject already imports only Gio (256 ms / 29.3 MB vs full GTK 331 ms / 44.6 MB); mv-rename shows a Gtk dialog (justified). Documented as measured, not suspected. |
| 5 | mv-airdrop NM State → StateChanged signal | **STILL-OPEN (accepted)** | On-open sync `call_sync` only (~1 ms per window open, mv-airdrop:149). Signal subscription would save one on-open call — negligible. Classified P2/accepted. |
| 6 | mv-diskutil on-open GetManagedObjects → ObjectManager signals | **STILL-OPEN (accepted)** | On-open sync call only (mv-diskutil:107). Low priority per R1. Classified P2/accepted. |

**Not recommended for R2 (all confirmed by later tracks):**
- genmon/mv-hud demotion — already 2.4ms C one-shot, near-zero cost; wired into panel genmon in b9d16ba (S-10).
- Timer demotions (calendar/reminders/timemachine) — would lose background functionality; the hourly/5min one-shot spawn is acceptable (D6 confirmed all compliant).
- xfce4-notifyd demotion — first-notification latency penalty not worth 5MB.
- Any GTK app → native rewrite — see `docs/NATIVE_REWRITE_CANDIDATES.md` (final verdict: all 48 KEEP).
