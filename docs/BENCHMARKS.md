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
