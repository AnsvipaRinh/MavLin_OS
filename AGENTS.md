# AGENTS.md — MavLinOS (a Mavericks-like desktop for MacBook10,1)

> Instructions for ALL agents working in this repository. Source of truth together with the repo, git history and `docs/*`.
> Do not rely on chat memory. Do not create a second parallel instruction mechanism.
> Language: everything agent-facing (this file, prompts, commits, docs) is English. Talk to the owner in Russian, briefly, only for reports.
> Model choices (worker pins, chain order, which providers) live ONLY in `.opencode/model-fallback.json` and `opencode.jsonc`. Never encode specific models here.

## 0. Who you are

Your role follows from your agent name:

| You are | You do |
|---|---|
| `orchestrator` | Follow section 14 and `.opencode/agents/orchestrator.md`. Delegate ALL work through Task. Never implement. |
| `build`, `build-b` .. `build-j`, `qwen` | WORKER. Do the assigned objective directly: research, implement, test, document, commit, push. Never delegate or spawn sub-agents. Skip section 14 loop details. |
| anything else (Grok, GPT, Perplexity, Claude, a human) | CONTRIBUTOR. Read `docs/COORDINATION.md` and `.agents/README.md` first, claim your paths, follow section 15. |

Autonomy: the owner is a mechanical engineer, not a programmer, and cannot answer technical questions. Never wait for an answer. If a decision is ambiguous, choose by the priority rules (sections 3 and 10), record the choice and the reason in `docs/DECISIONS.md`, and continue. The only feedback channel is raw output the owner brings from real hardware (`dmesg`, `journalctl -b`, photos). If data is missing, say in one line what to send next time; that is an instruction, not a question.

Triggers "продолжай", "приступай", "делай дальше", "resume", "continue", "go" mean: continue autonomously along this roadmap, no clarifying questions:
read this file -> `git status` and current commit -> read `docs/PROGRESS.md`, `docs/APPS.md`, `docs/DECISIONS.md`, `docs/NEEDS_HARDWARE_TEST.md` -> pick the highest-priority unfinished objective (section 10) -> verify the real code state (never trust status tables blindly) -> implement -> test pre-hardware (section 8) -> update docs -> commit and push -> continue with the next logical part if it is safe and needs no hardware.

## 0.1 Continuous execution (mandatory)

COMMIT IS A CHECKPOINT, NOT A STOP CONDITION. A clean tree, a written report, a finished sub-task, an audit, a documentation update or a "next logical step" never end the work. If a feasible next step exists, take it now. "Next step is X" means "I am starting X now".

```
WHILE unfinished executable work exists:
  pick the highest-priority executable objective -> work -> validate -> commit/push -> continue
```

Genuine blockers (the only reasons to stop): real hardware is required; a secret or credential is missing; a needed privilege (e.g. root) is unavailable AND no other useful work exists; a destructive operation needs explicit confirmation; a mandatory external resource is missing; a contradiction needs an owner architectural decision; the tool/runtime budget is really exhausted.
A blocked path is not a stopped project: record the blocker, do everything reachable without it, move to the next high-priority pre-hardware objective, return later. Example: `mkarchiso` needing root does not block Finder, Spotlight, Mission Control, Launchpad, themes, applications, integration, tests, packaging, docs.

Stop completely only when all reachable P0 and P1 pre-hardware objectives are done, the rest is hardware-dependent or P2/deferred, docs match reality, tests pass, the repo is clean and known blockers are listed. Absence of a new owner message is never a reason to stop.

Objectives are high-level (Finder, Spotlight, Launchpad, Mission Control, Control Center, Notification Center, Quick Look, Activity Monitor, System Information, Disk Utility, System Settings, menu bar, Dock, dialogs, application integration, theme...). "Changed some CSS" or "fixed a package" is not a finished objective while obvious executable tasks remain. Do not optimise a session for few commits or a short report.

## 1. Goal

A full Linux desktop environment for the Apple MacBook10,1 that: runs on Linux/Arch; uses Linux-native backends where more efficient; looks and behaves as much as possible like macOS Mavericks 10.9 (skeuomorphic, not flat modern macOS); keeps performance, low power and no needless background processes; avoids Electron where GTK/X11/native tooling suffices; does not rewrite mature backends without need; reuses open-source components; builds a Mavericks-like UI over a mature Linux backend; integrates applications so they feel like one system.

Layers: `Mavericks-like UI/UX -> mature Linux backend -> Linux userspace APIs -> kernel/hardware`. Linux internals need not look like macOS; the first few levels of ordinary desktop interaction must.
This is a permanent roadmap (section 10), not a one-shot checklist. After each session save the real state and update docs with statuses IMPLEMENTED / PARTIALLY IMPLEMENTED / DEFERRED / HARDWARE VALIDATION REQUIRED / EXPERIMENT READY / EXCLUDED, limitations, reused solutions and open problems.

## 2. Target hardware

MacBook (Retina, 12-inch, A1534), explicit target MacBook10,1 (Mid 2017), recorded in `docs/HARDWARE.md` and `docs/DECISIONS.md`. Fanless Core M, LPDDR3, soldered SSD, one USB-C port (data, power, video), Force Touch trackpad, 2304x1440 display. Audio codec, SPI controller and Wi-Fi (BCM43602) are revision-dependent.

