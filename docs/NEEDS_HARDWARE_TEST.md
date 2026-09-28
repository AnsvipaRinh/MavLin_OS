# NEEDS_HARDWARE_TEST — Items requiring real MacBook10,1 hardware

## Browser chrome visual checklist (phase 0.70, pixel validation on HW)
All states below are covered-by-CSS (gate-validated, see docs/SAFARI_SPEC.md §17)
but NOT pixel-validated. Screenshot each on MacBook10,1 at 2304×1440:
- [ ] Fresh launch: toolbar gradient, 38px height, button spacing, inset sheen
- [ ] Empty tab: light #f9f9fb background, wordmark, search field
- [ ] 1 tab / N tabs: rounded top corners, active gradient + toolbar connection, inactive dimming
- [ ] Tab hover/active states: opacity 0.9 / bg 0.12
- [ ] Focused urlbar: blue ring 3px
- [ ] Typed URL: urlbarView popup panel, row selected blue, one-offs
- [ ] Loading: urlbar[busy] tint + 2px blue bottom border
- [ ] Bookmarks bar (newtab): gradient, item hover
- [ ] Top Sites: tile grid spacing, white tiles, hover
- [ ] Downloads: panel + button + [progress] fill + badge
- [ ] Findbar: banner gradient, textbox, focus ring
- [ ] Sidebar: container, header, title, switcher/close buttons
- [ ] Private: purple-tinted toolbar + bookmarks + indicator
- [ ] Context menu: panel, item hover gray, separator, disabled
- [ ] appMenu popup + urlbar popup: panel styling, subviewbutton rows
- [ ] Error page: native chrome acceptable (no CSS covers error pages)
- [ ] History sidebar: native rows acceptable
- [ ] Fullscreen: native behavior acceptable
- [ ] Maximized: window controls (GTK/xfwm4) coherent
- [ ] 2304×1440: HiDPI rendering of all above

## Browser / Video — hardware validation (phase 0.67)
- [ ] vainfo on HD 615 Gen9.5 — confirm H.264/VP8/VP9/HEVC VAAPI profiles
- [ ] Real YouTube playback via Firefox+uBO — measure CPU/RSS with uBO blocking ON
- [ ] Real YouTube playback via mpv+yt-dlp — measure CPU/RSS, compare vs Firefox
- [ ] AV1 software decode cost on Core M (expected high — Gen9.5 has no AV1 HW)
- [ ] WebRender vs basic compositor on HD 615 at 2304×1440
- [ ] HiDPI rendering of Firefox UI (uidensity=0, 2x scaling)
- [ ] dom.ipc.processCount tuning (4 vs 6 vs 8) on 8-16GB RAM
- [ ] Tab thrashing behavior with many tabs on fanless Core M
- [ ] VAAPI video decode performance (H.264/VP9/HEVC) — media.ffmpeg.vaapi.enabled

### 4-mode browser/video validation matrix (phase 0.69)
See `docs/HW_BROWSER_MATRIX.md` for the full 4-mode measurement plan:
- M1: Firefox-vanilla (baseline)
- M2: Firefox+uBO+SB (general browsing with blocking)
- M3: Firefox→ytplayer hybrid (recommended daily workflow)
- M4: ytplayer-direct (video-only, minimal overhead)

All modes use identical workload (3 clips × 5 min), identical metrics
(CPU/GPU/RSS/dropped/wakeups/temp/freq/discharge/time-to-idle), and identical
measurement commands. Run on target hardware only.

