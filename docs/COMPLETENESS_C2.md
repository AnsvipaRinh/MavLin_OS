# COMPLETENESS C2 — Completeness Research Track (RESEARCH, no production patches)

> Track C2: challenge the previous audit's assumptions along NEW axes J–S.
> Method: Observe → Hypothesis → Measure → Decide. High-confidence findings
> become implementation proposals; NO production code patched in this task
> (bench harness additions only — they are test tooling, not system code).
> Date: 2026-09-29. Host: WSL2 Arch (AMD R7 5800HS 3.19 GHz, 2 vCPU, 7.6 GB).
> Companion to: COMPLETENESS_C1.md, ARCHITECTURE_OPTIMIZATION_AUDIT.md,
> PERF_METHODOLOGY.md, SERVICE_AUDIT.md, DEPENDENCY_AUDIT.md, NEEDS_HARDWARE_TEST.md.

## Verdict summary

| Axis | Status | Key number |
|---|---|---|
| J — Security/perf | PARTIALLY (1 real P0) | ISO: sshd ENABLED + PermitRootLogin yes + root EMPTY password |
| K — Build/ELF optimization | PROVEN-COMPLETE | mv-hud: all flag variants 14320 B identical; runtime = spawn+/sys floor |
| L — Resource/UI loading | PARTIALLY | theme CSS parse 4.1–4.5 ms/process; AppInfo.get_all 12–14 ms; typelib 163–324 ms |
| M — Firefox startup/profile | PARTIALLY | profile seed 44 KB but NO profiles.ini (activation unverified); 9 uBO lists |
| N — YouTube pipeline | PROVEN-COMPLETE | 3 processes/playback (bash→mpv→yt-dlp); 1 metadata resolution; no residue |
| O — ISO minimalism | PARTIALLY | 129 pkgs classified; intel-gpu-tools 31.5 MiB top removal candidate |
| P — Service parallelism | PROVEN-COMPLETE | tlp/zram/NM/resolved/lightdm/BT all parallel; no artificial serialization |
| Q — Logging/journal | PROVEN-COMPLETE | mv-timemachine 64 B/h only recurring noise; calendar/reminders silent |
| R — Observability itself | PARTIALLY | S23: host drift ±20% within batch > cold-cache effect; S03 repeats=1 = cold |
| S — Failure/recovery | DESIGN | 7 failure classes × rollback path; lab A/B + btrfs + restic + git |

**New P0/P1 implementation proposals (with measurements):**
- **P0-J1: Harden ISO SSH** — sshd.service is enabled in the ISO with `PermitRootLogin yes` + `PasswordAuthentication yes` and root has an EMPTY password (`root::` in airootfs shadow). sshd's default `PermitEmptyPasswords no` blocks empty-password login, but the config is wrong and the attack surface is real. Fix: disable sshd in ISO (firstboot already does on install), set root password to locked (`root:!`), or remove the permissive sshd_config.d override.
- **P1-O1: Remove intel-gpu-tools from ISO** (31.5 MiB installed) — diagnostic-only, largest single removal candidate. Move to AUR/optional or a recovery-only profile.
- **P1-O2: Evaluate ~25 OPTIONAL/P2 packages** (~60 MiB combined) — lvm2, xfsprogs, jfsutils, f2fs-tools, udftools, mdadm, sg3_utils, nfs-utils, etc. — no users on MacBook10,1 (btrfs target, NVMe, no RAID/LVM/NFS). Keep recovery-critical (testdisk, ddrescue, partclone, fsarchiver, gptfdisk, cryptsetup, smartmontools, nvme-cli).
- **P1-M1: Add profiles.ini to Firefox seed** — the 44 KB seed (user.js + userChrome.css + userContent.css) has NO profiles.ini/installs.ini/times.json; Firefox may not auto-activate `mavericks.default`. Activation path unverified offline. Add profiles.ini for determinism.
- **P1-L1: (optional) shared .desktop parse cache** — mv-launchpad (15.5 ms) + mv-spotlight (12.1 ms) re-parse the desktop DB manually on every open. A mtime-keyed cache would save ~12–15 ms per open. Low priority (small vs 300 ms startup).

**C3 handoff (ripest remaining axes):** T (per-app deep-dive: mv-dictionary WebKit2 175 MB memory), U (HiDPI/2304×1440 rendering calibration), V (real Firefox startup on hardware), W (applespi 3-strategy limit), X (S3X NVMe resume validation). Several are HW-REQUIRED — see NEEDS_HARDWARE_TEST.md.

---

## AXIS J — Security/perf

**STATUS:** PARTIALLY (one real P0 finding; rest clean-by-design)
**MEASURED?:** Yes — full privilege-transition grep + sshd/root config audit + unit hardening review
**HARDWARE_REQUIRED?:** No

### Evidence

