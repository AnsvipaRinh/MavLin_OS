# RUNTIME SOURCE AUDIT — NETWORK (brcmfmac / BCM43602)

> Deep Runtime Track D1. Audit date: 2026-09-28. Source: Linux 7.3.0-rc5 (torvalds) brcmfmac + linux-firmware WHENCE.
> Method: full source fetch from git.kernel.org plain endpoint; every claim cites file:line. Host had no kernel source; re-verify on target (see RUNTIME_COMPONENT_MAP.md §6).
> NO driver modifications. Findings classified: KEEP / CONFIG-CANDIDATE / UPSTREAM-CANDIDATE / LOCAL-CANDIDATE / FALSE-POSITIVE.

---

## 1. Firmware event processing path

| Field | Value |
|---|---|
| Component | fweh (firmware event handler) |
| Source file | `fweh.c` |
| Function | `brcmf_fweh_process_event` (fweh.c:480), `brcmf_fweh_event_worker` (fweh.c:361), `brcmf_fweh_queue_event` (fweh.c:94) |
| Hypothesis | Event processing is efficient: single work item on system_wq, event queue with lock, no per-packet logging |
| Evidence | `schedule_work(&fweh->event_work)` (fweh.c:94); `INIT_WORK(&fweh->event_work, brcmf_fweh_event_worker)` (fweh.c:361); event mask via `event_msgs` iovar (fweh.c:460-466) |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 2. RX/TX path

| Field | Value |
|---|---|
| Component | MSGBUF protocol |
| Source file | `msgbuf.c` |
| Function | TX: `brcmf_netdev_start_xmit` (core.c:293) → `brcmf_proto_tx_queue_data` → `brcmf_msgbuf_tx_queue_data` (msgbuf.c:823) → `brcmf_msgbuf_schedule_txdata` (msgbuf.c:808) → `brcmf_msgbuf_txflow_worker` (msgbuf.c:795) on `msgbuf_txflow` wq. RX: `brcmf_proto_msgbuf_rx_trigger` (msgbuf.c:1404) → `brcmf_msgbuf_process_rx` (msgbuf.c:1372) → `brcmf_msgbuf_process_rx_complete` (msgbuf.c:1173) |
| Hypothesis | TX uses a dedicated singlethread workqueue (`msgbuf_txflow`, msgbuf.c:1581) that is idle when no TX; RX is interrupt-driven with buffer posting; no per-packet logging |
| Evidence | `msgbuf->txflow_wq = create_singlethread_workqueue("msgbuf_txflow")` (msgbuf.c:1581); `queue_work(msgbuf->txflow_wq, &msgbuf->txflow_work)` only when `outstanding_tx < BRCMF_MSGBUF_DELAY_TXWORKER_THRS` (msgbuf.c:812); RX buffer posting via `brcmf_msgbuf_rxbuf_data_post` (msgbuf.c:932) |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 3. Scan path

| Field | Value |
|---|---|
| Component | escan (enhanced scan) |
| Source file | `cfg80211.c` |
| Function | `brcmf_cfg80211_scan` (cfg80211.c:1531) → `brcmf_do_escan` (cfg80211.c:1506) → `brcmf_run_escan` (cfg80211.c:1443) → `escan` iovar. Timeout: `brcmf_escan_timeout` (cfg80211.c:3586) → `brcmf_cfg80211_escan_timeout_worker` (cfg80211.c:3576) |
| Hypothesis | Scan is firmware-offloaded (escan iovar); MPC disabled during scan; 10 s timeout timer; no host-side per-channel logging |
| Evidence | `brcmf_scan_config_mpc(ifp, 0)` (cfg80211.c:1518); `mod_timer(&cfg->escan_timeout, jiffies + msecs_to_jiffies(BRCMF_ESCAN_TIMER_INTERVAL_MS))` (cfg80211.c:1587-1588); `BRCMF_ESCAN_TIMER_INTERVAL_MS = 10000` (cfg80211.h:49); ESCAN V2 vs V1 via `BRCMF_FEAT_SCAN_V2` (cfg80211.c:1471) |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 4. Roaming

| Field | Value |
|---|---|
| Component | firmware roaming |
| Source file | `cfg80211.c` |
| Function | `brcmf_notify_roaming_status` (cfg80211.c:6655-6672); `BRCMF_E_ROAM` event handler registered at cfg80211.c:6812 |
| Hypothesis | Roaming is firmware-driven; driver only receives `BRCMF_E_ROAM` event and updates cfg80211; `roamoff` module param disables |
| Evidence | `if (event == BRCMF_E_ROAM && status == BRCMF_E_STATUS_SUCCESS)` (cfg80211.c:6662); `settings->roamoff` checked at cfg80211.c:606, 6923, 7714 |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 5. Powersave

| Field | Value |
|---|---|
| Component | 802.11 power save |
| Source file | `cfg80211.c` |
| Function | `brcmf_cfg80211_set_power_mgmt` (cfg80211.c:3305-3345) → `BRCMF_C_SET_PM` iovar |
| Hypothesis | Powersave is firmware-managed via `PM_FAST`/`PM_OFF`; P2P clients always `PM_OFF`; no `pm_block` or PM-QOS usage |
| Evidence | `pm = enabled ? PM_FAST : PM_OFF` (cfg80211.c:3326); `if (ifp->vif->wdev.iftype == NL80211_IFTYPE_P2P_CLIENT) { pm = PM_OFF; }` (cfg80211.c:3328-3331); no `pm_block` symbol in any brcmfmac file |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 6. Suspend/resume hooks