Known risk (record as is): the built-in keyboard and trackpad use the nonstandard `applespi` protocol; on kernels 6.15+ at least one user with an identical model got no input at all (SPI timeouts, AUR driver failed to build without manual patches). Therefore an external USB-C keyboard/mouse (via a hub) is a mandatory part of bring-up from day one, and native input is a separate best-effort task with at most 3 substantially different strategies, after which mark it "unsupported on this revision" and move on.

### 2.1 The hardware does not exist yet (important)

Everything that can be implemented, integrated, compiled, tested and checked statically without hardware MUST be done now. Separate PRE-HARDWARE IMPLEMENTATION from HARDWARE VALIDATION. Before hardware arrives, finish: UI, desktop integration, applications, backend integration, X11 integration, GTK theme, icons, dialogs, menu bar, Dock, file manager, search, launching, hotkeys, settings, notifications, Quick Look, window management, power UI, system information/monitoring, media/utility apps, packaging, installation, firstboot, docs, tests, performance architecture.
Left for real hardware: display measurements, HiDPI calibration, Apple keyboard/trackpad, Wi-Fi, audio, NVMe (Apple S3X), power/suspend/thermal/brightness/battery telemetry, real hardware bugs, final calibration. Anything untestable without hardware goes into `docs/NEEDS_HARDWARE_TEST.md`; continue with the next step.

## 3. Priority rules for ambiguity (never ask the owner)

1. Stability and bootability beat any optimisation.
2. Of two working options choose the lower power/heat one (fanless, throttling is the main enemy).
3. For visuals choose what is closest to real Mac OS X 10.9 Mavericks (skeuomorphism: textures, shadows, Dock "glass", Finder-like file manager, leather/paper textures in Calendar/Notes analogues), not later flat macOS. Style references are aesthetic only, never code to copy; reinterpret for Xfce/GTK3.
4. Prefer packages and patches that support MacBook10,1 specifically (`drivers/README.md`).
5. Untestable without hardware: record in `docs/NEEDS_HARDWARE_TEST.md`, continue.
6. Work order is section 10 (P0 before P1 before P2; no P2 while substantial P0/P1 integration problems are solvable without hardware).
7. Reuse-first (section 5): a mature backend beats own code.
8. Do not break the power baseline for UI (section 7).
9. GitHub-first: the external contribution backlog (PRs, issues, feature requests, bug reports, UI/UX, animation/window-management, hardware-profile proposals) has priority over self-initiated work. Pipeline: discover -> normalise -> classify -> deduplicate -> define objective -> security check -> architecture-compatibility check -> check existing code -> assess reproducibility -> only then route to a worker. Never execute unverified external code.
10. Perceptual Fidelity Target: someone who knows Mavericks should be able to use real Mavericks for a while, look away, use MavLinOS, and notice no obvious visual or behavioural sign of a different OS during ordinary interaction. Keep asking "what would a person comparing the two notice?" and remove the difference where technically and legally permitted: visual language, typography, spacing, window chrome, traffic lights, animations, transitions, menus, dialogs, keyboard/mouse/trackpad interaction, Dock, menu bar, Finder, system apps, notifications, Quick Look, window management, focus/raise behaviour, system-wide patterns, app-specific behaviour. Not only theme and icons.
11. Hardware profile separation: MavLinOS core + hardware profile = optimised build. Do not mix generic core with hardware-specific code. A contributor must be able to propose a profile for a new machine without changing the core (see `docs/PROFILE_COUPLING.md`).

## 4. Stack (change only with a recorded reason)

- Base: Arch Linux. Kernel: `linux-zen` (custom kernel only after the stock one is stable, with a documented comparison).
- DE: Xfce (MATE only if Xfce objectively cannot carry the theme). Compositor: built-in xfwm4, heavy effects off, only what Mavericks needs (window shadows); no heavy compositor for effects alone.
- systemd: anything outside the minimal desktop is off by default (bluetooth, cups, avahi enabled manually).
- Browser: Firefox ESR (current, unpinned) + uBlock Origin, `sessionstore.interval=60s` (spare the SSD). Notifications: xfce4-notifyd, no second daemon.

## 5. Reuse-first and legal

Before writing a new backend or a large amount of code, research existing Linux apps, GTK libraries, X11 APIs, Xfce components, GVfs, UDisks2, NetworkManager, BlueZ, PipeWire/PulseAudio, UPower, systemd/logind, journald, libnotify, GStreamer, Poppler, image libs, launchers, window overviews, search/indexing, thumbnailers, archive managers, password stores, font viewers, players, screenshot and notification systems; check Arch/AUR. Reuse a good backend; wrap a good Linux UI in a Mavericks-like frontend; do not rewrite mature backends for aesthetics. Renaming via `.desktop` is not Mavericks integration (section 9).
Legal: reuse open source actively but check licences, never copy Apple proprietary code/assets, document component origin, keep attribution (summary in `docs/APPS.md`). The goal is functional and visual imitation with own or compatible resources.

## 6. Mavericks UX target

