# PROFILE_COUPLING.md — Generic-vs-MacBook10,1 Coupling Map

**Source of truth:** This document identifies every file/key that is MacBook10,1-specific vs generic-with-fallback, and classifies coupling as ISOLATED / ENTANGLED / GENERIC-OK.

**Conventions:**
- **ISOLATED**: MacBook-specific config in dedicated file(s); no generic fallback needed; removing file disables feature cleanly.
- **ENTANGLED**: MacBook-specific keys coexist with generic keys in shared file; changing one may affect generic behavior.
- **GENERIC-OK**: No MacBook-specific content; works on any hardware; kept for completeness.

---

## 1. Wi-Fi (Broadcom BCM43602)

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `configs/network/99-mavericks.conf` | `wifi.backend=wpa_supplicant` | ENTANGLED | Pins NM backend; generic but chosen for BCM43602 FullMAC support (P2P/AP/hidden). Fallback: iwd exists in ISO but not pinned. |
| `archiso-profile/releng/airootfs/etc/modprobe.d/broadcom-wl.conf` | (commented blacklist overrides) | ISOLATED | Empty active content; enables `broadcom-wl-dkms` experiment. Fallback: brcmfmac in baseline. |
| `archiso-profile/releng/airootfs/etc/modprobe.d/99-mavericks.conf` | (no active options) | GENERIC-OK | Baseline intentionally empty; `brcmfmac` is kernel default. |
| `scripts/install/extract-brcmfmac-nvram.sh` | `brcmfmac43602-pcie.txt`, `macaddr=` | ISOLATED | First-boot NVRAM provisioning. Template installs placeholder; **verify fallback EXISTS**: EFI NVRAM path detected via `dmesg | grep "Using nvram EFI variable"` — if present, script exits 0 without writing placeholder. |
| `apply-hardware-selection.sh` (lines 26-47) | `WIFI_DRIVER` selection logic | ISOLATED | Runtime detection: `lspci -nn -d 14e4:` revision check. Fallback: `brcmfmac` (line 46). |

### Classification: **ENTANGLED** (NM config) + **ISOLATED** (NVRAM/modprobe/experiments)
**Fallback verified**: Yes — `brcmfmac` in baseline packages + EFI NVRAM detection in extract script.

---

## 2. Bluetooth

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `apply-hardware-selection.sh` (lines 60-69) | `BT_DRIVER` selection logic | ISOLATED | Runtime: `btmgmt info` controller detection. Fallback: `in-kernel` (line 65) + `bluez/bluez-utils` always installed. |
| `archiso-profile/releng/packages.x86_64` | `bluez`, `bluez-utils` | GENERIC-OK | Always installed; no MacBook-specific config. |
| `packages/mavericks-apps/src/mavericks-apps/config/mv-control-center.desktop` | (launch entry) | GENERIC-OK | Generic UI; no HW-specific keys. |

### Classification: **ISOLATED** (detection logic) + **GENERIC-OK** (packages/UI)
**Fallback verified**: Yes — kernel btusb + bluez always present; no MacBook-specific modprobe.

---

## 3. Audio (Cirrus Logic CS4208)

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `packages/macbook12-audio-driver/99-macbook12-audio.conf` | (no active options) | ISOLATED | Intentionally empty; A1534 init unconditional in DKMS driver. Documents that `model=macbook12` was no-op, `power_save` duplicated TLP. |
| `packages/macbook12-audio-driver/51-macbook-cs4208-softvol.conf` | `monitor.alsa.rules` → `api.alsa.soft-mixer=true` | ISOLATED | WirePlumber rule for software volume on internal speakers. Device match: `alsa_card.pci-0000_00_1f.3` — **MacBook-specific PCI address**. Fallback: none needed (rule only applies if device present). |
| `packages/macbook12-audio-driver/PKGBUILD` | `dkms`, kernel source deps | ISOLATED | DKMS package; builds against running kernel. |
| `apply-hardware-selection.sh` (lines 49-58) | `AUDIO_DRIVER` selection logic | ISOLATED | Runtime: `speaker-test` → if fails, installs `macbook12-audio-driver`. Fallback: "none" (line 54) — works out of box on some revisions. |
| `archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks.conf` | (no audio-specific keys) | GENERIC-OK | TLP 1.9.1 defaults: `SOUND_POWER_SAVE_ON_AC=1`, `SOUND_POWER_SAVE_ON_BAT=1`, `SOUND_POWER_SAVE_CONTROLLER=Y` — applied by TLP, not hardcoded here. |

### Classification: **ISOLATED** (DKMS package + WirePlumber rule + runtime detection)
**Fallback verified**: Yes — `speaker-test` runtime check; TLP defaults handle power save generically.

---

