# PERF METHODOLOGY — performance/power measurement track (phase A)

> Companion to `docs/BENCHMARKS.md` (results), `docs/RUNTIME_AUDIT.md` (daemon
> inventory), `docs/SERVICE_AUDIT.md` (services), `docs/MEMORY_BUDGET.md` (RAM).
> This document defines WHAT we measure, HOW, and HOW HONEST each number is.
> Phase A = methodology + harness + baseline. Phase B = optimization driven by
> the baseline and the static audit. The frozen power baseline (AGENTS.md §7)
> is never modified by measurement work.

## 0. Host vs target — the honesty contract

| | Build host (measurement) | Target (MacBook10,1) |
|---|---|---|
| CPU | 2 vCPU WSL2 (shared, burstable) | Core m3-7Y32, 2C/4T, fanless, 4.5W TDP |
| RAM | 7.6 GB | 8 GB LPDDR3 |
| Display | none (headless container) | 2304×1440 IPS |
| GPU | none (software) | Intel HD 615 |
| Storage | WSL virtual disk on SSD | soldered Apple S3X NVMe |
| RAPL/battery/thermals | **absent** | present |

**Rules:**

1. Every comparison is a **delta on the same host, before vs after a change**.
   Absolute host numbers are never presented as MacBook predictions.
2. Every metric carries one of three tiers:
   - **MEASURABLE NOW** — measured on this host, meaningful as-is for
     relative (before/after) decisions.
   - **ESTIMABLE** — scaled model with stated assumptions; used only for
     rough ordering, never for watt predictions.
   - **HW-ONLY** — RAPL package energy, battery discharge rate, thermals,
     panel self-refresh, applespi/BCM43602/Cirrus behavior. Cannot be
     measured here at all; listed so phase B does not "discover" them late.
3. Host watts ≠ MacBook watts. The host has no RAPL, no battery, and a
   different power delivery path. No watt numbers are produced by this
   harness; energy-proxy metrics (CPU time, wakeups, ctx-switches) are the
   portable currency.
4. Constrained-profile runs (taskset/cgroup CPU cap, mem cap) are a **rough
   ordering tool** to approximate "weak fanless CPU" behavior (e.g. does a
   scenario degrade superlinearly when CPU-bound?). They are **not** a watt
   predictor and are labelled `constrained` in results.

## 1. Scenario catalogue

Each scenario maps to a real user interaction. "Tier" = strongest honesty
tier available for its primary metric on this host.

| # | Scenario | User interaction | Primary metric | Tier |
|---|---|---|---|---|
| S01 | idle-residual | sitting at desktop, doing nothing | CPU idle %, ctx-switch rate, residual process CPU | MEASURABLE NOW |
| S02 | py-framework-startup | any mv-* app launch (framework part) | wall to `import gi; Gtk` ready | MEASURABLE NOW (proxy) |
| S03 | app-import-proxy | launching each mv-* app | wall until window-create or headless exit | MEASURABLE NOW (proxy) |
| S04 | spotlight-query | Cmd+Space, type query | query latency (rofi script mode) | MEASURABLE NOW (partial: no plocate) |
| S05 | finder-browse-large | open folder with 5k files | dir enumeration + sort wall | MEASURABLE NOW (backend only) |
| S06 | launchpad-open | F4 / hotcorner | rofi spawn + render | HW-ONLY (GUI tier; spawn cost measurable) |
| S07 | mission-control | Ctrl+Up | overview render | HW-ONLY |
| S08 | window-switch | Cmd+Tab / Alt+Tab | switch latency | HW-ONLY |
| S09 | file-copy | drag 500MB to another folder | wall, CPU, disk I/O bytes | MEASURABLE NOW |
| S10 | quicklook-open | Space on a file | preview window latency | HW-ONLY (decode cost measurable) |
| S11 | preview-render | image/PDF first page | decode+render wall | MEASURABLE NOW (decode only) |
| S12 | music-library-scan | first Music open, scan library | scan wall for N tracks | MEASURABLE NOW (backend only) |
| S13 | notification-burst | 100 notifications arrive | transport wall for 100 dbus Notify calls | MEASURABLE NOW (transport proxy) |
| S14 | browser-workload | Firefox page-load subset | — | DEFERRED (no Firefox on host; see §4) |
| S15 | cpu-burst-short | opening a heavy app | 1-thread 2s busy loop wall/CPU | MEASURABLE NOW |
| S16 | cpu-burst-sustained | sustained mixed workload | 2-thread mixed loop wall/CPU | MEASURABLE NOW |
| S17 | return-to-idle | **the KEY question**: after any action, how fast does the desktop return to idle? | seconds until CPU idle % recovers and ctx-switch rate falls back to baseline | MEASURABLE NOW |
| S18 | nmcli-wifi-list | Control Center Wi-Fi panel refresh | wall per `nmcli dev wifi list` (triggers rescan) | MEASURABLE NOW |

