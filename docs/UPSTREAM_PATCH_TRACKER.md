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
