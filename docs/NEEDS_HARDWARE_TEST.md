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
- [ ] TLP baseline effectiveness (read-only measurement: tools/diagnostics/mv-power.sh; NEVER powertop --auto-tune on baseline)
- [ ] Intel P-state / HWP behavior (turbostat + energy_performance_preference)
- [ ] Battery discharge rate under idle load (10-min samples)
- [ ] Thermal throttling thresholds (tools/diagnostics/mv-thermal.sh)

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
## E-MC — Mission Control overview (skippy-xd, on HW only)
- [ ] Install: `yay -S skippy-xd-git` (AUR VCS; pulls giflib, libjpeg-turbo, libxcomposite, libxdamage, libxext, libxft, libxinerama + meson/cmake/git)
- [ ] Baseline check first: Super+Tab = rofi script mode (mv-mission-control) works in live session
- [ ] Apply: `sudo tools/experiments/mv-experiment.sh E-MC apply` (or configs/profiles/experiments/E-MC-skippy-xd.sh apply)
- [ ] Validate expose: Super+Tab shows ALL open windows non-overlapping; arrows move highlight; Return/space selects; Escape cancels; click selects
- [ ] Validate minimized windows show filler (accepted — daemon stays OFF by design; do NOT --start-daemon)
- [ ] Validate xfce4-panel (menu bar) stays visible above overview; labels readable on 2304x1440
- [ ] Perf feel: animation 150ms snappy on HD 615, no stutter with 6+ windows
- [ ] Revert check: `... E-MC revert` restores rofi binding; `... E-MC status` reports clean state
- [ ] Record verdict in docs/APPS.md (promote to IMPLEMENTED — HARDWARE VALIDATION REQUIRED, or keep EXPERIMENT READY with findings)

## Mission Control — rofi/wmctrl path (on HW)
- [ ] Super+Tab opens mv-mission-control window overview in live session
- [ ] Window list shows all open windows grouped by workspace
- [ ] Active workspace listed first with "●" marker
- [ ] Active window marked with "▸" prefix
- [ ] Empty workspaces shown with "(empty)" placeholder
- [ ] Window icons display correctly for known applications
- [ ] Filter/search within overview works
- [ ] Enter/click activates selected window
- [ ] Escape closes overview
- [ ] Error handling: if wmctrl missing, user-friendly message with install hint appears

## Phase 3+ — app validation (source-уровень готов в 0.8–0.15)
- [ ] Preview: открыть PDF в evince через mv-preview alias на панели 2304x1440
- [ ] Spotlight: после первой загрузки дождаться plocate-updatedb.timer, Super+Space находит файлы
- [ ] Quick Look: mv-quicklook на image/PDF/text/audio — multi-file nav (←/→/Space), fullscreen (F), Open button work
- [ ] Quick Look: Super+Shift+Space в Thunar копирует выбор в буфер обмена и открывает mv-quicklook с выбранными файлами
- [ ] Quick Look: UCA контекстное меню "Quick Look" работает (правый клик → Quick Look)
- [ ] Quick Look: PDF превью через poppler-glib рендерит первую страницу на 2304x1440
- [ ] Quick Look: Медиа файлы показывают метаданные через ffprobe
- [ ] GUI: notes/settings/about/activity/console на живой Xfce-сессии (на хосте — alive)
- [ ] HUD: mv-hud в genmon показывает ватты RAPL m3-7Y32 (на хосте — graceful `n/a`)
- [ ] Launchpad: Super+L открывает полноэкранную сетку; поиск фильтрует; папки (Utilities/Other) открываются; Back возвращает; иконки отображаются корректно на 2304x1440
- [ ] Launchpad: mv-launchpad.desktop доступен в меню приложений и может быть закреплен в Dock

## Control Center — hardware validation
- [ ] Wi-Fi: network list populates, connect to open/secured AP, disconnect works, password prompt appears
- [ ] Bluetooth: device list shows paired/available devices, connect/disconnect/pair works
- [ ] Sound: output device list shows all sinks, switching changes default sink, volume/mute work
- [ ] Display: brightness slider controls actual panel backlight, Night Shift toggle (if redshift installed)
- [ ] Battery: charge/state/time read from UPower, power mode reflects TLP state
- [ ] DND: toggle syncs with xfce4-notifyd do-not-disturb setting

## Notification Center — hardware validation
- [ ] Super+Shift+V opens mv-notification-center
- [ ] Notification history shows grouped by app with timestamps
- [ ] Clear/Clear All buttons work
- [ ] DND toggle in header syncs with xfce4-notifyd
- [ ] Banner notifications appear top-right with Mavericks theme (rounded, translucent)
- [ ] Urgency colors (low/normal/critical) render correctly on 2304x1440
- [ ] Keyboard navigation (arrows, Escape) works
- [ ] Focus-out auto-close works