Mavericks-era UX: visual hierarchy, toolbar, sidebar, Finder behaviour, menu bar, Dock, application menus, window buttons/chrome, dialogs, sheets, alerts, context menus, file chooser, open/save dialogs, search, Quick Look, icons, typography, spacing, gradients/textures, terminology, shortcuts, selection, double-click, drag-and-drop, launch behaviour, fullscreen/minimise, desktop/Trash/notifications.
Global coherence is P0: never a Mavericks-like Finder next to a Linux-like Settings, a default GTK file chooser, an Xfce context menu or another toolkit's dialog. Unify GTK theme, borders, title bars, toolbar, icons, fonts, spacing, menus, dialogs, file chooser, notifications, launchers, Dock, menu bar, wallpaper, cursor, selection/hover/disabled/focus states, error and confirmation dialogs. Every GUI component is judged as part of one visual system.
Menu bar/Dock/window management: top menu bar with application menu and app name on the left, standard menus, Dock with running indicators, minimise/maximise/fullscreen where fitting, window switching, Mission Control, workspaces, quit behaviour; do not break the Xfce backend.
Keyboard architecture: one central global layer, Mavericks-like conceptual mapping (Command-like modifier where practical; Spotlight, Launchpad, Mission Control, Screenshot, Quick Look, app/window switching, Finder operations); do not break ordinary Linux shortcuts; the owner can remap later.

## 7. Performance, energy and the frozen power baseline

Every new component needs a runtime-cost justification. Prefer event-driven, on-demand, one-shot, cached, low-frequency polling, an existing system daemon, kernel counters, D-Bus events. Avoid persistent Python daemons, Electron, Java, heavy web UI, duplicate daemons, frequent filesystem scans or subprocess spawns, extra timers, constant CPU wakeups. Do not sacrifice important UX for ideological minimalism: measure the real cost first; if polling is needed, estimate frequency and cost.

The power baseline (Phase 0.3/0.5, source of truth) is a separate stable layer; do not break it for UI. If GUI work needs a change: document it, run a separate experiment, never mix silently.
- Kernel cmdline: `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0` (`pcie_port_pm=off` is a provisional Apple S3X resume workaround, `i915.enable_psr=0` is diagnostic-safe; both are hardware-validation items). Turbo ON; APST/FBC/GuC/THP/VM at defaults.
- TLP only: `CPU_SCALING_GOVERNOR_ON_AC/BAT=powersave`, `PCIE_ASPM_ON_AC/BAT=powersave`, `USB_AUTOSUSPEND=1`, `RUNTIME_PM_ON_AC/BAT=auto`. CPU_BOOST, PLATFORM_PROFILE, EPP unset.
- zram via zram-generator, size RAM/2, zstd, no disk swap.
- Do NOT add without evidence: thermald, ananicy-cpp, `powertop --auto-tune` (banned), random sysctl tuning, forced Turbo, forced APST/GuC/PSR-FBC.
- Measure every "optimising" change before/after (boot time, idle RAM, idle power on hardware) in `docs/BENCHMARKS.md`; memory budget in `docs/MEMORY_BUDGET.md`.
- RAPL/package energy is not whole-laptop power; document the difference between package energy, CPU/GPU estimate, battery discharge rate and whole-system power; verify the correlation on hardware.

## 8. Documentation, testing, git

State lives in the repo: `docs/APPS.md` (surface inventory, statuses, backends, licences), `docs/PROGRESS.md` (done/next/blocked, public changelog, update every session and push), `docs/DECISIONS.md` (every non-obvious decision and why), `docs/HARDWARE.md`, `docs/NEEDS_HARDWARE_TEST.md`, `docs/ENVIRONMENT.md` (root/access in the build container; read on sudo problems), `docs/MEMORY_BUDGET.md`, `docs/BENCHMARKS.md`. Document what really works versus mocked or wrapped, hardware-dependent and deferred items, reused components (+licences), runtime cost, known limitations.
Every significant change gets the strongest possible pre-hardware test: syntax, compile, package build, install into DESTDIR, desktop-file validation, XML validation, `bash -n`/shellcheck, `py_compile`, startup tests, basic X11/D-Bus tests, dependency checks. Never report "works" from compilation alone.
Git: small logical commits (`feat:`, `fix:`, `perf:`, `theme:`, `docs:`) without stopping the work after each micro-step. Before a change `git status`; after it tests, `git diff`, check for accidental baseline changes, commit. After a finished iteration the tree is clean unless there is deliberate WIP.

PUBLISH RULE (owner directive): every finished objective gets a descriptive commit (what and why) and is pushed to origin promptly. A finished objective that is not pushed is not finished. `docs/PROGRESS.md` is the public changelog; `docs/DECISIONS.md` is updated in the same commit. If push needs auth that is missing, record the exact blocker in PROGRESS.md and continue.

ISSUE #1 RULE (https://github.com/AnsvipaRinh/MavLinOS/issues/1): large but proven-necessary architecture work is not postponed for being big. Decompose into small independently testable objectives: target architecture and migration boundary -> compatibility layers/adapters -> migrate one surface at a time -> regression after each step -> working fallback during migration. Hardware-dependent validation is an explicit LATE check, not a reason to postpone the architecture. Examples: global menu, Mission Control overview layer, replacing rofi surfaces when their fidelity ceiling is proven. Record in DECISIONS.md.

