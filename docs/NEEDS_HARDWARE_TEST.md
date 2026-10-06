# NEEDS_HARDWARE_TEST — Items requiring real MacBook10,1 hardware

## Dock (plank) visual + behavioural validation (phase dock-p0)
Behaviour is proven pre-hardware (real plank on Xvfb :97 — theme/zoom/icon-size
reach it, 8 pins, bottom-edge geometry, user customisation preserved), but the
*look* and the *feel* need the real 2304×1440 panel and the trackpad:
- [ ] Zoom feel: 150% magnification depth reads like macOS at 2x scaling (not too shallow, not overshooting the screen edge with 8 pins)
- [ ] Metallic shelf: FillStart/FillEnd gradient + hairline outer/inner stroke + TopRoundness=4 looks like a Mavericks Dock, not a Linux panel
- [ ] Running-indicator dots under pinned and un-pinned icons are legible and in the Mavericks accent; the Dock grows when an app launches and shrinks when it quits (pre-hardware this is proven with Openbox on Xvfb, 424→484→424 px — confirm with the real WM, xfwm4, since plank enumerates windows through WNCK/BAMF)
- [ ] Clicking a Dock icon switches to that application / raises its window (needs a real WM; not testable on bare Xvfb)
- [ ] Intelligent auto-hide: reveal on approach, hide when a maximised window covers the edge, no jitter at the screen edge
- [ ] Tooltips (app names) render in the Mavericks font/skin
- [ ] Trash docklet: icon present, count/label behaviour, click opens Thunar at Trash, right-click offers Empty Trash
- [ ] Mission Control pin launches the window overview (`mv-mission-control --native`) and the icon matches the window-overview look
- [ ] Force Touch trackpad: two-finger swipe up over the Dock does not fight auto-hide; click-through on the revealed Dock edge
- [ ] External USB-C input only until applespi lands: click/hover/scroll behaviour of the Dock with an external mouse
- [ ] Energy: measure the always-on cost of the Dock on battery (plank idle CPU + the one-shot `mv-dock-config` seeding per login) before adding anything else to the baseline

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
- [ ] Menu bar: menu-bar gradient + translucent look from `_panel.scss` (`.panel-1` window + `.xfce4-panel` plug windows) on the real panel
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

## Context Menus — hardware validation (phase contextmenus-p0)
- [ ] Thunar right-click context menu renders with Mavericks theme (frosted-glass background, rounded corners, separator styling) on 2304×1440
- [ ] All 17 uca.xml actions appear in correct order in context menu (Quick Look → Put Back → New Folder → Get Info → Open With → Rename → Move to Trash → Copy Path → Go to Path… → Compress → Open in Terminal → Eject → AirDrop → ytplayer → Search → Columns → Empty Trash)
- [ ] Icons resolve via Mavericks→Adwaita inheritance for all actions (preview, edit-undo, document-new, dialog-information, document-open, edit-rename, user-trash, edit-copy, document-open-recent, package-x-generic, utilities-terminal, media-eject, airdrop, mpv, edit-find, format-justify-fill, user-trash-full)
- [ ] Move to Trash (mv-trash) moves selection to GVfs trash; trash-cli restore works via Put Back
- [ ] Copy Path copies absolute path(s) to clipboard; newline-joined for multi-select; pasteable in terminal/editor
- [ ] Go to Path… reads path from clipboard, opens directory or selects file in Thunar
- [ ] Quick Look (mv-quicklook-thunar) via Super+Shift+Space copies Thunar selection to clipboard and opens preview
- [ ] Keyboard accelerators in context menu (if any) do not conflict with xfwm4/global shortcuts on real session
- [ ] Submenu behavior (if nested menus added later) works with trackpad/mouse on real hardware
- [ ] Energy: context menu population is instant (no measurable delay) on fanless Core M

