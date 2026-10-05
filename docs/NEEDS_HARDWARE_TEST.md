# NEEDS_HARDWARE_TEST — Items requiring real MacBook10,1 hardware

## Finder search / column browser — hardware validation (phase finder-p0)
- [ ] Visual: mv-finder-search results window (HeaderBar + search field, Name/Kind/Size/Where columns, folders-first ordering) under the Mavericks GTK theme at 2304×1440
- [ ] Visual: mv-finder-columns multi-pane column browser proportions at 2304×1440 (240px columns readable at 2x scaling)
- [ ] Thunar UCA entries appear in context menu and pass `%f` correctly for background click (current folder) and selected folder
- [ ] Recursive search latency over the real $HOME tree on Apple S3X NVMe (walk backend) and plocate fast-path with real index
- [ ] UCA icons resolve (edit-find, format-justify-fill via Mavericks→Adwaita inheritance)
- [ ] Esc semantics in the search window do not collide with xfwm4 keybindings on real session

## Finder view/zoom fidelity — hardware validation (phase finder-p0 close-out)
- [ ] 64px icon default (THUNAR_ZOOM_LEVEL_150_PERCENT) at 2x scaling on 2304×1440 — confirm Mavericks-like proportions; revisit if oversized for the 1152×720 logical space
- [ ] Ctrl+=/-/0 zoom feel in Thunar (icon/list/compact views) and in mv-finder-search / mv-finder-columns (16/22/32/48 ladder)
- [ ] Ctrl+1/2/3 view switching does not collide with anything on real session
- [ ] Per-directory zoom memory works over real GVfs metadata on S3X (folder opened at custom zoom stays zoomed)

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
- [ ] **D1 audit HW items** (see docs/DRIVER_OPTIMIZATION_CANDIDATES.md §2):
  - [ ] Confirm EFI NVRAM path: `dmesg | grep "Using nvram EFI variable"` — if present, placeholder .txt is NOT needed (F1/F6)
  - [ ] Confirm ACPI board detection: `dmesg | grep -iE "ACPI module-instance|Apple board"` — determines NVRAM file selection (F5)
  - [ ] Confirm DMI fallback: `dmesg | grep -i "Board:"` — expect "Apple Inc.-MacBook10,1" if no ACPI (F4)
  - [ ] Verify 5GHz channels available: `iw dev wlan0 scan | grep -c "freq 5"` — confirms NVRAM calibration loaded
  - [ ] Verify signal strength: `iw dev wlan0 station dump | grep signal` — should be reasonable (>-70 dBm)
  - [ ] Measure idle interrupt rate: `cat /proc/interrupts | grep brcmf` over 60 s — expect <10/s (H1)
  - [ ] Measure powersave: `iw dev wlan0 get power_save` — confirm PM_FAST/PM_OFF (H1/O6)
  - [ ] Measure scan duration: `iw dev wlan0 scan` — expect <5 s, no 10 s timeout (H6/O7)
  - [ ] Measure suspend/resume: `systemctl suspend` — confirm hot resume, no re-probe (H7/O8)
  - [ ] Measure throughput: `iperf3 -c <server> -t 60` — RX/TX rate, errors (C/D states)
  - [ ] Confirm no per-packet logging: `dmesg | grep brcmf` — should be silent at default debug (H8)

### Audio (Cirrus codec)
- [ ] **Packaging resolved (D4-4-FOLLOWUP):** pin switched to tanisperez/macbook12-audio-driver (PRE_BUILD downloads kernel source, DKMS-native). Package is NOT in ISO — manual post-install required.
- [ ] **Manual install procedure:**
    1. Boot installed system with external USB-C network (ethernet dongle or Wi-Fi via phone tether)
    2. `git clone https://github.com/tanisperez/macbook12-audio-driver.git`
    3. `cd macbook12-audio-driver && sudo ./install.cirrus.driver.sh -i`
    4. Reboot
  Or if using local repo: `cd /path/to/MavLinOS/packages/macbook12-audio-driver && sudo pacman -U macbook12-audio-driver-*.pkg.tar.zst` then `sudo dkms install -m macbook12-audio-driver -v <pkgver>` (PRE_BUILD fetches kernel source)