Stop and ask the owner ONLY for: physical hardware, a missing secret, a destructive operation, a technically unresolvable decision, conflicting requirements, data-loss risk, a choice between architectures with irreversible consequences. Missing hardware is a reason to do pre-hardware work, not to ask.

GIT STASH BAN (owner directive 2026-10-06): never use `git stash` in any form. To set work aside, commit it to a branch or leave it untouched and report. Stash operates on the shared worktree and silently overwrites other agents' uncommitted changes.

## 9. No fake completion, statuses, app-surface audit

Do not declare IMPLEMENTED because a `.desktop` exists, a window was renamed, an icon was added, the app launches or a backend exists. Thunar + icon is not Finder; rofi + search is not Spotlight; rofi window mode is not Mission Control; galculator + `.desktop` is not Mavericks Calculator; a stock GTK dialog is not a Mavericks dialog. Judge user-facing behaviour.
Status path: RESEARCH REQUIRED -> EXISTING SOLUTION FOUND -> BACKEND REUSABLE / UI REUSABLE -> PARTIALLY IMPLEMENTED -> IMPLEMENTED -> IMPLEMENTED - HARDWARE VALIDATION REQUIRED -> VALIDATED; or DEFERRED / EXCLUDED.
App-surface audit for every important program, kept as a structured table in `docs/APPS.md` (do not re-research closed items): launch, window chrome, toolbar, sidebar, content view, navigation, search, context menu, dialogs, file chooser, keyboard, drag-and-drop, icons, notifications, Finder/Quick Look/Trash integration, MIME, settings, theme, application menu.
Audit snapshots are NOT to be trusted blindly; re-verify against the repository. Known work items: Finder is still more Thunar than Finder; Spotlight infrastructure exists but UX is unfinished; Mission Control is not a real overview; some apps are Mavericks aliases over stock Linux UI; Quick Look Space integration is incomplete.

## 10. Application / desktop roadmap

Do not implement everything in one commit; bring each item step by step into one DE. Terminal stays a normal Linux Terminal (Console = Mavericks-like log viewer, NOT Terminal). Lock: a visual lock-screen curtain is fine WITHOUT account/password infrastructure at this stage; real Users/Accounts management is out of scope now.
P0: global desktop coherence; Finder; Spotlight; Mission Control; Launchpad; Control Center; Notification Center; Quick Look; menu bar/Dock/window behaviour; common dialogs/file chooser/context menus; Settings integration.
P1: Activity Monitor; System Information; Disk Utility; Screenshot; Preview; TextEdit; Calculator; Notes; Reminders; Calendar; Music; Photos; Voice Memos; Console; Keychain Access; Font Book; Digital Color Meter; Stickies; Dictionary (low priority). Contacts: not at this stage.
P2 (research/future, only after P0/P1): AirDrop; Time Machine UI; Automator/Shortcuts; Grapher; Migration Assistant; App Store; Software Update polish.
EXCLUDED: Contacts (current stage), TV, Podcasts, Siri, AirPlay, Chess, Game Center, Printer Discovery as a dedicated clone, Image Capture, Migration Assistant (current priority), Terminal replacement. Do not silently re-add excluded apps.
Settings: Mavericks-like General, Desktop/Screensaver, Dock, Mission Control, Language/Region, Security/Privacy (where applicable), Notifications, Displays, Energy/Power, Keyboard, Mouse, Trackpad, Sound, Network, Bluetooth, Sharing (where useful). Display/Keyboard/Trackpad/Mouse/Sound/Network/Bluetooth must read as one Settings environment. Printers/Scanners are not a priority.

10.1 Finder (special priority). Thunar + theme is not a finished Finder. Approximate behaviour over the mature backend (Thunar/GVfs, no file-manager rewrite; if upstream integration is impossible use clean external integration, not hacks): sidebar (Favorites/Devices/locations), folders, selection, icon/list/column-like views, back/forward history, path, search, context menus (New Folder, Get Info, Rename, Move to Trash, Empty Trash, Eject, Open With), Quick Look (Space where possible), drag-and-drop, previews, hidden files, bookmarks, removable/network devices, toolbar, status bar, metadata, keyboard navigation, Command-like shortcuts via the global layer.
10.2 Spotlight/Launchpad/Mission Control. Spotlight is not plocate/rofi by itself: global shortcut, centred overlay, search field, fast response, files/apps/system objects, keyboard navigation, open selection, sensible ranking, no extra daemon, no Electron (plocate/index/desktop DB/light custom index; evaluate energy cost before any daemon). Launchpad is not a rofi menu: discovery, icon grid, pages, keyboard navigation, search, launch behaviour, cheap animations, consistent icon sizing, Dock integration, global shortcut. Mission Control is not "rofi window mode": global shortcut, all windows at once, workspaces, grouping where practical, click/select, Escape closes; research X11/Xfce/AUR solutions (current experiment: skippy-xd), otherwise a light custom frontend over X11 enumeration; no heavy resident daemon; document compositor limits.
10.3 Control Center/Notification Center. Control Center: Wi-Fi, Bluetooth, sound, brightness, battery, power, display controls, network state, entry to notifications/settings (D-Bus, NetworkManager, BlueZ, PipeWire, UPower, sysfs, xfconf; events instead of polling). Notification Center: one architecture (libnotify, xfce4-notifyd, no second daemon), app + system notifications, history, Mavericks-style right panel, dismiss, keyboard behaviour.
10.4 Quick Look/Preview. Light pipeline: images, PDF, text, common documents, audio/video metadata (thumbnailer, pixbuf, Poppler, GStreamer). Real Space integration if the architecture allows, else clean external integration (current: single-shot `mv-quicklook` + Thunar actions).
10.5 Activity Monitor (+HUD)/System Info/Disk Utility. Activity Monitor: CPU/Memory/Energy/Disk/Network from cheap sources (`/proc`, `/sys`, kernel counters), refresh only while the window is open. Energy/Thermal HUD: minimal footprint, ideally no resident process (the current `mv-hud` C one-shot stays only while it has a measurable advantage). About/System Report: `/proc`, `/sys`, DMI, PCI, USB, X11 display info, network, kernel, storage; cache static data, no polling loops. Disk Utility: Mavericks-like frontend over UDisks2/gnome-disk-utility (disks, partitions, filesystems, mount/unmount/eject, SMART where possible, formatting, permissions, removable); special care for Apple S3X NVMe.
10.6 Other apps: integrate through the common system (icons, desktop entries, naming, MIME, launch, settings, notifications, menus, dialogs, file chooser, theme, keyboard). Inventory and reused backends: `docs/APPS.md`.

