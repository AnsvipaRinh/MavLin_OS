# RUNTIME COMPONENT MAP — NETWORK (BCM43602 / brcmfmac)

> Deep Runtime Track D1. Audit date: 2026-09-28. Target: MacBook10,1, Broadcom BCM43602 (PCIe FullMAC/D11).
> Source basis: Linux 7.3.0-rc5 (torvalds) `drivers/net/wireless/broadcom/brcm80211/brcmfmac/` + `linux-firmware` WHENCE.
> Host had no kernel `.c` source; all references verified against upstream git.kernel.org plain fetches. Re-verify on target with the commands in §6.
> NO driver modifications. This is a map + audit only.

---

## 1. brcmfmac module structure (PCIe path)

brcmfmac is a **FullMAC** driver: it implements `struct cfg80211_ops` directly and does **not** use mac80211. Kconfig: `BRCMFMAC depends on CFG80211` (brcmfmac/Kconfig:3-6). PCIe selects the MSGBUF protocol: `BRCMFMAC_PCIE select BRCMFMAC_PROTO_MSGBUF` (brcmfmac/Kconfig:52-58).

| Layer | File | Role |
|---|---|---|
| Bus: PCIe | `pcie.c` | probe/remove, firmware download, ring buffers, IRQ (threaded MSI), mailbox, OTP, shared RAM, suspend/resume |
| Bus: SDIO | `sdio.c`, `bcmsdh.c` | not used for BCM43602 |
| Bus: USB | `usb.c` | not used for BCM43602 |
| Bus core | `bus.c`, `bus.h` | `brcmf_bus` struct, bus state machine |
| Common | `common.c`, `common.h` | `brcmf_if`, preinit dcmds, module params, DMI/ACPI/OF probe |
| Core | `core.c` | attach/detach, netdev ops, `brcmf_bus_started`, xmit entry |
| Protocol: MSGBUF | `msgbuf.c`, `msgbuf.h` | PCIe protocol: TX flowrings, RX, events, ioctl |
| Protocol: BCDC | `bcdc.c`, `fwsignal.c` | SDIO/USB protocol — **not used for PCIe** |
| FW event handler | `fweh.c`, `fweh.h` | firmware event queue + worker (system_wq) |
| FW interface | `fwil.c`, `fwil.h` | iovar/cmd helpers (`brcmf_fil_iovar_data_set`, etc.) |
| FW vendor | `fwvid.c` | firmware vendor detection (WCC/BCA/CYW) |
| Firmware | `firmware.c`, `firmware.h` | `brcmf_fw_alloc_request`, board-specific path fallback, EFI NVRAM |
| NVRAM parse | `nvram.c` | NVRAM txt parsing (via `nvram_parser` in firmware.c) |
| Chip | `chip.c`, `chip.h` | chip info table, RAM info, core access |
| cfg80211 | `cfg80211.c`, `cfg80211.h` | wiphy ops: scan, connect, powersave, roam, wowlan, p2p, reg |
| P2P | `p2p.c`, `p2p.h` | P2P vif, listen timer |
| PNO | `pno.c`, `pno.h` | preferred network offload (firmware scheduled scan) |
| Feature | `feature.c`, `feature.h` | feature flags, `feature_disable` parsing |
| BT coex | `btcoex.c`, `btcoex.h` | Bluetooth coexistence state machine |
| Vendor | `vendor.c` | Broadcom OUI vendor command (DCMD diagnostics) |
| Flowring | `flowring.c`, `flowring.h` | TX flow control, queue blocking |
| Commonring | `commonring.c`, `commonring.h` | common ring buffer management |
| XTLV | `xtlv.c`, `xtlv.h` | TLV parsing |
| DMI | `dmi.c` | DMI quirk table → board_type |
| ACPI | `acpi.c` | ACPI module-instance/RWCV → board_type/antenna_sku (Asahi) |

---

## 2. cfg80211 / mac80211 involvement

**FullMAC → mac80211 is bypassed entirely.** The driver registers a `struct cfg80211_ops` (`brcmf_cfg80211_ops`, cfg80211.c:6007+) with handlers: `.scan`, `.connect`, `.disconnect`, `.set_power_mgmt`, `.join_ibss`, `.leave_ibss`, `.get_station`, `.set_wiphy_params`, `.set_tx_power`, `.get_tx_power`, `.dump_survey`, `.remain_on_channel`, `.cancel_remain_on_channel`, `.mgmt_tx`, `.mgmt_tx_cancel`, `.scan`, etc. There is no `ieee80211_ops` and no mac80211 TX/RX path. All 802.11 management is handled in firmware; the driver exchanges ethernet frames with the netdev and iovar/cmd messages with firmware.

---

## 3. Firmware interface

### 3.1 Firmware files (BCM43602, PCIe)

| File | Required | Source | Notes |
|---|---|---|---|
| `brcm/brcmfmac43602-pcie.bin` | **yes** | linux-firmware | main firmware binary |
| `brcm/brcmfmac43602-pcie.ap.bin` | no | linux-firmware | AP-mode variant |
| `brcm/brcmfmac43602-pcie.txt` | no (but radio calibration needed) | **NOT in linux-firmware** | per-board NVRAM; must be provisioned |
| `brcm/brcmfmac43602-pcie.clm_blob` | no | **NOT in linux-firmware** | CLM limits blob |
| `brcm/brcmfmac43602-pcie.txcap_blob` | no | **NOT in linux-firmware** | TX capability blob |

Evidence: linux-firmware WHENCE lists only `brcmfmac43602-pcie.bin` and `brcmfmac43602-pcie.ap.bin` (WHENCE:2976-2977). No `.txt`, `.clm_blob`, or `.txcap_blob` for 43602.

### 3.2 Firmware request flow

`brcmf_pcie_prepare_fw_request` (pcie.c:2239-2299) builds a `brcmf_fw_request` with items: `.bin` (required), `.txt` (NVRAM, `BRCMF_FW_REQF_OPTIONAL`), `.clm_blob` (optional), `.txcap_blob` (optional). `brcmf_fw_get_firmwares` (firmware.c:760-800) first tries board-specific path (`brcm_alt_fw_path` → `brcmfmac43602-pcie.<board_type>.txt`), then falls back to canonical `brcmfmac43602-pcie.txt`.