| Field | Value |
|---|---|
| Component | PCIe runtime PM |
| Source file | `pcie.c` |
| Function | `brcmf_pcie_pm_enter_D3` (pcie.c:2636-2662), `brcmf_pcie_pm_leave_D3` (pcie.c:2666-2706); `dev_pm_ops brcmf_pciedevr_pm` (pcie.c:2708-2712) |
| Hypothesis | Suspend sends D3 inform mailbox with 2 s timeout; resume uses hot resume (D0 inform) or full re-probe; `device_wakeup_enable` called; WoWLAN capability from `pci_pme_capable(PCI_D3hot)` |
| Evidence | `brcmf_pcie_send_mb_data(devinfo, BRCMF_H2D_HOST_D3_INFORM)` (pcie.c:2648); `wait_event_timeout(devinfo->mbdata_resp_wait, devinfo->mbdata_completed, BRCMF_PCIE_MBDATA_TIMEOUT)` (pcie.c:2650-2651); `BRCMF_PCIE_MBDATA_TIMEOUT = msecs_to_jiffies(2000)` (pcie.c:269); `device_wakeup_enable(&devinfo->pdev->dev)` (pcie.c:725); `bus->wowl_supported = pci_pme_capable(pdev, PCI_D3hot)` (pcie.c:2522) |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 7. Retry loops

| Field | Value |
|---|---|
| Component | firmware download |
| Source file | `pcie.c` |
| Function | `brcmf_pcie_download_fw_nvram` (pcie.c:1693) — has `loop_counter` for shared RAM address written check |
| Hypothesis | Retry loop is bounded and one-time at init; not a runtime concern |
| Evidence | `loop_counter` local var (pcie.c:1700); `sharedram_addr_written = brcmf_pcie_read_ram32(...)` (pcie.c:1753) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 8. Logging verbosity

| Field | Value |
|---|---|
| Component | brcmfmac debug |
| Source file | `common.c`, `pcie.c` |
| Function | `brcmf_msg_level` module param (common.c:42, `module_param_named(debug, brcmf_msg_level, int, 0600)`); `brcmf_dbg(PCIE/DATA/SCAN/TRACE, ...)` macros |
| Hypothesis | Default log level is quiet; no per-packet `dev_info`; `brcmf_dbg` is compiled out at runtime unless `debug` param set; console read in ISR thread is no-op unless `BRCMF_FWCON_ON()` debug flag |
| Evidence | `module_param_named(debug, brcmf_msg_level, int, 0600)` (common.c:42); `brcmf_dbg(DATA, "Enter, bsscfgidx=%d\n", ...)` (core.c:299) is trace-level; `brcmf_pcie_bus_console_read` early-returns `if (!error && !BRCMF_FWCON_ON())` (pcie.c:871); `brcmf_pcie_fwcon_timer` early-returns `if (... || !BRCMF_FWCON_ON())` (pcie.c:2322) |
| Risk | none identified |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 9. Redundant state refresh

| Field | Value |
|---|---|
| Component | preinit dcmds |
| Source file | `common.c` |
| Function | `brcmf_c_preinit_dcmds` (common.c:268+) — queries `cur_etheraddr`, `ver`, `clmver`, `event_msgs`, stat vars |
| Hypothesis | All iovar queries are one-time at init; no periodic refresh; no polling loops |
| Evidence | `brcmf_fil_iovar_data_get(ifp, "cur_etheraddr", ...)` (common.c:284); `brcmf_fil_iovar_data_get(ifp, "ver", ...)` (common.c:364); `brcmf_fil_iovar_data_get(ifp, "clmver", ...)` (common.c:387); `brcmf_fil_iovar_data_get(ifp, "event_msgs", ...)` (common.c:415); no `mod_timer`/`add_timer` in preinit path |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 10. NVRAM precedence (file vs EFI)

| Field | Value |
|---|---|
| Component | firmware/NVRAM loading |
| Source file | `firmware.c` |
| Function | `brcmf_fw_request_nvram_done` (firmware.c:532+); `brcmf_fw_nvram_from_efi` (firmware.c:488-518) |
| Hypothesis | **File NVRAM takes precedence over EFI NVRAM.** If a `.txt` file exists (even a 2-line placeholder), the driver uses it and never reads the EFI `nvram` variable. On a MacBook with a valid EFI NVRAM (written by macOS/Boot Camp), a placeholder `.txt` would shadow real calibration data |
| Evidence | `if (fw && fw->data) { data = (u8 *)fw->data; data_len = fw->size; } else { data = brcmf_fw_nvram_from_efi(&data_len); ... }` (firmware.c:559-561) — file first, EFI only as fallback |
| Risk | **Medium** — placeholder NVRAM may shadow valid EFI NVRAM on real hardware |
| Upstream status | stable (intentional design) |
| Proposed action | **CONFIG-CANDIDATE** — see DRIVER_AUDIT.md F1 |

---

## 11. ccode handling

| Field | Value |
|---|---|
| Component | NVRAM ccode / regulatory |
| Source file | `firmware.c`, `cfg80211.c` |
| Function | `brcmf_fw_fix_efi_nvram_ccode` (firmware.c:473-485); `brcmf_translate_country_code` (cfg80211.c:7982); `brmcf_use_iso3166_ccode_fallback` (cfg80211.c:7967) |
| Hypothesis | The driver's own EFI NVRAM fixup only rewrites `ccode=ALL` and `ccode=XV` → `ccode=X2` (firmware.c:465-471 comment). `ccode=X0` is NOT handled. For 43602, `brmcf_use_iso3166_ccode_fallback` returns true (cfg80211.c:7976), meaning cfg80211 regulatory requests use ISO3166 alpha2 directly. The NVRAM `ccode=` value is passed to firmware as-is; `X0` is not a valid ISO 3166-1 alpha-2 code |
| Evidence | `ccode = strnstr((char *)data, "ccode=ALL", data_len); if (!ccode) ccode = strnstr((char *)data, "ccode=XV\r", data_len);` (firmware.c:477-479); `case BRCM_CC_43602_CHIP_ID: return true;` (cfg80211.c:7976) |
| Risk | **Low** — placeholder only; real NVRAM should have valid ccode |
| Upstream status | stable |
| Proposed action | **CONFIG-CANDIDATE** — see DRIVER_AUDIT.md F2 |