**ISO SSH state (P0 finding):**
- `airootfs/etc/systemd/system/multi-user.target.wants/sshd.service` — sshd is ENABLED in the ISO.
- `airootfs/etc/ssh/sshd_config.d/10-archiso.conf`: `PasswordAuthentication yes` + `PermitRootLogin yes`.
- `airootfs/etc/shadow`: `root::14871::::::` — root has an EMPTY password.
- Net effect: the ISO ships with a running SSH daemon permitting root login, and root has no password. sshd's compiled-in default `PermitEmptyPasswords no` blocks empty-password login, so this is not a trivially exploitable root shell — but the configuration is wrong and the attack surface is real (any local-network user can attempt root login; password auth is on).
- Firstboot DOES disable sshd on the installed system (`systemctl disable sshd.service`, mavericks-firstboot.sh:60) — but the permissive sshd_config.d override remains, so any future `systemctl enable sshd` re-exposes root login.

**Polkit:** No polkit rules shipped (no `.pkla` files anywhere in repo). No `pkexec` usage in any mv-* app or script. This is the safe pattern — no privilege-escalation paths in our code.

**Privilege transitions in our code:**
- `mavericks-firstboot.sh:83,85`: `sudo -u "$TARGET_USER" systemctl --user enable ...` — root→user drop, correct direction.
- Diagnostic scripts (`mv-power.sh`, `mv-thermal.sh`, `mv-collect.sh`, `mv-experiment.sh`, `mv-suspend-test.sh`): require sudo, run as root, read-only or write to `/var/log/mavericks-*`. Acceptable.
- `mv-control:712-715`: TLP mode switching — currently shows info + tells user to run `sudo tlp set-mode` manually. No auto-escalation. Safe.
- No setuid binaries, no pkexec, no polkit rules. The privilege model is "user runs sudo manually when needed" — the safest possible for a desktop.

**Systemd hardening in our units:** None of the 6 user units (mv-calendar/mv-reminders/mv-timemachine × service+timer) have `ProtectSystem`, `NoNewPrivileges`, `PrivateTmp`, or `ProtectHome`. They are user oneshots running the user's own notify scripts — low risk. Adding `NoNewPrivileges=true` would be cheap but is cosmetic for user oneshots.

**Equal-security-cheaper cases:** None found. The units are already minimal; the privilege model is already the safe manual-sudo pattern.

### Open questions
- Whether the ISO sshd is intentional (remote bring-up convenience) or an archiso default — either way it should be explicit, not accidental.
- Whether root's empty password is an archiso default or a build artifact — should be locked (`root:!`) regardless.

### Next action
- P0-J1: disable sshd in ISO packages/wants + lock root password + remove permissive sshd_config override (or scope to a recovery profile).
- No other security changes warranted — the privilege model is already correct.

---

## AXIS K — Build/ELF optimization

**STATUS:** PROVEN-COMPLETE (no flag changes warranted)
**MEASURED?:** Yes — 6 flag variants compiled + sized + runtime-measured; GCC march support checked
**HARDWARE_REQUIRED?:** No

### Evidence

**mv-hud build flags** (Makefile): `CFLAGS = -march=skylake -mtune=skylake -O2 -pipe -fno-plt`, `LDFLAGS = -Wl,-O1,--sort-common,--as-needed -s`. Comment: "Target CPU: Kaby Lake-Y (m3-7Y32)".

**Finding 1 — `-march=skylake` is CORRECT for m3-7Y32, not a bug.** GCC 16.2.1 (host) does NOT accept `-march=kaby-lake` (removed from the valid list; kaby-lake was an alias of skylake for codegen — Kaby Lake has no ISA additions over Skylake that affect compiler tuning). The valid list jumps `skylake-avx512 → cannonlake`. So `-march=skylake` is the right and only correct choice for m3-7Y32 on modern GCC. The comment/flag mismatch is cosmetic.

**Finding 2 — zero headroom from flag changes.** Six variants compiled from the same 117-line C source:

| Variant | Size (bytes) | Runtime (µs, 100-run avg) |
|---|---|---|
| current (-O2, stripped) | 14320 | 4134 |
| -O3 | 14320 | 4674 |
| -Os | 14320 | 4410 |
| -O2 + LTO | 14320 | 4116 |
| -O2 no-strip | 16448 | — |
| -O0 | 16832 | 4279 |

All optimized variants produce IDENTICAL size (14320 B) — the binary is dominated by libc startup + ELF overhead, not the compiled code. Runtime is dominated by process spawn (~1.6 ms floor) + `/sys` reads (opendir `/sys/class/powercap`, `/sys/class/thermal`), not the compiled code. Flag changes have zero measurable effect.

**Finding 3 — PGO has no case.** The workload is `/sys` reads (opendir/fopen/fscanf) — PGO optimizes branch layout, not syscalls. The hot path is kernel-bound, not CPU-bound.

**Finding 4 — LTO has no case.** Identical size (14320 B), adds build complexity. No gain.

**Finding 5 — stripping is already on** (`-s` in LDFLAGS). no-strip is +15% (16448 B).

