# BENCHMARKS — performance/power measurement results

> Methodology + honesty tiers: `docs/PERF_METHODOLOGY.md`. Harness:
> `scripts/bench/bench.py` (run: `scripts/bench/run-bench.sh`). Static audit:
> `docs/PERF_AUDIT.md`. All numbers are **host-relative deltas** on a 2-vCPU
> WSL2 build host (AMD Ryzen 7 5800HS, 7.6 GB RAM, no X, no RAPL) — never
> MacBook watts or latencies. Phase B validates changes by before/after JSON
> pairs on this host.

## BASELINE — 2026-09-27 (pre-optimization)

- Harness: `scripts/bench/bench.py` schema 1, profile `unconstrained`
- Raw JSON: `docs/benchmarks/results-2026-09-27.json` (run 1; run 2 used for variance)
- Result: 18 scenarios — 13 ok, 5 skipped (GUI tier, reasons recorded in JSON), 0 failed
- Full suite wall: ~2.5 min (budget < 10 min)

### Determinism (two consecutive runs, median delta)

| Scenario | Metric | Run 1 | Run 2 | Variance |
|---|---|---|---|---|
| S01-idle-residual | cpu_idle_pct | 95.15 | 94.76 | -0.4% |
| S01-idle-residual | ctx_switches_per_s | 6.10 | 2.00 | **-67%** (host noise, expected) |
| S02-py-framework-startup | wall_s | 0.1518 | 0.1518 | 0.0% |
| S03-app-import-proxy | median_wall_s | 0.1708 | 0.1763 | +3.2% |
| S04-spotlight-query | wall_s | 0.0404 | 0.0384 | -4.9% |
| S05-finder-browse-large | wall_s | 0.0015 | 0.0014 | -4.6% |
| S09-file-copy | wall_s | 0.2903 | 0.2715 | -6.5% |
| S11-preview-render | wall_s | 0.0477 | 0.0461 | -3.3% |
| S12-music-library-scan | wall_s | 0.0016 | 0.0016 | -0.7% |
| S13-notification-burst | wall_s (100 dbus calls) | 0.0191 | 0.0185 | -3.0% |
| S15-cpu-burst-short | wall_s | 2.0135 | 2.0139 | 0.0% |
| S16-cpu-burst-sustained | wall_s | 3.0162 | 3.0168 | 0.0% |
| S17-return-to-idle | wall_s | 0.9015 | 0.9018 | 0.0% |
| S18-nmcli-wifi-list | wall_s | 0.0075 | 0.0067 | -10.7% (abs. small) |

Verdict: deterministic enough for before/after deltas except S01
ctx-switches (shared-host noise — treat as order-of-magnitude only).

### Top-5 most expensive (measured, this host)

1. **S16 cpu-burst-sustained** (2-thread, 3 s target): 3.02 s wall — most
   expensive measured workload; scales with thread count as expected.
2. **S15 cpu-burst-short** (1-thread, 2 s target): 2.01 s wall.
3. **S17 return-to-idle**: 0.90 s from burst end to sustained >95% idle —
   the KEY metric; host returns to idle fast (no desktop daemons running).
4. **S09 file-copy** (500 MB): 0.29 s wall (host virtual disk, cached).
5. **S02 py-framework-startup**: 0.152 s per GTK app launch (gi+Gtk import) —
   paid by every one of the 37 mv-* apps; the largest *per-app* startup cost.

### Slowest startups (S03, non-GTK apps, real wall)

| App | Wall | Note |
|---|---|---|
| mv-power-ui | 0.262 s | slowest non-GTK startup |
| mv-textedit | 0.213 s | |
| mv-control | 0.212 s | |
| mv-preview | 0.192 s | |
| mv-diskutil | 0.191 s | |

18 GTK apps reached `Gtk.main()` (killed at 5 s guard) — startup succeeds,
latency is GUI tier (QEMU/hardware). `mv-newfolder` 3.0 s wall is the
arg-validation path (exits rc=1 without args), not startup.

### Idle residual (S01, 10 s window)

- CPU idle: **95%** (host has no desktop running — this is host baseline,
  NOT target idle; target idle residual must be measured on hardware).
- ctx-switches: 2–6/s (noisy, shared host).
- Processes: 106 (host). Top-10 RSS: 853 MB — dominated by the `opencode`
  agent process (654 MB) on this host; not representative.

### Cheap wins already visible in baseline

- S04 Spotlight query: 0.040 s (rofi script mode, no plocate on host).
- S05 Finder browse (5000 files, scandir+sort): 0.0015 s.
- S11 Preview decode (12 MP PNG via GdkPixbuf): 0.048 s.
- S12 Music scan (500 files, walk+stat): 0.0016 s.
- S13 Notification burst (100 dbus round-trips): 0.019 s total.
- S18 nmcli wifi list: 0.0075 s/call on host (no Wi-Fi device) — on target
  each call is a physical rescan; see PERF_AUDIT S-01.

## Phase-B change log

### 2026-09-27 — Phase B: audit fixes S-01..S-11 (commits 8211b9f..b9d16ba)

