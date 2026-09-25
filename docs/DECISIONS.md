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

**Date:** 2026-09-25 (corrected Phase 0.5)
**Decision:** Use linux-zen kernel and systemd-boot for UEFI-only boot on MacBook 12".

**Reasoning:**
- linux-zen provides better interactive responsiveness on fanless Core M hardware
  (HZ=1000, PREEMPT=y, CFS scheduler with desktop-tuned latencies).
- CORRECTION: Arch linux-zen does NOT use MuQSS (earlier text was wrong).
  MuQSS is used by Liquorix; Arch zen uses CFS. No custom scheduler.
- MacBook 12" (A1534) is UEFI-only — no BIOS/CSM support needed
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

**Configuration:** /etc/systemd/zram-generator.conf.d/99-mavericks.conf sets zram-size = ram / 2, zstd. No sysctl overrides in baseline (kernel defaults). Firefox sessionstore.interval=60s to reduce SSD writes.

---

## Phase 0.3 baseline (source of truth)

**Date:** Phase 0.5 implementation
**Kernel cmdline:** `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`
- `pcie_port_pm=off` = sole MacBook10,1 provisional workaround (Sep 2026 LKML: Apple S3X resume).
- `i915.enable_psr=0` = diagnostic-safe baseline (generic flicker risk).
- Turbo ON, APST default, FBC auto, GuC default, THP default, VM defaults.
**Browser:** Firefox ESR (current, not version-pinned) + uBlock Origin. Epiphany removed from ISO.
**Notifications:** xfce4-notifyd (native), not dunst.
**Measurement:** read-only tools only; `powertop --auto-tune` BANNED from baseline.

---

## Power management: TLP only (thermald + ananicy-cpp REMOVED)

**Date:** 2026-09-25 (corrected Phase 0.5)
**Decision:** TLP only. thermald and ananicy-cpp removed.

**Reasoning:**
- TLP docs: thermald "does not conflict with TLP" but is also redundant on
  HWP systems where kernel + TLP govern power; no DPTF-profile need demonstrated.
- ananicy-cpp: nice-level tweaks with no measurable battery/perf benefit.
- Minimum policy engines: TLP + kernel thermal management.
- TLP baseline: governor=powersave, ASPM=powersave, USB_AUTOSUSPEND=1,
  RUNTIME_PM=auto. CPU_BOOST/PLATFORM_PROFILE/EPP unset (experiments).

---

## Phase 0.6 pre-hardware coherence fixes (no hardware)

**Date:** 2026-09-25
**Decisions:**
1. `mavericks-theme` added to `packages.x86_64`. skel/xsettings referenced
   `gtk-theme-name=Mavericks` but the package was never installed in the ISO —
   live session would fall back to stock Adwaita/Raleigh (P0 coherence break).
2. `mavericks-theme` + `epiphany-mavericks-theme` PKGBUILDs rewritten to
   repo-local sources (same pattern as `mavericks-apps`: no network fetch).
   Both previously cloned nonexistent `github.com/mavericks-linux/*.git`
   repos, so `scripts/build-local-pkgs.sh` could never build them.
3. `epiphany-mavericks-theme` → DEFERRED (system browser is Firefox ESR;
   Epiphany not in ISO). Kept buildable offline; built only with `--all`.
4. `packages.x86_64`: removed `dunst` (second notification daemon —
   contradicts xfce4-notifyd-only decision; risk of autostart conflict),
   removed `grub` (ISO bootmodes = `uefi.systemd-boot` only; A1534 has no
   BIOS/CSM), added `gvfs` (Thunar Trash/volumes — required for the
   Finder=IMPLEMENTED and Trash=IMPLEMENTED claims in APPS.md),
   `gtk-engine-murrine` (hard dep of mavericks-theme), `libnotify`
   (notify-send backend for mv-reminders/mv-control).
5. Theme SCSS fixed and verified by actual `sassc 3.6.2` compilation
   (gtk-3.0 ~26KB, gtk-3.20 ~27KB, epiphany ~4KB CSS): dropped 14
   nonexistent `@import`s, fixed malformed `border-radius ... / 8px`,
   converted GTK `@var` syntax to SCSS `$var` in compiled files,
   fixed `gtk-3.30` typo, fixed unterminated heredoc in epiphany PKGBUILD.