**PKGBUILD flags:** mavericks-apps PKGBUILD does not override CFLAGS (uses Makefile defaults). mavericks-theme PKGBUILD uses sassc + optipng (no C). epiphany-mavericks-theme: no C. macbook12-audio-driver: DKMS (kernel flags govern). No march/LTO/stripping issues in any PKGBUILD.

### Open questions
- None — mv-hud is at the floor; the build flags are correct.

### Next action
- None. Axis K is closed. The `-march=skylake` comment could be clarified ("Kaby Lake = skylake codegen on GCC ≥ 14") but that is cosmetic.

---

## AXIS L — Resource/UI loading

**STATUS:** PARTIALLY (measured; one reusable finding)
**MEASURED?:** Yes — CssProvider load, AppInfo.get_all, icon lookup, Pango fonts, typelib imports (fresh-process)
**HARDWARE_REQUIRED?:** No

### Evidence

**Method:** in-process medians (11 samples, 3 warmup) on host with theme installed; typelib imports measured as fresh-process wall (5 samples each).

| Resource | Cost | Paid by | Cached? |
|---|---|---|---|
| Gtk.CssProvider load (27 KB theme CSS) | 4.07–4.5 ms | every GTK3 app, once per process | no (per-process) |
| AppInfo.get_all() (108 desktop files) | 12.0–14.2 ms | mv-launchpad, mv-spotlight (manual parse) | no (per-call) |
| mv-launchpad.load_desktop_apps (Python) | 15.5 ms | mv-launchpad every open | no |
| mv-spotlight.load_desktop_apps (Python) | 12.1 ms | mv-spotlight every open | no |
| Icon lookup (Gtk.IconTheme) | 0.008–0.013 ms | any app | yes (after first) |
| Pango font families | 0.01 ms | any app | yes |
| Typelib import Gtk | 324 ms | every GTK app | per-process |
| Typelib import WebKit2 | 308 ms | mv-dictionary | per-process |
| Typelib import Gdk | 253 ms | GTK apps | per-process |
| Typelib import GLib/Gio/GdkPixbuf/Pango | 193–223 ms | most apps | per-process |
| Typelib import Secret / AppIndicator3 | 163–172 ms | mv-keychain / panel | per-process (rc=256 on host: not installed) |

**Key findings:**
1. **Theme CSS parse is 4.1–4.5 ms per process** — every one of the 32 mv-* GTK apps pays this at startup. It is part of the 331 ms startup floor (C1 axis B). Not cached across processes. Not reducible without shrinking the CSS (27 KB is already lean).
2. **Desktop DB re-parse is the one reusable finding** — mv-launchpad (15.5 ms) and mv-spotlight (12.1 ms) parse .desktop files MANUALLY in Python on every open. The Python cost is comparable to Gio's C `AppInfo.get_all()` (12–14 ms) because both are disk-bound (reading 108 files). A shared mtime-keyed cache (like plocate for files) would eliminate ~12–15 ms per open. Low priority: small vs the 300 ms startup dominated by typelib imports.
3. **Icon lookup and font discovery are negligible** (0.01 ms, cached). No action.
4. **Typelib imports dominate startup** (163–324 ms) — confirms C1 axis B. The Python interpreter floor is 26 ms (`python -c pass`); the rest is gi/typelib. No rewrite warranted (C1 axis B verdict stands).
5. **Inline CssProvider.load_from_data** in 5 apps (mv-airdrop, mv-calculator, mv-timemachine, mv-colormeter, mv-shot) — small inline CSS strings, cheap, correct pattern.
6. **No redundant cache scanning** — fontconfig/MIME/desktop cache invalidation is clean (C1 axis G confirmed).

### Open questions
- Whether a shared .desktop parse cache is worth it — 12–15 ms per launchpad/spotlight open, vs the complexity of cache invalidation. Probably not at current scale.

### Next action
- P1-L1 (optional): shared .desktop parse cache for mv-launchpad/mv-spotlight.
- No other UI-loading changes warranted — the costs are either negligible or already at the floor.

---

## AXIS M — Firefox startup/profile

**STATUS:** PARTIALLY (config-level analysis complete; runtime startup cost HW-REQUIRED)
**MEASURED?:** Partially — profile seed size + config audit measured; uBO list sizes + startup cost NOT-MEASURABLE offline (no Firefox on host)
**HARDWARE_REQUIRED?:** Yes — real Firefox startup cost, uBO filter-list load, SponsorBlock runtime, VAAPI/WebRender behavior

### Evidence

**Profile seed (measured):** 44 KB total in `airootfs/etc/skel/.mozilla/firefox/mavericks.default/`:
- user.js: 5759 bytes (synced with configs/firefox/user.js via check-sync)
- chrome/userChrome.css: 16251 bytes
- chrome/userContent.css: 1855 bytes