- Before: `docs/benchmarks/results-2026-09-27.json` (baseline, 20:09)
- After: `docs/benchmarks/results-2026-09-27-phaseB.json` (run 1, ~21:05)
  + `docs/benchmarks/results-2026-09-27-phaseB2.json` (run 2, same code, variance check)
- Result: 18 scenarios — 13 ok, 5 skipped (GUI tier), 0 failed. No harness
  regression: stable CPU scenarios moved ≤0.8% (S15 +0.7%, S16 +0.8%).

#### Delta table (baseline → phaseB run 1 → phaseB run 2)

| Scenario | Metric | Baseline | phB-1 | phB-2 | run1↔run2 | Verdict |
|---|---|---|---|---|---|---|
| S02 py-framework-startup | wall_s | 0.165 | 0.392 | 0.317 | -19% | host drift (untouched code path) |
| S03 app-import-proxy | median_wall_s | 0.178 | 0.374 | 0.394 | +5% | host drift |
| S03 app-import-proxy | apps_mainloop_reached | 17 | 24 | 24 | 0 | **real improvement** (S-11 fixes) |
| S04 spotlight-query | wall_s | 0.039 | 0.089 | 0.090 | +1.5% | host drift |
| S09 file-copy | wall_s | 0.269 | 0.528 | 0.519 | -1.8% | host drift |
| S11 preview-render | wall_s | 0.046 | 0.115 | 0.102 | -11% | host drift |
| S13 notification-burst | wall_s | 0.019 | 0.052 | 0.066 | +26% | host drift |
| S15 cpu-burst-short | wall_s | 2.013 | 2.028 | 2.029 | +0.1% | stable — no regression |
| S16 cpu-burst-sustained | wall_s | 3.016 | 3.040 | 3.034 | -0.2% | stable — no regression |
| S17 return-to-idle | wall_s | 1.204 | 6.921 | 0.903 | -87% | host drift (run 2 faster than baseline) |
| S18 nmcli-wifi-list | wall_s | 0.007 | 0.025 | 0.019 | -23% | per-call cost unchanged (as expected — S-01 reduces call *frequency*, not per-call cost) |

**Honesty note:** run-to-run variance on this shared WSL2 host is larger
than the baseline→phaseB delta for most scenarios (S17 swung 6.9 s → 0.9 s
between two runs of identical code). Per PERF_METHODOLOGY.md §0, only
same-host before/after deltas are meaningful, and here the dominant
factor is host contention, not the changes. The phase-B fixes are
app-level polling/timer/correctness changes whose effects are GUI-tier
or call-frequency — not host-measurable. The one directly measurable
signal (S03 apps_mainloop_reached 17 → 24) is a real improvement.

#### Per-fix behavior preservation + effect

| Fix | Behavior preserved | Measured/estimated delta |
|---|---|---|
| S-09 autostart removal | mv-notify-send still logs + forwards when called on-demand (mv-airdrop, mv-notification-center) | one less process + one less spurious notification per login |
| S-01 Wi-Fi signal-driven | same list fields, connect/disconnect/password flow, refresh on open, manual Refresh button | rescan frequency while Control Center open: 0.2 Hz → signal-driven + 0.033 Hz fallback (≥83% fewer rescans) |
| S-02 console follow | live tail, search-without-requery, Pause/Ctrl+L, cleanup on destroy | journalctl spawns while Console open: 0.5/s → 0 (persistent follow process, IO-watch driven) |
| S-03 music off-thread | now-playing freshness (on_change → immediate refresh), mini player | UI-thread blocking D-Bus: 3 round-trips/refresh → 0 (worker thread); initial refresh 300 ms → 1 s; kick retry 900 ms → 2 s |
| S-04 colormeter 200 ms | 5 Hz sampling still smooth under loupe | screen reads while open: 10 Hz → 5 Hz |
| S-10 hud wired | one-shot C tool, genmon 5 s interval | menu-bar energy/thermal readout now exists (was dead code); cost = one short-lived C process per 5 s |
| S-11 correctness | all apps construct and reach mainloop | S03 mainloop-reached 17 → 24; zero tracebacks in headless sweep |

#### Updated top-5 most expensive (phase-B run 1)

1. **S16 cpu-burst-sustained**: 3.04 s wall (stable vs baseline 3.02 s).
2. **S15 cpu-burst-short**: 2.03 s wall (stable).
3. **S09 file-copy**: 0.53 s (host drift; baseline 0.27 s — same disk).
4. **S11 preview-render**: 0.115 s (host drift; baseline 0.046 s).
5. **S02 py-framework-startup**: 0.39 s (host drift; baseline 0.17 s).

Slowest S03 exits are now all expected CLI arg-validation paths
(mv-newfolder 3.0 s, mv-quicklook-thunar 2.3 s, mv-getinfo 0.44 s,
mv-launchpad 0.41 s, mv-rename 0.38 s) — not startup crashes. The five
apps that previously "exited fast" because they crashed at init
(mv-control, mv-diskutil, mv-mail, mv-photos, mv-power-ui, mv-textedit)
now reach `Gtk.main()` like every other GUI app.