---

## 12. Default MAC detection

| Field | Value |
|---|---|
| Component | MAC address |
| Source file | `common.c` |
| Function | `brcmf_c_preinit_dcmds` (common.c:268+) |
| Hypothesis | If firmware reports the default MAC `00:90:4c:c5:12:38` (from a template NVRAM), the driver replaces it with a random MAC. A placeholder NVRAM may trigger this |
| Evidence | `static const u8 brcmf_default_mac_address[ETH_ALEN] = { 0x00, 0x90, 0x4c, 0xc5, 0x12, 0x38 };` (common.c:244-247); `if (ether_addr_equal_unaligned(ifp->mac_addr, brcmf_default_mac_address)) { ... eth_random_addr(ifp->mac_addr); ... }` (common.c:296-302) |
| Risk | **Low** — cosmetic (random MAC); real NVRAM has correct MAC |
| Upstream status | stable |
| Proposed action | **KEEP** — informational; no action needed |

---

## 13. Apple OTP board selection

| Field | Value |
|---|---|
| Component | Apple firmware/NVRAM selection |
| Source file | `pcie.c`, `acpi.c`, `dmi.c` |
| Function | `brcmf_pcie_prepare_fw_request` (pcie.c:2239-2299); `brcmf_acpi_probe` (acpi.c:11-51); `brcmf_dmi_probe` (dmi.c:199-228) |
| Hypothesis | On MacBook10,1, board_type is set via DMI fallback to `"Apple Inc.-MacBook10,1"` (with space). If ACPI provides `module-instance` and `RWCV`, board_type becomes `apple,<module-instance>` and antenna_sku is set, enabling OTP-based fancy board selection. Whether MacBook10,1 ACPI exposes these properties is **unknown without hardware** |
| Evidence | `snprintf(dmi_board_type, sizeof(dmi_board_type), "%s-%s", sys_vendor, product_name);` (dmi.c:224-226); `settings->board_type = devm_kasprintf(dev, GFP_KERNEL, "apple,%s", o->string.pointer);` (acpi.c:25-27); `if (devinfo->settings->board_type && devinfo->settings->antenna_sku && devinfo->otp.valid)` (pcie.c:2267) |
| Risk | **Medium** — determines which NVRAM file is loaded; wrong board_type → wrong/missing calibration |
| Upstream status | stable |
| Proposed action | **KEEP** — hardware validation item (see DRIVER_OPTIMIZATION_CANDIDATES.md) |

---

## 14. feature_disable=0x82000

| Field | Value |
|---|---|
| Component | feature flags |
| Source file | `feature.c`, `feature.h` |
| Function | `brcmf_feat_attach` (feature.c:349-353); `brcmf_feature_disable` module param (common.c:50) |
| Hypothesis | `0x82000` = bit 19 (SAE) + bit 17 (MONITOR_FMT_HW_RX_HDR) per the `BRCMF_FEAT_LIST` enum order (feature.h:36-68). Disabling SAE and monitor-format-HW-rx-hdr has no plausible connection to 5GHz/signal issues. The value appears cargo-culted |
| Evidence | Bit decode: `0x82000 = 0x80000 + 0x20000` = bit 19 + bit 17. Enum order: bit 17 = `BRCMF_FEAT_MONITOR_FMT_HW_RX_HDR`, bit 19 = `BRCMF_FEAT_SAE` (feature.h:36-68). `if (drvr->settings->feature_disable) { ... ifp->drvr->feat_flags &= ~drvr->settings->feature_disable; }` (feature.c:349-353) |
| Risk | **Low** — labeled EXPERIMENT in script; not baseline |
| Upstream status | stable |
| Proposed action | **FALSE-POSITIVE** — see DRIVER_AUDIT.md F3 |

---

## 15. Interrupt design

| Field | Value |
|---|---|
| Component | PCIe IRQ |
| Source file | `pcie.c` |
| Function | `brcmf_pcie_quick_check_isr` (pcie.c:928-939), `brcmf_pcie_isr_thread` (pcie.c:941-966), `brcmf_pcie_request_irq` (pcie.c:968-985) |
| Hypothesis | Threaded IRQ with MSI + quick-check hard ISR is optimal for low wakeup count: hard IRQ returns `IRQ_NONE` if not our device (shared IRQ), thread processes mailbox + doorbell |
| Evidence | `pci_enable_msi(pdev)` (pcie.c:978); `request_threaded_irq(pdev->irq, brcmf_pcie_quick_check_isr, brcmf_pcie_isr_thread, IRQF_SHARED, "brcmf_pcie_intr", devinfo)` (pcie.c:978-981); `if (brcmf_pcie_read_reg32(devinfo, devinfo->reginfo->mailboxint)) { brcmf_pcie_intr_disable(devinfo); return IRQ_WAKE_THREAD; } return IRQ_NONE;` (pcie.c:930-938) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 16. Console read in ISR thread

| Field | Value |
|---|---|
| Component | firmware console |
| Source file | `pcie.c` |
| Function | `brcmf_pcie_bus_console_read` (pcie.c:861-906) |
| Hypothesis | Console read is called on every ISR thread invocation but early-returns unless `BRCMF_FWCON_ON()` debug flag is set or error. No production cost |
| Evidence | `if (!error && !BRCMF_FWCON_ON()) return;` (pcie.c:871); `brcmf_pcie_fwcon_timer` early-returns `if (... || !BRCMF_FWCON_ON()) return;` (pcie.c:2322) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 17. BT coex timer

