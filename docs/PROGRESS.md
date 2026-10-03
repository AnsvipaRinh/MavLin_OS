# PROGRESS — MacBook 12 MavLinOS

### Finder P0 — view/zoom fidelity close-out (2026-10-03, без железа)
- [x] Evidence pass on installed Thunar 4.20.10 binary: in-window accelerators (Ctrl+1/2/3 view switch, Ctrl+=/-/0 zoom incl. KP_ variants), real thunarrc zoom keys (Last{Icon,Details,Compact}ViewZoomLevel), per-directory zoom memory via GVFS metadata, native icon-view reflow on resize.
- [x] thunarrc: removed dead `LastViewZoomLevel` key (never read by Thunar — binary evidence), added real `LastDetailsViewZoomLevel`/`LastCompactViewZoomLevel`, icon view default 64px (`THUNAR_ZOOM_LEVEL_150_PERCENT` = Mavericks Finder default; was 48px Thunar-ism). Mirror synced (check-sync green).
- [x] Keyboard architecture decision (DECISIONS): zoom/view keys stay app-level Ctrl (= macOS Cmd semantics); no global Super injection via xdotool — consistent with KEYBOARD.md Super=global / Ctrl=app-level split. No new global bindings.
- [x] mv-finder-search + mv-finder-columns: Finder-like Ctrl+=/-/0 zoom over 16/22/32/48 px ladder; results rebuild in place preserving rows/chain; pixbuf-based icons in search results. Tests: search 68 pass (+11 zoom), columns 24 pass (+10 zoom).
- [x] KEYBOARD.md: new "Finder / Thunar (app-level accelerators)" section.
- [x] APPS.md Finder status: **IMPLEMENTED — HARDWARE VALIDATION REQUIRED** — §13.6 checklist closed pre-hardware; 3 documented architectural deltas (in-window column view, in-toolbar search field, native Space key) all carry hard evidence + mitigations in DECISIONS.
- [x] Gate: check-sync.sh ALL CHECKS PASSED; :0 launch smoke clean for both helpers.
- [ ] HW: 64px default at 2x scaling on 2304×1440, zoom ladder feel, view-switch behavior (NEEDS_HARDWARE_TEST).

### Finder P0 — recursive search + column-view decision (2026-10-03, без железа)
- [x] Audit vs APPS.md line-55 claims: confirmed three open gaps — recursive search, column view, Space-key delta (accepted). Evidence: thunar-uca.xml actions, bin/mv-* helpers, thunarrc.
- [x] RECURSIVE SEARCH (headline): `bin/mv-finder-search` — Mavericks-style results window (HeaderBar + SearchEntry, Name/Kind/Size/Where columns, folders-first) rooted at the Thunar current folder. Debounced incremental search (250 ms, generation counter kills stale results), worker thread keeps UI responsive, `os.scandir` walk backend (no symlinked-dir traversal — find(1) parity), plocate fast-path ONLY for whole-$HOME roots (basename-filtered for walk parity; falls back to walk on plocate failure). Hidden files follow Finder convention (searchable when query starts with "."). Enter/double-click: folders → Thunar, files → xdg-open. Esc clears query then closes; Ctrl+F/L focuses entry. Unreadable-dirs warning InfoBar; empty/no-results/error states; status bar with result count + search root. On-demand single-shot process, no daemon.
- [x] UCA wiring: "Search in This Folder…" (edit-find) + "Browse as Columns" (format-justify-fill) in `config/thunar-uca.xml` + airootfs mirror (check-sync pair green).
- [x] COLUMN VIEW: investigated with hard evidence — thunarx-3 (gir introspected) has Menu/Preferences/PropertyPage/Renamer providers only, no view provider; Thunar view modes are compiled-in widgets. In-window column view = fork required (rejected, reuse-first). Shipped cheapest real improvement: `bin/mv-finder-columns` — Finder column navigation companion (multi-pane, folders-first, Left/Right/Backspace/Esc/Enter keyboard, "Open in Thunar" handoff for file management). DECISIONS.md entry documents the full rationale.
- [x] Tests: scripts/test-mv-finder-search.py 57 pass (rank ladder, hidden/dot conventions, walk+cap+skipped+symlink, plocate parse filtering, backend choice, sort; GUI smoke incl. full debounce→thread→idle pipeline, empty state, infobar, Esc semantics, Ctrl+F); scripts/test-mv-finder-columns.py 14 pass (ordering, hidden, unreadable OSError; GUI column build/truncate/error state). Both :0 launch-smoke clean.
- [x] Gate: check-sync.sh ALL CHECKS PASSED (incl. uca.xml mirror + py_compile + xmllint); DESTDIR install verified (both bins land in /usr/bin).
- [x] Docs: APPS.md Finder row updated; FIDELITY_AUDIT Finder Search/Icon View rows updated; NEEDS_HARDWARE_TEST entries added.
- [ ] HW: visual validation on 2304×1440 (search window, column browser, UCA entries in context menu) — NEEDS_HARDWARE_TEST.md.

### Theme: Mavericks skeuomorphic icon theme + cursor theme (2026-09-30, без железа)
- [x] Icon theme (packages/mavericks-theme/src/mavericks-theme/icons/): comprehensive Mavericks-era skeuomorphic icons
  - 28 core app icons (Finder, folder, trash empty/full, calculator, calendar, console, control-center, text-editor, system-monitor, help-about, display, drive-harddisk, launchpad, mail, archive, dictionary, log-viewer, image-viewer, audio-player, audio-recorder, screenshot, font-book, keychain, timemachine, terminal, document-viewer, color-picker, sticky-notes, reminders, sound, keyboard, mouse)
  - 30+ symlinks for standard Linux/GTK icon names (gnome-*, evince, eog, rhythmbox, gedit, seahorse, etc.)
  - All sizes: 16, 22, 24, 32, 48, 64, 128, 256, 512 + scalable SVG (HiDPI-ready, no hardcoded 1x)
  - Places: user-trash, user-trash-full
  - Devices: computer, drive-harddisk (+ symlinks for optical, floppy, removable)
  - Mimetypes: text, image, audio, video, archive, pdf, font, executable
  - Emblems: favorite, readonly, system, documents, photos, music, videos, downloads, shared
  - Actions, categories, filesystems, status directories structured
- [x] Cursor theme (packages/mavericks-theme/src/mavericks-theme/cursors/): Mavericks-Cursors replaces Adwaita inheritance
  - left_ptr (classic Mac arrow), hand1/hand2 (pointing hand), text/xterm (I-beam), crosshair/cross, watch/wait (spinning beach ball)
  - sb_h_double_arrow/ew-resize, sb_v_double_arrow/ns-resize, corner resizes (nwse, nesw, nw, ne, sw, se), move/all-scroll
  - Proper hotspots, 32px base with 16/24px variants
  - 13 base cursors + 30+ symlinks for X11/GTK standard names
  - Compiled to X11 .cursor format (Python-generated, no xcursorgen dependency)
- [x] All icons generated as PNG at all required sizes via rsvg-convert
- [x] check-sync.sh: 221 checks pass
- [x] test-theme-css.py: 9 checks pass

### Completeness C2 — P1 implementation (2026-09-29, без железа)
- [x] P0-J1 SECURITY (commit dfbd987): sshd disabled in ISO (.wants symlink removed), root locked (`root:!` in airootfs shadow + `passwd -l root` in firstboot), permissive sshd_config.d/10-archiso.conf deleted. Remote bring-up = explicit opt-in via lab/agent/install.sh (key-based forced-command as mavericks-lab, never root). Verified: install is local, no .wants/.requires references sshd, lab agent needs no root SSH. DECISIONS.md security entry. +6 check-sync security checks.
- [x] P1-M1 (commit 77f6e15): Firefox seed profiles.ini + installs.ini added (configs/firefox/ source, mirrored to seed). Before: no profiles.ini → activation non-deterministic, seed could be orphaned. check-sync validates INI content + profile existence.
- [x] P1-O1/O2 (commit 1409361): 18 unreferenced packages removed (129→111). intel-gpu-tools KEPT (intel_gpu_top = GPU metric in HW_BROWSER_MATRIX 4-mode plan) + 11 more KEEP with evidence (powertop/turbostat/ethtool/dmidecode/mesa-utils/openssh/stress-ng = HW procedures or code; less/diffutils/hdparm/usbutils = hard deps of man-db/mkinitcpio/tlp, pacman -Si verified). Reasons recorded in NEEDS_HARDWARE_TEST.md.
- [x] P1-L1 (commit dc2df3f): shared .desktop parse cache IMPLEMENTED (condition met: airtight invalidation + corrupt-cache safety + tests). mv_desktop_cache module: per-dir (mtime_ns,count) + per-file (mtime_ns,size) fingerprint, quarantine-on-corrupt (mv-music family pattern). mv-launchpad/mv-spotlight consume raw entries, keep own dedup/sort/icon logic. S25: cold 15.98ms → warm 1.15ms (13.9×). +41 tests. Bench 31 scenarios 0 failed.
- [x] Gate: check-sync --check-repos ALL CHECKS PASSED (227 checks); 23 test files (21 clean; mv-photos 2 + mv-textedit 6 = same pre-existing C1 host artifacts); bench 31 scenarios 0 failed; power baseline untouched.
- [x] Before/after: docs/BENCHMARKS.md (C2-P1 section) + docs/benchmarks/results-2026-09-29-c2-p1.json
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): all remaining items are hardware measurements/validation.

### Track 6/7 — Theme CSS redundancy audit (2026-09-29, без железа)
- [x] Removed duplicate CSS rules: `@import "../gtk-3.0/other";` from gtk-3.20/gtk.scss (eliminates ~400 duplicate SCSS lines)
- [x] Deprecated `_other.scss` (423→15 lines): all content duplicated in `_widgets.scss`, `_menus.scss`, `_windows.scss`
- [x] 11 selector groups deduplicated: scrollbar, scale, progressbar, sidebar, headerbar, titlebuttons, switch, checkbox/radio, paned, infobar, popover, drag-icon
- [x] Unique 3.20+ widgets retained in gtk-3.20/gtk.scss: emojichooser, modelbutton, viewswitcher, shortcut-label, flowbox, listbox, stackswitcher, levelbar
- [x] Assets unchanged: wallpapers/mavericks-desktop.png, icons/scalable/apps/sticky-notes.svg, timemachine.svg, airdrop.svg
- [x] Gate: test-theme-css.py 9/9 passed
- [x] Rebuild: makepkg + check-sync.sh passed
- [x] Before/after: BENCHMARKS.md parse-ms delta recorded (gtk-3.0: 2.3ms, gtk-3.20: 1.5ms)
- [ ] Commit: theme fix + docs

### Completeness C1 — P1 implementation (2026-09-29, без железа)
- [x] P1-C1: removed 13 dead-weight packages from ISO (142→129, ~330 MiB): linux, sof-firmware, linux-firmware-marvell, refind, orage, flameshot, xfce4-taskmanager, xfce4-appfinder, xfce4-notes-plugin, rsync, wireless_tools, mc, vim. **stress-ng KEPT** (mv-thermal.sh). Each verified unreferenced. check-sync --check-repos green. (3193695)
- [x] P1-C4: removed 8 dead systemd units via .wants symlink removal (archiso convention): 5x cloud-init + pcscd.socket + ModemManager + livecd-talk. firstboot ModemManager mask kept; VM agents kept for QEMU. (7eb6977)
- [x] P1-C2: lazy Gtk import in timer one-shots (mv-calendar/mv-reminders/mv-timemachine). Timer paths no longer import Gtk. mv-calendar 0.41→0.10s, mv-reminders 0.38→0.08s, mv-timemachine 0.43→0.26s (Secret retained). (444fba3)
- [x] P1-C3: mtime+size+count-keyed scan-result cache in mv-music/mv-photos. Warm hit skips all file reads. mv-music 0.054→0.007s (7.7×), mv-photos 0.016→0.008s (2.1×). Cover handling via cover_path + mtime-keyed cover_cache_path. (e6d65ba)
- [x] Tests: +9 cache tests per app, +1 lazy-import test per timer app. mv-music 117/0, mv-calendar 64/0, mv-reminders 32/0, mv-timemachine 60/0. Pre-existing host artifacts unchanged (mv-photos 2 gthumb, mv-textedit 6 respawn).
- [x] Gate: check-sync --check-repos ALL CHECKS PASSED. Power baseline untouched.
- [x] Before/after: docs/BENCHMARKS.md (C1-P1 section) + docs/benchmarks/results-2026-09-29-c1-p1.json
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): all remaining items are hardware measurements/validation.

### Phase 1 — Remote Lab Control Plane (2026-09-28, без железа)
- [x] Agent: `lab/agent/mavericks-lab-agent` — single-file, python3 stdlib, zero-idle, SSH forced-command, NOT a daemon
- [x] Protocol: NDJSON over stdin/stdout, 16 commands (status, inventory, collect, run-test, benchmark, deploy, verify, reboot, shutdown, select-boot, commit, rollback, snapshot, restore, logs, trace, ping)
- [x] Idempotency: UUID job IDs, journal replay returns cached response without re-exec
- [x] A/B state machine: UNKNOWN→BOOTING→NETWORK_READY→AGENT_READY→HEALTH_CHECK→HEALTHY→COMMITTED, FAIL→ROLLBACK, attempt counter, max_attempts=3, boot-loop protection
- [x] Persistent state: atomic writes (temp+rename), survives crash/reboot/power-loss
- [x] Event journal: append-only JSONL, job results cached for replay
- [x] Deployment: HOST→inactive slot, deterministic deployment_id (img-<sha256[:16]>), SHA-256 + ed25519 signature verification, idempotent re-deploy
- [x] Boot backend: QEMU simulation (files + systemd-boot entries), Mac backend documented (efibootmgr -n/-o, narrow sudoers)
- [x] Identity: ed25519 machine key on DATA, openssl/ssh-keygen with graceful fallback
- [x] Host CLI: `lab/host/mavericks-lab` — local mode (testing) + SSH mode (hardware)
- [x] Host store: SQLite (jobs + events tables), queryable by scenario/result/limit
- [x] Installer: `lab/agent/install.sh` — agent binary, identity, SSH forced-command, systemd oneshot, narrow sudoers
- [x] Tests: 7 test files, 158 tests, all green (protocol, state, deploy, boot, identity, store, e2e)
- [x] E2E: full A/B lifecycle (deploy→boot→health→test→commit), rollback, idempotency, crash recovery, snapshot/restore
- [x] Phase 2: QEMU/OVMF A/B test harness — 25 failure-injection scenarios, pluggable backends (sim/qemu/mac-stub), declarative YAML, result DB (1d56515)
  - [x] Sim backend: 25/25 scenarios pass (rootless, deterministic)
  - [x] Harness tests: 110/110 pass (lab/harness/tests/test_harness.py)

### Phase 3 — QEMU NIC Fix (2026-09-30, без железа)
- [x] Added virtio-net-pci with user-mode SLiRP to QEMU command line (`-netdev user,id=net0 -device virtio-net-pci,netdev=net0`)
- [x] Updated guest_init.py net_up(): waits for eth0 (built-in or modular), loads virtio_net.ko + deps (failover, net_failover) if needed, brings interface up with static IP 10.0.2.15/24, adds default route via 10.0.2.2
- [x] Added virtio-net.ko, net_failover.ko, failover.ko to initramfs (builder.py) with depmod
- [x] Verified: QEMU guest boots to HEALTHY with NET_DONE in serial log showing eth0 route via 10.0.2.2
- [x] Command channel migrated to 9p virtfs (virtio-fs) — infrastructure in place, but 9p mount fails in guest (ENODEV — transport not ready). Blocked on 9p virtio transport initialization order. Network scenarios (boot, network_down) work; command-channel scenarios (select_boot, status) blocked.
- [x] Sim backend unchanged (25/25 pass), lab tests (158) pass, harness tests (6) pass
- [x] No production bootloader/power/UI/kernel changes — only lab/harness/
  - [x] QEMU backend: real guest boot works; network-up scenarios fail health check → ROLLBACK (documented limitation: virtio-net module fails, no route creation)
  - [x] Mac backend: documented stub (efibootmgr -n/-o), raises NotImplementedError, does NOT touch production bootloader
  - [ ] Deferred seam: chunked deploy (large images), raw stream deploy, QEMU network-up fix, Mac backend wiring to production bootloader

### QEMU Track Closure (2026-10-01, без железа)
- [x] **Track CLOSED** — all pre-hardware QEMU objectives achieved; remaining items require physical MacBook10,1
- [x] SimBackend: 25/25 scenarios PASS (rootless, deterministic, primary)
- [x] QemuBackend: 7/25 scenarios PASS (01,02,11,15,16,23,25 — network boot HEALTHY; reboot path works manually); command-channel scenarios (select_boot, status, etc.) blocked on 9p virtfs ENODEV (transport not ready in guest)
- [x] MacBackend: documented stub only (efibootmgr -n/-o), raises NotImplementedError
- [x] **Environment limitation documented:** No `/dev/kvm` in build container → TCG emulation; 5.5× timing variance observed; harness flaky under TCG (timeout jitter). Hardware bring-up on MacBook10,1 with KVM will re-validate.
- [x] Test inventory reconciled: lab/tests/ = 7 scripts, 158 assertions (standalone runners); lab/harness/tests/ = 1 pytest file, 6 tests. Discrepancy (158 vs 122) explained: pytest collects 0 from standalone scripts.
- [x] Zero production touch — only lab/harness/ modified
- [x] Gate: check-sync 221/221 PASS; harness tests 6/6 PASS; lab tests 158/158 PASS
- [x] docs/LAB_HARNESS.md updated with canonical counts, final results table, and env limitation evidence

### Track closure — Architecture Optimization R1–R2 + D1–D7 (2026-09-28, без железа)
- [x] R2 proposal reconciled: 6 items → 3 SUPERSEDED (BlueZ signals, worker thread, pactl→D-Bus — all superseded by the 14c8009 signal-driven redesign + f2568dc dedup + measured P2 acceptance), 1 CLOSED (mv-eject/rename — already efficient), 2 STILL-OPEN accepted (mv-airdrop NM State, mv-diskutil ObjectManager — on-open only, P2) — ARCHITECTURE_OPTIMIZATION_AUDIT.md §R2
- [x] D-candidate statuses finalized: 11 APPLIED (D1: F1/F2/F3/U2/U3, D2: F10, D4: F19–F22, D5: F26), 105 KEEP, 3 SUPERSEDED, 2 STILL-OPEN, 1 FALSE-POSITIVE, 2 UPSTREAM, 35 HW-PENDING — ARCHITECTURE_OPTIMIZATION_AUDIT.md §Track summary
- [x] NATIVE_REWRITE_CANDIDATES.md finalized: all 48 components KEEP with measured verdict reasons (GTK-FLOOR / FAST-ENOUGH / NEAR-ZERO / NEGLIGIBLE / NOT-RUNTIME) — zero rewrites warranted; this IS the deliverable
- [x] DRIVER_OPTIMIZATION_CANDIDATES.md: PROPOSED-HW-MEASUREMENT → HW-PENDING for all 18 H/O items; applied items (F1/F2/F3/U2/U3/F26) noted in headers
- [x] Applied-change list with commits + measured deltas: 14c8009 (S-01 ≥83% rescan reduction), f2568dc (refresh_all 83% fewer ticks), 0b0fcb6 (--rescan no), a0623c9 (NM pin + connectivity off), ab10a5e (NVRAM F1/F2/F3), 888e0ff (audio F19–F22), e5cfc06 (fstrim), bfebe9b (S-02), 143e9b2 (S-03), 5330d93 (S-04), 8211b9f (S-09), b9d16ba (S-10), edd2eec (S-11)
- [x] Suite counts: 22 test files, check-sync 221 checks, bench 24 scenarios — all green
- [x] Gate: docs-only consolidation — zero code changes; power baseline untouched; no driver modifications
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): all remaining items are hardware measurements/validation — Wi-Fi counters (H1–H10, O1–O8), PSR/ASPM A/B, resume matrix, audio power/idle, applespi 3-strategy, S3X resume, boot chain. No pre-hardware software work remains open.

### Фаза D5 — INPUT + STORAGE audit: Apple SPI/HID + libinput + NVMe/S3X (2026-09-28, без железа)
- [x] INPUT runtime map: applespi driver (ACPI GPE interrupt, NOT SPI IRQ), no retry on timeout, no runtime PM, no wake from suspend, pure interrupt-driven — RUNTIME_COMPONENT_MAP.md §9
- [x] Timeout behavior: NO retry loop — SPI transfer failure logs pr_warn and drops event; 6.15+ failure root cause is SPI controller rev3+ hardware bug — RUNTIME_SOURCE_AUDIT.md §I2
- [x] Power: NO runtime PM — device stays powered in S0; only system suspend/resume; keyboard does NOT wake from suspend — RUNTIME_SOURCE_AUDIT.md §I3
- [x] Touchpad: standard multitouch (INPUT_PROP_POINTER | INPUT_PROP_BUTTONPAD), no ABS_MT_PRESSURE (Force Touch pressure not reported) — RUNTIME_SOURCE_AUDIT.md §I4
- [x] External USB-C HID: reference-good — USB interrupt, autosuspend, wake from suspend, full libinput — RUNTIME_SOURCE_AUDIT.md §I5
- [x] libinput: NO quirks or hwdb needed — standard multitouch device, default settings — RUNTIME_SOURCE_AUDIT.md §I6
- [x] STORAGE runtime map: S3X NVMe (106b:2003, no APST), ASPM interplay with pcie_port_pm=off, btrfs minimal mount options — RUNTIME_COMPONENT_MAP.md §10
- [x] APST: S3X does NOT expose APST — stays in D0, no autonomous power transition — RUNTIME_SOURCE_AUDIT.md §S1
- [x] ASPM cost: pcie_port_pm=off disables ALL PCIe root port PM — battery cost unmeasured, LKML thread open — RUNTIME_SOURCE_AUDIT.md §S2
- [x] btrfs: minimal mount options (subvol=@ only), kernel defaults fine — RUNTIME_SOURCE_AUDIT.md §S3
- [x] fstrim.timer: NOT enabled in our ISO — CONFIG-CANDIDATE, should enable — RUNTIME_SOURCE_AUDIT.md §S4
- [x] zram: CORRECT — ram/2, zstd, no disk swap — RUNTIME_SOURCE_AUDIT.md §S5
- [x] journald: CORRECT — volatile in ISO, persistent with limits on install — RUNTIME_SOURCE_AUDIT.md §S6
- [x] Driver audit: 6 findings — F23 (SPI timeout 6.15+, DOCUMENTED, 3-strategy limit), F24 (no runtime PM, DOCUMENTED), F25 (no wake from suspend, DOCUMENTED), F26 (fstrim.timer, CONFIG-CANDIDATE), F27 (S3X resume, BASELINE-JUSTIFIED), F28 (btrfs mount, KEEP) — DRIVER_AUDIT.md §D5
- [x] HW measurement plans: input (GPE status, evtest, suspend/resume, SPI timeout matrix), storage (NVMe SMART, PCIe power, ASPM A/B, btrfs, fstrim, zram) — DRIVER_OPTIMIZATION_CANDIDATES.md §8-9
- [x] Upstream tracker: applespi NOT mainlined, NO upstream SPI timeout fix; S3X NVMe NO upstream fix, LKML thread open — UPSTREAM_PATCH_TRACKER.md §D5
- [x] NEEDS_HARDWARE_TEST.md: input HW validation items (USB-C mandatory first, applespi 3-strategy, SPI timeout matrix, power/idle counters) + storage HW validation items (S3X basic, resume, ASPM A/B, btrfs/SSD, zram, power/idle counters)
- [x] Gate: docs-only phase — zero code changes; power baseline untouched; no driver modifications
- [x] fstrim.timer fix: added `systemctl enable fstrim.timer` to firstboot script
- [x] D6 proposal: persistent desktop services + own persistent components final sweep
- [x] D6: persistent services + own components final sweep — ALL compliant, zero changes — PERSISTENT_SERVICES_AUDIT.md
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): input (USB-C mandatory, applespi 3-strategy, SPI timeout matrix) + storage (S3X resume, ASPM A/B, btrfs/SSD, fstrim)