### 3.3 Board-specific NVRAM selection (Apple)

- **OTP path** (pcie.c:2267-2293): if `settings->board_type && settings->antenna_sku && otp.valid`, builds board type strings like `apple,<module>-<vendor>-<version>-<antenna_sku>` (example in comment: `apple,shikoku-RASP-m-6.11-X3`). OTP read via `brcmf_pcie_read_otp` (pcie.c:2049).
- **ACPI path** (acpi.c:11-51, Asahi): `module-instance` property → `board_type = "apple,<module-instance>"`; `RWCV` buffer → `antenna_sku` (2 chars).
- **DMI path** (dmi.c:199-228): if no DMI quirk match, `board_type = "<sys_vendor>-<product_name>"` → for MacBook10,1: `"Apple Inc.-MacBook10,1"` (note: contains a space).
- **EFI NVRAM** (firmware.c:488-518): if file NVRAM missing, driver reads EFI variable `nvram` (GUID `74b00bd9-805a-4d61-b51f-43268123d13`) — this is the macOS NVRAM blob. Logs `"Using nvram EFI variable"`.

### 3.4 Event channel

Firmware events arrive as MSGBUF event frames on the RX event ring → `brcmf_msgbuf_process_event` (msgbuf.c:1131-1168) → `brcmf_fweh_process_skb` (fweh.c) → `brcmf_fweh_queue_event` → `schedule_work(&fweh->event_work)` (fweh.c:94) → `brcmf_fweh_event_worker` (fweh.c:361) on the **system workqueue** (not a dedicated wq). Event mask set via `event_msgs` iovar (fweh.c:460-466). Event codes: `BRCMF_E_*` (fweh.h:104+).

---

## 4. NM → wpa_supplicant → nl80211 → cfg80211 → brcmfmac chain

```
NetworkManager (process, C)
  └─ D-Bus ─→ wpa_supplicant (process, C)   [or iwd — both installed in ISO]
       └─ nl80211 (generic netlink, kernel)
            └─ cfg80211 (kernel)
                 └─ brcmfmac (kernel, FullMAC)
                      └─ MSGBUF protocol ─→ firmware (BCM43602)
```

Process/module boundaries:
- **NetworkManager**: userspace daemon; talks to wpa_supplicant via D-Bus (`fi.w1.wpa_supplicant1`). Not a kernel component.
- **wpa_supplicant**: userspace daemon; sends `NL80211_CMD_*` commands via netlink. ISO also ships `iwd` (packages.x86_64:46) as an alternative NM backend.
- **nl80211/cfg80211**: kernel; no persistent process.
- **brcmfmac**: kernel module; no userspace daemon. All 802.11 state machine in firmware.

Powersave (NM 1.58.1, D2 correction): NM sets 802.11 PS **directly via nl80211**, not through wpa_supplicant. `set_powersave()` (nm-device-wifi.c:3412) reads `802-11-wireless.powersave` (default 0 → falls back to `[connection] wifi.powersave`, default `ignore`=1 → no touch) and calls `nm_platform_wifi_set_powersave` → `wifi_nl80211_set_powersave` (nm-wifi-utils-nl80211.c:260) → `NL80211_CMD_SET_POWER_SAVE` → `brcmf_cfg80211_set_power_mgmt` (cfg80211.c:3305) → `BRCMF_C_SET_PM` iovar. Identical for the iwd backend (nm-device-iwd.c:2274).

---

## 4.1. Userspace path audit (D2, 2026-09-28)

### 4.1.1 Active backend + versions

| Component | Version (Arch) | License | Repo | Role |
|---|---|---|---|---|
| NetworkManager | 1.58.1-1 | GPL-2.0-or-later, LGPL-2.1-or-later | extra | connection manager daemon |
| wpa_supplicant | 2:2.12-1 | BSD-3-Clause | core | NM Wi-Fi backend (active) |
| iwd | 3.12-2 | LGPL-2.1-or-later | extra | NM Wi-Fi backend (alternative, disabled on installed system) |

**Active backend: wpa_supplicant.** NM compile-time default is `wpa_supplicant` (meson.build:430-436: `config_wifi_backend_default='default'` → `'wpa_supplicant'`). Our packaging ships NO NM config that selects a backend, so the default applies. firstboot disables iwd on the installed system (`systemctl disable --now iwd.service`). Pinned explicitly in `configs/network/99-mavericks.conf` (`[device] wifi.backend=wpa_supplicant`).

### 4.1.2 D-Bus API surface

| Backend | D-Bus name | NM manager | Key objects |
|---|---|---|---|
| wpa_supplicant | `fi.w1.wpa_supplicant1` | `src/core/supplicant/nm-supplicant-manager.c` | Interface, BSS, Network, Group |
| iwd | `net.connman.iwd` | `src/core/devices/wifi/nm-iwd-manager.c` | Device, Station, Network, KnownNetwork, Manager |

### 4.1.3 NM config state (our packaging)

| Setting | Location | Value | Effect |
|---|---|---|---|
| `wifi.backend` | `configs/network/99-mavericks.conf` `[device]` | `wpa_supplicant` | explicit backend (no behavior change; pins default) |
| `connectivity.enabled` | `configs/network/99-mavericks.conf` `[connectivity]` | `false` | disables Arch's 300s HTTP check |
| `connectivity.uri` | Arch `/usr/lib/NetworkManager/conf.d/20-connectivity.conf` | `http://ping.archlinux.org/nm-check.txt` | shadowed by our `enabled=false` |
| `wifi.powersave` | (unset) | default `ignore` (1) | NM does not touch 802.11 PS; firmware default applies |

### 4.1.4 nl80211 command flow per NM operation

| NM operation | nl80211 command | brcmfmac handler |
|---|---|---|
| Scan (explicit/periodic) | `NL80211_CMD_TRIGGER_SCAN` | `brcmf_cfg80211_scan` (cfg80211.c:1531) → `escan` iovar |
| Connect | `NL80211_CMD_CONNECT` / auth | `brcmf_cfg80211_connect` (cfg80211.c:2381) |
| Powersave set | `NL80211_CMD_SET_POWER_SAVE` | `brcmf_cfg80211_set_power_mgmt` (cfg80211.c:3305) |
| Disconnect | `NL80211_CMD_DISCONNECT` | `brcmf_cfg80211_disconnect` (cfg80211.c:2627) |
| Signal/station | `NL80211_CMD_GET_STATION` | `brcmf_cfg80211_get_station` |

