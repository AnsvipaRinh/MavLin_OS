# PREHARDWARE COMPLETENESS AUDIT — all-axes closure (C1 A–I + C2 J–S + R/D/PERF + P0+)

> Closure audit of every completeness/performance axis explored to date.
> Date: 2026-09-29. Master: 0ccfe4c. Host: WSL2 Arch (AMD R7 5800HS, 2 vCPU, 7.6 GB).
> Sources: COMPLETENESS_C1.md, COMPLETENESS_C2.md, ARCHITECTURE_OPTIMIZATION_AUDIT.md,
> NATIVE_REWRITE_CANDIDATES.md, RUNTIME_AUDIT.md, RUNTIME_COMPONENT_MAP.md,
> RUNTIME_SOURCE_AUDIT.md, DRIVER_AUDIT.md, DRIVER_OPTIMIZATION_CANDIDATES.md,
> UPSTREAM_PATCH_TRACKER.md, PERF_METHODOLOGY.md, PERF_AUDIT.md, MEMORY_BUDGET.md,
> SERVICE_AUDIT.md, PERSISTENT_SERVICES_AUDIT.md, DEPENDENCY_AUDIT.md,
> NEEDS_HARDWARE_TEST.md, BENCHMARKS.md, VIDEO_PIPELINE.md, HW_BROWSER_MATRIX.md.
>
> Status classes: **PROVEN-COMPLETE** (measured, no open question, no HW dependency for the
> core claim) / **PARTIALLY-EXPLORED** (measured but a concrete missing piece remains) /
> **NOT-EXPLORED** (listed as handoff, never executed) / **HW-REQUIRED** (pre-hardware
> work done, only physical validation remains) / **NOT-WORTH-PURSUING** (considered, rejected).
>
> Adversarial rule applied: any axis previously hand-waved is PARTIALLY-EXPLORED with the
> concrete missing piece — no free PROVEN-COMPLETE.

---

## 1. Axis table

### C1 — Completeness Research Track (axes A–I)