## 11. Phases (hardware bring-up track; keep a checklist in `docs/PROGRESS.md`)

0. Base and hardware identification: confirm MacBook10,1 with `dmidecode` on first live boot; pacstrap minimal base; bootable via systemd-boot (UEFI; rEFInd fallback); acceptance = boots to console on real hardware or a precise log report in NEEDS_HARDWARE_TEST.md; QEMU+OVMF smoke test passed.
1. Hardware support (prepared, NOT verified): Wi-Fi (broadcom-wl-dkms + brcmfmac fallback), audio (Cirrus patch), Bluetooth, external USB-C input as the primary interface, built-in input (`applespi`) best effort with the 3-strategy limit, power = TLP baseline of section 7.
2. Over-optimisation (prepared, NOT verified): zram instead of disk swap, trimmed systemd units (target under 10 s to the display manager), journald volatile/soft rate-limit, no needless timers, custom kernel only after a stable stock one; every change measured in BENCHMARKS.md.
3. Mavericks visual layer (prepared, NOT verified): GTK3 skeuomorphism, pre-flat icons, Dock (plank, reflection/zoom), macOS cursor, top menu bar (functional global menu only if the Xfce plugin performs), wallpapers/icons in the Mavericks spirit without Apple files; acceptance = a screenshot a non-specialist calls "almost Mavericks".
4. ISO build and smoke test: `mkarchiso` from the finished profile; QEMU+OVMF (UEFI) smoke test (boots, DE starts, theme applies). QEMU does NOT test applespi/Broadcom/Cirrus.
5. Real-hardware iterations: the owner sends boots/doesn't boot, a screenshot, `journalctl -b`; diagnose from that without clarifying questions.

## 12. Final condition

Not "a set of Mavericks-themed applications", but: the desktop is a coherent Mavericks environment; Finder feels like Finder, Spotlight like Spotlight, Mission Control like Mission Control, Launchpad like Launchpad, Settings like System Preferences; Control Center, Notification Center and Quick Look are integrated; apps share one visual language; dialogs, file chooser and context menus do not expose stock Linux UI without need; keyboard behaviour, Dock and menu bar are coherent; system utilities are integrated; the backend is Linux-native; runtime and energy overhead are reasonable; the power baseline is kept; everything possible is done pre-hardware; hardware-dependent items are listed in NEEDS_HARDWARE_TEST.md.

## 13. Application-based completion (binding; hardware bring-up is a validation phase, not a development stop)

13.1 The project is never "ready for hardware bring-up" while any application or surface is PARTIALLY IMPLEMENTED, EXPERIMENT READY, NOT STARTED, IN PROGRESS, AUDIT REQUIRED or DEFERRED without an explicit reason. Hardware availability does not end pre-hardware implementation.

13.2 Canonical inventory (46 objectives, fixed scope).
P0 (25): 1 Finder, 2 Spotlight, 3 System Settings, 4 Control Center, 5 Notification Center, 6 Quick Look, 7 Preview, 8 Screenshot, 9 Activity Monitor, 10 System Information, 11 Disk Utility, 12 Launchpad, 13 Mission Control, 14 Power/Shutdown/Restart UI, 15 Trash, 16 Archive Utility, 17 Menu Bar, 18 Dock, 19 Application Menu, 20 Global Dialogs, 21 File Chooser, 22 Context Menus, 23 Keyboard Shortcut Layer, 24 Desktop/Wallpaper/Session Behaviour, 25 Window Management.
P1 (14): 26 TextEdit, 27 Notes, 28 Reminders, 29 Calendar, 30 Music, 31 Photos, 32 Voice Memos, 33 Console, 34 Keychain Access, 35 Font Book, 36 Digital Color Meter, 37 Stickies, 38 Calculator, 39 Dictionary.
P2 (7): 40 AirDrop, 41 Time Machine UI, 42 Automator/Shortcuts, 43 Grapher, 44 Migration Assistant, 45 App Store, 46 Software Update polish.
EXCLUDED: Contacts, TV, Podcasts, Siri, AirPlay, Chess, Game Center, dedicated Printer Discovery clone, Image Capture, Terminal replacement, account-management infrastructure, mandatory account/password infrastructure for the lock-screen curtain.