- [ ] Verify DKMS status: `dkms status` → `macbook12-audio/0.1, <kernel>, x86_64: installed`
- [ ] Verify module loaded: `lsmod | grep snd_hda_codec_cs420x`
- [ ] Verify built-in speakers work (not just headphone jack) — test `speaker-test -c 2`
- [ ] Test microphone input (internal mic)
- [ ] Check audio after suspend/resume
- [ ] Verify WirePlumber softvol rule active: `pw-dump | grep soft-mixer` → `api.alsa.soft-mixer=true` on `alsa_card.pci-0000_00_1f.3`; speaker volume slider actually changes volume

### Audio power/idle counters (D4, 2026-09-28)
- [ ] Controller runtime PM: `cat /sys/bus/pci/devices/0000:00:1f.3/power/runtime_status` → `suspended` at idle (TLP power_save=1, 1s timeout)
- [ ] Codec power state: `grep -A2 "Power:" /proc/asound/card0/codec#0` → D3 + clock gate at idle
- [ ] TLP audio params active: `cat /sys/module/snd_hda_intel/parameters/power_save` → 1; `power_save_controller` → Y (TLP 1.9.1 defaults)
- [ ] Jack wakeups at idle: `cat /proc/interrupts | grep -i hda` delta over 60 s → expect 0
- [ ] PipeWire graph idle: `pw-top` 5 s observation → no RUNNING nodes with zero streams; `pgrep -af "mv-control|mv-voice"` → empty
- [ ] Softvol rule active: `pw-dump | grep soft-mixer` → api.alsa.soft-mixer=true on alsa_card.pci-0000_00_1f.3; speaker volume slider actually changes volume
- [ ] power_save A/B: battery discharge rate with SOUND_POWER_SAVE_ON_AC=0 vs =1 (TLP conf) — keep =1 only if no glitches AND idle power lower
- [ ] Audio glitch check: low-volume playback, listen for pops/clicks ~1 s after silence (power_save=1 can pop on some codecs)
- [ ] Jack switching during playback: plug/unplug → stream follows, no speaker bleed, no crash
- [ ] Suspend/resume: audio survives `systemctl suspend` → resume (logind hooks)

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

### ISO diagnostic tools (KEEP reasons, C2 P1-O1/O2 verify-first)
These packages were candidates for removal but are KEPT because HW
procedures or active code reference them:
- `intel-gpu-tools` — `intel_gpu_top` is the GPU-usage metric source in
  the HW_BROWSER_MATRIX.md 4-mode validation plan (also DEPENDENCY_AUDIT.md:21)
- `powertop` — idle power draw measurement (read-only; DECISIONS.md:566)
- `turbostat` — used by tools/diagnostics/mv-power.sh, mv-thermal.sh, mv-collect.sh
- `ethtool` — `ethtool -S wlan0` HW counters in DRIVER_OPTIMIZATION_CANDIDATES.md
- `dmidecode` — MacBook10,1 revision confirmation + mv-collect.sh
- `mesa-utils` — GPU bring-up debug tooling (DEPENDENCY_AUDIT.md:21)
- `less` — man-db hard dependency; `diffutils` — mkinitcpio hard dependency;
  `hdparm` + `usbutils` — tlp hard dependencies (pacman -Si verified)
- `stress-ng` — mv-thermal.sh (C1-P1 precedent)
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
- [ ] **Window chrome fidelity — SSD (xfwm4) windows:**
  - [ ] Thunar: traffic lights with Mavericks gradients + symbols (X/–/+), hover/pressed states work
  - [ ] Mousepad: traffic lights with Mavericks gradients + symbols, all button states functional
  - [ ] xfce4-terminal: traffic lights with Mavericks gradients + symbols, all button states functional
  - [ ] Galculator: traffic lights with Mavericks gradients + symbols
  - [ ] Evince: traffic lights with Mavericks gradients + symbols
  - [ ] gThumb: traffic lights with Mavericks gradients + symbols
  - [ ] All xfwm4-decorated windows: frame pieces (titlebar gradient, corners, borders) render correctly