| Axis | Status | Evidence (commit + measurement) | Measured? | HW? | Open questions | Next action |
|---|---|---|---|---|---|---|
| **A — Boot-to-desktop pipeline** | PARTIALLY-EXPLORED | Static decomposition: 8 dead units + 5 dead initramfs hooks identified; P1-C4 applied (7eb6977, 8 units removed). Chain already parallel. | Partially (unit/hook inventory + serialization analysis) | Yes (wall-time decomposition) | Boot wall time to DM (target <10 s); initramfs decompress time with/without PXE+memdisk hooks | HW: systemd-analyze blame + boot wall time on target. Consider trimming PXE/memdisk hooks for USB-only boot. |
| **B — ELF/loader cost** | PROVEN-COMPLETE | 16-binary DT_NEEDED closure + loader cycles + page-fault proxy (C1 axis B table). Loader 1.5–4.8 ms/GTK binary; ~20 ms total session. GTK-floor CONFIRMED. mv-hud near-optimal (0.03 ms, 65 page faults). | Yes (LD_DEBUG=statistics + ru_minflt) | No | None — loader cost fully characterized and confirmed small. | None. Axis B is closed. |
| **C — Global dependency graph** | PARTIALLY-EXPLORED | All 142 direct packages classified by usage grep + installed size. P1-C1 applied (3193695, 13 packages removed, ~330 MiB). | Yes (package sizes + usage grep) | Yes (ISO size verification after removal) | Exact ISO size after removal — not verified by rebuild (mkarchiso needs root, blocked in this env). Transitive count (595) is ESTIMABLE, not verified. | Rebuild ISO in a root-enabled env and verify size + boot. |
| **D — True idle** | PARTIALLY-EXPLORED | Host idle 81.59% (60 s, includes agent noise — not a clean idle). ctx 28.4/s. WSL2 HVS/CAL IRQ noise identified as host-only. | Partially (CPU idle %, ctx-switch, IRQ breakdown) | Yes (per-process wakeups, RAPL, battery discharge) | Per-process wakeup count (`/proc/<pid>/wakeup`) — NOT-MEASURABLE on WSL2 kernel 6.18. Clean idle without agent noise. | HW: measure per-process wakeups + RAPL + battery discharge on target. |
| **E — Idle→active→idle** | PARTIALLY-EXPLORED | S19–S22 added + measured (results-2026-09-29-c1.json). Return-to-idle 0.9 s (isolated) / 1.2–13.8 s (with agent noise). S21 scan 24 ms warm. | Yes (4 scenarios) | Yes (network/audio/USB transitions) | Real network scan return-to-idle on BCM43602; real audio stream transition on Cirrus; real USB-plug transition on S3X. | HW: measure network/audio/USB transitions on target. |
| **F — Memory beyond RSS** | PARTIALLY-EXPLORED | Peak RSS ×10 spawns + in-process growth ×100 iterations + smaps_rollup. mv-dictionary 175.5 MB (WebKit2). In-process growth linear (14→132 MB, 95% anonymous). | Yes (spawn RSS + in-process growth) | Yes (long-session growth, zram under pressure) | mv-dictionary 175 MB: WebKit2 leak or steady-state? Long-session memory growth of persistent processes. zram effectiveness under pressure. | **Pre-hardware: investigate mv-dictionary WebKit2 memory (175 MB = 2× next-heaviest app).** HW: long-session growth on target. |
| **G — FS/cache architecture** | PARTIALLY-EXPLORED | Audit-hook call counts on fixture trees. mv-photos 6 opens/image (12000/2000). mv-music 1 open/track. P1-C3 cache applied (e6d65ba, warm hit 7.7×/2.1× faster). plocate updatedb 0.15 s/4.5k files. | Yes (call counts + plocate timing) | Yes (real library scan cost on large cold library) | mv-photos 6 opens/image → 1–2 combined header read — **listed as P1 next action, never implemented.** Real scan cost on 10k+ track cold library. | **Pre-hardware: reduce mv-photos 6 opens/image to 1–2 (combined header read).** HW: real library scan cost on target. |
| **H — IPC system-wide** | PROVEN-COMPLETE | Dio.DBus round-trip 0.205 ms (Gio sync), 0.246 ms (GetAll). Subprocess transport 3–8× more expensive. BT dedup VERIFIED (mv-control owns BlueZ exclusively). 52 own D-Bus call sites inventoried. | Yes (5-transport round-trip + BT dedup verification) | No | None — IPC fully characterized and confirmed clean. | None. Axis H is closed. |
| **I — Process model** | PARTIALLY-EXPLORED | Full reclassification (BOOT/PERSISTENT/EVENT/PERIODIC/ON-DEMAND/ONE-SHOT). P1-C2 lazy-import applied (444fba3, mv-calendar 0.41→0.10 s, mv-reminders 0.38→0.08 s). | Yes (import cost + process inventory) | No | Process inventory is static (from audit), not dynamically re-verified against current tree post-C2 changes (new cache module, etc.). Timer spawn cost reduction measured per-spawn, not in full-system context. | Re-verify process inventory against current tree. No other changes warranted. |

### C2 — Completeness Research Track (axes J–S)

