# MavLinOS

**MavLinOS is a Linux-based operating system whose user interface and user
experience are as close as technically possible to macOS Mavericks (10.9).**

Built on Arch Linux + Xfce, reusing mature Linux components wherever that is
reasonable. The goal is **not** a visual skin — it is the **Mavericks-era
interaction model**:

- window chrome and titlebar behavior
- the global menu bar and standard application menus
- the Dock (running-app indicators, magnification, trash)
- system applications: Finder, Spotlight, Launchpad, Mission Control,
  Control Center, Notification Center, Quick Look, System Preferences, and more
- dialogs, sheets, alerts and context menus
- animations and transitions
- keyboard shortcuts, including a global shortcut layer
- window management (spaces, minimize, zoom, fullscreen)
- notifications
- file management behavior (selection, drag-and-drop, Open With, Get Info,
  trash, eject)
- system interactions and application behavior
- the overall logic and *feel* of working in the system

**This is not:** a macOS clone, a GNOME/KDE theme, an icon pack, a visual
skin, an Electron app, or a "pretty Linux" distro. Linux internals stay
Linux — only the user-facing interaction layers follow Mavericks.

- **Repository:** https://github.com/AnsvipaRinh/MavLinOS
- **Public author:** Ansvipa_Rinh
- **License:** GPL-3.0-or-later (root `LICENSE`; per-package matrix in
  `docs/LICENSES.md`)

---

## Two goals

1. **Mavericks UI/UX fidelity** — the interaction model above, in the
   skeuomorphic 10.9 visual language (textures, gradients, glassy Dock),
   not modern flat macOS.
2. **Maximal practical optimization** — low resource usage, low power draw
   and fast interaction on weak hardware, including through specialized
   hardware profiles (see below).

---

## Architecture: generic core + hardware profiles

MavLinOS is explicitly split into two layers:

**Generic MavLinOS core** (machine-independent):

- common UI/UX and the Mavericks interaction model
- system applications
- themes (GTK/Xfce/Dock, icons, cursors)
- animations and transitions
- window management
- system integrations (D-Bus, systemd/logind, UDisks2, NetworkManager,
  BlueZ, PipeWire, …)
- general logic and performance architecture

**Hardware profiles** (machine-specific):

- CPU/GPU-specific tuning
- power management
- drivers and firmware integration
- input devices
- audio
- Wi-Fi/Bluetooth
- display
- storage
- thermal behavior
- boot/runtime configuration
- other machine-specific specifics

The current **MacBook10,1 (Mid 2017) profile is one specialized profile —
not the definition of the project.** Hardware-specific optimizations live in
profiles and must not pollute the generic core without necessity.

**Future:** a person with another computer (another MacBook or any other
compatible machine) can create a new hardware profile and get:
**MavLinOS core + their hardware profile → an optimized build for that
machine.** See `ARCHITECTURE.md` and `configs/profiles/`.

---

## Current implementation status (2026-10, pre-hardware)

| Layer | Status | Notes |
|-------|--------|-------|
| **Core desktop (P0)** | PARTIALLY IMPLEMENTED | Finder/Spotlight/Launchpad/Mission Control/Control Center/Notification Center/Quick Look/Dock/Menu Bar/Window Management/Global Dialogs/File Chooser/Context Menus/Keyboard Layer/Trash/Archive/Power UI — functional pre-hardware, hardware validation pending |
| **System apps (P1)** | PARTIALLY IMPLEMENTED | Activity Monitor, System Info, Disk Utility, Screenshot, TextEdit, Calculator, Notes, Reminders, Calendar, Music, Console, Keychain, Font Book, Color Meter, Stickies, Voice Memos — Mavericks UI over mature backends; HW validation pending |
| **P2 / Future** | DEFERRED / EXCLUDED | AirDrop, Time Machine UI, Automator/Shortcuts, Grapher, Migration Assistant, App Store, Software Update polish — explicitly not in scope for the current phase |
| **Excluded** | EXCLUDED | Contacts, TV, Podcasts, Siri, AirPlay, Chess, Game Center, dedicated Printer Discovery, Image Capture, Terminal replacement, mandatory account/password infra |

**Hardware-dependent items** (require real MacBook10,1): Wi-Fi (BCM43602),
audio (Cirrus CS42L83), applespi keyboard/trackpad, S3X NVMe resume,
display/brightness/thermal calibration, HiDPI pixel validation, power
measurements. See `docs/NEEDS_HARDWARE_TEST.md`. Native keyboard/trackpad
support (applespi) is best-effort; an external USB-C keyboard/mouse is the
recommended bring-up interface.

**No MacBook screenshots exist** (hardware not yet available). All UI claims
are pre-hardware implementation status only.

---

## Quick Start — Build ISO + Test

```bash
# 1. Build local packages (mavericks-apps, mavericks-theme, macbook12-audio-driver)
./scripts/build-local-pkgs.sh

# 2. Run pre-commit gate (144 checks: mirrors, syntax, security, ISO hardening)
./scripts/check-sync.sh --check-repos

# 3. Build ISO (requires root for mkarchiso; run on Arch host or CI)
sudo mkarchiso -v -w /tmp/archiso-build -o out/ archiso-profile/

# 4. Smoke test in QEMU+OVMF (UEFI, no KVM required)
qemu-system-x86_64 \
  -machine q35,accel=tcg \
  -cpu host \
  -m 4G \
  -bios /usr/share/edk2/x64/OVMF_CODE.fd \
  -drive file=out/mavericks-linux-*.iso,format=raw,if=virtio \
  -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
  -display gtk,gl=on
```

