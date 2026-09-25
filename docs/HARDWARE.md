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
- Kernel command line (Phase 0.3 baseline, source of truth):
  `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`
  (pcie_port_pm=off = Apple S3X resume workaround; psr=0 = diagnostic-safe)

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
- TLP only: CPU governor powersave, PCIe ASPM powersave, USB autosuspend, runtime PM auto
- thermald/ananicy-cpp REMOVED (Phase 0.2/0.3)
- zram + kernel defaults; no sysctl overrides in baseline

**Network:**
- systemd-networkd + systemd-resolved + iwd
- Wi-Fi: broadcom-wl-dkms (AUR) prioritized for BCM43602 on MacBook10,1
- Ethernet: DHCP via systemd-networkd

**Services enabled (installed system):**
- NetworkManager, systemd-resolved
- tlp, systemd-zram-setup@zram0
- lightdm, bluetooth
- fstrim.timer
- (ISO additionally: systemd-networkd, iwd, sshd, reflector for install)

**Modprobe configuration (/etc/modprobe.d/99-mavericks.conf):**
- Phase 0.3 baseline: kernel defaults, no active options.
- brcmfmac used for BCM43602 (NVRAM provisioned at first boot).
- i915/nvme/applespi experiments via configs/profiles/experiments/.

**Live ISO packages:** ~75 packages (base, linux-zen, network tools, storage tools, installation tools)
- ISO size: ~1.6 GB
- Boot tested in QEMU+OVMF (UEFI) — systemd-boot menu appears, kernel loads