| Axis | Status | Evidence (commit + measurement) | Measured? | HW? | Open questions | Next action |
|---|---|---|---|---|---|---|
| **J — Security/perf** | PROVEN-COMPLETE | P0-J1 applied (dfbd987): sshd disabled in ISO, root locked (`root:!`), permissive sshd_config.d override removed, opt-in gate via lab/agent/install.sh. Privilege model audited (no setuid, no pkexec, no polkit rules). | Yes (full privilege-transition grep + sshd/root config audit) | No | None — privilege model is already the safe manual-sudo pattern. | None. Axis J is closed. |
| **K — Build/ELF optimization** | PROVEN-COMPLETE | 6 flag variants compiled + sized + runtime-measured. All optimized variants identical size (14320 B). Runtime dominated by process spawn + /sys reads, not compiled code. PGO/LTO/stripping all have no case. `-march=skylake` confirmed correct for m3-7Y32. | Yes (6 flag variants + GCC march support check) | No | None — mv-hud is at the floor; build flags are correct. | None. Axis K is closed. |
| **L — Resource/UI loading** | PARTIALLY-EXPLORED | CssProvider load 4.07–4.5 ms. AppInfo.get_all 12–14.2 ms. Typelib imports 163–324 ms (dominate startup). P1-L1 cache applied (dc2df3f, cold 15.98 ms → warm 1.15 ms). | Yes (in-process medians + fresh-process typelib walls) | No | 27 KB theme CSS not audited for redundancy — "not reducible without shrinking the CSS" is a conclusion, not a verified measurement. | Audit theme CSS for redundancy (minor). No other changes warranted. |
| **M — Firefox startup/profile** | PARTIALLY-EXPLORED | Profile seed 44 KB measured. P1-M1 applied (77f6e15, profiles.ini + installs.ini added). Session-restore prefs quantified (6fd8fed). uBO 9 filter lists enabled. | Partially (profile seed size + config audit) | Yes (real Firefox startup cost, uBO filter-list load, SponsorBlock runtime) | uBO filter-list sizes are ESTIMATES (~30–40 MB raw), NOT measured offline. SponsorBlock third-party API privacy surface not documented to user. | HW: measure real Firefox startup + uBO load on target. Document SponsorBlock privacy surface. |
| **N — YouTube pipeline** | PROVEN-COMPLETE | 3 processes/playback (bash→mpv→yt-dlp). 1 metadata resolution. No teardown residue. Codec policy chain verified (avc1 > vp09 > hev1, AV1 excluded from preference). 19/19 tests pass. | Yes (static process/network analysis) | Yes (actual playback power/thermal on Gen9.5) | Codec policy is NO-CONCLUSION — final choice from HW measurement (HW_BROWSER_MATRIX 4-mode plan). Pre-hardware software work is done. | HW: validate codec policy on target (4-mode measurement). |
| **O — ISO minimalism** | PARTIALLY-EXPLORED | All 129 packages classified. P1-O1/O2 applied (1409361, 18 removed, 129→111). intel-gpu-tools KEPT (HW procedure). 11 more KEEP with evidence. | Yes (all 129 packages classified + installed sizes) | Yes (ISO size verification after removal) | Exact ISO size after removal — not verified by rebuild (mkarchiso needs root, blocked in this env). | Rebuild ISO in a root-enabled env and verify size + boot. |
| **P — Service parallelism** | PROVEN-COMPLETE | Unit DAG After=/Wants= audit for all boot-critical units. tlp/zram/NM/resolved/BT all parallel at multi-user.target. lightdm After=getty (minor, standard). No artificial serialization found. | Yes (unit DAG audit) | No | None — DAG fully audited and confirmed parallel. | None. Axis P is closed. |
| **Q — Logging/journal** | PROVEN-COMPLETE | Timer one-shot journal output measured (mv-timemachine 64 B/h only recurring noise; calendar/reminders silent). journald config audited (volatile in ISO, persistent with 100 MB cap on install). | Yes (timer one-shot output + journald config audit) | No | None — journal volume fully characterized and negligible. | None. Axis Q is closed. |
| **R — Observability itself** | PARTIALLY-EXPLORED | Subprocess spawn floor measured (/bin/true 1.60 ms, python 25.98 ms). Cold-vs-warm quantified (S02: +35 ms cold penalty). S23 host drift ±20% within batch measured. S23/S24 added to suite. | Yes (subprocess floor, cold-vs-warm, host drift) | No | True cold-cache measurement needs root (`/proc/sys/vm/drop_caches`) — NOT-MEASURABLE as user. Repeats=1 scenarios carry ±20% noise. | Root-level cold-cache measurement (host limitation, not a project gap — S23 honest alternative is in place). |
| **S — Failure/recovery** | PARTIALLY-EXPLORED | 7 failure classes × rollback path designed. Existing recovery infrastructure inventoried (lab control plane, mv-timemachine, systemd-boot fallback, mv-experiment.sh, git). | No (design track) | Yes (actual rollback validation on target) | Snapshot-before-change hooks (pacman + firstboot) — **designed but not implemented.** Lab control plane wiring into bring-up runbook — not done. | **Pre-hardware: implement snapshot-before-change hooks (pacman + firstboot).** Wire lab control plane into bring-up runbook. HW: validate each rollback path on target. |

### R-track — Architecture Optimization (R1–R2 + D1–D7)