## Global Dialogs — hardware validation (phase dialogs-p0)
- [ ] Alert look on real panel: 64px alert icon size, `.mavericks-alert` background, action-area button metrics (min-width 90px, aqua `suggested-action` default, `destructive-action` red) at 2304×1440 HiDPI
- [ ] `entry_dialog()` visual: message + entry + inline validator hint spacing/coherence with alert chrome on HiDPI
- [ ] SheetDialog attached geometry under real xfwm4: flush under parent title bar, parent-width match, square top corners, 12-frame ease-down slide smoothness on the real GPU/compositor path
- [ ] SheetDialog parentless fallback: centered on the real screen (Xvfb has no WM; real placement only verifiable in session)
- [ ] Keyboard contract on real input devices: Escape=cancel and Enter=default in alerts, entry dialogs and sheets, with focus landing on the entry (input surfaces) / default button (plain alerts) — external USB-C keyboard first, applespi best-effort later
- [ ] Destructive confirms read correctly at default zoom (Cancel default in confirm_delete, rightmost aqua default elsewhere)

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
---

## Menu Bar + Application Menu — hardware validation (phase menubar-p0, 2026-10-06)

Everything below is a *rendering / interaction* item that the build container
structurally cannot decide (see `docs/DECISIONS.md` D1–D9). The container smoke
(`scripts/test-panel-menubar-gui.sh`) proves only: the panel maps, it sits on the
**top** edge (`1680x25+0+0`), the config is accepted verbatim (no xfconf
migration), the `mv-apple` module is discovered and `construct()`ed, and zero
host-display leakage occurred.

### Menu bar geometry and typography
- [ ] Panel is on the **top** edge on the real 2304×1440 panel (`p=11`), not the bottom
- [ ] 24px bar: menu-bar text legible at 100% and at any HiDPI scale factor
- [ ] Clock renders **"Tue Oct 6 3:45 PM"** on one line, in Lucida Grande 11 (not 8pt Sans)
- [ ] Clock does not wrap/truncate at 24px across a full month of date strings (e.g. "Tue Sep 30", long month names)
- [ ] Clock tooltip shows the full date (`Tuesday, October 6, 2026`)
- [ ] Menu-bar gradient from `_panel.scss` reads as one continuous bar; plug windows are transparent (no seams between items)
- [ ] Systray / power-manager items sit right-aligned and read as part of the same bar

### Apple menu (`mv-apple`)
- [ ] Opens on click; no tear-off arrow; mnemonics underlined (macOS underlines the first letter)
- [ ] Items in Mavericks order with the four separators in the right places
- [ ] Accelerator glyphs render and are not tofu boxes: `⌥⌘⎋` Force Quit, `⇧⌃⌘Q` Lock Screen (needs a font covering U+2325/U+2318/U+238B — check the fallback on the real system)
- [ ] Keyboard: arrows + first-letter mnemonics + Enter + Escape all work; Escape closes without launching
- [ ] **Sleep / Restart… / Shut Down… / Log Out…** open the `mv-power-ui` Mavericks alert (60 s countdown, battery footer, Cancel/Escape abort) — *not* an instant `systemctl` action
- [ ] Restart/Shut Down respect polkit auth if prompted
- [ ] `About This Mac`, `System Preferences…`, `Recent Items`, `Force Quit…`, `Lock Screen` all launch

### Application menu (vala-panel-appmenu)
- [ ] With `vala-panel-appmenu` + `appmenu-gtk-module` installed, a native app (e.g. `mv-settings`) exports its menus: **bold app name first** (macOS app menu), then File / Window / Help
- [ ] Menus are populated from the running app and update when focus moves between apps
- [ ] Non-GTK apps (Firefox) do **not** appear — record the resulting incoherence honestly
- [ ] `Window ▸ Minimize / Zoom / Close Window` act on the app's window from the menu bar
- [ ] Menu-bar item font matches Lucida Grande 11 and the item highlight matches the `.xfce4-panel button:hover` rule

### Known-unreachable on Xfce 4.20 (do NOT treat as a bug to fix)
- [ ] macOS **window buttons** right of the app menus — not expressible with the appmenu plugin
- [ ] **Ctrl+F2** menu-bar keyboard focus — not expressible without a session-resident `XGrabKey` daemon (see D7)


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
- [ ] mv-quicklook on image/PDF/text/audio — multi-file nav (←/→/Space), fullscreen (F), Open button work
- [ ] PDF preview via poppler-glib renders first page on 2304x1440
- [ ] Media files show metadata via ffprobe