| Field | Value |
|---|---|
| Component | Bluetooth coexistence |
| Source file | `btcoex.c` |
| Function | `brcmf_btcoex_timerfunc` (btcoex.c:273), `brcmf_btcoex_handler` (btcoex.c:283) |
| Hypothesis | BT coex timer only runs during DHCP opportunity windows when BT coex is active. With BT rfkill-blocked (our config), BT coex is inactive → timer never armed |
| Evidence | `timer_setup(&btci->timer, brcmf_btcoex_timerfunc, 0)` (btcoex.c:374); `mod_timer(&btci->timer, jiffies + btci->timeout)` (btcoex.c:325) only in DHCP state machine; `BRCMF_BTCOEX_OPPR_WIN_TIME = msecs_to_jiffies(2000)` (btcoex.c:21) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 18. PNO (offloaded scan)

| Field | Value |
|---|---|
| Component | preferred network offload |
| Source file | `pno.c` |
| Function | `brcmf_pno_config` (pno.c:102), `brcmf_pno_store_request` (pno.c:40) |
| Hypothesis | PNO is firmware-offloaded scheduled scan; only active if `BRCMF_FEAT_PNO`/`BRCMF_FEAT_GSCAN` features enabled and NM requests scheduled scan. No host polling |
| Evidence | `brcmf_fil_iovar_data_set(ifp, "pfn_cfg", cfg, sizeof(*cfg))` (pno.c:99); `brcmf_feat_iovar_int_get(ifp, BRCMF_FEAT_PNO, "pfn")` (feature.c:306) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 19. debugfs surface

| Field | Value |
|---|---|
| Component | debugfs |
| Source file | `core.c`, `msgbuf.c`, `feature.c` |
| Function | `brcmf_debugfs_add_entry(drvr, "revinfo", ...)` (core.c:1307); `brcmf_msgbuf_debugfs_create` (msgbuf.c:1557); `brcmf_feat_debugfs_create` (feature.c:370) |
| Hypothesis | debugfs entries are passive (read on demand); debugfs not mounted by default → zero runtime cost |
| Evidence | `debugfs_create_file("reset", 0600, brcmf_debugfs_get_devdir(drvr), drvr, &bus_reset_fops)` (core.c:1308-1309); `brcmf_debugfs_add_entry(drvr, "msgbuf_stats", brcmf_msgbuf_stats_read)` (msgbuf.c:1558) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## 20. WoWLAN

| Field | Value |
|---|---|
| Component | Wake-on-WLAN |
| Source file | `cfg80211.c` |
| Function | `brcmf_wiphy_wowl_params` (cfg80211.c:7628-7655); `brcmf_wowlan_support` (cfg80211.c:7619-7625) |
| Hypothesis | WoWLAN is firmware-offloaded; only active if configured by NM/user. Default: not configured → no cost |
| Evidence | `.flags = WIPHY_WOWLAN_MAGIC_PKT | WIPHY_WOWLAN_DISCONNECT` (cfg80211.c:7620-7621); `if (brcmf_feat_is_enabled(ifp, BRCMF_FEAT_PNO)) { if (brcmf_feat_is_enabled(ifp, BRCMF_FEAT_WOWL_ND)) { wowl->flags |= WIPHY_WOWLAN_NET_DETECT; ... } }` (cfg80211.c:7641-7648) |
| Risk | none |
| Upstream status | stable |
| Proposed action | **KEEP** — no change |

---

## Finding summary

| Outcome class | Count | Findings |
|---|---|---|
| KEEP | 16 | 1,2,3,4,5,6,7,8,9,12,15,16,17,18,19,20 |
| CONFIG-CANDIDATE | 2 | 10 (NVRAM precedence), 11 (ccode) |
| UPSTREAM-CANDIDATE | 0 | — |
| LOCAL-CANDIDATE | 0 | — |
| FALSE-POSITIVE | 1 | 14 (feature_disable=0x82000) |
| **Total** | **18** | |

---

## D2 — Userspace path findings (NetworkManager / wpa_supplicant / iwd)

> Audit date: 2026-09-28. Source: NetworkManager 1.58.1, wpa_supplicant 2.12, iwd 3.12 sources + Arch package file lists.
> Focus: periodic activity, scan triggers, backend trade-off, config levers. No daemon rewrites.

### U1 — NM periodic scan schedule (by design, not a defect)

| Field | Value |
|---|---|
| Component | NM Wi-Fi scan scheduler |
| Source | `src/core/devices/wifi/nm-device-wifi.c` (`_scan_notify_allowed`, `_scan_kickoff`) |
| Finding | Periodic scans are **DISCONNECTED/FAILED-only**. When ACTIVATED, `periodic_allowed=FALSE` — NM relies on supplicant background scans. Disconnected interval: `SCAN_INTERVAL_SEC_MIN 3` → `SCAN_INTERVAL_SEC_MAX 120` (×1.5 backoff, step via `SCAN_INTERVAL_SEC_STEP 20`). Rate limit 1.5s disconnected / 8s activated for explicit scans. |
| Evidence | `SCAN_INTERVAL_SEC_MIN/STEP/MAX` (nm-device-wifi.c:30-32); `_scan_notify_allowed` state machine (nm-device-wifi.c:462-491); `_scan_kickoff` rate limit (nm-device-wifi.c:1793-1797) |
| Risk | none — by design |
| Proposed action | **KEEP** — no change. Documented in DRIVER_OPTIMIZATION_CANDIDATES.md HW plan. |

### U2 — mv-control 30s fallback poll triggers a scan every ~30s (FIXED)