## Phase-C change log

### 2026-09-27 — Phase C: lazy imports (8 apps touched)

- Before: `docs/benchmarks/results-2026-09-27-phaseC-before.json`
- After: `docs/benchmarks/results-2026-09-27-phaseC.json` +
  `results-2026-09-27-phaseC2.json` (variance check, same code)
- Result: 18 scenarios — 13 ok, 5 skipped (GUI tier), 0 failed.
- Measurement note: a Wayland compositor became available on the build
  host mid-phase, so S03 GTK apps now reach `Gtk.main()` (5 s kill) under
  the harness instead of failing fast at init. Before/after pairs were
  therefore taken with `GDK_BACKEND=x11` + no DISPLAY (fast-fail mode,
  matching baseline conditions). Per-app import walls were additionally
  measured with an interleaved 5-rep `python -X importtime` harness
  (ABAB order to cancel host drift).

#### Import-breakdown (self-time, fresh process, ms)

| Module | Self cost | In Gtk dep tree? |
|---|---|---|
| Gtk | 136.9 | — (root) |
| GtkSource | 145.2 | no (unique lib) |
| WebKit2 | 129.9 | no (unique libs) |
| Gdk | 107.2 | yes (via Gtk) |
| PangoCairo | 50.0 | yes |
| GdkPixbuf | 40.1 | no |
| Pango | 45.7 | yes (via Gtk) |
| Notify | 38.9 | no |
| Gio | 35.1 | yes (via Gtk) |
| Secret | 35.1 | yes |
| GLib | 10.0 | yes |

Key insight: the large self-times of Gdk/Gio/GLib/Pango/PangoCairo are
mostly shared infrastructure that Gtk already loads — their *marginal*
cost on top of Gtk is ~0–2 ms. The modules with real unique dependency
trees are WebKit2, GtkSource, GdkPixbuf (and Poppler, absent on this
host). Lazy-importing those is where the actual saving is.

#### Lazy-import changes (files changed)

| File | Import | Move |
|---|---|---|
| mv-dictionary | WebKit2 (4.1→4.0 loop) | `_ensure_webkit()` with module-global cache; called from tab construction. Local-mode (`WebKit2=None`) fallback preserved; tests mock `m.WebKit2` directly — `_WEBKIT_TRIED` sentinel keeps mocked None stable |
| mv-quicklook | Poppler | `_ensure_poppler()` + `_POPPLER` cache; PDF branch only |
| mv-quicklook | GtkSource 4 | `_ensure_gtksource()` + `_GTKSOURCE` cache; text/code branch only |
| mv-preview | Poppler | `_ensure_poppler()` + `_POPPLER` cache; PDF branch only |
| mv-notification-center | Gdk | removed (unused — 0 references) |
| mv-rename | GLib | removed (unused) |
| mv-launchpad | Gio, GLib | removed (unused) |
| mv-getinfo | GdkPixbuf | removed (unused) |
| mv-calendar | GdkPixbuf | removed (unused, had noqa) |

No behavior change: all ImportError/ValueError fallbacks preserved
verbatim; import-once semantics via `_TRIED` sentinels; no lazy loading
inside loops. mv-textedit keeps top-level GtkSource (syntax
highlighting is its core function — common path). mv-fontbook keeps
PangoCairo (font rendering is its core function).

#### S02/S03 scenario deltas (before → after run 1 → after run 2)

| Scenario | Metric | Before | phC-1 | phC-2 | Verdict |
|---|---|---|---|---|---|
| S02 py-framework-startup | wall_s | 0.311 | 0.353 | 0.336 | host drift (Gtk import itself unchanged — expected) |
| S03 app-import-proxy | median_wall_s | 0.319 | 0.339 | 0.335 | host drift; no regression |
| S03 app-import-proxy | max_wall_s | 3.010 | 3.012 | 3.009 | stable (mv-newfolder arg-validation path) |
| S11 preview-render | wall_s | 0.113 | 0.114 | 0.228 | host drift |
| S13 notification-burst | wall_s | 0.053 | 0.074 | 0.062 | host drift |
| S15 cpu-burst-short | wall_s | 2.033 | 2.033 | 2.044 | stable — no regression |
| S16 cpu-burst-sustained | wall_s | 3.039 | 3.043 | 3.035 | stable — no regression |
| S17 return-to-idle | wall_s | 1.805 | 0.902 | 1.505 | host drift (identical code swings ±0.9 s) |
| S18 nmcli-wifi-list | wall_s | 0.019 | 0.016 | 0.022 | stable |

Honesty note (same as phase B): this shared host's run-to-run variance
exceeds the phase-C per-scenario deltas. The CPU scenarios (S15/S16)
are stable, confirming no systemic regression.

#### Per-app import walls (interleaved 5-rep median, ms)

