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

### Music (audio stack + backend)
- [ ] Validate lollypop playback on MacBook10,1 audio (Cirrus codec, macbook12-audio-driver)
- [ ] Verify MPRIS D-Bus interface exposed by lollypop on this PipeWire/PulseAudio stack
- [ ] Test XF86AudioPlay/Next/Prev/Stop media keys (internal applespi keyboard and external USB keyboard)
- [ ] Verify HiDPI (2304×1440) rendering of album art grid, leather sidebar, now-playing bar
- [ ] Check energy cost of PropertiesChanged-driven refresh during playback

### Voice Memos (recording + playback)
- [ ] Test pw-record recording from Cirrus microphone input (macbook12-audio-driver); verify WAV file created and level meter moves
- [ ] Test pw-play playback of recorded memo on internal speakers
- [ ] Verify cassette reel animation and waveform strip rendering on 2304×1440 panel
- [ ] Test trim/export/rename/delete (Trash) flows on real install
- [ ] Verify %U open from Thunar (MimeType audio/*) plays the memo
- [ ] Check recording energy cost (pw-record one-shot, no daemon)

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

### Photos
- [ ] gthumb availability and Edit-in-gthumb handoff on real install
- [ ] exiftool availability for rotate fallback
- [ ] Thumbnail cache behavior on real library (~/.cache/mv-photos/thumbs)
- [ ] HiDPI rendering of grid/sidebar on 2304×1440 panel
- [ ] Import flow from USB-C card reader / camera
- [ ] Slideshow performance on Intel HD 615
- [ ] Geometry restore on real session

## Phase 2 — Optimization
- [ ] zram/zswap actual memory savings measurement
- [ ] Boot time (systemd-analyze blame) target <10s to DM
- [ ] Idle RAM usage measurement
- [ ] Idle power draw (if measurable via powertop/battery)

## Phase 3 — Visual layer

### Desktop Chrome visual validation (2304×1440)
- [ ] Menu bar: panel.css translucent/gradient look on real panel
- [ ] Dock: plank Mavericks theme (zoom, reflection, indicators) on real panel
- [ ] xfwm4: traffic-light buttons (close/minimize/maximize LEFT) visible and functional
- [ ] Wallpaper: mavericks-desktop.png (2304×1440) displays correctly
- [ ] File chooser: pathbar buttons + column headers visible
- [ ] Dialogs: dialog-action-area button styling visible
- [ ] Context menus: frosted-glass menu look

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
- [ ] Preview: открыть PDF через mv-preview на панели 2304x1440 — multi-page nav (arrows, Home/End), thumbnail sidebar click, fullscreen (F), Open button, annotation toolbar visible
- [ ] Preview: открыть image (PNG/JPG/TIFF) через mv-preview — render, fullscreen, multi-file nav (Ctrl+arrows)
- [ ] Preview: MIME associations — double-click PDF/image in Thunar opens mv-preview
- [ ] Preview: annotation toolbar stubs show status feedback; no crashes on tool clicks
- [ ] Spotlight: после первой загрузки дождаться plocate-updatedb.timer, Super+Space находит файлы
- [ ] Quick Look: mv-quicklook на image/PDF/text/audio — multi-file nav (←/→/Space), fullscreen (F), Open button work
- [ ] Quick Look: Super+Shift+Space в Thunar копирует выбор в буфер обмена и открывает mv-quicklook с выбранными файлами
- [ ] Quick Look: UCA контекстное меню "Quick Look" работает (правый клик → Quick Look)
- [ ] Quick Look: PDF превью через poppler-glib рендерит первую страницу на 2304x1440
- [ ] Quick Look: Медиа файлы показывают метаданные через ffprobe
- [ ] GUI: notes/settings/about/activity/console на живой Xfce-сессии (на хосте — alive)
- [ ] Console: реальные значения journald на MacBook10,1 — JSON-поля PRIORITY/SYSLOG_IDENTIFIER/__REALTIME_TIMESTAMP парсятся, severity badges соответствуют приоритетам ядра/systemd
- [ ] Console: dmesg permissions (root vs обычный пользователь — state «requires root» или реальные строки), наличие «Previous Boot» после реальных ребутов, рендеринг badges/sidebar на 2304×1440, energy cost 2s live-tail при открытом окне
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

## Screenshot — hardware validation
- [ ] Super+Shift+3 captures fullscreen to ~/Pictures/Screenshots
- [ ] Super+Shift+4 captures region to clipboard
- [ ] Super+Shift+5 captures region to file
- [ ] Post-capture preview dialog appears with thumbnail and actions
- [ ] "Open in Preview" launches mv-preview with annotation toolbar
- [ ] "Show in Finder" opens Thunar with file selected
- [ ] "Move to Trash" moves file to GVfs trash
- [ ] Preview dialog auto-closes after configurable timeout
- [ ] Config file (~/.config/mv-shot/config.ini) controls save_dir, show_preview, preview_timeout, copy_to_clipboard
- [ ] Recording (--record) works via ffmpeg x11grab, CPU/power acceptable on m3-7Y32
- [ ] Error handling: graceful degradation if xfce4-screenshooter/ffmpeg missing
- [ ] Visual validation: preview dialog renders correctly on 2304×1440 panel

## Disk Utility — hardware validation
- [ ] mv-diskutil launches from .desktop / app menu and shows the internal Apple SSD in the sidebar (Internal group)
- [ ] S3X NVMe section appears for the Apple SSD and populates with real NVMe SMART/telemetry (graceful "Available on hardware" state is expected to be replaced by real data)
- [ ] Capacity bar shows real used/free values (statvfs) for the mounted root volume
- [ ] First Aid shows real S.M.A.R.T. status (Verified) and temperature for the internal SSD
- [ ] Unmount/eject of a USB stick works via the UI; error dialog appears on failure (e.g. busy device)
- [ ] UDisks2 not-available empty state is NOT shown on a normal boot (service present)
- [ ] Visual validation: sidebar/detail/First Aid render correctly on 2304×1440 panel
- [ ] Format/partition fallback note: launching gnome-disks from terminal works for destructive ops

## Power UI — hardware validation
- [ ] Ctrl+Alt+Escape opens the chooser; Ctrl+Alt+Delete opens the Log Out dialog
- [ ] Sleep: system suspends and resumes cleanly (S3) on MacBook10,1; Wi-Fi/audio survive resume
- [ ] Restart: 60 s countdown auto-executes; Cancel aborts; reopen-windows checkbox restores session
- [ ] Shut Down: powers off completely; next boot starts firmware/UEFI normally
- [ ] Log out: xfce4-session-logout terminates the session back to the login screen
- [ ] Battery footer shows real percentage/state from UPower (Charging/Discharging)
- [ ] polkit interactive auth (if required) renders correctly during power actions
- [ ] Hardware power button (top-right) behavior is coherent with the dialog (logind HandlePowerKey)
- [ ] Visual validation: undecorated Mavericks alert renders correctly on 2304×1440 panel (shadow, rounded corners, aqua default button)
- [ ] Countdown label updates each second; Escape/Cancel aborts without executing

## Notes — hardware validation
- [ ] Visual validation: leather folder sidebar, lined paper editor, paper notes list render correctly on 2304×1440 panel (CSS gradients, margins)
- [ ] Checkbox click-to-toggle feels correct (click zone vs cursor placement) on the real trackpad
- [ ] Print dialog renders note text correctly (Gtk.PrintOperation draw-page)
- [ ] Window geometry persistence restores size/position on relaunch in a real session
- [ ] Search highlighting visible at 2304×1440 with project font stack
- [ ] %U import: opening a .txt file from Thunar/Finder creates a note (MIME association check)

## Reminders — hardware validation
- [ ] Visual validation: leather list sidebar, paper task list, priority badges, overdue/due-today highlighting render correctly on 2304×1440 panel
- [ ] Due-date nudges: hourly user systemd timer (mv-reminders-check) fires notify-send for due/overdue tasks in a real session (once per task per day)
- [ ] notify-send notifications appear in xfce4-notifyd and reach Notification Center
- [ ] Checkbox toggle feels correct on the real trackpad; row double-click opens edit dialog
- [ ] Context menus (task: Edit/Toggle/Delete; list: Rename/Delete) render with Mavericks styling on 2304×1440
- [ ] Last-list deletion guard shows the info dialog in a real session
- [ ] Window geometry persistence restores size/position on relaunch in a real session
- [ ] Corrupt-store warning dialog renders correctly (backup restore + quarantine paths)

## Calendar — hardware validation
- [ ] Visual validation: leather sidebar, paper content, mini-month marks, colored event blocks render correctly on 2304×1440 panel
- [ ] Week/Day time grid: hour gutter, all-day strip, event block positioning by hour/minute render correctly
- [ ] Upcoming-event nudges: mv-calendar-check user timer (every 5 min) fires notify-send for events starting within 15 minutes in a real session; once per event per start
- [ ] notify-send notifications appear in xfce4-notifyd and reach Notification Center
- [ ] Ctrl+Alt+C global binding opens Calendar in a real Xfce session
- [ ] Event dialog validation UX (OK disabled until title; end<start error) with real keyboard/trackpad
- [ ] Window geometry persistence restores size/position on relaunch in a real session
- [ ] Corrupt-store warning dialog renders correctly (backup restore + quarantine paths)
- [ ] Import a real-world ICS (e.g. Google Calendar export): escaping/folding/RRULE parse correctly

## Keychain Access — hardware validation
- [ ] Real gnome-keyring daemon present in the Xfce session; auto-unlock at login (pam-gnome-keyring or equivalent) works on MacBook10,1
- [ ] Collections from the real daemon (login / System / System Roots) appear in the sidebar with correct lock icons
- [ ] Real items visible: NetworkManager network passwords, stored Wi-Fi credentials, any certificates/keys in the system keyring
- [ ] "Show password" triggers the daemon unlock prompt for a locked collection; secret renders only after successful unlock
- [ ] Lock button actually locks items (verify via seahorse or secret-service state after click)
- [ ] New Password Item / generator / delete work against the real daemon; stored items appear in seahorse
- [ ] Rendering of leather sidebar, paper detail pane, and dialogs on the 2304×1440 panel
- [ ] Energy cost of the open window (design goal: zero — no polling, all reads on-demand; verify no periodic wakeups)

## Font Book — hardware validation
- [ ] Waterfall + glyph grid rendering quality on the 2304×1440 HiDPI panel (cell density, paper backgrounds, section headers)
- [ ] Install font round-trip on the real system: copy to ~/.local/share/fonts, fc-cache picks it up, font appears in apps (Firefox) after re-enumeration
- [ ] Serif/Sans/Fixed Width classification sanity against the real font set of the installed ISO
- [ ] gnome-font-viewer handoff button behavior when gnome-font-viewer is installed
- [ ] Energy cost of the open window (design goal: zero — all rendering on-demand via draw signals, no timers, no polling; verify no periodic wakeups)

## Digital Color Meter — hardware validation
- [ ] Real pixel values on the 2304×1440 panel: sample known colors (e.g., a test image in Preview) and verify readout accuracy
- [ ] X11 session under Xfce: live sampling works (build env is Wayland — X11 path validated only via mocked sampler)
- [ ] Aperture averaging correctness on real screen content (1×1 vs 25×25 on gradients)
- [ ] Loupe rendering quality on the HiDPI panel (cell density, center outline)
- [ ] Pointer tracking smoothness at 100 ms refresh on the real panel
- [ ] gcolor3 handoff button when gcolor3 is installed
- [ ] Energy cost of the open window (design goal: only the 100 ms timer while open; verify no periodic wakeups when closed)