| Field | Value |
|---|---|
| Component | mv-control Wi-Fi list refresh |
| Source | `packages/mavericks-apps/src/mavericks-apps/bin/mv-control` (`refresh_wifi_list`, `_wifi_fallback_tick`) |
| Finding | The 30s fallback poll calls `nmcli dev wifi list`, which per nmcli(1) "ensures that the access point list is no older than 30 seconds and triggers a network scan if necessary." With a 30s poll interval, the cache is always borderline → **a firmware scan every ~30s while Control Center is open**. Each scan = `NL80211_CMD_TRIGGER_SCAN` → `escan` iovar → MPC disabled. |
| Evidence | nmcli(1) man page; mv-control `WIFI_FALLBACK_POLL_S = 30` (mv-control:21); `refresh_wifi_list` nmcli call (mv-control:187) |
| Risk | **Medium** — unnecessary scan wakeups + MPC-off while Control Center open |
| Proposed action | **FIXED** — `refresh_wifi_list` now passes `--rescan no` by default (cached AP list, no scan). NM D-Bus signals (already subscribed) refresh on AP changes. Explicit Refresh button passes `--rescan yes`. Test added (test-mv-control.py). |

### U3 — Connectivity check: Arch ships a 300s HTTP poll (CONFIG-CANDIDATE → APPLIED)

| Field | Value |
|---|---|
| Component | NM connectivity check |
| Source | `nm-config.h` (`NM_CONFIG_DEFAULT_CONNECTIVITY_INTERVAL 300`), Arch `/usr/lib/NetworkManager/conf.d/20-connectivity.conf` |
| Finding | Arch ships `uri=http://ping.archlinux.org/nm-check.txt`. NM defaults: `enabled=true`, `interval=300s`, `timeout=20s`. So stock Arch NM polls an HTTP endpoint every 5 min whenever a connection exists — a periodic network wakeup. |
| Evidence | `nm-config.h:38` (`NM_CONFIG_DEFAULT_CONNECTIVITY_INTERVAL 300`); Arch package file list + extracted `20-connectivity.conf`; `man/NetworkManager.conf.xml` (`enabled` default true, `interval` default 300) |
| Risk | **Low-Medium** — 5-min HTTP poll; battery/wakeup cost; no captive-portal need in our discipline |
| Proposed action | **APPLIED** — `configs/network/99-mavericks.conf` `[connectivity] enabled=false` shadows the Arch default. |

### U4 — Powersave: identical for both backends in NM 1.58.1 (informational)

| Field | Value |
|---|---|
| Component | 802.11 powersave |
| Source | `nm-device-wifi.c:3412`, `nm-device-iwd.c:2274`, `nm-wifi-utils-nl80211.c:260` |
| Finding | NM 1.58.1 sets 802.11 PS via `NL80211_CMD_SET_POWER_SAVE` **directly via nl80211** for BOTH backends (not through wpa_supplicant). Default `802-11-wireless.powersave=0` → falls back to `[connection] wifi.powersave` (default `ignore`=1) → NM does not touch PS; firmware default applies. |
| Evidence | `set_powersave()` in both device backends; `wifi_nl80211_set_powersave` (nm-wifi-utils-nl80211.c:260-272); `NM_CON_DEFAULT_NOP("wifi.powersave")` (nm-device.c:20720) |
| Risk | none — by design |
| Proposed action | **KEEP** — no change. Lever documented (`[connection] wifi.powersave=3` to enable); PM_FAST stability is a HW-validation item (D1 hypothesis O6). |

### U5 — Backend trade-off: wpa_supplicant vs iwd for BCM43602 FullMAC (informational)

| Field | Value |
|---|---|
| Component | NM Wi-Fi backend selection |
| Source | `nm-wifi-factory.c:126`, `nm-device-iwd.c`, wpa_supplicant 2.12 + iwd 3.12 sources |
| Finding | **wpa_supplicant** (active): full feature support (P2P/AP/hidden/ad-hoc), NM-controlled roaming with supplicant settle wait, mature NM integration. **iwd** (alternative): no P2P, 802.1X needs iwd provisioning files, hidden SSIDs infra-only, iwd-controlled roaming/autoconnect (network ranking), native `PowerSaveDisable` config. Powersave identical (U4). SAE/WPA3 supported by both (wpa_supplicant `CONFIG_SAE=y`; iwd WPA3 since 1.0). |
| Evidence | `nm-wifi-factory.c:126` (backend selection); `nm-device-iwd.c` capability checks; wpa_supplicant 2.12 `defconfig` (`CONFIG_SAE=y`); iwd/Arch package versions; NM commit 5838c38 (iwd powersave added) |
| Risk | none — wpa_supplicant is the safer default |
| Proposed action | **KEEP** — wpa_supplicant pinned explicitly in `99-mavericks.conf`. |

### D2 userspace finding summary

| Outcome class | Count | Findings |
|---|---|---|
| KEEP | 3 | U1 (NM scan schedule), U4 (powersave identical), U5 (backend trade-off) |
| CONFIG-CANDIDATE (APPLIED) | 1 | U3 (connectivity check disabled) |
| LOCAL-FIX (APPLIED) | 1 | U2 (mv-control --rescan no) |
| UPSTREAM-CANDIDATE | 0 | — |
| **Total** | **5** | |

---

## D3 — i915 display path source audit (Gen9.5, 2026-09-28)

> Source: Linux master (torvalds) i915 display code via codebrowser.dev.
> Every claim cites file:line. Re-verify commands in RUNTIME_COMPONENT_MAP.md §5.9.

### S1 — PSR entry path: idle_frames + sync latency (KEEP)

**Finding:** `psr_compute_idle_frames()` (intel_psr.c:917-933) computes the minimum
idle frames before PSR entry as `max(6, vbt.idle_frames, sink_sync_latency + 1)`.
The `sink_sync_latency` is read from DPCD `DP_SYNCHRONIZATION_LATENCY_IN_SINK`
(intel_psr.c:483-495). If DPCD read fails, assumes 8 frames (worst case).
This is correct and panel-appropriate — no change needed.

### S2 — PSR2 Y-coordinate support gate (KEEP)