---

## 5. Wakeup sources, timers, workqueues, runtime PM

### 5.1 Interrupts

- **MSI** (not MSI-X): `pci_enable_msi(pdev)` (pcie.c:978). `IRQF_SHARED`.
- **Threaded IRQ**: `brcmf_pcie_quick_check_isr` (hard IRQ, pcie.c:928-939) reads `mailboxint`; if set → disable interrupts, return `IRQ_WAKE_THREAD`; else `IRQ_NONE` (shared IRQ optimization). `brcmf_pcie_isr_thread` (pcie.c:941-966) ACKs, handles mailbox (FN0) and D2H doorbell → `brcmf_proto_msgbuf_rx_trigger`.
- Interrupt masking: `brcmf_pcie_intr_enable/disable` (pcie.c:908-918) via `mailboxmask` register.

### 5.2 Firmware events

- Scan results, connect done, roam, disconnect, etc. → fweh worker (system_wq). Event-driven, no polling.

### 5.3 Scan

- Triggered by cfg80211 (NM/wpa_supplicant `NL80211_CMD_TRIGGER_SCAN`) → `brcmf_cfg80211_scan` (cfg80211.c:1531) → `brcmf_do_escan` → `brcmf_run_escan` (cfg80211.c:1443) → `escan` iovar → firmware.
- MPC (minimum power consumption) disabled during scan: `brcmf_scan_config_mpc(ifp, 0)` (cfg80211.c:1518).
- Scan timeout timer: `cfg->escan_timeout`, 10 s (`BRCMF_ESCAN_TIMER_INTERVAL_MS`, cfg80211.h:49), armed at scan start (cfg80211.c:1587).

### 5.4 Roaming

- Firmware-driven. `BRCMF_E_ROAM` event → `brcmf_notify_roaming_status` (cfg80211.c:6655-6672). `roamoff` module param (common.c:63) disables roaming.

### 5.5 Powersave

- 802.11 PS: `brcmf_cfg80211_set_power_mgmt` (cfg80211.c:3305-3345) → `BRCMF_C_SET_PM` with `PM_FAST`/`PM_OFF`. P2P clients always `PM_OFF`.
- No `pm_block` usage. No PM-QOS usage. Powersave is firmware-managed.

### 5.6 Timers (complete list)

| Timer | File | Active when |
|---|---|---|
| `escan_timeout` | cfg80211.c:3756 | only during scan (10 s timeout) |
| `btcoex` timer | btcoex.c:374 | only during DHCP opportunity windows (BT coex active) |
| `listen_timer` | p2p.h:127 | only during P2P listen |

**No periodic idle timers.** The driver is fully event-driven at idle.

### 5.7 Workqueues

| Workqueue | File | Nature |
|---|---|---|
| system_wq (`fweh->event_work`) | fweh.c:361 | firmware event processing; schedule_work per event batch |
| system_wq (`flowring_work`) | msgbuf.c:1667 | flowring creation; schedule_work |
| `msgbuf_txflow` (dedicated singlethread) | msgbuf.c:1581 | TX flow processing; queue_work per TX batch; **idle when no TX** |
| system_wq (`escan_timeout_work`) | cfg80211.c:3580 | scan timeout handler |
| btcoex work | btcoex.c | BT coex state machine |

### 5.8 Runtime PM / suspend-resume

- `dev_pm_ops brcmf_pciedevr_pm` (pcie.c:2708-2712): `.suspend = brcmf_pcie_pm_enter_D3`, `.resume = brcmf_pcie_pm_leave_D3`.
- Suspend: `brcmf_pcie_pm_enter_D3` (pcie.c:2636-2662) — sends `BRCMF_H2D_HOST_D3_INFORM` mailbox, waits for response (2 s timeout `BRCMF_PCIE_MBDATA_TIMEOUT`).
- Resume: `brcmf_pcie_pm_leave_D3` (pcie.c:2666-2706) — hot resume (`BRCMF_H2D_HOST_D0_INFORM`) if device still alive, else full re-probe (`brcmf_pcie_remove` + `brcmf_pcie_probe`).
- `device_wakeup_enable(&devinfo->pdev->dev)` (pcie.c:725).
- `bus->wowl_supported = pci_pme_capable(pdev, PCI_D3hot)` (pcie.c:2522).
- WoWLAN: `brcmf_wowlan_support` (cfg80211.c:7619-7625): `WIPHY_WOWLAN_MAGIC_PKT | WIPHY_WOWLAN_DISCONNECT` (+ `NET_DETECT`, `GTK_REKEY` if features enabled).

### 5.9 sysfs / debugfs surfaces

- debugfs: `/sys/kernel/debug/brcmfmac/` — entries: `revinfo`, `reset`, `msgbuf_stats` (msgbuf.c:1557), `feat` (feature.c:370). Not mounted by default → no runtime cost.
- sysfs: standard netdev attributes (`/sys/class/net/wlan0/`). No custom polling sysfs entries.

---

## 6. Re-verification commands (on target)

```bash
# PCI ID
lspci -nn | grep -i network
# Expected: 14e4:43ba (BCM43602)

# Firmware files present
ls -la /usr/lib/firmware/brcm/brcmfmac43602-pcie.*
# Expected: .bin, .ap.bin (from linux-firmware); .txt only if provisioned

# Driver loaded + firmware source
dmesg | grep -iE "brcmfmac|nvram|EFI variable"
# Look for: "Using nvram EFI variable" (EFI path) or firmware file load

# Module params
systool -m brcmfmac -av 2>/dev/null || modinfo brcmfmac

# Interrupt
cat /proc/interrupts | grep brcmf

# Powersave state
iw dev wlan0 get power_save

# Scan activity
iw dev wlan0 scan dump | head

# debugfs
mount -t debugfs none /sys/kernel/debug 2>/dev/null
ls /sys/kernel/debug/brcmfmac/
```

---

## 7. PCI IDs + firmware set (summary)