## Thumbnailer — config gap (decision: no new daemon)
- [ ] tumbler is absent from the ISO package list; thunarrc requests
      thumbnails (`MiscThumbnailMode=ALWAYS`, `MiscShowThumbnails=TRUE`)
      but no backend serves them. Adding tumbler = resident daemon;
      deferred by phase-C decision (power baseline frozen). On hardware:
      decide tumbler vs ffmpegthumbnailer-only vs thumbnails-off, then
      verify Thunar icon-view thumbnails appear without measurable
      idle CPU cost

## Phase 3+ — app validation (source-уровень готов в 0.8–0.15)
- [ ] Preview: открыть PDF через mv-preview на панели 2304x1440 — multi-page nav (arrows, Home/End), thumbnail sidebar click, fullscreen (F), Open button, markup toolbar visible
- [ ] Preview: PDF render path на реальном железе (Cairo `page.render()` + `Gdk.pixbuf_get_from_surface`; старый `render_to_pixbuf` API удалён из poppler — на текущем poppler-glib PDF раньше не открывался вообще)
- [ ] Preview: открыть image (PNG/JPG/TIFF) через mv-preview — render, fullscreen, multi-file nav (Ctrl+arrows)
- [ ] Preview: markup tools на тачпаде/мыши — Rect/Oval/Arrow/Sketch drag, Text click+dialog, свотчи цвета, Thin/Medium/Thick, Ctrl+Z undo; markup не смещается после zoom (±/0/Ctrl+scroll) и rotation (r/R)
- [ ] Preview: fit-width (w) на реальной панели; zoom 0.2–5.0 без лагов на fanless Core M
- [ ] Preview: rotation r/R — per-file, переживает смену страницы, Export-as-PNG запекает поворот
- [ ] Preview: Export as PNG… (Ctrl+E) — SAVE dialog, overwrite confirm, PNG содержит page+markup+rotation; исходный файл не изменяется
- [ ] Preview: текстовые файлы (.txt/.md/.log/.csv/.conf) открываются read-only monospace, markup toolbar скрыта
- [ ] Preview: MIME default binding НЕ настроено (mimeapps.list — зона интеграции/firstboot): double-click PDF/image в Thunar сейчас открывает NOT mv-preview; после настройки дефолта — перепроверить
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
- [ ] Per-entry ✕ dismiss removes exactly that notification and the list updates without flicker
- [ ] Delete/BackSpace dismisses the selected entry after Down/Up seeds the cursor
- [ ] Enter activates a notification carrying a URL or desktop-entry hint (xdg-open / app launch)
- [ ] Urgency accent dot is visible for critical/low entries and absent for normal ones
- [ ] DND toggle in header syncs with xfce4-notifyd
- [ ] Banner notifications appear top-right with Mavericks theme (rounded, translucent)
- [ ] Urgency colors (low/normal/critical) render correctly on 2304x1440
- [ ] Keyboard navigation (arrows, Enter, Delete, Escape) works
- [ ] Ordering is newest-first after a restore of a history file that is not chronologically sorted
- [ ] Focus-out auto-close works

## Screenshot — hardware validation
- [ ] Super+Shift+3 captures fullscreen to ~/Pictures/Screenshots
- [ ] Super+Shift+4 captures region to clipboard
- [ ] Super+Shift+5 captures region to file
- [ ] Post-capture preview dialog appears with thumbnail and actions
- [ ] "Open in Preview" launches mv-preview with the markup toolbar (Rect/Oval/Arrow/Sketch/Text now real, not stubs)
- [ ] "Show in Finder" opens Thunar with file selected
- [ ] "Move to Trash" moves file to GVfs trash
- [ ] Preview dialog auto-closes after configurable timeout
- [ ] Config file (~/.config/mv-shot/config.ini) controls save_dir, show_preview, preview_timeout, copy_to_clipboard
- [ ] Recording (--record) works via ffmpeg x11grab, CPU/power acceptable on m3-7Y32
- [ ] Error handling: graceful degradation if xfce4-screenshooter/ffmpeg missing
- [ ] Visual validation: preview dialog renders correctly on 2304×1440 panel