- [ ] **Window chrome fidelity — CSD (GTK HeaderBar) windows:**
  - [ ] gnome-disks: HeaderBar traffic lights with :hover/:active/:focus states
  - [ ] seahorse (Keychain): HeaderBar traffic lights with :hover/:active/:focus states
  - [ ] gnome-font-viewer: HeaderBar traffic lights with :hover/:active/:focus states
  - [ ] gcolor3: HeaderBar traffic lights with :hover/:active/:focus states
  - [ ] mv-* apps (mv-activity, mv-notes, mv-calculator, etc.): HeaderBar traffic lights with :hover/:active/:focus states
- [ ] **Window state behaviors:**
  - [ ] Maximized windows: titlebar buttons still functional, frame border removed
  - [ ] Minimized windows: Dock indicator shows correctly
  - [ ] Inactive windows: titlebar dimmed, buttons dimmed
  - [ ] Dialog/modal/transient/utility: appropriate frame styling
- [ ] **Keyboard/mouse interaction:**
  - [ ] Click traffic lights: Close/Minimize/Zoom work correctly
  - [ ] Double-click titlebar: maximize/restore (xfwm4 default)
  - [ ] Drag titlebar: move window
  - [ ] Drag edges/corners: resize window
  - [ ] Alt+Tab: window switching with previews
  - [ ] Super+Arrows: tiling (left/right/up/down)
  - [ ] Super+Alt+Arrows: workspace switching
- [ ] Wallpaper: mavericks-desktop.png (2304×1440) displays correctly
- [ ] File chooser: pathbar buttons + column headers visible
- [ ] Dialogs: dialog-action-area button styling visible
- [ ] Context menus: frosted-glass menu look

### Icon Theme — hardware validation (2304×1440)
- [ ] All 28 core Mavericks app icons render correctly at 2304×1440 (HiDPI 2x scaling)
- [ ] Finder icon (smiling face) appears correctly in Dock/panel/Thunar
- [ ] Folder icon (manila with tab) appears correctly in Thunar sidebar/tree/grid
- [ ] Trash (empty/full) renders correctly with paper texture in Dock and Thunar
- [ ] System Settings (gear), Activity Monitor (chart), Disk Utility (drive) appear with correct Mavericks styling
- [ ] Launchpad grid icon (view-app-grid) renders correctly in Dock and app menu
- [ ] Places icons (user-trash, user-trash-full, user-home, user-desktop) appear in Thunar sidebar
- [ ] Device icons (drive-harddisk, computer, video-display) appear in Thunar sidebar
- [ ] Mimetype icons (text, image, audio, video, archive, pdf) render in Thunar/file chooser
- [ ] Emblem icons (favorite, readonly, system, documents, photos, music, videos) overlay correctly
- [ ] Toolbar/action icons (new-folder, edit-copy, edit-paste, go-up, etc.) render in Thunar/GTK dialogs
- [ ] Symlinked standard icons (gnome-*, evince, eog, rhythmbox, gedit, seahorse, etc.) resolve correctly via Mavericks→hicolor→Adwaita chain
- [ ] SVG scalable icons scale cleanly at all sizes (16-512) without pixelation on 2304×1440 panel

### Cursor Theme — hardware validation (2304×1440)
- [ ] left_ptr (classic Mac arrow) appears with correct hotspot (0,0) and shadow
- [ ] hand1/hand2 (pointing hand) appears on links/buttons with correct hotspot
- [ ] text/xterm (I-beam) appears in text fields with correct hotspot
- [ ] crosshair/cross appears in graphics apps with correct hotspot
- [ ] watch/wait (spinning beach ball) animates smoothly during app launch/load
- [ ] sb_h_double_arrow/ew-resize appears on horizontal resize edges
- [ ] sb_v_double_arrow/ns-resize appears on vertical resize edges
- [ ] Corner resize cursors (nwse, nesw, nw, ne, sw, se) appear on window corners
- [ ] move/all-scroll appears during drag operations
- [ ] All cursors render at correct HiDPI scale (2x) without blur on 2304×1440 panel
- [ ] Cursor hotspots align correctly with visual center on Retina display
- [ ] Cursor theme inherits from Adwaita for missing cursors (no gaps)

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

