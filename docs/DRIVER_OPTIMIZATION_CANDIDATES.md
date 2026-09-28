# DRIVER OPTIMIZATION CANDIDATES — NETWORK (brcmfmac / BCM43602)

> Deep Runtime Track D1. Audit date: 2026-09-28. Source: Linux 7.3.0-rc5 (torvalds) brcmfmac.
> All findings status: **PROPOSED-HW-MEASUREMENT** — none implemented. No driver modifications.
> Frozen power baseline (TLP-only, `pcie_port_pm=off`, `i915.enable_psr=0`) is NOT touched; D6 judges it separately.

---

## 1. Idle-state analysis (A–G)

For each state: which code paths are ACTIVE (from source), expected wakeup/interrupt profile, and what to measure on hardware.

### A. Idle-connected (associated, no traffic)

**Active paths:**
- MSI interrupt: only for firmware events (keepalive, null-function, rare) and RX of broadcast/multicast (if not filtered by firmware).
- fweh workqueue: only when events arrive.
- `msgbuf_txflow` workqueue: idle (no TX).
- No timers armed (escan_timeout, btcoex, p2p listen all inactive).
- PCIe ASPM: L1/L0s via TLP (`PCIE_ASPM_ON_AC/BAT=powersave`).
- Firmware PM: `PM_FAST` powersave (if enabled by NM) or `PM_OFF`.

**Expected wakeup profile:** Very low. Occasional firmware event interrupt (e.g., null-function keepalive every ~1 s if PM_FAST, or none if PM_MAX). PCIe ASPM L1 entry/exit per wake.

**Measure on hardware:**
- `/proc/interrupts` — `brcmf_pcie_intr` line: count over 60 s idle.
- `iw dev wlan0 get power_save` — confirm PM mode.
- `powertop` — wakeup lines for `brcmfmac` / `msgbuf_txflow` / `fweh`.
- `dmesg` — no per-packet logs (confirm quiet).
- `ethtool -S wlan0` — RX/TX packet counters (should be near-zero).

---

### B. Light traffic (occasional packets, e.g., DNS, NTP)

**Active paths:**
- MSI interrupt: per RX/TX batch (doorbell coalesces).
- fweh: only for connection events (none during steady light traffic).
- `msgbuf_txflow` wq: active during TX bursts, idle between.
- TX flowring: `brcmf_msgbuf_tx_queue_data` → `brcmf_msgbuf_schedule_txdata` → `msgbuf_txflow` wq.
- RX: `brcmf_proto_msgbuf_rx_trigger` → `brcmf_msgbuf_process_rx` → `brcmf_msgbuf_process_rx_complete`.

**Expected wakeup profile:** Low-moderate. Interrupt per batch; txflow wq active during TX. No timers.

**Measure on hardware:**
- `/proc/interrupts` — interrupt rate during light ping.
- `ethtool -S wlan0` — RX/TX counters, errors, dropped.
- `powertop` — wakeup rate.
- `iw dev wlan0 station dump` — signal, TX/RX bytes, retry count.

---

### C. Download (sustained RX)

**Active paths:**
- MSI interrupt: high rate (doorbell per RX batch).
- RX buffer posting: `brcmf_msgbuf_rxbuf_data_post` (msgbuf.c:932) — replenishes RX buffers.
- `brcmf_msgbuf_rxreorder` (msgbuf.c:544) — RX reordering if enabled.
- fweh: only for events (none during pure data RX).
- `msgbuf_txflow` wq: active for TCP ACKs (TX).
- Flowring: TX flowring for ACKs.

**Expected wakeup profile:** High interrupt rate (RX-bound). txflow wq active for ACKs. No timers. PCIe ASPM may reduce L1 residency under load.

**Measure on hardware:**
- `/proc/interrupts` — interrupt rate during `iperf3` / `curl` download.
- `ethtool -S wlan0` — RX packets, bytes, errors, dropped, FIFO errors.
- `iw dev wlan0 survey dump` — channel busy time, noise.
- `powertop` — wakeup rate, CPU package power.
- `dmesg` — any `brcmf_err` / `brcmf_dbg` (should be silent).

---

### D. Upload (sustained TX)

**Active paths:**
- `msgbuf_txflow` wq: high activity (TX-bound).
- TX flowring: `brcmf_msgbuf_tx_queue_data` → flowring → `brcmf_msgbuf_schedule_txdata`.
- `brcmf_flowring_block` (flowring.c:178) — queue blocking if flowring full.
- MSI interrupt: per TX completion batch.
- fweh: only for events.

**Expected wakeup profile:** High txflow wq activity; interrupt per TX completion batch. No timers.

