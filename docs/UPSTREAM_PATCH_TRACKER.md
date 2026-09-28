# UPSTREAM PATCH TRACKER

> Tracks upstream fixes identified during runtime/driver audits that would
> require a patch to NetworkManager / wpa_supplicant / iwd / the kernel
> driver. Config/packaging workarounds live in DECISIONS.md, NOT here.
> A patch is only listed here when a real upstream defect or missing
> feature is found that cannot be worked around from our packaging.

---

## D2 — NetworkManager → wpa_supplicant/iwd → nl80211 → cfg80211 userspace path (2026-09-28)

**Result: NONE — no upstream fix identified.**

### Search performed

| # | Question | Where searched | Outcome |
|---|---|---|---|
| 1 | Does NM have a periodic-scan defect on FullMAC? | NM 1.58.1 `src/core/devices/wifi/nm-device-wifi.c` (`_scan_notify_allowed`, `_scan_kickoff`) | No defect. Periodic scans are DISCONNECTED-only (3s→120s backoff, `SCAN_INTERVAL_SEC_MIN/STEP/MAX`); ACTIVATED relies on supplicant background scan. Explicit scans rate-limited 8s. By design. |
| 2 | Does NM connectivity-check need an upstream fix? | NM 1.58.1 `nm-config.h` (`NM_CONFIG_DEFAULT_CONNECTIVITY_INTERVAL 300`), `man/NetworkManager.conf.xml`, Arch `20-connectivity.conf` | No defect. Arch ships `uri=http://ping.archlinux.org/nm-check.txt`; NM default `enabled=true`, `interval=300s`. Worked around from our packaging (`enabled=false`). |
| 3 | Does wpa_supplicant need a powersave fix for BCM43602? | wpa_supplicant 2.12 `src/drivers/driver_nl80211.c` (`nl80211_set_power_save`), NM 1.58.1 `nm-device-wifi.c:3412` | No defect. NM 1.58.1 sets 802.11 PS via `NL80211_CMD_SET_POWER_SAVE` directly (both backends). wpa_supplicant's own PS path is not on the NM path. |
| 4 | Does iwd need a powersave fix for the NM backend? | NM 1.58.1 `nm-device-iwd.c:2274` (`set_powersave`), NM commit 5838c38 | No defect. iwd-backend powersave support added in NM (commit 5838c38); present in 1.58.1. |
| 5 | Is there an NM/iwd backend-selection defect? | NM 1.58.1 `meson.build:430-436`, `nm-wifi-factory.c:126` | No defect. Default `wpa_supplicant`; `wifi.backend` device config selects backend. Pinned explicitly in our packaging. |
| 6 | Does the mv-control 30s scan issue need an upstream fix? | nmcli(1) man page ("ensures that the access point list is no older than 30 seconds and triggers a network scan if necessary") | Not an upstream defect — nmcli behavior is documented and correct. Fixed in our app (`--rescan no`). |

### Conclusion

No upstream patches required for the D2 userspace path. All findings are
either (a) by-design NM behavior, (b) Arch packaging defaults worked around
from our own config, or (c) our own app behavior fixed locally. No NM /
wpa_supplicant / iwd source patches are needed or proposed.

---

## D3 — i915 display path upstream status (Gen9.5, 2026-09-28)

### PSR flicker fixes (Gen9 KBL/CML/SKL)

**Status: LANDED upstream (mainline 6.8.0-53+).**

Jouni Högander's 8-patch series "Fix panel flickering issue when i915.psr2 is enabled"
landed in mainline. The series improves ALPM (Active Link Power Management) wake
lines calculation for PSR2, fixing flicker on affected panels. Ubuntu SRU patches
applied to Noble (6.8.0-53) and later.

**Relevance to us:** The upstream fix addresses PSR2 flicker on Gen9. However,
our baseline is `i915.enable_psr=0` (diagnostic-safe). The upstream fix may allow
re-enabling PSR1 (not PSR2) on our panel if it is not in the affected quirk list.
HW validation (§6.1) will determine if PSR1 can be safely enabled.

**References:**
- Ubuntu SRU: lists.ubuntu.com/archives/kernel-team/2024-May/151052.html
- Upstream bug: gitlab.freedesktop.org/drm/intel/-/issues/9739
- LP#2086587, LP#2062951 (Gen9 flicker reports)

### Apple S3X NVMe resume fix

**Status: NO upstream fix yet — LKML thread open (Sep 2026).**

The LKML thread "nvme: Apple S3X (106b:2003) unresponsive after resume on
MacBook10,1, fixed by pcie_port_pm=off" (Sep 2026) documents the issue and
the workaround. No upstream patch has been proposed or merged. The thread asks
if a PCI quirk for root port 00:1c.0 is possible instead of the global
`pcie_port_pm=off` disable.

**Relevance to us:** Our baseline uses `pcie_port_pm=off` as a provisional
workaround. If an upstream quirk or fix lands, we can switch to the narrower
fix and restore PCIe root port runtime PM (saving battery). Monitor the LKML
thread for updates.

**References:**
- LKML: lists.openwall.net/linux-kernel/2026/09/21/161
- Root port: Intel Sunrise Point-LP PCH 00:1c.0 (L1 PM Substates capable)

### DMC firmware (KBL)

**Status: STABLE — no upstream issues.**

The KBL DMC firmware (`i915/kbl_dmc.bin`) is in linux-firmware and loads
correctly. No known issues with DMC on Gen9.5.

### FBC on Gen9

**Status: STABLE — no upstream issues.**

FBC on Gen9 is mature and stable. No known flicker or corruption issues.
FBC + PSR1 coexistence on Gen9 is correct (mutual exclusion only on Gen12+).
