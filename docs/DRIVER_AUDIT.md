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