## Disk Utility — hardware validation
(pre-HW coverage: 250 headless tests against a mock UDisks2 service + real-widgets
GUI smoke on pinned Xvfb :97; listed below is ONLY what needs the machine)

- [ ] mv-diskutil launches from .desktop / app menu and shows the internal Apple SSD in the sidebar (Internal group)
- [ ] Apple S3X appears as ConnectionBus=nvme → S3X NVMe section shown, reading REAL `/sys/class/nvme/nvme0` (model `APPLE SSD SM0256*`, firmware_rev, serial, state=live, critical_warning=0) and hwmon `temp1_input`; compare against `nvme smart-log /proc/partitions`
- [ ] S3X critical-warning bit: no NVMe health warnings reported on a healthy drive; verify a failing bit would render red (cannot be induced safely on the target SSD)
- [ ] Capacity bar shows real used/free values (statvfs) for the mounted root volume
- [ ] First Aid shows real S.M.A.R.T. status (Verified) + temperature + power-on time for the internal SSD; smartctl cross-check
- [ ] Mount of the boot volume from the UI works (UDisks2 polkit: allowed for an active local session)
- [ ] Unmount confirmation dialog appears for the real root volume; cancel must change NOTHING
- [ ] Eject of a USB stick works via the UI; confirmation dialog names the disk and any mounted volume count
- [ ] Busy-device error: open a file on a USB stick, unmount → "The Disk Is Busy" alert (NOT raw GDBus text); close file, retry succeeds
- [ ] Polkit denial path: cancel the auth prompt during unmount → "Authorization Cancelled", volume untouched
- [ ] Erase gate on real media: a mounted stick shows the "Erasing is unavailable: the volume is mounted" note and NO Erase button; an unmounted stick offers Erase; the typed-name confirmation is required; wrong name erases nothing
- [ ] Erase actually works on throwaway media only (NEVER the internal S3X): exfat/exFAT-cross-platform check from another machine; verify the polkit prompt appears once
- [ ] Hot-plug: insert a USB stick → appears in the External group via the D-Bus signal with no manual refresh; remove it → row disappears
- [ ] Multi-mount-point volume (e.g. bind mounts) renders its full comma-joined mount list without crashing
- [ ] Whole-disk ("superfloppy") stick appears under OTHER VOLUMES, not silently missing
- [ ] UDisks2 not-available empty state is NOT shown on a normal boot (service present)
- [ ] Right-click context menu on sidebar rows: Mount/Unmount/Erase…/First Aid, and Eject on the drive row
- [ ] Ctrl+R refresh, Delete=eject/unmount, Escape=deselect (window must NOT quit) on the real keyboard
- [ ] Show in Finder opens Thunar at the mount point
- [ ] GNOME Disks fallback button launches gnome-disks from the no-UDisks2 empty state
- [ ] Visual validation: sidebar/detail/First Aid/Erase sheet render correctly on 2304×1440 panel; sidebar row contrast + ellipsize at 250px
- [ ] Format/partition fallback note: launching gnome-disks from terminal works for destructive ops
- [ ] Energy: idle CPU ~0 between interactions (confirm the ObjectManager signal does not wake the app); app memory after 10 min idle

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

## Visual demo follow-ups (2026-10-06, from scripts/demo)
 
- [ ] xfdesktop wallpaper: xfdesktop 4.20.2 ignored every /backdrop xfconf
      property layout tried under Xvfb (monitor0 / monitorVNStr /
      monitor<connector> / single-workspace-mode); the demo harness falls
      back to `feh --bg-fill`. On real hardware verify that the skel's
      xfce4-desktop.xml backdrop properties (monitor0 paths) actually apply
      with the panel's real connector name; if not, the product needs a
      backdrop-path migration to the live connector name.
- [ ] Desktop right-click menu: verify menu.xml loads and all items work —
      Change Wallpaper (zenity file chooser → xfconf), New Folder (mv-newfolder),
      Clean Up (icon re-layout), Sort By submenu (Name/Kind/Date/Size/None/Snap),
      Paste (clipboard file URIs → ~/Desktop), Show Desktop.
