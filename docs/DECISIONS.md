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

## 2026-09-26 — Orchestration architecture: Orchestrator/Builder/Scout/Planner

**Problem:** the primary agent combined orchestrator+builder roles: it analyzed,
implemented, tested and committed in one body, burning its generation budget on
implementation and stopping after each cycle while the project was far from done.

**Decision:** four roles in `.opencode/agents/` (project-level, travel with repo):
`orchestrator.md` (mode primary, edit/write DENY, bash DENY except
`git status/log/diff`, task ONLY builder/scout/planner),
`builder.md` (mode all, full permissions),
`scout.md` (mode all, read-only override),
`planner.md` (mode all, read-only).
AGENTS.md section 14 is binding; section 0 points to it.

**Inspection findings that shaped this:**
- Built-in `scout` was documented as read-only but actually had full
  edit/write/bash tools in this install (verified via `debug agent scout`) —
  overridden to read-only by `scout.md`.
- Custom agents work via `.opencode/agents/*.md` frontmatter
  (`mode`/`permission`/`model`); verified with `agent list` + `debug agent`.
- Permission system cannot deny `read`; orchestrator keeps read/search/skill —
  intended (state inspection is its job). `question` stays denied for
  orchestrator (autonomous doctrine: instruct, don't ask).
- `mode: all` on builder/scout/planner preserves manual Tab/@ sessions.
- `project-meta.json` already referenced a nonexistent `"agent": "orchestrator"` —
  now valid.
- Residual: task-tool `task` permission is name-glob based; users can still
  @-invoke any subagent manually regardless of orchestrator's task allow-list
  (by design, manual override preserved).

## 2026-09-26 — Orchestration architecture: Orchestrator/Builder/Scout/Planner

**Problem:** the primary agent combined orchestrator+builder roles: it analyzed,
implemented, tested and committed in one body, burning its generation budget on
implementation and stopping after each cycle while the project was far from done.

**Decision:** four roles in `.opencode/agents/` (project-level, travel with repo):
`orchestrator.md` (mode primary, edit/write DENY, bash DENY except
`git status/log/diff`, task ONLY builder/scout/planner),
`builder.md` (mode all, full permissions),
`scout.md` (mode all, read-only override),
`planner.md` (mode all, read-only).
AGENTS.md section 14 is binding; section 0 points to it.

**Inspection findings that shaped this:**
- Built-in `scout` was documented as read-only but actually had full
  edit/write/bash tools in this install (verified via `debug agent scout`) —
  overridden to read-only by `scout.md`.
- Custom agents work via `.opencode/agents/*.md` frontmatter
  (`mode`/`permission`/`model`); verified with `agent list` + `debug agent`.
- Permission system cannot deny `read`; orchestrator keeps read/search/skill —
  intended (state inspection is its job). `question` stays denied for
  orchestrator (autonomous doctrine: instruct, don't ask).
- `mode: all` on builder/scout/planner preserves manual Tab/@ sessions.
- `project-meta.json` already referenced a nonexistent `"agent": "orchestrator"` —
  now valid.
- Residual: task-tool `task` permission is name-glob based; users can still
  @-invoke any subagent manually regardless of orchestrator's task allow-list
  (by design, manual override preserved).
- NOTE: a parallel session's commit e7923bf swept the first version of these
  files via `git add -A`; re-applied deltas are committed separately here.

## 2026-09-26 — TEMP: nemotron-3.5-lightning-free disabled

**Symptom (user report):** 3.5-lightning stops generation mid-output for the
last ~2 days. **Action:** `opencode.jsonc` general/explore and
`.opencode/agents/planner.md` temporarily pinned to
`opencode/muse-spark-1.3-contributor-free` (already used for scout,
known-good). **Revert when:** lightning generates cleanly again for a few
days — flip the three pins back, no other changes needed.

## 2026-09-26 — Session reuse: real mechanisms only (no invented API)

**Verified live on installed 1.18.32 (server + SDK types + docs):**
`POST /session {parentID?,title?}` (child/sub-agent sessions),
`GET /session/status` (idle/busy/retry — NO token numbers),
`GET /session/:id/children`, `GET /session/:id/message` (per-assistant
`tokens.input` cumulative), `POST /session/:id/message|prompt_async`
(continuation), `POST /session/:id/fork|abort`, `DELETE /session/:id`,
CLI `session list|delete`, `run -s/-c/--fork`, `export`,
`Model.limit.context` (e.g. muse-spark = 1048576),
plugin `event` bus (`session.status/idle/deleted`, `message.updated`) +
`chat.message` + `experimental.session.compacting`.
**No single "context remaining %" endpoint exists** — honest signal is
last-assistant-tokens.input / model limit.context, computed live by
`scripts/session-reuse.py` (`context`/`decide`/`register`/`retire`/`delete`/
`status`/`children`/`list`). Registry `.opencode/sessions/registry.json`
stores metadata only. Policy: RESUME same role+objective while >50%
remaining; RETIRE+delete at <=50%, on objective/role change, error state,
or unverifiable context. Proven: probe parent+child create/list/delete
round-trip, RESUME/NEW verdicts incl. objective boundary.

## 2026-09-26 — Orchestrator missing from agent picker: root cause + fix

**Symptom:** new OpenCode session picker shows Build/Plan/Scout, no Orchestrator.
**NOT a frontmatter bug:** file presence != registration was checked properly —
`agent list` and server `GET /agent` with server-cwd=repo both list
`orchestrator|primary` (native:false) with correct enforced permissions
(edit:false, write:false, bash deny-all + git ro, task only
builder/scout/planner). Proven with a throwaway probe server.
**Also NOT a missing built-in:** clean-env `agent list` outside any project
shows NO scout at all in 1.18.32 — i.e. no built-in scout exists here; the
visible "Scout" already came from our custom file, so custom loading worked
where the server cwd was right.
**Root cause:** project agents resolve from the SERVER working directory, not
per session directory (probe: cwd=`~` -> built-ins only; cwd=repo -> all
customs). The desktop app attaches to a long-lived server (cwd=`~`), so
project-only agents never reach its picker. No hot-reload either (verified:
new global files invisible until server restart).
**Fix (minimal, no arch change):** global visibility shim — symlinks
`~/.config/opencode/agents/{orchestrator,builder,scout,planner}.md` ->
repo `.opencode/agents/*.md` (single source of truth in repo), plus plain
copies at `%USERPROFILE%/.config/opencode/agents/` for Windows-spawned
servers. Verified: fresh server with cwd=`~` now lists all four roles;
cold-start required. **User action still needed once:** restart
`opencode serve` / the desktop app (running servers do not re-read agents).
Machine-verified; actual desktop-picker pixels not observable from WSL.

## 2026-09-26 — Picker reduced to 2 roles: Build + Orchestrator

**User decision:** five entries (Build/Builder/Orchestrator/Plan/Planner/Scout)
confused the picker. Target: full **Build** (stock built-in, untouched) +
restricted **Orchestrator** (Task -> build only). Custom builder/scout/planner
deleted (repo + global symlinks + Windows copies); built-in plan/explore/general
disabled via `opencode.jsonc` (`disable: true`); orchestrator.md rewired
(`task: allow` only `build`; research/decomposition/implementation are just
different Task shapes for the same worker). Session lifecycle unchanged,
role name in registry is now always `build`. AGENTS.md section 14 rewritten
for the 2-role model.

**Global mirror (required for picker):** project-level `disable` only applies
when server cwd = repo, and project agents resolve from server cwd too —
so the same disables were mirrored to global
`~/.config/opencode/opencode.jsonc` (+ Windows-side copy) and the role file
to global `agents/` (symlink WSL-side, copy Windows-side). Verified cold:
fresh server with cwd=`~` lists only build/orchestrator (+hidden system
compaction/summary/title). Running servers need restart (no hot-reload).

---

## 2026-09-26 — Finder UCA: Empty Trash action + global keyboard shortcuts

**Problem:** Finder UCA had Get Info, Open With, Rename, Eject, New Folder, Put Back,
Quick Look, Compress, Terminal but no "Empty Trash" action. No global keyboard
shortcuts for Finder operations (New Folder, Get Info, Open With).

**Decision:** 
1. Added "Empty Trash" UCA action using `trash-empty` (from trash-cli, already
   in ISO) with `user-trash-full` icon, available in all contexts.
2. Added global keyboard shortcuts via xfce4-keyboard-shortcuts.xml:
   - Super+N → New Folder on Desktop (`mv-newfolder $HOME/Desktop`)
   - Super+Shift+N → New Folder in Home (`mv-newfolder $HOME`)
   - Super+I → Get Info (`mv-getinfo $HOME`)
   - Super+O → Open With (`mv-openwith $HOME`)
   These are global (not Thunar-specific) because Thunar UCA doesn't support
   keyboard accelerators; global shortcuts provide discoverable Finder-like
   keybindings. The `$HOME` fallback paths work when Thunar isn't focused.
3. Enhanced thunarrc with Finder-like defaults: ShowToolbar, ShowStatusbar,
   ShowLocationSelector, TreePaneWidth=200, window geometry, case-insensitive
   sort, MiscShowAboutTimestamps=FALSE.

**Reasoning:** 
- Empty Trash completes the Trash workflow (Put Back + Empty Trash = full cycle).
- Global shortcuts are the only feasible way to provide keyboard access to
  custom actions in Thunar (UCA has no accelerator support). Using `$HOME` as
  fallback path is a pragmatic compromise — when Thunar is focused, user can
  use context menu; global shortcuts provide quick access from anywhere.
- thunarrc enhancements make the default Thunar behavior closer to Finder
  (toolbar, statusbar, location selector always visible).

**Alternatives considered:**
- Thunar plugin for Space key / accelerators — rejected (adds dependency,
  maintenance burden, not in Arch repos).
- Per-application shortcuts via xfce4-keyboard-shortcuts.xml with
  `xfce4-terminal -e` wrappers — rejected (complexity, fragile).

**Implementation:** thunar-uca.xml, xfce4-keyboard-shortcuts.xml, thunarrc.
All XML validated (xmllint), sync check passed, packages rebuilt.

---

## 2026-09-26 — Spotlight gap fixes: file actions, system actions, error/empty states, visual polish

**Problem:** Spotlight (mv-spotlight + rofi) had core search working (apps, files via plocate, calculator, recent items) but missing: file open action from results, system actions (Settings, Control Center, etc.), user-visible error handling when plocate missing/index empty, empty state feedback, and the rofi theme was visually basic.

**Decision:**
1. **File open action:** File results now include `action\x1fxdg-open '{path}'` so Enter opens the file.
2. **System actions:** Added 5 system actions (System Settings, Control Center, Activity Monitor, Disk Utility, Terminal) that match on query substring against name/description. Appear under "System" category.
3. **Error handling:** `search_files()` now returns `(files, error_msg)` tuple. If plocate missing, timeout, or other error, shows user-visible result with warning icon: "plocate not installed — file search unavailable. Install 'plocate' package and run 'sudo updatedb'." Only shown when no other results exist.
4. **Empty states:** 
   - Empty query with no recent items: "No recent items" with dialog-information icon.
   - Query with zero matches across all sources: "No results for 'query'" with dialog-information icon.
5. **Visual polish (rofi-mavericks.rasi):** Mavericks-style skeuomorphic accents: softer palette (rgba backgrounds), rounded corners (10px window, 6px elements), better spacing (16px window padding, 10px element padding), larger icons (28px), custom scrollbar, category styling with subtle background, accent blue (#007aff) for selection.
6. **Performance guardrails:** plocate subprocess timeout kept at 3s (existing). All searches on-demand (no daemon).

**Reasoning:**
- File open action is essential for Spotlight parity — results must be actionable.
- System actions provide cheap high-value entries (no new deps, on-demand).
- Error/empty states critical for first-run UX (plocate index builds daily via timer, so initial boot has empty index).
- Visual polish aligns with Mavericks coherence goal (section 6, 13.3).
- No new dependencies, no daemons, on-demand only — fits power budget.

**Alternatives considered:**
- Preview pane in rofi — rejected (rofi script mode doesn't support rich preview; would need custom GUI, Electron, or daemon — all violate power budget).
- Always show plocate status — rejected (noisy; only show when relevant i.e. no other results).

**Implementation:** mv-spotlight (Python), rofi-mavericks.rasi.
Validations: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED.

---

## 2026-09-26 — Launchpad gap fixes: desktop entry, folder navigation, empty states, icon validation, visual polish

**Problem:** Launchpad (mv-launchpad + rofi) had pagination, folders, search, and custom positions working, but missing: mv-launchpad.desktop for app menu integration, default folders on first run, folder open/back navigation, empty state handling (no apps, no search results, empty folder), robust .desktop parsing with icon validation, and visual polish of the grid theme.

**Decision:**
1. **Desktop entry:** Added `mv-launchpad.desktop` with `X-Mavericks-Native=true` for app menu/Dock integration. Exec uses `sh -c` wrapper to handle single quotes in rofi modi argument.
2. **Default folders (auto-population):** On first run, `folders.json` is created with "Utilities" and "Other" folders. Apps are auto-categorized by keyword matching (e.g., "calculator", "terminal", "disk", "settings" → Utilities).
3. **Folder navigation:** New `open_folder` parameter allows showing folder contents with a "← Back" item to return to main grid. Implemented via rofi script mode argument passing.
4. **Empty states:** Three empty states handled with user-visible feedback:
   - No .desktop files found: "No applications found" with dialog-information icon.
   - Search with zero matches: "No results for 'query'" with suggestion.
   - Empty folder: "Folder 'X' is empty" with instruction to edit folders.json.
5. **Robust .desktop parsing:** 
   - Duplicate handling: user `~/.local/share/applications` overrides system dirs (seen_ids set).
   - Icon validation: `_icon_exists()` checks Gtk.IconTheme before using icon; falls back to `application-x-executable`.
   - Malformed .desktop files silently skipped (try/except per file).
6. **Visual polish (rofi-launchpad.rasi):** Mavericks-style skeuomorphic grid: rgba backgrounds, 18px border-radius, subtle borders, box-shadow on selection, custom scrollbar, transitions (120ms), element states (normal/selected/urgent), larger search bar (360px), increased spacing (18px).

**Reasoning:**
- Desktop entry completes the integration — Launchpad now appears in app menus and can be pinned to Dock.
- Auto-populated folders provide immediate value on first run without manual config.
- Folder navigation via "Back" button is the only feasible approach in rofi script mode (no persistent state between invocations).
- Empty states critical for first-run UX and edge cases.
- Icon validation prevents broken icon placeholders in the grid.
- Visual polish aligns with Mavericks coherence goal and matches Spotlight theme evolution.
- No new dependencies, no daemons, on-demand only — fits power budget.

**Alternatives considered:**
- Jiggle/edit mode (drag-to-rearrange) — rejected: rofi script mode has no drag-and-drop support; would require a persistent GUI daemon (Electron/Python/GTK) violating power budget and reuse-first. Documented as accepted delta.
- App Store integration — rejected: no Linux equivalent; Mac App Store is proprietary.
- Nested folders — rejected: rofi script mode doesn't support hierarchical navigation cleanly; single-level folders match Mavericks Launchpad behavior.

**Implementation:** mv-launchpad (Python), rofi-launchpad.rasi, mv-launchpad.desktop.
Validations: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED.

---

## 2026-09-26 — Control Center gap fixes: Wi-Fi connect, BT devices, audio output switching, error states

**Problem:** Control Center (mv-control) had basic toggles and sliders but missing actionable controls: Wi-Fi network connect/disconnect, Bluetooth device list with pair/connect, audio output device switching, brightness unavailable state, battery power mode reading, and error/empty states for missing backends.

**Decision:**
1. **Wi-Fi connect/disconnect:** Click network row → password dialog for secured networks → nmcli connect. Active network shows disconnect on click. Empty state when NetworkManager unavailable.
2. **Bluetooth devices:** Full BlueZ D-Bus enumeration (org.bluez.Device1) showing name, icon, connected/paired status. Buttons for Connect/Disconnect/Pair per device. "Open Bluetooth Settings" button launches blueman-manager. No pairing daemon required.
3. **Audio output switching:** Combo box selection now calls `pactl set-default-sink`. Sink list refreshed on open, default marked.
4. **Brightness robustness:** When no backlight path found (`/sys/class/backlight` empty), slider disabled and info row shown: "Brightness control not available on this hardware".
5. **Battery power mode:** Reads current TLP governor state (balanced/powersave/performance). Changing mode shows info dialog with `sudo tlp set-mode` command (requires root, not automated).
6. **Error/empty states:** Each section shows user-friendly message when backend unavailable (NetworkManager, BlueZ, PulseAudio, backlight, UPower, xfce4-notifyd).
7. **No new dependencies:** Uses existing NM, BlueZ, pactl, upower, tlp, xfconf. On-demand only, no daemons.

**Reasoning:**
- Wi-Fi connect is essential for Control Center parity — list without connect is incomplete.
- BlueZ D-Bus enumeration is lightweight and doesn't require blueman/daemon running.
- Audio switching via pactl is standard and instant.
- Brightness unavailable state is honest UX rather than silent failure.
- TLP mode reading is read-only; changing requires root — info dialog avoids polkit complexity.
- Error states critical for first-run UX on hardware where services may not be running.
- All changes maintain on-demand, event-driven architecture (5s refresh only while window open).

**Alternatives considered:**
- Full NM connection editor clone — rejected (redundant, nm-connection-editor already in System Settings).
- blueman-applet integration — rejected (adds daemon, not needed for basic device list).
- Automated TLP mode switching via polkit — rejected (adds complexity, security surface; info dialog is sufficient pre-hardware).
- Night Shift via redshift — rejected (not in ISO by default; placeholder with info message).

**Implementation:** mv-control (Python).
Validations: py_compile, check-sync ALL PASSED, headless import test passed, fallback paths verified.

---

## 2026-09-26 — Notification Center: history viewer + logging wrapper (no daemon)

**Problem:** Notification Center was PARTIALLY IMPLEMENTED with only the banner UI (xfce4-notifyd Mavericks theme + DND toggle). Missing: history UI, grouping, action buttons, keyboard shortcut.

**Decision:**
1. **mv-notify-send** — notify-send wrapper that logs every notification to `~/.local/share/mavericks/notifications.json` (max 500 entries, FIFO). No persistent daemon; logging is synchronous and fast.
2. **mv-notification-center** — GTK3 history viewer with: app-grouped list (newest first), per-app "Clear" + global "Clear All", DND toggle in header bar (syncs with xfce4-notifyd via xfconf), relative timestamps, urgency colors, keyboard navigation (arrows, Escape), focus-out auto-close.
3. **Keyboard shortcut:** Super+Shift+V → mv-notification-center (added to xfce4-keyboard-shortcuts.xml).
4. **Desktop entry:** mv-notification-center.desktop for app menu/Dock integration.
5. **No action buttons on banners** — xfce4-notifyd does not support action buttons without a persistent daemon; this is an accepted limitation. The history viewer provides the actionable surface instead.
6. **On-demand only** — both scripts exit immediately after use; zero idle cost. History log persists across sessions.

**Reasoning:**
- xfce4-notifyd is the single notification daemon (dunst removed per Phase 0.6 decision). It provides banners but no history.
- A wrapper logging to JSON is the lightest way to add history without a second daemon or D-Bus monitor.
- The history viewer is a proper Mavericks-style UI (app grouping, clear actions, DND toggle) rather than a raw log dump.
- Super+Shift+V mirrors macOS gesture-to-keyboard mapping (V = View).
- Action buttons on banners would require either: (a) patching xfce4-notifyd, (b) a second daemon, or (c) a custom notification server — all violate power budget or reuse-first. Documented as accepted delta.

**Alternatives considered:**
- D-Bus monitor daemon (e.g., `gdbus monitor`) — rejected: persistent process, adds complexity, fragile.
- Patching xfce4-notifyd to write history — rejected: upstream divergence, maintenance burden.
- rofi-based history viewer — rejected: rofi script mode doesn't support rich list with headers/actions cleanly; GTK3 gives better Mavericks visual integration.

**Implementation:** mv-notify-send (Python), mv-notification-center (Python/GTK3), xfce4-keyboard-shortcuts.xml, mv-notification-center.desktop, Makefile.
**Validations:** py_compile, xmllint, desktop-file-validate, check-sync ALL PASSED.

---

## 2026-09-26 — Quick Look Space binding investigation + enhancements

**Problem:** Quick Look (mv-quicklook) was single-file only with no Space key integration in Thunar. Thunar UCA does not support keyboard accelerators; no native Space hook exists.

**Investigation:**
1. Thunar UCA XML schema has no `<accelerator>` or `<keybinding>` element — verified via Thunar 4.20 source and docs.
2. Thunar plugin API (thunarx-3) supports menu providers, property pages, renamers — but adding a global key handler requires a C plugin loaded by Thunar, adding build complexity and maintenance burden.
3. xfce4-keyboard-shortcuts.xml supports only global shortcuts, not app-specific ones.
4. xdotool-based clipboard grab (Ctrl+C → parse file:// URIs) is the only feasible pre-hardware approach for a global hotkey that works when Thunar is focused.

**Decision:**
1. Enhanced mv-quicklook with multi-file navigation (Left/Right/Space), fullscreen toggle (F), counter display, toolbar buttons, and proper keyboard handling (Escape, Enter, arrows).
2. Created mv-quicklook-thunar as a global hotkey handler (Super+Shift+Space) using xdotool clipboard grab.
3. Accepted limitations: ~150ms latency for clipboard sync; requires xdotool dependency; only works when Thunar is active window; no native Space key in Thunar context menu.
4. Native Thunar plugin for Space key deferred — would require C development, thunarx-3 API, and hardware testing for validation. Not feasible pre-hardware.

**Alternatives considered:**
- Thunar C plugin for Space key — rejected (adds compiled dependency, maintenance burden, no Arch package).
- rofi-based file preview — rejected (rofi script mode doesn't support rich preview; would need custom GUI).
- Patch Thunar upstream — rejected (not our fork, long review cycle).

**Implementation:** mv-quicklook (enhanced), mv-quicklook-thunar (new), mv-quicklook-thunar.desktop, xfce4-keyboard-shortcuts.xml, Makefile.
**Validations:** py_compile, xmllint, desktop-file-validate, check-sync ALL PASSED.

---

## 2026-09-26 — Orchestrator model fallback (single pinned model = single point of failure)

**Symptom (user report + live repro in-session):** `nemotron-3-ultra` exhausted
its quota; Orchestrator `Task → build` was cancelled and the loop stopped —
while `muse-spark-3.5-lightning` / LongCat answered the same ping.

**Root cause (verified, not assumed):**
1. `.opencode/agents/orchestrator.md` frontmatter AND `opencode.jsonc`
   `agent.build.model` BOTH pinned `opencode/nemotron-3-ultra-free`. Per OpenCode
   model rules a pinned build model never inherits the invoker's model — one
   dead model kills orchestrator + build together.
2. No fallback procedure existed anywhere: `git log -S fallback/quota/rate`
   over `.opencode/` shows only unrelated hits; `bda113c`/`d7764c3` rewired
   roles (builder/scout/planner → build) but never added fallback. So there was
   nothing to "restore" — the canonical mechanism was created, not resurrected.

**Fix (minimal, no parallel system):**
1. `.opencode/model-fallback.json` (NEW, single source of user-ordered chain):
   OpenRouter North Mini Code (`openrouter/cohere/north-mini-code:free`)
   → OpenRouter Free Router (`openrouter/openrouter/free`)
   → Zen LongCat 2.5 Preview (`opencode/longcat-2.5-preview-free`)
   → Zen Nemotron 3 Ultra (`opencode/nemotron-3-ultra-free`)
   → Zen Nemotron 3.5 Lightning (`opencode/nemotron-3.5-lightning-free`,
   last resort). Entries use substring `match` so renames still resolve live.
2. `scripts/session-reuse.py`: `models --exclude ...` (chain order matched live
   vs `GET /provider`, then config pins, registry last-good, rest of live;
   offline-degrades to chain+config+registry) and `classify-error`
   (QUOTA=10 / CONTEXT=12 → fallback; ORDINARY=20 / UNKNOWN=30 → no auto-fallback).
   Existing reuse/retire commands untouched.
3. `.opencode/agents/orchestrator.md`: MODEL FALLBACK section (classify →
   resolve → ping-probe → RESUME-or-NEW with carried context → loop; blocker
   ONLY on `next-available: NONE` or ORDINARY error). Bare "Task cancelled"
   = UNKNOWN: re-ping current + ping candidate, switch only on split result.
4. `opencode.jsonc`: `agent.build.model` pin REMOVED — build inherits the
   orchestrator's live model, so one `/models` switch unblocks the whole loop.
   NEVER re-pin build to a single model. AGENTS.md 14.3 points at the fallback.

**Verification:** `py_compile` OK; classifier matrix (5 quota → 10, context →
12, 4 ordinary + bare-cancel → 20/30) all correct; `models --exclude
...ultra-free` offline prints user chain order with ultra skipped and
`next-available: openrouter/cohere/north-mini-code:free`. Live proof: this very
objective started as a Task on ultra (cancelled) and continued here on
muse-spark with full task context — an actual cross-model continuation.

**Caveats:** LongCat Zen id NOT verified live (no auth from build env) —
substring resolution + `opencode models` check pending; lightning stays last
resort per the 2026-09-26 TEMP instability note; OpenRouter entries need a
connected provider (else skipped live); after agent-file changes restart
`opencode serve` / desktop app (no hot-reload).