6. Empty `archiso-profile/.../etc/ananicy.d/` removed (leftover of the
   removed ananicy-cpp); `powertop` package KEPT (used read-only via
   `powertop --time=20 --csv` in mv-collect; only `--auto-tune` is banned).

---

## Phase 0.7 pre-hardware hardening (no hardware)

**Date:** 2026-09-25
**Decisions:**
1. `gtk-engine-murrine` removed from `mavericks-theme` deps and ISO list.
   The theme is GTK3-only (no gtk-2.0 dir, no murrine directives in SCSS) and
   the package no longer exists in current Arch repos. ISO package list and
   `mavericks-apps` deps are now fully verified against Arch sync DBs
   (`scripts/check-sync.sh --check-repos`); only the two local packages are
   expected to be absent upstream.
2. Thunar custom actions hardened: quote all `%`-placeholders (paths with
   spaces broke Quick Look/Compress/Terminal/New Folder), `New%20Folder`
   (literal — Thunar does not URL-decode) → `"New Folder"`, bare interactive
   `trash-restore` (hangs without a terminal) wrapped as
   `xfce4-terminal --hold -e trash-restore`.
3. firstboot install flow defined: repo checkout must exist (auto-detected at
   `/root/macbook12-macos-linux` etc., clear error otherwise); local packages
   (`mavericks-apps`, `mavericks-theme`) install from nearby `.pkg.tar.zst`
   via `pacman -U` first (ISO build output / checkout / live medium), repo
   second, explicit warning last. Rationale: local packages are NOT in
   upstream repos, so a bare `pacman -S` could never succeed on the target.
4. `scripts/`+`tools/`+`configs/` are sources of truth; the ~26 mirror copies
   under `archiso-profile/.../airootfs` are build artifacts of those sources.
   `scripts/check-sync.sh` is the pre-commit gate enforcing this (sync +
   bash/py/XML/desktop/PKGBUILD checks). Symlinks are not used because
   airootfs is a plain directory tree consumed by mkarchiso.

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
---

## Mission Control: skippy-xd as gated E-MC experiment, one-shot (no daemon)

**Date:** 2026-09-25
**Decision:** Mission Control baseline stays rofi window mode (zero new
dependencies). The real overview is experiment E-MC: skippy-xd expose,
invoked one-shot (`skippy-xd`, no arguments), gated behind
`configs/profiles/experiments/E-MC-skippy-xd.sh` (apply/revert/status),
NOT enabled by default in the ISO.

**Reasoning (verified pre-hardware via AUR RPC + upstream source):**
- AUR has no stable `skippy-xd` package — only `skippy-xd-git` (VCS,
  maintainer xiota, GPL-2.0-or-later, updated 2026-09-13). A -git dependency
  in the default ISO would be fragile (build-at-install, git+codeberg
  sources); experiment-gating avoids that risk while keeping the path ready.
- Upstream man page: bare `skippy-xd` = one-shot expose with no daemon.
  Daemon mode (`--start-daemon`) exists only for previews of
  minimized/unmapped windows — a permanent resident process, rejected for
  the fanless power budget. One-shot = zero idle cost.
- Runtime deps are light X libs only (giflib, libjpeg-turbo, libxcomposite,
  libxdamage, libxext, libxft, libxinerama); no compositor required
  (pseudoTrans=false since xfwm4 compositing is on).
- Upstream owns `/etc/xdg/skippy-xd.rc`, so our tuning ships per-user at
  `/etc/skel/.config/skippy-xd/skippy-xd.rc` (source:
  `configs/desktop/skippy-xd/skippy-xd.rc`, sync-gated) — no package conflict.
- `exposeLayout = cosmos` (position-preserving) is the closest to Mission
  Control; `animationDuration` 200→150ms for HD 615 snappiness.

**Alternatives considered:** promoting skippy-xd-git to default ISO now —
rejected (VCS fragility + unvalidated xfwm4 interplay); bespoke X11 overview
frontend — rejected for now (reuse-first; revisit only if E-MC fails on HW).

**HW validation (E-MC apply on target):** expose shows all windows
non-overlapping; arrows+Return select; Escape cancels; Super+Tab rebind works
via xfconf-query; minimized windows show filler (accepted: daemon stays off).