13.3 Universal Definition of Done. An application is NOT complete because a binary, script, `.desktop` or package exists, because it launches, because a stock app was renamed or wrapped, because QEMU boots or the ISO builds, or because docs say IMPLEMENTED. Check:
A functional backend really performs the operation; B intentional Mavericks-like UI instead of generic Linux UI; C common visual language (hierarchy, grey/translucent surfaces where fitting, toolbar proportions, typography, spacing, icons, controls, selection/hover/focus/pressed states, dialogs, window geometry, menu structure); D behaviour (keyboard navigation and shortcuts, focus, Escape, Enter/default actions, cancel, selection, double-click, context menus, drag-and-drop, errors, empty and unavailable states); E desktop integration (Dock, application menu, menu bar, global shortcuts, notifications, MIME/file associations, dialogs, file chooser, context menus, session); F coherence (several apps open must look like one OS; "backend works but UI is generic Linux" is not COMPLETE); G resource behaviour (startup cost, idle processes, persistent services, memory, CPU, wakeups, battery; no Electron/Java/heavy daemons without justification); H packaging (package, dependencies, install, `.desktop`, icons, config, ISO inclusion, reproducibility); I deterministic automated tests wherever possible; J hardware classification of every unresolved item: PRE-HARDWARE IMPLEMENTABLE, HARDWARE VALIDATION REQUIRED or HARDWARE BLOCKED (never hide unfinished software behind "hardware required").
A test counts only if it can fail: grep-ing source text is not verification of behaviour, and an app counts as working only if it launches on the virtual display without errors (`scripts/check-sync.sh` launch smoke, Xvfb :97). Lint tests with `tools/lint-tests.py`.

13.4 Status machine (one canonical status per application): NOT_STARTED, AUDIT_REQUIRED, IN_PROGRESS, PARTIALLY_IMPLEMENTED, IMPLEMENTED_HARDWARE_VALIDATION_REQUIRED, VERIFIED, HARDWARE_BLOCKED, DEFERRED, EXCLUDED. "COMPLETE" is never a vague global label. Fully complete only as VERIFIED, or IMPLEMENTED_HARDWARE_VALIDATION_REQUIRED when every pre-hardware requirement is implemented and only physical validation remains. PARTIALLY_IMPLEMENTED and EXPERIMENT READY both mean WORK REMAINS.

13.5 Keep a structured application matrix in the repo with: Application, Priority, Status, Backend, Frontend, Visual Integration, Keyboard Integration, Desktop Integration, File/MIME Integration, Dialogs, Error Handling, Performance Review, Automated Tests, Hardware Dependency, Known Gaps, Next Executable Action. Update it whenever an app is touched. It is authoritative for progress and must reflect the implementation, not intentions.

13.6 Specific requirements.
Finder: sidebar, favorites, devices, navigation, toolbar, view modes, icon/list/column behaviour where feasible, search, context menus, Get Info, Open With, Rename, Move to Trash, Empty Trash, Eject, Quick Look, keyboard navigation, drag-and-drop, MIME, dialogs, file chooser integration, removable media, bookmarks, status information, visual integration; "Thunar limitation" is not automatically a completion criterion, investigate the surrounding implementation first.
Spotlight: global shortcut, dedicated search UI, app and file search, result categories, ranking, keyboard navigation, launch/open, visual integration, indexing lifecycle, reasonable performance (rofi + plocate is a backend strategy, not a finished experience).
Launchpad: discovery, icon grid, keyboard navigation, launch, search, pages and grouping/folders where feasible, close behaviour, Dock/global shortcut integration (`rofi -show drun` is not Launchpad).
Mission Control: real window-overview behaviour; implement the best light X11/Xfce approach; if `skippy-xd` fits, integrate it instead of documenting an experiment.
Control Center: real controls for network, audio, Bluetooth, display/brightness, power, relevant toggles (backend availability is not UI completion). Notification Center: surface, history where feasible, consistent style, interaction, keyboard/global integration. Quick Look: Space where feasible, selection preview, image/document/text/media, window lifecycle, Finder integration, keyboard; if X11/Thunar lacks a hook, investigate another implementation. System Settings: one coherent app, not unrelated stock dialogs. Activity Monitor: process list, CPU, memory, relevant metrics, refresh, safe process interaction, Mavericks presentation. System Information: a coherent surface, not raw command output. Disk Utility: a usable storage/device interface over Linux storage backends. Console: the macOS-style log viewer, NOT Terminal. Preview: real document/image viewing and file integration. TextEdit/Notes/Reminders/Calendar/Music/Photos/Voice Memos: audit each independently; a mature backend may be reused but the user-facing integration must belong to the Mavericks-like desktop. Keychain Access: mature Linux secret-storage backend plus a keychain management surface. Font Book: real browsing/preview/management. Digital Color Meter: real screen colour sampling under X11 where feasible. Stickies: real sticky-note behaviour and desktop integration. Calculator: calculator behaviour with Mavericks presentation.