**GAP — profile activation unverified:** the seed has NO `profiles.ini`, NO `installs.ini`, NO `times.json`, NO `prefs.js`. Firefox's legacy-profile auto-detection may pick up `mavericks.default` when profiles.ini is absent, but this is version-dependent and the seed lacks the marker files (times.json/prefs.js) that make detection deterministic. Without profiles.ini, the seed may be orphaned and Firefox creates `default-release` instead. **The seed is inert until activation is verified.** Fix direction: add `profiles.ini` + `installs.ini` to the seed (or a firstboot step that copies the profile and writes profiles.ini).

**uBlock Origin:** 9 filter lists enabled (easylist, easyprivacy, ublock-filters, ublock-badware, ublock-privacy, ublock-unbreak, ublock-resource-abuse, urlhaus-1). The backup file (`configs/firefox/ublock-backup.json`) is 2324 bytes — settings only, NOT the lists. The lists are downloaded by uBO at first run and auto-updated every few days. Raw list sizes are NOT-MEASURED offline (no Firefox, no network); estimated ~30–40 MB raw at first run from uBO list characteristics (urlhaus alone is ~100k+ entries). This is a one-time cost + periodic update, cached in the uBO storage.

**SponsorBlock:** force-installed via `policies.json` (`sponsorBlocker@ajay.app`, force_installed from AMO). Cost class: extension download at first run (network) + per-video API calls to `sponsor.ajay.app` (small JSON, a few KB per video). Privacy consideration: video ID is sent to a third-party server. This is a deliberate feature (SponsorBlock), not a bug, but it is a network dependency + privacy surface that should be documented to the user.

**Session-restore prefs (from 6fd8fed, quantified):**
- `browser.sessionstore.restore_on_demand = true` — tabs restore on demand, not all at once.
- `browser.sessionstore.restore_pinned_tabs_on_demand = true` — pinned tabs too.
- `browser.sessionstore.max_tabs_on_startup = 10` — cap tabs restored.
- `browser.sessionstore.max_windows_on_startup = 3` — cap windows restored.
- `browser.sessionstore.interval = 60000` — 60 s (default 15 s), fewer SSD writes.
- Effect: bounds startup cost to ≤10 tabs + ≤3 windows, restored lazily. Actual startup cost reduction HW-REQUIRED to measure (no Firefox on host).

**Cache/history/thumbnail audit (SSD frugality):**
- `browser.cache.disk.capacity = 102400` (100 MB cap) — good, memory cache handles the rest.
- `browser.sessionstore.interval = 60000` — good.
- `places.history.enabled = true` — history grows with browsing; no explicit cap pref set. Firefox auto-expires history based on disk-space heuristics, so this is self-limiting but unbounded in the short term. Minor.
- Thumbnails: stored in `~/.cache/mozilla/firefox/*/thumbnails` — small, self-limiting.
- `policies.json`: DisableTelemetry, DisableFirefoxStudies, DontCheckDefaultBrowser — good (no background telemetry).

**EXPERIMENT prefs (commented out, hardware-validation items):** media.ffmpeg.vaapi.enabled, gfx.webrender.all, layers.acceleration.force-enabled, media.hardware-video-decoding.force-enabled, dom.ipc.processCount, browser.tabs.unloadOnLowMemory. Correctly left as experiments — not assumed.

### Open questions
- Real Firefox startup cost with the seed profile + uBO + SponsorBlock — HW-REQUIRED.
- Whether the profile seed auto-activates without profiles.ini — recommend adding profiles.ini for determinism (P1-M1).
- uBO filter-list load time at first run — HW-REQUIRED (network + Firefox).

### Next action
- P1-M1: add profiles.ini + installs.ini to the Firefox seed (or firstboot activation step).
- HW: measure real Firefox startup + uBO load on target.
- Document SponsorBlock's third-party API privacy surface to the user.

---

## AXIS N — YouTube pipeline

**STATUS:** PROVEN-COMPLETE
**MEASURED?:** Yes — static process/network analysis of mv-ytplayer + mpv + yt-dlp chain
**HARDWARE_REQUIRED?:** Yes — actual playback power/thermal on Gen9.5 (codec policy validation)

### Evidence

**Process creations per playback: 3** — `bash mv-ytplayer` → `mpv --ytdl-format=...` → `yt-dlp` (spawned internally by mpv for URL resolution). No resident processes, no teardown residue (mpv `--keep-open=no` exits after playback).

**Network round-trips: 1 metadata resolution + stream fetches.** The 5-branch codec chain (`avc1, vp09, hev1, !av01, any`) is a SINGLE yt-dlp format string (comma-separated fallback) — evaluated in ONE pass by yt-dlp, no duplicate metadata fetches. The chain is built from the editable policy file (`/etc/mv-ytplayer/codec-policy.conf`: avc1 > vp09 > hev1, AV1 excluded from preference). Correct design.