**Measure on hardware:**
- `/proc/interrupts` — interrupt rate during `iperf3` upload.
- `ethtool -S wlan0` — TX packets, bytes, errors, dropped.
- `powertop` — wakeup rate.
- `iw dev wlan0 survey dump` — channel busy.

---

### E. Scan (active or passive)

**Active paths:**
- `brcmf_cfg80211_scan` (cfg80211.c:1531) → `brcmf_do_escan` → `brcmf_run_escan` → `escan` iovar.
- MPC disabled: `brcmf_scan_config_mpc(ifp, 0)` (cfg80211.c:1518).
- Scan timeout timer: `cfg->escan_timeout` armed (10 s, cfg80211.c:1587).
- ESCAN_RESULT events → fweh → `brcmf_notify_escan_complete` (cfg80211.c:1184).
- `brcmf_cfg80211_escan_timeout_worker` (cfg80211.c:3576) — if scan times out.

**Expected wakeup profile:** Burst of interrupts during scan (per channel, per result). Timer armed for 10 s. After scan: idle.

**Measure on hardware:**
- `/proc/interrupts` — interrupt rate during `iw dev wlan0 scan`.
- `iw dev wlan0 scan dump` — results.
- `dmesg` — `brcmf_dbg(SCAN, ...)` if debug enabled (default: silent).
- `powertop` — wakeup rate during scan.
- Time scan duration (should be < 10 s; if 10 s, timeout fired → check `brcmf_notify_escan_complete` abort path).

---

### F. Reconnect (disconnect + connect)

**Active paths:**
- `brcmf_cfg80211_disconnect` (cfg80211.c:2627) → `BRCMF_C_DISASSOC` iovar.
- `brcmf_cfg80211_connect` (cfg80211.c:2381) → auth/assoc iovars → firmware.
- BRCMF_E_CONNECT / BRCMF_E_DISCONNECT events → fweh → `brcmf_notify_connect_done` / `brcmf_notify_disconnect_done`.
- `brcmf_cfg80211_wait_vif_event` (cfg80211.c:7957) — wait queue for IF_ADD/IF_DEL.
- Possible re-probe on failure: `brcmf_pcie_remove` + `brcmf_pcie_probe` (pcie.c:2698-2704).

**Expected wakeup profile:** Burst of interrupts during connect sequence. No timers (unless scan is triggered first). After connect: idle.

**Measure on hardware:**
- `/proc/interrupts` — interrupt rate during `nmcli dev disconnect` + `nmcli dev connect`.
- `dmesg` — connect sequence, any errors.
- `iw dev wlan0 station dump` — confirm associated.
- `nmcli dev wifi list` — confirm scan works after reconnect.
- Time to reconnect (should be < 5 s).

---

### G. Suspend-resume

**Active paths:**
- Suspend: `brcmf_pcie_pm_enter_D3` (pcie.c:2636) → `BRCMF_H2D_HOST_D3_INFORM` mailbox → wait for response (2 s timeout).
- Resume: `brcmf_pcie_pm_leave_D3` (pcie.c:2666) → hot resume (`BRCMF_H2D_HOST_D0_INFORM`) or full re-probe.
- WoWLAN (if configured): `brcmf_wowlan_support` (cfg80211.c:7619) — MAGIC_PKT | DISCONNECT (+ NET_DETECT, GTK_REKEY if features).
- `device_wakeup_enable` (pcie.c:725) — wakeup enabled.
- `bus->wowl_supported = pci_pme_capable(pdev, PCI_D3hot)` (pcie.c:2522).

**Expected wakeup profile:** Suspend: mailbox handshake, then D3 (no interrupts). Resume: D0 inform or re-probe. If WoWLAN configured: firmware wakes host on magic packet / disconnect.

**Measure on hardware:**
- `dmesg` — suspend/resume messages, any timeout (`Timeout on response for entering D3 substate`).
- `journalctl -b` — resume time.
- `iw dev wlan0 get power_save` — confirm powersave state after resume.
- `nmcli dev status` — confirm reconnected after resume.
- If WoWLAN configured: test magic packet wake.
- `/proc/interrupts` — confirm no interrupts during suspend (D3).

---

## 2. HW measurement plan

### 2.1 Counters to collect

| Counter | Source | What it tells |
|---|---|---|
| `brcmf_pcie_intr` interrupt count | `/proc/interrupts` | total firmware wakeups |
| `ethtool -S wlan0` | ethtool | RX/TX packets, bytes, errors, dropped, FIFO |
| `iw dev wlan0 survey dump` | iw | channel busy, noise, RX/TX time |
| `iw dev wlan0 station dump` | iw | signal, TX/RX bytes, retry count, bitrate |
| `iw dev wlan0 get power_save` | iw | PM mode (PM_FAST/PM_OFF) |
| `powertop` wakeup lines | powertop | kernel wakeup sources |
| `dmesg` patterns | dmesg | errors, EFI NVRAM, board type, connect events |
| `nmcli dev wifi list` time | nmcli | scan duration |
| `iperf3` throughput | iperf3 | sustained RX/TX rate |