| Axis | Status | Evidence (commit + measurement) | Measured? | HW? | Open questions | Next action |
|---|---|---|---|---|---|---|
| **R1 — Architecture inventory** | PROVEN-COMPLETE | 39 bin/mv-* + 12 bash tools + 6 units + 27 .desktop + 3 rofi themes + 2 Thunar actions + 7 xfce configs inventoried. Per-component startup cost + RSS measured. 52 D-Bus call sites inventoried. Process graph classified. | Yes (full inventory + per-component measurement) | No | None — inventory complete. | None. R1 is closed. |
| **R2 — Implementation priority** | PROVEN-COMPLETE | 6 items → 3 SUPERSEDED (BlueZ signals, worker thread, pactl→D-Bus), 1 CLOSED (mv-eject/rename), 2 STILL-OPEN accepted (mv-airdrop NM State, mv-diskutil ObjectManager — on-open only, P2). All reconciled with commits. | Yes (reconciliation with commit-level evidence) | No | None — all items reconciled. | None. R2 is closed. |
| **D1 — Network (brcmfmac/BCM43602)** | HW-REQUIRED | Runtime map + 18 source findings + 9 driver findings. Config fixes applied (F1/F2/F3/U2/U3, ab10a5e/0b0fcb6/a0623c9). 10 HW hypotheses (H1–H10) + 8 optimization candidates (O1–O8) all HW-PENDING. | Yes (source audit + config fixes) | Yes (all H1–H10 + O1–O8) | All HW measurements: idle interrupt rate, powersave, scan duration, suspend/resume, throughput, EFI NVRAM path, ACPI board detection. | HW: execute DRIVER_OPTIMIZATION_CANDIDATES §2 measurement plan. |
| **D2 — NM userspace** | PROVEN-COMPLETE | Backend pin (wpa_supplicant), connectivity check off, mv-control scan fix, backend A/B plan. All config-level work done. U1–U5 findings all KEEP or APPLIED. | Yes (source audit + config verification) | Yes (backend A/B on real BCM43602) | Backend A/B (wpa_supplicant vs iwd) — HW validation, but pre-hardware config work is complete. | HW: backend A/B measurement on target. |
| **D3 — Display (i915 Gen9.5)** | HW-REQUIRED | Runtime map + 10 source findings (S1–S10) + 4 driver findings (F12–F15). Baseline judged (PSR off, pcie_port_pm off). PSR flicker fix landed upstream 6.8.0-53. | Yes (source audit + baseline judgment) | Yes (PSR/ASPM A/B, resume matrix, compositor, backlight) | PSR on/off A/B, ASPM A/B, resume-cycle matrix, xfwm4 compositor settings, backlight PWM, DMC firmware, FBC status, forcewake. | HW: execute DRIVER_OPTIMIZATION_CANDIDATES §6 measurement plan. |
| **D4 — Audio (HDA/Cirrus CS4208)** | PARTIALLY-EXPLORED | Runtime map + 5 source findings (A1–A5) + 7 driver findings (F16–F22). Packaging fixes applied (F19–F22, 888e0ff). Driver source compiles on target kernel (F18 VERIFIED). DKMS build broken (F16/F17). | Yes (source audit + build verification) | Yes (audio power/idle, jack switching, suspend/resume) | **DKMS packaging track NOT executed** — driver NOT in ISO. tanisperez fork (working DKMS via PRE_BUILD) tracked as replacement pin but never evaluated or pinned. Audio on target is HW-blocked-by-packaging. | **Pre-hardware: execute DKMS packaging track (DECISIONS D4-4: tanisperez fork vs manual flow vs own PRE_BUILD).** HW: audio power/idle counters. |
| **D5 — Input/storage (applespi + S3X NVMe)** | HW-REQUIRED | applespi + S3X NVMe runtime maps + 12 source findings (I1–I6, S1–S6) + 6 driver findings (F23–F28). fstrim fix applied (F26, e5cfc06). applespi 3-strategy limit documented. | Yes (source audit + config fix) | Yes (applespi 3-strategy, S3X resume, ASPM A/B, power/idle counters) | applespi 3-strategy execution, S3X resume validation, ASPM A/B, NVMe idle power, battery discharge rate. | HW: execute DRIVER_OPTIMIZATION_CANDIDATES §8–9 measurement plans. |
| **D6 — Persistent services** | PROVEN-COMPLETE | All persistent services + own components final sweep — ALL compliant, zero changes. 8 system services, 3 user timers, 7 panel plugins, 1 autostart (Plank), 40 mv-* apps all on-demand. | Yes (full sweep) | No | None — all compliant. | None. D6 is closed. |
| **D7 — Boot + ISO packaging** | PROVEN-COMPLETE | mkinitcpio/systemd-boot/profiledef/packages/firstboot all CORRECT. Zero changes. | Yes (full audit) | No | None — all correct. | None. D7 is closed. |