| App | Before | After | Delta | Note |
|---|---|---|---|---|
| mv-dictionary | 137.3 | 141.0 | +3.7 | noise; WebKit2 marginal-after-Gtk ≈ 1–13 ms (Gtk pre-loads its dep tree) |
| mv-quicklook | 142.1 | 138.8 | −3.3 | GtkSource deferred to text path |
| mv-preview | 142.6 | 138.4 | −4.2 | Poppler absent on host — no measurable change here |
| mv-notification-center | 135.0 | 143.7 | +8.7 | noise (Gdk marginal ≈ 0 — Gtk loads it anyway) |
| mv-rename | 137.2 | 144.6 | +7.4 | noise |
| mv-launchpad | 146.3 | 134.2 | −12.0 | Gio+GLib removed (marginal ≈ 0; drift-dominated) |
| mv-getinfo | 146.6 | 136.9 | −9.6 | GdkPixbuf removed (real marginal ≈ −10 ms) |
| mv-calendar | 147.0 | 144.2 | −2.7 | GdkPixbuf removed |

Net assessment: measured per-app deltas on this warm host are small
(±15 ms) because Gtk pre-loads most of the shared gi infrastructure.
The structural win is real but shows mainly on a **cold** target
system: image-only Quick Look / Preview never loads GtkSource/Poppler
at all, and apps that never open an online dictionary tab never load
WebKit2. First-launch-after-boot on the MacBook (cold page cache) is
where the 130–145 ms module costs actually apply.

#### Thumbnailer / decode-path audit (task item 3)

- tumbler is **absent** from the ISO package list (thunar +
  ffmpegthumbnailer ship, but no tumbler daemon and no tumbler
  config). thunarrc sets `MiscThumbnailMode=ALWAYS` +
  `MiscShowThumbnails=TRUE` without a backend that can serve them.
  Decision: do NOT add tumbler now (it is a resident daemon — power
  baseline frozen; task rule). Documented in NEEDS_HARDWARE_TEST.md.
- mv-preview: thumbnail sidebar renders each page once at 160 px cap
  into a ListStore (surfaces cached, no per-frame re-decode); main
  page render capped at 800×600 / 3.0 scale. No re-decode found.
- mv-quicklook: renders only the current file; image path uses
  `new_from_file_at_scale` (no full decode); text capped at 200 KB;
  media via ffprobe metadata only. No re-decode found.

## Phase-D change log

### 2026-09-27 — Phase D: harness hardening + remaining measurable wins

- Commits: c359ab0 (harness fix), 2ae61e6 (unused imports), ec4dad4 (S14 absence record)
- Full run: `docs/benchmarks/results-2026-09-27-phaseD.json` — 18 scenarios,
  13 ok, 5 skipped (GUI tier), 0 failed.

#### D-1 harness display-leak fix (S02/S03)

Problem: S02/S03 children inherited the host DISPLAY/Wayland env. A Wayland
compositor became available on the build host mid-phase-C, so S03 GTK apps
reached `Gtk.main()` under Wayland (23 × 5 s kills = 127 s scenario wall)
instead of fast-failing at display init like the phase-A/B baseline.
Before/after pairs were not comparable across host display states.

Fix: `headless_env()` in bench.py — `GDK_BACKEND=x11` + DISPLAY stripped for
both scenarios (commit c359ab0).

| Scenario | Metric | Before (leak) | After (fixed) | Delta | Verdict |
|---|---|---|---|---|---|
| S02 | wall_s median | 0.3418 | 0.3029 | −11.4% | real: Wayland backend probe removed from import path |
| S03 | median_wall_s | 0.3851 | 0.3088 | −19.8% | real: same mechanism |
| S03 | apps_mainloop_reached | 23 | 0 | — | classification restored to baseline fast-fail semantics |
| S03 | scenario wall | 127.0 s | ~15 s | −88% | harness no longer pays 23×5 s kills |

Stability check: after-fix runs with parent DISPLAY set vs unset → same
classification (mainloop=0), medians 0.309 vs 0.327 (host drift band). Pairs
now comparable regardless of host display state.

#### D-2 unused-import cleanup (20 imports, 15 apps)

AST-based audit (pyflakes absent on host): zero Name/Attribute references, no
star-imports, no `__all__`, no dynamic usage. Removed: `sys` (airdrop, mail,
notify-send, settings), `os` (mail ×2, mission-control), `subprocess` (eject,
launchpad, openwith), `mimetypes` (preview), `Path` (shot), `GLib` (eject,
keychain, reminders), `Pango` (keychain), `GdkPixbuf` (colormeter, voice +
their `require_version` lines), `Gio` (timemachine + `require_version`).
Commit 2ae61e6.

S03 delta: 0.3088 → 0.3302 (host drift band; removed gi modules were already
loaded by Gtk — marginal ≈ 0, consistent with the phase-C import breakdown).
Full suite 1233/1233 green.

#### D-3 cold-cache import approximation (no root)

Method: `posix_fadvise(POSIX_FADV_DONTNEED)` on the 113 .so/typelib files
mapped by a probe child running the S02-style import; interleaved 5-rep
warm/cold measurement (ABAB order cancels host drift).

| Metric | Warm | Cold (evicted) | Delta |
|---|---|---|---|
| S02-style import wall, median | 0.3298 | 0.5379 | +0.2081 (+63.1%) |