**Finding:** PSR2 selective update on Gen9 requires `sink_psr2_support` which is
gated on: DPCD PSR version ≥ 03h AND `DP_PSR2_SU_Y_COORDINATE_REQUIRED` AND
`intel_alpm_aux_wake_supported()` (intel_psr.c:704-724). If any condition fails,
PSR2 is disabled and PSR1 is used instead. This is correct — no change needed.

### S3 — PSR exit on vblank/vsync interrupt (KEEP)

**Finding:** PSR entry is blocked while `vblank->enabled` (intel_psr.c:945,
`is_dc5_dc6_blocked()`). The vblank interrupt is unmasked during PSR to allow
exit on frontbuffer modification. This means PSR and vblank are mutually
exclusive — PSR entry requires vblank to be disabled first. This is by design.

### S4 — FBC nuke on flip (KEEP)

**Finding:** `intel_fbc_nuke()` (intel_fbc.c:750-760) writes `DSPADDR` to trigger
a re-compress of the framebuffer. Called from `intel_fbc_activate()` on every
plane flip. The nuke is a single MMIO write — negligible cost. Correct behavior.

### S5 — FBC + PSR1 coexistence on Gen9 (KEEP)

**Finding:** On Gen9 (DISPLAY_VER=9), FBC and PSR1 can coexist. The mutual
exclusion (`Wa_14016291713`) only applies to Gen12+ (intel_fbc.c:1561-1566).
On Gen9, FBC compresses the framebuffer while PSR caches it in the panel RFB.
No conflict — both can be active simultaneously.

### S6 — Backlight PWM frequency from VBT (KEEP)

**Finding:** `get_vbt_pwm_freq()` (intel_backlight.c:1162-1179) reads the PWM
frequency from VBT (Video BIOS Table). If VBT doesn't specify, defaults to 200Hz.
The `pwm_level_max` is computed from this frequency and the display raw clock.
This is panel-specific and correct — no change needed.

### S7 — DC5/6 entry blocked by active vblank (KEEP)

**Finding:** `is_dc5_dc6_blocked()` (intel_psr.c:935-946) returns true if
`current_dc_state < DC5` OR `active_non_psr_pipes` OR `vblank->enabled`.
This means DC5/6 entry requires all pipes to be in PSR (or disabled) and
vblank to be disabled. This is the hardware coordination mechanism — correct.

### S8 — DMC firmware required for DC5/6 (KEEP)

**Finding:** `skl_display_core_init()` (intel_display_power.c:1456-1487) calls
`intel_dmc_load_program()` on resume. Without DMC firmware, DC5/6 entry is
blocked (the `gen9_dc_off_power_well_disable` path checks `intel_dmc_has_payload`).
The KBL DMC firmware (`i915/kbl_dmc.bin`) must be present in `/usr/lib/firmware`.
This is a packaging dependency — verified in packages.x86_64 (linux-firmware).

### S9 — Forcewake for register access in low-power (KEEP)

**Finding:** `hsw_restore_lcpll()` (intel_display_power.c:1331-1381) calls
`intel_uncore_forcewake_get(FORCEWAKE_ALL)` before accessing LCPLL registers,
and `intel_uncore_forcewake_put()` after. This is required because the GT
domain may be powered down during PC8+. Correct — no change needed.

### S10 — PSR + DC5/6 mutual exclusion (KEEP)

**Finding:** PSR entry requires DC5/6 to be blocked (intel_psr.c:935-946), and
DC5/6 entry requires PSR to be inactive (all pipes must be in PSR or disabled).
This means PSR and DC5/6 are mutually exclusive power-saving states. The driver
coordinates this via the `DC_OFF` power well and `target_dc_state`. This is
correct hardware coordination — no change needed.

### D3 source audit summary

| Outcome class | Count | Findings |
|---|---|---|
| KEEP | 10 | S1-S10 — all display power management paths are correct by design |
| CONFIG-CANDIDATE | 0 | — |
| LOCAL-FIX | 0 | — |
| UPSTREAM-CANDIDATE | 0 | — |
| **Total** | **10** | |

---

# AUDIO SOURCE AUDIT — HDA / Cirrus CS4208 / PipeWire (D4, 2026-09-28)

> Deep Runtime Track D4. Source basis: linux-7.2.6 (kernel.org tarball),
> leifliddy/macbook12-audio-driver r108.g4cdfcdb (vendored), PipeWire 1.6.9 /
> WirePlumber 0.5.17 (Arch repos), TLP 1.9.1 docs. Build behavior empirically
> verified in the build container (RUNTIME_COMPONENT_MAP.md §8.4).

## A1. HDA controller power path (snd-hda-intel / azx)

| Question | Answer | Evidence |
|---|---|---|
| How does the controller power down at idle? | `power_save=N` module param → azx runtime suspend after N seconds of stream inactivity; `power_save_controller=Y` → PCI runtime PM for the controller itself | sound/hda/hda_intel.c (azx runtime PM); TLP writes the same sysfs params |
| Who owns power_save in our stack? | TLP (frozen baseline). TLP 1.9.1 defaults: SOUND_POWER_SAVE_ON_AC=1, SOUND_POWER_SAVE_ON_BAT=1, SOUND_POWER_SAVE_CONTROLLER=Y | TLP 1.9.1 docs (linrunner.de) + defaults.conf |
| Wakeup sources at idle? | stream start (DMA ring), jack GPIO interrupt, power_save timeout re-entry | azx interrupt + runtime PM |
| Any polling in azx? | No — interrupt + runtime PM only | hda_intel.c |

## A2. Codec PM / jack detection (CS4208 via DKMS snd-hda-codec-cs420x)