GUI-tier scenarios (S06–S08, S10) are **defined here** and skipped by the
harness with reason `no-x-display` when `$DISPLAY` is unset. They are not
"failed" — they are scheduled for the QEMU+OVMF smoke environment or
hardware, and their harness stubs record the skip reason so the gap is
visible, not silent.

## 2. Measured quantities (per scenario)

| Quantity | Source | Portability |
|---|---|---|
| wall-clock latency | `time.monotonic` around op | host + target |
| CPU time (user+sys) | `/proc/<pid>/stat` deltas, `resource.getrusage` | host + target |
| peak CPU % | `/proc/stat` sampling at 100ms | host + target |
| peak RSS | `/proc/<pid>/status` VmHWM, psutil | host + target |
| process count | `psutil.process_iter` | host + target |
| ctx-switches | `/proc/<pid>/stat` voluntary+nonvoluntary deltas, summed | host + target |
| wakeups | `/proc/<pid>/wakeup` (kernel 6.12+; else ctx-switch proxy) | target primarily |
| disk I/O | `/proc/<pid>/io` + `/proc/diskstats` deltas | host + target |
| startup latency | wall to first window (GUI tier) | target |
| background overhead | S01 idle residual: CPU% and ctx-rate with desktop "running" (simulated daemon set where possible) | host + target |
| RAPL package energy | `/sys/class/powercap/intel-rapl` | **HW-ONLY** |
| battery discharge | `power_supply` uevent rate | **HW-ONLY** |
| thermals | `/sys/class/thermal` | **HW-ONLY** |

## 3. Harness contract

- Location: `scripts/bench/bench.py` (runner + scenarios), `scripts/bench/run-bench.sh` (wrapper).
- Reproducibility: fixed fixtures under `/tmp/mv-bench/` (regenerated
  deterministically per run), warmup pass discarded, N repeats per scenario
  (default 5, I/O-heavy 3), median/min/max reported, per-scenario timeout
  guard (default 120s, idle 30s).
- Output: `docs/benchmarks/results-<date>.json`, schema versioned, includes
  host metadata (kernel, CPU model, RAM, container detection, DISPLAY).
- Determinism check: two consecutive full runs; variance recorded as
  `run1_vs_run2` median delta per scenario in `docs/BENCHMARKS.md`.
- Full suite wall time < 10 min on the build host.
- GUI scenarios: status `skipped`, reason recorded — never silently omitted.
- Exit code 0 when all *runnable* scenarios pass; skipped ≠ failed.

## 4. Deferred / partial measurements (explicit)

| Item | Status | Why | When |
|---|---|---|---|
| plocate file search (S04 full) | PARTIAL | plocate not installed on build host | install plocate + `updatedb` on host, or measure on target |
| Firefox page-load subset (S14) | DEFERRED | no Firefox on build host; headless WebGL/HD615 behavior is HW-only anyway | phase B decision: measure on target only |
| Real app startup (S03 full) | PROXY | no X display; proxy = wall to window-create failure point | QEMU+OVMF or hardware |
| RAPL/battery/thermals | HW-ONLY | absent on host | hardware bring-up |
| Wakeups (`/proc/<pid>/wakeup`) | HOST-LIMITED | kernel 6.18 WSL2 may not expose per-process wakeups; harness falls back to ctx-switch proxy and records which source was used | check on target kernel |

## 5. Constrained-profile runs (optional, ordering only)

`bench.py --profile constrained` adds:

- `taskset -c 0` (1 vCPU) to CPU-bound scenarios — approximates "weaker,
  contended CPU" ordering;
- `systemd-run -p MemoryMax=2G` if available, else `ulimit -v` — memory
  pressure ordering;
- software-rendering note: host has no GPU at all, so ALL host GPU-ish work
  is already software; this is stated, not simulated.

Results are tagged `"profile": "constrained"` and **must not** be compared
with unconstrained numbers as if they were watts. They answer one question
only: "does this scenario get *disproportionately* worse when CPU-bound?"

## 6. Phase-B feed

The static audit (`docs/PERF_AUDIT.md`) + this baseline produce a ranked
optimization backlog. Every phase-B change is validated by: same harness,
same host, before/after JSON pair, delta table in `docs/BENCHMARKS.md`.
A change is "worth it" if it improves a MEASURABLE NOW metric without
regressing another, and does not touch the frozen power baseline.
