# NEEDS_HARDWARE_TEST — Items requiring real MacBook10,1 hardware

## Phase 0 — Base system
- [ ] Boot ISO on real hardware (UEFI boot via systemd-boot)
- [ ] Verify console access (autologin root, zsh prompt)
- [ ] Confirm dmidecode -s system-product-name outputs "MacBook10,1"

## Phase 1 — Hardware support

### Wi-Fi (Broadcom BCM43602)
- [ ] lspci -nn to confirm exact device ID (14e4:43ba or similar)
- [ ] Test broadcom-wl-dkms (AUR) vs brcmfmac in-kernel
- [ ] Verify firmware loading and connection to AP
- [ ] Test suspend/resume Wi-Fi behavior

### Audio (Cirrus codec)
- [ ] Test macbook12-audio-driver (github.com/leifliddy/macbook12-audio-driver)
- [ ] Verify built-in speakers work (not just headphone jack)
- [ ] Test microphone input
- [ ] Check audio after suspend/resume

### Bluetooth
- [ ] Test macbook12-bluetooth-driver (AUR)
- [ ] Verify Bluetooth controller enumeration
- [ ] Test pairing with devices

### External USB-C input (mandatory for bring-up)
- [ ] Verify USB-C hub + keyboard/mouse works out of box
- [ ] Test USB-C power delivery while using hub

### Internal keyboard/trackpad (applespi) — BEST EFFORT, limit 3 strategies
Strategy 1: macbook12-spi-driver-dkms (AUR) on linux-zen
Strategy 2: linux-zen with applespi patches from linux-macbook kernel
Strategy 3: Try linux-lts or different kernel version
- [ ] Document which strategy (if any) works
- [ ] If all 3 fail → mark as "not supported on this revision"

### Power management
- [ ] TLP configuration effectiveness (powertop --auto-tune comparison)
- [ ] thermald with DPTF profile (if available for MacBook10,1)
- [ ] Intel P-state / HWP behavior
- [ ] Battery life estimation under idle load
- [ ] Thermal throttling thresholds

## Phase 2 — Optimization
- [ ] zram/zswap actual memory savings measurement
- [ ] Boot time (systemd-analyze blame) target <10s to DM
- [ ] Idle RAM usage measurement
- [ ] Idle power draw (if measurable via powertop/battery)

## Phase 3 — Visual layer
- [ ] GTK3 Mavericks theme renders correctly on hardware display (2304×1440)
- [ ] HiDPI scaling works (fractional scaling if needed)
- [ ] Dock (plank) performance acceptable

## Phase 5 — Iteration
- [ ] Collect user feedback: dmesg, journalctl -b, photos of boot/DE
- [ ] Document all regressions and fixes needed