**QEMU tests:** Sim backend (rootless, deterministic) — 25/25 scenarios pass.
QEMU backend — 7/25 pass (network boot); command-channel scenarios blocked on
9p virtfs. Mac backend — documented stub only. See `docs/LAB_HARNESS.md`.

---

## Repository Structure

```
.
├── AGENTS.md                 # Autonomous agent instructions (this project's constitution)
├── archiso-profile/          # mkarchiso profile (UEFI, systemd-boot, ~750 pkgs)
├── configs/                  # Source configs (mirrored to archiso-profile by check-sync)
│   ├── desktop/              # Xfce, LightDM, Plank, Thunar, skippy-xd, fonts
│   ├── firefox/              # Firefox ESR userChrome.css + user.js (Mavericks Safari 7)
│   ├── mv-ytplayer/          # Codec policy for mpv+yt-dlp video path
│   ├── network/              # NetworkManager pin + connectivity off
│   └── profiles/             # Kernel cmdline profiles (baseline + 12 experiments)
├── docs/                     # All project documentation (see index below)
├── lab/                      # Remote lab control plane (agent + harness + 25 scenarios)
├── packages/                 # Arch packages (repo-local, no AUR in default ISO)
│   ├── mavericks-apps/       # 23 custom apps (mv-*) + desktop files + rofi themes
│   ├── mavericks-theme/      # GTK3/Xfce/Plank theme + icon + cursor (SCSS → CSS)
│   ├── macbook12-audio-driver/  # Cirrus CS42L83 DKMS (tanisperez fork, pinned)
│   └── epiphany-mavericks-theme/  # DEFERRED (not in ISO)
├── scripts/                  # Build, test, bench, install, diagnostics
├── tools/                    # Ad-hoc utilities
└── .opencode/                # Orchestrator + worker config (project-local)
```

---

## Documentation Index

| File | Purpose |
|------|---------|
| `AGENTS.md` | Autonomous agent constitution (read first) |
| `docs/HARDWARE.md` | MacBook10,1 spec + base config |
| `docs/PROGRESS.md` | Phase-by-phase implementation log |
| `docs/APPS.md` | 46-objective application inventory + statuses |
| `docs/NEEDS_HARDWARE_TEST.md` | Every item requiring real hardware |
| `docs/SAFARI_SPEC.md` | Firefox chrome CSS fidelity spec (498 lines, 142-check gate) |
| `docs/PERF_CRITERIA.md` | Optimization stopping rules (P0/P1/P2/IGNORE) |
| `docs/BENCHMARKS.md` | Measured deltas + calibration maps |
| `docs/KEYBOARD.md` | Global Super-layer shortcut map |
| `docs/DECISIONS.md` | Every non-obvious decision + rationale |
| `docs/LAB_HARNESS.md` | A/B deploy + 25 failure-injection scenarios |
| `CONTRIBUTING.md` | Contribution guide (this repo) |
| `SECURITY.md` | Threat model + review verdicts + responsible disclosure |
| `CODE_OF_CONDUCT.md` | Community rules (Contributor Covenant 2.1) |
| `ARCHITECTURE.md` | Layer diagram + profiles + lab harness |
| `docs/CONTRIBUTION_PROTOCOL.md` | End-to-end contribution flow (discovery → human merge) |
| `docs/SECURITY_MODEL.md` | Threat model, isolation guarantees, no-secrets-in-CI |
| `docs/VIBE_CODING.md` | External agent workflow |
| `docs/UI_UX_CONTRIBUTION.md` | Fidelity axes + completion criteria |
| `docs/GITHUB_SETUP.md` | First-time GitHub publish walkthrough |
| `docs/RELEASE_READINESS.md` | Pre-publication audit + publication procedure |
| `docs/LICENSES.md` | Full license matrix (all packages + backends) |

---

## Hardware profiles (OS-2c)

Two build profiles in `configs/profiles/` selected at ISO build time:

- **generic** — baseline Arch + Xfce + Mavericks theme, no MacBook drivers
- **macbook10,1** — + applespi, brcmfmac/broadcom-wl, Cirrus audio, S3X NVMe,
  `pcie_port_pm=off`, `i915.enable_psr=0`

Selector: `scripts/apply-hardware-selection.sh` (interactive, runs on first
boot). The generic profile is the clean core; the MacBook profile is the
reference hardware profile. New profiles follow the same separation rule:
**never add machine-specific configuration to the generic profile.**

---

## Contributing

Community participation is welcome across: **UI, UX, animations, window
management, applications, system integrations, performance, hardware profiles,
compatibility, documentation, testing, and tooling** — for example an animation
improvement, a window-behavior fix, a more precise Mavericks-like interaction,
an application improvement, or a hardware profile for a specific computer.

Public contributions are treated as **untrusted external input**: every
contribution passes the existing contribution/security/validation pipeline
(static security scan, classification, isolated build-agent testing, fidelity
and regression audit) before a human integration decision. **A community idea
can become part of the main MavLinOS codebase if it passes review and truly
fits the project goals — no contribution is accepted automatically.**

Start with `CONTRIBUTING.md` and `docs/CONTRIBUTION_PROTOCOL.md`.

---

## License

Project code: GPL-3.0-or-later (root `LICENSE`); per-package: GPL-2.0-or-later
(mavericks-apps), GPL-3.0-or-later (mavericks-theme). Full matrix:
`docs/LICENSES.md`. Upstream components retain their licenses (see
`docs/APPS.md` backend column). No Apple proprietary code/assets/resources.
Visual fidelity via reimplementation only.