**Codec policy rationale:** Gen9.5 (HD 615) has AVC/VP9/HEVC HW decode, AV1 SW-only. The policy prefers HW codecs and excludes AV1 from preference (last-resort branches 4–5 allow AV1 only if nothing else is available). The policy file is explicitly marked NO-CONCLUSION — final choice comes from measured power/thermal on MacBook10,1 (see HW_BROWSER_MATRIX.md 4-mode plan). Correct: policy is a starting point, not a conclusion.

**Player startup:** `mpv --hwdec=auto --ytdl-format=$CHAIN --force-window=yes --keep-open=no`. `--hwdec=auto` lets mpv pick HW decode when available. `--force-window=yes` creates a window even for audio-only. Clean.

**Integration:** Thunar action (`thunar-uca-ytplayer.xml`, video-files pattern), `mv-ytplayer://` protocol handler (Firefox bookmarklet handoff), no regular `.desktop` (intentional — it is a playback backend, not a launcher). The `--explain` mode prints the codec chain + HW status + live yt-dlp query for diagnostics.

**Teardown residue:** none — mpv exits, yt-dlp exits, mv-ytplayer exits. No cache cleaning (yt-dlp cache in `~/.cache/yt-dlp` is small and self-limiting).

### Open questions
- Actual power/thermal per codec on Gen9.5 — HW-REQUIRED (HW_BROWSER_MATRIX.md 4-mode plan).
- Whether `--hwdec=auto` reliably picks HW decode on Gen9.5 — HW-REQUIRED.

### Next action
- HW: validate codec policy on target (4-mode measurement per HW_BROWSER_MATRIX.md).
- No code changes warranted — the pipeline is clean.

---

## AXIS O — ISO minimalism

**STATUS:** PARTIALLY (classification complete; removals are proposals per track rules)
**MEASURED?:** Yes — all 129 packages classified + installed sizes measured for OPTIONAL candidates
**HARDWARE_REQUIRED?:** No (classification); Yes (ISO size verification after removal)

### Evidence

**ISO size (measured):** 2.87 GB (`out/mavericks-linux-2026.09.27-x86_64.iso`, 2866518016 bytes). Dominated by base system + firefox + webkit2gtk-4.1 (133 MiB) + mesa/Xorg/Xfce + linux-zen + fonts + firmware. The mavericks-theme package is ~500 KB (tiny).

**Classification of 129 packages:**

| Class | Count | Packages | Verdict |
|---|---|---|---|
| BASE (boot/core/desktop) | ~85 | base, linux-zen(+headers), linux-firmware, intel-ucode, mkinitcpio*, systemd-resolvconf, zram-generator, tlp, networkmanager, wpa_supplicant, iwd, dhcpcd, bluez(+utils), pipewire*(3), wireplumber, upower, gvfs, fontconfig, gsfonts, wireless-regdb, xorg-server/xinit/xrandr, xfce4-* (14), lightdm(+greeter), plank, thunar(+archive), trash-cli, xdg-*, xarchiver, ffmpeg(+thumbnailer), intel-media-driver, mpv, yt-dlp, firefox(+ublock), webkit2gtk-4.1, mvericks-apps, mavericks-theme, rofi, libnotify, libsecret, seahorse, galculator, gcolor3, geary, evince, gnome-disk-utility, gnome-font-viewer, gthumb, lollypop, pavucontrol, mousepad, nano, sudo, openssh, xdotool, xfce4-genmon, adwaita-icon-theme, alsa-utils, btrfs-progs, restic, efibootmgr, plocate, arch-install-scripts, reflector, dmidecode, ethtool, usbutils, man-db, man-pages, tmux, zsh, terminus-font, less, diffutils, bash-completion | KEEP — all verified used or boot-critical |
| RECOVERY (bring-up) | ~15 | ddrescue, testdisk, partclone, fsarchiver, gptfdisk, parted, fatresize, cryptsetup, smartmontools, nvme-cli, squashfs-utils, arch-install-scripts, reflector, stress-ng (mv-thermal.sh), btrfs-progs, restic | KEEP — diagnostics/recovery for bring-up |
| OPTIONAL/P2 (removal candidates) | ~25 | **intel-gpu-tools (31.5 MiB!)**, lvm2 (5.3), xfsprogs (4.7), jfsutils, f2fs-tools, udftools, dosfstools, exfatprogs, nfs-utils, mdadm, sg3_utils (3.4), mmc-utils, hdparm, sdparm, lsscsi, tcpdump, powertop, turbostat, mesa-utils, terminus-font (3.1), bash-completion (1.0), tmux (1.2), less, diffutils, ethtool, dmidecode, usbutils | PROPOSE REMOVE or move to recovery-profile/AUR |

