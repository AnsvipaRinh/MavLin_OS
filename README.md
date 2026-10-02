# Mavericks Linux — MacBook 12" (MacBook10,1) Desktop Environment

A Linux desktop that behaves and looks like **macOS Mavericks (10.9)** — skeuomorphic,
not modern flat macOS — built on Arch + Xfce + mature Linux backends. Target hardware:
**MacBook10,1 (Mid 2017, A1534)**, fanless Core m3-7Y32, 2304×1440 HiDPI, single USB-C.

**This is not:** a macOS clone, a GNOME/KDE theme, Electron-based, or a "pretty Linux" distro.
It is a Mavericks-era UX layer over standard Linux userspace.

---

## Status (2026-10-02, pre-hardware)

| Layer | Status | Notes |
|-------|--------|-------|
| **Core desktop (P0)** | PARTIALLY IMPLEMENTED | Finder/Spotlight/Launchpad/Mission Control/Control Center/Notification Center/Quick Look/Dock/Menu Bar/Window Management/Global Dialogs/File Chooser/Context Menus/Keyboard Layer/Trash/Archive/Power UI — functional pre-hardware, hardware validation pending |
| **System apps (P1)** | PARTIALLY IMPLEMENTED | Activity Monitor, System Info, Disk Utility, Screenshot, TextEdit, Calculator, Notes, Reminders, Calendar, Music, Console, Keychain, Font Book, Color Meter, Stickies, Voice Memos — Mavericks UI over mature backends; HW validation pending |
| **P2 / Future** | DEFERRED / EXCLUDED | AirDrop, Time Machine UI, Automator/Shortcuts, Grapher, Migration Assistant, App Store, Software Update polish — explicitly not in scope for current phase |
| **Excluded** | EXCLUDED | Contacts, TV, Podcasts, Siri, AirPlay, Chess, Game Center, dedicated Printer Discovery, Image Capture, Terminal replacement, mandatory account/password infra |

**Hardware-dependent items** (require real MacBook10,1): Wi-Fi (BCM43602), audio (Cirrus CS42L83), applespi keyboard/trackpad, S3X NVMe resume, display/brightness/thermal calibration, HiDPI pixel validation, power measurements. See `docs/NEEDS_HARDWARE_TEST.md`.

**No MacBook screenshots exist** (hardware not yet available). All UI claims are pre-hardware implementation status only.

---

## Quick Start — Build ISO + Test

```bash
# 1. Build local packages (mavericks-apps, mavericks-theme, macbook12-audio-driver)
./scripts/build-local-pkgs.sh

# 2. Run pre-commit gate (221 checks: mirrors, syntax, security, ISO hardening)
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
QEMU backend — 7/25 pass (network boot); command-channel scenarios blocked on 9p virtfs.
Mac backend — documented stub only. See `docs/LAB_HARNESS.md`.

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
| `docs/AGENTS.md` | Autonomous agent constitution (read first) |
| `docs/HARDWARE.md` | MacBook10,1 spec + base config |
| `docs/PROGRESS.md` | Phase-by-phase implementation log |
| `docs/APPS.md` | 46-objective application inventory + statuses |
| `docs/NEEDS_HARDWARE_TEST.md` | Every item requiring real hardware |
| `docs/SAFARI_SPEC.md` | Firefox chrome CSS fidelity spec (498 lines, 221-check gate) |
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
| `docs/RELEASE_READINESS.md` | Pre-publication audit + remaining user decisions |
| `docs/LICENSES.md` | Full license matrix (all packages + backends) |

---

## Profiles (OS-2c)

Two build profiles in `configs/profiles/` selected at ISO build time:

- **generic** — baseline Arch + Xfce + Mavericks theme, no MacBook drivers
- **macbook10,1** — + applespi, brcmfmac/broadcom-wl, Cirrus audio, S3X NVMe, `pcie_port_pm=off`, `i915.enable_psr=0`

Selector: `scripts/apply-hardware-selection.sh` (interactive, runs on first boot).

---

## License

Project code: GPL-3.0-or-later (root `LICENSE`); per-package: GPL-2.0-or-later (mavericks-apps), GPL-3.0-or-later (mavericks-theme). Full matrix: `docs/LICENSES.md`.
Upstream components retain their licenses (see `docs/APPS.md` backend column).
No Apple proprietary code/assets/resources. Visual fidelity via reimplementation only.