### PERF — Performance Track (phases A–E)

| Axis | Status | Evidence (commit + measurement) | Measured? | HW? | Open questions | Next action |
|---|---|---|---|---|---|---|
| **PERF-A — Static audit** | PROVEN-COMPLETE | 12 suspects ranked (S-01..S-12). All disposed in Phase B. | Yes (static audit) | No | None — all suspects disposed. | None. PERF-A is closed. |
| **PERF-B — Phase B fixes** | PROVEN-COMPLETE | S-01..S-11 fixed with commits (14c8009, bfebe9b, 143e9b2, 5330d93, 8211b9f, b9d16ba, edd2eec). S-01 rescan 0.2 Hz → signals + 0.033 Hz fallback (≥83% reduction). S-03 MPRIS off UI thread. S-11 7 startup crashes fixed. | Yes (before/after + commit-level evidence) | No | None — all fixes applied and verified. | None. PERF-B is closed. |
| **PERF-C — Lazy imports** | PROVEN-COMPLETE | 8 apps touched (mv-dictionary WebKit2, mv-quicklook Poppler/GtkSource, mv-preview Poppler, + 4 unused-import removals). Per-app import walls measured (interleaved 5-rep). Structural win is cold-target effect. | Yes (per-app import walls) | No | None — measured and verified. | None. PERF-C is closed. |
| **PERF-D — Harness hardening** | PROVEN-COMPLETE | D-01 harness display-leak fix (c359ab0, S02 −11%, S03 −20%). D-02 unused-import cleanup (2ae61e6, 20 imports). D-03 cold-cache proxy (+63% warm→cold). D-04 browser absence recorded (ec4dad4). | Yes (before/after + proxy measurement) | No | None — all items done. | None. PERF-D is closed. |
| **PERF-E — Re-audit + stopping criteria** | PROVEN-COMPLETE | Full re-audit with GUI tier (G01–G05). 0 P0, 0 P1 suspects. All 24 suspects P2 or IGNORE. Stopping criteria reached (PERF_CRITERIA.md). | Yes (full re-audit + GUI tier) | No | None — stopping criteria reached. | None. PERF-E is closed. |

### P0+ — Settings / Browser / Video

| Axis | Status | Evidence (commit + measurement) | Measured? | HW? | Open questions | Next action |
|---|---|---|---|---|---|---|
| **Settings (mv-settings/mv-control)** | HW-REQUIRED | Full audit + P0/P1 fixes (phase 0.66). refresh_all 5s→30s (83% fewer ticks). BT dedup (2→1 D-Bus calls). 92% fewer subprocess spawns. mv-settings duplicates removed (21→18 entries). | Yes (full audit + before/after) | Yes (suspend/resume, panel-brightness, BT-pairing-real) | Suspend/resume + lid, panel-brightness on real BT panel, BT pairing with real devices. | HW: validate settings behaviors on target. |
| **Browser (Firefox)** | PARTIALLY-EXPLORED | Chrome fidelity rewrite done (toolbar, tabs, urlbar, sidebar, context menus, private, downloads, findbar). Profile seed + profiles.ini (77f6e15). uBO 9 filter lists + SponsorBlock configured. Session-restore prefs quantified. | Partially (config audit + CSS gate validation) | Yes (real Firefox startup, uBO load, VAAPI/WebRender, HiDPI) | uBO filter-list sizes ESTIMATED not measured. SponsorBlock third-party API privacy surface not documented to user. Real Firefox startup cost HW-REQUIRED. | Document SponsorBlock privacy surface. HW: measure real Firefox startup + uBO load on target. |
| **Video (mv-ytplayer)** | PROVEN-COMPLETE | Codec ranking measured host-SW (h264 4.20, vp9 5.57, hevc 7.99, av1 5.38 ms/frame). Selector chain implemented. 19/19 tests pass. Pre-hardware software work done. | Yes (host-SW codec ranking) | Yes (VA-API decode, power/thermal per codec) | Codec policy is NO-CONCLUSION — final choice from HW measurement. Pre-hardware work is done. | HW: validate codec policy on target (HW_BROWSER_MATRIX 4-mode plan). |

