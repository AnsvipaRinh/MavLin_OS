# HARDWARE

**Model: MacBook10,1 (Mid 2017)**

**Known A1534 revisions:**
- Keyboard/Trackpad: AppleSPI protocol — behavior differs from MacBook9,1; SPI controller rev 3+ on kernels 6.15+ may have timeout issues; external USB-C input mandatory for bring-up
- Audio: Cirrus codec — patch required for built-in speakers (same codec, different revision than MacBook9,1)
- Wi-Fi: Broadcom BCM43602 — revision dependent on lspci; MacBook10,1 uses specific rev requiring broadcom-wl-dkms or specific brcmfmac firmware build
- Webcam: FaceTime HD — facetimehd project, low priority if not critical

**Critical note:** Internal keyboard/trackpad via applespi has known issues on kernels 6.15+ (SPI timeouts, driver from AUR fails to build without manual patches). External USB-C keyboard/mouse via hub is mandatory for bring-up, not optional fallback.

**Verification:** Upon first real hardware boot, confirm via `dmidecode -s system-product-name` outputs MacBook10,1. If different revision, adjust driver selections and rebuild ISO.

---

## Base System Configuration (ISO)

**Kernel:** linux-zen (latest in Arch repos)
- Better interactive responsiveness on fanless Core M
- Newer Apple hardware support (applespi, Broadcom, Cirrus)

**Bootloader:** systemd-boot (UEFI only)
- MacBook 12" is UEFI-only, no BIOS/CSM
- Loader entries: mavericks-linux-zen.conf, mavericks-linux-zen-fallback.conf
- Kernel command line includes: intel_idle.max_cstate=4 i915.enable_guc=3 i915.enable_fbc=1 i915.enable_psr=2 nvme.noacpi=1 acpi_backlight=vendor applespi.debug=0

**Initramfs:** mkinitcpio with hooks: base udev autodetect microcode modconf kms keyboard keymap block filesystems fsck
- MODULES: applespi spi_pxa2xx_platform intel_lpss_pci intel_lpss_acpi
- Compression: zstd (fast on Core M)

**Filesystem (installed system):** btrfs with subvolumes
- @ (root), @home, @var_log, @snapshots
- Compression: zstd
- Bootloader uses rootflags=subvol=@

**Swap:** zram-generator (zram0 = RAM/2, zstd compression)
- No disk swap partition (SSD endurance)
- systemd-zram-setup@zram0.service enabled

**Power Management:**
- TLP: CPU governor powersave, boost disabled, PCIe ASPM powersupersave, USB autosuspend
- thermald: Intel DPTF thermal management (if profile available)
- ananicy-cpp: Process priority optimization for interactivity

**Network:**
- systemd-networkd + systemd-resolved + iwd
- Wi-Fi: broadcom-wl-dkms (AUR) prioritized for BCM43602 on MacBook10,1
- Ethernet: DHCP via systemd-networkd

**Services enabled by default:**
- systemd-networkd, systemd-resolved, iwd
- tlp, thermald, ananicy-cpp
- systemd-zram-setup@zram0
- fstrim.timer, reflector.service
- sshd (for remote access during bring-up)

**Modprobe configuration (/etc/modprobe.d/99-mavericks.conf):**
- Blacklist: brcmfmac, brcmsmac, b43, b43legacy, ssb, bcma
- applespi debug=0
- i915 enable_guc=3 enable_fbc=1 enable_psr=2
- nvme_core default_ps_max_latency_us=0

**Live ISO packages:** ~75 packages (base, linux-zen, network tools, storage tools, installation tools)
- ISO size: ~1.6 GB
- Boot tested in QEMU+OVMF (UEFI) — systemd-boot menu appears, kernel loads