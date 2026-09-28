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

---

## D4 — Audio path upstream status (Cirrus CS4208 / HDA, 2026-09-28)

**Result: NO upstream patches required from our side. One community-driver
tracking decision (tanisperez fork) is recommended.**

### Search performed

| # | Question | Where searched | Outcome |
|---|---|---|---|
| 1 | Is CS4208 MacBook support upstreamed in the kernel? | mainline sound/hda (patch_cirrus.c history), leifliddy/tanisperez driver READMEs | **No.** Mainline has no working CS4208 configuration for MacBook9,1/10,1: the codec is detected but the speaker amplifier is never enabled → speakers stay silent. The community DKMS driver (leifliddy, based on davidjo's snd_hda_macbookpro) is the only working implementation. No upstream patch proposed or merged. |
| 2 | Does alsa-ucm-conf have UCM for CS4208? | GitHub API: alsa-project/alsa-ucm-conf ucm2/ tree listing | **No.** No cs4208/Cirrus entry; only generic HDA HiFi profiles. No UCM gap — the codec driver does its own mixer setup. |
| 3 | Is the leifliddy driver maintained? | github.com/leifliddy/macbook12-audio-driver (README: "WIP") | **Stale.** README marks the project WIP; does not compile on modern kernels per community reports. The tanisperez fork adds 6.17+ support and a working DKMS flow (PRE_BUILD kernel-source download). |
| 4 | Does the tanisperez fork fix the DKMS build? | github.com/tanisperez/macbook12-audio-driver dkms.conf | **Yes.** dkms.conf uses `PRE_BUILD="install.cirrus.driver.sh -k $kernelver"` + plain `make` with a restructured `build/hda/codecs/cirrus` layout — the install script downloads the kernel source, patches it in-tree, and builds. Requires network at install time. |
| 5 | Does TLP need a fix for audio power save? | TLP 1.9.1 docs (linrunner.de/settings/audio), TLP defaults.conf | **No defect.** TLP 1.9.1 defaults (SOUND_POWER_SAVE_ON_AC=1, ON_BAT=1, CONTROLLER=Y) already enable audio power save on AC+BAT. Our former modprobe lines were redundant (removed in D4). |
| 6 | Do PipeWire / WirePlumber need fixes for this card? | PipeWire 1.6.9 / WirePlumber 0.5.17 behavior + driver README | **No defect.** The soft-volume rule (api.alsa.soft-mixer) is a supported WirePlumber device property; installed by our package since D4. No upstream issue. |

### Conclusion

No upstream patches are needed or proposed for the D4 audio path. All D4
fixes are our own packaging (888e0ff). The one tracking decision: the
recommended replacement pin for the DKMS driver is
**tanisperez/macbook12-audio-driver** (active maintenance, 6.17+ support,
working DKMS via PRE_BUILD) — to be executed as a separate packaging track
with its own validation (DECISIONS D4-4, DRIVER_OPTIMIZATION_CANDIDATES §7.1).
Monitor the leifliddy and tanisperez repos for changes.

**References:**
- Driver: github.com/leifliddy/macbook12-audio-driver (WIP, pinned r108.g4cdfcdb)
- Fork: github.com/tanisperez/macbook12-audio-driver (6.17+, working DKMS)
- UCM: github.com/alsa-project/alsa-ucm-conf (no CS4208 entry)
- TLP audio: linrunner.de/tlp/settings/audio (1.9.1 defaults)

---

## D5 — INPUT + STORAGE upstream status (2026-09-28)

### Apple SPI (applespi) upstream status

**Status: NO upstream fix for SPI timeout on kernel 6.15+.**

The applespi driver (roadrunner2/macbook12-spi-driver) is a community driver, not
mainlined. The SPI controller timeout bug on MacBook10,1 (rev3+) is in the
spi_pxa2xx_platform driver, which IS mainlined, but the bug is hardware-specific
and has no upstream fix.

| # | Question | Where searched | Outcome |
|---|---|---|---|
| 1 | Is applespi mainlined? | Linux input subsystem (drivers/input/keyboard/) | **No.** applespi is a community driver (AUR macbook12-spi-driver-dkms). |
| 2 | Is the SPI timeout bug fixed upstream? | Linux SPI subsystem (drivers/spi/spi-pxa2xx-platform.c) | **No.** The bug is hardware-specific (MacBook10,1 rev3+ SPI controller). No upstream patch. |
| 3 | Does the AUR macbook12-spi-driver-dkms package fix it? | AUR package description | **Unknown.** The package may have patches, but compatibility with MacBook10,1 on 6.15+ is unverified. |
| 4 | Does the linux-macbook kernel have patches? | linux-macbook kernel (GitHub) | **Unknown.** The linux-macbook kernel may have SPI controller patches, but compatibility is unverified. |
| 5 | Does linux-lts avoid the bug? | Linux LTS kernel (6.6+) | **Unknown.** The bug may be 6.15+ only, but this is unverified. |

**Conclusion:** No upstream fix is available. The 3-strategy best-effort limit applies.
External USB-C HID is the mandatory bring-up interface.

**References:**
- Driver: github.com/roadrunner2/macbook12-spi-driver (GPL-2.0)
- AUR: macbook12-spi-driver-dkms
- SPI controller: drivers/spi/spi-pxa2xx-platform.c (mainlined)
- linux-macbook kernel: github.com/torvalds/linux (no MacBook10,1-specific patches)

### Apple S3X NVMe upstream status

**Status: NO upstream fix yet — LKML thread open (Sep 2026).**

The Apple S3X NVMe controller (106b:2003) becomes unresponsive after S3/s2idle
resume on MacBook10,1. The workaround is `pcie_port_pm=off` (global, disables
ALL PCIe root port runtime PM). The LKML thread asks if a PCI quirk for 00:1c.0
is possible instead of the global disable.

| # | Question | Where searched | Outcome |
|---|---|---|---|
| 1 | Is there an upstream NVMe fix for S3X? | Linux NVMe subsystem (drivers/nvme/) | **No.** No Apple S3X-specific patches. |
| 2 | Is there an upstream PCIe quirk for 00:1c.0? | Linux PCIe subsystem (drivers/pci/) | **No.** No Apple-specific quirk. |
| 3 | Is the LKML thread still open? | LKML (Sep 2026) | **Yes.** Thread open, no patch proposed. |
| 4 | Does `pcie_aspm=off` help? | LKML thread | **No.** Did not fix the resume bug. |
| 5 | Does `nvme_core.default_ps_max_latency_us=0` help? | LKML thread | **No.** Did not fix the resume bug. |

**Conclusion:** No upstream fix is available. `pcie_port_pm=off` is our provisional
workaround. Monitor the LKML thread for updates.

**References:**
- LKML: lists.openwall.net/linux-kernel/2026/09/21/161
- Root port: Intel Sunrise Point-LP PCH 00:1c.0 (L1 PM Substates capable)
- NVMe driver: drivers/nvme/host/core.c (mainlined, no S3X-specific code)