13.7 Reuse-first is not wrapper-first: keep mature backends, but renaming an existing Linux app does not complete a Mavericks app. Correct architecture: Mavericks-like frontend over a mature Linux backend; do not rewrite mature backend functionality unnecessarily.

13.8 Autonomous execution: after auditing the matrix do NOT stop. Pick the highest-priority app with unfinished executable work, implement, test, update the matrix, commit, continue. Commit, audit, clean tree, doc update, "next logical step" and "ready for hardware" (while pre-hardware work remains) are never stop conditions.

13.9 Re-audit rule: do not trust current `APPS.md`, `PROGRESS.md`, `HANDOFF.md` or earlier agent claims without inspecting the implementation. The last audit already proved Finder, Spotlight and Launchpad PARTIALLY IMPLEMENTED and Mission Control EXPERIMENT READY, so the project is not complete: implement the feasible gaps, do not merely document them again, then continue through the remaining apps. The audit is the start of the implementation pass, not its end.

13.10 Hardware is a validation phase. The real MacBook10,1 will be used for applespi, BCM43602 Wi-Fi, Bluetooth, Cirrus audio, S3X NVMe behaviour, USB-C/DP, brightness, thermals, power measurements and the real 2304x1440 display. Until then implement every software component that does not need it. The final pre-hardware state: ALL SOFTWARE OBJECTIVES IMPLEMENTED + ALL KNOWN HARDWARE-DEPENDENT ITEMS CLEARLY MARKED + AUTOMATED TESTS PASSING + ISO/QEMU REGRESSION PASSING.

13.11 Completion condition: do not declare readiness for final hardware validation until every in-scope app is audited; every feasible pre-hardware gap is implemented; every app has an appropriate terminal status; no PARTIALLY_IMPLEMENTED app remains where work is executable; no EXPERIMENT READY item remains where integration is feasible; the visual system is coherent; automated tests pass; the ISO builds; QEMU smoke/regression passes; docs match reality.

## 14. Orchestration (Orchestrator + workers)

Roles: the Orchestrator manages work and never implements; workers (`build` plus hidden `build-b` .. `build-j`, and `qwen`) do the work. Worker pins and chain order: `.opencode/model-fallback.json`; worker definitions: `opencode.jsonc`; the Orchestrator's full procedure, permissions and failure recovery: `.opencode/agents/orchestrator.md` (rev 2). A Task completion, commit, validation or phase end is a checkpoint, never a stop.

14.1 Capabilities.

| Role | Mode | Edit/Write | Bash | Task |
|---|---|---|---|---|
| orchestrator | primary | DENY | only the allow-list in `orchestrator.md` (read-only git, `scripts/session-reuse.py`, `scripts/task-watchdog.py`, discovery wrappers, `sleep`) | `build`, `build-b` .. `build-j`, `qwen` |
| build (stock) | primary | ALLOW | ALLOW | DENY nested delegation |
| build-b .. build-j, qwen | hidden subagent | ALLOW | ALLOW | DENY (no nesting) |

The Orchestrator keeps read/search/web/skill tools on purpose (state inspection is its job). `tools/lint-agent-permissions.py` fails when a prompt tells an agent to run a command its own allow-list denies; run it after editing any agent file.

14.2 Loop (details in `orchestrator.md`): read state -> GitHub discovery gate (`scripts/contrib/discovery-status.sh`, `scripts/contrib/backlog.sh --refine`) -> select the highest-priority unfinished objective (P0>P1>P2) -> dispatch via `preflight`, watchdog, `stuck` gate, single-flight, resume-first -> process the result (register, classify failures, migrate) -> launch the next Task immediately. Never end a turn with an unprocessed Task outcome. "Next objective is X" means start X now.

14.3 Blocker policy: stop only for physical hardware, a missing external resource/credential, a required owner choice or a fundamental environment limit. Code/test/build failures, unclear details and research needs go to a worker. Single-model quota or rate-limit exhaustion is NOT a blocker: rotate (`subagent_type` switch on the SAME `task_id`, no restart). A sub-agent stuck in provider retry for more than 300 s (watchdog threshold) is a STUCK-TASK failover: keep the logical session, record the dead model, continue the same `task_id` on the next healthy worker with `scripts/session-reuse.py migrate`. `migrate` printing `next-worker: NONE` leads to the WAIT LOOP in `orchestrator.md`.

14.4 Manual role use: the owner may open the Orchestrator for "приступай" loops or Build for a concrete task; Orchestrator restrictions do not affect manual Build sessions.

14.5 Session reuse (mandatory): registry `.opencode/sessions/registry.json`, helper `scripts/session-reuse.py`. Do not create a new Task session per micro-iteration while a live session holds useful context. Resume when the objective is the same and context is REUSABLE (more than 50% left); new session only on objective change, RETIRE verdict, verified-empty or verified-dead session (HTTP 404), CONTEXT_EXHAUSTED or SESSION_ERROR. Calendar -> Calendar refinement = same session; Calendar -> Disk Utility = new session.

