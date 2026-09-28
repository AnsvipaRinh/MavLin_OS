# DRIVER AUDIT — NETWORK (brcmfmac / BCM43602)

> Deep Runtime Track D1. Audit date: 2026-09-28. Source: Linux 7.3.0-rc5 (torvalds) brcmfmac + linux-firmware WHENCE.
> Companion to: `RUNTIME_SOURCE_AUDIT.md` (per-path audit), `RUNTIME_COMPONENT_MAP.md` (structure), `DRIVER_OPTIMIZATION_CANDIDATES.md` (HW measurement plan).
> NO driver modifications. Config changes only where a real inconsistency exists in our own packaging (with evidence).

---

## F1 — NVRAM file precedence shadows EFI NVRAM

| Field | Value |
|---|---|
| Severity | Medium |
| Component | firmware/NVRAM loading |
| Source | `firmware.c:559-561` |
| Function | `brcmf_fw_request_nvram_done` |
| Finding | The driver loads NVRAM from file first; only if the file is missing does it fall back to the EFI `nvram` variable (`brcmf_fw_nvram_from_efi`, firmware.c:488-518). Our `extract-brcmfmac-nvram.sh` writes a 2-line placeholder `.txt` whenever the file is absent. Since linux-firmware never ships `brcmfmac43602-pcie.txt`, the placeholder is **always** installed on first boot — and it shadows any valid EFI NVRAM the firmware may provide on real hardware |
| Evidence | `if (fw && fw->data) { data = (u8 *)fw->data; data_len = fw->size; } else { data = brcmf_fw_nvram_from_efi(&data_len); ... }` (firmware.c:559-561); WHENCE has no `brcmfmac43602-pcie.txt`; script writes placeholder unconditionally when file missing (extract-brcmfmac-nvram.sh:17-30) |
| Risk | Placeholder NVRAM (macaddr + ccode only, no calibration) overrides potentially valid EFI NVRAM → no 5GHz, weak signal, or default MAC |
| Upstream status | stable (intentional design: file > EFI) |
| Proposed action | **CONFIG-CANDIDATE** — modify `extract-brcmfmac-nvram.sh` to check for EFI NVRAM usage before writing placeholder. If `dmesg` shows "Using nvram EFI variable" or the driver loaded NVRAM from EFI, skip placeholder. Only write placeholder if neither file nor EFI NVRAM is available. See proposed patch below |

### Proposed fix (F1)

```bash
# In extract-brcmfmac-nvram.sh, before writing placeholder:
# Check if driver already loaded NVRAM from EFI (real hardware)
if dmesg 2>/dev/null | grep -q "Using nvram EFI variable"; then
    echo "EFI NVRAM detected — skipping placeholder (driver uses EFI NVRAM)."
    exit 0
fi
# Otherwise write placeholder as before
```

---

## F2 — ccode=X0 in placeholder NVRAM