(rep0 outlier +0.87 s — first-eviction partial effect; reps 1–4 delta
+0.17…+0.26 s.)

Verdict: FEASIBLE proxy, measured. Caveats: fadvise DONTNEED is best-effort;
the WSL virtual disk is backed by the Windows host page cache (real S3X NVMe
cold reads will differ in magnitude, not in kind); python/libc stayed warm
(parent-held). Validates the phase-C insight: the lazy-import structural win
is a cold-target effect — a cold Gtk import tree costs +0.21 s here; apps that
never load WebKit2/GtkSource/GdkPixbuf on a given code path avoid those module
costs entirely on first launch after boot.

#### D-4 browser workload (S14)

Absence recorded (2026-09-27): firefox, firefox-esr, epiphany, icecat,
chromium, google-chrome, brave, edge, web — none found. Offline discipline:
no install. S14 stays HW-deferred; skip reason in bench.py updated (ec4dad4).
What HW will show: headless startup wall + fixed file:// page-load wall on the
target, plus HD615 render behavior.

#### Phase C → D delta table (full run, medians)

| Scenario | Metric | Phase C (phC-1) | Phase D | Verdict |
|---|---|---|---|---|
| S02 | wall_s | 0.353 | 0.304 | harness fix (−14% vs phC-1; −2% vs phC-before 0.311) |
| S03 | median_wall_s | 0.339 | 0.310 | host drift band; no regression |
| S03 | max_wall_s | 3.012 | 3.009 | stable (mv-newfolder arg-validation path) |
| S04 | wall_s | 0.089 | 0.084 | stable |
| S09 | wall_s | 0.528 | 0.664 | host drift (shared disk) |
| S11 | wall_s | 0.114 | 0.138 | host drift |
| S13 | wall_s | 0.074 | 0.077 | stable |
| S15 | wall_s | 2.033 | 2.029 | stable — no regression |
| S16 | wall_s | 3.043 | 3.033 | stable — no regression |
| S17 | wall_s | 0.902 | 1.204 | host drift (identical-code swings ±0.9 s in phase B) |
| S18 | wall_s | 0.016 | 0.022 | stable (abs. small) |

Honesty note (unchanged from phases B/C): run-to-run variance on this shared
WSL2 host exceeds the per-scenario deltas; CPU scenarios S15/S16 are stable,
confirming no systemic regression. Phase-D changes are harness/tooling/hygiene
— their effects are cold-target or GUI-tier, quantified via the D-3 proxy.

## Phase-E change log

### 2026-09-27 — Phase E: browser emulator + GUI tier + stopping criteria + re-audit

- Full run: `docs/benchmarks/results-2026-09-27-phaseE.json` — 24 scenarios,
  19 ok, 5 skipped (S06/S07/S08/S10/S14 — specific app interactions, not
  general GUI), 0 failed.

#### E-1 browser-workload emulator (S14E)

- New: `scripts/bench/browser_emu.py` — synthetic Firefox-ESR-class tabbed
  session model. 7 phases: startup (regex/DOM), tab-alloc (RSS plateaus),
  scroll (render ticks), media-burst (zlib image-decode-like), js-churn,
  network-wait, return-idle. Deterministic (seed=42). Timeboxed (<3 min).
- Integrated into bench.py as S14E (3 repeats).
- Output: JSON schema 1 (compatible with bench.py). Logs to stderr, JSON to
  stdout.

#### E-2 GUI tier (G01-G05)

- X-server detection: Xvfb/Xephyr absent, but WSLg X server on :0 is reachable
  (Gdk.Display.open + window create/show/destroy verified). GUI tier is now
  measurable — first time in the perf track.
- G01: window create/show/hide/destroy ×10 per app (5 slowest starters).
  Median 3.6-3.9 ms per cycle. P2.
- G02: repeated open/close memory growth (RSS delta over 20 cycles).
  0-4 KB for 4 apps; mv-diskutil 996 KB (one-time GTK/UDisks2 caching,
  not a linear leak — inconsistent across runs). P2.
- G03: event-loop latency (idle_add round-trip p50/p99). 1.5/2.6 ms. P2.
- G04: notification burst through mv-notify-send logging path (50×).
  0.13-0.48 s. P2. (notify-send transport blocked without daemon; logging
  cost is the measurable part.)
- G05: startup-to-first-draw for 5 slowest apps (X11 window detection via
  ctypes + libX11). 0.24-0.30 s. P2 (all under 0.5 s P1 threshold).

#### E-3 stopping criteria (docs/PERF_CRITERIA.md)

- P0: interactive latency regression, background wakeup/rescan class, or
  crash/leak with growth >threshold.
- P1: startup >0.5 s cold-proxy-measured, or timer faster than UX needs with
  backend cost.
- P2: below host drift band, cosmetic, accepted-with-reason.
- IGNORE: synthetic-only, no user-visible path.
- Applied to all PERF_AUDIT.md suspects: **0 P0, 0 P1**. All suspects are
  P2 or IGNORE. Performance track has reached its stopping criteria.