| Question | Answer | Evidence |
|---|---|---|
| Does the codec have its own runtime PM? | No — the codec powers with the HDA controller; controller D3hot covers the codec | HDA spec behavior; driver has no codec PM |
| Jack detection wakeup? | GPIO interrupt from the codec (headphone sense) → wakes controller from D3hot → driver re-points the stream (cs_4208_playback_pcm_hook) | patch_cirrus_a1534_pcm.h; cs420x.c patch_cs4208() |
| DSP on this path? | No — CS4208 init is a verb sequence (setup_a1534/play_a1534), streams are HDA-link DMA, codec DSP core unused | patch_cirrus_a1534_setup.h; driver README |
| Clock gating? | HDA link clock stops with controller power_save; no independent codec clock gating | HDA spec behavior |

## A3. ALSA UCM presence for CS4208

| Question | Answer | Evidence |
|---|---|---|
| UCM for CS4208 upstream? | **No** — alsa-ucm-conf has no cs4208/Cirrus entry (verified via GitHub API ucm2/ tree listing; only generic HDA HiFi profiles) | api.github.com/repos/alsa-project/alsa-ucm-conf/contents/ucm2 |
| Do we ship UCM? | No — and none is needed: the codec driver does its own mixer setup; the card uses the generic HiFi UCM profile / fallback | driver README; RUNTIME_COMPONENT_MAP.md §8.3 |
| Verdict | No UCM gap — consistent with the audio-driver package (which also ships no UCM) | — |

## A4. PipeWire graph idle behavior

| Question | Answer | Evidence |
|---|---|---|
| Which nodes run with zero streams? | None — nodes are created per stream/card and destroyed on stream end; pipewire daemon + wireplumber remain, idle on epoll | PipeWire 1.6.9 architecture |
| WirePlumber polling? | No — Lua scripts run on graph changes only (no timers in the default scripts we use) | wireplumber 0.5.17; RUNTIME_AUDIT.md persistent-daemons table |
| pactl-per-poll sites? | **None** — all pactl usage is event-driven (keypress/user action/window open); mv-control 30s refresh_all never touches sound | verified in current tree (RUNTIME_AUDIT.md AUDIO §pactl sites) |
| Soft-volume rule | api.alsa.soft-mixer=true on alsa_card.pci-0000_00_1f.3 — installed by macbook12-audio-driver since D4 (888e0ff) | contrib/wireplumber/wireplumber.conf.d/51-macbook-cs4208-softvol.conf |

## A5. D4 source audit summary

| Outcome class | Count | Findings |
|---|---|---|
| KEEP | 4 | A1 (azx power path by design), A2 (codec PM by design), A3 (no UCM needed), A4 (graph idle by design) |
| CONFIG-CANDIDATE | 0 | — |
| LOCAL-FIX | 3 | softvol conf install (888e0ff), udev rule removal (888e0ff), modprobe conf cleanup (888e0ff) |
| UPSTREAM-CANDIDATE | 0 | — |
| **Total** | **7** | |

---

## D5 — INPUT + STORAGE source audit (2026-09-28)

> Source: applespi driver (roadrunner2/macbook12-spi-driver, GPL-2.0), Linux 7.3.0-rc5
> (torvalds) nvme core + btrfs, systemd zram-generator + fstrim.
> Every claim cites file:line. Re-verify commands in RUNTIME_COMPONENT_MAP.md §9.9, §10.9.

### I1. applespi GPE interrupt model (KEEP)

| Question | Answer | Evidence |
|---|---|---|
| How does applespi receive input events? | ACPI GPE (General Purpose Event), level-triggered. NOT a traditional SPI IRQ. | `acpi_install_gpe_handler(NULL, gpe, ACPI_GPE_LEVEL_TRIGGERED, applespi_notify, applespi)` (applespi.c:1860-1865) |
| Is the GPE edge or level triggered? | Level-triggered (ACPI_GPE_LEVEL_TRIGGERED) | applespi.c:1862 |
| Does the GPE wake from suspend? | NO — `applespi_suspend()` calls `acpi_disable_gpe()` | applespi.c:1765 |
| Is there a polling fallback? | NO — pure interrupt-driven, no timers, no workqueues | applespi.c (no mod_timer/add_timer) |

### I2. applespi timeout-retry behavior (KEEP — no retry exists)

| Question | Answer | Evidence |
|---|---|---|
| What happens on SPI read timeout? | `applespi_async_read_complete()` logs `pr_warn("Error reading from device: %d\n", status)` and calls `acpi_finish_gpe()`. NO retry. | applespi.c:1735-1740 |
| What happens on SPI write timeout? | `applespi_async_write_complete()` logs `pr_warn("Error writing to device: %d\n", sts)`. NO retry. | applespi.c:1560-1575 |
| What happens on CRC mismatch? | `applespi_verify_crc()` returns false → `dev_warn_ratelimited("Received corrupted packet (crc mismatch)")` → packet dropped. NO retry. | applespi.c:1620-1630 |
| Is there any retry loop? | NO — the driver has no retry mechanism for failed transfers | applespi.c (no retry loop) |
| Root cause of 6.15+ failure? | SPI controller (spi_pxa2xx_platform) rev3+ hardware bug — transfers timeout. Driver sees ETIMEDOUT (-110) and logs it. | dmesg: `applespi: Error reading from device: -110` |

### I3. applespi power management (KEEP — no runtime PM)

| Question | Answer | Evidence |
|---|---|---|
| Does applespi have runtime PM? | NO — `applespi_pm_ops` only has `.suspend` and `.resume`, no `.runtime_suspend`/`.runtime_resume` | applespi.c:1828-1829 |
| What does suspend do? | Drains outstanding writes/reads, disables GPE | applespi.c:1754-1785 |
| What does resume do? | Re-enables GPE, re-initializes touchpad (sends init command) | applespi.c:1789-1816 |
| Is there autosuspend? | N/A — SPI slave device, no runtime PM | — |
| Keyboard backlight power? | LED classdev `spi::kbd_backlight` — sends SPI command on brightness change | applespi.c:1840-1850 |

### I4. applespi touchpad input capabilities (KEEP)