### C2 handoff — axes T–X (listed as C3 handoff, never executed)

| Axis | Status | Evidence (commit + measurement) | Measured? | HW? | Open questions | Next action |
|---|---|---|---|---|---|---|
| **T — Per-app deep-dive (mv-dictionary WebKit2 175 MB)** | NOT-EXPLORED | Listed as C3 handoff in COMPLETENESS_C2.md. Never executed. C1 axis F measured 175.5 MB peak RSS but did not investigate whether it is a WebKit2 leak or steady-state. | No | Partially (long-session growth needs HW, but leak-vs-steady-state can be investigated on host with long-running process + smaps_rollup polling) | Is 175 MB a WebKit2 leak or steady-state? Does it grow over hours? | **Pre-hardware: investigate mv-dictionary WebKit2 memory (long-running host process + smaps_rollup polling).** |
| **U — HiDPI/2304×1440 rendering calibration** | NOT-EXPLORED | Listed as C3 handoff. Never executed. Host has no display; pixel validation is HW-REQUIRED. | No | Yes (pixel validation needs real panel) | All HiDPI rendering: theme proportions, font scaling, icon resolution, CSS gradients at 2304×1440. | HW: pixel validation on target. Some pre-hardware work possible (Xvfb at 2304×1440 for layout smoke-test). |
| **V — Real Firefox startup on hardware** | NOT-EXPLORED | Listed as C3 handoff. Never executed. No Firefox on host (offline discipline). | No | Yes (real Firefox startup cost) | Real Firefox startup wall with seed profile + uBO + SponsorBlock. | HW: measure on target. |
| **W — applespi 3-strategy** | NOT-EXPLORED | Listed as C3 handoff. Never executed. 3-strategy best-effort limit per AGENTS.md §2. | No | Yes (applespi needs real SPI hardware) | Which strategy (if any) works on MacBook10,1 with kernel 6.15+. | HW: execute 3-strategy plan (AUR DKMS → linux-macbook patches → linux-lts). |
| **X — S3X NVMe resume validation** | NOT-EXPLORED | Listed as C3 handoff. Never executed. LKML thread open (Sep 2026), no upstream fix. | No | Yes (S3X resume needs real NVMe) | Does pcie_port_pm=off remain required? Is there a narrower PCI quirk? Battery cost of pcie_port_pm=off? | HW: execute resume-cycle matrix + ASPM A/B. |

---

## 2. Axis class counts

| Status | Count | Axes |
|---|---|---|
| PROVEN-COMPLETE | 18 | B, H, J, K, N, P, Q, R1, R2, D2, D6, D7, PERF-A, PERF-B, PERF-C, PERF-D, PERF-E, video |
| PARTIALLY-EXPLORED | 14 | A, C, D, E, F, G, I, L, M, O, R, S, D4, browser |
| NOT-EXPLORED | 1 | T |
| HW-REQUIRED | 8 | U, V, W, X, D1, D3, D5, settings |
| NOT-WORTH-PURSUING | 0 | — |
| **Total** | **41** | |

---

## 3. Second-order chains

### Chain 1 — Timer→wakeup→C-state→power→thermal→latency

**Path:** mv-calendar 5-min timer → 12 spawns/hr → each spawn wakes CPU from C-state → CPU power draw → thermal (fanless, throttling risk) → latency (if throttled, UI latency increases).