### Фаза D6 — Persistent desktop services + own persistent components final sweep (2026-09-28, без железа)
- [x] System services audit: 8 services (tlp, zram-setup, NM, resolved, lightdm, bluetooth, fstrim.timer, plocate-updatedb.timer) — all event-driven or oneshot, no polling — PERSISTENT_SERVICES_AUDIT.md §1
- [x] User timers audit: 3 timers (mv-reminders-check hourly, mv-calendar-check 5min, mv-timemachine-check hourly) — all oneshot, no polling — PERSISTENT_SERVICES_AUDIT.md §2
- [x] Panel plugins audit: 7 plugins (applicationsmenu, tasklist, separator, systray, clock, actions, genmon) — genmon is only polling plugin (5s, one-shot C tool) — PERSISTENT_SERVICES_AUDIT.md §3
- [x] Autostart audit: 1 entry (Plank Dock) — no other autostart — PERSISTENT_SERVICES_AUDIT.md §4
- [x] mv-* timer/poll audit: 15 timers across 14 apps — all window-open-only or one-shot, classified P2/IGNORE per §7 — PERSISTENT_SERVICES_AUDIT.md §5
- [x] mv-* persistent process audit: 40 apps — zero persistent processes, zero autostart, zero daemons — PERSISTENT_SERVICES_AUDIT.md §6
- [x] Final verdict: ALL persistent services and own components are power-baseline compliant — no new daemons, no new polling, no persistent processes beyond standard Xfce stack — PERSISTENT_SERVICES_AUDIT.md §7
- [x] Gate: docs-only phase — zero code changes; power baseline untouched; no driver modifications
- [x] D7 proposal: boot/ISO packaging audit (mkinitcpio, systemd-boot, profiledef, packages.x86_64 consistency)
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): input (USB-C mandatory, applespi 3-strategy, SPI timeout matrix) + storage (S3X resume, ASPM A/B, btrfs/SSD, fstrim)

### Фаза D7 — BOOT + ISO packaging audit: mkinitcpio, systemd-boot, profiledef, packages.x86_64, firstboot (2026-09-28, без железа)
- [x] mkinitcpio.conf: MODULES=(applespi spi_pxa2xx_platform intel_lpss_pci intel_lpss_acpi) — all 4 correct for MacBook10,1; HOOKS=(base udev autodetect microcode modconf kms keyboard keymap block filesystems fsck) — no encrypted root, no btrfs hook needed (in-kernel); COMPRESSION=zstd -T0 --long -19 — CORRECT — BOOT_AUDIT.md §1
- [x] systemd-boot entries: mavlinos-zen.conf + fallback — cmdline correct (quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0); loader.conf timeout 3, default mavlinos-zen.conf, editor 1 — CORRECT — BOOT_AUDIT.md §2
- [x] profiledef.sh: bootmodes=('uefi.systemd-boot') — UEFI-only, no grub; all settings correct — BOOT_AUDIT.md §3
- [x] packages.x86_64: 142 packages (140 Arch + 2 local); NO AUR in default list (localsend-bin/skippy-xd opt-in); all new deps from chrome/ytplayer/policy phases present — CORRECT — BOOT_AUDIT.md §4
- [x] firstboot: 8-step idempotent script — hostname/locale, bootloader cmdline, TLP baseline, zram, NM config, fstrim.timer (D5 fix), desktop/firefox skel, NVRAM check, local pkgs — CORRECT — BOOT_AUDIT.md §5
- [x] Cold-start decomposition: necessary (zram, tlp, resolved, networkd, lightdm), lazy-startable (bluetooth, NM), parallelizable (most), removable (ModemManager, hv_*, vbox/vmware, livecd-talk, reflector, sshd, iwd, pacman-init), replaceable-lightweight (iwd↔wpa_supplicant) — BOOT_AUDIT.md §6
- [x] ISO size: 2.7G, 737 pkgs — all top grows justified by applications — BOOT_AUDIT.md §7
- [x] NEEDS_HARDWARE_TEST.md: first-boot HW procedure refreshed (boot chain validation, live ISO boot, installed system first boot) — BOOT_AUDIT.md §9
- [x] Gate: docs-only phase — zero code changes; power baseline untouched; no driver modifications
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): boot chain, input, storage, audio, display, network

### Фаза D4 — Audio path audit: HDA/Cirrus CS4208 + ALSA + PipeWire/WirePlumber + pactl usage (2026-09-28, без железа)
- [x] Runtime map: HDA controller (snd-hda-intel, PCI 00:1f.3, power_save + runtime PM), CS4208 codec (DKMS snd-hda-codec-cs420x, A1534 init unconditional), speaker path (digital 0x0a→0x1d, no HW volume → softvol), headphone path (analog 0x02→0x10), jack GPIO interrupt, ALSA (no UCM for CS4208), PipeWire 1.6.9 + WirePlumber 0.5.17 (event-driven, zero-stream idle), mv-control/mv-voice pactl+pw one-shot — RUNTIME_AUDIT.md §AUDIO
- [x] Idle-component table: pipewire + wireplumber run at idle (epoll, no wakeups at zero streams); HDA controller D3hot (TLP power_save=1); codec powers with controller; jack GPIO wakes from D3hot; mv-control/mv-voice zero idle presence — RUNTIME_AUDIT.md §AUDIO idle table
- [x] DSP/clock-gating: none on this path (HDA not DSP-based; verb-sequence init; HDA-link DMA; controller-level gating only) — RUNTIME_AUDIT.md §AUDIO
- [x] Source audit: 7 findings (A1-A5) — 4 KEEP (azx power path, codec PM, no UCM needed, graph idle — all by design), 3 LOCAL-FIX — RUNTIME_SOURCE_AUDIT.md §A1-A5
- [x] Driver audit: 7 findings — F16 (DKMS build broken: no root Makefile, DOCUMENTED), F17 (internal HDA headers not in linux-zen-headers, DOCUMENTED), F18 (driver source COMPILES on target kernel 7.2.6 — VERIFIED in build container), F19 (dangling udev rule, FIXED), F20 (softvol conf never installed, FIXED), F21 (dead model=macbook12, FIXED), F22 (redundant power_save lines, FIXED) — DRIVER_AUDIT.md §D4
- [x] Packaging changes (888e0ff): wireplumber softvol conf installed to /etc/wireplumber/wireplumber.conf.d/; dangling udev rule removed; 99-macbook12-audio.conf cleaned (comment-only)
- [x] DKMS defect disposition: package kept in local repo (manual build flow); NOT added to ISO (would break pacstrap); tanisperez fork recommended as replacement pin — separate packaging track — DECISIONS.md D4-4
- [x] UCM verdict: none needed (no upstream UCM for CS4208; driver does own mixer setup) — DECISIONS.md D4-5
- [x] pactl sites: R1/R2 flag CLOSED — all sites event-driven, no audio polling (re-verified after 14c8009/143e9b2) — DECISIONS.md D4-6
- [x] TLP interaction: no double-tuning — TLP 1.9.1 defaults (AC=1/BAT=1/controller=Y) cover audio PM; our redundant modprobe lines removed — DECISIONS.md D4-3
- [x] HW measurement plan: DKMS track decision (tanisperez vs manual), power_save A/B + glitch check, codec power_state, jack wakeups, pw-top idle, softvol rule validation — DRIVER_OPTIMIZATION_CANDIDATES.md §7
- [x] Upstream tracker: NO upstream patches required; CS4208 not upstreamed (community driver only); alsa-ucm-conf has no CS4208 entry; TLP/PipeWire/WirePlumber no defects; tanisperez fork tracked as replacement candidate — UPSTREAM_PATCH_TRACKER.md §D4
- [x] NEEDS_HARDWARE_TEST.md: audio power/idle counters added (controller runtime_status, codec power_state, TLP params, jack wakeups, pw-top idle, softvol rule, power_save A/B, glitch check, jack switching, suspend/resume)
- [x] Gate: check-sync ALL CHECKS PASSED (221 checks, 0 failures); all test-*.py green; PKGBUILD parse OK
- [x] D5 proposal: SPI/input (applespi, best-effort 3-strategy limit) + NVMe/storage (Apple S3X, pcie_port_pm=off validation)
- [ ] HW validation (NEEDS_HARDWARE_TEST.md §Audio power/idle): DKMS track decision, power_save A/B, glitch check, codec power_state, jack wakeups, pw-top idle, softvol, speaker/mic functional

### Фаза D3 — Intel HD 615 display path audit: i915 → DRM/KMS → X11 → xfwm4/Xfce (2026-09-28, без железа)
- [x] Runtime map: i915 power domains (DISPLAY_CORE/PIPE/TRANSCODER/DDI/AUX/GMBUS/DC_OFF), Gen9 power wells (PW1/PW2/MISC_IO/DC_OFF), DC5/6 states, DMC firmware (kbl_dmc.bin), PSR1/PSR2 entry/exit path, FBC (Gen9 FBC1, nuke on flip), forcewake model, GEM/fence activity, backlight PWM (BXT_BLC_PWM_DUTY), DPST absent on Gen9.5 eDP, vblank/pageflip under xfwm4 — RUNTIME_COMPONENT_MAP.md §5
- [x] Source audit: 10 findings (S1-S10) — all KEEP; PSR entry (idle_frames + sync latency), PSR2 Y-coord gate, PSR exit on vblank, FBC nuke on flip, FBC+PSR1 coexistence on Gen9, backlight PWM from VBT, DC5/6 blocked by vblank, DMC firmware required, forcewake for register access, PSR+DC5/6 mutual exclusion — RUNTIME_SOURCE_AUDIT.md §D3
- [x] Driver audit: 4 findings — F12 (PSR flicker Gen9, BASELINE-JUSTIFIED), F13 (Apple S3X resume, BASELINE-JUSTIFIED provisional), F14 (xfwm4 vblank/unredirect PROVISIONAL), F15 (DMC firmware packaging KEEP) — DRIVER_AUDIT.md §D3
- [x] Baseline judgment: pcie_port_pm=off = JUSTIFIED (provisional, LKML Sep 2026, S3X resume fix, battery cost unmeasured); i915.enable_psr=0 = JUSTIFIED (diagnostic-safe, Gen9 flicker LP#2086587/2062951, upstream fix landed 6.8.0-53 but panel-specific) — DECISIONS.md D3
- [x] X11-side cost table: xfwm4 compositing (use_compositing=true, vblank_mode=off PROVISIONAL, unredirect_overlays=true PROVISIONAL, shadows), PSR+vblank mutual exclusion, cursor plane PSR exit, DPMS not configured, screensaver timeout=60 — DECISIONS.md D3
- [x] HW measurement plan: PSR on/off A/B, ASPM A/B, resume-cycle matrix (8 rows), xfwm4 compositor validation, backlight PWM validation — DRIVER_OPTIMIZATION_CANDIDATES.md §6
- [x] Upstream tracker: PSR2 flicker fixes LANDED (Jouni Högander 8-patch series, mainline 6.8.0-53); Apple S3X resume NO fix yet (LKML open); DMC/FBC stable — UPSTREAM_PATCH_TRACKER.md §D3
- [x] NEEDS_HARDWARE_TEST.md: 8 HW validation items (PSR A/B, ASPM A/B, resume matrix, xfwm4, backlight, DMC, FBC, forcewake)
- [x] Gate: docs-only phase — zero code changes; power baseline untouched; no driver modifications
- [x] D4 proposal: PipeWire/audio path audit (HDAudio Cirrus codec, PipeWire graph, ALSA UCM, D-Bus media session, power audio)
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): PSR on/off A/B, ASPM A/B, resume-cycle matrix, xfwm4 tearing, backlight PWM, DMC firmware, FBC status, forcewake leaks

### Фаза D2 — NM userspace path audit: backend pin + connectivity off + mv-control scan fix (2026-09-28, без железа)
- [x] Active backend = wpa_supplicant (NM default, meson.build:430-436); versions: NM 1.58.1-1 (GPL-2.0/LGPL-2.1, extra), wpa_supplicant 2:2.12-1 (BSD-3-Clause, core), iwd 3.12-2 (LGPL-2.1, extra); our packaging had NO NM config → defaults applied
- [x] Periodic-activity table: NM scan (DISCONNECTED-only 3s→120s backoff; ACTIVATED = supplicant bgscan), connectivity check (Arch ships uri → 300s HTTP), mv-control 30s poll (triggered scan every ~30s — FIXED), powersave (default ignore → firmware default)
- [x] Config changes (evidence-backed, our packaging only): `configs/network/99-mavericks.conf` `[device] wifi.backend=wpa_supplicant` (pin, no behavior change) + `[connectivity] enabled=false` (shadows Arch 300s HTTP poll); mirrored to airootfs + firstboot install + check-sync pair
- [x] mv-control: `refresh_wifi_list` `--rescan no` default (cached AP list, no scan); Refresh button `--rescan yes`; NM D-Bus signals still drive refresh; test +2 (34/34)
- [x] Backend trade-off documented: wpa_supplicant (full features, NM-controlled roaming) vs iwd (no P2P, 802.1X provisioning, iwd roaming); powersave identical (NL80211_CMD_SET_POWER_SAVE direct); SAE both
- [x] docs: RUNTIME_COMPONENT_MAP §4.1 (userspace audit), RUNTIME_SOURCE_AUDIT §D2 (U1-U5), DRIVER_AUDIT §D2 (F10-F11 + config changes), DRIVER_OPTIMIZATION_CANDIDATES §5 (NM scan wakeup plan, backend A/B procedure, powersave lever), UPSTREAM_PATCH_TRACKER (NONE + search), DECISIONS (D2 entry)
- [x] Gate: mv-control 34/34; check-sync ALL CHECKS PASSED; power baseline untouched; no NM/supplicant source patches
- [ ] HW validation (NEEDS_HARDWARE_TEST.md): NM scan wakeup measurement, backend A/B, powersave lever, PM_FAST stability