## Finder Quick Look Space Binding — hardware validation
- [ ] Super+Shift+Space in Thunar copies selection to clipboard and opens mv-quicklook with selected files
- [ ] **Native Space binding limitation**: Thunar does not support binding Space key to custom actions without a C/Vala plugin (ThunarX). Current workaround uses Super+Shift+Space. A native Thunar plugin would be required for true Space-key Quick Look integration (investigate thunarx-python or Vala plugin for future).
- [ ] UCA context menu "Quick Look" works (right-click → Quick Look)
- [ ] mv-quicklook on image/PDF/text/office/audio/video — multi-file nav (←/→/Space/Home/End/PgUp/PgDn), fullscreen (F), Open button work
- [ ] Preview selection grid (G key / headerbar button) — thumbnail grid for multi-file selection, Enter/Space to preview, Esc to cancel
- [ ] PDF preview via poppler-glib renders first page on 2304x1440
- [ ] Media files show metadata via ffprobe (duration, bitrate, resolution, codecs, audio channels, subtitles)
- [ ] Extended format support: HEIC, AVIF, TIFF images; DOC/DOCX/ODT/RTF office docs (metadata + Open handoff); Opus, M4V, TS, MTS video
- [ ] Focus-out auto-close behavior (500ms delay) matches Mavericks sheet feel under real xfwm4
- [ ] HiDPI rendering: thumbnails, grid, text preview, media metadata grid at 2304×1440 (2x scaling)
- [ ] Clipboard grab reliability on real Thunar/xfwm4 — multi-select paste, special chars in filenames
- [ ] Keyboard navigation feel: Space for next, arrows, Home/End, PgUp/PgDn, G for grid, F fullscreen, Esc close

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
- [ ] Launchpad: Super+Shift+L открывает mv-launchpad-edit GTK3 диалог для перетаскивания/переупорядочивания приложений; drag-and-drop и Ctrl+↑/↓ работают; изменения сохраняются в positions.json и отражаются в Launchpad после закрытия
- [ ] Launchpad: Mavericks-style page dots (●○○) отображаются корректно на 2304×1440; переключение страниц Left/Right/PgUp/PgDn обновляет dots
- [ ] Launchpad: "Edit Launchpad…" запись в сетке (page 0, не в поиске, не в папке) запускает mv-launchpad-edit; запись скрывается при поиске/внутри папки

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

## Fresh-ISO hardware checklist (Phase D7 refresh, 2026-09-28)

### Boot chain validation (D7 audit — all CORRECT pre-hardware)
- [ ] **systemd-boot menu appears** → select "MavLinOS (linux-zen)" (default entry, timeout 3s)
- [ ] **Cmdline correct:** `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0` visible in `journalctl -k` or `/proc/cmdline`
- [ ] **Fallback entry works:** reboot, select "MavLinOS (linux-zen fallback)" → boots successfully
- [ ] **mkinitcpio modules loaded:** `lsmod | grep -E "applespi|spi_pxa|intel_lpss"` → all 4 modules present
- [ ] **No encrypted root:** confirm no `encrypt` hook needed (btrfs root, no LUKS)
- [ ] **zram active:** `zramctl` → zram0 with zstd, size = RAM/2
- [ ] **TLP active:** `systemctl status tlp` → active
- [ ] **fstrim timer:** `systemctl status fstrim.timer` → active (enabled by firstboot)
- [ ] **plocate timer:** `systemctl status plocate-updatedb.timer` → active (enabled by firstboot)

### Live ISO boot
- [ ] Boot mavlinos-*.iso on MacBook10,1 via USB-C (write with dd or balenaEtcher)
- [ ] airootfs loads → archiso hook runs → /run/archiso/bootmnt mounted
- [ ] lightdm starts → Xfce session starts → Mavericks theme applies (panel, wallpaper, GTK theme name)
- [ ] Spot-check: panel visible, wallpaper set, gtk theme = Mavericks (xfconf-query -c xsettings -p /Net/ThemeName)

### Installed system first boot
- [ ] Run `mavericks-firstboot.sh` as root → all 8 steps complete
- [ ] Reboot → systemd-boot menu → select "MavLinOS (linux-zen)"
- [ ] lightdm starts → Xfce session starts → Mavericks theme applies
- [ ] **NetworkManager:** `systemctl status NetworkManager` → active; Wi-Fi scan works
- [ ] **Bluetooth:** `systemctl status bluetooth` → active (if enabled)
- [ ] **Audio:** `pactl info` → PipeWire running; `wpctl status` → sinks present
- [ ] **Desktop:** panel, dock (plank), wallpaper all visible
- [ ] **First app:** open Finder (Thunar) → Mavericks theme applied
- [ ] **Spotlight:** Super+Space → overlay appears (after plocate-updatedb.timer runs)