| PCI ID | Device | Notes |
|---|---|---|
| `14e4:43ba` | BCM43602 | **MacBook10,1 target** |
| `14e4:43bb` | BCM43602 2G | 2.4 GHz variant |
| `14e4:43bc` | BCM43602 5G | 5 GHz variant |
| `14e4:43602` | BCM43602 RAW | raw device |

Chip ID: `BRCM_CC_43602_CHIP_ID = 43602` (brcm_hw_ids.h:48). TCM rambase: `0x180000` (chip.c:725). Firmware vendor: WCC (pcie.c:2746-2749).

Firmware set expected on target:
- `/usr/lib/firmware/brcm/brcmfmac43602-pcie.bin` (linux-firmware)
- `/usr/lib/firmware/brcm/brcmfmac43602-pcie.ap.bin` (linux-firmware)
- `/usr/lib/firmware/brcm/brcmfmac43602-pcie.txt` (provisioned by firstboot — NOT in linux-firmware)

---

## 5. i915 display path runtime map (D3, 2026-09-28)

> Deep Runtime Track D3. Target: MacBook10,1, Intel HD 615 (Gen9.5, Kaby Lake, device ID 591e).
> Source: Linux master (torvalds) i915 display code, fetched via codebrowser.dev.

### 5.1 i915 power domains and power wells

**Power domains** (intel_display_power.c:47-206): The i915 display engine is divided into
fine-grained power domains — `DISPLAY_CORE`, `PIPE_A/B/C`, `TRANSCODER_A/B/C/EDP`,
`PORT_DDI_LANES_*`, `PORT_DDI_IO_*`, `AUX_IO_*`, `AUX_*`, `GMBUS`, `DC_OFF`, `GT_IRQ`.
Each domain maps to one or more hardware power wells. Domains are reference-counted
(`domain_use_count[]`); the async-put mechanism (`__intel_display_power_put_async`,
intel_display_power.c:742-785) schedules power-down after a 100ms delay when the last
reference is dropped.

**Gen9 power wells** (intel_display_power_well.c, skl_power_wells[]):
- `SKL_DISP_PW_1` (PG1): display core, always-on dependency for most domains
- `SKL_DISP_PW_2` (PG2): pipe/transcoder/DDI/AUX power; disabling triggers DC5/6 entry
- `SKL_DISP_PW_MISC_IO`: misc I/O (firmware, DMC communication)
- `SKL_DISP_DC_OFF`: controls DC state target; disabling allows DC5/6 entry

**DC states** (intel_display_power.c:951-1019): Gen9 (DISPLAY_VER=9) supports
`max_dc=2` → `DC_STATE_EN_UPTO_DC6`. The `allowed_dc_mask` is set from `enable_dc`
module param (default -1 → max). DC5/DC6 entry is asynchronous; exit is synchronous
(DC_STATE_EN write blocks until HW restores). DMC firmware coordinates entry/exit.

**DMC firmware** (intel_dmc.c:45-51): From Gen9 onwards, the Display Microcontroller
(DMC) saves/restores display engine state during DC transitions. Kaby Lake uses
`i915/kbl_dmc.bin` (intel_dmc.c:235-239). DMC is loaded on resume
(`skl_display_core_init` → `intel_dmc_load_program`, intel_display_power.c:1486).
Without DMC firmware, DC5/6 entry is blocked (display stays in DC0).

### 5.2 PSR (Panel Self Refresh) entry/exit path

**PSR1 vs PSR2** (intel_psr.c:190-205):
- PSR1: full-frame self-refresh; panel RFB caches entire framebuffer
- PSR2: selective update; only dirty regions sent (requires Y-coordinate support)
- Gen9 (DISPLAY_VER=9): PSR2 supported if `sink_psr2_support` (DPCD PSR version ≥ 03h
  + Y-coord + ALPM aux wake) — intel_psr.c:704-724

**PSR entry** (intel_psr.c:948-984, hsw_activate_psr1):
1. `psr_compute_idle_frames()`: min 6 idle frames + sink sync latency
2. TP1/TP2/TP3 timing from VBT (panel-specific)
3. `EDP_PSR_CTL` write → HW starts entry sequence
4. Entry takes ~2 vblanks (PSR2: `EDP_PSR2_CTL` + `PSR2_MAN_TRK_CTL`)
5. Frontbuffer tracking: `intel_psr_invalidate()` called on FB dirty → PSR exit triggered

**PSR exit** (intel_psr.c:432-481, intel_psr_irq_handler):
- Triggers: frontbuffer modification, vblank/vsync interrupt, register writes,
  cursor move (CURPOS), HDCP enable, KVMR session
- `PSR_EVENT` register logs exit reason (intel_psr.c:394-430)
- Exit completes asynchronously; `last_exit` timestamp recorded

**PSR + DC5/6 interaction** (intel_psr.c:935-946, is_dc5_dc6_blocked):
- PSR entry blocked if `current_dc_state < DC5` OR `vblank->enabled` OR
  `active_non_psr_pipes` — PSR and DC5/6 are mutually exclusive on Gen9

### 5.3 FBC (Frame Buffer Compression)

**Gen9 FBC** (intel_fbc.c:25-39): FBC compresses the display framebuffer in stolen
memory, reducing memory bandwidth. Transparent to userspace.
- Compression limit: 1:1 to 1:4 (intel_fbc.c:823-834)
- CFB allocated from stolen memory (intel_fbc.c:861-900)
- Gen9 stride: 512-byte aligned (intel_fbc.c:199-200)
- Nuke on flip: `intel_fbc_nuke()` writes DSPADDR to trigger re-compress
- FBC + PSR1: mutually exclusive on Gen12+ (Wa_14016291713, intel_fbc.c:1561-1566);
  on Gen9 they can coexist

### 5.4 Forcewake model

**Forcewake** (intel_display_power.c:1347, 1377): Register access in low-power states
requires `intel_uncore_forcewake_get(FORCEWAKE_ALL)`. The forcewake mechanism
temporarily powers the GT (graphics) domain to allow MMIO reads/writes. Released
via `intel_uncore_forcewake_put()`. Needed during LCPLL disable/restore (PC8+).

### 5.5 GEM/fence activity

**Legacy fencing** (intel_fbc.c:268-273): Gen9 uses legacy fencing
(`intel_gt_support_legacy_fencing`). FBC uses `fence_id` to detect scanout writes.
`i915_vma_fence_id()` returns the fence associated with a GEM object's PPGTT mapping.
FBC nuke is triggered when the fence is re-written (new flip).