| Link | Status | Evidence |
|---|---|---|
| Timer→spawn cost | **MEASURED** | P1-C2 (444fba3): mv-calendar 0.41→0.10 s, mv-reminders 0.38→0.08 s after lazy-import. |
| Spawn→wakeup | **HW-ONLY** | Needs `/proc/<pid>/wakeup` on target kernel. NOT-MEASURABLE on WSL2. |
| Wakeup→C-state | **HW-ONLY** | Needs RAPL/package energy + C-state residency counters on target. |
| C-state→power | **HW-ONLY** | Needs battery discharge rate measurement on target. |
| Power→thermal | **HW-ONLY** | Needs `/sys/class/thermal` on target (fanless Core M). |
| Thermal→latency | **HW-ONLY** | Needs turbostat + UI latency measurement under thermal pressure. |

**Verdict:** Only the first link (timer spawn cost) is measured. The full chain is HW-REQUIRED. The P1-C2 lazy-import fix reduces the timer spawn cost by 77–79%, which reduces the frequency of the entire chain's activation.

### Chain 2 — Dep→pagefault→IO→startup

**Path:** GTK import → typelib imports (163–324 ms) → page faults (ru_minflt: python3+Gtk 5,941) → disk IO (cold: +0.21 s from D-03 fadvise eviction) → startup wall (331 ms / 44.6 MB).

| Link | Status | Evidence |
|---|---|---|
| Dep→pagefault | **MEASURED** | C1 axis B: ru_minflt proxy for 16 binaries. python3+Gtk 5,941 page faults. |
| Pagefault→IO | **MEASURED** | D-03 (PERF_D): cold-cache import +0.21 s (+63%) warm→cold via fadvise eviction. |
| IO→startup | **MEASURED** | S02/S03: 331 ms import, cold +0.21 s. G05: startup-to-first-draw 0.24–0.30 s. |
| (HW) NVMe cold-read magnitude | **HW-ONLY** | WSL page cache ≠ S3X NVMe. Real cold-read magnitude needs target. |

**Verdict:** Fully measured on host. The HW-only part is the real NVMe cold-read magnitude (WSL page cache ≠ S3X NVMe). The lazy-import structural win (PERF-C) is a cold-target effect: apps that never load WebKit2/GtkSource/GdkPixbuf on a given code path avoid those module costs entirely on first launch after boot.

### Chain 3 — Scan→open→IO→battery

**Path:** mv-music/mv-photos open → full library scan → 2000–12000 file opens → disk IO → NVMe power → battery drain.

| Link | Status | Evidence |
|---|---|---|
| Scan→open count | **MEASURED** | C1 axis G: mv-music 2000 opens (1/track), mv-photos 12000 opens (6/image). |
| Open→IO | **MEASURED** | Audit-hook call counts on fixture trees. |
| IO→NVMe power | **HW-ONLY** | Needs S3X NVMe power counters (`nvme smart-log`) on target. |
| NVMe power→battery | **HW-ONLY** | Needs battery discharge rate on target. |

**Verdict:** Scan cost and call counts measured. IO→battery is HW-ONLY. P1-C3 cache (e6d65ba) mitigates the warm case (7.7×/2.1× faster). The mv-photos 6→1–2 opens/image optimization (axis G) would reduce the cold-case IO by 3–6× but is not implemented.

### Chain 4 — PSR→display power→thermal→throttle

**Path:** i915.enable_psr=0 → display continuously refreshes from DDR → higher display power → thermal (fanless) → potential throttling → latency.

| Link | Status | Evidence |
|---|---|---|
| PSR off→display refresh | **VERIFIED (source)** | F12: PSR flicker on Gen9 with kernel 6.8+. Baseline `i915.enable_psr=0` is diagnostic-safe. Upstream fix landed 6.8.0-53. |
| Display refresh→power | **HW-ONLY** | Needs battery discharge A/B (PSR on vs off) on target. |
| Power→thermal | **HW-ONLY** | Needs `/sys/class/thermal` on target. |
| Thermal→throttle | **HW-ONLY** | Needs turbostat + frequency measurement under load. |

**Verdict:** PSR off decision is source-verified and baseline-justified. The power/thermal/throttle chain is HW-ONLY. The PSR A/B plan (DRIVER_OPTIMIZATION_CANDIDATES §6.1) is prepared but not run.

### Chain 5 — pcie_port_pm=off→NVMe D0→power→battery

**Path:** pcie_port_pm=off → NVMe stays in D0 (no D3hot, no APST) → higher idle power → faster battery drain.