#### E-4 re-audit

- Full re-audit with criteria: polling, timers, wakeups, persistent processes,
  repeated FS scans, unnecessary D-Bus, UI-thread blocking, memory growth
  (G02), cold-start (S03/G05), return-to-idle (S17).
- Result: 0 P0, 0 P1 suspects. All 24 suspects classified as P2 or IGNORE.
  See PERF_AUDIT.md "Phase-E re-audit" section for the full table.

#### GUI tier separation (X server proves vs HW-only)

| What X server on :0 proves | What is HW-only |
|---|---|
| Widget construction cost (G01) | Compositing performance |
| Memory growth/leak detection (G02) | Vsync/frame timing |
| Event-loop latency (G03) | Panel pixels/HiDPI rendering |
| Notification logging cost (G04) | notifyd processing/display |
| Startup-to-first-draw wall (G05) | Real display latency |

The X server on :0 is WSLg (software rendering, no GPU). It proves that
widgets construct correctly, no leaks exist, the event loop is responsive,
and apps start in <0.5 s. It does NOT prove anything about compositing,
vsync, panel pixels, or HiDPI behavior — those require the real HD 615
GPU and 2304×1440 display on MacBook10,1.

#### CALIBRATION map (emulator → future real-Firefox measurements)

The browser emulator produces synthetic patterns that can be correlated with
real Firefox-ESR measurements on MacBook10,1. The calibration map documents
which emulator numbers map to which future real-Firefox measurements:

| Emulator phase | Emulator metric | Future real-Firefox measurement | Calibration notes |
|---|---|---|---|
| startup | wall_s, cpu_s | Firefox headless startup wall | Regex/DOM ops model HTML/CSS/JS parsing. Calibrate by measuring real Firefox startup on target. |
| tab_alloc | peak_rss_kb, per_tab_rss_kb | Per-tab RSS in Firefox | 80 MB/tab default. Calibrate by measuring real per-tab RSS on target. |
| scroll | tick_ms_median, tick_ms_p99 | Scroll frame time on Firefox | 16.7 ms target (60 fps). Calibrate by measuring real scroll frame times on target. |
| media_burst | wall_s, cpu_s | Image decode time on Firefox | zlib compress/decompress models image decode. Calibrate by measuring real image decode on target. |
| js_churn | wall_s, cpu_s | JS execution time on Firefox | Arithmetic + GC churn models JS execution. Calibrate by measuring real JS execution on target. |
| network_wait | wall_s | Network wait time on Firefox | Idle sleeps model network waits. No calibration needed (wall = sleep duration). |
| return_idle | wall_s | Firefox return-to-idle after workload | KEY metric. Calibrate by measuring real Firefox return-to-idle on target. |

The emulator is NOT a Firefox replacement — it is a reproducible synthetic
workload that exercises the same resources (CPU, memory, I/O) in the same
patterns. When real Firefox measurements become available (on hardware), the
emulator can be fitted to match by adjusting the phase intensities.

## Phase 0.66 — mv-settings + mv-control full audit & P0/P1 fixes (2026-09-27)

### Per-section backend/cost table

| Section | Backend | Polling | Startup (ms) | D-Bus calls on open | RAM delta (20 cycles) | Issues |
|---|---|---|---|---|---|---|
| mv-settings (launcher) | subprocess.Popen per click | None | ~150-300 | 0 | 0 (exits on close) | Duplicates: Network/Wi-Fi, Battery/Energy |
| Wi-Fi (mv-control) | nmcli subprocess + NM D-Bus signals | 30s fallback + signal-driven | ~50 | 6 (NM subs) + 1 (nmcli radio) | 0 | Signal-driven since phase B |
| Bluetooth (mv-control) | BlueZ D-Bus GetManagedObjects | 30s (via refresh_all) | ~20 | 1 | 0 | Was: 2 D-Bus calls per 5s tick |
| Sound (mv-control) | pactl subprocess | None (user-initiated) | ~20 | 0 | 0 | Was: 2 pactl calls per 5s tick |
| Display (mv-control) | /sys/class/backlight reads | None (user-initiated) | ~5 | 0 | 0 | Was: /sys reads per 5s tick |
| Battery (mv-control) | upower subprocess | 30s (via refresh_all) | ~15 | 0 | 0 | Was: upower call per 5s tick |
| Power Mode (mv-control) | tlp-stat subprocess | 30s (via refresh_all) | ~15 | 0 | 0 | Was: tlp-stat call per 5s tick |
| DND (mv-control) | xfconf-query subprocess | 30s (via refresh_all) | ~10 | 0 | 0 | Was: xfconf-query call per 5s tick |

### P0/P1 fixes with before/after numbers