### 5.6 Backlight PWM control path

**Gen9 backlight** (intel_backlight.c:195-201, bxt_get_backlight):
- Register: `BXT_BLC_PWM_DUTY(controller)` — PWM duty cycle
- PWM frequency: from VBT (`pwm_freq_hz`, default 200Hz) — intel_backlight.c:1162-1179
- `pwm_level_max`: 16-bit value written to `BXT_BLC_PWM_FREQ`
- Enable: `BXT_BLC_PWM_CTL` → `BXT_BLC_PWM_ENABLE` bit
- Controller 1 uses utility pin (`UTIL_PIN_CTL`) — intel_backlight.c:689-705
- Brightness scaling: user [0..255] → hw [pwm_level_min..pwm_level_max] via `scale()`

### 5.7 DPST (Display Power Saving Technology)

**DPST is NOT present on Gen9.5 eDP.** DPST is a DisplayPort link-layer power-saving
feature (reduces link rate/lanes during idle). It applies to external DP outputs,
not to the internal eDP panel. The internal panel uses PSR (panel self-refresh) +
DC5/6 (display power wells) for power saving. No DPST code path exists in the
i915 eDP driver for Gen9. Our stance: DPST is irrelevant for the MacBook10,1
internal display; PSR + DC5/6 + FBC are the relevant power-saving mechanisms.

### 5.8 vblank/pageflip path under xfwm4

**xfwm4 compositing** (configs/desktop/xfce/xfwm4.xml):
- `use_compositing=true` — compositor active
- `vblank_mode=off` — PROVISIONAL: no vsync wait; pageflips at render rate
- `unredirect_overlays=true` — PROVISIONAL: fullscreen windows bypass compositor
- Shadows: `show_dock_shadow=true`, `show_popup_shadow=true`, `shadow_opacity=50`

**Pageflip flow**: xfwm4 → X11 Present extension → DRM_IOCTL_MODE_PAGE_FLIP →
i915 `intel_crtc_page_flip()` → plane flip → vblank interrupt. With `vblank_mode=off`,
the compositor renders immediately without waiting for vblank → higher CPU/GPU
load but lower latency. PSR entry is blocked while vblank is enabled
(intel_psr.c:945: `READ_ONCE(vblank->enabled)`).

**Cursor plane**: Gen9 has a hardware cursor plane (CURBASE). Cursor moves trigger
PSR exit (intel_psr.c:139-144: `PIPE_MISC_PSR_MASK_CURSOR_MOVE`). The compositor
can use the hardware cursor plane to avoid full-frame updates on cursor movement.

### 5.9 Re-verification commands (on target)

```bash
# Power wells
cat /sys/kernel/debug/dri/0/i915_power_well_count 2>/dev/null
cat /sys/kernel/debug/dri/0/i915_display_power 2>/dev/null

# DC state
cat /sys/kernel/debug/dri/0/i915_dc_state 2>/dev/null

# PSR status
cat /sys/kernel/debug/dri/0/i915_edp_psr_status 2>/dev/null
cat /sys/kernel/debug/dri/0/i915_edp_psr_sink_status 2>/dev/null

# FBC status
cat /sys/kernel/debug/dri/0/i915_fbc_status 2>/dev/null

# DMC firmware
cat /sys/kernel/debug/dri/0/i915_dmc_info 2>/dev/null

# Backlight
cat /sys/class/backlight/intel_backlight/brightness
cat /sys/class/backlight/intel_backlight/max_brightness

# Forcewake
cat /sys/kernel/debug/dri/0/i915_forcewake_count 2>/dev/null
```

---

## 8. AUDIO component map — HDA / Cirrus CS4208 / PipeWire (D4, 2026-09-28)

> Deep Runtime Track D4. Target: MacBook10,1, Cirrus CS4208 codec on Intel HDA (PCI 00:1f.3).
> Source basis: driver source (leifliddy/macbook12-audio-driver r108.g4cdfcdb, vendored in
> packages/macbook12-audio-driver/src/), linux-7.2.6 source (kernel.org tarball), PipeWire 1.6.9 /
> WirePlumber 0.5.17 (Arch repos). Build behavior empirically verified in the build container
> (§8.4). No driver modifications — map + audit only.

### 8.1 Hardware path

| Layer | Device | Driver | Notes |
|---|---|---|---|
| HDA controller | Intel Sunrise Point-LP HDA, PCI 00:1f.3 | snd-hda-intel (in-tree) | power_save + runtime PM (TLP-owned) |
| Codec | Cirrus CS4208 (vendor NID 0x24) | snd-hda-codec-cs420x (DKMS, replaces in-tree) | A1534 init unconditional in patch_cs4208() |
| Speaker path | digital: converter 0x0a → pin 0x1d, amp via GPIO | codec driver verbs | no hardware volume → software mixer required |
| Headphone path | analog DAC: converter 0x02 → pin 0x10 | codec driver verbs | hardware amp lives on this path |
| Mic path | internal mic ADC | codec driver | — |
| Jack detection | GPIO interrupt | codec driver (cs_4208_playback_pcm_hook) | re-points stream on plug/unplug |

### 8.2 Driver structure (snd-hda-codec-cs420x, 6.17+ layout)

| File | Role |
|---|---|
| patch_cirrus/cs420x.c | CS420x codec driver: fixups, patch_cs4208() with unconditional setup_a1534/play_a1534, cs_4208_playback_pcm_hook (jack switching), amp cap overrides |
| patch_cirrus/patch_cirrus.c | pre-6.17 layout (old patch_cirrus path) — not built on 6.17+ |
| patch_cirrus/patch_cirrus_a1534_setup.h | macOS-init verb sequence (1678 lines) + coef helpers |
| patch_cirrus/patch_cirrus_a1534_pcm.h | PCM hook: jack detect → re-point stream, speaker pin disable (444 lines) |
| patch_cirrus/Makefile_cs420x | in-tree kbuild Makefile (subdir-ccflags -I../../common) |

### 8.3 ALSA / UCM / PipeWire graph

- **UCM:** no UCM for CS4208 exists upstream (alsa-ucm-conf has no cs4208/Cirrus
  entry — verified via GitHub API, ucm2/ tree listing) and we ship none. The card
  uses the generic HiFi UCM profile / fallback; mixer setup is done by the codec
  driver itself. Consistent — no UCM gap to fill.
