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
