# Architecture

## Layer Diagram (Mavericks UI → Mature Backend → Kernel)

```
┌─────────────────────────────────────────────────────────────────┐
│  MAVERICKS-ERA USER EXPERIENCE (skeuomorphic, 10.9 fidelity)   │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ Finder       │ Spotlight    │ Launchpad    │ Mission Ctrl │  │
│  │ Control Ctr  │ Notif Center │ Quick Look   │ Preview      │  │
│  │ Settings     │ Activity Mon │ System Info  │ Disk Utility │  │
│  │ TextEdit     │ Calculator   │ Notes        │ Reminders    │  │
│  │ Calendar     │ Music        │ Photos       │ Voice Memos  │  │
│  │ Console      │ Keychain     │ Font Book    │ Color Meter  │  │
│  │ Stickies     │ Screenshot   │ Archive      │ Trash        │  │
│  │ Menu Bar     │ Dock         │ App Menu     │ Global Dlgs  │  │
│  │ File Chooser │ Context Menu │ Kbd Shortcuts│ Window Mgmt  │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  MATURE LINUX BACKENDS (reused, not rewritten)                 │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ Thunar/GVfs  │ rofi +       │ xfwm4        │ xfce4-panel  │  │
│  │ (file mgr)   │ plocate      │ (compositor) │ + plugins    │  │
│  ├──────────────┼──────────────┼──────────────┼──────────────┤  │
│  │ UDisks2      │ NetworkMgr   │ BlueZ        │ PipeWire/    │  │
│  │ (storage)    │ + wpa_sup.   │ (BT)         │ WirePlumber  │  │
│  ├──────────────┼──────────────┼──────────────┼──────────────┤  │
│  │ UPower       │ logind       │ GTK3/Pango/  │ poppler/     │  │
│  │ (power)      │ (session)    │ Cairo        │ GStreamer/   │  │
│  │              │              │ (rendering)  │ ffmpeg       │  │
│  ├──────────────┼──────────────┼──────────────┼──────────────┤  │
│  │ libsecret    │ libnotify/   │ xarchiver/   │ plank        │  │
│  │ (secrets)    │ xfce4-notifyd│ libarchive   │ (dock)       │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  LINUX USERSpace APIs                                           │
│  D-Bus • systemd/logind • UDisks2 • NetworkManager • BlueZ     │
│  PipeWire • UPower • GTK3 • X11 • /proc • /sys                 │
├─────────────────────────────────────────────────────────────────┤
│  KERNEL / HARDWARE (MacBook10,1 specific)                      │
│  linux-zen • applespi • brcmfmac/broadcom-wl • snd-hda-codec-  │
│  cs420x (Cirrus) • i915 (HD 615) • NVMe (Apple S3X) • USB-C    │
└─────────────────────────────────────────────────────────────────┘
```

**Principle:** Linux internals stay Linux. Only the top 2-3 interaction layers mimic Mavericks.

---

## Profiles Layout (`configs/profiles/`)

```
profiles/
├── baseline.conf          # generic: quiet loglevel=3
├── bootstrap.conf         # install ISO: +systemd-networkd +iwd +sshd +reflector
├── diagnostic.conf        # debug: loglevel=7 + initcall_debug
├── production.conf        # macbook10,1: +pcie_port_pm=off +i915.enable_psr=0
├── recovery.conf          # fallback: nomodeset + single
└── experiments/
    ├── E1-turbo-off.cmdline      # CPU boost disable
    ├── E2-pcie-pm-on.cmdline     # revert pcie_port_pm=off
    ├── E3-apst-off.cmdline       # NVMe APST disable
    ├── E4-psr1.cmdline           # i915.enable_psr=1
    ├── E5-psr2.cmdline           # i915.enable_psr=2
    ├── E6-fbc-force.cmdline      # i915.enable_fbc=1
    ├── E7-huc.cmdline            # i915.enable_huc=1
    ├── E8-epp.conf               # energy_perf_preference
    ├── E9-usb-nosuspend.conf     # USB autosuspend off
    ├── E10-wifi-powersave.sh     # Wi-Fi powersave script
    ├── E11-swappiness.conf       # vm.swappiness
    └── E12-writeback.conf        # dirty_writeback_centisecs
```

**Selector:** `scripts/apply-hardware-selection.sh` — interactive, runs on first boot, detects `dmidecode` product name, writes selected profile to `/etc/kernel/cmdline.d/99-mavericks.conf`, regenerates initramfs + bootloader.

---

## Lab Harness (`lab/`)

```
lab/
├── agent/
│   └── mavericks-lab-agent      # Single-file Python3 stdlib, SSH forced-command
├── harness/
│   ├── backends/
│   │   ├── sim_backend.py       # Rootless, deterministic (primary CI)
│   │   ├── qemu_backend.py      # QEMU+OVMF UEFI (ISO boot smoke)
│   │   └── mac_backend.py       # MacBook10,1 hardware (stub)
│   ├── scenarios/               # 25 YAML scenarios (A/B boot, 9 failure injections)
│   ├── runner.py
│   └── tests/test_harness.py    # 6 unit tests
├── host/
│   └── mavericks-lab            # Host CLI (local + SSH modes)
└── tests/                       # 7 standalone test scripts, 158 assertions
```

**Scenarios:** 01–10 (A-side boot + B-side deploy/boot/health/commit), 11–25 (agent lifecycle, host crashes, power loss, rollback, network flaps, idempotency).

**Backends:** `sim` (default, 25/25 pass), `qemu` (7/25 pass — network boot works; command-channel blocked on 9p virtfs), `mac` (stub).

**Results DB:** SQLite (`lab/host/store.db`) — queryable by scenario/result/limit.

---

## Custom Packages (`packages/`)

| Package | License | Purpose | In ISO |
|---------|---------|---------|--------|
| `mavericks-apps` | GPL-2.0+ | 23 apps (mv-*) + rofi themes + Thunar actions + hotkey layer | Yes |
| `mavericks-theme` | GPL-3.0+ | GTK3/Xfce/Plank theme + icon theme + cursor theme (SCSS→CSS) | Yes |
| `macbook12-audio-driver` | GPL | Cirrus CS42L83 DKMS (tanisperez fork, pinned commit) | No (manual post-install) |
| `epiphany-mavericks-theme` | GPL-3.0+ | Epiphany browser theme | No (deferred) |

All repo-local sources. `makepkg` via `scripts/build-local-pkgs.sh` → local pacman repo.

---

## Session / Orchestrator Note

This repository includes `.opencode/` with an **Orchestrator** agent (primary, restricted: no edit/write/bash/Task) and **Build** workers (`build` primary + `build-b`..`build-h` hidden fallbacks).

**External agents (OpenCode, Claude, Codex, Gemini, Cursor) use THEIR OWN setup.** Our `.opencode/` is a reference implementation of the autonomous loop (see `AGENTS.md` §14), not a requirement. You do not need OpenCode to contribute.

The Orchestrator loop: read state → select highest-priority unfinished objective → delegate to Build via Task → verify → commit → repeat. A commit is a checkpoint, not a stop condition.