## Dictionary — hardware validation
- [ ] WebKit2 tab rendering on the 2304×1440 panel (web process cannot start in the build container — load-changed never fires even with sandbox disabled; all load paths verified at call level + local mode fully tested)
- [ ] Mavericks paper/leather/serif CSS appearance under the Mavericks GTK theme at 2304×1440 (build env has no WM; pixel verification was GTK-level only)
- [ ] espeak-ng pronunciation audio through the Cirrus codec (button presence, voice quality, no audio glitches)
- [ ] dictd/dict-wn availability and offline WordNet lookup on the target system (optdep; graceful no-data state already verified when absent)
- [ ] Online tabs (Wiktionary/thesaurus.com/Wikipedia) load over the BCM43602 Wi-Fi after Phase 1 bring-up
- [ ] load-failed offline page on real network loss (signal signature unit-tested; end-to-end needs real offline moment)

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

### Time Machine (restic + btrfs)
- [ ] USB-C disk throughput on Apple S3X NVMe host (backup window size; restic over USB-C bridge)
- [ ] restic repo on exFAT/NTFS USB disk (cross-platform target readability) vs ext4/btrfs
- [ ] Real restic restore round-trip: backup → delete file → restore → verify content
- [ ] Destructive btrfs subvolume restore from recovery environment (UI currently shows guidance only)
- [ ] Hourly timer wakeup energy cost on battery (expect ~zero when restic no-ops; measure)
- [ ] libsecret/gnome-keyring unlock integration on real login session
- [ ] Starfield CSS appearance on 2304×1440 panel (dot density, label contrast)

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

## Thumbnailer — config gap (decision: no new daemon)
- [ ] tumbler is absent from the ISO package list; thunarrc requests
      thumbnails (`MiscThumbnailMode=ALWAYS`, `MiscShowThumbnails=TRUE`)
      but no backend serves them. Adding tumbler = resident daemon;
      deferred by phase-C decision (power baseline frozen). On hardware:
      decide tumbler vs ffmpegthumbnailer-only vs thumbnails-off, then
      verify Thunar icon-view thumbnails appear without measurable
      idle CPU cost

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
- [ ] Console: dmesg permissions (root vs обычный пользователь — state «requires root» или реальные строки), наличие «Previous Boot» после реальных ребутов, рендеринг badges/sidebar на 2304×1440, energy cost persistent `journalctl --follow` при открытом окне (phase B: заменил 2s respawn poll; kernel-источник — 5s fallback poll)
- [ ] HUD: mv-hud в genmon показывает ватты RAPL m3-7Y32 (на хосте — graceful `n/a`)
- [ ] Launchpad: Super+L открывает полноэкранную сетку; поиск фильтрует; папки (Utilities/Other) открываются; Back возвращает; иконки отображаются корректно на 2304x1440
- [ ] Launchpad: mv-launchpad.desktop доступен в меню приложений и может быть закреплен в Dock

## Control Center — hardware validation
- [ ] Wi-Fi: network list populates, connect to open/secured AP, disconnect works, password prompt appears; NM D-Bus signal-driven refresh fires on scan/connect (phase B: заменил 5s `nmcli dev wifi list` rescan poll; 30s fallback + manual Refresh button) — проверить что спасает battery (rescan energy на BCM43602)
- [ ] Bluetooth: device list shows paired/available devices, connect/disconnect/pair works; verify single _bluez_get_objects D-Bus call per refresh (phase 0.66 dedup)
- [ ] Sound: output device list shows all sinks, switching changes default sink, volume/mute work; verify no-op pactl call removed (phase 0.66)
- [ ] Display: brightness slider controls actual panel backlight on MacBook10,1 (phase 0.66: /sys/class/backlight path verified); Night Shift toggle (if redshift installed)
- [ ] Battery: charge/state/time read from UPower, power mode reflects TLP state; verify 30s refresh_all interval (phase 0.66: was 5s)
- [ ] DND: toggle syncs with xfce4-notifyd do-not-disturb setting
- [ ] Energy Saver: xfce4-power-manager-settings opens from mv-settings (phase 0.66: consolidated from duplicate Battery+Energy entries)

