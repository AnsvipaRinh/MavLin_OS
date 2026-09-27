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

(empty — phase B has not started; each entry: date, change, before/after JSON
pair, delta table, verdict)