| Link | Status | Evidence |
|---|---|---|
| pcie_port_pm=off→D0 | **VERIFIED (source)** | S3X does not expose APST (S1). Root port PM disabled → NVMe stays in D0. |
| D0→power | **HW-ONLY** | Needs battery discharge A/B (pcie_port_pm on vs off) on target. |
| Power→battery | **HW-ONLY** | Needs battery discharge rate on target. |

**Verdict:** pcie_port_pm=off→D0 is source-verified. The power/battery cost is unmeasured (HW-ONLY). The LKML thread (Sep 2026) asks if a PCI quirk for 00:1c.0 is possible instead of the global disable. The ASPM A/B plan (§6.2/§9.3) is prepared but not run.

---

## 4. Final Question — "Have we actually exhausted all meaningful software/pre-hardware work?"

**Answer: NO.**

The axis table shows 14 PARTIALLY-EXPLORED axes + 1 NOT-EXPLORED axis. Several of these have concrete pre-hardware missing pieces that are executable without hardware:

1. **Axis T (NOT-EXPLORED):** mv-dictionary WebKit2 175 MB memory investigation — listed as C3 handoff, never executed. This is the heaviest app (2× the next-heaviest). Leak-vs-steady-state can be investigated on the host with a long-running process + smaps_rollup polling.

2. **Axis G (PARTIALLY-EXPLORED):** mv-photos 6 opens/image → 1–2 combined header read — listed as P1 next action, never implemented. Would reduce cold-case IO by 3–6×.

3. **Axis S (PARTIALLY-EXPLORED):** Snapshot-before-change hooks (pacman + firstboot) — designed but not implemented. Recovery engineering gap.

4. **Axis D4 (PARTIALLY-EXPLORED):** DKMS packaging track — tanisperez fork evaluation + pin change never executed. Audio is completely blocked without this.

5. **Axis C/O (PARTIALLY-EXPLORED):** ISO rebuild verification — blocked by root/mkarchiso in this env, but executable in a root-enabled environment.

6. **Axis L (PARTIALLY-EXPLORED):** Theme CSS redundancy audit — minor, not done.

7. **Axis browser (PARTIALLY-EXPLORED):** SponsorBlock privacy surface documentation — minor, not done.

These are not vague "more audit" items. They are concrete software tasks with clear first steps. The project has exhausted the *research* phase but not the *implementation* phase for these specific items.

---

## 5. Open tracks (concrete next tasks)

| # | Track | Axis | First task | Blocked by? |
|---|---|---|---|---|
| 1 | mv-dictionary WebKit2 memory deep-dive | T | Long-running host process + smaps_rollup polling to determine leak vs steady-state | No (host-executable) |
| 2 | mv-photos combined header read | G | Reduce 6 opens/image to 1–2 via combined header read | No (host-executable) |
| 3 | Snapshot-before-change hooks | S | Implement pacman hook + firstboot hook for btrfs snapshot before change | No (host-executable) |
| 4 | DKMS packaging track | D4 | Evaluate tanisperez fork + execute pin change (DECISIONS D4-4) | No (host-executable) |
| 5 | ISO rebuild verification | C/O | Rebuild ISO in root-enabled env, verify size + boot | Yes (root/mkarchiso blocked in this env) |
| 6 | Theme CSS redundancy audit | L | Audit 27 KB CSS for redundancy | No (host-executable) |
| 7 | SponsorBlock privacy documentation | browser | Document third-party API privacy surface to user | No (docs-only) |

---

## 6. Honesty contract

- All host numbers are WSL2/5800HS-relative deltas, NOT MacBook predictions.
- GUI-tier measurements (window render, compositor, real browser, real playback) are HW-REQUIRED/QEMU.
- The 2 failing tests (mv-photos gthumb, mv-textedit respawn) are pre-existing host artifacts, NOT regressions.
- The axis statuses in this document are adversarial re-classifications, not rubber-stamps of prior track verdicts. Axes previously marked PROVEN-COMPLETE in C1/C2 but with concrete missing pieces are re-classified as PARTIALLY-EXPLORED here.
- HW-REQUIRED axes have their pre-hardware work complete; only physical validation remains. This is distinct from PARTIALLY-EXPLORED, where pre-hardware work remains.