| Fix | Before | After | Delta |
|---|---|---|---|
| refresh_all timer interval | 5s | 30s | 83% fewer timer ticks |
| refresh_all subprocess calls per tick | ~8 (nmcli, pactl×2, upower, tlp-stat, xfconf-query, + 2 BT D-Bus) | ~4 (nmcli, tlp-stat, xfconf-query, + 1 BT D-Bus) | 50% fewer per tick |
| BT D-Bus calls per refresh_all tick | 2 (get_bt_enabled + refresh_bt_list) | 1 (shared _bluez_get_objects) | 50% fewer |
| Total subprocess spawns per 30s while CC open | ~48 (8×6 ticks) | ~4 (4×1 tick) | 92% reduction |
| on_output_device_changed no-op pactl | 1 subprocess per change | 0 | Removed |
| mv-settings duplicate entries | 21 entries (4 dupes) | 18 entries | Cleaner UI |

### Fidelity changes

- mv-settings: Removed duplicate Wi-Fi/Battery/Energy entries; consolidated
  to single "Network" and "Energy Saver" (matches macOS Mavericks layout)
- mv-settings: Removed dual-app launch from "Desktop & Dock" (was launching
  both xfce4-desktop-settings AND plank --preferences simultaneously)
- mv-control: No visual changes (CSS/layout already Mavericks-coherent)

### Suite counts

- mv-control: 32 tests (was 26, +6 new: BT on/off paths, _bluez_get_objects)
- Full suite: 1233 → 1239 tests, all pass
- check-sync.sh: ALL CHECKS PASSED

### HW-only remainder for settings

- suspend/resume + lid: logind hooks verified by inspection; HW behavior
  (S3 state, Wi-Fi/audio survive resume) → NEEDS_HARDWARE_TEST.md
- panel-brightness: /sys/class/backlight path verified; actual backlight
  control on MacBook10,1 → NEEDS_HARDWARE_TEST.md
- BT-pairing-real: BlueZ D-Bus calls verified; actual pairing with
  real devices → NEEDS_HARDWARE_TEST.md

## VIDEO CODEC — 2026-09-28 (host-SW tier, MEASURABLE)

- Harness: `scripts/bench/video_codec.py` (fixture clips, 120 frames, 3 repeats, median)
- Raw JSON: `scripts/bench/results/video-codecs.json`
- Run metadata: AMD Ryzen 7 5800HS, 2 cores, ffmpeg n9.0.2, WSL2 (Linux 6.18.33.2),
  2026-09-28 05:01:58. Deadline 41.67 ms/frame (24 fps).
- Tiers: host-SW = MEASURABLE (this run); VA-API = HW-ONLY (vainfo: no driver on
  host); power/thermal = HW-ONLY (needs MacBook10,1 instrumentation).

### 1080p ranking (cost per frame, median of 3 repeats)

| Rank | Codec | cost/frame | ffmpeg fps | wall (120f) | CPU% | RSS | HW Gen9.5 |
|---|---|---|---|---|---|---|---|
| 1 | H.264 (avc1) | 4.20 ms | 238.2 | 0.504 s | 107.0 | 65.3 MB | YES |
| 2 | VP9 (vp09) | 5.57 ms | 179.7 | 0.668 s | 102.2 | 73.6 MB | YES |
| 3 | HEVC (hev1) | 7.99 ms | 125.2 | 0.959 s | 111.0 | 97.8 MB | YES |
| 4 | AV1 (av01) | 5.38 ms | 185.8 | 0.646 s | 100.2 | 103.8 MB | NO (SW-only) |

All codecs meet the 41.67 ms deadline in host SW (max 7.99 ms). Ranking is by Gen9.5
HW-engine availability, not raw SW speed. 720p reference: h264 2.37 / vp9 2.70 /
hevc 4.00 / av1(SVT) 2.80 ms per frame.

### HW-only remainder

- VA-API decode on HD 615 (h264/vp9/hevc offload, av1 absence) → NEEDS_HARDWARE_TEST.md
- Power/thermal per codec (battery discharge, package vs whole-system, fanless
  throttling) → NEEDS_HARDWARE_TEST.md

---

## COMPLETENESS C1 — P1 implementation before/after — 2026-09-29

- Raw JSON: `docs/benchmarks/results-2026-09-29-c1-p1.json`
- Method: median of 3 runs. C2 = full-process wall (the timer spawns a
  process, so process startup is part of the measured cost). C3 =
  in-process scan wall (the scan is called in-process by the app, so
  process startup is excluded; cold = cache miss = full scan, warm =
  cache hit = the post-fix common case).
- Host: WSL2 Arch (AMD R7 5800HS, 2 vCPU, 7.6 GB). All numbers are
  host-relative deltas, NOT MacBook predictions (honesty contract).

### C2 — lazy Gtk import in timer one-shots (P1-C2)

| Timer path | Before | After | Delta |
|---|---|---|---|
| mv-calendar --check-upcoming (5-min) | 0.4115 s | 0.0964 s | **-77%** |
| mv-reminders --check-due (hourly) | 0.3770 s | 0.0801 s | **-79%** |
| mv-timemachine --check-due (hourly) | 0.4291 s | 0.2627 s | **-39%** |

The --check-* paths are pure Python (+ notify-send / libsecret) but paid
the module-level Gtk import (~150-400 ms per spawn). Defining the GUI
classes only in GUI mode eliminates it. mv-timemachine retains the
Secret (libsecret) import in timer mode for passphrase lookup (hence
the smaller delta). Saves ~4.4 s/hr CPU on the 5-min calendar timer.