- [ ] Desktop icon grid: verify 64px icons, sort by name ascending, snap-to-grid
      behavior on real 2304×1440 panel; Home/Trash/removable icons visible and
      functional (click opens Thunar, right-click offers Empty Trash for Trash).
- [ ] Traffic-light side consistency: headerbar apps follow the
      Gtk/DecorationLayout xsetting (demo override set it to
      `close,minimize,maximize:` = left); confirm the skel xsettings.xml
      gains the same DecorationLayout so all windows match xfwm4's CHM|.
- [ ] Launchpad icon resolution on the real session (full icon theme set);
      in the demo container the rofi grid rendered text-only.
 
## Activity Monitor — hardware validation (OS-activity-p0, 2026-10-06)
 
- [ ] Per-process Energy Impact accuracy: correlate mv-activity %CPU categories
      (Very High/High/Moderate/Low/None) with actual RAPL package power
      readings on m3-7Y32 during sustained CPU loads
- [ ] Disk I/O counter rollover behavior: verify /proc/PID/io read_bytes/write_bytes
      do not wrap or reset unexpectedly on long-running processes (e.g., browser,
      compiler) over multi-hour sessions
- [ ] Renice permission behavior: confirm SIGKILL/renice dialogs correctly handle
      CAP_SYS_NICE; negative nice values (-20..-1) require root — test with
      real sudo/polkit setup on installed system
- [ ] Column rendering and sort behavior on 2304×1440 HiDPI panel: verify
      sortable column headers, right-aligned numeric columns, default sort by
      %CPU desc, Energy tab hidden %CPU sort, and search filter all render
      correctly at 2x scaling
- [ ] Process action dialogs (Quit/Force Quit/Renice/Inspect) appear correctly
      on the real display with Mavericks theme; confirm modal behavior,
      destructive-action button styling, and keyboard shortcuts (Enter/Escape)
- [ ] Network tab interface rates: verify RX/TX bytes/s from /proc/net/dev delta
      matches actual throughput on BCM43602 Wi-Fi and USB-C ethernet dongle
- [ ] Energy cost of open window: measure mv-activity idle CPU/wakeups with
      window open (2s refresh) vs closed; confirm zero cost when closed
      (no GLib timer, no background threads)
- [ ] Window geometry persistence: Activity Monitor window size/position
      restores correctly on relaunch in a real session

## System Information (About This Mac / System Report) — hardware validation (OS-sysinfo-p0, 2026-10-06)

- [ ] About This Mac window renders correctly on 2304×1440 HiDPI panel: sidebar labels, detail pane, Mavericks theme integration, window size (620×460), header bar with "System Report…" button
- [ ] System Report window opens on "System Report…" click: tabbed interface with Hardware, PCI Devices, USB Devices, Display, Storage, Network, Audio, Power, Software tabs (and MacBook Profile tab first when on MacBook10,1)
- [ ] MacBook Profile tab (MacBook10,1 only): shows Model Identifier (MacBook10,1), Model Name (MacBook Retina 12-inch Mid 2017), Processor Name/Speed/Cores/Caches, Memory, Boot ROM Version, SMC Version, Serial Number, Hardware UUID — all populated from DMI; verify no fake Apple data on non-Apple hardware
- [ ] Hardware tab: DMI/SMBIOS fields (BIOS Vendor/Version/Date, System Manufacturer/Product/Version/Serial/UUID, Board Name/Vendor/Version, Chassis Vendor/Type/Version) readable and correctly formatted
- [ ] PCI Devices tab: devices grouped by class (Graphics, Network, Storage, Multimedia, USB, Host Bridge, PCI Bridge) with address, description, vendor:device IDs; verify real Apple S3X NVMe and Intel GPU appear on MacBook10,1
- [ ] USB Devices tab: `lsusb -t` tree renders correctly; verify internal devices (keyboard/trackpad via applespi, Bluetooth, FaceTime camera) and external USB-C hub devices appear
- [ ] Display tab: xrandr current mode shows 2304×1440 @ 60Hz (or actual panel mode), xdpyinfo DPI shows ~226 DPI (2x scaling); verify connected output name (eDP-1) and available modes list
- [ ] Storage tab: NVMe section shows Apple SSD model (APPLE SSD SM0256*), firmware, serial; block devices (lsblk) show root filesystem; zram size = RAM/2 with zstd; mount points list all mounted volumes with fstype/options
- [ ] Network tab: PCI network device (BCM43602), interfaces (ip addr), routes, NetworkManager state; verify Wi-Fi interface appears and state transitions work
- [ ] Audio tab: ALSA cards (Cirrus codec), PCM devices, PipeWire/PulseAudio sinks; verify internal speakers and microphone appear after Cirrus driver install
- [ ] Power tab: Battery percentage/state/time-to-empty from UPower; TLP status; verify on battery vs AC behavior
- [ ] Software tab: OS (Mavericks Linux), Kernel, Architecture (x86_64), DE (Xfce 4 Mavericks), Display Server (X11), Init (systemd), Shell, Python version
- [ ] Copy Report button: copies entire report (About + all tabs + MacBook Profile) to clipboard as structured text; verify paste into TextEdit/terminal preserves formatting
- [ ] Tab sorting: Property/Value columns sortable by clicking headers; verify on 2304×1440
- [ ] Window geometry persistence: System Report window size/position restores on relaunch
- [ ] Energy cost: confirm zero idle cost when window closed (no timers, no daemons); measure CPU/wakeups with window open (on-demand reads only)