### 2.2 Dmesg patterns to watch

| Pattern | Meaning | Source |
|---|---|---|
| `Using nvram EFI variable` | EFI NVRAM path taken (no file NVRAM) | firmware.c:513 |
| `Apple board: <type>` | OTP-based board selection active | pcie.c:2273 |
| `ACPI module-instance=<val>` | ACPI board_type override | acpi.c:24 |
| `ACPI antenna-sku=<val>` | ACPI antenna_sku set | acpi.c:41 |
| `Board: <type>` | DMI fallback board_type | pcie.c:2296 |
| `Default MAC is used, replacing with random MAC` | template NVRAM detected | common.c:297 |
| `Timeout on response for entering D3 substate` | suspend mailbox timeout | pcie.c:2653 |
| `probe after resume failed` | resume re-probe failed | pcie.c:2701 |
| `brcmf_err` / `brcmf_dbg` | driver errors / debug (default: silent) | various |

### 2.3 Measurement procedure (per state)

1. **Baseline**: boot to idle desktop, wait 2 min, collect all counters.
2. **A (idle-connected)**: collect counters over 60 s. Record interrupt rate, powertop wakeups.
3. **B (light)**: `ping -i 0.2 <gw>` for 60 s. Collect counters.
4. **C (download)**: `iperf3 -c <server> -t 60` or `curl -o /dev/null <large-file>`. Collect counters.
5. **D (upload)**: `iperf3 -c <server> -t 60 -R`. Collect counters.
6. **E (scan)**: `iw dev wlan0 scan`. Collect counters + scan duration.
7. **F (reconnect)**: `nmcli dev disconnect wlan0 && nmcli dev connect wlan0`. Collect counters + reconnect time.
8. **G (suspend-resume)**: `systemctl suspend`. Collect dmesg + resume time + post-resume state.

### 2.4 Expected findings (hypotheses to confirm/refute)

| # | Hypothesis | Status |
|---|---|---|
| H1 | Idle interrupt rate is < 10/s with PM_FAST | PROPOSED-HW-MEASUREMENT |
| H2 | No periodic timers fire at idle (only event-driven) | PROPOSED-HW-MEASUREMENT |
| H3 | EFI NVRAM is used on MacBook10,1 (no file NVRAM) | PROPOSED-HW-MEASUREMENT |
| H4 | ACPI module-instance/RWCV present on MacBook10,1 | PROPOSED-HW-MEASUREMENT |
| H5 | DMI board_type = "Apple Inc.-MacBook10,1" (with space) | PROPOSED-HW-MEASUREMENT |
| H6 | Scan completes in < 5 s (no 10 s timeout) | PROPOSED-HW-MEASUREMENT |
| H7 | Suspend/resume works with hot resume (no re-probe) | PROPOSED-HW-MEASUREMENT |
| H8 | No per-packet logging at default debug level | PROPOSED-HW-MEASUREMENT |
| H9 | txflow wq is idle at idle (no TX) | PROPOSED-HW-MEASUREMENT |
| H10 | PCIe ASPM L1 is entered at idle | PROPOSED-HW-MEASUREMENT |

---

## 3. Optimization candidates (all PROPOSED-HW-MEASUREMENT)

| # | Candidate | Source | Hypothesis | Risk | Status |
|---|---|---|---|---|---|
| O1 | Verify EFI NVRAM is used (not placeholder) | firmware.c:488-518 | If EFI NVRAM valid, remove placeholder → real calibration | Low | PROPOSED-HW-MEASUREMENT |
| O2 | Verify ACPI board_type path | acpi.c, pcie.c:2267 | If ACPI properties present, provision Apple-specific NVRAM | Medium | PROPOSED-HW-MEASUREMENT |
| O3 | Confirm no periodic idle timers | cfg80211.c, btcoex.c, p2p.h | Driver is event-driven at idle | None | PROPOSED-HW-MEASUREMENT |
| O4 | Confirm txflow wq idle at idle | msgbuf.c:1581 | Dedicated wq is work-driven, not polling | None | PROPOSED-HW-MEASUREMENT |
| O5 | Measure interrupt coalescing effectiveness | pcie.c:941-966 | Threaded IRQ + doorbell batches reduce wakeups | None | PROPOSED-HW-MEASUREMENT |
| O6 | Verify powersave PM_FAST stability | cfg80211.c:3305 | PM_FAST does not cause disconnects | Low | PROPOSED-HW-MEASUREMENT |
| O7 | Measure scan power cost | cfg80211.c:1506 | Scan is firmware-offloaded, host cost is low | None | PROPOSED-HW-MEASUREMENT |
| O8 | Verify suspend/resume hot path | pcie.c:2636-2706 | Hot resume works, no re-probe | Low | PROPOSED-HW-MEASUREMENT |