**Top removal candidates (by size):**
1. **intel-gpu-tools: 31.5 MiB** — diagnostic-only (intel_gpu_top, intel_gpu_time, etc.), largest single package in the ISO. No users in our code. Remove or move to recovery profile.
2. **lvm2: 5.3 MiB** — no LVM on target (btrfs). Remove.
3. **xfsprogs: 4.7 MiB** — no XFS on target (btrfs). Remove.
4. **sg3_utils: 3.4 MiB** — SCSI diagnostics, useless on NVMe. Remove.
5. **terminus-font: 3.1 MiB** — console bitmap font; useful for HiDPI console but optional. Evaluate.
6. **jfsutils, f2fs-tools, udftools, dosfstools, exfatprogs, nfs-utils, mdadm, mmc-utils, hdparm, sdparm, lsscsi, tcpdump, powertop, turbostat, mesa-utils** — all small (0.1–1.4 MiB), no users on target. Remove or recovery-profile.

**Attack-surface candidates (running services):**
- **openssh** — sshd ENABLED in ISO (see axis J P0). Biggest attack surface.
- reflector — one-shot, ISO-only, disabled on install. Low.
- iwd — disabled on install (firstboot). Low.
- dhcpcd — not enabled (NM handles DHCP). Low.
- nfs-utils — client only, no server. Low.

**RAM candidates:** none beyond BASE — all OPTIONAL packages are on-disk only, no services started.

### Open questions
- Exact ISO size after OPTIONAL removal — HW-REQUIRED (rebuild ISO). Estimated ~60–80 MiB reduction (intel-gpu-tools 31.5 + lvm2 5.3 + xfsprogs 4.7 + sg3_utils 3.4 + terminus-font 3.1 + ~25 small).
- Whether stress-ng should stay (mv-thermal.sh uses it) — KEEP per C1-P1 decision.

### Next action
- P1-O1: remove intel-gpu-tools (31.5 MiB).
- P1-O2: evaluate ~25 OPTIONAL/P2 packages (~60–80 MiB combined) for removal or recovery-profile move.
- Rebuild ISO and verify size + boot.

---

## AXIS P — Service parallelism

**STATUS:** PROVEN-COMPLETE
**MEASURED?:** Yes — unit DAG After=/Wants= audit for all boot-critical units
**HARDWARE_REQUIRED?:** No

### Evidence

**Method:** `systemd show <unit> -p After -p Wants -p Requires -p Before` for all boot-critical units on host + airootfs .wants audit.

**Boot-critical unit DAG (installed system after firstboot):**

| Unit | After | Wants | Parallel? |
|---|---|---|---|
| tlp.service | (none) | (none) | yes — multi-user.target |
| systemd-zram-setup@zram0.service | (none) | (none) | yes |
| NetworkManager.service | network-pre.target, sysinit.target, basic.target, dbus.socket | network.target, tmp.mount | yes |
| systemd-resolved.service | sysctl, sysusers, journald.socket | nss-lookup.target | yes |
| lightdm.service | sysinit.target, basic.target, getty@tty1.service | — | mostly (see below) |
| bluetooth.service | remount-fs, tmpfiles, sysinit.target, basic.target | tmp.mount | yes |
| plocate-updatedb.timer | time-sync.target, sysinit.target | — | timer |
| fstrim.timer | time-sync.target, sysinit.target | — | timer |

**Key findings:**
1. **tlp, zram, NetworkManager, resolved, bluetooth all start in parallel** at multi-user.target — no artificial serialization between them. Correct.
2. **lightdm After=getty@tty1.service** — minor (~1 s) serialization: lightdm waits for getty (which has autologin root for emergency shell). This is standard Arch behavior and the getty is up in <1 s. Not worth changing.
3. **plocate-updatedb.timer + fstrim.timer After=time-sync.target** — both wait for timesyncd to sync time. If the RTC is dead or time sync is slow (no network), these timers are delayed. Low impact: they are daily/weekly timers, not boot-critical. On a MacBook with a dead battery, time sync could take a few seconds — acceptable.
4. **networkd-wait-online** with `wait-for-only-one-interface.conf` — waits for only ONE interface (not all). Good — no unnecessary wait for all interfaces.
5. **mv-* user timers** (mv-calendar, mv-reminders, mv-timemachine) — no deps, fire on their own schedules. Correct.
6. **ISO-only units** (choose-mirror, pacman-init, reflector, sshd, VM agents) — one-shot or disabled on install. No serialization concern.

**Late-startable candidates:**
- sshd could be socket-activated (ISO-only, minor — and see axis J: should be disabled anyway).
- bluetooth could be D-Bus activated, but needs rfkill events. KEEP as-is.
- reflector is already one-shot. KEEP.

**Artificial serialization:** None found. The critical path is the inherent systemd → DM → Xsession → panel chain (C1 axis A confirmed). The unit DAG is already parallel where it matters.

### Open questions
- None — the DAG is fully audited and confirmed parallel.

### Next action
- None. Axis P is closed.

---

## AXIS Q — Logging/journal

**STATUS:** PROVEN-COMPLETE
**MEASURED?:** Yes — timer one-shot output measured (bytes/lines); journald config audited
**HARDWARE_REQUIRED?:** No

### Evidence

**Timer one-shot journal output (measured):**