### Hardware validation (from previous phases)
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

---

## Network (NM userspace path) — hardware validation (Phase D2, 2026-09-28)

Pre-hardware state: NM 1.58.1 + wpa_supplicant 2.12 + iwd 3.12 audited from source;
active backend = wpa_supplicant (pinned); connectivity check disabled; mv-control
`--rescan no` applied. Remaining items are HW-only (no BCM43602 on host):

- [ ] **NM scan wakeup measurement** (DRIVER_OPTIMIZATION_CANDIDATES.md §5.1):
      idle-connected interrupt rate; confirm NO 30s scan spikes with Control Center
      open (D2 fix); explicit Refresh = one scan; disconnected = NM periodic 3s→120s
      backoff; connected = scan suppressed (supplicant bgscan). Counters:
      `/proc/interrupts` (brcmf_pcie_intr), `iw dev wlan0 survey dump`, powertop.
- [ ] **Backend A/B** (DRIVER_OPTIMIZATION_CANDIDATES.md §5.2): wpa_supplicant vs
      iwd on BCM43602 — idle wakeups, scan, roaming, powersave, SAE, suspend/resume.
      Adopt iwd only if measurable wakeup/energy win AND no feature regression.
- [ ] **Powersave lever** (DRIVER_OPTIMIZATION_CANDIDATES.md §5.3): measure idle
      wakeups with default (`ignore` → firmware default) vs `[connection]
      wifi.powersave=3` (PM_FAST). Adopt only if wakeups drop AND no
      disconnects/latency regression (D1 hypothesis O6 — PM_FAST stability unverified).