## 4. NVMe / Apple S3X Controller

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `configs/profiles/production.conf` (line 7) | `pcie_port_pm=off` in CMDLINE | ENTANGLED | **Provisional workaround** for Apple S3X resume. Shared kernel cmdline — affects all PCIe. Fallback test: E2 experiment tests removal. |
| `configs/profiles/baseline.conf` (line 4) | Same `pcie_port_pm=off` | ENTANGLED | Baseline canonical; same as production. |
| `configs/profiles/experiments/E2-pcie-pm-on.cmdline` | (test removal) | ISOLATED | Experiment to validate if workaround still needed. |
| `tools/diagnostics/mv-collect.sh` (lines 63-66) | `nvme smart-log`, `default_ps_max_latency_us`, `pcie_aspm/policy` | GENERIC-OK | Read-only diagnostics; no config writes. |
| `archiso-profile/releng/packages.x86_64` | `nvme-cli` | GENERIC-OK | Generic tool. |

### Classification: **ENTANGLED** (kernel cmdline workaround shared with generic PCIe)
**Fallback verified**: E2 experiment exists to test removal; no MacBook-specific modprobe or udev rules.

---

## 5. SPI / applespi (Keyboard + Trackpad)

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `archiso-profile/releng/airootfs/etc/mkinitcpio.conf.d/archiso.conf` | `MODULES=(... applespi spi_pxa2xx_platform intel_lpss_pci intel_lpss_acpi)` | ENTANGLED | Initramfs modules — affects boot on ALL hardware. MacBook-specific modules mixed with generic. |
| `apply-hardware-selection.sh` (lines 71-96, 169-175) | `SPI_DRIVER` selection + `MKINITCPIO_MODULES` rewrite | ENTANGLED | Runtime strategy selection (3 strategies + skip). Rewrites `/etc/mkinitcpio.conf` MODULES line — **modifies generic config**. |
| `scripts/install/mavericks-firstboot.sh` | (not found in search) | — | Checked: no separate firstboot for SPI. |

### Classification: **ENTANGLED** (initramfs modules + mkinitcpio rewrite)
**Fallback verified**: Strategy 4 = "Skip (use external USB-C input)" — explicit external input fallback documented and mandatory per HARDWARE.md.

---

## 6. Power / TLP

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `configs/profiles/baseline.conf` (line 8) | TLP settings documented | GENERIC-OK | Documents baseline; no active config file. |
| `archiso-profile/releng/airootfs/etc/tlp.d/99-mavericks.conf` | `CPU_SCALING_GOVERNOR_ON_AC/BAT=powersave`, `PCIE_ASPM_ON_AC/BAT=powersave`, `USB_AUTOSUSPEND=1`, `RUNTIME_PM_ON_AC/BAT=auto` | ENTANGLED | **MacBook-tuned but generic keys** — powersave governor/ASPM chosen for fanless Core M. Works on any laptop. No MacBook-specific keys. |
| `configs/profiles/experiments/E8-epp.conf` | `CPU_ENERGY_PERF_POLICY_*` | ISOLATED | Experiment only; not in baseline. |
| `configs/profiles/experiments/E9-usb-nosuspend.conf` | `USB_AUTOSUSPEND=0` | ISOLATED | Experiment only. |
| `apply-hardware-selection.sh` (lines 206-209) | `systemctl enable --now tlp` | GENERIC-OK | Generic service enable. |

### Classification: **ENTANGLED** (tuned generic keys in shared TLP config) + **ISOLATED** (experiments)
**Fallback verified**: TLP defaults work on any hardware; experiments are opt-in.

---

## 7. Display / Backlight

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `configs/profiles/production.conf` (line 10) | `i915.enable_psr=0` in CMDLINE | ENTANGLED | Diagnostic-safe default for i915 Panel Self-Refresh. Shared kernel cmdline. |
| `configs/profiles/baseline.conf` (line 4) | Same `i915.enable_psr=0` | ENTANGLED | Baseline canonical. |
| `configs/profiles/experiments/E4-psr1.cmdline` / `E5-psr2.cmdline` / `E6-fbc-force.cmdline` | PSR/FBC enable experiments | ISOLATED | Opt-in experiments. |
| `tools/diagnostics/mv-collect.sh` (lines 35-38) | Reads `enable_psr`, `enable_fbc`, `enable_guc` | GENERIC-OK | Read-only diagnostics. |
| `archiso-profile/releng/packages.x86_64` | `intel-media-driver`, `mesa-utils` | GENERIC-OK | Generic Intel GPU packages. |

### Classification: **ENTANGLED** (kernel cmdline i915 params) + **ISOLATED** (experiments)
**Fallback verified**: Experiments E4/E5/E6 test enabling; baseline is conservative default.

---

## 8. Firmware / NVRAM / EFI

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `archiso-profile/releng/efiboot/loader/entries/*.conf` | `options root=PARTUUID=%ROOT_PARTUUID% rw rootflags=subvol=@ $BASELINE_OPTS` | ENTANGLED | Bootloader entries reference MacBook-specific PARTUUID placeholder; `BASELINE_OPTS` includes `pcie_port_pm=off i915.enable_psr=0`. |
| `apply-hardware-selection.sh` (lines 179-195) | Generates `mavlinos-macbook.conf` / `mavlinos-lts.conf` | ISOLATED | Only created if SPI strategy 2/3 chosen (kernel swap). |
| `scripts/install/extract-brcmfmac-nvram.sh` | EFI NVRAM detection | ISOLATED | See Wi-Fi section. |
| `archiso-profile/releng/airootfs/etc/mkinitcpio.d/linux-zen.preset` | Standard preset | GENERIC-OK | Generic. |