| Field | Value |
|---|---|
| Severity | Low |
| Component | NVRAM ccode |
| Source | `firmware.c:465-485`, `cfg80211.c:7967-7976` |
| Function | `brcmf_fw_fix_efi_nvram_ccode`, `brmcf_use_iso3166_ccode_fallback` |
| Finding | The placeholder NVRAM uses `ccode=X0`. `X0` is not a valid ISO 3166-1 alpha-2 code. The driver's own EFI NVRAM fixup only rewrites `ccode=ALL` and `ccode=XV` → `ccode=X2` (the driver's documented "worldwide" code). `X0` is passed to firmware as-is. For 43602, `brmcf_use_iso3166_ccode_fallback` returns true, meaning cfg80211 regulatory requests use ISO3166 alpha2 directly — but the NVRAM `ccode=` is separate (passed to firmware, not via cfg80211) |
| Evidence | `ccode = strnstr((char *)data, "ccode=ALL", data_len); if (!ccode) ccode = strnstr((char *)data, "ccode=XV\r", data_len);` (firmware.c:477-479) — only ALL and XV are fixed; `case BRCM_CC_43602_CHIP_ID: return true;` (cfg80211.c:7976) |
| Risk | Low — placeholder only; real NVRAM should have valid ccode (e.g., `GB`, `US`, `X2`, or `ALL`) |
| Upstream status | stable |
| Proposed action | **CONFIG-CANDIDATE** — change placeholder `ccode=X0` to `ccode=X2` (the driver's own documented worldwide code, firmware.c:465-471) or omit `ccode=` entirely (firmware uses default). See proposed patch below |

### Proposed fix (F2)

```bash
# In extract-brcmfmac-nvram.sh, change:
#   ccode=X0
# to:
#   ccode=X2
# X2 is the driver's documented "worldwide" code (firmware.c:465-471 comment)
```

---

## F3 — feature_disable=0x82000 cargo-cult value

| Field | Value |
|---|---|
| Severity | Low |
| Component | feature flags |
| Source | `feature.h:36-68`, `feature.c:349-353` |
| Function | `brcmf_feat_attach` |
| Finding | The script's experiment hint `options brcmfmac feature_disable=0x82000 roamoff=1` decodes to bit 19 (SAE) + bit 17 (MONITOR_FMT_HW_RX_HDR). Disabling SAE and monitor-format-HW-rx-hdr has no plausible connection to 5GHz/signal issues on BCM43602. The value appears cargo-culted from an unrelated context |
| Evidence | `0x82000 = 0x80000 + 0x20000` = bit 19 + bit 17. Enum order (feature.h:36-68): bit 17 = `BRCMF_FEAT_MONITOR_FMT_HW_RX_HDR`, bit 19 = `BRCMF_FEAT_SAE`. `if (drvr->settings->feature_disable) { ... ifp->drvr->feat_flags &= ~drvr->settings->feature_disable; }` (feature.c:349-353) |
| Risk | Low — labeled EXPERIMENT in script; not baseline |
| Upstream status | stable |
| Proposed action | **FALSE-POSITIVE** — remove the specific `0x82000` value from the script's experiment hint, or replace with a comment that the value is unverified. The script already labels it "EXPERIMENTS (E10 family), not baseline" — keep that label but remove the specific hex value to prevent cargo-culting |

---

## F4 — DMI board_type contains a space

| Field | Value |
|---|---|
| Severity | Informational |
| Component | DMI board detection |
| Source | `dmi.c:220-227` |
| Function | `brcmf_dmi_probe` |
| Finding | If no DMI quirk matches and no ACPI module-instance is present, `board_type` is set to `"<sys_vendor>-<product_name>"` = `"Apple Inc.-MacBook10,1"` (with a space). This produces a firmware filename attempt `brcmfmac43602-pcie.Apple Inc.-MacBook10,1.txt` which will not exist, then falls back to canonical `brcmfmac43602-pcie.txt`. The space in the filename is unusual but harmless (fallback works) |
| Evidence | `snprintf(dmi_board_type, sizeof(dmi_board_type), "%s-%s", sys_vendor, product_name);` (dmi.c:224-226) |
| Risk | Informational — fallback to canonical path works correctly |
| Upstream status | stable |
| Proposed action | **KEEP** — no action; document as known behavior |

---

## F5 — Apple ACPI properties (module-instance / RWCV) unknown on MacBook10,1

| Field | Value |
|---|---|
| Severity | Hardware validation |
| Component | Apple firmware/NVRAM selection |
| Source | `acpi.c:11-51`, `pcie.c:2267-2293` |
| Function | `brcmf_acpi_probe`, `brcmf_pcie_prepare_fw_request` |
| Finding | The Asahi-derived ACPI code reads `module-instance` (→ `board_type = "apple,<module-instance>"`) and `RWCV` (→ `antenna_sku`). If both are present and OTP is valid, the driver builds fancy board type strings (e.g., `apple,shikoku-RASP-m-6.11-X3`) and tries Apple-specific NVRAM files. Whether MacBook10,1's ACPI exposes these properties is **unknown without hardware** — the Asahi code targets Apple Silicon, but the ACPI methods may exist on Intel Macs too |
| Evidence | `acpi_dev_get_property(adev, "module-instance", ACPI_TYPE_STRING, &o)` (acpi.c:22); `acpi_evaluate_object(adev->handle, "RWCV", NULL, &buf)` (acpi.c:33); `if (devinfo->settings->board_type && devinfo->settings->antenna_sku && devinfo->otp.valid)` (pcie.c:2267) |
| Risk | Medium — determines NVRAM file selection; if ACPI properties exist, the driver may look for `brcmfmac43602-pcie.apple,<module-instance>.txt` which we have not provisioned |
| Upstream status | stable |
| Proposed action | **KEEP** — hardware validation item; on hardware, check `dmesg | grep -i "ACPI module-instance"` and `dmesg | grep -i "Apple board"` to determine which path was taken |

---

## F6 — EFI NVRAM may provide real calibration on Macs

| Field | Value |
|---|---|
| Severity | Hardware validation |
| Component | EFI NVRAM |
| Source | `firmware.c:488-518` |
| Function | `brcmf_fw_nvram_from_efi` |
| Finding | The driver can read the macOS NVRAM blob from EFI variable `nvram` (GUID `74b00bd9-805a-4d61-b51f-43268123d13`) when no file NVRAM is present. On a Mac that has run macOS or Boot Camp, this variable may contain real per-board calibration. The driver logs `"Using nvram EFI variable"` when this path is taken. Our placeholder `.txt` shadows this (F1) |
| Evidence | `efi.get_variable(L"nvram", &guid, NULL, &data_len, data)` (firmware.c:505); `brcmf_info("Using nvram EFI variable\n")` (firmware.c:513) |
| Risk | Medium — if EFI NVRAM is valid, placeholder shadows it (see F1) |
| Upstream status | stable |
| Proposed action | **KEEP** — hardware validation item; on hardware, check `dmesg | grep -i "nvram EFI"` to see if EFI path was taken |

---

## F7 — Default MAC randomization

| Field | Value |
|---|---|
| Severity | Informational |
| Component | MAC address |
| Source | `common.c:244-302` |
| Function | `brcmf_c_preinit_dcmds` |
| Finding | If firmware reports the default MAC `00:90:4c:c5:12:38` (from a template NVRAM), the driver replaces it with a random MAC. A placeholder NVRAM may trigger this. The script already sets `macaddr=$MAC` from the interface, which may mitigate |
| Evidence | `static const u8 brcmf_default_mac_address[ETH_ALEN] = { 0x00, 0x90, 0x4c, 0xc5, 0x12, 0x38 };` (common.c:244-247); `if (ether_addr_equal_unaligned(ifp->mac_addr, brcmf_default_mac_address)) { ... eth_random_addr(ifp->mac_addr); ... }` (common.c:296-302) |
| Risk | Informational — cosmetic |
| Upstream status | stable |
| Proposed action | **KEEP** — no action; document as known behavior |

---

## F8 — 43602-specific download state handling

| Field | Value |
|---|---|
| Severity | Informational |
| Component | firmware download |
| Source | `pcie.c:731-760` |
| Function | `brcmf_pcie_enter_download_state`, `brcmf_pcie_exit_download_state` |
| Finding | BCM43602 has special download-state handling: ARM_CR4 core selection, bank register manipulation (bankidx 5, 7), and `brcmf_chip_resetcore` on exit. This is chip-specific init, not a runtime concern |
| Evidence | `if (devinfo->ci->chip == BRCM_CC_43602_CHIP_ID) { brcmf_pcie_select_core(devinfo, BCMA_CORE_ARM_CR4); brcmf_pcie_write_reg32(devinfo, BRCMF_PCIE_ARMCR4REG_BANKIDX, 5); ... }` (pcie.c:731-737); `core = brcmf_chip_get_core(devinfo->ci, BCMA_CORE_INTERNAL_MEM); brcmf_chip_resetcore(core, 0, 0, 0);` (pcie.c:753-754) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no action |

---

## F9 — ISO package consistency

| Field | Value |
|---|---|
| Severity | Informational |
| Component | ISO packaging |
| Source | `archiso-profile/releng/packages.x86_64`, `profiledef.sh` |
| Finding | ISO includes `linux-firmware` (has `.bin` + `.ap.bin`), `networkmanager`, `wpa_supplicant`, `iwd`, `wireless-regdb`, `wireless_tools`. `extract-brcmfmac-nvram.sh` is in profiledef.sh. `mkinitcpio.conf` does NOT include brcmfmac in MODULES (loaded on demand — correct). `broadcom-wl.conf` and `99-mavericks.conf` are consistent (no active overrides). No inconsistencies found in packaging |
| Evidence | packages.x86_64:54,74,115,116,118; profiledef.sh:25; mkinitcpio.conf:1; modprobe.d/broadcom-wl.conf; modprobe.d/99-mavericks.conf |
| Risk | none |
| Upstream status | n/a |
| Proposed action | **KEEP** — no action |

---

## Finding summary

| Outcome class | Count | Findings |
|---|---|---|
| KEEP | 6 | F4, F5, F6, F7, F8, F9 |
| CONFIG-CANDIDATE | 2 | F1 (NVRAM precedence), F2 (ccode) |
| UPSTREAM-CANDIDATE | 0 | — |
| LOCAL-CANDIDATE | 0 | — |
| FALSE-POSITIVE | 1 | F3 (feature_disable=0x82000) |
| **Total** | **9** | |

---

## Config changes applied

Only F1 and F2 have proposed config changes (to `extract-brcmfmac-nvram.sh`). Both are in our own packaging, evidence-backed, and do not touch the frozen power baseline or driver code. See the proposed patches in F1/F2 above. These will be applied in a follow-up commit if approved.

---

## D2 — Userspace backend audit (NetworkManager / wpa_supplicant / iwd)

> Audit date: 2026-09-28. Source: NM 1.58.1, wpa_supplicant 2.12, iwd 3.12 sources + Arch package file lists.
> Companion to RUNTIME_SOURCE_AUDIT.md §D2 (U1-U5) and RUNTIME_COMPONENT_MAP.md §4.1.

### F10 — Active backend is wpa_supplicant (by default, now pinned)

| Field | Value |
|---|---|
| Severity | Informational |
| Component | NM Wi-Fi backend selection |
| Source | `meson.build:430-436`, `nm-wifi-factory.c:126` |
| Finding | NM compile-time default backend is `wpa_supplicant` (`config_wifi_backend_default='default'` → `'wpa_supplicant'`). Our packaging shipped no backend selection → default applied implicitly. iwd is installed in the ISO but disabled on the installed system by firstboot. |
| Evidence | `meson.build:430-436`; `nm-wifi-factory.c:126` (`backend = "" NM_CONFIG_DEFAULT_WIFI_BACKEND`); firstboot `systemctl disable --now iwd.service` |
| Risk | Low — implicit default; a future NM default flip could silently change backend |
| Proposed action | **APPLIED** — `configs/network/99-mavericks.conf` `[device] wifi.backend=wpa_supplicant` pins it explicitly. No behavior change. |

### F11 — wpa_supplicant vs iwd trade-off for BCM43602 FullMAC

| Field | Value |
|---|---|
| Severity | Informational |
| Component | NM Wi-Fi backend |
| Source | `nm-device-iwd.c`, wpa_supplicant 2.12 + iwd 3.12 sources |
| Finding | **wpa_supplicant** (active): full features (P2P/AP/hidden/ad-hoc), NM-controlled roaming (supplicant settle wait, nm-device-wifi.c:2611), mature. **iwd**: no P2P, 802.1X needs iwd provisioning files, hidden SSIDs infra-only, iwd-controlled roaming/autoconnect (network ranking). Powersave identical in NM 1.58.1 (both via `NL80211_CMD_SET_POWER_SAVE` directly). SAE/WPA3: both support. |
| Evidence | `nm-device-iwd.c` capability checks; wpa_supplicant 2.12 `defconfig` `CONFIG_SAE=y`; NM commit 5838c38 (iwd powersave); RUNTIME_SOURCE_AUDIT.md U5 |
| Risk | none — wpa_supplicant is the safer default for our feature set |
| Proposed action | **KEEP** — wpa_supplicant pinned. iwd remains available as a future A/B option (see DRIVER_OPTIMIZATION_CANDIDATES.md). |

### D2 config changes applied

| Change | File | Evidence | Baseline impact |
|---|---|---|---|
| Pin `wifi.backend=wpa_supplicant` | `configs/network/99-mavericks.conf` `[device]` | NM default is wpa_supplicant (meson.build:430-436) | none (pins existing default) |
| Disable connectivity check (`enabled=false`) | `configs/network/99-mavericks.conf` `[connectivity]` | Arch ships `uri=http://ping.archlinux.org/nm-check.txt`; NM default interval 300s | removes 5-min HTTP poll |
| mv-control `--rescan no` default | `packages/.../mv-control` `refresh_wifi_list` | nmcli(1): 30s-old cache triggers scan | removes 30s scan while CC open |

All three are in our own packaging, evidence-backed, no NM/supplicant source patches, frozen power baseline untouched.

---

## D3 — i915 display path driver audit (Gen9.5, 2026-09-28)

> Companion to RUNTIME_SOURCE_AUDIT.md §D3 (S1-S10) and RUNTIME_COMPONENT_MAP.md §5.
> Source: Linux master (torvalds) i915 display code via codebrowser.dev.

### F12 — PSR flicker on Gen9 (KBL/CML/SKL) with kernel 6.8+ (BASELINE ITEM)

**Finding:** Random panel flickering on Gen9 GPUs (Kaby Lake, Comet Lake, Skylake)
with kernel 6.8+. Correlated with `CONFIG_INTEL_IOMMU_DEFAULT_ON` and
`CONFIG_INTEL_IOMMU_SCALABLE_MODE_DEFAULT_ON` changes. Fixed by `i915.enable_psr=0`
or `intel_iommu=igfx_off`. Flicker occurs when cursor is in bottom quarter of screen;
stops when cursor leaves that area. Accompanied by `CPU pipe A FIFO underrun` in dmesg.

**Evidence:**
- LP#2086587: "Random flickering with Intel i915 (Comet Lake and Kaby Lake) on Linux 6.8+"
- LP#2062951: "Random flickering with Intel i915 (Gen9 GPUs in 6th-8th gen CPUs) on Linux 6.8"
- Both fixed by `i915.enable_psr=0` or `intel_iommu=igfx_off`
- Upstream fix: Jouni Högander 8-patch series (ALPM wake lines calculation) —
  landed in mainline 6.8.0-53 (Ubuntu SRU)

**Our baseline:** `i915.enable_psr=0` — diagnostic-safe. Our panel (2304×1440 eDP,
likely LP125WF2 or similar) may or may not be affected. The flicker is panel-specific.
With PSR disabled, the display continuously refreshes from DDR — higher idle power.
**Verdict: JUSTIFIED** — see DECISIONS.md D3 entry for full judgment.

### F13 — Apple S3X NVMe resume failure (BASELINE ITEM)

**Finding:** Apple S3X NVMe controller (106b:2003) becomes unresponsive after
S3/s2idle resume on MacBook10,1. Root port 00:1c.0 (Sunrise Point-LP PCH) D3
entry/exit leaves the device unreachable. `pcie_port_pm=off` fixes it.
Without the workaround, the root filesystem goes read-only after ~60s.

**Evidence:**
- LKML Sep 2026: "nvme: Apple S3X (106b:2003) unresponsive after resume on
  MacBook10,1, fixed by pcie_port_pm=off" (lists.openwall.net/linux-kernel/2026/09/21/161)
- `pcie_aspm=off` and `nvme_core.default_ps_max_latency_us=0` did NOT help
- `pcie_port_pm=off` passes all pm_test levels + real suspend + lid close/open
- Root port: Intel Sunrise Point-LP PCH root port #1 (00:1c.0), L1 PM Substates capable

**Our baseline:** `pcie_port_pm=off` — provisional workaround. Disables ALL PCIe
root port runtime PM → battery life impact (unmeasured). The LKML thread asks
if a PCI quirk for 00:1c.0 is possible instead of global disable.
**Verdict: JUSTIFIED (provisional)** — see DECISIONS.md D3 entry for full judgment.

### F14 — xfwm4 vblank_mode=off + unredirect_overlays=true (PROVISIONAL CONFIG)

**Finding:** Our xfwm4 config sets `vblank_mode=off` and `unredirect_overlays=true`
as PROVISIONAL optimizations for the fanless Core M. These reduce compositor work
but may cause tearing on the real panel. Marked as requiring hardware validation.

**Evidence:**
- `configs/desktop/xfce/xfwm4.xml:25-26` — both settings with PROVISIONAL comment
- `vblank_mode=off`: xfwm4 renders without waiting for vblank → pageflips at render rate
- `unredirect_overlays=true`: fullscreen windows bypass compositor → no compositor overhead
- PSR entry is blocked while vblank is enabled (intel_psr.c:945) — so vblank_mode=off
  actually HELPS PSR entry (vblank can be disabled when compositor doesn't need it)

**Our baseline:** No change — these are our own config settings, not kernel params.
**Verdict: NEUTRAL** — provisional, requires HW validation for tearing.

### F15 — DMC firmware dependency for DC5/6 (PACKAGING)

**Finding:** DC5/6 entry requires DMC firmware (`i915/kbl_dmc.bin`). Without it,
the display stays in DC0 (no power saving). The firmware is in `linux-firmware`
package (verified in packages.x86_64).

**Evidence:**
- intel_dmc.c:235-239 — KBL_DMC_PATH = "i915/kbl_dmc.bin"
- intel_display_power.c:1486 — `intel_dmc_load_program()` called on resume
- `gen9_dc_off_power_well_disable` checks `intel_dmc_has_payload` before DC entry

**Our baseline:** `linux-firmware` in packages.x86_64 — DMC firmware present.
**Verdict: KEEP** — packaging correct, no change needed.

### D3 driver audit summary

| Outcome class | Count | Findings |
|---|---|---|
| BASELINE-JUSTIFIED | 2 | F12 (PSR off), F13 (pcie_port_pm off) |
| PROVISIONAL-CONFIG | 1 | F14 (xfwm4 vblank/unredirect) |
| KEEP | 1 | F15 (DMC firmware packaging) |
| **Total** | **4** | |

---

# DRIVER AUDIT — AUDIO (Cirrus CS4208 / HDA) (D4, 2026-09-28)

> Deep Runtime Track D4. Target: MacBook10,1, Cirrus CS4208 on Intel HDA
> (PCI 00:1f.3). Driver: DKMS snd-hda-codec-cs420x (leifliddy
> r108.g4cdfcdb, vendored in packages/macbook12-audio-driver/src/).
> All findings empirically verified in the build container
> (linux-zen-headers 7.2.6.zen2-1 + linux-7.2.6 source) unless noted.

### F16 — DKMS build broken: no root Makefile (PACKAGING, documented)

**Finding:** `dkms install` runs `make -C /usr/lib/modules/<ver>/build
M=<srcroot> modules` (dkms.conf MAKE[0]). The DKMS source tree has **no
root Makefile** — Makefile_cirrus/Makefile_cs420x are in-tree kbuild files,
not external-module Makefiles.

**Evidence:** empirical — replicated the exact dkms.conf MAKE[0] command in
the build container: `Makefile: No such file or directory` (build fails).

**Verdict: DOCUMENTED DEFECT** — the package cannot install via DKMS as
shipped. Not fixed in D4 (fix requires either a PRE_BUILD kernel-source
download flow or tracking the tanisperez fork — both are separate packaging
tracks). Package kept in the local repo for the manual build flow; NOT added
to ISO packages.x86_64 (post_install would fail and break pacstrap).

### F17 — Internal HDA headers not in linux-zen-headers (ENVIRONMENT)

**Finding:** the driver needs kernel-internal HDA headers
(sound/hda/common/hda_local.h, hda_auto_parser.h, hda_jack.h,
sound/hda/codecs/generic.h). The linux-zen-headers build tree ships
**zero .h files under sound/hda/** (verified: 0 headers found).

**Evidence:** empirical — `find /usr/lib/modules/7.2.6-zen2-1-zen/build/sound
-name "*.h"` → empty; external build fails with `hda_local.h: No such file
or directory` until the full kernel source tree is supplied via -I.

**Verdict: DOCUMENTED** — external-module builds of this driver are
impossible against the headers package alone; the working install path
(upstream prepare.cirrus.driver.sh) downloads the kernel source tarball.
This is why the DKMS flow needs a PRE_BUILD step (see F16 disposition).

### F18 — Driver source compiles on the target kernel (VERIFIED)

**Finding:** the leifliddy r108 driver source (patch_cirrus/cs420x.c +
A1534 headers) compiles cleanly against the target kernel.

**Evidence:** empirical — external build against linux-7.2.6 source +
linux-zen-headers 7.2.6.zen2-1 with `-I<src>/sound/hda/common`:
`snd-hda-codec-cs420x.ko` builds (1.75MB, GPL, alias hdaudio:v10134208,
depends: snd-hda-codec, snd-hda-codec-generic, snd-hda-core).

**Verdict: VERIFIED** — the driver code is viable on our target kernel
(linux-zen 7.2.6); only the DKMS packaging is broken (F16/F17).

### F19 — Dangling udev rule (FIXED in D4)

**Finding:** the package installed a udev rule running
`/usr/bin/alsa-ucm-awake` — a script shipped nowhere (not in the repo, not
in the driver source). Every sound-card change event produced a udev
execution-failure log.

**Evidence:** repo-wide grep for alsa-ucm-awake → only the PKGBUILD (and
the gitignored pkg/ build artifact) reference it.

**Fix (888e0ff):** udev rule removed from package().

### F20 — WirePlumber softvol conf never installed (FIXED in D4)

**Finding:** the driver README marks the WirePlumber soft-volume rule as
**required** ("Without this step the volume slider appears to do nothing on
the speakers") — the CS4208 speaker path has no hardware volume control.
The contrib file shipped in the source tree, but package() never installed
it → speaker volume would have been dead on any install.

**Fix (888e0ff):** package() now installs
contrib/wireplumber/wireplumber.conf.d/51-macbook-cs4208-softvol.conf →
/etc/wireplumber/wireplumber.conf.d/ (WirePlumber 0.5+ variant; Arch ships
0.5.17).

### F21 — Dead model=macbook12 modprobe line (FIXED in D4)

**Finding:** `options snd-hda-intel model=macbook12` was a no-op: the A1534
initialization is unconditional in patch_cs4208() (setup_a1534/play_a1534
called for every CS4208), and the driver's model fixup tables
(gpio0/mba6/mbp11/macmini) contain no "macbook12" entry.

**Evidence:** patch_cirrus/patch_cirrus.c:793-794 (unconditional A1534
calls); cs420x_models/cs4208_models tables (no macbook12).

**Fix (888e0ff):** line removed; 99-macbook12-audio.conf kept as
comment-only documentation.

### F22 — Redundant power_save modprobe lines (FIXED in D4)

**Finding:** `power_save=1 power_save_controller=Y` duplicated TLP, which
owns audio PM in the frozen baseline. TLP 1.9.1 defaults:
SOUND_POWER_SAVE_ON_AC=1, SOUND_POWER_SAVE_ON_BAT=1,
SOUND_POWER_SAVE_CONTROLLER=Y — identical values, no conflict, pure
redundancy.

**Evidence:** TLP 1.9.1 docs (linrunner.de/settings/audio) + TLP
defaults.conf; our /etc/tlp.d/99-mavericks.conf sets no sound keys (TLP
defaults apply).

**Fix (888e0ff):** lines removed; TLP remains the single audio-PM
mechanism. HW item: validate power_save=1 for audio glitches on CS4208
(NEEDS_HARDWARE_TEST.md §Audio power/idle).

### D4 driver audit summary

| Outcome class | Count | Findings |
|---|---|---|
| VERIFIED | 1 | F18 (driver compiles on target kernel) |
| DOCUMENTED-DEFECT | 2 | F16 (DKMS build broken), F17 (headers not in headers package) |
| FIXED | 4 | F19 (udev rule), F20 (softvol conf), F21 (dead model=), F22 (redundant power_save) |
| **Total** | **7** | |

---

## D5 — INPUT + STORAGE driver audit (2026-09-28)

> Deep Runtime Track D5. Target: MacBook10,1, Apple SPI keyboard + Force Touch trackpad,
> Apple S3X NVMe (106b:2003). Source: applespi driver (roadrunner2/macbook12-spi-driver,
> GPL-2.0), Linux 7.3.0-rc5 (torvalds) nvme core + btrfs.
> NO driver modifications. Config changes only where a real inconsistency exists in our own
> packaging (with evidence).

### F23 — applespi SPI timeout on kernel 6.15+ (DOCUMENTED — 3-strategy limit)

| Field | Value |
|---|---|
| Severity | High (input failure) |
| Component | SPI controller (spi_pxa2xx_platform) rev3+ |
| Source | applespi.c:1735-1740 (read), applespi.c:1560-1575 (write) |
| Function | `applespi_async_read_complete`, `applespi_async_write_complete` |
| Finding | The SPI controller on MacBook10,1 (rev3+) has a hardware/firmware bug where SPI transfers timeout on kernel 6.15+. The applespi driver sees ETIMEDOUT (-110) and logs it. There is NO retry mechanism — the input event is lost. This affects both keyboard and trackpad. |
| Evidence | `pr_warn("Error reading from device: %d\n", status)` (applespi.c:1736); `pr_warn("Error writing to device: %d\n", sts)` (applespi.c:1562); dmesg: `applespi: Error reading from device: -110` |
| Risk | **High** — intermittent or complete input failure on kernel 6.15+ |
| Upstream status | **NO fix** — the bug is in the SPI controller driver (spi_pxa2xx_platform), not in applespi. The AUR macbook12-spi-driver-dkms package may have patches. |
| Proposed action | **3-strategy best-effort limit** (AGENTS.md §2): Strategy A: AUR macbook12-spi-driver-dkms on linux-zen. Strategy B: linux-zen with applespi patches from linux-macbook kernel. Strategy C: linux-lts or different kernel version. If all 3 fail → mark as "not supported on this revision". External USB-C HID is the mandatory bring-up interface. |

### F24 — applespi no runtime PM (DOCUMENTED — by design)

| Field | Value |
|---|---|
| Severity | Informational |
| Component | applespi power management |
| Source | applespi.c:1828-1829 |
| Function | `applespi_pm_ops` |
| Finding | The applespi driver does NOT implement runtime PM. The device stays powered in S0. There is no autosuspend. The only power saving is at system suspend (S3/s2idle). |
| Evidence | `UNIVERSAL_DEV_PM_OPS(applespi_pm_ops, applespi_suspend, applespi_resume, NULL)` (applespi.c:1828) — no `.runtime_suspend`/`.runtime_resume` |
| Risk | Informational — the SPI controller and input device stay powered at idle |
| Upstream status | By design — SPI slave devices typically don't have runtime PM |
| Proposed action | **KEEP** — no change. Documented as known behavior. |

### F25 — applespi keyboard does NOT wake from suspend (DOCUMENTED — by design)

| Field | Value |
|---|---|
| Severity | Informational |
| Component | applespi suspend/resume |
| Source | applespi.c:1754-1785 |
| Function | `applespi_suspend` |
| Finding | The applespi driver disables the GPE in suspend. The keyboard does NOT wake the system from suspend. External USB keyboard can wake via USB resume. |
| Evidence | `acpi_disable_gpe(NULL, applespi->gpe)` (applespi.c:1765) |
| Risk | Informational — keyboard cannot wake the system |
| Upstream status | By design — GPE disabled in suspend |
| Proposed action | **KEEP** — no change. Documented as known behavior. External USB keyboard is the wake interface. |

### F26 — fstrim.timer not enabled (CONFIG-CANDIDATE — should enable)

| Field | Value |
|---|---|
| Severity | Low |
| Component | SSD TRIM |
| Source | mavericks-firstboot.sh (no fstrim) |
| Function | firstboot script |
| Finding | The `fstrim.timer` systemd timer is NOT enabled in our ISO or on the installed system. The firstboot script does not enable it. Without periodic TRIM, SSD performance may degrade over time. |
| Evidence | mavericks-firstboot.sh — no `systemctl enable fstrim.timer` |
| Risk | **Low** — SSD performance degradation over time |
| Upstream status | N/A — our packaging |
| Proposed action | **CONFIG-CANDIDATE** — add `systemctl enable fstrim.timer` to firstboot script. One-line addition. Cost is negligible (weekly oneshot, ~seconds). |

### F27 — S3X NVMe resume bug (BASELINE ITEM — already documented in D3)

| Field | Value |
|---|---|
| Severity | High (data loss) |
| Component | Apple S3X NVMe (106b:2003) |
| Source | LKML Sep 2026 |
| Function | PCIe root port 00:1c.0 runtime PM |
| Finding | S3X becomes unresponsive after S3/s2idle resume without `pcie_port_pm=off`. Root filesystem goes read-only after ~60s. |
| Evidence | LKML: lists.openwall.net/linux-kernel/2026/09/21/161 |
| Risk | **High** — data loss on resume |
| Upstream status | **NO fix yet** — LKML thread open (Sep 2026) |
| Proposed action | **BASELINE-JUSTIFIED** — `pcie_port_pm=off` is our provisional workaround. Already documented in D3 (F13). No change. |

### F28 — btrfs mount options minimal (KEEP — by design)

| Field | Value |
|---|---|
| Severity | Informational |
| Component | btrfs mount options |
| Source | kernel cmdline |
| Function | `rootflags=subvol=@` |
| Finding | Our btrfs mount options are minimal — only `subvol=@`. No `noatime`, no `discard`, no `ssd`. Kernel defaults apply. |
| Evidence | kernel cmdline: `rootflags=subvol=@` |
| Risk | Informational — kernel defaults are fine for SSD |
| Upstream status | N/A — our packaging |
| Proposed action | **KEEP** — no change. `relatime` (kernel default) is frugal, no `discard` is correct, 30s commit is fine. |

### D5 driver audit summary

| Outcome class | Count | Findings |
|---|---|---|
| DOCUMENTED | 3 | F23 (SPI timeout 6.15+), F24 (no runtime PM), F25 (no wake from suspend) |
| CONFIG-CANDIDATE | 1 | F26 (fstrim.timer not enabled) |
| BASELINE-JUSTIFIED | 1 | F27 (S3X resume bug — already in D3) |
| KEEP | 1 | F28 (btrfs mount options) |
| **Total** | **6** | |