## Screenshot — hardware validation (OS-shot-p0, 2026-10-06)

- [ ] `Super+Shift+3/4/5` on the real keyboard: confirm xfce4-keyboard-shortcuts
      actually delivers them (xfwm4 + Xfce session, not bare Xvfb) and that the
      full-screen / region+clipboard / region bindings behave as on macOS.
      Pre-hardware these were only verified as registry + XML entries.
- [ ] Retina (2304×1440) capture fidelity: full-screen grab resolution, correct
      pixel dimensions in the saved PNG, and whether xfce4-screenshooter honours
      the HiDPI scale factor or returns a scaled-down buffer.
- [ ] Capture flash and countdown legibility on the real panel: a full-screen
      white flash at 2304×1440 on this display — visible, not a hard flicker.
- [ ] Thumbnail placement on the real screen: bottom-right anchor inside the
      panel work area, i.e. it must not collide with the xfce4-panel or the
      plank Dock, and must not be covered by either.
- [ ] Always-on-top behaviour under a real window manager: confirm the thumbnail
      and the tools bar keep EWMH `_NET_WM_STATE_ABOVE` above xfwm4 windows and
      are not dropped by the WM.
- [ ] Region drag-select on the built-in trackpad: applespi input is expected to
      be unavailable/best-effort (see HARDWARE.md), so region capture must be
      exercised with the external USB-C mouse AND, if applespi ever works, the
      Force Touch trackpad — a region drag is the one screenshot interaction that
      cannot be done from the keyboard.
- [ ] Timed capture accuracy end-to-end: with `-T 10`, confirm the shot lands
      ~10 s after the keypress including the drag time, i.e. the timer starts
      before region selection completes (macOS semantics).
- [ ] Clipboard round-trip (`-c`): confirm the image actually reaches the
      CLIPBOARD selection and pastes into an external app (Firefox / mousepad)
      under a real session; Xvfb has no clipboard owner.
- [ ] `Show in Finder` → `thunar --select` reveals the file in the real session
      and the selection highlight lands on it.
- [ ] `Move to Trash` → `trash-put` on a real capture: verify it lands in
      `~/.local/share/Trash` and that Thunar's Empty Trash / Put Back work on it.
- [ ] `Open in Preview` handoff: `mv-preview` must start and display the capture;
      the annotation toolbar is still a stub, so the edit path is NOT yet
      hardware-validated as a whole.
- [ ] Screen recording energy cost: `ffmpeg x11grab` with libx264 ultrafast on
      the fanless m3-7Y32 — measure CPU%, clock and battery discharge for a
      60 s recording. Recording stays EXPERIMENT and must not become a default
      until this is measured (DECISIONS.md §7 power baseline is frozen).