| Timer | Output when idle | Frequency | Journal volume |
|---|---|---|---|
| mv-calendar --check-upcoming | 0 bytes (silent) | 5 min | 0 |
| mv-reminders --check-due | 0 bytes (silent) | hourly | 0 |
| mv-timemachine --check-due | 64 bytes ("no target configured — skipping") | hourly | ~64 B/h = 1.5 KB/day = 550 KB/year |
| plocate-updatedb | 1 line (daily) | daily | negligible |
| fstrim | 1 line (weekly) | weekly | negligible |
| genmon/mv-hud | not journaled (genmon captures stdout) | 5 s | 0 |

**Key findings:**
1. **mv-timemachine is the only recurring journal noise** — 64 B/hour ("no target configured — skipping") until the user configures a backup target. This is a useful one-time signal, not a bug. After configuration, it goes silent. 550 KB/year is negligible. No action needed (silencing it with `StandardOutput=null` would hide real errors too).
2. **mv-calendar and mv-reminders are completely silent** when idle — correct (they only notify when there is something to report).
3. **journald config is reasonable** — volatile storage (ISO) + `RuntimeMaxUse=50M` + `SystemMaxUse=100M` + `ForwardToSyslog=no`. On the installed system, firstboot removes the volatile override (persistent journal, 100 MB cap). Correct.
4. **No StandardOutput overrides** in our units (default: journal). Correct — no stdout noise.
5. **Host journal is 496 MB** — but that is the WSL2 dev box (general use), not our system. Our config caps at 100 MB persistent / 50 MB volatile.

**Verbosity trims keeping usefulness:** None needed — the journal volume is already negligible. The only trim candidate is mv-timemachine's 64 B/h "not configured" line, but it is a useful signal. No action.

### Open questions
- None — journal volume is fully characterized and negligible.

### Next action
- None. Axis Q is closed.

---

## AXIS R — Observability itself

**STATUS:** PARTIALLY (distortion quantified and now tracked; no harness fix needed)
**MEASURED?:** Yes — subprocess floor, cold-vs-warm, host-drift measured; S23+S24 scenarios added
**HARDWARE_REQUIRED?:** No

### Evidence

**Method:** direct measurement of bench.py's own distortion sources + new S23/S24 scenarios added to the harness.

**Subprocess spawn floor (measured):**
- `/bin/true`: median 1.60 ms (min 1.49, max 41.15 — WSL2 noise outlier)
- `python -c pass`: median 25.98 ms — the Python interpreter floor, included in every Python measurement. Appropriate for app startup (real apps pay it), but means one-shot measurements include 26 ms of interpreter.

**Cold vs warm (S02, gi+Gtk import, 10 runs):**
- run1 = 311.9 ms (cold), run2+ = 278 ms, median(all 10) = 271.0 ms.
- Cold penalty ~35 ms on the first run. With repeats=10, the median is barely affected (~0.3%). S02 is robust.

**S03 distortion (repeats=1, always cold):**
- mv-settings: run1 = 282.7 ms (cold) vs median = 273.0 ms → +3.6% inflation.
- S03 reports the cold value every time → ~4–13% inflation vs warm. Quantified.

**S23 — host drift within a batch (NEW, measured):**
- 6 consecutive gi+Gtk imports: [283.9, 281.4, 287.3, 343.0, 348.3, 353.6] ms.
- Runs 1–3: ~285 ms. Runs 4–6: ~348 ms. **Host drift = +22% within a single batch.**
- first_run = 283.9, warm_median = 343.0, distortion = −17.2% (first run FASTER than warm median — the host got slower during the batch).
- This is the dominant distortion on this host: ±20% host drift > cold-cache effect. Single measurements (repeats=1) carry ±20% noise.

**S24 — UI resource load (NEW, measured):**
- css_parse 4.5 ms, appinfo_getall 14.23 ms, icon_lookup 0.013 ms, font_families 0.01 ms. (See axis L.)

**Max outlier:** /bin/true max = 41 ms (WSL2 noise) — the median is robust to this. Good design.

**Fix or document?** Document + track. The harness's median-of-N is robust for repeats≥3. The repeats=1 scenarios (S03, S24) carry ±20% host noise — this is now quantified and tracked by S23 on every run. No harness fix needed (the distortion is a host property, not a harness bug). True cold-cache measurement needs root (`/proc/sys/vm/drop_caches`) — NOT-MEASURABLE as user; the session-level proxy (S23) is the honest alternative.

### Open questions
- None — distortion is fully characterized and now tracked by S23/S24.

### Next action
- None. Axis R is closed. S23/S24 are now in the suite for regression tracking.

---

## AXIS S — Failure/recovery engineering

**STATUS:** DESIGN (per-failure-class rollback paths designed; no implementation in this track)
**MEASURED?:** No (design track) — existing recovery infrastructure inventoried
**HARDWARE_REQUIRED?:** Yes — actual rollback validation on target

### Evidence