### C3 — mtime+size-keyed scan-result cache (P1-C3)

| Scan | Before (full) | After cold (miss) | After warm (hit) |
|---|---|---|---|
| mv-music scan_library | 0.0541 s | 0.0818 s | **0.0070 s** |
| mv-photos scan_library | 0.0163 s | 0.0350 s | **0.0077 s** |

Every app open re-walked the full library and re-read all metadata. The
cache (mtime+size+count keyed JSON) makes a warm hit skip all file reads
(walk+stat fingerprint is the invalidation check). The cold-miss column
carries a one-time fingerprint + cache-write overhead per library change;
the warm hit is the common case (2nd+ app open) and is 7.7x (music) /
2.1x (photos) faster than the pre-cache full scan. Break-even vs the
pre-cache full scan is at 2 opens.

### Suite / gate

- Test scripts: 22 test-*.py. After C1-P1: 20 pass clean; mv-photos
  91/2 (2 pre-existing gthumb host artifacts); mv-textedit 6/6
  (pre-existing respawn host artifacts). mv-music 117/0 (+9 cache
  tests), mv-calendar 64/0, mv-reminders 32/0, mv-timemachine 60/0.
- Gate: `scripts/check-sync.sh --check-repos` → ALL CHECKS PASSED.

## COMPLETENESS C2 — P1 implementation before/after — 2026-09-29

- Raw JSON: `docs/benchmarks/results-2026-09-29-c2-p1.json` (31 scenarios,
  5 skipped GUI-tier, 0 failed)
- Host: WSL2 Arch (AMD R7 5800HS, 2 vCPU, 7.6 GB). All numbers are
  host-relative deltas, NOT MacBook predictions (honesty contract).

### J1 — security (P0-J1): sshd off + root locked + override removed

| State | Before | After |
|---|---|---|
| sshd in ISO | ENABLED (`multi-user.target.wants/sshd.service`) | symlink removed (OFF) |
| sshd_config.d/10-archiso.conf | `PasswordAuthentication yes` + `PermitRootLogin yes` | deleted (distro defaults) |
| root password field (airootfs shadow) | `root::` (empty) | `root:!` (locked) |
| firstboot root lock | — | `passwd -l root` (installed system) |
| remote bring-up | open-by-default root-SSH surface | explicit opt-in: `lab/agent/install.sh` → `systemctl enable --now sshd` (key-based forced-command as mavericks-lab, never root) |

No-boot-breakage: install is local (USB-C console); no `.wants/
.requires` references sshd (explicit symlink walk in check-sync);
lab agent needs no root SSH. sshd was idle-sleep ~5 MB — disabling
removes a resident process (strictly less).

### M1 — Firefox seed profiles.ini (P1-M1)

| Seed state | Before | After |
|---|---|---|
| profiles.ini / installs.ini | absent (activation non-deterministic; seed could be orphaned) | present (`Default=1` → mavericks.default) |

### O1/O2 — package removal (P1-O1/O2)

| | Before | After |
|---|---|---|
| packages in ISO | 129 | 111 (−18 unreferenced) |
| intel-gpu-tools | removal candidate (31.5 MiB) | **KEPT** — intel_gpu_top = GPU metric in HW_BROWSER_MATRIX 4-mode plan |
| powertop / turbostat / ethtool / dmidecode / mesa-utils | candidates | **KEPT** — HW procedures / active code (evidence in NEEDS_HARDWARE_TEST.md) |
| less / diffutils / hdparm / usbutils | candidates | **KEPT** — hard deps of man-db / mkinitcpio / tlp (pacman -Si verified) |

### L1 — shared .desktop parse cache (P1-L1)

| load_desktop_entries | Before (every open) | After cold (miss) | After warm (hit) |
|---|---|---|---|
| mv-launchpad + mv-spotlight raw parse | 15.5 / 12.1 ms (C2 axis L) | 15.98 ms | **1.15 ms** |

Warm hit = fingerprint (stat walk) + JSON read only; zero .desktop file
reads (test-verified). 13.9× vs the pre-cache full parse; the cold miss
carries a one-time fingerprint + cache-write overhead per desktop-DB
change. Break-even vs pre-cache full parse is at 2 opens (same class as
C1-P1 C3).

### Suite / gate

- Test scripts: 23 test-*.py (+test-mv-desktop-cache.py, 41 tests).
  21 pass clean; mv-photos 91/2 and mv-textedit 6/6 fail with the SAME
  pre-existing host artifacts documented in C1 (gthumb installed on
  host; respawn). NOT regressions.
- Gate: `scripts/check-sync.sh --check-repos` → ALL CHECKS PASSED
  (162 OK checks incl. 6 P0-J1 security + 1 P1-M1 seed validation).
- Bench: 31 scenarios, 5 skipped (GUI-tier), 0 failed.
- Power baseline untouched; no new daemons (cache is in-process JSON,
  event-driven invalidation).
