# PERF CRITERIA — optimization stopping criteria (phase E)

> Companion to `docs/PERF_METHODOLOGY.md`, `docs/PERF_AUDIT.md`,
> `docs/BENCHMARKS.md`. Defines when to STOP optimizing and accept the
> current state. Every open suspect must carry one label + the measurement
> that justifies it.

## Label definitions

| Label | Definition | Action |
|---|---|---|
| **P0** | Interactive latency regression, OR background wakeup/rescan class, OR crash/leak with growth >threshold | **FIX BLOCKER** — must fix before hardware bring-up |
| **P1** | Startup >0.5 s cold-proxy-measured, OR timer faster than UX needs with backend cost (rescan/subprocess) | **FIX** — fix in current phase |
| **P2** | Below host drift band, cosmetic, accepted-with-reason | **ACCEPT** — document, move on |
| **IGNORE** | Synthetic-only, no user-visible path | **SKIP** — no action needed |

## P0 thresholds

| Criterion | Threshold | Measurement |
|---|---|---|
| Interactive latency regression | Any measurable increase in G03 p50/p99 or S17 return-to-idle | G03 p50 >5 ms or p99 >20 ms; S17 >2 s |
| Background wakeup/rescan class | Any timer/scan that fires while NO window is open | Static audit: `timeout_add` in apps with no window-open guard |
| Crash/leak with growth | G02 RSS delta >100 KB over 20 cycles, OR any startup crash | G02 per-app `rss_delta_kb` >100; S03 `exited-error` with traceback |

## P1 thresholds

| Criterion | Threshold | Measurement |
|---|---|---|
| Startup (cold-proxy) | >0.5 s wall for a single app launch | S03 per-app `wall_s` >0.5 (cold-target; warm-host proxy via D-03) |
| Timer faster than UX needs with backend cost | Timer interval <5 s AND backend does rescan/subprocess per tick | Static audit: `timeout_add` interval + backend cost class |

## P2 thresholds

| Criterion | Threshold | Measurement |
|---|---|---|
| Below host drift band | Delta <10% between identical-code runs | BENCHMARKS.md run1↔run2 variance |
| Cosmetic | No measurable runtime cost | Static audit: one-shot, on-demand, no timer |

## IGNORE criteria

| Criterion | Definition |
|---|---|
| Synthetic-only | Measurement exists only in emulator/harness, no user-visible path |
| No user-visible path | Code path never executed in normal use |

## Application to PERF_AUDIT.md suspects

Every suspect in `docs/PERF_AUDIT.md` must carry one label. See the
"Phase-E dispositions" section of that document for the full table.

## Stopping rules

1. **Stop optimizing a scenario** when: P0/P1 count = 0 AND all remaining
   suspects are P2 or IGNORE.
2. **Stop the performance track** when: all scenarios have 0 P0/P1 AND
   the full suite is green AND the harness produces stable deltas.
3. **Never stop for host drift** — if run-to-run variance exceeds the
   before/after delta, the change is P2 (accepted) unless a P0/P1
   threshold is crossed.
4. **Re-open a P2** only if: new evidence (hardware measurement, user
   report) shows it crosses a P0/P1 threshold.