---

## 4. What NOT to change (frozen baseline)

- TLP config (`CPU_SCALING_GOVERNOR_ON_AC/BAT=powersave`, `PCIE_ASPM_ON_AC/BAT=powersave`, `USB_AUTOSUSPEND=1`, `RUNTIME_PM_ON_AC/BAT=auto`) — D6 judges separately.
- Kernel cmdline (`quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`) — hardware-validation items, not optimization.
- No `powertop --auto-tune` (banned).
- No `thermald`, `ananicy-cpp`, random sysctl tuning.
- No driver code patches.

---

## 5. D2 — NM scan wakeup + backend A/B HW measurement plan

> Audit date: 2026-09-28. Userspace path: NM → wpa_supplicant → nl80211 → cfg80211 → brcmfmac.
> All items below are HARDWARE VALIDATION REQUIRED (no hardware yet).

### 5.1 NM scan wakeup measurement

Goal: quantify scan-induced wakeups and confirm the D2 config changes reduce them.

| Step | Command | Expected after D2 changes |
|---|---|---|
| 1. Baseline idle-connected | `cat /proc/interrupts \| grep brcmf` over 60s | low event rate (keepalive only) |
| 2. Control Center open (mv-control) | open CC, wait 60s, count `brcmf_pcie_intr` | **no 30s scan spikes** (was: scan every ~30s before `--rescan no`) |
| 3. Explicit refresh | click Refresh in CC | one scan, then quiet |
| 4. Disconnected periodic scan | `nmcli dev disconnect wlan0`, count scans over 60s | NM periodic scan 3s→120s backoff (by design) |
| 5. Connect | `nmcli dev connect wlan0` | scan suppressed when ACTIVATED (supplicant bgscan) |

Counters: `/proc/interrupts` (`brcmf_pcie_intr`), `iw dev wlan0 get power_save`, `iw dev wlan0 survey dump`, `powertop` wakeup lines, `dmesg` (quiet).

### 5.2 Backend A/B procedure (wpa_supplicant vs iwd)

Goal: determine if iwd offers a measurable advantage for BCM43602 on MacBook10,1.

| Step | wpa_supplicant (baseline) | iwd (experiment) |
|---|---|---|
| 1. Select backend | `[device] wifi.backend=wpa_supplicant` (default) | `nmcli` / edit `99-mavericks.conf` → `wifi.backend=iwd` |
| 2. Restart NM | `systemctl restart NetworkManager` | same |
| 3. Connect | `nmcli dev wifi connect <ssid>` | same |
| 4. Idle wakeups | `/proc/interrupts` over 60s | same |
| 5. Scan behavior | `nmcli dev wifi list` (note: iwd has no P2P; 802.1X needs provisioning) | same |
| 6. Roaming | walk between APs, `dmesg`, reconnect time | same (iwd does own roaming) |
| 7. Powersave | `iw dev wlan0 get power_save` | same (identical in NM 1.58.1) |
| 8. SAE/WPA3 | connect to WPA3 AP | connect to WPA3 AP |
| 9. Suspend/resume | `systemctl suspend`, resume, reconnect | same |
| 10. Decision | KEEP wpa_supplicant unless iwd shows measurable wakeup/energy win AND no feature regression | — |

**Decision criteria:** iwd is only adopted if it shows a measurable idle-wakeup or energy advantage AND no feature regression (P2P not needed; 802.1X not needed for home use). Otherwise wpa_supplicant stays (mature, full features). Record result in DECISIONS.md.

### 5.3 Powersave lever (HW validation)

The `[connection] wifi.powersave=3` (enable) lever would make NM send `NL80211_CMD_SET_POWER_SAVE` (PS_ENABLED) → `PM_FAST` for all connections. This is a battery-vs-latency trade-off:
- **Before:** measure idle interrupt rate + `iw dev wlan0 get power_save` with default (`ignore` → firmware default).
- **After:** set `wifi.powersave=3`, reconnect, measure again.
- **Decision:** adopt only if idle wakeups drop AND no disconnects/latency regression (D1 hypothesis O6). Otherwise keep `ignore` (firmware default). PM_FAST stability on BCM43602 is unverified.