**Existing recovery infrastructure (inventoried):**
- **lab/ control plane** (committed 760b443): A/B slot state machine UNKNOWN→BOOTING→NETWORK_READY→AGENT_READY→HEALTH_CHECK→HEALTHY→COMMITTED; FAIL→rollback. NDJSON over SSH, ed25519 machine identity, deploy/verify/select-boot/commit/rollback. This IS the remote bring-up mechanism.
- **mv-timemachine**: btrfs subvolume snapshots (read-only CoW of @ / @home under @snapshots) + restic (off-device encrypted dedup). btrfs-progs + restic in ISO.
- **systemd-boot entries**: mavericks-linux-zen.conf + mavericks-linux-zen-fallback.conf (fallback for boot failure).
- **mv-experiment.sh**: apply|revert|status for E1–E12 experiments — each has a revert path.
- **git**: all configs versioned; rollback = `git checkout -- <path>` + re-run firstboot.

**Per-failure-class rollback design:**

| # | Failure class | Detection | Rollback path | Automation |
|---|---|---|---|---|
| 1 | BOOT FAILURE (kernel/cmdline regression) | system won't boot / panics | systemd-boot menu → select fallback entry (mavericks-linux-zen-fallback.conf) | manual (boot menu) |
| 2 | DESKTOP SESSION FAILURE (Xfce/panel broken) | black screen / panel crash | log out/in (new session); btrfs snapshot of @home before firstboot changes | manual + snapshot |
| 3 | PACKAGE/PACMAN FAILURE (bad update) | boot loops / missing libs | pacman cache (`/var/cache/pacman/pkg/`) + btrfs snapshot before update; rollback = `pacman -U <cached>` + snapshot restore | semi-auto (snapshot hook) |
| 4 | CONFIG REGRESSION (our configs) | settings broken / theme broken | `git -C /root/macbook12-macos-linux checkout -- <path>` + re-run firstboot | manual (git) |
| 5 | FULL SYSTEM CORRUPTION | unbootable / data loss | btrfs snapshot rollback (mv-timemachine btrfs layer) or restic restore (off-device); reinstall from ISO (2.87 GB known-good) | manual |
| 6 | REMOTE BRING-UP FAILURE (lab) | health check fails | lab controller: deploy to inactive slot → verify → select-boot → commit; FAIL → select-boot previous slot | auto (lab state machine) |
| 7 | EXPERIMENT REGRESSION (E1–E12) | perf/thermal regression | `mv-experiment.sh <E> revert` — each experiment has a revert path | semi-auto |

**Integration with future remote bring-up:** the lab control plane (class 6) is the remote bring-up mechanism. The per-failure-class rollback paths map to: boot entry selection (class 1), session restart (class 2), pacman cache + snapshot (class 3), git checkout (class 4), btrfs/restic (class 5), lab A/B slots (class 6), mv-experiment revert (class 7). The design is complete; implementation of the snapshot-before-change hooks (class 2, 3) and the lab-driven bring-up (class 6) is future work.

### Open questions
- Whether to automate snapshot-before-change (pacman hook + firstboot hook) — design decision for implementation track.
- Whether the lab control plane should drive the full bring-up or just A/B validation — scope decision.

### Next action
- Implementation track: add btrfs snapshot-before-change hooks (pacman + firstboot).
- Implementation track: wire lab control plane into the bring-up runbook.
- HW: validate each rollback path on target.

---

## Suite counts

- Bench scenarios before C2: 28 (S01–S22, S14E, G01–G05)
- Bench scenarios added in C2: 2 (S23-cold-warm-distortion, S24-ui-resource-load)
- Bench scenarios after C2: 30
- Full suite run: 30 scenarios, 25 ok, 5 skipped (GUI-tier), 0 failed
  (docs/benchmarks/results-2026-09-29-c2.json)
- Test scripts: 22 test-*.py — gate GREEN (20 pass clean; mv-photos + mv-textedit
  fail with the SAME 2 host artifacts documented in C1: gthumb installed on
  host for measurement, graceful-no-backend path not taken. NOT regressions.)
- New measurements: 6 mv-hud flag variants, 12 typelib imports, 4 UI-resource
  costs, 2 desktop-parse costs, 6-run cold/warm/drift batch, 3 timer one-shot
  outputs, 129-package classification, 8 unit DAG audits

## Honesty contract

- All host numbers are WSL2/5800HS-relative deltas, NOT MacBook predictions.
- GUI-tier measurements (window render, compositor, real browser, real playback)
  are HW-REQUIRED/QEMU.
- uBO filter-list sizes are ESTIMATES from uBO list characteristics, NOT
  measured offline (no Firefox, no network).
- Firefox startup cost is HW-REQUIRED (no Firefox on host).
- The S23 distortion (−17.2%) is a host-drift measurement, not a cold-cache
  measurement; true cold needs root (drop_caches), NOT-MEASURABLE as user.
- The 2 failing tests are pre-existing host artifacts (gthumb installed),
  NOT regressions from this run.