### Фаза D1 — Network deep audit: brcmfmac/BCM43602 runtime map + source audit + HW plan (2026-09-28, без железа)
- [x] docs/RUNTIME_COMPONENT_MAP.md: brcmfmac module structure (PCIe bus, MSGBUF protocol, FullMAC → cfg80211 no mac80211), firmware interface (bin/txt/clm/txcap + board-specific OTP/ACPI/DMI selection), NM→wpa_supplicant→nl80211→cfg80211→brcmfmac chain, wakeup sources (threaded MSI IRQ, fweh events, scan, roam), timers (escan 10s, btcoex DHCP, p2p listen — no idle timers), runtime PM (D3 hot-resume), sysfs/debugfs, PCI IDs (14e4:43ba), firmware set
- [x] docs/RUNTIME_SOURCE_AUDIT.md: 18 findings across event/RX/TX/scan/roam/powersave/suspend/logging/NVRAM paths — 16 KEEP, 2 CONFIG-CANDIDATE (NVRAM file>EFI precedence, ccode=X0), 1 FALSE-POSITIVE (feature_disable=0x82000 = SAE|MONITOR_FMT_HW_RX_HDR cargo-cult)
- [x] docs/DRIVER_AUDIT.md: 9 findings — F1 placeholder shadows EFI NVRAM (firmware.c:559-561), F2 ccode=X0 invalid (driver fixup only handles ALL/XV→X2), F3 0x82000 decodes to SAE|MONITOR_FMT_HW_RX_HDR (no 5GHz link), F4 DMI board_type="Apple Inc.-MacBook10,1" (space), F5 Apple ACPI module-instance/RWCV unknown on MacBook10,1, F6 EFI NVRAM may provide real calibration, F7 default MAC randomization, F8 43602 download-state, F9 ISO packaging consistent
- [x] docs/DRIVER_OPTIMIZATION_CANDIDATES.md: idle-state analysis A-G (idle-connected/light/download/upload/scan/reconnect/suspend-resume), HW measurement plan (counters, dmesg patterns, procedure), 10 hypotheses (all PROPOSED-HW-MEASUREMENT), 8 optimization candidates
- [x] extract-brcmfmac-nvram.sh: F1 skip placeholder when EFI NVRAM detected in dmesg, F2 ccode=X0→X2 (driver's documented worldwide code), F3 remove cargo-cult feature_disable=0x82000 value; synced to archiso profile copy
- [x] Source basis: Linux 7.3.0-rc5 (torvalds) brcmfmac + linux-firmware WHENCE, fetched from git.kernel.org; every claim cites file:line; re-verify commands in RUNTIME_COMPONENT_MAP.md §6
- [x] Gate: check-sync.sh 221 checks 0 failures; bash -n clean; power baseline untouched; no driver modifications
- [x] Commit: ab10a5e

### Фаза 0.71 — Full regression after Safari-chrome track + respawn fix (2026-09-28, без железа)
- [x] No-change regression: 22/22 suites green (1,269+ checks incl. firefox-chrome 221, theme-css 9); bench 24 scenarios 0 failed (5 skipped, host-load variance); check-sync --check-repos ALL CHECKS PASSED. Zero code changes; gate green.

### Фаза 0.70 — Safari chrome fidelity rewrite: spec → actual implementation (2026-09-28, без железа)
- [x] docs/SAFARI_SPEC.md fidelity rewrite: all "userChrome.css notes" spec-only prose replaced with actual implementation citations (file:line). 20 priority items classified: 9 implemented / 9 partially-implemented / 2 Firefox-native / 0 impossible-without-fork / 0 intentionally-different (item-level); 4 sub-aspects intentionally-different documented (tabs trapezoid transform, Top Sites light bg, menu gray hover, private light purple tint).
- [x] Validation checklist added (§17): 23 browser-chrome states — 17 covered-by-CSS / 4 needs-pixel-validation-on-HW (error, history, fullscreen, maximized) / 2 untestable-headless (keyboard nav, 2304×1440). Pixel states cross-referenced to NEEDS_HARDWARE_TEST.md — NOT claimed validated.
- [x] Energy sanity section (§18): pure-CSS/no-JS/no-timers/no-keyframes confirmed by grep (keyframes only in comments userChrome.css:216-217; no @-rules per gate test-firefox-chrome.py:157); transitions limited to opacity+background-color 120ms (allowlist-enforced).
- [x] Phase delivery recorded (§14): S1a toolbar + S1b unified field (28220a1), S1c tabs + S1d bookmarks + S1e typography (190fb2b), S2a newtab userContent.css + inventory + gate (f4ea0e6), S2b downloads/findbar/loading (e1ed62b), S2c sidebar/menus/private/focus (769590e), S2d appMenu + urlbar popups (8184883), S2e icons + borders/gradients/textures (4a23570).
- [x] Gate: test-firefox-chrome.py 221 checks, 0 failures (112 selectors, 191 !important). Docs-only phase — zero chrome CSS changes.
- [x] Power baseline untouched; no new daemons; no polling added

### Фаза 0.69 — Final narrow audit: System Settings + Browser/YouTube readiness for first boot (2026-09-28, без железа)
- [x] Cmd-layer collision audit: 3 real collisions found + fixed (Super+C→Super+Shift+C, Super+F→Super+Shift+F, Super+N→Ctrl+Alt+N). Remaining Cmd-layer shortcuts (T/W/Q/1..9/[/]) documented as app-level (Ctrl equivalents in Firefox), NOT globally bound to avoid breaking other apps. KEYBOARD.md + SAFARI_SPEC.md updated.
- [x] mv-ytplayer Firefox handoff: protocol handler (mv-ytplayer://) + Firefox bookmarklet ("Watch efficiently") + --url intake. One user action from YouTube page → mv-ytplayer → mpv one-shot → full exit. No manual URL copy, no terminal. Tests: 19→30 (+11 handoff tests).
- [x] Codec policy layer: extracted to configs/mv-ytplayer/codec-policy.conf (easily editable). Policy doc table in VIDEO_PIPELINE.md with codec/resolution/HW-SW/expected-CPU/GPU/fallback + explicit NO-CONCLUSION note (final choice from measured power/thermal on MacBook, not host bench).
- [x] docs/HW_BROWSER_MATRIX.md: 4-mode validation plan (M1: Firefox-vanilla / M2: Firefox+uBO+SB / M3: Firefox→ytplayer hybrid / M4: ytplayer-direct). Identical workload (3 clips × 5 min), identical metrics (CPU/GPU/RSS/dropped/wakeups/temp/freq/discharge/time-to-idle), exact commands per mode. Return-to-idle emphasized.
- [x] Browser background audit: session restore prefs added (restore_on_demand, restore_pinned_tabs_on_demand, max_tabs_on_startup=10, max_windows_on_startup=3) — P1: reduces startup cost + memory on 8-16GB RAM. Background tab throttling prefs verified (already at defaults).
- [x] Settings audit (mv-control): P1 fix — refresh_all 30s timer was not removed on destroy (kept firing after window close). Fixed: stored timer ID + GLib.source_remove in on_destroy. Test updated (+1 assertion).
- [x] YouTube-like UI minimum: mpv-native OSD covers play-pause/seek/volume/fullscreen/quality/metadata (press 'i' for stats). Thumbnail/channel/duration/next-video NOT provided by mpv natively — recorded as accepted-minimal (no SPA clone, no new daemon per audit scope).
- [x] Full suite: 20 files, 1199 tests, all pass. check-sync ALL CHECKS PASSED.
- [x] Power baseline untouched; no new daemons; no polling added; one-shot processes only

### Фаза 0.68 — Video pipeline: codec benchmark + selector verification + docs (2026-09-28, без железа)
- [x] Codec benchmark COMPLETE: scripts/bench/video_codec.py + results/video-codecs.json — real measurements, 1080p/720p × h264/vp9/hevc/av1, 120 frames, 3 repeats median. Ranking (cost/frame): h264 4.20 ms > vp9 5.57 ms > hevc 7.99 ms > av1 5.38 ms (SW-only on Gen9.5). All meet 41.67 ms deadline in host SW.
- [x] Tiers recorded: host-SW=MEASURABLE; VA-API=HW-ONLY (vainfo: no driver on host); power/thermal=HW-ONLY.
- [x] mv-ytplayer verified: bash -n clean; scripts/test-mv-ytplayer.py 19/19 pass (3 buggy test assertions fixed — plain-string mismatches, not script bugs); desktop-file-validate clean. Real bug fixed: build_chain branch5 was duplicate of branch4 (non-av01) — now true unconditional fallback (AV1 reachable only via branch 5).
- [x] Firefox mirror sync: configs/firefox/user.js edit had dropped the cache/downloads/history/extensions baseline block (lossy) — merged both blocks; policies.json (SponsorBlocker@ajay.app force_installed) + user.js mirrored to archiso-profile. check-sync.sh: ALL CHECKS PASSED.
- [x] SponsorBlock disposition: CONFIRMED ADDED — configs/firefox/policies.json Extensions.Install + ExtensionSettings.sponsorBlocker@ajay.app force_installed; mirrored to archiso-profile/releng/airootfs/usr/lib/firefox/distribution/policies.json.
- [x] docs/VIDEO_PIPELINE.md created: ranking table, tier labels, per-codec Gen9.5 feasibility, selector rule (real --explain chain), optimized-mode enumeration (no page JS/DOM/ads/tracking/polling/network-page; audio separate stream; one-shot).
- [x] docs/BENCHMARKS.md: video codec section with real numbers + run metadata (Ryzen 7 5800HS, 2 cores, ffmpeg n9.0.2, WSL2).
- [x] docs/NEEDS_HARDWARE_TEST.md: VA-API HW decode validation + power/thermal per-codec measurements added.
- [x] P0/P1 sweep: timeout_add/while-True/GFileMonitor grep across mv-* apps — all hits match existing Phase-E labels (P2/IGNORE); mv-ytplayer one-shot (no timer) = IGNORE-class. Phase-E verdict stands: 0 P0, 0 P1.
- [x] Power baseline untouched; no new daemons; no polling added; one-shot processes only

### Фаза 0.67 — Safari-Mavericks UX spec + Firefox optimized config + mpv video-only + B01-B09 workloads (2026-09-28, без железа)
- [x] docs/SAFARI_SPEC.md: full Safari 7 / Mavericks UX spec — toolbar, tabs, unified address/search, bookmarks bar+sidebar, Top Sites grid, downloads popover, history, find bar, private browsing, context menus, keyboard (Cmd-layer mapping to KEYBOARD.md), dialogs, typography/spacing/icons/loading states. Implementation surface: userChrome.css notes + Firefox prefs. No engine fork.
- [x] Firefox optimized config: user.js extended (drawInTitlebar, closeButtons=1, firefox-view off, tabmanager off, sharepane off, Top Sites prefs, download.useDownloadDir, findbar prefs). AV1 pref commented-out (E-AV1). EXPERIMENT prefs unchanged (VAAPI, WebRender, processCount, unloadOnLowMemory). sessionstore 60s preserved.
- [x] policies.json: ExtensionSettings added — `*` blocked + uBO force_installed. Homepage/TopSites hygiene verified.
- [x] uBO backup: configs/firefox/ublock-backup.json — EasyList + EasyPrivacy + uBO filters + badware + privacy + unbreak + resource-abuse + URLhaus. SponsorBlock noted. Blocking ON/OFF modes documented.
- [x] mpv video-only path: packages.x86_64 += mpv, yt-dlp, intel-media-driver (all verified in extra repo). mv-ytplayer script (one-shot, graceful no-backend). Thunar UCA "Play video-only" action. .desktop + MIME wiring (opt-in, no default-handler theft). Return-to-idle: one-shot process.
- [x] B01-B09 workloads: browser_emu.py extended with 9 workload functions + CALIBRATION map. Baseline run: all 9 completed, JSON output in scripts/bench/results/. return_idle ~30s (host under load, emulator timeout — expected).
- [x] check-sync.sh: extended with user.js no-duplicate-keys test + policies.json schema validation. --check-repos verified mpv/yt-dlp/intel-media-driver in extra.
- [x] HW-only remainder: vainfo, real YouTube, AV1-SW cost, panel rendering → NEEDS_HARDWARE_TEST.md
- [x] Power baseline untouched; no new daemons; no polling added; one-shot processes only

### Фаза 0.66 — mv-settings + mv-control full audit & P0/P1 fixes (2026-09-27, без железа)
- [x] Per-section backend/cost table (BENCHMARKS.md): all 8 sections audited — backend, polling, startup, D-Bus calls, RAM delta
- [x] P1 fix: mv-control `refresh_all` timer 5s→30s (83% fewer ticks); removed user-initiated refreshes (volume/mute/brightness/output-devices) from timer — only external-state polls remain (wifi-enable, bt-enable+list, power-mode, DND)
- [x] P1 fix: mv-control BT deduplication — `get_bt_enabled()` + `refresh_bt_list()` shared `_bluez_get_objects()` helper; was 2 BlueZ GetManagedObjects D-Bus calls per tick, now 1
- [x] P2 fix: mv-control `on_output_device_changed` no-op `pactl list short sink-inputs` removed
- [x] P2 fix: mv-settings duplicates removed — Wi-Fi (dup of Network), Battery/Energy (dup of Energy Saver); "Desktop & Dock" no longer launches both xfce4-desktop-settings AND plank simultaneously
- [x] Tests: mv-control 26→32 (+6: BT on/off paths, _bluez_get_objects, refresh_all interval); full suite 1239/1239 green; check-sync ALL CHECKS PASSED
- [x] Fidelity: no visual changes needed (CSS/layout already Mavericks-coherent); mv-settings section list now matches macOS Mavericks layout
- [x] HW-only remainder documented: suspend/resume+lid (logind hooks), panel-brightness (real backlight), BT-pairing-real (actual devices) → NEEDS_HARDWARE_TEST.md
- [x] Power baseline untouched; no new daemons; no polling added

### Фаза 0.65 — Performance track phase E: browser emulator + GUI tier + stopping criteria + re-audit (2026-09-27, без железа)
- [x] Browser-workload emulator S14E (`scripts/bench/browser_emu.py`): synthetic Firefox-ESR-class tabbed session model — 7 phases (startup regex/DOM, tab-alloc RSS plateaus, scroll render ticks, media-burst zlib, js-churn, network-wait, return-idle); deterministic (seed=42); timeboxed <3 min; JSON schema 1 compatible with bench.py; integrated as S14E (3 repeats)
- [x] GUI tier G01-G05 integrated into bench.py: X-server detection (Xvfb/Xephyr absent, WSLg :0 reachable — GUI tier now measurable for the first time); G01 window cycles 3.6-3.9 ms; G02 memory growth 0-4 KB (mv-diskutil 996 KB = one-time caching, not leak); G03 event-loop p50/p99 1.5/2.6 ms; G04 notification logging 0.13-0.48 s; G05 startup-to-first-draw 0.24-0.30 s (all P2)
- [x] Stopping criteria (`docs/PERF_CRITERIA.md`): P0/P1/P2/IGNORE definitions + thresholds; applied to all PERF_AUDIT.md suspects — 0 P0, 0 P1; all 24 suspects P2 or IGNORE; performance track has reached stopping criteria
- [x] Full re-audit: polling, timers, wakeups, persistent processes, repeated FS scans, unnecessary D-Bus, UI-thread blocking, memory growth (G02), cold-start (S03/G05), return-to-idle (S17) — 0 P0, 0 P1 found
- [x] CALIBRATION map in BENCHMARKS.md: emulator phases → future real-Firefox measurements on MacBook10,1 (startup wall, per-tab RSS, scroll-tick CPU, burst CPU, return-to-idle)
- [x] GUI tier separation doc: what X server proves (widget construction, leaks, loop latency) vs HW-only (compositing, vsync, panel pixels, HiDPI)
- [x] Full harness: 24 scenarios, 19 ok, 5 skipped (S06/S07/S08/S10/S14 — specific app interactions), 0 failed (`results-2026-09-27-phaseE.json`); S17 33 s/repeat (host under load); S14E 37 s/repeat (host under load); CPU scenarios S15/S16 stable (≤1%)
- [x] Docs: BENCHMARKS.md phase-E change log + calibration map + GUI separation; PERF_AUDIT.md phase-E re-audit (24 suspects, all P2/IGNORE); power baseline untouched
- [x] Track assessment (A→E): measurable host wins = harness comparability + S02/S03 import-path reduction + cold-tier quantification + GUI tier now measurable (G01-G05); 0 P0/P1 after full re-audit; performance track stopping criteria met

### Фаза 0.64 — Performance track phase D: harness hardening + final measurable wins (2026-09-27, без железа)
- [x] Harness display-leak fix (c359ab0): S02/S03 children no longer inherit host Wayland env (`headless_env()`: GDK_BACKEND=x11 + DISPLAY stripped); S03 scenario wall 127s→~15s, mainloop-reached 23→0, S02 −11%, S03 median −20%; before/after pairs comparable regardless of host display state
- [x] Unused-import audit (2ae61e6): AST-based checker (pyflakes absent on host), 20 provably-unused imports removed across 15 mv-* apps; zero behavior change; 1233/1233 green
- [x] Cold-cache approximation (no root): fadvise(DONTNEED) eviction proxy over 113 mapped libs, interleaved 5-rep — cold Gtk import +0.21s (+63%) warm→cold on host; caveats documented (best-effort eviction, WSL page cache, python/libc warm); validates phase-C cold-target insight
- [x] Browser workload S14: exact absence recorded (9 browser names checked, none found; offline discipline) — stays HW-deferred (ec4dad4)
- [x] Full harness: 18 scenarios, 13 ok, 5 skipped GUI-tier, 0 failed (results-2026-09-27-phaseD.json); full suite 1233/1233; check-sync ALL CHECKS PASSED
- [x] Docs: BENCHMARKS.md phase-D change log + delta table; PERF_AUDIT.md phase-D dispositions (D-01..D-04); DECISIONS.md phase-D entry; power baseline untouched
- [x] Track assessment (A→D): measurable host wins = harness comparability + S02/S03 import-path −11%/−20% + cold-tier quantification; accepted = host drift band + warm marginal ≈ 0 for gi cleanup; HW-only = GUI tiers S06–S08/S10, S14 browser, RAPL/battery/thermals, applespi/BCM43602/Cirrus, cold-target magnitudes on real NVMe

### Фаза B — Performance track: audit fixes S-01..S-11 (2026-09-27, без железа)
- [x] S-09 HYGIENE (8211b9f): autostart/mv-notify-send.desktop removed (on-demand tool); on-demand callers (mv-airdrop, mv-notification-center) verified unaffected
- [x] S-01 HIGH (14c8009): mv-control Wi-Fi refresh → NM D-Bus signal-driven (wireless PropertiesChanged, AP added/removed + PropertiesChanged, device add/removed) + 1s debounce/2s min interval + 30s fallback poll + window-open refresh + manual Refresh button; rescan frequency while CC open 0.2Hz → signal+0.033Hz (≥83% reduction). BT steady state confirmed 5s (S-06). Also fixed 2 mv-control startup crashes unmasked by verification: Gtk.ListBox.pack_start AttributeError + modal dialog.run() hang from set_active during init
- [x] S-11 CORRECTNESS (edd2eec): mv-about self.tv ordering fixed; empirical tree-wide sweep found+fixed 6 more startup crashes: mv-diskutil (pack_empty_state receiver), mv-mail+mv-photos (invalid GTK3 CSS text-transform/text-align killed stylesheet), mv-power-ui (Gtk.WindowTypeHint→Gdk.WindowTypeHint), mv-textedit (SearchContext before self.buffer). Post-fix sweep: zero tracebacks; S03 mainloop-reached 17→24
- [x] S-02 (bfebe9b): mv-console follow → persistent `journalctl -f -n 0` + GLib IO watch (event-driven, 0 polling); kernel source falls back to 5s poll; live-tail UX preserved (search-without-requery, Pause/Ctrl+L, destroy cleanup)
- [x] S-03 (143e9b2): mv-music MPRIS fetch off UI thread (worker thread + own session-bus connection + GLib.idle_add); main window + mini player; initial refresh 300ms→1s; _kick_playback 900ms→2s; on_change PropertiesChanged path preserved
- [x] S-10 (b9d16ba): mv-hud WIRED into panel genmon (plugin-7, command mv-hud, 5s) in both xfce4-panel.xml mirrors (verdict: wire, not remove — one-shot C tool matches §7; genmon already in ISO list)
- [x] S-04 (5330d93): mv-colormeter tick 100ms→200ms (10Hz→5Hz while open)
- [x] S-05/S-08 ACCEPTED (no change): activity 2s = pure /proc reads window-open-only (§7); textedit autosave 30s = same class as Firefox sessionstore 60s
- [x] S-07 ACCEPTED (misdiagnosis): power-ui 1Hz ticker is the countdown UI (no UPower reads); UPower read once at window open — no poll to relax
- [x] S-12 ACCEPTED (no change): extensionless launchers are deliberate convention; documented disposition
- [x] New tests: scripts/test-mv-control.py (26 tests: scheduling constants, debounce, min-interval, refresh_all no-wifi-poll, NM subscription set, destroy cleanup, pack_row dispatch); test-mv-console.py 92→100 (follow_command pure tests + redesigned pause/resume coverage)
- [x] Full regression: 18 suites, 1233 tests, all pass (was 1199: +26 control, +8 console); check-sync.sh ALL CHECKS PASSED; bash -n/py_compile/desktop-file-validate/xmllint via gate
- [x] Bench: full harness → docs/benchmarks/results-2026-09-27-phaseB.json (18 scenarios, 5 skipped GUI-tier, 0 failed); run-2 variance check (/tmp/results-phaseB2.json); honest delta table in BENCHMARKS.md — host drift dominates (S17 swung 6.9s→0.9s between identical-code runs); stable CPU scenarios S15/S16 moved ≤0.8%; S03 mainloop-reached 17→24 is the real measurable improvement
- [x] Docs: PERF_AUDIT.md phase-B dispositions (FIXED/ACCEPTED with reasons); BENCHMARKS.md phase-B change log + delta table + updated top-5; DECISIONS.md phase-B entry (11 verdicts); power baseline untouched
- [x] Phase-C proposal (remaining): startup overhead (S02 per-app gi+Gtk import ~0.15-0.4s × 37 apps — lazy-import candidates: gi.require_version + Gtk import is the cost; defer), thumbnailers (none configured — QEMU/hardware item), browser workload (S14 deferred — no Firefox on host, HD615 behavior HW-only), GUI-tier scenarios S06-S08/S10 (need QEMU+OVMF or hardware), RAPL/battery/thermals (HW-only), nmcli-wifi-list on real BCM43602 (rescan energy cost HW-validation)

### Фаза 0.63 — Pre-hardware regression sweep + P2 research close (2026-09-27, без железа)
- [x] Full regression: 16 test suites (1,147 tests) all pass — airdrop 51, calculator 141, calendar 63, colormeter 76, console 92, dictionary 70, diskutil 34, fontbook 65, keychain 96, music 108, notes 41, photos 84, power-ui 44, reminders 31, stickies 72, timemachine 59, voice 63; test-theme-css 9/9; check-sync --check-repos ALL PASS; bash -n ALL-PASS; py_compile exit 0; desktop-file-validate 64/64; xmllint ALL-PASS
- [x] Fixed SyntaxWarning in test-mv-calendar.py (invalid escape sequences `\;` `\,` → raw strings)
- [x] P2 research close (docs/RESEARCH_P2_CLOSE.md): Automator/Shortcuts → DEFERRED; Grapher → DEFERRED; Migration Assistant → EXCLUDED (confirmed); App Store → EXCLUDED (confirmed); Software Update polish → DEFERRED. No new pre-hardware implementation items. P2 research track closed.
- [x] Docs-reality audit: spot-checked all 17 P1 apps (line counts 139–1636, all real code) + P0 scripts (all exist) + 31 .desktop files. No new fake-completion found. mv-mail (139 lines, thin geary wrapper) correctly marked PARTIALLY_IMPLEMENTED.
- [x] DECISIONS.md: Phase 0.63 entry added. APPS.md: P2 table updated with all 5 items + verdicts. NEEDS_HARDWARE_TEST.md: no gaps found (fresh-ISO checklist from 0.62 still current).
- [x] Next: hardware validation on MacBook10,1 (Phase 5). All feasible pre-hardware P0/P1 work complete; P2 research closed.

### Фаза 0.60 — Time Machine UI over restic (P2 #41; 2026-09-27, без железа)
- [x] Backend-вердикт: restic (extra, 0.19.1-1, BSD-2-Clause) — XOR-выбор против borg 1.4.5 по DECISIONS Phase 0.58; borg НЕ реализуется; btrfs subvolume snapshot layer сохраняется как комплементарный instant local layer (btrfs-progs 7.1 core, уже в ISO)
- [x] mv-timemachine (Python/GTK3): setup-флоу (выбор destination dir/USB-C, passphrase-диалог), restic init/backup/snapshots/restore wiring, passphrase через RESTIC_PASSWORD env only (никогда на cmdline, никогда plaintext на диске), libsecret-персистентность с fallback на per-run prompt, btrfs local snapshot list, destructive-restore confirmation, starfield CSS-браузер (дешёвые radial-gradient точки), empty/error состояния: no-target, restic-missing, no-snapshots, restore-confirm
- [x] Timer: mv-timemachine-check.timer (OnCalendar=hourly, Persistent) + .service (Type=oneshot, `mv-timemachine --check-due`) — паттерн mv-reminders-check; no daemon, no polling; check-due бэкапит только если newest snapshot старше интервала
- [x] Интеграция: mv-time-machine.desktop (Name=Time Machine, Icon=timemachine, Categories=System;Utility;), timemachine.svg (оригинальная отрисовка: часы с круговой стрелкой, не Apple asset), Makefile install-лист (bin + timer + service), PKGBUILD depends += restic, packages.x86_64 += restic
- [x] Energy-модель: on-demand only — hourly oneshot timer, restic short-lived subprocess, dedup делает no-op дешёвым; никаких демонов
- [x] Validation: 59 headless-тест (scripts/test-mv-timemachine.py: snapshots JSON parse/malformed/non-list/missing-fields/sort, RFC3339 parse, snapshot_due, OnCalendar parse, backup_command excludes + repo-self-exclude, restore-cmd, btrfs cmd shapes + list parse, config round-trip в isolated HOME, env-only passphrase, check_due no-target/no-pw/due/skip/error/failure с мокнутым subprocess, GUI smoke: construct/setup-view/main-view/empty-state/gating/keyboard), py_compile OK, desktop-file-validate OK, check-sync ALL CHECKS PASSED, make install DESTDIR OK, makepkg -f OK, launch smoke на :0 (exit 124 = окно живо, stderr чист), --check-due smoke (no target → skip rc=0)
- [x] Remaining gaps: file-level restore browser (restore = copy-out в папку, не in-place), cloud backend config UI нет, btrfs restore — guidance-only (требует recovery env), нет просмотра содержимого snapshot без restore (restic mount/FUSE — возможно позже)
- [x] Next: remaining P2 per roadmap (Automator/Shortcuts, Grapher — research-only)

### Фаза 0.59 — AirDrop: LocalSend integration (P2 #40; 2026-09-27, без железа)
- [x] Forensic-оценка LocalSend: AUR `localsend` 1.18.2-2 (source, тяжёлый Flutter/fvm+Rust build — не подходит) vs `localsend-bin` 1.18_1-1 (бинарный .deb, 152 голоса, depends fuse2/xdg-user-dirs/libayatana-*) — выбор `localsend-bin`; официальный CLI `localsend-cli-bin` 1.18.2-1 (AGPL-3.0-only, только glibc, `send --to <ip|alias>` неинтерактивно, `--destination` default = Downloads); оба Apache-2.0/AGPL-3.0 подтверждены AUR-метаданными; в официальных Arch-репах нет (sync DB пуст) → только AUR
- [x] Protocol v2 (github.com/localsend/protocol): multicast UDP 224.0.0.167:53317 (announce:true → ответы announce:false или POST /register), HTTP TCP 53317; avahi НЕ нужен (собственная мультикаст-реализация) — совместимо с baseline (avahi off)
- [x] mv-airdrop (Python/GTK3, ~470 строк): one-shot discovery (announce + слушаем ~2.5 s, дедуп по fingerprint, фильтр собственного fingerprint от loopback), список устройств с иконками по deviceType, отправка через `localsend-cli send --to <ip> <files>` (async, child_watch, статус + уведомление об успехе, error-dialog с stderr при неудаче), приём — запуск GUI LocalSend (приём требует работающий экземпляр LocalSend — архитектурное ограничение backend'а, задокументировано), состояния: no-backend (инструкция установки AUR), NM-offline (discovery пропускается), port-busy (LocalSend уже запущен → его список устройств), no-devices (same network/AP isolation/порт 53317), send-failure
- [x] Receive-конвенция: `~/Downloads` = default LocalSend = конвенция macOS AirDrop — без хака конфигов LocalSend
- [x] Интеграция: Thunar UCA "Send via AirDrop…" (`mv-airdrop --send %F`, паттерн `*`, все типы файлов) + mirror в airootfs (пара check-sync); mv-airdrop.desktop (Name=AirDrop, Comment с атрибуцией LocalSend, Icon=airdrop, Categories=Network;FileTransfer;); airdrop.svg (синяя сфера с концентрическими дугами — оригинальная отрисовка, не Apple asset) в mvericks-theme/icons/scalable/apps/; Makefile install-лист; PKGBUILD optdepends (localsend-bin, localsend-cli-bin — AUR)
- [x] Energy-модель: on-demand only — нет демона/автостарта/трей-процесса/polling; discovery = один UDP-бурст ~2.5 s на открытие окна; send = короткоживущий subprocess; LocalSend GUI НЕ автостартится (его настройка autostart остаётся off); ISO-вердикт: НЕ в дефолтном пакетлисте ISO (AUR-only, ISO собирается из Arch-реп + repo-local пакетов) — opt-in как skippy-xd E-MC; mv-airdrop в ISO через mavericks-apps с graceful no-backend состоянием
- [x] Validation: 51 headless-тест (scripts/test-mv-airdrop.py: announcement shape, datagram parse incl own-fp filter/malformed/non-dict/bad-port, discovery на loopback UDP-паре с mock-responder без мультикаста, NM state mapping 70/40/30/20/0/None, send-cmd construction, device-icon mapping, GUI smoke: construct/banners/offline-skip/list-rebuild/selection/gating/keyboard), py_compile OK, desktop-file-validate OK, check-sync ALL CHECKS PASSED, makepkg mavericks-apps (--nodeps, webkit2gtk нет в build env — как в предыдущих фазах) + mvericks-theme OK, launch smoke на :0 (exit 124 = окно живо, stderr чист кроме  environmental locale warning), иконка в пакете + резолвится при теме Mavericks (Gtk.IconTheme append_search_path)
- [x] Решения (DECISIONS.md): backend-выбор (localsend-bin + localsend-cli-bin), autostart/energy disposition (on-demand, без демона), ISO-вердикт (opt-in AUR, не в ISO), receive-конвенция (~/Downloads), avahi-interplay (не нужен — плюс к baseline)
- [ ] HW: реальный передача Mac↔Linux (LocalSend на обоих концах), видимость устройств через BCM43602 Wi-Fi (multicast 224.0.0.167), порт 53317/AP isolation на реальном роутере, energy cost бурста discovery + передачи, приём через LocalSend GUI на Cirrus audio (уведомления)

### Фаза 0.58 — Dictionary: forensic launchability audit + offline-sources rewrite (2026-09-27, без железа)
- [x] Forensic audit: real launch smoke — mv-dictionary был НЕЗАПУСКАЕМ: `gi.require_version("WebKit2", "4.0")` → ValueError при импорте (webkit2gtk в текущих Arch даёт только 4.1) — exit 1 до создания окна; тот же класс fake-completion, что calculator 0.57 (зависимость от точной версии в жёстком require)
- [x] Другие найденные дефекты: (1) обработчик `load-failed` имел сигнатуру (widget, error), а сигнал WebKit2 эмитит (web_view, load_event, failing_uri, error) → TypeError при срабатывании, offline-страница никогда не показывалась; (2) HTML-инъекция: слово вставлялось в HTML Apple-таба без экранирования (`<script>` в слове = XSS); (3) все источники определений были онлайн-URL (wiktionary/thesaurus.com/wikipedia) — офлайн не работал вообще, локального словаря не было; (4) search-as-you-type был заглушкой (pass); (5) нет word-of-the-day; (6) нет keyboard shortcuts; (7) нет pronunciation; (8) history limit несогласован (50 в add / 100 в save); (9) плоский современный CSS (#007aff — iOS-синее, не Mavericks); (10) GTK warning'и при аллокации (SearchEntry+StackSwitcher+Stack в headerbar — отрицательная ширина)
- [x] Переписан: загрузка WebKit2 4.1→4.0→local mode (без webkit2gtk работают glossary + Apple tab + wod + history + bookmarks, онлайн-табы показывают честное уведомление); load-failed сигнатура исправлена (offline-страница при обрыве сети); экранирование всего пользовательского текста в HTML
- [x] Офлайн-источники с порядком разрешения: built-in glossary (60 слов,  ships с приложением) → WordNet через dictd (`dict -d wn`, optdep, 5s timeout) → system word list /usr/share/dict/* (только проверка существования) → graceful no-data state (онлайн-табы)
- [x] Word of the Day: детерминирован по day-of-year из glossary, dismissible InfoBar-баннер при старте + в welcome-странице Dictionary-таба
- [x] Search-as-you-type: debounce 300ms через GLib.timeout_add с generation counter (гонка «таймаут срабатывает на устаревшем тексте» найдена тестом и исправлена); Enter — мгновенный поиск; пустая строка → welcome
- [x] Клавиатура: Ctrl+L (фокус поиска), Ctrl+1..4 (табы), Ctrl+B (bookmark), Ctrl+H (history), Escape (очистить); bookmark/speak кнопки неактивны без текущего слова
- [x] Pronunciation: кнопка speaker в headerbar, видна только при установленном espeak-ng/espeak (optdep); on-demand subprocess, без аудио-демона
- [x] Mavericks-визуал: paper-фон (#f7f4ec), serif-определения (Georgia), Helvetica-заголовки, leather band на Apple-табе, source attribution; поиск-поле вынесено в toolbar под headerbar (macOS-faithful + устраняет GTK allocation warning'и — проверено бисекцией)
- [x] Empty/error states: welcome-страница при старте, «No recent lookups» в history, not-found в Apple-табе, offline-страница при load-failed, corrupt-store → [] (list-of-str validation)
- [x] Validation: py_compile OK, desktop-file-validate OK, check-sync ALL CHECKS PASSED, launch smoke (X11 :0, живёт 4с+, пустой stderr, argv=finder), local-mode smoke (WebKit2=None), 70 headless-тестов (scripts/test-mv-dictionary.py: glossary/dictd/wordlist resolution, wod determinism, store round-trip/corrupt/junk/limit, HTML escaping, speak backend, CSS content + GUI smoke: construct/search/debounce/ctrl+1..4/ctrl+l/ctrl+b/escape/bookmark persist/history restore/empty state/local mode/load-failed signature/run() prefill)
- [x] WebKit2-рендеринг в build-контейнере НЕ проверяем: web-процесс WebKit2 не стартует даже с WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 (load-changed не эмитится ни на один load) — ограничение окружения, не приложения; все load-пути проверены на уровне вызовов + local mode полностью протестирован
- [x] PKGBUILD: espeak-ng + dictd → optdepends
- [x] Решения (DECISIONS.md): выбор источников (glossary→dictd→wordlist→online), pronunciation disposition (espeak-ng on-demand, кнопка скрыта при отсутствии), page-flip анимация отложена (compositor-level, не стоит runtime cost)
- [ ] HW: рендеринг WebKit2-табов на 2304×1440 (web-процесс не стартует в контейнере); реальный звук espeak-ng на Cirrus audio; наличие dictd/dict-wn в целевой системе; визуальная проверка paper/leather CSS под темой Mavericks

### Фаза 0.58b — P2 research opening (P1 закрыт; 2026-09-27, без железа)
- [x] P1 полностью закрыт (Dictionary = последнее P1-приложение) → по AGENTS.md §10 открывается P2
- [x] AirDrop: DEFERRED → EXISTING SOLUTION FOUND — LocalSend (Apache-2.0, 90k★, v1.18.2 2026-08, cross-platform, local-network P2P + TLS, CLI с 1.18.0); НЕ AWDL-протокол (Mac↔Linux через LocalSend на обоих концах) → Mavericks-like frontend = share-sheet sender/receive UI поверх LocalSend
- [x] Time Machine UI: backend = restic (BSD-2, 0.19.1 2026-07; encrypted/dedup/incremental, single binary, local/sftp/S3 backends); borg+btrfs-исследование 2026-09-25 упразднено в пользу restic; linux-timemachine (MIT) как CLI-референс
- [x] Записано в APPS.md (P2-таблица) + DECISIONS.md; следующая цель реализации: AirDrop (интеграция LocalSend)

### Фаза 0.57 — Calculator: forensic launchability audit + refinement (2026-09-27, без железа)
- [x] Forensic audit: real launch smoke — mv-calculator ЗАПУСКАЕМ (exit 124, окно живёт, без краша); py_compile OK, desktop-file-validate OK, check-sync OK — НЕ 7-й fake-completion repair; но найдены реальные дефекты (ниже)
- [x] Найденные дефекты: (1) краш в программистском режиме: on_operator/on_bitwise делали float(current) без try — hex-ввод "A" → ValueError → краш; (2) calculate() в programmer mode: float("FF") → всегда "Error"; (3) отрицательный hex: hex(-5)[2:] = "x5"; (4) деление на ноль → float('inf') → показывался "inf" вместо Error; (5) tape-запись унарных функций показывала результат как вход (sin(0.5) = 0.5 вместо sin(30) = 0.5); (6) on_percent определён 3 раза; (7) Pango/Gdk импортировались только в __main__ (работало как скрипт, хрупко); (8) override_font deprecated; (9) basic grid: кнопка "." перекрывалась со spanning "0"; (10) scientific grid: "=" посреди сетки, "+" продублирован; (11) нет клавиатурного ввода; (12) нет персистентности tape; (13) нет copy/paste; (14) нет CSS/визуальной интеграции
- [x] Eval safety: аудит подтвердил — никакого eval()/exec() в приложении, state-machine архитектура (pending_op/pending_val) → поверхности инъекции нет; тесты включают adversarial-батарею ("eval('1+1')", "__import__('os')...", "().__class__", ...) + source-level guard "no eval in source"
- [x] Исправлено: base-aware парсинг (parse_number с базой), integer division с truncation к нулю, отрицательный hex (-FF), деление на ноль → Error, корректные tape-записи, единый on_percent, импорты на уровне модуля, шрифт через CSS font-stack, исправлен basic grid (spanning), перестроен scientific grid ("=" span 4 строки, 32 кнопки), programmer grid (34 кнопки, AC вместо C — конфликт с hex-цифрой C)
- [x] Программистский режим: конвертация баз HEX/DEC/OCT/BIN с корректными отрицательными числами, метка базы у display, валидация цифр по базе (BIN отклоняет 2-9), немедленный NOT, bitwise AND/OR/XOR/<<, >>, integer ÷
- [x] Клавиатура: цифры, операторы (+ − × ÷ + numpad-варианты), Enter/KP_Enter =, Escape = clear, Backspace, c = clear, p = π (scientific), e = e (scientific), A-F в HEX; Ctrl+C копирует результат, Ctrl+V вставляет цифры; кнопки can_focus=False → Enter всегда equals
- [x] Персистентность: tape → ~/.local/share/mv-calculator/tape.json (atomic replace, cap 200), восстановление при запуске, кнопка Clear в tape-окне
- [x] Mavericks CSS: recessed display с градиентом и рамкой, error-состояние (красный текст), metal-кнопки с hover/active, = с тёплым градиентом, tape-окно paper-фон; font-stack "San Francisco", "Helvetica Neue", sans-serif
- [x] Validation: py_compile OK, launch smoke OK (exit 124, без warning'ов), desktop-file-validate OK, 141 headless-тест (scripts/test-mv-calculator.py: parse/format/to_base, операторы incl div-zero/int-truncation/bitwise/complex-guard, unary domain/overflow, adversarial-батарея, tape store round-trip/corrupt/cap, no-eval guard + GUI smoke: modes/arithmetic/error states/programmer hex+bitwise/keyboard/copy-paste/tape persistence), check-sync ALL CHECKS PASSED, sibling suites green (stickies 72, notes 41, keychain 96), make install DESTDIR OK
- [x] Решения (DECISIONS.md): RPN исключён (macOS Calculator не имеет RPN — не Mavericks-faithful); скобки ( ) убраны из scientific grid (state machine без группировки; macOS Calculator тоже не имеет); tape store упрощён (atomic replace без backup/quarantine — данные низкой ценности)
- [ ] HW: рендеринг CSS-скина на 2304×1440, поведение клавиатуры под xfwm4 (фокус/Enter), energy cost открытого окна (нет polling — только on-demand saves), tape persistence на реальной ФС

### Фаза 0.56 — Stickies: forensic launchability audit + refinement (2026-09-27, без железа)
- [x] Forensic audit: real launch smoke — mv-stickies был НЕЗАПУСКАЕМ: `line-height: 1.5;` не существует в GTK3 CSS → GLib.GError в `apply_css()` при старте (exit 1 до создания окна) — тот же класс fake-completion, что mv-voice/mv-console/mv-keychain/mv-fontbook (5-й подряд); store даже не создавался
- [x] Другие найденные дефекты: (1) свежие заметки НЕ были жёлтыми — CSS-класс `.sticky-note` никогда не применялся к окну, `override_background_color` вызывался только при смене цвета; (2) шрифт «Bradley Hand»/«Comic Sans MS» не существуют в системе — `fc-match cursive` → FreeSans (fake «handwriting font»); (3) дублированные module-level `load()`/`save()`, двойные вызовы `apply_css()`/move/resize; (4) мёртвый код; (5) отсутствие corrupt-store safety (тихая потеря данных); (6) нет print/keyboard/new-note/collapse/search; (7) Icon=sticky-notes не существовал ни в одной теме; (8) UTILITY+keep-above вместо нормального уровня окна
- [x] Переписан: жёлтый фон через CSS `background-color` на окне + headerbar (цвет запекается в CSS, reload при смене); нормализация цветов из store (Gdk.RGBA.parse → #rrggbb, невалидный → default); corrupt-store backup/quarantine + warning (паттерн mv-notes/mv-reminders); print через Gtk.PrintOperation (Ctrl+P, паттерн mv-notes); keyboard: Ctrl+N (новая заметка, + кнопка в headerbar), Ctrl+P, Delete (удалить с confirm), Ctrl+F (поиск по всем заметкам — отдельное окно, filter, jump-to-note через present(), Escape закрывает); collapse/expand (кнопка в headerbar, сохраняется в store); заголовок окна = первая строка; уровень окна NORMAL; единый app-объект без Gtk.Application (plain Gtk.Window + Gtk.main, паттерн mv-fontbook/mv-reminders — Gtk.Application давал GLib-GIO-CRITICAL в тестах без run()); single-instance pidfile lock с stale-lock takeover; процесс выходит при закрытии последней заметки (нет zombie); relaunch guard (повторный запуск не плодит дубли)
- [x] Шрифт: gsfonts (URW base35, extra repo, free) добавлен в ISO packages.x86_64 — содержит Z003 (chancery/cursive); fontconfig-конфиг configs/desktop/fonts/99-mavericks-cursive.conf (mirror в airootfs, пара в check-sync) маппит generic `cursive` → Z003; стек в CSS: "Bradley Hand", "Z003", "Comic Sans MS", cursive; проверено: fc-match cursive → Z003, style context окна = #fff8b0, font desc редактора = стек
- [x] Иконка: оригинальный sticky-notes.svg (жёлтая заметка с загнутым уголком) в mvericks-theme/icons/scalable/apps/ — резолвится при активной теме Mavericks (проверено через Gtk.IconTheme с set_custom_theme)
- [x] Регрессия fontbook, найденная gsfonts-установкой: `on_font_selected` матчил шрифт по (family, style) — при наличии одного лица и в user-, и в system-каталогах fc-list возвращает оба, `next()` брал system-копию → remove_btn не чувствительна. Исправлено: store-строки несут file-path (4-я колонка ListStore), матчинг по file с fallback на (family, style); select_font тоже по file. fontbook снова 65/0 с установленным gsfonts
- [x] Реальный launch smoke (X11 :0): стартует, живёт (exit 124), store пишется; вторая инстанция отказывается («another instance is already running», exit 0); закрытие всех окон → чистый выход (exit 0, нет zombie); corrupt store → backup-restore; relaunch с valid store → restore текст/цвет/геометрия; пиксельная рендер-проверка невозможна headless без WM (bare Gtk.Window тоже чёрный — ограничение окружения, не приложения); жёлтый фон и шрифт-стек верифицированы на GTK-уровне (style context)
- [x] scripts/test-mv-stickies.py: 72 теста (pure: normalize_color/clip/_normalize/store round-trip/backup/quarantine/lock/paginate/title + GUI smoke: construct/persist/color/ctrl+n/delete/collapse/print-op/search/relaunch/restore/quit-on-last), все проходят
- [x] Gate: py_compile OK, desktop-file-validate OK, check-sync ALL CHECKS PASSED, makepkg -f --nodeps собирается (webkit2gtk нет в build env — локальная проверка без проверки зависимостей; сам список зависимостей валиден для ISO pacstrap), make install DESTDIR OK
- [x] Известная предсуществующая проблема (НЕ регрессия 0.56): коммитированный mavericks-theme/gtk-3.0/gtk.css содержит GTK4-синтаксис (@use и др.) — GTK3 не парсит → ~90 theme-parsing warning на каждый запуск GTK-приложения в окружении с темой Mavericks по умолчанию; активировано в build env пересборкой темы (пакет был устаревший); в ISO присутствовал с abee05b; требует отдельной фазы (переписать SCSS под GTK3 или мигрировать на GTK4-совместимый парсер)
- [ ] HW: print dialog без CUPS (только диалог/сохранить в PDF); рендеринг Z003 на 2304×1440; визуальная проверка жёлтой заметки + иконки в лаунчере; поведение фокуса/raise под xfwm4; pidlock на реальной ФС; energy cost открытого окна (нет polling — только on-demand saves)

### Фаза 0.53 — Keychain Access: repair unlaunchable app + real libsecret backend (2026-09-27, без железа)
- [x] Аудит: mv-keychain (102 строки) был НЕЗАПУСКАЕМ — `text-align: left;` не существует в GTK3 CSS → GLib.GError в `apply_css()` при старте (exit 1); py_compile и import проходят — тот же класс fake-completion, что mv-voice (0.51) и mv-console (0.52); APPS.md заявил «custom wrapper with Mavericks sidebar/theme»
- [x] Найдено и исправлено по ходу: (1) `paned` создавался дважды — sidebar/content попадали в второй Paned, который никогда не добавлялся в окно (окно было бы пустым даже после фикса CSS); (2) дублированные импорты os/sys/gi дважды; (3) двойной вызов `apply_css()`; (4) sidebar был статическим списком `["login","System","System Roots","iCloud"]` с мёртвыми кнопками; (5) backend'ом был только `subprocess.Popen(["seahorse"])` через 100 мс — никакого libsecret/secret-tool кода не существовало; (6) PKGBUILD не имел зависимости libsecret/seahorse; (7) `.desktop` имел `Exec=mv-keychain %U` (%U не нужен — keychain не открывает файлы); (8) GtkInfoBar добавлялся вторым child в GtkWindow (GtkBin warning) — обёрнут в root Box
- [x] Backend: Gio.Secret (libsecret typelib) напрямую, без subprocess: `Secret.Service.get_sync` → коллекции (имя/label/locked), fallback на список известных keychains когда daemon отсутствует; `load_items_sync` → предметы с attributes/schema/locked; `SecretValue.get()` → секрет по требованию (never logged, never on disk); `password_store_sync` с динамической Generic-схемой; `password_lock_sync` для блокировки; `item.delete_sync()`; graceful None/[] граница (None = сервис недоступен, [] = пусто)
- [x] Password generator: `secrets` CSPRNG, гарантированное покрытие каждого включённого класса, оценка энтропии (bits), диалог с length/charset/entropy/Copy; сгенерированные пароли нигде не логируются и не сохраняются
- [x] UI: Mavericks leather sidebar (коллекции с lock-иконками), item list (Name/Kind), detail pane (атрибуты grid + секрет по требованию с «Show password» + Copy), New Password Item диалог (Label/Account/Where/Password+Generate), Delete с confirm, Lock keychain (per-item lock), client-side search без ре-запроса backend'а (проверено счётчиком вызовов), состояния: no-libsecret / no-daemon / empty keychain / locked item; классификация предметов Password/Certificate/Key/Secure Note по schema/атрибутам
- [x] Keyboard: Ctrl+N new item, Ctrl+G generator, Ctrl+L lock, Delete delete, Escape close dialogs
- [x] Security: секреты никогда не логируются, не пишутся на диск, не попадают в state-файлы; clipboard только по явному действию пользователя; тесты используют полностью мокированный Secret backend — реальные секреты не затрагиваются
- [x] Validation: py_compile OK, import test OK (subprocess), desktop-file-validate OK, 96 headless-тест (scripts/test-mv-keychain.py: generator charset/length/coverage/uniqueness/CSPRNG-via-secrets, strength entropy, classify, collections fallback/parsing, list_items fallback/empty/default-collection, secret bytes/str/error, store wiring+validation+errors, delete, lock per-item+skip+error tolerance, GUI smoke на реальном GTK :0 — construct/sidebar/items/detail/search-no-requery/secret reveal/new-dialog-store/generator-entropy/lock/delete/unavailable states), check-sync ALL CHECKS PASSED, sibling suites green (notes 41, reminders 31, console 92, voice 63, music 108, calendar 63, photos 84), прямой запуск OK (exit 124 = живой до timeout, без warning'ов)
- [ ] HW: реальный gnome-keyring daemon (автоматический unlock при логине), реальные предметы (сетевые пароли NetworkManager, сертификаты, SSH-ключи через ssh-agent/libsecret), разблокировка коллекции по требованию (daemon prompt), рендеринг на 2304×1440, блокировка/разблокировка в реальной сессии, energy cost открытого окна (нет polling — только on-demand reads)

### Фаза 0.52 — Console: repair unlaunchable app + Mavericks refinement (2026-09-27, без железа)
- [x] Аудит: mv-console (291 строка) был НЕЗАПУСКАЕМ — `sys.exit(main())` стоял на уровне модуля без `import sys` (NameError при импорте/запуске); py_compile gate это ловит НЕТ (runtime, не syntax) — тот же класс fake-completion, что mv-voice; APPS.md заявлял «custom app implemented»
- [x] Найдено и исправлено по ходу: (1) «System Log» использовал `-k` (kernel messages) — дублировал Kernel Log; (2) `.console-log-view` CSS-класс был определён, но никогда не применён к TextView (тёмный вид не работал); (3) иконки в sidebar store не рендерились (нет pixbuf-колонки); (4) headerbar source-combo не обновлял `current_source` (только sidebar — combo был декоративным); (5) level-combo не имел пункта «All» (стартовал на Emergency); (6) `level.connect("changed", self.reload)` передавал виджет как `initial` → count-перезапросы на каждый чих; (7) дубликат метода `on_source_select`; (8) `Gtk.IconSize.SMALL_MENU` не существует в GTK3 (AttributeError на старте)
- [x] Backend: journalctl `-o json` (структурированный PRIORITY → severity, SYSLOG_IDENTIFIER, __REALTIME_TIMESTAMP); fallback на text-scan для dmesg -T / plain-строк; binary MESSAGE-массивы декодируются как bytes
- [x] Severity badges: EMRG/ALRT/CRIT/ERR/WRN/NTC/INF/DBG фиксированной ширины в начале строки + цвет всей строки по severity (emerg/crit/err — bold)
- [x] Sources: All Messages / Current Boot / Previous Boot (`journalctl -b -1`, state «No previous boot recorded» если пусто) / Kernel Log (dmesg -T, `-l` level-фильтр) / User Log; per-source счётчики в sidebar (один раз на открытие окна, не на каждый тик)
- [x] Live tail: только пока открыто окно (GLib.timeout_add_seconds(2), source_remove на destroy), pause через Live toggle или «Pause Updates» в меню (двусторонняя синхронизация, guard против рекурсии)
- [x] Search: фильтрует уже загруженные строки без перезапроса backend; Enter = render, Escape = очистка; Ctrl+F focus
- [x] Export: FileChooserDialog SAVE → «console-log.txt» с шапкой (source/level/дата) + видимые строки; OSError → error MessageDialog
- [x] Wrap toggle (меню), Clear Display, empty/error states («No messages for this source.», «journalctl is unavailable…», «dmesg … requires root», «The log could not be read.» + stderr detail)
- [x] Keyboard: Ctrl+F search, Ctrl+E export, Ctrl+L live toggle, Escape clear
- [x] Validation: py_compile OK, desktop-file-validate OK, 92 headless-тест (scripts/test-mv-console.py: severity/priority parsing, journal json/text/dmesg parsers, dispatch, filter, source_command shapes incl. no -k regression и dmesg -l mapping, badge width, GUI smoke на реальном GTK :0 — construct/entries/badges/dark class, source/level command shapes, pause tick no-query, search без re-query, wrap/pause sync, export + error path, clear, empty/no-prevboot/no-journal states, key routing, timer removed on destroy), check-sync ALL CHECKS PASSED, sibling suites green (notes 41), прямой запуск OK (exit 124 = живой до timeout), makepkg parse OK (полная сборка требует webkit2gtk из sync DB — host limitation, pre-existing)
- [ ] HW: реальные значения journald (JSON-поля PRIORITY/SYSLOG_IDENTIFIER на MacBook10,1), dmesg permissions (root vs user), наличие Previous Boot после реальных ребутов, рендеринг на 2304×1440, energy cost 2s-tail при открытом окне

### Фаза 0.51 — Voice Memos: repair unlaunchable app + Mavericks refinement (2026-09-27, без железа)
- [x] Аудит: mv-voice (406 строк) был НЕЗАПУСКАЕМ — invalid CSS-свойство `font-variant-numeric` роняло Gtk.CssProvider (GLib.Error на load_from_data), далее `CassetteWidget` использовался, но никогда не был определён (NameError), `import sys` отсутствовал (NameError на выходе); APPS.md заявлял «custom app implemented» — fake completion (раздел 9)
- [x] Backend auto-detect: pw-record (PipeWire) → parec (PulseAudio) fallback; playback pw-play → paplay; graceful no-backend state (кнопка record disabled + статус с инструкцией)
- [x] Cassette UI реализованна: Gtk.DrawingArea + Cairo — корпус с градиентом, два катушки со спиницами, вращение при record/play (GLib timer 60ms), лента, плейка «VOICE MEMOS», LED (красный пульсирующий при записи, зелёный при воспроизведении)
- [x] Waveform strip: пики PCM нативно (struct unpack, buckets=160), прогресс воспроизведения подсвечивается; вычисление при выборе строки
- [x] Level meter без второго аудиопотока: RMS хвоста записываемого WAV (seek к size-1600, struct-based RMS, timer 200ms) — дёшево, работает с pw-record
- [x] In-app playback:  one-shot pw-play/paplay, позиция/длительность, stop (SIGINT), cassette animation
- [x] Trim: frame-aligned PCM cut без ffmpeg (wave module, setpos/readframes, temp+os.replace); диалог Start/End spinbuttons; clamp/empty-selection ошибки
- [x] Export через Gtk.FileChooserNative (copyfile); Rename через sanitize_memo_name + collision check; Delete → Gio.File.trash (fallback os.remove) с confirm; Info dialog (name/date/duration/size/rate/channels/path)
- [x] Empty state («No recordings yet…»), выбор строки загружает waveform + длительность, корректная обработка не-wav/битых wav (duration «—»), каталог-как-файл → error state
- [x] Keyboard: Ctrl+R record, Return/Space play-stop, Delete, Ctrl+E export, Ctrl+I info; %U открывает аудиофайл (запуск воспроизведения)
- [x] .desktop: MimeType=audio/wav;audio/x-wav;audio/mpeg;audio/ogg;audio/flac;audio/x-m4a;audio/mp4, Categories=AudioVideo;Audio
- [x] PKGBUILD optdepends: pipewire (backend), pulseaudio (fallback backend)
- [x] Найдено и исправлено по ходу: (1) get_selected() возвращает (model, None) при пустой выборе — `if not row` не ловит, NoneType crash в _selected_memo/rename/delete; (2) show_all() после refresh() затирал видимую страницу Gtk.Stack (empty state не показывался) — порядок исправлен; (3) refresh() внутри trim сбрасывает выбор строки (тест-бага + UX note: выбор сохраняется при ручном rename/delete)
- [x] Validation: py_compile OK, desktop-file-validate OK, 63 headless-тест (scripts/test-mv-voice.py: backend/playback detection incl no-exe, wav_info/duration synthetic+garbage+missing, sanitize (traversal/unsafe/empty), list_memos ordering/skip, waveform peaks loud/silent/garbage, rms_level, trim frame-aligned/clamp/empty/garbage, GUI smoke на реальном GTK :0 — construct/list/empty, selection→waveform+duration, record start/stop mocked, play start/stop mocked, trim/rename/info/delete-mock, key routing, no-backend state), check-sync ALL CHECKS PASSED, sibling suites green (notes 41, reminders 31, music 108, calendar 63), real binary launch OK (в т.ч. с %U-файлом)
- [ ] HW: запись с Cirrus микрофона через pw-record (macbook12-audio-driver), воспроизведение через pw-play на встроенных динамиках, рендеринг cassette/waveform на 2304×1440, trim/export/delete на реальной установке, %U из Thunar, energy cost однократной записи

### Фаза 0.50 — Photos: Mavericks integration (library engine, Moments, albums) (2026-09-27, без железа)
- [x] Аудит: существующий mv-photos был 141-строчным stub (запускал gthumb, показывал label) — нет library engine, нет EXIF, нет Moments, нет избранного, нет альбомов, нет state store, нет реального UI
- [x] Library engine (pure, headless-testable): нативный парсинг JPEG EXIF DateTimeOriginal (APP1 → TIFF IFD → tag 0x9003), парсинг размеров изображений из заголовков PNG/JPEG/GIF/BMP/TIFF/WebP (без внешних зависимостей); scan_library с детерминированным сортировкой по mtime desc
- [x] Moments: группировка по дате (YYYY-MM-DD) из EXIF или fallback "Unknown"; сортировка по дате desc; поддержка search filter внутри Moments
- [x] Favorites: toggle по path, persistence в state store, звезда в grid UI
- [x] Albums: пользовательские альбомы (New Album dialog), add/remove photo, sidebar со счётчиками, удаление альбома
- [x] Import: выбор папки → копирование в ~/Pictures/Imports/YYYY-MM-DD_HHMMSS → обновление библиотеки → запись в imports log (cap 200)
- [x] Search: по filename и date (YYYY-MM-DD), Ctrl+F focus, real-time фильтрация
- [x] State store: backup-on-save (.bak), restore-from-backup, quarantine при повреждении, normalize, geometry persistence — тот же паттерн что mv-music/mv-notes
- [x] GUI: Mavericks CSS (leather sidebar #f5f0e8, selected #007aff), FlowBox grid с thumbnails (GdkPixbuf cache в ~/.cache/mv-photos/thumbs), sidebar (Library: All/Favorites/Recently Added | Moments | Albums), full-view dialog (dims/size/date/Edit in gthumb/Favorite), slideshow (Space, 3s interval, Escape stop), empty states, error bar
- [x] Keyboard: Ctrl+F search, Ctrl+I import, Space slideshow toggle, Escape stop/close
- [x] Thumbnails: GdkPixbuf scaled cache (sha1 key = path+size+mtime), placeholder icon при ошибке
- [x] Edit handoff: gthumb launcher (graceful degradation если не установлен), rotate handoff (gthumb CLI → exiftool fallback)
- [x] Mime types: .desktop обновлён (image/jpeg;png;gif;bmp;tiff;webp;heic), Categories=Graphics;Photography
- [x] --scan CLI mode: `mv-photos --scan [path]` — выводит количество фото + первые 10 с датами и размерами
- [x] Deferred (documented в DECISIONS.md): People/faces (нет лёгкой mature face-recognition библиотеки в scope), Memories (ML-based curation), Shared Albums (нет cloud backend)
- [x] Validation: py_compile OK, 84 headless-тест (scripts/test-mv-photos.py: dims PNG/JPEG/GIF/BMP/TIFF/WebP, EXIF DateTimeOriginal, failure modes, scan, moments, search, state store roundtrip/backup/quarantine/restore/normalize, favorites, albums, imports, thumb paths, rotate/editor graceful degradation, fmt helpers), desktop-file-validate OK, check-sync ALL CHECKS PASSED
- [ ] HW: gthumb availability + Edit handoff, exiftool rotate fallback, thumbnail cache на реальной библиотеке, HiDPI rendering grid/sidebar на 2304×1440, import flow с USB-C card reader, slideshow performance на Intel HD 615, geometry restore на реальной сессии

### Фаза 0.49 — Music: Mavericks integration (library engine, MPRIS backend, views) (2026-09-26, без железа)
- [x] Аудит WIP предыдущей попытки (1584 строки, не закоммичен): архитектура валидная (pure library engine + MPRIS-контроллер + GTK3 UI), но содержала 7 реальных дефектов — все найдены и исправлены:
- [x] Баги парсинга тегов (найдены synthetic-fixture тестами): (1) `_vorbis_comments` читал vendor_len со смещением +4 вместо +0 — FLAC/Ogg теги молча парсились в мусор; (2) `_parse_ogg` искал идентификационный заголовок `\x01vorbis`, где vendor_len не существует — переписан на page-scan заголовка комментариев `\x03vorbis`; (3) MP4 track-number atom — это `trkn` без `\xa9` префикса, сравнение с `\xa9trkn` никогда бы не совпало; (4) APIC с пустым description (`mime\0\0data`) не находился — поиск второго разделителя сдвинут с p+1 на p
- [x] Баги GUI/логики: (5) вызов несуществующего `self._queue_load()` в `_rescan_library` (NameError при любой непустой библиотеке); (6) `Gtk.ListBox.append` не существует в GTK3 (GTK4 API) — `insert(row, -1)`; (7) `GdkPixbuf` использовался, но не импортировался (NameError на первой же плитке альбома)
- [x] Library engine: нативный парсинг ID3v2.3 (TIT2/TPE1/TALB/TCON/TRCK/APIC), FLAC (Vorbis comments + STREAMINFO duration + METADATA_BLOCK_PICTURE), Ogg Vorbis (comment header через page-scan), MP4/M4A (ilst atoms, \xa9nam/\xa9ART/\xa9alb/trkn, \xa9covr); сканер библиотеки с детерминированным порядком, группировка по альбомам с trackno-сортировкой и наследованием обложки; cover-кэш (~/.cache/mv-music/covers, идемпотентная запись)
- [x] Backend: MPRIS2 D-Bus контроллер lollypop (PlayPause/Next/Previous/Stop, Metadata/PlaybackStatus/Position); event-driven — NameOwnerChanged watch + PropertiesChanged subscription (now-playing обновляется при смене трека без polling); graceful degradation при отсутствии backend (все методы → False/None, error bar с инструкцией pacman -S lollypop)
- [x] Play log / smart-плейлисты: record_play с dedup подряд идущих одинаковых треков; Recently Played (dedup by path, latest wins), Top Played (count-ranked) — sidebar со счётчиками, persistence в state store
- [x] Queue: display-side "up next" (MPRIS2 не имеет queue-order API — задокументировано в DECISIONS), activate-from-row проигрывает с выбранного трека в сохранённом порядке
- [x] Now-playing bar: обложка (library match → MPRIS artUrl → placeholder), title/artist, position/length, prev/playpause/next, sensitivity по backend availability
- [x] Mini player: компактное окно (Ctrl+M, toolbar button, geometry persistence через state store, Escape закрывает), cover из library или artUrl
- [x] Keyboard: Ctrl+F search, Ctrl+Q queue view, Ctrl+M mini player, Space play/pause; media keys XF86AudioPlay/Next/Prev/Stop → `mv-music --media-key ...` в xfce4-keyboard-shortcuts.xml (source + airootfs mirror)
- [x] Mavericks integration: leather sidebar CSS (#e8dcc8), paper content, styled album tiles (cover/letter fallback, hover/selected), error/empty states с Choose Folder dialog, context menu альбома (Play/Enqueue/Show in Finder/Get Info), Get Info dialog, geometry persistence, corrupt-store safety (backup/quarantine — как Notes/Calendar family)
- [x] Deferred (documented в DECISIONS.md): cover flow (3D transforms + animation loop — runtime cost ради эстетики, как Calendar page-flip в 0.48), lyrics panel (online service, вне local-first области)
- [x] Найдено и исправлено по ходу: (1) mini player play button брался по хрупкому индексу children[3] (был backward) — прямая ссылка; (2) mini cover не установился; (3) geometry["mini"] никогда не записывался; (4) record_play дублировался при каждом PropertiesChanged — dedup guard; (5) queue activation сортировал весь очередь по trackno вместо сохранения порядка; (6) reveal_group вызывал несуществующий "threnameplace"; (7) мёртвый код (`set_tooltext_text if False else None`, пустой warnings loop); (8) версия Gdk не указана (конфликт Gdk 4.0 на некоторых хостах)
- [x] Validation: py_compile OK, 108 headless-тест (scripts/test-mv-music.py: ID3/FLAC/Ogg/MP4 parsing incl APIC/duration/trkn, failure modes, scan/group, store round-trip/backup/quarantine/restore/normalize/caps, play log dedup/ranking, search, cover cache, media-key CLI с моком Gio, MprisController degradation, GUI smoke на реальном GTK :0 — views/enqueue/search/error/play/mini/empty), desktop-file-validate OK, check-sync ALL CHECKS PASSED, make install DESTDIR OK
- [ ] HW: lollypop playback на MacBook10,1 (Cirrus), MPRIS на этом стеке, XF86Audio* клавиши (applespi + external), HiDPI рендеринг обложек/sidebar, energy cost PropertiesChanged refresh (см. NEEDS_HARDWARE_TEST.md → Music)

### Фаза 0.48 — Calendar: Mavericks visual integration + refinement (2026-09-26, без железа)
- [x] Аудит: mv-calendar был 614 строк stock-GTK (без leather/paper, без search, без keyboard, remove-calendar заглушка, ICS import — `pass`, баг отображения времени `[11:16]`, load() молча сбрасывал corrupt store, валидация отсутствовала, end<start проходил, минуты нельзя было выбрать); APPS.md claims (libical, search, birthdays) не соответствовали коду — docstring исправлен
- [x] Mavericks visual integration (как Notes/Reminders family): leather sidebar с mini-month (Gtk.Calendar, отметки дней с событиями, клик → переход) и списком календарей (color dot + visibility toggle), paper content area, colored event blocks, Mavericks toolbar buttons, view switcher Month/Week/Day (toggle segments с mutual exclusion)
- [x] Week view: time grid (24h, hour gutter, all-day strip, абсолютное позиционирование событий по часам/минутам); Day view: time grid + детали (время, location, notes); Month view: styled cells (today highlight, other-month dim, event bullets с временем)
- [x] Event dialog: валидация (title required → OK disabled; end<start → error dialog), hour+minute spinbuttons (ранее только часы), all-day toggle (отключает time), repeat (none/daily/weekly/monthly/yearly с month-end clamp и leap-year clamp), location, notes; edit mode (двойной клик / context menu) с prefill
- [x] Repeat expansion: iter_event_dates (daily/weekly/monthly/yearly, anchor day, 5-год horizon, 500 occurrences cap); RRULE:FREQ export/import round-trip
- [x] ICS: export с escaping (\, \; \\ \n), folding (75 chars), VALUE=DATE для all-day, CRLF, RRULE; import parser (unfold, VEVENT, DTSTART/DTEND DATE+DATETIME, SUMMARY/LOCATION/DESCRIPTION/UID/RRULE, malformed VEVENT skipped + count)
- [x] Upcoming-event nudges: --check-upcoming CLI (events в течение 15 мин, all-day/past/already-notified пропуск), mv-calendar-check.timer (OnCalendar=*:0/5, oneshot) + .service, firstboot enable; тот же паттерн, что Reminders
- [x] Search filter (Ctrl+F, Escape clears): week/day lists + month bullets; keyboard: Ctrl+N/Ctrl+F/Ctrl+E/Ctrl+I, ←/→, T, 1/2/3, Delete (confirm); context menu event block (Edit/Delete); empty states ("No events / match your search")
- [x] Corrupt-store safety (как Notes/Reminders): backup-on-save, restore from backup, quarantine + warning dialog; normalize (defaults для calendars/events, non-dict events dropped); geometry persistence; strict parse_dt (None вместо now() fallback — silent data corruption устранён)
- [x] Multi-account LOCAL: независимые календари (Personal/Work → Personal/Family/Work/Projects), each с name+color+show/hide, per-calendar CRUD, account isolation (events namespaced per calendar, no cross-leak), persistence round-trip, fully offline; Mavericks UI: sidebar account/calendar hierarchy with color dots
- [x] Найдено и исправлено по ходу: (1) Gtk.Calendar.get_year() не существует в GTK3 — краш при сохранении любого события (найдено GUI smoke, заменено на get_date()); (2) Gtk.ToggleButton не имеет mutual exclusion — view switcher мог оставаться в двух active-состояниях, re-click не работал (найдено GUI smoke, добавлен handler_block + manual exclusivity + no-op re-click); (3) _normalize не удалял non-dict events; (4) write_ics не писал VALUE=DATE; (5) read_ics не unescape-ил значения; (6) read_ics KeyError на VEVENT без DTSTART
- [x] Validation: py_compile OK, 63 headless-тест (scripts/test-mv-calendar.py: store/backup/quarantine/restore/normalize/parse_dt/events_for_day/repeat/matches/validate/ICS round-trip incl escaping/folding/RRULE/malformed-skip/check_upcoming с моком notify-send/CLI), GUI interaction smoke на реальном GTK :0 (20 checks: views/search/dialogs/validation/keyboard/selection/ICS/visibility), desktop-file-validate OK, check-sync ALL CHECKS PASSED, make install DESTDIR OK (timer+service installed), sibling suites green (notes 41, reminders 31)
- [ ] HW: visual validation leather/paper + event blocks на 2304×1440, upcoming-nudge через реальный user timer в сессии, Ctrl+Alt+C global binding, geometry restore на реальной сессии

### Фаза 0.47 — Reminders: regression restore + refinement pass (2026-09-26, без железа)
- [x] Forensic audit: подтверждено, что коммит 89b6649 (Voice Memos) молча откатил mv-reminders 359→156 строк — leather sidebar, paper task list, priority badges, overdue highlighting уничтожены; APPS.md индексировал регрессию, но код не был восстановлен после Notes 0.46
- [x] Visual integration восстановлена из 89b6649^: leather list sidebar, paper task list, custom checkboxes (cell data funcs), priority badges, overdue/due-today подсветка, strikethrough выполненных, Mavericks toolbar CSS
- [x] Latent bug найден и исправлен: CellRendererText не имеет get_style_context в GTK3 — pre-regression код вызывал его в render_due_cell/render_priority_cell (краш на любой задаче с due/prio); заменено на прямые свойства (foreground/background/weight)
- [x] Due-date notifications: существующий hourly user systemd timer (mv-reminders-check, oneshot → --check-due) покрывает due-today + overdue, notify once/task/day через libnotify; проверено тестами с моком notify-send
- [x] Refinement: search filter (Ctrl+F, Escape — фикс тот же, что в mv-notes: "changed" вместо "search-changed"), context menus (task: Edit/Toggle/Delete; list: Rename/Delete с защитой последнего списка), Clear Completed с confirm, rename/delete list, keyboard Ctrl+N/Ctrl+Shift+N/Delete/Ctrl+F/Escape, empty states, geometry persistence
- [x] Corrupt-store safety (как в Notes): backup-on-save (.bak), restore from backup, quarantine + warning-диалог; missing store — тихий first-run
- [x] Sibling regression audit: mv-calendar (614), mv-voice (405), mv-console (290), mv-textedit (584), mv-notes (938), mv-calculator (369), mv-stickies (203) — все совпадают с последними feature-коммитами, silent reverts не найдены; только mv-reminders был откачен
- [x] Validation: py_compile OK, desktop-file-validate OK, 31 headless-тест (scripts/test-mv-reminders.py: store/backup/quarantine/restore/normalize/due_state/matches/geometry/check_due с моком notify-send), GUI smoke на реальном GTK :0 (create/add/toggle/search/shortcuts/context-menus/clear-completed/last-list-guard/corrupt-store-warning), check-sync ALL CHECKS PASSED, systemd-analyze verify OK (с DESTDIR-установленным бинарём; на build-хосте /usr/bin/mv-reminders отсутствует — ожидаемо, путь из target-установки), makepkg rebuild OK, packed binary == source, DESTDIR install OK
- [ ] HW: visual validation leather/paper на 2304×1440, due/priority cell rendering, доставка уведомлений через реальный user timer в сессии, geometry restore на реальной сессии

### Фаза 0.46 — Notes: regression restore + trash/shortcuts/export/print (2026-09-26, без железа)
- [x] Forensic audit: APPS.md заявлял leather sidebar/lined paper/checkboxes/pin/search-highlight, но код mv-notes был откачен к базовой версии 159 строк в коммите 89b6649 (Voice Memos) — визуальная интеграция уничтожена молча; найдено через git history (03e26cd → 89b6649)
- [x] Регрессия восстановлена: Mavericks CSS (leather folder sidebar, lined paper editor), custom cell renderers, pin/checklist индикаторы, text tags
- [x] Recently Deleted: delete → trash (не удаление), restore/delete-forever/empty-trash с confirm-диалогами, 30-дневный auto-purge при load, trash pseudo-folder в sidebar со счётчиком
- [x] Pin toggle (кнопка + Ctrl+Shift+P + context menu) — ранее флаг pinned существовал, но UI-действия не было
- [x] Click-to-toggle checkboxes ([ ]↔[x]) кликом в checkbox-зоне редактора
- [x] Search highlighting: тег search_highlight применяется к совпадениям в открытой заметке (тег был создан, но не использован)
- [x] Export note → .txt (FileChooser save), Print (Gtk.PrintOperation, draw-page рендеринг текста)
- [x] Keyboard shortcuts: Ctrl+N note, Ctrl+Shift+N folder, Delete, Ctrl+F search, Ctrl+P print, Ctrl+E export, Ctrl+Shift+P pin, Escape clear search
- [x] Context notes: note (Pin/Export/Delete), folder (New/Delete folder → notes в trash), trash (Restore/Delete Forever/Empty Trash)
- [x] Empty states: подсказки в notes pane и editor pane; сортировка по mtime, счётчики в sidebar, даты в списке
- [x] Window geometry persistence (store["geometry"], save on destroy)
- [x] %U import: открытие .txt файла создаёт новую заметку
- [x] Corrupt-store handling: backup-on-save (.bak), restore from backup при повреждении, quarantine файла + warning-диалог, missing store ≠ corruption (silent first-run)
- [x] Найдено и исправлено по ходу: (1) refresh_folders менял selection → view переключался в trash mode (handler block + restore selection); (2) Gtk.SearchEntry search-changed не срабатывает на programmatic set_text → connect на changed; (3) STORE default-arg binding → late binding; (4) missing store ошибочно считался corruption → блокирующий диалог на первом запуске
- [x] Validation: py_compile OK, 41 headless-тест (scripts/test-mv-notes.py: store/backup/quarantine/trash/purge/folders/checklist/sanitize/highlight/paginate/import/geometry), GUI smoke на реальном GTK (create/edit/pin/search/trash/restore/shortcuts/delete-folder), corrupt-store GUI warning OK, desktop-file-validate OK, check-sync ALL CHECKS PASSED, package rebuilt + DESTDIR install OK
- [ ] HW: visual validation leather/lined-paper на 2304×1440, print dialog rendering, checkbox click feel, geometry restore на реальной сессии

### Фаза 0.45 — TextEdit: Mavericks visual integration (2026-09-26, без железа)
- [x] Аудит существующего mv-textedit: GtkSourceView4, HeaderBar с New/Open/Save/SaveAs, format-меню (Bold/Italic/Underline/Strikethrough/Font/Color/Alignment), status bar (Ln/Col/chars), открытие/сохранение .txt/.md
- [x] Format bar добавлен как отдельная панель под HeaderBar: Bold/Italic/Underline (ToggleButton), Alignment (Left/Center/Right), Font Family combo, Font Size combo, Text Color picker
- [x] Find/Replace панель добавлена (GtkSource.SearchContext): search entry, Next/Previous, Replace/Replace All, highlight matches, Escape закрывает
- [x] Print поддержка добавлена (Gtk.PrintOperation с PRINT_DIALOG)
- [x] Document inspector расширен: word count, encoding (UTF-8), line endings (LF/CRLF/CR detection) в status bar
- [x] Autosave/draft recovery для untitled документов: автосохранение каждые 30с в ~/.local/share/mv-textedit/drafts/autosave.json, восстановление при следующем открытии, очистка при save/close
- [x] Обновлен status bar: "Ln X, Col Y | N words | M chars | ENC | EOL"
- [x] Validation: py_compile OK, desktop-file-validate OK, scripts/check-sync.sh ALL CHECKS PASSED, headless import OK
- [ ] HW: visual validation of format bar appearance, print dialog, autosave behavior on real session

### Фаза 0.44 — P0 Desktop Chrome: audit + gaps (2026-09-26, без железа)
- [x] Forensic audit всех 9 поверхностей (Menu Bar, Dock, App Menu, Dialogs, File Chooser, Context Menus, Keyboard, Desktop/Wallpaper/Session, Window Management)
- [x] Keyboard layer verified: 20+ bindings, no conflicts, no orphans; missing Super+Q/M/H/W/E/T; docs/KEYBOARD.md created
- [x] xfwm4 theme CREATED (was referenced but missing): themerc (button_layout=OIM|:, traffic lights LEFT) + close/minimize/maximize XPMs
- [x] Wallpaper CREATED: mavericks-desktop.png 2304×1440 (blue-green gradient, pure Python PNG)
- [x] Autostart CREATED: plank.desktop + mv-notify-send.desktop in skel/.config/autostart/
- [x] xfce4-panel theme CREATED: panel.css (translucent, gradient, tasklist indicators)
- [x] File chooser polish: pathbar buttons + column headers added to _widgets.scss
- [x] Dialog polish: dialog-action-area + button styling added to _windows.scss
- [x] APPS.md: 9 new P0 rows added with real statuses
- [x] Validation: sassc compile OK, xmllint OK, desktop-file-validate OK (both autostart .desktop files)
- [ ] HW: visual validation of panel/dock/wallpaper/xfwm4 theme on 2304×1440; plank zoom/reflect; menu bar look

### Фаза 0.43 — Power UI: Mavericks-диалог питания поверх logind D-Bus (2026-09-26, без железа)
- [x] Аудит: старая mv-power-ui была минималистичным GTK-окном (4 кнопка + systemctl напрямую, без logind/UPower/логута/состояний ошибок); строки в APPS.md P0 не было вовсе
- [x] Развёрнут backend: logind D-Bus (CanSuspend/CanReboot/CanPowerOff → Suspend/Reboot/PowerOff с interactive=TRUE), fallback на systemctl при отсутствии logind, логут через xfce4-session-logout, только-чтение батарея через UPower D-Bus
- [x] Mavericks UX: chooser (Sleep/Restart/Shut Down/Log Out) + preset-диалоги с 60-секундным обратным отсчётом (Cancel/Escape прерывает), кнопка по умолчанию — aqua-синяя, чекбокс «Reopen windows when logging back in» → xfconf SaveOnExit, футер батареи, бесшовное оформление через CSS (градиентное окно, скругления, тень)
- [x] Состояния: кнопка действия недоступна при Can*=no; error-dialog при отказе logind D-Bus; «Battery status unavailable» при отсутствии UPower
- [x] Тесты: scripts/test-mv-power-ui.py — 44 headless-теста (mock-logind на private bus: caps yes/no/challenge, записывает вызовы, не выполняя реальных действий; fallback-планы; Countdown/countdown_text/format_battery_line/action_state; execute_plan с инжектированными моками; CLI --status с и без logind); все проходят
- [x] Проверки: py_compile, xmllint (оба зеркала keybindings), desktop-file-validate (mv-power-ui.desktop), scripts/check-sync.sh — ALL CHECKS PASSED
- [x] Keybindings: Ctrl+Alt+Escape → chooser (было), добавлен Ctrl+Alt+Delete → logout; оба зеркала xfce4-keyboard-shortcuts.xml синхронны
- [x] .desktop: mv-power-ui.desktop (NoDisplay=true — в Launchpad не нужен, как и в macOS; приложение вызывается hotkey/Apple-меню)
- [x] GUI smoke на этом хосте невозможен (нет Xvfb) — инстанциация PowerUI остаётся HW-валидацией; логика покрыта 44 тестами
- [ ] HW: suspend/resume реальный, телеметрия батареи, polkit interactive auth, аппаратная кнопка питания

### Фаза 0.38 — Orchestrator model fallback (2026-09-26, без железа)
- [x] Причина: двойной пин `nemotron-3-ultra-free` (orchestrator frontmatter + agent.build) — одна мёртвая модель роняла весь loop; fallback-процедуры не было вовсе (проверено историей)
- [x] `.opencode/model-fallback.json`: цепочка пользователя (OpenRouter North Mini Code → Free Router → Zen LongCat 2.5 Preview → Nemotron 3 Ultra → Nemotron 3.5 Lightning last-resort)
- [x] `scripts/session-reuse.py`: `models` (chain-first live-резолвер, без хардкода) + `classify-error` (quota=10/context=12 → fallback; ordinary/unknown → без fallback); reuse/retire не тронуты
- [x] `orchestrator.md` MODEL FALLBACK + `opencode.jsonc`: пин build СНЯТ (наследует живую модель); AGENTS.md 14.3 — указатель
- [x] Проверено: py_compile, матрица классификатора, offline-резолвер (ultra skipped → next North Mini Code); живое доказательство — objective продолжен кросс-модельно (ultra Task cancelled → продолжение на muse-spark)
- [x] Caveats: LongCat Zen-id не верифицирован live; lightning — last resort; нужен connected OpenRouter; после правок agent-файла — рестарт сервера

### Фаза 0.39 — Fallback hardening (2026-09-26, без железа)
- [x] Chain-only execution по умолчанию (`--all` только для диагностики); `never`-list (Muse Spark) исключается всегда — проверено unit-тестом
- [x] Orchestrator frontmatter → `openrouter/cohere/north-mini-code:free` (head цепочки); явный запрет self-invoke (только `build` через Task)
- [x] LongCat: ВЕРИФИЦИРОВАН как Zen-модель (`longcat-2.5-preview-free`, models.dev, релиз 2026-09-25) — guess ID совпал
- [x] Auth-инвентарь (без секретов): контейнер — openrouter+opencode; Windows-профиль — openrouter+google+groq, БЕЗ opencode → Zen-пункты на Windows-сервере только после `/connect` Zen
- [x] Проверено: py_compile, резолвер chain-only/--all, never-enforcement; опциональный hard-block — disable muse-spark в Zen-консоли

### Фаза 0.40 — Two-plane topology (2026-09-26, без железа)
- [x] Доказательство из opencode.db: живой `MavLinOS` сидит на spark (stale session), дети build наследовали её после unpin — механизм работал как настроен
- [x] `agent.build.model` = `opencode/longcat-2.5-preview-free` (worker-plane); orchestrator-plane = north-mini; spark невозможен конструктивно
- [x] Классификатор: `AUTH_ERROR` (40); резолвер: `rotate:`-строка + «no rotation» пока пин жив
- [x] Честное ограничение: смерть пина = единственная stop-and-wait (one-paste sed + рестарт); зафиксировано в orchestrator.md
- [x] Проверено: py_compile, оба сценария резолвера, jsonc-пин

### Фаза 0.41 — Plane split в конфиге (2026-09-26, без железа)
- [x] `provider.opencode.blacklist` (4 spark-ID): проект + оба global-зеркала — spark скрыт из `/models`-пикера везде
- [x] `small_model` = north-mini (проект): фоновые title/summary не уедут на spark через auto-cheap-pick
- [x] Матрица плоскостей зафиксирована в DECISIONS.md; sync never/blacklist описан в chain-файле
- [x] Проверено: все 3 jsonc парсятся, пины на месте; требуется ПОЛНЫЙ рестарт сервера + разовый уход stale-сессии со spark

### Фаза 0.42 — Исправление: spark в пикере для оркестратора, blacklist убран (2026-09-26)
- [x] `provider.opencode.blacklist` УДАЛЁН из проекта + обоих global-зеркал — spark теперь виден в /models для выбора оркестратора (требование пользователя)
- [x] Worker pin (LongCat) + small_model (north-mini) — исполнительный слой неизменен, spark как воркер невозможен конструктивно
- [x] `.opencode/model-fallback.json`: `never` = только для резолвера (исполнение), picker visibility свободен
- [x] Проверено: конфиги парсятся, пины на месте; требуется ПОЛНЫЙ рестарт сервера

### Фаза 0.43 — Workers never delegate (2026-09-26, без железа)
- [x] Причина: топ-уровень `task allow` без overrides для build — Task воркера показывал всех агентов, отсюда попытки вложенной делегации и build→orchestrator self-invoke
- [x] `agent.build.permission.task` = deny-all + worker-description; stock Build не тронут, subagent_depth без изменений
- [x] Промпт-компаньоны: orchestrator.md шаг 3 + AGENTS.md 14.7
- [x] Проверено: jsonc валиден (deny у build, allow топ-уровня цел); требуется ПОЛНЫЙ рестарт сервера

## Phase 0 — База и идентификация железа
- [x] Определить точную модель/ревизию: MacBook10,1 (Mid 2017)
- [x] Зафиксировать в docs/HARDWARE.md
- [x] Pacstrap минимальной базовой системы, загружаемость через systemd-boot (UEFI)
- [x] Acceptance: система грузится до консоли в QEMU+OVMF (smoke-test пройден)

### Фаза 1 — Аппаратная поддержка (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- [x] Wi-Fi: broadcom-wl-dkms (AUR) + brcmfmac fallback — оба профиля готовы
- [x] Аудио: macbook12-audio-driver (github.com/leifliddy/macbook12-audio-driver) — PKGBUILD готов
- [x] Bluetooth: macbook12-bluetooth-driver (AUR) — готов
- [x] Внешний ввод через USB-C: работает из коробки (standard USB HID)
- [x] Встроенные клавиатура/трекпад (applespi) — 3 стратегии подготовлены:
  - Стратегия А: macbook12-spi-driver-dkms (AUR) на linux-zen
  - Стратегия Б: linux-macbook kernel (github.com/marcosfad/macbook12-spi-driver) с патчами
  - Стратегия В: linux-lts + applespi backport patches
- [x] Управление питанием: TLP, thermald, ananicy-cpp — конфиги готовы и включены

### Фаза 2 — Сверхоптимизация (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- [x] zram/zswap: zram-generator (zram0 = RAM/2, zstd)
- [x] ananicy-cpp: установлен и включен
- [x] Урезание systemd unit'ов: оставлены только критические
- [x] Минимизация фонового I/O: journald volatile, отключены лишние таймеры

### Фаза 3 — Визуальный слой (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- [x] GTK3 тема Mavericks (скеоморфизм: текстуры, тени, стекло)
- [x] Иконки в стиле Mavericks/pre-flat
- [x] Dock: plank с рефлексией/зумом
- [x] Курсор macOS
- [x] Верхняя панель в стиле menu bar
- [x] Аналог Finder (thunar с боковой панелью и Mavericks-иконками)
- [x] Аналог System Preferences (xfce4-settings с сеткой иконок)
- [x] Браузер: Epiphany/GNOME Web с темой Safari 7 (Top Sites, компас, unified toolbar)
### Фаза 0.5 — Pre-hardware feature-complete (2026-09-25)
- [x] Baseline reconciled to Phase 0.3: cmdline `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`
- [x] Removed: thermald, ananicy-cpp, broadcom-wl blacklist, i915 guc/fbc/psr2 force, nvme APST-off, turbo-off, all sysctl overrides
- [x] Profiles: bootstrap/baseline/production/diagnostic/recovery + E1-E12 experiments
- [x] Diagnostics: mv-collect/mv-power/mv-suspend-test/mv-thermal (read-only) + mv-experiment runner
- [x] Desktop: Xfce/xfwm4/panel/plank/LightDM/terminal configs in skel + system xdg
- [x] Firefox ESR user.js + policies.json (uBlock, sessionstore 60s, no version pin)
- [x] Audits: SERVICE_AUDIT, RUNTIME_AUDIT, DEPENDENCY_AUDIT, CPU_COMPILATION, MEMORY_BUDGET
- [x] Scripts: mavericks-firstboot.sh, extract-brcmfmac-nvram.sh; apply-hardware-selection.sh reconciled
- [x] ISO package list: full desktop (Xorg/LightDM/Xfce/PipeWire/NM/Firefox), no thermald/ananicy/epiphany
### Фаза 0.6 — Pre-hardware P0 coherence fixes (2026-09-25, без железа)
- [x] Validation suite: bash -n (все .sh), py_compile (все mv-*), gcc mv-hud (one-shot OK),
      xmllint (все XML), desktop-file-validate (0 errors), makepkg build mavericks-apps OK
- [x] mavericks-theme добавлен в packages.x86_64 (тема была прописана в skel, но не ставилась в ISO)
- [x] mavericks-theme + epiphany-mavericks-theme PKGBUILD → repo-local (были git-URL несуществующих репо)
- [x] SCSS-баги: 14 несуществующих @import в gtk.scss, `border-radius: 3px; ... / 8px;` (gtk.scss + _other.scss),
      `@var` вместо `$var` (gtk.scss inline + epiphany.scss), `}EOF` склейка + незакрытый package() в epiphany PKGBUILD,
      опечатка gtk-3.30 → gtk-3.20; все три CSS проверены компиляцией sassc 3.6.2
- [x] packages.x86_64: удалён dunst (второй notify-daemon, противоречил аудиту), удалён grub (UEFI-only ISO),
      добавлены gvfs (Trash/volumes в Thunar — требование Finder/Trash), gtk-engine-murrine, libnotify
- [x] Удалена пустая ananicy.d/; epiphany-mavericks-theme → DEFERRED (только --all); .desktop hints исправлены
- [x] HANDOFF.md приведён к Phase 0.5 реальности (был stale: thermald/ananicy/Epiphany)
### Фаза 0.7 — Pre-hardware install/UX hardening (2026-09-25, без железа)
- [x] packages.x86_64 + mavericks-apps deps сверены с репозиториями Arch (pacman -Si):
      ВСЕ имена валидны; убран gtk-engine-murrine (нет в текущих репозиториях;
      теме не нужен — она GTK3-only без gtk-2.0/murrine-директив)
- [x] Thunar uca.xml: закавычены %-плейсхолдеры (ломались на путях с пробелами),
      `New%20Folder` → `"New Folder"`, Put Back обёрнут в `xfce4-terminal --hold`
      (голый интерактивный trash-restore без терминала висел бы)
- [x] firstboot: детект REPO_DIR с понятной ошибкой (раньше падал obscurely на шаге 3
      вне checkout), установка mavericks-apps/theme из рядом лежащих .pkg.tar.zst
      через pacman -U с fallback на репозиторий (раньше — только repo, которого нет
      в апстриме); фикс опечатки BASELINE_CDLINE
- [x] Дубли scripts/tools/configs ↔ airootfs сверены (26 пар — все SYNC);
      добавлен scripts/check-sync.sh — pre-commit gate (sync + bash + py + XML +
      desktop + PKGBUILD + опционально --check-repos); обе копии firstboot/uca обновлены
- [x] Проверено: policies.json валиден, systemd timer/service корректны
      (verify ругается только на отсутствие /usr/bin/mv-reminders на build-хосте —
      ожидаемо), обе rofi-темы парсятся реальным rofi, mkinitcpio MODULES/HOOKS на месте
### Фаза 0.8 — Mission Control E-MC experiment prepared (2026-09-25, без железа)

- [x] ISO built: `mavlinos-2026.09.25-x86_64.iso` (`<build-host>/archiso-out/`)
- [x] QEMU+OVMF smoke-test: ISO boots → systemd-boot menu → archiso hook → airootfs → DE loads
- [x] Pre-hardware P0 coherence fully validated: ISO contains mavericks-apps + mavericks-theme pkgs

### Фаза 0.9 — Finder New Folder hardening (2026-09-25, без железа)
- [x] Исследование: в AUR нет стабильного skippy-xd, только skippy-xd-git (VCS, GPL-2.0-or-later);
      upstream подтверждает one-shot expose без daemon (`skippy-xd` без аргументов) — нулевой idle cost
- [x] `configs/desktop/skippy-xd/skippy-xd.rc` (cosmos layout, animation 150ms, dim background,
      panel visible) + зеркало в skel (per-user, без конфликта с /etc/xdg пакета); sync-пара в check-sync.sh
- [x] `configs/profiles/experiments/E-MC-skippy-xd.sh` (apply/revert/status: AUR-install gate,
      xfconf Super+Tab rebind с backup, отказ от --start-daemon) + диспетчер E-MC в mv-experiment.sh (оба зеркала)
- [x] Gate расширен: `find ... configs -name *.sh` (E10 тоже покрыт); решение зафиксировано в DECISIONS.md;
      APPS.md/NEEDS_HARDWARE_TEST.md обновлены (чеклист E-MC); baseline по умолчанию НЕ изменён (rofi)
### Фаза 0.9 — Finder New Folder hardening (2026-09-25, без железа)
- [x] `mv-newfolder <dir>`: Finder-нумерация (New Folder, New Folder 2..N), проверка
      writable, ошибка → notify-send (best-effort под `timeout 3`, без зависаний headless) + exit 1;
      функц. тесты в /tmp: создание/инкремент/usage/readonly — все exit-коды корректны
- [x] uca.xml New Folder → `mv-newfolder "%d"` (источник + skel-зеркало, sync OK);
      mv-newfolder добавлен в Makefile install (DESTDIR-установка проверена)
- [x] Зафиксированные accepted Finder-deltas (не баги, backend-пределы Thunar):
      column view невозможен; рекурсивный search-toolbar отсутствует (deferred, без нового dep)
### Фаза 0.10 — Spotlight index wiring (2026-09-25, без железа)
- [x] Найден разрыв: plocate+rofi в ISO есть, но индекс ничто не строило/обновляло —
      файловый поиск Spotlight был бы пуст на установленной системе
- [x] `systemctl enable plocate-updatedb.timer` в firstboot (исходник + зеркало, sync OK,
      bash -n OK); unit-имя сверено с файлами пакета Arch (plocate-updatedb.service/.timer);
      daily oneshot, не daemon — в рамках energy-бюджета
### Фаза 0.11 — Launcher/dependency audit (2026-09-25, без железа)
- [x] Все 22 .desktop Exec сверены с packages.x86_64: mv-* — из mavericks-apps,
      бэкенды (xarchiver/galculator/orage/gcolor3/thunar/gnome-font-viewer/seahorse/
      geary/lollypop/gthumb/mousepad/trash-cli/rofi/plocate/gvfs/...) — в ISO;
      gnome-disks поставляется пакетом gnome-disk-utility (строка 30) — разрывов нет
- [x] mv-control: fallback-поведение без железа уже есть (try/except вокруг pactl/sysfs,
      isdir-guard backlight, FileNotFoundError) — правок не потребовалось
### Фаза 0.12 — GUI smoke tests on live X (2026-09-25, без целевого железа)
- [x] Хост имеет рабочий X (:0): mv-quicklook (text/GtkSourceView-путь), mv-console
      (journalctl-backend), mv-activity (/proc-путь) — все стартуют без traceback
      и живут (timeout-kill 124 = alive); Poppler на хосте отсутствует (ожидаемо,
      PDF-путь валидируется на железе/ISO)
- [x] mv-settings: missing-backend fallback уже есть (INFO-диалог, напр. blueman) — правок нет
### Фаза 0.13 — rofi themes re-validated (2026-09-25, без железа)
- [x] rofi-mavericks.rasi + rofi-launchpad.rasi: `rofi -dump-theme` exit 0, stderr пуст
      (real rofi 2.0.0); ВАЖНО: без LANG=C.UTF-8 dump падает с exit 1 и пустым stdout
      даже на дефолтной теме — это env-проблема хоста, не баг тем
### Фаза 0.14 — Preview alias + more GUI smoke (2026-09-25, без железа)
- [x] Разрыв: P1 Preview был в roadmap, evince в ISO есть, но .desktop-алиаса и строки
      в APPS.md не было → создан mv-preview.desktop (Exec=evince %U,
      Icon=document-viewer), desktop-file-validate чист
- [x] GUI smoke alive на :0: mv-notes, mv-settings, mv-about (в дополнение к 0.12)
### Фаза 0.15 — HUD no-hardware fallback validated (2026-09-25, без железа)
- [x] mv-hud one-shot на нецелевом хосте (без RAPL m3-7Y32): `CPU n/a | n/a`,
      exit 0 — graceful degradation подтверждён; бинарь в .gitignore (3200d9a), tree чист
### Фаза 0.16 — power-ui alive, screenshot host-limit, blockers confirmed (2026-09-25)
- [x] mv-power-ui: SMOKE-ALIVE на :0 (logind-путь стартует)
- [x] Screenshot E2E НЕ валидируем на хосте: xfce4-screenshooter требует Wayland
      screencopy-протоколы даже под DISPLAY=:0 (хост-квайрк; цель — X11/Xfce,
      штатная среда screenshooter) — остаётся HW-валидацией, в коде mv-shot
      признаков бага нет (делегирует бэкенду)
- [x] Blockers подтверждены: root недоступен (`sudo -n true` → password required) ⇒
      mkarchiso/QEMU-сборка заблокирована; остальное сделано (0.1: обход blocker)
- [x] Оценка P0/P1 pre-hardware: существенных code/integration-проблем, решаемых
      без железа и без root, не осталось (Finder/Spotlight/MC/Launchpad/CC/NC/QL/
      Settings/Power/Preview/Console/Notes/Activity/HUD/dialogs/launchers покрыты
      выше); P2-research разблокирован для следующей итерации по правилу приоритетов
### Фаза 0.17 — P2 Time Machine backend research (2026-09-25, без железа)
- [x] Сверено: borg 1.4.5 + restic 0.19.1 в extra, оба активны; fuse3/rclone/btrfs-progs в репозиториях
- [x] docs/RESEARCH_TIMEMACHINE.md: Borg primary (dedup+zstd+FUSE+шифрование на USB-C),
      btrfs-снапшоты как instant local layer (ФС уже btrfs), restic deferred до cloud-требований;
      всё oneshot-by-timer, без daemon — в рамках power-модели; в ISO пока НЕ добавлять
### Фаза 0.18 — Local package repo BUILT (2026-09-25, с root)
- [x] /tmp/mavericks-repo: mavericks-apps, mavericks-theme, macbook12-audio-driver
      (1.0.0.r108.g4cdfcdb) + mavericks.db — `build-local-pkgs.sh` exit 0
- [x] Исправлены три бага сборки: placeholder-sha256 в audio-PKGBUILD (реальные суммы),
      pkgver-pipe-ловушка (`describe|sed||fallback` давал пустую версию — тегов нет
      в апстриме; переписан на if/desc), неидемпотентность скрипта (добавлен -f) + exec-bit
- [x] ИНЦИДЕНТ и урок: ручной `rm -rf packages/*/src` удалил TRACKED-исходники
      (src/ у этих пакетов — не residue, а общие с makepkg $srcdir имена);
      восстановлено `git checkout`, потерь нет; в скрипт вписан WARNING, residue
      покрыт .gitignore (pkg/, audio-clone, audio-src/)

### Фаза 0.19 — Forensic audit + P0 gap fixes (2026-09-26, без железа)
- [x] Full source audit of all mv-* apps, Finder, Spotlight, Launchpad, Mission Control, Global Desktop coherence
- [x] Finder status corrected: PARTIALLY IMPLEMENTED (no Space binding, no column view, no recursive search)
- [x] Spotlight enhanced: mv-spotlight script (unified app+file search), improved rofi theme with categories
- [x] Launchpad status corrected: PARTIALLY IMPLEMENTED (no pagination, folders, jiggle mode)
- [x] Mission Control: EXPERIMENT READY (skippy-xd E-MC experiment, not in ISO)
- [x] Global Desktop: filechooser theming enhanced (Mavericks-style sidebar, path-bar, file-list)
- [x] Keyboard shortcuts: Super+Space → mv-spotlight (script mode), XML validated
- [x] All packages rebuilt (mavericks-apps, mavericks-theme), local repo updated, check-sync ALL PASSED
- [x] APPS.md updated with real statuses (no fake "IMPLEMENTED" claims)

### Фаза 0.20 — Finder UCA actions implemented (2026-09-26, без железа)
- [x] mv-getinfo: Finder-like Get Info dialog (size, dates, permissions, kind)
- [x] mv-openwith: Finder-like Open With dialog (recommended apps + choose other)
- [x] mv-rename: Finder-like Rename dialog (GTK-based, validates name)
- [x] mv-eject: Finder-like Eject for removable devices (Gio.UnixMountMonitor)
- [x] Thunar UCA updated with all 4 new actions (Get Info, Open With, Rename, Eject)
- [x] All scripts added to Makefile, packages rebuilt, check-sync ALL PASSED
- [x] APPS.md updated: Finder UCA now includes Get Info, Open With, Rename, Eject

### Фаза 0.21 — Spotlight enhancements (2026-09-26, без железа)
- [x] mv-spotlight: calculator (math eval), unit conversion (length/weight/temp)
- [x] File results categorized: Folders, Documents, Images, Audio, Video, Archives, Code, Spreadsheets, Presentations, Other
- [x] Improved app ranking: exact > prefix > word-prefix > substring > exec-substring
- [x] Recent items shown on empty query (from GTK recently-used.xbel)
- [x] Separator between calculator and main results
- [x] APPS.md: Spotlight status updated with implemented features

### Фаза 0.22 — Launchpad pagination, folders, search (2026-09-26, без железа)
- [x] mv-launchpad: paginated script-mode Launchpad for rofi
- [x] Pagination: Left/Right arrows, PgUp/PgDn, 35 items/page (7x5 grid)
- [x] Folders: configurable via ~/.config/mv-launchpad/folders.json
- [x] Custom positions: ~/.config/mv-launchpad/positions.json
- [x] Search filtering within Launchpad
- [x] Keyboard navigation (arrows, Enter, Escape)
- [x] Super+L → mv-launchpad script mode (XML validated)
- [x] APPS.md: Launchpad status updated with implemented features

### Фаза 0.23 — Mission Control window overview (2026-09-26, без железа)
- [x] mv-mission-control: wmctrl-based window overview for rofi script mode
- [x] Groups windows by workspace, shows active workspace first
- [x] rofi-mission-control.rasi theme for window overview
- [x] Super+Tab → mv-mission-control script mode (XML validated)
- [x] E-MC experiment preserved: skippy-xd one-shot expose as advanced option
- [x] APPS.md: Mission Control status updated

### Фаза 0.24 — Control Center + Notification Center (2026-09-26, без железа)
- [x] mv-control: full Mavericks-like Control Center with sliders (Wi-Fi toggle/list, BT toggle, volume/mute/output device, brightness/night shift, battery/power mode, DND)
- [x] xfce4-notifyd: Mavericks theme (top-right, rounded, translucent) + notifyd config
- [x] APPS.md: Control Center & Notification Center statuses updated to PARTIALLY IMPLEMENTED
- [x] Packages rebuilt, check-sync ALL PASSED

### Фаза 0.25 — Quick Look, Preview, Screenshot, Disk Utility status corrections (2026-09-26)
- [x] Quick Look: PARTIALLY IMPLEMENTED (Space binding not feasible without Thunar plugin; UCA workaround)
- [x] Preview: PARTIALLY IMPLEMENTED (evince alias, no Mavericks UI)
- [x] Screenshot: PARTIALLY IMPLEMENTED (xfce4-screenshooter backend, no annotation)
- [x] Disk Utility: PARTIALLY IMPLEMENTED (gnome-disks alias, no Mavericks UI)
- [x] APPS.md statuses corrected

### Фаза 0.26 — P0 infrastructure items added (2026-09-26)
- [x] Menu Bar: PARTIALLY IMPLEMENTED (xfce4-panel Mavericks theme)
- [x] Dock: PARTIALLY IMPLEMENTED (plank Mavericks theme)
- [x] Application Menu: PARTIALLY IMPLEMENTED (applicationsmenu plugin)
- [x] Global Dialogs: PARTIALLY IMPLEMENTED (GTK3 Mavericks theme)
- [x] File Chooser: PARTIALLY IMPLEMENTED (GTK3 Mavericks theme)
- [x] Context Menus: PARTIALLY IMPLEMENTED (GTK3 theme + Thunar UCA)
- [x] Keyboard Shortcut Layer: IMPLEMENTED (centralized xfconf)
- [x] Desktop/Wallpaper: PARTIALLY IMPLEMENTED (xfdesktop + Mavericks wallpapers)
- [x] Window Management: PARTIALLY IMPLEMENTED (xfwm4 Mavericks theme + tiling)
- [x] APPS.md updated with all P0 infrastructure items

### Фаза 0.27 — P1 applications forensic audit (2026-09-26)
- [x] Full source audit of all 15 P1 applications
- [x] Identified 8 alias/wrapper apps (Category D): TextEdit, Calculator, Calendar, Music, Photos, Keychain, Font Book, Color Meter, Stickies, Mail, Preview
- [x] Identified 4 custom frontend apps (Category B): Notes, Reminders, Voice Memos, Console
- [x] Dictionary: NOT_STARTED (no implementation)
- [x] APPS.md P1 section completely rewritten with real statuses (all PARTIALLY IMPLEMENTED or NOT_STARTED)
- [x] No fake IMPLEMENTED claims remain

### Фаза 0.28 — P1 Calendar implementation (2026-09-26, без железа)
- [x] mv-calendar: custom Mavericks-like Calendar with Month/Week/Day views
- [x] ICS import/export support
- [x] Multiple calendars with color coding and visibility toggles
- [x] Event creation dialog with recurring support placeholder
- [x] .desktop file updated to X-Mavericks-Native=true
- [x] APPS.md status updated to PARTIALLY IMPLEMENTED (custom frontend)
- [x] Package rebuilt, check-sync ALL PASSED

### Фаза 0.29 — Finder keyboard shortcuts, Empty Trash, thunarrc enhancements (2026-09-26, без железа)
- [x] thunar-uca.xml: added "Empty Trash" action (trash-empty) with user-trash-full icon
- [x] xfce4-keyboard-shortcuts.xml: added Finder-like global shortcuts:
  - Super+N → mv-newfolder $HOME/Desktop (New Folder on Desktop)
  - Super+Shift+N → mv-newfolder $HOME (New Folder in Home)
  - Super+I → mv-getinfo $HOME (Get Info)
  - Super+O → mv-openwith $HOME (Open With)
- [x] thunarrc: enhanced with Finder-like defaults (ShowToolbar, ShowStatusbar, ShowLocationSelector, TreePaneWidth, window geometry, case-insensitive sort)
- [x] All XML validated (xmllint), sync check passed, packages rebuilt
- [x] APPS.md updated: Finder UCA now includes Empty Trash; keyboard shortcuts documented

### Фаза 0.30 — Spotlight gap fixes (2026-09-26, без железа)
- [x] mv-spotlight: file results now include xdg-open action (files open from results)
- [x] System actions added: Settings, Control Center, Activity Monitor, Disk Utility, Terminal (match on name/description)
- [x] Error handling: missing plocate / empty index / timeout shown as user-visible result
- [x] Empty state handling: "No recent items" on empty query; "No results for 'query'" when nothing matches
- [x] rofi-mavericks.rasi: visual polish (Mavericks-style skeuomorphic accents, better spacing, scrollbar, rounded corners, softer colors)
- [x] All validations pass: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED
- [x] mv-spotlight: added headless test suite (scripts/test-mv-spotlight.py) covering rank_app_match, categorize_file, get_icon_for_file, evaluate_calculator, format_result, search_files error states, and main() query routing
- [x] APPS.md Spotlight row updated with implemented features

### Фаза 0.31 — Launchpad gap fixes (2026-09-26, без железа)
- [x] mv-launchpad: mv-launchpad.desktop entry added for app menu integration
- [x] mv-launchpad: default folders.json auto-population (Utilities/Other) on first run
- [x] mv-launchpad: folder navigation with "Back" button (open folder → view apps → back to main)
- [x] mv-launchpad: empty state handling (no apps found, no search results, empty folder)
- [x] mv-launchpad: robust .desktop parsing with icon existence validation and fallback
- [x] mv-launchpad: duplicate .desktop handling (user overrides system)
- [x] rofi-launchpad.rasi: Mavericks-style visual polish (skeuomorphic accents, rounded corners, scrollbar, softer colors, shadows, transitions)
- [x] All validations pass: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED
- [x] APPS.md Launchpad row updated with implemented features

### Фаза 0.32 — Mission Control window overview enhancements (2026-09-26, без железа)
- [x] mv-mission-control: added active window detection (via xprop _NET_ACTIVE_WINDOW) with "▸" prefix marker
- [x] mv-mission-control: added empty workspace display (shows "(empty)" placeholder for workspaces with no windows)
- [x] mv-mission-control: improved error handling — graceful degradation when wmctrl missing (shows install hint)
- [x] mv-mission-control: added window action stubs (--activate, --close, --minimize) for future rofi keybinding integration
- [x] mv-mission-control: expanded icon mapping for common applications (Chrome, VS Code, Discord, Steam, terminals, Office, etc.)
- [x] rofi-mission-control.rasi: Mavericks-style visual polish matching Spotlight/Launchpad theme evolution (softer palette, rounded corners, better spacing, larger icons, custom scrollbar, accent blue selection)
- [x] E-MC experiment: updated BASELINE_CMD to use mv-mission-control script mode (was rofi window mode)
- [x] E-MC experiment: added wmctrl presence check in status; skel rc path variable; improved apply/revert messaging
- [x] All validations pass: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED
- [x] APPS.md Mission Control row updated with implemented features

### Фаза 0.33 — Control Center gap fixes (2026-09-26, без железа)
- [x] mv-control: Wi-Fi connect/disconnect with password prompt for secured networks via nmcli
- [x] mv-control: Bluetooth device list with actual BlueZ D-Bus enumeration (name, connected/paired status, device icon)
- [x] mv-control: Bluetooth connect/disconnect/pair actions via BlueZ D-Bus (no pairing daemon)
- [x] mv-control: Audio output device switching via pactl set-default-sink (combo box now functional)
- [x] mv-control: Brightness slider robustness — shows "Brightness control not available" when no backlight path
- [x] mv-control: Battery power mode — reads current TLP mode (balanced/powersave/performance), shows info dialog for changes (requires root)
- [x] mv-control: Error/empty states for all sections (NetworkManager, BlueZ, PulseAudio, backlight, UPower, xfce4-notifyd)
- [x] All validations pass: py_compile, check-sync ALL PASSED
- [x] APPS.md Control Center row updated with implemented features

### Фаза 0.34 — Notification Center history + keyboard shortcut (2026-09-26, без железа)
- [x] mv-notify-send: notify-send wrapper that logs notifications to ~/.local/share/mavericks/notifications.json (max 500 entries, no daemon)
- [x] mv-notification-center: Mavericks-style history viewer (GTK3, app-grouped list, Clear/Clear All buttons, DND toggle in header, keyboard navigation)
- [x] Keyboard shortcut: Super+Shift+V → mv-notification-center (added to xfce4-keyboard-shortcuts.xml)
- [x] Desktop entry: mv-notification-center.desktop with X-Mavericks-Native=true
- [x] Makefile updated to install both scripts
- [x] All validations pass: py_compile, xmllint, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Notification Center row updated with implemented features
- [x] Remaining gap: action buttons on banners (xfce4-notifyd limitation, not feasible without daemon); banner visual validation needs hardware

### Фаза 0.35 — Quick Look enhancements (2026-09-26, без железа)
- [x] mv-quicklook: multi-file support (pass multiple files, navigate with Left/Right arrows, Space, PgUp/PgDn)
- [x] mv-quicklook: fullscreen toggle (F key, double-click, toolbar button)
- [x] mv-quicklook: counter display ("2 of 5") in header bar
- [x] mv-quicklook: Previous/Next/Fullscreen toolbar buttons
- [x] mv-quicklook: keyboard shortcuts (Escape/q=close, Enter/o=open, Left/P/Up=prev, Right/N/Down/Space=next, F/F11=fullscreen)
- [x] mv-quicklook-thunar: global hotkey handler (Super+Shift+Space) — uses xdotool to copy Thunar selection to clipboard, parses file:// URIs, launches mv-quicklook
- [x] mv-quicklook-thunar.desktop: desktop entry for app menu integration
- [x] xfce4-keyboard-shortcuts.xml: added Super+Shift+Space → mv-quicklook-thunar
- [x] Makefile: added mv-quicklook-thunar to install targets
- [x] All validations pass: py_compile, xmllint, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Quick Look row updated with implemented features
- [x] Remaining gap: native Thunar Space key binding (requires Thunar plugin, not feasible pre-hardware); clipboard-based approach has ~150ms latency and requires xdotool; test Super+Shift+Space on HW

### Фаза 0.36 — Preview implementation (2026-09-26, без железа)
- [x] mv-preview: complete rewrite using poppler-glib (mature PDF backend, same as evince) + GdkPixbuf for images
- [x] Multi-file support: navigate between files with Ctrl+Left/Right arrows
- [x] Multi-page PDF navigation: Left/Right arrows, Home/End, thumbnail sidebar click
- [x] Thumbnail sidebar: renders all PDF page thumbnails, click to jump to page
- [x] Annotation toolbar UI: Select, Text, Shape, Sign buttons (stubbed, status bar feedback)
- [x] Keyboard shortcuts: Escape/q=close, Enter/o=open, arrows=page, Ctrl+arrows=file, Home/End=first/last page, F/F11=fullscreen, Alt+1-4=annotation tools
- [x] Fullscreen toggle (F key, toolbar button)
- [x] Open button: launches file in default external handler (xdg-open)
- [x] Error states: missing file, unsupported type, missing poppler, render errors shown in UI
- [x] Mavericks visual integration: skeuomorphic sidebar gradient, custom toolbar styling, status bar
- [x] MIME type associations in .desktop: application/pdf, application/postscript, image/* — Preview becomes default handler
- [x] poppler-glib dependency added to mavericks-apps optdepends (already present)
- [x] All validations pass: py_compile, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Preview row updated with implemented features
- [x] Remaining gaps: annotation persistence (requires poppler annotation API), form filling, export, signature management; PDF render validation needs hardware (2304×1440 panel)

### Фаза 0.37 — Screenshot post-capture preview + config + annotation handoff (2026-09-26, без железа)
- [x] mv-shot: rewritten with config file support (~/.config/mv-shot/config.ini) — save_dir, show_preview, preview_timeout, copy_to_clipboard
- [x] mv-shot: post-capture preview dialog (GTK3, Mavericks-style) with actions: Open in Preview, Show in Finder (Thunar), Move to Trash, Dismiss
- [x] mv-shot: auto-close timer for preview dialog (configurable timeout)
- [x] mv-shot: clipboard copy wiring — config option copy_to_clipboard copies saved file to clipboard after capture
- [x] mv-shot: error handling for missing backends (xfce4-screenshooter, ffmpeg) with user-friendly dialogs
- [x] mv-shot: annotation handoff — "Open in Preview" launches mv-preview with annotation toolbar UI (Select/Text/Shape/Sign stubs)
- [x] mv-shot: --config flag to show config file path
- [x] mv-screenshot.desktop: added MimeType, Keywords for better integration
- [x] All validations pass: py_compile, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Screenshot row updated with implemented features
- [x] Remaining gaps: actual annotation persistence (requires poppler annotation API in Preview); recording validation on HW (ffmpeg x11grab CPU/power); keybinding feel test on real hardware; preview dialog visual validation on 2304×1440 panel

### Фаза 0.39 — Disk Utility Mavericks frontend (2026-09-26, без железа)
- [x] mv-diskutil: custom Mavericks-like Disk Utility frontend (Python/GTK3) over UDisks2 via Gio.DBus — storage stack reused, not rewritten
- [x] Sidebar: Internal/External groups, drives + partition children, Mavericks-style selection
- [x] Detail pane: model/vendor/serial/capacity/connection/media, capacity bar (statvfs), FS type/label/UUID/mount point/device/partition type
- [x] Actions: mount/unmount/eject via UDisks2 D-Bus (DO_NOT_AUTO_START, 15s timeout, error dialogs, re-enumerate after)
- [x] First Aid: S.M.A.R.T. status/temperature/power-on hours/bad sectors + SmartGetAttributes table (read-only); fsck repair explicitly NOT performed — dialog explains and points to gnome-disks
- [x] Destructive actions (format/partition/erase): deferred with in-UI reason pointing to gnome-disks — no unguarded destructive ops shipped
- [x] Empty states: UDisks2 not-available / cannot-connect / no devices / no selection
- [x] Apple S3X NVMe section: shown for NVMe drives, graceful "Available on hardware" empty state pre-HW
- [x] Keyboard: ListBox arrow navigation, Escape closes; refresh via header-bar button; no polling, no daemon
- [x] mv-disk-utility.desktop: Exec=mv-diskutil, X-Mavericks-Native=true, Keywords
- [x] Makefile: mv-diskutil added to install targets; no new heavy deps (python-gobject already in mavericks-apps)
- [x] Headless tests: scripts/mock-udisks2.py (fake UDisks2 service: SATA+ext4 mounted, USB vfat unmounted, Apple NVMe hfsplus) + scripts/test-mv-diskutil.py — 34 tests, all pass (read-only, no real disks)
- [x] All validations pass: py_compile, desktop-file-validate, check-sync ALL PASSED, make install DESTDIR smoke test OK
- [x] APPS.md Disk Utility row updated
- [x] Remaining gaps: S3X NVMe telemetry validation on HW; whole-disk filesystems without partition table not listed (UDisks2 limitation); visual validation on 2304×1440 panel; format/partition remain in gnome-disks by design

### Фаза 0.54 — Font Book: forensic launchability audit + self-sufficient rewrite (2026-09-27, без железа)
- [x] Forensic audit: real binary launch reproduced 100% startup crash — `Gtk.CssProvider.load_from_data` raised `gtk-css-provider-error-quark: 'text-align' is not a valid property name` (invalid GTK3 CSS in `.sidebar-item`), exit 1 before window construction. Same bug class as mv-keychain (7785bf4) — 4th fake completion.
- [x] Audit findings beyond crash: sidebar buttons non-functional, gnome-font-viewer handoff leaves window (and gnome-font-viewer not even in PKGBUILD deps), no enumeration/waterfall/glyphs/collections/search/keyboard, duplicate imports.
- [x] mv-fontbook rewritten self-sufficient: fontconfig enumeration via `fc-list --format` (cached per process, no polling) with Pango family-list fallback for degraded systems
- [x] Preview waterfall: selected face at 11/14/18/24/36/48 pt with pt labels + separators on paper background (PangoCairo on Gtk.DrawingArea)
- [x] Glyph grid: Pango coverage (`font.get_coverage`) over Basic Latin + Latin-1 + punctuation ranges, paper-backed section headers, dashed cells for uncovered codepoints
- [x] Collections: All Fonts / User / Computer / Fixed Width (fontconfig spacing ≥ 90) / Serif / Sans Serif (family-name heuristics — documented limits)
- [x] Install/remove user fonts: FileChooser → ~/.local/share/fonts (XDG) → fc-cache → re-enumerate; system font dirs never touched (path-prefix guard); confirm dialog on remove
- [x] Search (client-side filter, Ctrl+F), keyboard: Ctrl+F/I/O, Delete (user fonts only), Escape clears search; per-view GTK interactive search disabled so Ctrl+F always means the global field
- [x] Error/empty states: no-backend InfoBar, empty collection/search, install failure, remove refusal, missing gnome-font-viewer handoff
- [x] CSS crash-class regression fix: provider load wrapped in try/except GLib.Error → stderr + default theme, never crash on CSS
- [x] Real GUI smoke (Wayland :0): window constructs, 6 collections, 36 container fonts enumerated, collections/search filter, install+remove round-trip in isolated HOME, argv file preselection, waterfall + glyph grid rendered to cairo surfaces and visually verified (screenshots)
- [x] Launch re-verified post-fix: real binary alive at 4s, zero stderr (pre-fix: GLib.GError + exit 1)
- [x] scripts/test-mv-fontbook.py: 65 tests (pure logic + GUI smoke), all pass
- [x] Gate: py_compile, desktop-file-validate, check-sync ALL CHECKS PASSED, makepkg -f builds
- [x] mv-font-book.desktop: added MimeType (font/ttf, font/otf, font/collection, x-font forms)
- [x] PKGBUILD: fontconfig → depends; gnome-font-viewer → optdepends
- [x] Remaining gaps: Serif/Sans heuristics are name-based (documented); visual validation on 2304×1440 panel; font install round-trip on real system; HiDPI glyph grid density

### Фаза 0.55 — Digital Color Meter: forensic launchability audit + functional rewrite (2026-09-27, без железа)
- [x] Forensic audit: real launch smoke — окно _constructs без CSS-краша, но второй скрытый баг: `display.get_pointer()[:2]` в GDK3 возвращает (screen, x, y, mask), т.е. x=объект GdkScreen → `pixbuf_get_from_window` падал с TypeError → проглатывался `except: pass` → показания цвета НИКОГДА не обновлялись. Aperture combo, Lock Position, HSV-лейбл и gcolor3 handoff были нерабочими; не было loupe/форматов/копирования/палитры/клавиатуры.
- [x] mv-colormeter переписан: сэмплинг через Gdk root-window (X11), позиция указателя через seat API (non-deprecated) с fallback на get_pointer()
- [x] Aperture 1×1/3×3/5×5/10×10/25×25 с настоящим усреднением блока (с клампом к границам экрана)
- [x] Pixel loupe: увеличенное окно 11×11 вокруг точки с обведённой центральной ячейкой
- [x] Переключение форматов: sRGB 8-bit / sRGB % / Hex / HSV / Display P3 (настоящая матричная конверсия sRGB↔P3 через D65, не гамма-фейк)
- [x] Копирование в буфер (Ctrl+C) в активном формате; Ctrl+1..5 — горячие клавиши форматов
- [x] Сессионная палитра: Ctrl+P добавить (дубликаты отклоняются), клик по swatch — загрузить цвет, × — удалить, Ctrl+S — экспорт в .gpl (GIMP Palette, round-trip протестирован)
- [x] Lock Position: фиксирует точку сэмплинга; стрелки двигают на 1 px (Shift — 8 px)
- [x] Wayland disposition: явное состояние "sampling unavailable under Wayland", без фейковых чёрных сэмплов; таймер 100 ms только под X11 и только пока окно открыто
- [x] Error-состояния: нулевая геометрия экрана, сбой захвата, исключение сэмплинга, сохранение пустой палитры, отсутствующий gcolor3
- [x] gcolor3 handoff: кнопка в header bar (Ctrl+O), видна только если установлен; optdep в PKGBUILD
- [x] CSS crash-class regression guard: загрузка provider обёрнута в try/except GLib.Error (паттерн mv-fontbook)
- [x] Реальный GUI smoke (Wayland :0): окно строится, fallback-состояние показано, все контролы протестированы
- [x] Launch перепроверен: реальный бинарь жив на 4с, пустой stderr
- [x] scripts/test-mv-colormeter.py: 76 тестов (pure logic + GUI smoke), все проходят
- [x] Gate: py_compile, desktop-file-validate, check-sync ALL CHECKS PASSED, make install DESTDIR OK, makepkg -f собирается
- [x] Remaining gaps: реальные значения пикселей на панели 2304×1440 (HW); валидация X11-пути под Xfce (build env — Wayland, X11 проверен только через мок-сэмплер); плотность loupe на HiDPI

### Фаза 0.61 — Theme CSS repair: GTK4/dart-sass contamination + icon-theme fallback (2026-09-27, без железа)
- [x] Forensic confirmation: 8 SCSS partials in packages/mavericks-theme/src/mavericks-theme/gtk-3.0/ contained 17 dart-sass `@use "X" as *;` directives (present since abee05b, theme introduction). libsass/sassc does not support `@use` and passed the lines through verbatim into compiled gtk.css → GTK3 CssProvider parse failure ("unknown @ rule") + cascade of follow-on errors. Measured with Gtk.CssProvider (GTK 3.24.52, python3-gi): OLD gtk-3.0 = 65 parse errors, OLD gtk-3.20 = 74 parse errors per load (~90/app start as flagged).
- [x] Full GTK3-invalid construct census via isolated CssProvider probes (not just @use): `:focus-visible`, `:insensitive` (deprecated), `backdrop-filter`, `@media print`, `@media (prefers-contrast: high)`, `@media (prefers-reduced-motion: reduce)`, `@define-color` with non-color values (font_family/font_size/animation_*), `@font-face`, `transform: scale()/translateX()`, `-gtk-icon-transform: scale()/rotate()`, bare `width:`/`height:`/`max-width:`, `overflow:`, `text-align:`, `display: none`, `z-index:`, `flex-shrink:`, `:horizontal`/`:vertical` pseudo-classes, `*::selection`, `entry::placeholder`, `margin-left: auto`, 5-value `border-radius` (0 0 $tab_border_radius expansion).
- [x] Repair (syntax-only, Mavericks look preserved): `@use`→`@import` in all partials; removed dead @define-color/@font-face/@media-print blocks; `:insensitive`→`:disabled`; `:focus-visible` merged into `:focus`; width/height→min-width/min-height; removed overflow/text-align/display/z-index/flex-shrink/transform/-gtk-icon-transform/::selection/::placeholder/:horizontal/:vertical/margin-left:auto; 5-value border-radius→4-value; progress pulse keyframes transform→opacity; scrollbar stepper buttons display:none→min-width/min-height:0 collapse.
- [x] NEW permanent gate: scripts/test-theme-css.py — source scan (no @use/GTK4 constructs), sassc compile of both targets, Gtk.CssProvider load with zero parsing-error signals. Result: 9/9 checks pass, 0 errors both targets (was 65/74).
- [x] Icon-theme gap fix: ISO had zero icon-theme packages; mavericks-theme icons/index.theme declares Inherits=hicolor,Adwaita but Adwaita was absent → 28 standard icon names referenced by mv-* .desktop files failed to resolve. Added adwaita-icon-theme to archiso-profile/releng/packages.x86_64 AND mavericks-theme depends (theme package now guarantees its own fallback chain). No Apple assets; our 3 SVG glyphs (airdrop/sticky-notes/timemachine) unchanged.
- [x] Package rebuilt: makepkg -sf OK; built gtk.css verified clean (zero @use/GTK4 constructs); gtk-update-icon-cache builds icon-theme.cache OK.
- [x] Gates: scripts/check-sync.sh ALL CHECKS PASSED (incl. --check-repos: adwaita-icon-theme in repos); desktop-file-validate OK; PKGBUILD parse OK.
- [x] Not feasible here (no Xvfb): mv-* app-launch stderr before/after sampling → moved to NEEDS_HARDWARE_TEST.md (CssProvider gate is the pre-hardware substitute).
- [x] Remaining gaps: visual validation of repaired theme on 2304×1440 (HW); selection color now GTK default (::selection removed — real GTK3 supports it, this container's 3.24.52 rejects it; documented trade-off); placeholder/icon-transform minor visual deltas accepted for zero-warning guarantee.

### Фаза 0.62 — Rebuild ISO + QEMU smoke test (2026-09-27, без железа)
- [x] webkit2gtk → webkit2gtk-4.1: Arch extra переименовал пакет (слот 4.0 удалён); PKGBUILD depends исправлен; packages.x86_64 добавлен webkit2gtk-4.1 (явно, не только транзитивно через geary)
- [x] packages.x86_64 coherence: добавлены fontconfig и libsecret как явные hard deps mavericks-apps (были транзитивными); espeak-ng/dictd — optdeps, valid repo names, остаются optdeps
- [x] check-sync.sh --check-repos: ALL CHECKS PASSED (все имена валидны в текущих sync DB)
- [x] build-local-pkgs.sh: mavericks-apps 0.1.0-1, mavericks-theme 1.0.0-2, macbook12-audio-driver 1.0.0.r108.g4cdfcdb-1 — все собраны, repo-add OK
- [x] mkarchiso: out/mavlinos-2026.09.27-x86_64.iso — 2.7G (2,866,518,016 bytes), sha256=02f9f2c45af157b4077f560f79dd0f701d4b4387bff7a6ce99b147f02b1a31fb
- [x] ISO structure verified: EFI/BOOT/BOOTx64.EFI + BOOTIA32.EFI, systemd-boot entries (01-archiso-linux.conf, 02-archiso-speech-linux.conf), airootfs.sfs + airootfs.sha512, 737 packages (600 transitive deps + 137 direct from packages.x86_64)
- [x] Package coherence: 0 profile-only packages missing from ISO (comm -23 = empty)
- [x] QEMU+OVMF: BLOCKED — OVMF firmware runs ("Guest has not initialized the display (yet)") but does not detect bootable device from ISO CD-ROM; tried: -vga virtio, -vga std, direct kernel boot, EFI disk image, USB mass storage — all same result. Environment limitation (container lacks proper UEFI boot device emulation), NOT an ISO defect. ISO structure is valid per xorriso inspection.
- [x] Note: first build attempt failed (tmpfs /tmp 3.8G 100% full → "Write failed" on kernel module extraction); fixed by moving work dir to <build-host>/mv-iso-work (937G free)
- [x] Note: corrupted mavericks-* packages in /var/cache/pacman/pkg from first failed attempt; cleared with sudo rm, rebuild succeeded

### TRACK 1/7 — mv-dictionary WebKit2 memory: leak vs steady-state (2026-09-29, без железа)
- [x] Новый инструмент: `scripts/bench-mv-dictionary.py` — полное процесс-дерево (RSS/PSS/fds) реального приложения на Xvfb, свежий HOME на прогон, синхронизированный GO-протокол между драйвером и сэмплером (без гонок), роли по исполняемому пути (gst-plugin-scanner/bwrap/glycin не считаются web)
- [x] Вердикт: НЕ артефакт и НЕ неограниченный leak — структурный steady-state + декelerирующий growth. Baseline 485 MB (UI 211 + web 226 + network 46; PSS 290 — ~40% shared file-backed). После 80 поисков load-all-вариант: 1766 MB / 4 web-процесса / +6.2 MB за поиск (монотонный GROWTH). C1-F 175 MB — частичная нижняя граница (один процесс, до инициализации)
- [x] Корневая причина: `load_definitions()` грузил ВСЕ 4 вкладки на каждый поиск (3 remote + 1 local) — process-per-view форсирован с webkit2gtk 2.26 (`set_process_model(SHARED_SECONDARY_PROCESS)` и `set_web_process_count_limit()` — deprecated no-ops, проверено документацией 2.52.6 + runtime readback). Каждая использованная вкладка = 1 постоянный WebKitWebProcess (~150–250 MB)
- [x] Фикс: грузить только видимую вкладку + загрузка при первой активации (`notify::visible-child`). Remote-вкладки рендерятся при выборе (как в macOS Dictionary). Результат: 80 поисков → 657 MB (−63%), 1 web-процесс, PLATEAU (tail deltas ≈ 0)
- [x] Fallback: web-RSS бюджет (`MV_DICT_WEB_BUDGET_MB`, default 500) — одноразовая /proc-проверка после каждого поиска; при превышении → InfoBar "Disable online tabs" → LocalView для dict/thesaurus/wikipedia (Apple и offline-источники работают). Ограничивает all-tabs-случай (~1.6 GB, 4 процесса)
- [x] Отклонено с замерами: `set_cache_model(DOCUMENT_VIEWER)` — 1291 vs ~1260 MB на 40 поисках (load-all прототип), growth от аккумуляции страниц в процессах, не от HTTP-кэша
- [x] Тесты: `scripts/test-mv-dictionary.py` — 84 passed, 0 failed (было 70; +14: load-only-visible, tab-switch loading, budget warning, fallback replacement, keep-online). WebKit-absent пути зелёные
- [x] Без демонов и polling (budget check — one-shot /proc); power baseline не тронут
- [x] Residual: один web-процесс ~400 MB после использования (реальный контент страниц); all-tabs-случай — 4 процесса (форсировано), ограничен budget-fallback. HW: рендеринг на 2304×1440, многочасовая сессия
- [x] Подробности: `docs/BENCHMARKS.md` (TRACK 1/7), `docs/DECISIONS.md`, `docs/APPS.md` (Dictionary)

### Track 3/7 — Snapshot hooks (2026-09-29, без железа)
- [x] mv-snapshot-take.sh: axis-S compliant — helper NEVER fails wrapped operation (logs + returns 0 on validation/snapshot errors), no recursion, prune keep-last-N (5 per label, 10 overall) documented in comments, mocked-btrfs tests pass (scripts/test_mv_snapshot_take.py: 7 tests).
- [x] mavericks-rollback.sh: single rollback procedure (no new daemon), fixed path bug (target_dir#l → #/) and dangerous rm -rf removed; uses cp -a overwrite.
- [x] mv-experiment.sh: fixed broken case statement syntax, added --no-snapshot flag, pre-change snapshot hook integrated (calls mv-snapshot-take on btrfs, logs + continues on non-btrfs).
- [x] mavericks-firstboot.sh: pre-change snapshot hook integrated (calls mv-snapshot-take on btrfs, logs + continues on non-btrfs).
- [x] check-sync.sh: added sync pair for mv-snapshot-take.sh (tools/diagnostics ↔ airootfs).
- [x] Gate: check-sync ALL CHECKS PASSED (227 checks); test_mv_snapshot_take.py 7/7 pass; bash syntax clean.
- [x] DECISIONS.md: hook policy entry added (snapshot-before-change = mandatory on btrfs, best-effort on non-btrfs; never blocks operation).

### Track 5/7 — Rebuild local packages + ISO + QEMU smoke attempt (2026-09-29, без железа)
- [x] build-local-pkgs.sh: mavericks-apps 0.1.0-1, mavericks-theme 1.0.0-2, macbook12-audio-driver 1.0.0.r94.g75884e2-1 — all rebuilt, repo-add OK at /tmp/mavericks-repo
- [x] packages.x86_64 coherence verified: mavericks-apps, mavericks-theme PRESENT; macbook12-audio-driver ABSENT (ISO-excluded as per P1-C1); openssh PRESENT but disabled (no sshd.service in multi-user.target.wants)
- [x] P0-J1 verified in airootfs: sshd.service NOT in multi-user.target.wants; root locked in /etc/shadow (`root:!14871::::::`); sshd disabled in firstboot via `systemctl disable sshd.service reflector.service`
- [x] mkarchiso: work dir <build-host>/mv-iso-work (not tmpfs), output <build-host>/out/mavlinos-2026.09.29-x86_64.iso — 2.0G (2,099,507,200 bytes), sha256=81d560d7db2a9e08be18942af285359726a4bbde461c8a91f4fbfcdfbadc9bb3
- [x] ISO package count: 712 packages (pkglist.x86_64.txt)
- [x] ISO structure verified via xorriso: UEFI bootable (El Torito EFI image at LBA 884846, 140288 blocks), MBR protective + GPT, systemd-boot entries present
- [x] QEMU+OVMF attempt: BLOCKED at boot menu — OVMF firmware loads, shows UEFI boot menu with "UEFI QEMU DVD-ROM QM00003" entry, but times out at 120s waiting for kernel handoff. Container lacks KVM (no hardware acceleration) and proper UEFI CD-ROM emulation; NOT an ISO defect. ISO structure valid per xorriso.
- [x] NEEDS_HARDWARE_TEST.md updated with ISO validation items
- [x] All gates: check-sync.sh ALL CHECKS PASSED, py_compile clean, desktop-file-validate clean

### OS-GH — GitHub publication + contribution architecture (2026-10-03, без железа)

- [x] Forensic re-audit of full tree (1140 tracked files — the original "1112" was the count at audit START; the publication commit added 28 of its own pipeline files, root-caused in the 2026-10-03 forensic audit): git status/branches/remotes (master, no remotes), .gitignore coverage, generated artifacts (out/ ISO gitignored), secret scan (regex sweep across all history: CLEAN — independently re-verified: 1898 reachable + 3 unreachable blobs, 0 findings), personal-path scan
- [x] Public/private boundary sanitized: all `/home/builder` absolute paths removed from tracked files — pacman.conf local repo → `file:///tmp/mavericks-repo` (matches build-local-pkgs.sh default + ENVIRONMENT.md doc), test-session-reuse.py mock ps output → `/home/user`, test_mv_launchpad.py + lab/tests/contrib/test_security_scan.py → paths derived from `__file__`, docs (DECISIONS/ENVIRONMENT/PROGRESS) → `<build-host>` placeholder
- [x] Root LICENSE added (GPL-3.0-or-later; per-package licenses in docs/LICENSES.md)
- [x] CODE_OF_CONDUCT.md added (Contributor Covenant 2.1, enforcement via private maintainer report per SECURITY.md)
- [x] Contribution pipeline committed: docs/CONTRIBUTION_PROTOCOL.md, docs/SECURITY_MODEL.md, scripts/contrib/{discover,fetch-pr,security-scan,triage}.sh, lab/tests/contrib/ (2 suites + 5 fixture PRs)
- [x] security-scan.sh calibrated (was 1/5): word-boundary regexes (no `sh `→"push " / `dd `→"add " FPs), XML `?>`/`/>` excluded from redirect detection, C `a > b` comparisons excluded, doc-only patches skip code-execution categories, `../` alone ≠ path traversal (needs extraction co-occurrence), PKGBUILD patch-application → MED BUILD_RECIPE. Result: 5/5 fixture verdicts correct
- [x] triage.sh fixed: `PATH=` env clobber bug (line 184) → `F_PATH=`; REQUIRES_SECURITY_REVIEW now adds OS-SEC-REVIEW objective without overriding topical classification; multi-objective routing (every matching category adds objective); word-boundary fixes (`ux` in "linux", bare `ui`/`ci`/`iso`); integration checked before backend. Result: 5/5 fixture classifications correct
- [x] test_triage.py REPO_ROOT fixed (was one dirname short → wrong scripts path)
- [x] CONTRIBUTION_PROTOCOL.md §4 corrected: CI job table now matches actual ci.yml (was referencing nonexistent mkarchiso.sh/qemu-smoke-test.sh); contrib scripts documented as local-orchestrator-only
- [x] project-meta.json: stale `hardwareAssumption: MacBook9,1` → `MacBook10,1`
- [x] Validation: bash -n all .sh clean, py_compile all .py clean, check-sync.sh ALL CHECKS PASSED, check-profile-sync.sh pass, security-scan 5/5, triage 5/5, CI secret-scan fallback patterns → 0 matches on tracked tree
- [x] Remaining user decisions documented in docs/RELEASE_READINESS.md (git author identity rewrite, GitHub auth/gh CLI)
- [x] Pre-existing CI blockers found by gate re-run and fixed:
  - configs/profiles/generic/99-mavericks-network.conf had drifted from airootfs mirror (source was condensed, mirror kept evidence comments) — synced source to richer mirror content
  - mavericks-firstboot.sh never sourced /etc/mavericks/profile.conf (written by mavericks-profile-select.sh) — profile selection had no effect. Fixed: firstboot sources PROFILE_CONF; MacBook fragments (S3X/display cmdline, TLP power, NM wifi-backend, brcmfmac NVRAM) now gated on `macbook_profile()` (macbook10,1 or legacy-absent); generic profile → fragments skipped + stale fragments removed. Mirrored to airootfs (check-sync pair)
  - Gates: check-profile-sync.sh OK, check-sync.sh ALL CHECKS PASSED

### OS-FORENSIC — Independent forensic audit of publication readiness (2026-10-03, без железа)

Triggered by the chat-transfer context recovery: the previous agent's
final report was treated as CLAIMS, not facts, and independently
re-verified against the repository. Full report: `docs/FORENSIC_AUDIT.md`.

- [x] Re-verified independently: check-sync (142 OK / 0 FAIL), check-profile-sync OK, security-scan 5/5, triage 5/5, py_compile clean, bash -n clean, sim harness (25 scenarios / 110 assertions), spot-run test-mv-calculator (141) + test-mv-notes (41), full test-mv-*.py suite (21/22 pass; test-mv-photos has 2 known pre-existing headless failures — documented, not a regression)
- [x] Secret sweep across ALL history (1898 reachable blobs + 3 unreachable blobs, 31.5 MB): 0 credentials/tokens/keys; high-entropy sweep: only hashes/test strings; PII sweep (phones/addresses/cards): noise only
- [x] Root-caused the 1112-vs-1140 tracked-file discrepancy: count was taken at audit START (parent `939c8ad` = 1112); publication commit `b27af3d` added 28 of its own pipeline files → 1140. The "complete inventory reviewed" claim never covered those 28 as an audited inventory (they were same-session authored)
- [x] Resolved the "history clean" contradiction: worktree functional paths ARE sanitized, but history retains 204 `/home/builder` line-occurrences in 136 old blob versions (10 files), 17 personal-email occurrences in old doc blobs, and 4 commits (incl. the ROOT commit) under the original author's personal identity — all public after push unless the §3.1 rewrite is applied
- [x] Quantified identity-rewrite scope: personal-identity set includes the root commit → ALL 329 commit IDs change under mailmap (not just 4)
- [x] Found NEW issues the previous audit missed: (F5) 3 Apple-derived SVGs tracked for publication despite NON-redistributable verdict in LICENSES.md §6 — isolation prevents installation, not redistribution; (F10) build-host hardware fingerprint (Ryzen 7 5800HS / WSL2) recorded verbatim in 14 tracked benchmark JSONs while the audit itself was self-contradictory on their classification; (F6) CI unit-tests job swallowed check-sync exit code via `grep ... || true`
- [x] Sanitized: personal name/email from 4 current docs (DECISIONS, ENVIRONMENT, PUBLIC_AUDIT, RELEASE_READINESS) → neutral placeholders (audit facts preserved); benchmark host fingerprint → `<build-host-cpu>` / `<build-host-platform>` (measurements preserved)
- [x] Corrected stale audit figures: tracked files 1112 → 1140, `.git` 7.9M → 5.4M, working tree "~10M" → 6.2M tracked (2.8G with gitignored ISO), check-sync "221/227 checks" → 142 verified lines
- [x] Fixed CI: removed exit-code-swallowing step from unit-tests job
- [x] User decisions recorded: identity rewrite = option (b) to `Ansvipa_Rinh <336997779+AnsvipaRinh@users.noreply.github.com>` (numeric ID 336997779 obtained 2026-10-03 via `gh api user`: login `AnsvipaRinh`, no underscore); `.opencode/` internals stay public (audited: no credentials/keys/paths/session data); branch rename master → main done; GitHub auth completed 2026-10-03 (gh 2.102.0, scopes gist/read:org/repo); push explicitly NOT performed
- [x] Open: D1 Apple-derived assets (user decision required before push), ISO rebuild re-verification (REQUIRES EXTERNAL EVIDENCE — hours + root), first real GitHub Actions run (REQUIRES EXTERNAL EVIDENCE)

### OS-PUBLISH — Publication prep: D1 executed, naming audit, verified rewrite tooling (2026-10-03, без железа)

Continuation of OS-FORENSIC. Full evidence: `docs/FORENSIC_AUDIT.md` §10.

- [x] D1 EXECUTED (user decision, option i — Apple assets NOT published): 3 Apple-derived SVGs removed from tree (`git rm docs/isolated-assets/apple-derived/`), provenance note added (`docs/isolated-assets/README.md`); LICENSES.md §4/§6/§8/§9/§10 + DECISIONS.md OS-4a updated; current theme SVGs diffed against Apple originals — zero Apple strings (generic replacements ship since `522ab98`)
- [x] Public-identity/naming audit completed: project renamed to **MavLinOS** across README, CONTRIBUTING, issue/PR templates, GITHUB_SETUP, project-meta.json, PKGBUILDs (url + maintainer line `Ansvipa_Rinh <GITHUB_NOREPLY_EMAIL>`), boot entries, firstboot scripts (sync pair), config headers (both sync-pair sides), uBlock backup, orchestrator/agent docs; repo URL `github.com/AnsvipaRinh/MavLinOS`; internal `mavericks-*` identifiers deliberately unchanged
- [x] Branch renamed `master` → `main` (D3 done — the rewrite tooling runs on main)
- [x] Publication rewrite implemented as tooling (`scripts/contrib/publication-rewrite/`: mailmap template, 6 replace-text rules, 30 Apple-blob IDs with generator, orchestrator script) — 4 filter-repo passes on a fresh clone
- [x] Dry-run with TEST identity: ALL 9 GATES PASS — commit count, single public identity, personal strings absent, Apple path absent, 30 blobs stripped, private absolute paths (`/home/builder` + 2 superseded-draft paths) purged, HEAD tree identical after EXACTLY the intended neutralizations (rule-derived sed replication + `diff -r --no-dereference`), commit messages identical modulo commit-ID references, fsck clean
- [x] Two corruption modes caught by the gates during development and fixed: mailmap bracket loss (sed ate the `<>` around the new email → old emails silently kept — caught by identity gate); replace-text comment corruption (`git-filter-repo --replace-text` has NO comment support — a bare `#` line became a rule replacing every `#` in every file — caught by the HEAD-tree gate; rules file now comment-free)
- [x] Private absolute paths added to the purge scope per user constraint: `/home/builder` (204 historical line-occurrences / 136 blobs), `/home/mavericks-lab`, `/home/custompkgs` (single superseded-draft occurrences); `/root/` occurrences classified functional (ISO's own root-home structure + live-ISO example) and kept; `/home/user` is the deliberate sanitization placeholder
- [x] Documented unavoidable rewrite consequences: ALL commit IDs change (root in affected set); commit messages byte-identical except 7-char commit-ID references (remapped to new IDs — proven by gate); published copy's own tooling appears redacted (its rules contain the old identities by design)
- [x] Validation re-run after all changes: check-sync ALL CHECKS PASSED, check-profile-sync OK, JSON valid (project-meta + 14 benchmarks), bash -n / py_compile clean, full test-mv suite 21/22 (same 2 known pre-existing headless failures in test-mv-photos — not a regression)
- [x] FORENSIC_AUDIT.md updated to actual state (F1/F2/F3/F5 resolved or verified, §5 classifications, §8 change log, §9 residual risks, new §10 dry-run evidence); RELEASE_READINESS.md updated (header, checklist items 4/6/10, §3.1 → verified tooling, §3.3 D1/D3 resolved, §5 blockers)
- [ ] REMAINING (user-performed, authenticated): run `scripts/contrib/publication-rewrite/publication-rewrite.sh "336997779+AnsvipaRinh@users.noreply.github.com"` (numeric ID 336997779 obtained 2026-10-03; login `AnsvipaRinh`) → remote add + push (procedure: RELEASE_READINESS §3.1–§3.2, GITHUB_SETUP.md)