- **Software volume:** the speaker path has no hardware volume control (the only
  analog amp is on the headphone path). WirePlumber rule
  `api.alsa.soft-mixer=true` for `alsa_card.pci-0000_00_1f.3` (installed by the
  macbook12-audio-driver package since D4, 888e0ff) makes PipeWire apply volume
  in software. Without it the volume slider does nothing on speakers (driver
  README, "required" step).
- **PipeWire graph at idle:** pipewire daemon + wireplumber run always
  (event-driven, epoll). With zero streams both idle — no per-stream nodes
  exist, no polling. WirePlumber Lua scripts run on graph changes only.
- **pactl sites:** all on-demand (see RUNTIME_AUDIT.md AUDIO section). No audio
  polling anywhere in our stack.

### 8.4 Build verification (empirical, build container)

| Test | Result |
|---|---|
| `dkms install` flow (dkms.conf MAKE[0], M=<srcroot>) | **FAIL** — no root Makefile in DKMS source tree |
| External build vs linux-zen-headers only | **FAIL** — internal HDA headers not shipped in headers package (0 .h under sound/hda) |
| Driver source vs linux-7.2.6 source + headers (external, -I sound/hda/common) | **PASS** — snd-hda-codec-cs420x.ko builds (1.75MB, GPL, alias hdaudio:v10134208) |

### 8.5 Wakeup sources, timers, runtime PM

| Source | Type | Expectation |
|---|---|---|
| HDA controller runtime PM | power_save=1 (1s) + controller PM (TLP defaults) | controller in D3hot ~1s after stream end |
| Jack GPIO interrupt | edge wake from D3hot | wakes controller on plug/unplug only |
| pipewire daemon | epoll idle | no wakeups at zero streams |
| wireplumber | graph-change events | no wakeups at zero streams |
| mv-control / mv-voice | on-demand processes | zero idle presence |

### 8.6 Re-verification commands (on target)

```
# driver loaded (DKMS module, not the in-tree stub)
modinfo snd_hda_codec_cs420x | grep filename   # → .../updates/... or dkms path
# controller power
cat /sys/bus/pci/devices/0000:00:1f.3/power/runtime_status   # suspended at idle (TLP)
cat /sys/module/snd_hda_intel/parameters/power_save           # 1 (TLP default)
# codec power state
grep -A2 "Power:" /proc/asound/card0/codec#0                  # D0/D3 + clock gate
# graph idle
pw-top                                                        # no RUNNING nodes with zero streams
pw-dump | grep soft-mixer                                     # api.alsa.soft-mixer on the card
# jack switching
wpctl status                                                  # sink follows plug/unplug
```

### 8.7 Codec + driver summary

| Item | Status |
|---|---|
| Driver source compiles on target kernel (7.2.6) | VERIFIED (build container) |
| DKMS packaging buildable | BROKEN (no root Makefile; internal headers not in headers package) |
| ISO inclusion | NO (would break pacstrap) — see DECISIONS D4 |
| Recommended path forward | track tanisperez fork (working DKMS PRE_BUILD) — separate track |

---

## 9. INPUT component map — Apple SPI / HID / libinput (D5, 2026-09-28)

> Deep Runtime Track D5. Target: MacBook10,1, Apple SPI keyboard + Force Touch trackpad.
> Source basis: applespi driver (roadrunner2/macbook12-spi-driver, GPL-2.0), fetched from
> GitHub raw. Linux 7.3.0-rc5 (torvalds) input subsystem. libinput 1.27+ (Arch).
> NO driver modifications. This is a map + audit only.

### 9.1 Hardware path

| Layer | Device | Driver | Notes |
|---|---|---|---|
| SPI controller | Intel Sunrise Point-LP SPI (rev3+) | spi_pxa2xx_platform (in-tree) | rev3+ has SPI transfer timeout bug on 6.15+ |
| SPI device | Apple keyboard + trackpad controller | applespi (AUR DKMS) | ACPI GPE interrupt, not SPI IRQ |
| Keyboard input | "Apple SPI Keyboard" | applespi → input_dev | EV_KEY + EV_LED, 6KRO |
| Trackpad input | "Apple SPI Touchpad" | applespi → input_dev | INPUT_PROP_POINTER \| INPUT_PROP_BUTTONPAD, MT slots |
| X11 input | evdev/libinput | xorg-server | libinput handles multitouch |
| Window manager | xfwm4 | xfwm4 | standard X11 window management |

### 9.2 applespi driver structure

| File | Role |
|---|---|
| `applespi.c` | SPI protocol driver: probe/remove, GPE handler, read/write async, input dev registration |
| `applespi.h` | (not fetched — header-only, included by .c) |
| `appleacpi.c` | ACPI driver: matches "topcase" class, registers SPI slave when master appears |

### 9.3 Interrupt model — ACPI GPE (NOT SPI IRQ)

**Critical finding:** The applespi driver does NOT use a traditional SPI interrupt. Instead it uses
an **ACPI GPE (General Purpose Event)** — a level-triggered ACPI event.

| Aspect | Detail |
|---|---|
| GPE installation | `acpi_install_gpe_handler(NULL, gpe, ACPI_GPE_LEVEL_TRIGGERED, applespi_notify, applespi)` (applespi.c:1860-1865) |
| GPE enable | `acpi_enable_gpe(NULL, gpe)` (applespi.c:1870) |
| GPE handler | `applespi_notify()` (applespi.c:1690-1710) — queues async SPI read |
| GPE re-enable | `acpi_finish_gpe(NULL, gpe)` in `applespi_async_read_complete()` (applespi.c:1740) |
| Trigger type | Level-triggered (ACPI_GPE_LEVEL_TRIGGERED) |
| Wake from suspend | **NO** — `applespi_suspend()` calls `acpi_disable_gpe()` (applespi.c:1765) |

**Implication:** The keyboard does NOT wake the system from suspend. This is a known
limitation of the applespi driver. External USB keyboard can wake via USB resume.

### 9.4 Timeout-retry behavior (source-level)

**Critical finding:** The applespi driver has **NO retry loop** for failed SPI transfers.