### Classification: **ENTANGLED** (bootloader cmdline) + **ISOLATED** (kernel-swap entries + NVRAM)
**Fallback verified**: Baseline entries work generically; kernel-swap entries only created on explicit strategy choice.

---

## 9. Thermal

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `tools/diagnostics/mv-thermal.sh` | `stress-ng`, `turbostat` readout | GENERIC-OK | Read-only sustained-load test; no config. |
| `tools/diagnostics/mv-power.sh` | `turbostat`, battery sysfs reads | GENERIC-OK | Read-only power measurement. |
| `configs/profiles/experiments/E1-turbo-off.cmdline` | `intel_pstate.no_turbo=1` | ISOLATED | Experiment only; not in baseline. |
| `archiso-profile/releng/packages.x86_64` | `thermald` **absent**, `stress-ng`, `turbostat` | GENERIC-OK | thermald explicitly excluded per DECISIONS.md. |

### Classification: **GENERIC-OK** (diagnostics) + **ISOLATED** (experiments)
**Fallback verified**: No thermal daemon in baseline; diagnostics work on any Intel hardware.

---

## 10. UCM (ALSA Use Case Manager) / Audio Profiles

### Files + Keys
| File | Key(s) | Type | Notes |
|------|--------|------|-------|
| `packages/macbook12-audio-driver/` | DKMS driver provides UCM profiles | ISOLATED | DKMS package installs UCM configs for CS4208. Not in baseline ISO. |
| `archiso-profile/releng/packages.x86_64` | `alsa-utils`, `pipewire`, `wireplumber` | GENERIC-OK | Generic audio stack; UCM profiles from kernel/alsa-ucm-conf. |

### Classification: **ISOLATED** (DKMS package) + **GENERIC-OK** (base audio stack)
**Fallback verified**: Base PipeWire/WirePlumber + kernel UCM works generically; MacBook-specific UCM only via optional DKMS package.

---

## Summary Matrix

| Subsystem | Classification | MacBook-Specific Files | Generic Fallback Exists? |
|-----------|----------------|------------------------|--------------------------|
| Wi-Fi | ENTANGLED + ISOLATED | 5 files | ✅ brcmfmac baseline + EFI NVRAM |
| Bluetooth | ISOLATED + GENERIC-OK | 1 detection script | ✅ in-kernel btusb + bluez |
| Audio | ISOLATED | 3 files (DKMS + WirePlumber + detection) | ✅ speaker-test runtime check + TLP defaults |
| NVMe/S3X | ENTANGLED | 1 kernel cmdline key (shared) | ✅ E2 experiment tests removal |
| SPI/applespi | ENTANGLED | 2 files (initramfs + detection+rewrite) | ✅ Strategy 4 = external USB-C input |
| Power/TLP | ENTANGLED + ISOLATED | 1 tuned config + experiments | ✅ TLP defaults generic |
| Display/Backlight | ENTANGLED + ISOLATED | 1 kernel cmdline key + experiments | ✅ Experiments test enable |
| Firmware/NVRAM/EFI | ENTANGLED + ISOLATED | Bootloader cmdline + kernel-swap entries | ✅ Baseline entries generic |
| Thermal | GENERIC-OK + ISOLATED | Experiments only | ✅ No daemon; read-only tools |
| UCM | ISOLATED + GENERIC-OK | DKMS package only | ✅ Kernel/alsa-ucm-conf generic |

---

## Coupling Counts

- **ISOLATED**: 6 subsystems (Wi-Fi NVRAM/modprobe, Bluetooth detection, Audio DKMS+WirePlumber, SPI detection, Firmware kernel-swap, Thermal experiments, UCM DKMS)
- **ENTANGLED**: 5 subsystems (Wi-Fi NM backend, NVMe cmdline, SPI initramfs, Power TLP tuned keys, Display i915 cmdline, Firmware bootloader cmdline)
- **GENERIC-OK**: 4 subsystems (Bluetooth packages, NVMe tools, Thermal diagnostics, UCM base stack, Display packages)

**Total MacBook-coupled files/keys: ~22** (across 10 subsystems)

---

## Gate Checklist

- [x] Zero hardcoded `/home/builder` paths in tracked files (verified: sanitized to `$REPO_ROOT`/`$HOME`)
- [x] Every MacBook-specific key has documented fallback or experiment
- [x] No ENTANGLED config lacks a path to generic behavior (experiments or runtime detection)
- [x] ISOLATED components removable without breaking generic boot
- [x] `bash -n` passes on all modified `.sh` files (no modifications made in this task)