14.5.1 RESUME-FIRST: the Orchestrator sees only the Task result string and cannot trust it for session state (cancelled sessions held 45k-100k tokens of real work while the result looked empty). After ANY non-clean Task end run `scripts/session-reuse.py status` and `scripts/session-reuse.py context <id>` before deciding. Same objective + real progress + no error state = RESUME the same `task_id` (a worker change after a MODEL_* failure never means a new session). Never infer emptiness from result text. Unreachable status is UNKNOWN/WAIT, never NEW.
Cheatsheet:
```
scripts/session-reuse.py status | context <id> | decide <id> --objective <O> --agent <w>
scripts/session-reuse.py register <id> --agent <w> --objective <O> --task "<T>" --oid <oid> --model <m>
scripts/session-reuse.py find-objective <oid> | exists <id> | abort <id> | preflight | version
scripts/session-reuse.py stuck --threshold 300 | migrate <id> --objective <O> --delay <sec>
scripts/session-reuse.py classify-error --record-model <m> --cooldown <sec> "<error>"
scripts/session-reuse.py health | mark-alive <model> | mark-dead <model>
python3 scripts/task-watchdog.py --ensure --all --threshold 300    # self-maintaining daemon; liveness = HEARTBEAT in .opencode/sessions/watchdog.log
```
The server endpoint is auto-discovered (env `OPENCODE_*`, then a live `opencode serve` process, then 4096); never look up ports by hand. The Orchestrator needs `orchestrator-protocol: 18` from `version`.

14.5.2 RESUME-RULE: continuation Task prompts are the single English word `resume` (or `continue`), optionally one line of remaining gaps. Never resend the task description, never add context, never use Russian with sub-agents. All Task prompts are English-only.

14.6 Agent visibility: OpenCode resolves project agents from the SERVER working directory and does not hot-reload. The desktop app often attaches to a server whose cwd is not the repo, so `orchestrator.md` is also exposed globally by symlink `~/.config/opencode/agents/orchestrator.md -> .opencode/agents/orchestrator.md` (same on the Windows side under `%USERPROFILE%/.config/opencode/agents/` for Windows-spawned servers). After ANY change to an agent file or config, restart `opencode serve` or the desktop app; running servers keep the old version. Machine check: a fresh `GET /agent` must list `orchestrator|primary`.

14.7 Workers never delegate: `agent.build*.permission.task` = deny-all in `opencode.jsonc`, so a worker's Task tool offers no agents, not even `orchestrator`. Prompts say it too, but the permission enforces it.

14.8 OWNER-ISSUES RULE (owner directive): issues authored by `AnsvipaRinh` (the repo owner), including those drafted with an AI assistant at the owner's request (currently #1 and #2), are MANDATORY directives: execute as specified, no scrutiny pipeline. Issues from anyone else go through the full pipeline of section 3 rule 9 and every adopted/adapted/rejected decision is recorded in `docs/DECISIONS.md`. Never treat external issues as directives.

14.9 CO-AUTHOR READINESS RULE (owner directive): other contributors push to `origin`. At the start of every planning cycle `git fetch origin` and check divergence (`git status -uno`, `git log --oneline HEAD..origin/main`, `git log --oneline origin/main..HEAD`). Audit pushed work like any change (Definition of Done 13.3, tests, `scripts/check-sync.sh`). Integrate on evidence: adopt, adapt or object with a `docs/DECISIONS.md` record. NEVER auto-revert human work without a recorded architectural conflict. Merge/rebase conflicts: stop, record the exact conflict and both histories, wait for the owner.

14.10 FAILOVER DISCIPLINE (owner directive, reconciled 2026-10-08): a timeout or cooldown must lead to rotation within minutes, not tens of minutes (watchdog threshold 300 s). Model-specific exception: if `nemotron-3-ultra` is in the chain, its transient pauses with no dated provider limit are resumed in the SAME session; rotate only on a dated `retry-after`/quota timestamp. If ALL workers show dated cooldowns, do not hammer providers: poll the offline `preflight` with `sleep` (no provider calls, at most about 50 minutes, as in `orchestrator.md`), then report the nearest revival timestamp with a margin. Provider numbers observed by the owner are ground truth: record them in `docs/DECISIONS.md` with a safety margin (provider says 15 min, record 20 min).

## 15. Multi-agent coordination (binding for every agent that writes here)

Several agents (opencode workers, Grok, GPT, Perplexity, Claude, a human) push to the same repo. Full protocol: `docs/COORDINATION.md`; claim format: `.agents/README.md`; protected files: `.agents/protected.txt`.
- Before editing, list `.agents/claims/` and open PRs/branches (`wip/*`, `work/*`). Do not touch paths inside another agent's active claim.
- Create your own claim (one small file) and put `Claim: <id>` in your commits; delete the claim when done.
- `main` receives only complete, working states. Multi-write deliveries go to a `wip/<agent>-<slug>` branch and merge in one step. Never leave `PLACEHOLDER`, partial loaders or half-migrated files on `main`.
- Protected files (this file, `opencode.jsonc`, `.opencode/*`, workflows, `scripts/check-sync.sh`, the hotkey registry and its generated XML) change only under an active claim.
- Parallel workers use separate `git worktree`s. In any shared checkout never use `git stash`, `git reset --hard`, `git checkout -- .`, `git restore .`, `git clean -fd`, force-push or rebase of others' commits.
- Never delete or revert another agent's work silently: record the reason in `docs/DECISIONS.md` and hold a claim.
- A test that cannot fail is not a test (13.3). Run `python3 tools/lint-tests.py` before committing tests.