| Scenario | Behavior | Source |
|---|---|---|
| SPI read fails | `applespi_async_read_complete()` logs `pr_warn("Error reading from device: %d\n", status)` and calls `acpi_finish_gpe()` — GPE re-enabled, but NO retry | applespi.c:1735-1740 |
| SPI write fails | `applespi_async_write_complete()` logs `pr_warn("Error writing to device: %d\n", sts)` or `pr_warn("Error writing to device: %x %x %x %x\n", ...)` — NO retry | applespi.c:1560-1575 |
| CRC mismatch | `applespi_verify_crc()` returns false → `dev_warn_ratelimited("Received corrupted packet (crc mismatch)")` → packet dropped, NO retry | applespi.c:1620-1630 |
| Invalid packet length | `dev_warn_ratelimited("Received corrupted packet (invalid packet length)")` → dropped | applespi.c:1655-1660 |
| Invalid message length | `dev_warn_ratelimited("Received corrupted packet (invalid message length)")` → dropped | applespi.c:1690-1695 |

**Root cause of 6.15+ failure:** The SPI controller (spi_pxa2xx_platform) on MacBook10,1
(rev3+) has a hardware/firmware bug where SPI transfers timeout. The applespi driver
sees this as a failed `spi_async()` call — it logs the error and moves on. There is
no mechanism to recover the lost keyboard/trackpad event. The result is intermittent
or complete input failure.

**dmesg signature of SPI timeout:**
```
applespi: Error reading from device: -110   (ETIMEDOUT)
applespi: Error writing to device: -110
```

### 9.5 Polling vs interrupt

**Pure interrupt-driven (GPE).** No polling. No timers. No workqueues for input processing.
The driver is completely event-driven: GPE fires → async SPI read → input event → done.

### 9.6 Power management

| Aspect | Detail |
|---|---|
| Runtime PM | **NONE** — no `runtime_suspend`/`runtime_resume` in `applespi_pm_ops` |
| System suspend | `applespi_suspend()` — drains outstanding writes/reads, disables GPE |
| System resume | `applespi_resume()` — re-enables GPE, re-initializes touchpad (sends init command) |
| PM ops | `UNIVERSAL_DEV_PM_OPS(applespi_pm_ops, applespi_suspend, applespi_resume, NULL)` (applespi.c:1828) |
| Keyboard backlight | LED classdev `spi::kbd_backlight` — `applespi_set_bl_level()` sends SPI command |
| Autosuspend | N/A — SPI slave device, no runtime PM |

**Power implication:** The applespi device stays powered as long as the system is in S0.
There is no runtime power management for the SPI controller or the input device.
The only power saving is at system suspend (S3/s2idle).

### 9.7 External USB-C HID path (reference-good)

| Aspect | Detail |
|---|---|
| Interrupt | USB interrupt endpoint (HID) |
| Driver | hid-generic / hid-apple (in-tree) |
| Runtime PM | USB autosuspend (TLP `USB_AUTOSUSPEND=1`) |
| Wake from suspend | YES — USB remote wakeup |
| libinput | Standard evdev device, full multitouch + acceleration |

**This is the bring-up interface.** External USB-C keyboard/mouse works out of the box
with zero configuration. All keyboard shortcuts, trackpad gestures, and media keys
function through this path.

### 9.8 libinput configuration (our packaging)

| Setting | Location | Value | Effect |
|---|---|---|---|
| Quirks | NONE shipped | — | No Apple-specific libinput quirks |
| hwdb | NONE shipped | — | No Apple-specific hwdb entries |
| Accel profile | libinput default | `adaptive` | Standard pointer acceleration |
| Tap-to-click | libinput default | enabled for trackpad | Standard tap-to-click |
| Scroll method | libinput default | two-finger | Standard two-finger scroll |

**Verdict:** No libinput configuration needed. The applespi touchpad is a standard
multitouch device (INPUT_PROP_POINTER | INPUT_PROP_BUTTONPAD) and libinput handles
it with default settings. Force Touch pressure is NOT reported (no ABS_MT_PRESSURE
in the driver) — this is a driver limitation, not a libinput issue.

### 9.9 Re-verification commands (on target)

```bash
# SPI controller + driver loaded
lsmod | grep -E "applespi|spi_pxa"
dmesg | grep -iE "applespi|spi"

# Input devices
libinput list-devices | grep -A5 "Apple SPI"
cat /proc/bus/input/devices | grep -A10 "Apple SPI"

# GPE status
cat /proc/interrupts | grep -i gpe

# SPI timeout check
dmesg | grep -i "Error reading from device\|Error writing to device"

# Touchpad capabilities
cat /sys/class/input/event*/device/name  # find Apple SPI Touchpad event
evtest /dev/input/eventXX  # test raw events

# External USB HID (reference)
lsusb -t
libinput list-devices | grep -A5 "USB"
```

### 9.10 Input summary

| Item | Status |
|---|---|
| Driver source | VERIFIED — applespi.c (GPL-2.0, roadrunner2) |
| Interrupt model | ACPI GPE (level-triggered), NOT SPI IRQ |
| Timeout behavior | NO retry — logs error, drops event |
| Runtime PM | NONE — device stays powered in S0 |
| Wake from suspend | NO — GPE disabled in suspend |
| Polling | NONE — pure interrupt-driven |
| libinput config | NONE needed — standard multitouch device |
| External USB-C HID | Reference-good — full functionality |
| 6.15+ compatibility | BROKEN — SPI controller rev3+ timeout bug |
| AUR package | macbook12-spi-driver-dkms (strategy A) |
| 3-strategy limit | A: AUR DKMS, B: linux-macbook patches, C: linux-lts |

---

## 10. STORAGE component map — Apple S3X NVMe / btrfs / zram (D5, 2026-09-28)

> Deep Runtime Track D5. Target: MacBook10,1, Apple S3X NVMe (106b:2003), btrfs root.
> Source basis: Linux 7.3.0-rc5 (torvalds) nvme core, btrfs, systemd zram-generator.
> NO driver modifications. This is a map + audit only.

### 10.1 Hardware path