## Session/Power UI — hardware validation
- [ ] Suspend/resume: S3 state on MacBook10,1; Wi-Fi/audio survive resume (logind hooks verified by inspection in phase 0.66)
- [ ] Lid close/open: logind HandleLidSwitch fires; system suspends/resumes correctly
- [ ] Power button: logind HandlePowerKey behavior coherent with mv-power-ui dialog
- [ ] External display: xfce4-display-settings detects and configures via USB-C/DP
- [ ] Suspend/resume test: tools/diagnostics/mv-suspend-test.sh runs clean on hardware

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

## Stickies — hardware validation
- [ ] Print dialog behavior on the real system without CUPS installed (dialog opens; "Save to PDF" path works; no printer → honest state, no hang)
- [ ] Z003 handwriting font rendering quality on the 2304×1440 HiDPI panel (stroke weight, 14pt sizing, line spacing feel)
- [ ] Visual check: yellow note background + border + headerbar color under the Mavericks theme at 2304×1440 (build env cannot render — no WM; pixel verification was GTK-level only: style context bg = #fff8b0)
- [ ] sticky-notes icon appears correctly in Launchpad/Dock/menu with the Mavericks icon theme
- [ ] Focus/raise behavior under xfwm4: clicking a note brings it forward; NORMAL window level behaves like macOS stickies (notes can go behind windows)
- [ ] Multi-note workflow on the real panel: drag/resize smoothness, position persistence across reboots
- [ ] pidfile single-instance lock on the real filesystem (second launch refuses; stale lock after crash is taken over)
- [ ] Energy cost of an open note (design goal: zero — saves are event-driven on edit/configure, no timers, no polling; verify no periodic wakeups)
- [ ] Corrupt-store recovery on the real system (kill -9 during edit → relaunch → backup/quarantine path, no data-loss loop)

## Calculator — hardware validation
- [ ] Mavericks CSS skin rendering on the 2304×1440 HiDPI panel (recessed display gradient, metal button gradients, error-state red, = warm gradient)
- [ ] Keyboard behavior under xfwm4: window-level key-press routing (Enter always equals, Escape clears, numpad), focus behavior with can_focus=False buttons
- [ ] Ctrl+C/Ctrl+V clipboard integration with the real X11/Wayland session
- [ ] Paper tape persistence on the real filesystem (entries survive reboot; corrupt tape → empty, no crash)
- [ ] Energy cost of an open calculator window (design goal: zero — no timers, no polling; saves are event-driven on tape add)
- [ ] Mode switching (Basic/Scientific/Programmer) with the headerbar mode combo under the real WM

## AirDrop — hardware validation
- [ ] Real-device transfer Mac↔Linux with LocalSend on both ends (NOT Apple AWDL — a real Mac AirDrop client will not see this Mac; validation requires LocalSend installed on the other device too)
- [ ] Device discovery over the BCM43602 Wi-Fi: multicast 224.0.0.167:53317 visible on the real AP; check router AP-isolation is off
- [ ] Port 53317 (TCP+UDP) reachable on the real network (no firewall in our baseline; verify no local filtering)
- [ ] Send path end-to-end: mv-airdrop → localsend-cli → LocalSend receiver (small file + large file, checksum verification)
- [ ] Receive path: LocalSend GUI accept dialog on the Mavericks theme; files land in ~/Downloads
- [ ] Energy cost measurement: discovery burst (~2.5 s UDP) and active transfer vs idle baseline (design goal: zero idle cost — no daemon/autostart)
- [ ] HiDPI rendering of the device list and airdrop.svg icon at 2304×1440

## Theme CSS repair — hardware validation (Phase 0.61)
- [ ] Visual check of repaired Mavericks theme on the 2304×1440 HiDPI panel: gradients/shadows/radii intact after syntax-only repair (width/height→min-width/min-height, border-radius 4-value fix, scrollbar stepper collapse)
- [ ] Selection color: ::selection was removed (container GTK 3.24.52 rejects it; real GTK3 supports it) — verify text selection is visible/acceptable with GTK default on hardware; if unacceptable, re-add `*::selection` guarded for real GTK3
- [ ] Placeholder text color in entries (entry::placeholder removed — same GTK3 build limitation) — verify default placeholder contrast on hardware
- [ ] Progress bar pulse (now opacity-based, was transform slide) and spinner animation (now native) render correctly
- [ ] Icon resolution end-to-end on hardware: mv-* .desktop icons resolve via Mavericks→hicolor→Adwaita chain (adwaita-icon-theme now in ISO); check Dock/plank, file dialogs, and app launcher show real icons (not broken-image placeholders)
- [ ] App-launch stderr sample on hardware: confirm zero Gtk-WARNING theme-parse lines per app start (pre-fix: ~90; gate: scripts/test-theme-css.py)
- [ ] HiDPI: theme proportions at 2304×1440 (titlebutton 14px circles, scale/switch slider min-sizes, scrollbar min-slider lengths)

## Fresh-ISO hardware checklist (Phase 0.62, 2026-09-27)
- [ ] Boot mavericks-linux-2026.09.27-x86_64.iso on MacBook10,1 via USB-C (write with dd or balenaEtcher)
- [ ] systemd-boot menu appears → select "Arch Linux install medium"
- [ ] airootfs loads → archiso hook runs → /run/archiso/bootmnt mounted
- [ ] lightdm starts → Xfce session starts → Mavericks theme applies (panel, wallpaper, GTK theme name)
- [ ] Spot-check: panel visible, wallpaper set, gtk theme = Mavericks (xfconf-query -c xsettings -p /Net/ThemeName)
- [ ] applespi: keyboard + trackpad work (known risk — may not work on kernel 6.15+; external USB-C keyboard is fallback)
- [ ] Wi-Fi: broadcom-wl-dkms or brcmfmac loads → BCM43602 associated
- [ ] Audio: Cirrus codec patch → sound output works
- [ ] NVMe: Apple S3X detected → /dev/nvme0n1 visible
- [ ] Battery/thermal: power readings sane, no immediate throttling
- [ ] Display: 2304×1440 panel at correct resolution, HiDPI scaling acceptable
- [ ] USB-C: data + video output through single port

## Video codec HW validation — hardware validation (Phase 0.68, 2026-09-28)

Pre-hardware state: codec ranking measured host-SW (`scripts/bench/results/video-codecs.json`);
selector chain implemented in `mv-ytplayer` (avc1 > vp09 > hev1 > non-av01 > best).
Remaining items are HW-only by construction (no GPU on host; `vainfo` finds no VA driver):

- [ ] VA-API probe on MacBook10,1: `vainfo` lists Gen9.5 (HD 615) engines —
      confirm H.264, VP9, HEVC Main decode profiles present; confirm AV1 absent
      (expected: no AV1 engine on Gen9.5)
- [ ] `mpv --hwdec=auto` end-to-end on YouTube via `mv-ytplayer`: verify chosen
      format is avc1/vp09/hev1 (not av01) and `mpv --hwdec=auto` reports HW decode
      active (mpv OSD/stats: `hwdec: vaapi`); verify no SW fallback during playback
- [ ] AV1 fallback path: force an AV1-only stream, confirm branch-5 fallback works
      and SW decode is flagged (expected heavy on Core M — document actual cost)
- [ ] Power/thermal per codec on battery: h264 vs vp9 vs hevc 1080p playback —
      battery discharge rate, package energy (RAPL), surface temperature, fanless
      throttling behavior; compare against host-SW baseline (4.20/5.57/7.99 ms/frame)
- [ ] VA-API vs SW power delta: measure whole-system power with HW decode on vs
      off to quantify the HW-decode win on the fanless chassis
- [ ] Firefox VA-API: `media.ffmpeg.vaapi.enabled` experiment (commented in
      `configs/firefox/user.js`) — validate on hardware, measure before/after