| Question | Answer | Evidence |
|---|---|---|
| What input properties? | INPUT_PROP_POINTER \| INPUT_PROP_BUTTONPAD | applespi.c:1830-1831 |
| Multitouch? | Yes — `input_mt_init_slots()` with MAX_FINGERS (11) | applespi.c:1835-1837 |
| Pressure (Force Touch)? | **NOT reported** — no ABS_MT_PRESSURE in the driver | applespi.c (no ABS_MT_PRESSURE) |
| What is reported? | ABS_MT_TOUCH_MAJOR/MINOR, ABS_MT_WIDTH_MAJOR/MINOR, ABS_MT_ORIENTATION, ABS_MT_POSITION_X/Y | applespi.c:1590-1610 |
| Button? | BTN_LEFT (click detected by controller) | applespi.c:1615 |

### I5. External USB-C HID path (KEEP — reference-good)

| Question | Answer | Evidence |
|---|---|---|
| Interrupt? | USB interrupt endpoint (HID) | USB HID spec |
| Driver? | hid-generic / hid-apple (in-tree) | Linux input subsystem |
| Runtime PM? | USB autosuspend (TLP `USB_AUTOSUSPEND=1`) | TLP 1.9.1 |
| Wake from suspend? | YES — USB remote wakeup | USB HID spec |
| libinput? | Standard evdev device, full multitouch + acceleration | libinput 1.27+ |

### I6. libinput configuration (KEEP — none needed)

| Question | Answer | Evidence |
|---|---|---|
| Do we ship libinput quirks? | NO | — |
| Do we ship hwdb entries? | NO | — |
| Is configuration needed? | NO — applespi touchpad is standard multitouch, libinput handles it with defaults | — |
| Accel profile? | libinput default `adaptive` | libinput 1.27+ |
| Tap-to-click? | libinput default enabled for trackpad | libinput 1.27+ |

### S1. S3X NVMe APST (KEEP — not exposed)

| Question | Answer | Evidence |
|---|---|---|
| Does S3X expose APST? | **NO** — Apple S3X does not support APST | Linux nvme core: S3X ignores APST |
| What does `nvme_core.default_ps_max_latency_us` do? | Controls APST for standard NVMe controllers; S3X ignores it | Linux nvme core |
| What power states does S3X support? | D0 (active) only — no autonomous transition | Linux nvme core |
| Implication? | NVMe controller stays powered at all times; only PCIe ASPM and system suspend save power | — |

### S2. ASPM interplay with pcie_port_pm=off (BASELINE ITEM)

| Question | Answer | Evidence |
|---|---|---|
| What does `pcie_port_pm=off` do? | Disables ALL PCIe root port runtime PM | Linux PCIe core |
| What is the power cost? | NVMe stays in D0 — higher idle power (unmeasured) | — |
| What counters prove it? | `/sys/bus/pci/devices/0000:00:1c.0/power/runtime_status` → `active` vs `suspended` | — |
| Is there a narrower fix? | LKML thread (Sep 2026) asks if PCI quirk for 00:1c.0 is possible | LKML: lists.openwall.net/linux-kernel/2026/09/21/161 |
| Our baseline? | `pcie_port_pm=off` — provisional workaround | kernel cmdline |

### S3. btrfs mount options (KEEP — minimal)

| Question | Answer | Evidence |
|---|---|---|
| What mount options do we use? | `rootflags=subvol=@` only | kernel cmdline |
| noatime? | NOT set — kernel default `relatime` | — |
| discard? | NOT set — correct (use fstrim instead) | — |
| commit interval? | NOT set — kernel default 30s | — |
| ssd? | NOT set — kernel default | — |
| Is this a problem? | NO — relatime is frugal, no discard is correct, 30s commit is fine | — |

### S4. fstrim timer state (CONFIG-CANDIDATE — should enable)

| Question | Answer | Evidence |
|---|---|---|
| Is fstrim.timer enabled in our ISO? | **NO** — not explicitly enabled in firstboot | mavericks-firstboot.sh (no fstrim) |
| Is fstrim.timer enabled on installed? | **NO** — firstboot does not enable it | mavericks-firstboot.sh |
| What is the effect? | No periodic TRIM — SSD performance may degrade over time | — |
| What is the cost? | Negligible — weekly oneshot, ~seconds | systemd fstrim.timer |
| Recommendation? | **Enable fstrim.timer** — one-line addition to firstboot | — |

### S5. zram config (KEEP — correct)

| Question | Answer | Evidence |
|---|---|---|
| zram-size? | ram / 2 | zram-generator.conf.d/99-mavericks.conf |
| compression-algorithm? | zstd | zram-generator.conf.d/99-mavericks.conf |
| disk swap? | NONE | — |
| Correct? | YES — per baseline | — |

### S6. journald config (KEEP — correct)

| Question | Answer | Evidence |
|---|---|---|
| Storage? | volatile (ISO), persistent (installed) | journald.conf.d/99-mavericks.conf + firstboot |
| RuntimeMaxUse? | 50M | journald.conf.d/99-mavericks.conf |
| SystemMaxUse? | 100M | journald.conf.d/99-mavericks.conf |
| ForwardToSyslog? | no | journald.conf.d/99-mavericks.conf |
| Correct? | YES — volatile in ISO, persistent with limits on install | — |

### D5 source audit summary

| Outcome class | Count | Findings |
|---|---|---|
| KEEP | 10 | I1 (GPE model), I2 (no retry), I3 (no runtime PM), I4 (touchpad caps), I5 (USB HID), I6 (libinput), S1 (APST), S3 (btrfs), S5 (zram), S6 (journald) |
| CONFIG-CANDIDATE | 1 | S4 (fstrim.timer not enabled) |
| BASELINE-JUSTIFIED | 1 | S2 (pcie_port_pm=off) |
| LOCAL-FIX | 0 | — |
| UPSTREAM-CANDIDATE | 0 | — |
| **Total** | **12** | |
