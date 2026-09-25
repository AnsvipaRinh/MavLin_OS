# DECISIONS

## Model: MacBook10,1 (Mid 2017) — explicit, not assumption

**Date:** 2026-09-25
**Decision:** Target hardware model explicitly set to MacBook10,1 (Mid 2017), replacing conservative assumption of MacBook9,1 (Early 2016).

**Reasoning:**
- Development now targets MacBook10,1 specifically, eliminating the 

- Wi-Fi chip revision differs between MacBook9,1 and MacBook10,1: MacBook10,1 uses a specific Broadcom BCM43602 revision that requires broadcom-wl-dkms or specific brcmfmac firmware, whereas MacBook9,1 may use brcmfmac in-kernel
- SPI controller behavior differs: MacBook10,1 has SPI controller rev 3+ which exhibits timeout issues on kernels 6.15+ affecting applespi-driven keyboard/trackpad; the AUR macbook12-spi-driver-dkms package has different compatibility characteristics between the two models
- Keyboard/trackpad bring-up strategy differs: MacBook10,1 requires different quirks and fallback planning than MacBook9,1

**Impact on driver selections (drivers/README.md):'
- Wi-Fi: Prioritize broadcom-wl-dkms for MacBook10,1; brcmfmac may work but requires firmware revision matching
- Keyboard/Trackpad: macbook12-spi-driver-dkms AUR package must be evaluated for MacBook10,1 specifically; external USB-C input remains mandatory for bring-up
- Webcam: facetimehd project compatibility may differ between model revisions

**Rollback path:** If real hardware identifies as MacBook9,1 or MacBook8,1, revert HARDWARE.md model field and adjust driver selections accordingly. Document actual model in DECISIONS.md with date.

---

## Base system: linux-zen + systemd-boot (UEFI only)

**Date:** 2026-09-25
**Decision:** Use linux-zen kernel and systemd-boot for UEFI-only boot on MacBook 12".

**Reasoning:**
- linux-zen provides better interactive responsiveness on fanless Core M hardware (MuQSS scheduler, optimized for desktop interactivity)
- MacBook 12" (A1534) is UEFI-only — no BIOS/CSM support needed, so syslinux/GRUB BIOS boot removed
- systemd-boot is simpler, faster, and integrates well with UKI/EFI stub approach
- rEFInd kept as fallback in package list but systemd-boot is primary

**Alternative considered:** linux-lts (more stable, older kernel) — rejected because MacBook10,1 hardware support (especially applespi, Broadcom Wi-Fi, Cirrus audio) benefits from newer kernel versions; linux-zen 6.x has better Apple hardware support.

---

## Filesystem: btrfs with subvolumes (@, @home, @var_log, @snapshots)

**Date:** 2026-09-25
**Decision:** Use btrfs with subvolume layout for the installed system.

**Reasoning:**
- Snapshots for easy rollback (critical for hardware bring-up iterations)
- Compression (zstd) saves space on soldered SSD
- Subvolumes allow selective snapshot/restore
- Native send/receive for backups

**Implementation:** mkinitcpio.conf includes 'filesystems' hook; bootloader entries use rootflags=subvol=@

---

## Swap: zram (zram-generator) — no disk swap partition

**Date:** 2026-09-25
**Decision:** Use zram-generator for compressed RAM swap, no dedicated swap partition.

**Reasoning:**
- Soldered SSD has limited write endurance — avoid swap partition
- Core M has limited RAM (8GB typical) — zram gives 2-3x effective swap
- zstd compression is fast on Core M
- zram-generator integrates with systemd, no manual setup needed

**Configuration:** /etc/systemd/zram-generator.conf.d/99-mavericks.conf sets zram-size = ram / 2

---

## Power management: TLP + thermald + ananicy-cpp

**Date:** 2026-09-25
**Decision:** Enable TLP, thermald, and ananicy-cpp by default for power management and responsiveness.

**Reasoning:**
- Fanless design makes thermal management critical — TLP configures CPU governors, PCIe ASPM, USB autosuspend
- thermald uses Intel DPTF (if profile available) for proactive thermal control
- ananicy-cpp prioritizes interactive processes (DE, browser) over background tasks
- All three are lightweight and work well together

**Configuration files:** /etc/tlp.d/99-mavericks.conf, /etc/ananicy.d/ (default rules), thermald uses auto-detection

---

## Visual target: Mavericks (OS X 10.9) skeuomorphic aesthetic on Xfce

**Date:** 2026-09-25
**Decision:** Target OS X 10.9 Mavericks visual style (skeuomorphic: textures, shadows, glass, leather/paper textures) implemented on Xfce/GTK3.

**Reasoning:**
- Xfce has minimal overhead on fanless Core M
- GTK3 theming supports the required visual effects (gradients, textures, shadows)
- Mavericks was the peak of skeuomorphic design before flat iOS 7 / Yosemite transition
- Avoids GNOME/KDE bloat while still providing full theming capability

**Components:**
- GTK3 theme (custom, based on historical MacBuntu references)
- Icon theme (Mavericks-era style)
- Dock: plank with reflection/zoom
- Top panel: Xfce panel styled as menu bar
- Cursor: macOS-style
- Wallpapers: Mavericks-inspired (no Apple assets)