- [ ] Multi-monitor: window capture (-w) with an external USB-C/DP display
      attached — confirm the correct window is picked and the grab is not
      offset by the second monitor's coordinate origin.

## System Settings — hardware validation (OS-settings-p0, 2026-10-06)

- [ ] Pane rendering on the real 2304×1440 panel: ListBox row spacing,
      slider widths, icon-grid proportions and header typography at HiDPI
      (pre-hardware only Xvfb geometry could be checked, not visual
      fidelity).
- [ ] General pane against a live xfsettingsd: confirm theme / icon-theme
      / font writes via xfconf `xsettings` actually re-skin running apps
      (mv-control, Thunar, mv-settings itself) on a real session.
- [ ] Mission Control pane against live xfwm4: `workspace_count` writes
      must be honoured by the running WM and reflected by
      mv-mission-control / workspace switcher applet.
- [ ] Energy Saver pane with a real battery: UPower DisplayDevice
      percentage/state must read live on the MacBook10,1 battery; blank /
      DPMS timeout writes must be enforced by the running
      xfce4-power-manager (and not contradict the frozen TLP baseline).
- [ ] Trackpad pane: with applespi working (best-effort track), the
      pane must flip to "Trackpad detected" and pointing settings must
      apply to the Force Touch trackpad; if applespi stays dead, the
      honest empty state is the accepted outcome.
- [ ] Security & Privacy pane on the ISO (xfce4-screensaver installed
      there): the lock toggle must appear and persist; dev container
      lacks the schema, so only the honest fallback path was testable.
- [ ] Bluetooth pane after the blueman install decision on hardware:
      pane must launch blueman-manager once installed.
- [ ] Keyboard flows on the real keyboard: Esc-from-pane-back,
      search-typing latency, Enter activation of grid items (FlowBox
      keynav) under xfwm4 focus handling.

## File Chooser (canonical #21 — theme layer, oid `OS-filechooser-p0`)

Pre-hardware status: every rule in
`packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_filechooser.scss` is
verified live on a real `GtkFileChooserDialog` on the pinned Xvfb :97, and
`scripts/test-filechooser-theme.py` (37 checks) asserts the rendered result.
The items below are what only the MacBook10,1 can settle.

- [ ] Chooser appearance on the real 2304×1440 panel at the shipping scale:
      the 22px path bar and column-header strip, the 8px-inset blue sidebar
      pill and the white selection bar must stay crisp with no 1px seam
      between the paper sidebar and the white list.
- [ ] Focus ring under real xfwm4: the list must not gain a blue focus ring
      when the chooser is opened by keyboard (the container has no window
      manager, so the ring behaviour there is only partially representative).
- [ ] Sidebar with real hardware: the Apple S3X internal volume, any USB-C
      attached storage and the network sidebar must all appear with the
      Mavericks pill/label treatment, and hot-plugging a device must not
      leave a stale pill.
- [ ] Trash row: with GVfs trash active the sidebar must show a Trash entry
      whose label uses the non-white rule (a white Trash label on paper is
      the exact shipped readability bug, and Trash is where it would hurt
      most).
- [ ] The chooser's search box: no `filechooser`-scoped selector was proven
      to reach the lazily built search popover, so it currently inherits the
      global flat `entry` styling. Pop the search on hardware and confirm it
      reads as Mavericks, or fall back to styling `entry.search` globally
      (Global Dialogs surface, needs its owner's sign-off).
- [ ] View modes: this container's GTK builds a chooser with a single
      GtkTreeView and exposes no reachable icon view (no GtkIconView in any of
      the four dialog shapes; the path-bar toggle button and an image filter
      both leave the list view). Confirm on the live ISO whether the shipping
      GTK offers an icon view at all. If it does, it is unstyled and its node
      names need the same injection treatment the list got — do not assume the
      list's selectors carry over.
- [ ] Save flow on real storage: Save As must show the name entry, the
      create-folder button and the overwrite-confirmation alert in the same
      visual language (the alert comes from the shared mv_dialogs layer).
- [ ] Slow mount points (S3X cold mount, USB-C hub): the chooser must not
      show a blank or half-painted sidebar while GIO populates it.