| Layer | Device | Driver | Notes |
|---|---|---|---|
| PCIe root port | Intel Sunrise Point-LP PCH 00:1c.0 | pcieport | L1 PM Substates capable |
| NVMe controller | Apple S3X (106b:2003) | nvme (in-tree) | Apple proprietary, no APST |
| Block device | /dev/nvme0n1 | block layer | — |
| Filesystem | btrfs (subvol @) | btrfs (in-tree) | rootflags=subvol=@ |
| Swap | zram0 (zstd) | zram-generator | zram-size = ram/2 |

### 10.2 S3X NVMe controller behavior

| Aspect | Detail |
|---|---|
| PCI ID | 106b:2003 (Apple S3X) |
| APST | **NOT exposed** — S3X does not support APST (Autonomous Power State Transition) |
| ASPM | Supported but problematic — `pcie_port_pm=off` disables root port runtime PM |
| Resume bug | S3X becomes unresponsive after S3/s2idle resume without `pcie_port_pm=off` |
| LKML status | Thread open (Sep 2026) — no upstream fix yet |
| Workaround | `pcie_port_pm=off` (global, disables ALL PCIe root port PM) |

### 10.3 APST states

**S3X does NOT expose APST.** The `nvme_core.default_ps_max_latency_us` module parameter
controls APST for standard NVMe controllers, but S3X ignores it. The controller stays
in D0 (active) at all times. There is no autonomous power state transition.

**Implication:** The NVMe controller is always powered. The only power saving comes
from PCIe ASPM (L0s/L1 link states) and system suspend (S3/s2idle).

### 10.4 ASPM interplay with pcie_port_pm=off

| Setting | Effect | Power cost |
|---|---|---|
| `pcie_port_pm=off` (our baseline) | Disables ALL PCIe root port runtime PM | NVMe stays in D0 — higher idle power |
| `pcie_port_pm=on` (default) | Enables root port runtime PM | NVMe can enter D3hot — lower idle power |
| `pcie_aspm=off` | Disables ASPM entirely | Highest idle power |
| `pcie_aspm=powersave` (TLP) | Enables ASPM L0s/L1 | Lower idle power |

**Cost statement:** With `pcie_port_pm=off`, we leave PCIe root port runtime PM on the
table. The NVMe controller cannot enter D3hot, so it stays in D0 at idle. The exact
power cost is unmeasured (requires hardware). The LKML thread (Sep 2026) asks if a
PCI quirk for 00:1c.0 is possible instead of the global disable.

**Counters that prove it on HW:**
- `/sys/bus/pci/devices/0000:00:1c.0/power/runtime_status` → `active` (with pcie_port_pm=off) vs `suspended` (without)
- `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status` → `active` vs `suspended`
- `nvme smart-log /dev/nvme0` → power state transitions
- Battery discharge rate with/without `pcie_port_pm=off`

### 10.5 btrfs mount options (our packaging)

| Option | Location | Value | Effect |
|---|---|---|---|
| subvol=@ | kernel cmdline | `rootflags=subvol=@` | Root subvolume |
| noatime | NOT set | kernel default `relatime` | atime updated on read if older than mtime |
| discard | NOT set | kernel default (no discard) | No real-time TRIM |
| commit | NOT set | kernel default 30s | btrfs commit interval |
| ssd | NOT set | kernel default | No SSD-specific optimizations |
| space_cache | NOT set | kernel default | v1 space cache |

**Verdict:** Our btrfs mount options are minimal. The kernel defaults are mostly fine
for SSD (relatime is frugal, no discard is correct). The main gap is **no `noatime`**
— but `relatime` only updates atime if the file was modified since the last atime
update, so the write amplification is minimal.

### 10.6 fstrim timer state

| Aspect | Detail |
|---|---|
| fstrim.timer | systemd timer, weekly |
| Enabled in our ISO | **NO** — not explicitly enabled in firstboot |
| Enabled on installed | **NO** — firstboot does not enable it |
| Effect | No periodic TRIM — SSD performance may degrade over time |

**Recommendation:** Enable `fstrim.timer` on the installed system. This is a one-line
addition to the firstboot script. The cost is negligible (weekly oneshot, ~seconds).

### 10.7 zram config sanity

| Setting | Location | Value | Correct? |
|---|---|---|---|
| zram-size | zram-generator.conf.d/99-mavericks.conf | ram / 2 | YES — per baseline |
| compression-algorithm | zram-generator.conf.d/99-mavericks.conf | zstd | YES — per baseline |
| disk swap | NONE | — | YES — no disk swap per baseline |

### 10.8 journald config

| Setting | Location | Value | Effect |
|---|---|---|---|
| Storage | journald.conf.d/99-mavericks.conf | volatile | RAM-only, no disk writes |
| RuntimeMaxUse | journald.conf.d/99-mavericks.conf | 50M | Cap on RAM journal |
| SystemMaxUse | journald.conf.d/99-mavericks.conf | 100M | Cap on disk journal (if persistent) |
| ForwardToSyslog | journald.conf.d/99-mavericks.conf | no | No syslog forwarding |

**Note:** The firstboot script removes `volatile-storage.conf` on the installed system
(line 90), making journald persistent. The `99-mavericks.conf` limits still apply.

### 10.9 Re-verification commands (on target)

```bash
# NVMe controller
lspci -nn | grep -i nvme
nvme list
nvme smart-log /dev/nvme0

# PCIe power
cat /sys/bus/pci/devices/0000:00:1c.0/power/runtime_status
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status

# btrfs
btrfs filesystem show /
btrfs filesystem df /
cat /proc/mounts | grep btrfs

# fstrim
systemctl status fstrim.timer
fstrim -av /

# zram
zramctl
cat /sys/block/zram0/comp_algorithm

# journald
journalctl --disk-usage
cat /etc/systemd/journald.conf.d/99-mavericks.conf
```

### 10.10 Storage summary

| Item | Status |
|---|---|
| S3X NVMe | VERIFIED — 106b:2003, no APST, resume bug |
| APST | NOT exposed — S3X stays in D0 |
| ASPM | `pcie_port_pm=off` disables root port PM — battery cost unmeasured |
| btrfs mount | Minimal — kernel defaults, no noatime |
| fstrim.timer | NOT enabled — should be enabled for SSD health |
| zram | CORRECT — ram/2, zstd, no disk swap |
| journald | CORRECT — volatile in ISO, persistent on install with limits |
| LKML status | Thread open (Sep 2026) — no upstream fix yet |