- [ ] **Connectivity check off — confirm no regression**: with `enabled=false`,
      confirm NM still connects/resumes normally and no captive-portal false-negative
      matters (we don't rely on portal detection). Confirm no NM errors in journal.
- [ ] **Supplicant D-Bus chatter**: `dbus-monitor` on `fi.w1.wpa_supplicant1` during
      idle — confirm no periodic control-interface polling (event-driven expected).
- [ ] **iwd not active on installed system**: confirm `systemctl status iwd` = inactive
      and NM uses wpa_supplicant (`nmcli dev wifi` works, `journalctl -u NetworkManager`
      shows supplicant backend).

---

## Display (i915) — hardware validation (Phase D3, 2026-09-28)

Pre-hardware state: i915 display path audited from source (RUNTIME_COMPONENT_MAP.md §5,
RUNTIME_SOURCE_AUDIT.md §D3, DRIVER_AUDIT.md §D3). Baseline judged (DECISIONS.md D3).
Remaining items are HW-only (no HD 615 panel on host):

- [ ] **PSR on/off A/B** (DRIVER_OPTIMIZATION_CANDIDATES.md §6.1): idle power with
      `i915.enable_psr=0` vs `=1`; PSR status via `/sys/kernel/debug/dri/0/i915_edp_psr_status`;
      flicker test (cursor bottom quarter, 5 min); DC state via `/sys/kernel/debug/dri/0/i915_dc_state`.
      Adopt PSR on only if no flicker AND idle power drops.
- [ ] **ASPM A/B** (DRIVER_OPTIMIZATION_CANDIDATES.md §6.2): idle power with
      `pcie_port_pm=off` vs without; resume test (`systemctl suspend` → resume →
      `dmesg | grep nvme`); pm_test matrix. Keep `pcie_port_pm=off` if resume fails
      without it (confirms F13).
- [ ] **Resume-cycle matrix** (DRIVER_OPTIMIZATION_CANDIDATES.md §6.3): 8-row matrix
      (s2idle/deep × pcie_port_pm on/off × enable_psr on/off). Each row: reboot →
      suspend → resume → check NVMe + display. Record in BENCHMARKS.md.
- [ ] **xfwm4 compositor settings** (DRIVER_OPTIMIZATION_CANDIDATES.md §6.4): tearing
      test with `vblank_mode=off` vs `=on`; PSR interaction check. Keep `vblank_mode=off`
      if no tearing AND PSR entry improves.
- [ ] **Backlight PWM** (DRIVER_OPTIMIZATION_CANDIDATES.md §6.5): brightness range,
      dim/bright test, low-brightness flicker check. Consider `invert_brightness` quirk
      if PWM flicker at low brightness.
- [ ] **DMC firmware**: confirm `i915/kbl_dmc.bin` loads (`dmesg | grep dmc`) and
      DC5/6 entry works (`cat /sys/kernel/debug/dri/0/i915_dc_state`).
- [ ] **FBC status**: confirm FBC active (`cat /sys/kernel/debug/dri/0/i915_fbc_status`)
      and no underruns (`dmesg | grep -i underrun`).
- [ ] **Forcewake**: confirm no forcewake leaks (`cat /sys/kernel/debug/dri/0/i915_forcewake_count`
      returns to 0 after idle).

---

## INPUT (Apple SPI / HID) — hardware validation (Phase D5, 2026-09-28)

Pre-hardware state: applespi driver audited from source (RUNTIME_COMPONENT_MAP.md §9,
RUNTIME_SOURCE_AUDIT.md §D5, DRIVER_AUDIT.md §D5). 3-strategy best-effort limit.
External USB-C HID is the mandatory bring-up interface.

### External USB-C input (MANDATORY — bring-up first)
- [ ] Verify USB-C hub + keyboard/mouse works out of box
- [ ] Test all keyboard shortcuts (Super+Space, Super+L, Super+Tab, etc.)
      — 55 managed bindings; full table in `docs/KEYBOARD.md`, source of
      truth `lib/mv_hotkeys_core.py`. On hardware: (a) `mv-hotkeys verify --live`
      must be clean, (b) `mv-hotkeys-gui` recorder must capture real keypresses
      (Force Touch trackpad has no `key-press-event` path, so recording needs
      the external keyboard), (c) confirm Super+Fn row maps volume/brightness
      XF86 keysyms on this firmware, (d) confirm a rebind survives logout/login
      and `xfsettingsd` restart.
- [ ] Test trackpad multitouch (two-finger scroll, tap-to-click)
- [ ] Test media keys (XF86AudioRaiseVolume, XF86AudioLowerVolume, XF86AudioMute)
- [ ] Test USB-C power delivery while using hub
- [ ] Verify USB keyboard can wake system from suspend

### Internal keyboard/trackpad (applespi) — BEST EFFORT, limit 3 strategies
- [ ] **Strategy A**: Install macbook12-spi-driver-dkms (AUR) on linux-zen
  - [ ] Check `lsmod | grep applespi` — driver loaded
  - [ ] Check `dmesg | grep applespi` — no timeout errors
  - [ ] Test keyboard input (`evtest /dev/input/eventXX`)
  - [ ] Test trackpad input (`evtest /dev/input/eventYY`)
  - [ ] If timeouts → Strategy A failed, try Strategy B
- [ ] **Strategy B**: linux-zen with applespi patches from linux-macbook kernel
  - [ ] Apply patches, rebuild kernel
  - [ ] Check `dmesg | grep applespi` — no timeout errors
  - [ ] Test keyboard + trackpad input
  - [ ] If timeouts → Strategy B failed, try Strategy C
- [ ] **Strategy C**: Try linux-lts or different kernel version
  - [ ] Install linux-lts
  - [ ] Check `dmesg | grep applespi` — no timeout errors
  - [ ] Test keyboard + trackpad input
  - [ ] If timeouts → all 3 strategies failed, mark as "not supported on this revision"
- [ ] Document which strategy (if any) works
- [ ] If all 3 fail → mark as "not supported on this revision"

### SPI timeout dmesg matrix (per strategy)
- [ ] Strategy A: `dmesg | grep -i "Error reading from device\|Error writing to device"` → count
- [ ] Strategy B: same
- [ ] Strategy C: same
- [ ] Record in BENCHMARKS.md

### Input power/idle counters (D5)
- [ ] GPE status: `cat /proc/interrupts | grep -i gpe` → GPE line (if visible)
- [ ] Input devices: `libinput list-devices | grep -A5 "Apple SPI"` → keyboard + touchpad
- [ ] Touchpad capabilities: `cat /sys/class/input/event*/device/name` → Apple SPI Touchpad
- [ ] libinput accel: `libinput measure touchpad-pressure` (if available) → pressure range
- [ ] Suspend/resume: `systemctl suspend` → resume → `dmesg | grep applespi` → messages
- [ ] Wake from suspend: Close lid → open lid → `dmesg | grep -i wake` → wake source

---

## STORAGE (Apple S3X NVMe) — hardware validation (Phase D5, 2026-09-28)

Pre-hardware state: S3X NVMe audited from source (RUNTIME_COMPONENT_MAP.md §10,
RUNTIME_SOURCE_AUDIT.md §D5, DRIVER_AUDIT.md §D5). `pcie_port_pm=off` workaround
documented. LKML thread open (Sep 2026).

### S3X NVMe basic validation
- [ ] `lspci -nn | grep -i nvme` → 106b:2003
- [ ] `nvme list` → /dev/nvme0n1
- [ ] `nvme smart-log /dev/nvme0` → temperature, power state, data written
- [ ] `cat /sys/bus/pci/devices/0000:00:1c.0/power/runtime_status` → active (with pcie_port_pm=off)
- [ ] `cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status` → active
- [ ] `cat /sys/bus/pci/devices/0000:01:00.0/power/aspm` → L0s/L1 enabled

### S3X NVMe resume validation
- [ ] `systemctl suspend` → resume → `dmesg | grep nvme` → no errors
- [ ] Root filesystem still writable after resume
- [ ] Repeat 5x — all resume clean
- [ ] If resume fails → confirms `pcie_port_pm=off` is required

### ASPM A/B test (battery cost of pcie_port_pm=off)
- [ ] Baseline (pcie_port_pm=off): measure idle battery discharge rate (10-min samples)
- [ ] Remove pcie_port_pm=off: edit kernel cmdline, reboot
- [ ] Test (pcie_port_pm=on): measure idle battery discharge rate (10-min samples)
- [ ] Resume test: `systemctl suspend` → resume → `dmesg | grep nvme` → check for errors
- [ ] If resume fails without pcie_port_pm=off → confirms F13 (S3X resume bug)
- [ ] Record in BENCHMARKS.md

### btrfs + SSD validation
- [ ] `btrfs filesystem show /` → subvol @
- [ ] `btrfs filesystem df /` → space usage
- [ ] `cat /proc/mounts | grep btrfs` → mount options
- [ ] `systemctl status fstrim.timer` → active (after enabling)
- [ ] `fstrim -av /` → TRIM completion
- [ ] `journalctl --disk-usage` → disk usage (should be 0 in volatile)

### zram validation
- [ ] `zramctl` → zram0 with zstd
- [ ] `cat /sys/block/zram0/comp_algorithm` → zstd
- [ ] No disk swap: `cat /proc/swaps` → only zram0

### Storage power/idle counters (D5)
- [ ] NVMe idle power: `nvme smart-log /dev/nvme0` → power state transitions (should be 0)
- [ ] PCIe idle power: `cat /sys/bus/pci/devices/0000:00:1c.0/power/runtime_status` → active
- [ ] Battery discharge rate at idle (10-min samples)
- [ ] Compare with/without pcie_port_pm=off

## ISO validation — hardware validation (Track 5/7, 2026-09-29)
- [ ] Boot ISO on real MacBook10,1 hardware (UEFI boot via systemd-boot)
- [ ] Verify ISO loads to live desktop (LightDM → Xfce with Mavericks theme)
- [ ] Verify mavericks-apps and mavericks-theme packages are installed in live system
- [ ] Verify macbook12-audio-driver is NOT installed (ISO-excluded by design)
- [ ] Verify sshd is disabled in live system (`systemctl is-enabled sshd` → disabled)
- [ ] Verify root is locked in live system (`passwd -S root` → L)
- [ ] Verify firstboot script works on installed system (applies baseline, enables services)
- [ ] Verify fstrim.timer and plocate-updatedb.timer are enabled after firstboot
- [ ] Verify snapshot hooks work on installed btrfs system
