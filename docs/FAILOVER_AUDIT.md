# FAILOVER AUDIT — forensic review of the orchestrator model-failover machinery

Date: 2026-10-06. Mandate: owner-reported instability — «саб-агенты висят в
таймаутах, а оркестратор долго ничего не делает; нужно радикально улучшить».
Evidence set E1–E11 collected live in the hour before the audit; every item
was reproduced from repository/runtime state, not from memory.

Scope: `scripts/session-reuse.py`, `scripts/task-watchdog.py`,
`.opencode/sessions/registry.json`, `.opencode/sessions/model-health.json`,
`.opencode/model-fallback.json`, `opencode.jsonc`, `.opencode/agents/orchestrator.md`,
AGENTS.md doctrine. Everything outside the failover plane (packages/, docs
unrelated, panel/theme) is untouched.

---

## 1. Architecture-as-built (before this fix)

Intended flow «Task → зависание → детекция → аборт → cooldown → re-point →
resume»:

```
Orchestrator (foreground)                    Independent control path
─────────────────────────                    ─────────────────────────
Task(subagent_type=build-*) ──blocks──► provider retry loop (8800s observed)
        │                                              │
        │ prompt-discipline only                       │ scripts/task-watchdog.py
        │ (stuck --threshold 600,                      │ --daemon --all, every 20s:
        │  preflight, migrate)                         │ check_session()
        │                                              │  1. sr.session_exists (GET /session/{id})
        │                                              │  2. /session/status entry
        │                                              │     retry + MODEL_* + delay>600
        │                                              │     OR sr.stalled_generation (status-blind)
        │                                              │     OR sr.check_tool_abort_quota
        │                                              │  3. POST /session/{id}/abort
        │                                              │  4. health[model] = dead(retryAfter)
        │                                              │  5. registry lastAbort
        ▼                                              ▼
Task returns error ──► classify-error ──► health[model] (maybe) ──► migrate
                                                                    │ 1. record old model dead
                                                                    │ 2. resolve_next_worker()
                                                                    │    = worker_pins() minus
                                                                    │      cooldown/never/exclude
                                                                    │ 3. print Task block, SAME task_id
                                                                    ▼
                                                       preflight (next round) must skip
                                                       cooling models BEFORE any Task
```

Key components:

| Concern | File / function | State before fix |
|---|---|---|
| Worker pins | `session-reuse.py:worker_pins()` reads `opencode.jsonc` agent.* | worktree state, silent |
| Chain order/pools | `session-reuse.py:load_chain()` reads `.opencode/model-fallback.json` | worktree state, silent; no pool concept |
| Cooldown memory | `model-health.json` via `load_health()/save_health()/cooldown_remaining()` | key = **exact string passed by the writer** |
| Writers | `mark-dead`, `classify-error --record-model`, `cmd_migrate`, watchdog `check_session` | four call sites, four string conventions |
| Readers | `resolve_next_worker` → `preflight`/`migrate`/`models` | lookup by **pin string** |
| Stuck detection | `cmd_stuck` (status+delay), `stalled_generation` (status-blind), watchdog loop | registry-only rows reported as STUCK |
| Abort | `cmd_abort`, watchdog `POST /abort` | works; result channel loses task_id (E5) |
| Supervision | `task-watchdog.py --ensure` (daemon_healthy), `--daemon` loop | silent STARTED path (E9) |

### The breaks, mapped to evidence

**E1 — orphan flood, no GC.** `cmd_stuck`'s second loop flagged every
registry entry absent from `/session/status` with `verdict=STUCK` purely by
`lastUsed` age. But on this platform *status absence means IDLE* (documented
invariant in `session_exists`), so ~150 finished/forgotten entries produced
permanent STUCK noise (busyAge up to 180690s ≈ 50h), drowning the one real
signal and making `exit 2` meaningless. No GC existed anywhere: the registry
grew to 207 entries / 102 KB; nothing ever retired a verified-gone session.

**E2 — hard quota refusal invisible to the watchdog.** The refusal
(«Usage limit reached for 5 hour... reset 2026-10-06 07:06:36») arrived as a
Task *return*, not as a retry status entry. The watchdog only inspects
status/stalled/tool-abort shapes, so it never saw the class. The
orchestrator learned only after the Task returned — no cooldown was recorded
proactively, and the *exact provider-stated revival timestamp* in the
message was thrown away (classify-error used the flat 3h default).

**E3 — split-brain preflight.** `classify-error --record-model X` stored the
cooldown under the exact string the orchestrator typed (often the bare id
shown in Task output, e.g. `north-mini`), while `preflight →
resolve_next_worker → cooldown_remaining` looked up the exact *pin* string
(`openrouter/cohere/north-mini-code:free`). Different key shapes → miss →
`PREFLIGHT_OK build-b/north-mini` seconds after the model was recorded dead
20h. Same store, no shared matching rule.

**E4 — migrate ignored its own memory.** Identical root cause: `cmd_migrate`
ranked candidates via `resolve_next_worker`, whose cooldown lookup missed
entries recorded under another spelling; longcat was selected while its
cooldown sat in `model-health.json`. (Secondary contributor:
`cmd_migrate`'s re-record of the dead model with the 3h default could
SHRINK a longer existing cooldown — e.g. overwriting a 20h entry — making
the memory even less trustworthy.)

**E5 — cancelled Task loses task_id.** The OpenCode result channel does not
carry the child session id on cancellation. Recovery exists
(`discover_live_children` + `upsert_discovered` in the watchdog), but the
orchestrator must know to run it; bookkeeping is the only bridge. Not
fixable in our layer; documented + mitigated by GC never retiring sessions
that still exist server-side (verified-only retirement).

**E6 — config tug-of-war.** Uncommitted worktree rewrites of
`.opencode/model-fallback.json` (GLM entries wiped, `primaryWorker:
build-j`) and `opencode.jsonc` (build pin → ling-3.1) went wholly unnoticed:
`worker_pins()`/`load_chain()` read the worktree silently. The stale «GLM
REMOVAL RULE» in AGENTS.md gave an actor doctrinal cover to revert the
owner's restored state; owner restored both files with `git checkout HEAD --`
and there was no gate preventing a repeat. A protocol-version tug-of-war ran
in parallel (worktree downgrades 17→16/15; the consistency test that would
have caught it was deleted from the worktree).

**E7 — mass foreign churn.** ~170 files dirty at once, including all four
orchestration files, `.gitignore` (which made `.opencode/sessions/` and
`lab/contrib/` untracked). Actor unidentified. Structural mitigation = A2
drift gate on the two worker-config files + this audit's paper trail; the
rest is outside the failover plane.

**E8 — dead pin lived 13h, random-model on the critical path.** Historical
chain state: `ling-3.0-flash-fin` («no Zen route», Not Found) stayed pinned
while usable; `openrouter/free` (nondeterministic random model) sat on the
critical fallback path. Current committed chain already demotes/neutralizes
both (order 4 `worker: null` «random-model router … unsuitable»); the
residual gap is *visibility* — nothing surfaced «this pin 404s»
continuously. Mitigated by `models` live-resolution tags +
`dashboard` next-worker line; full per-pin health probing is future work.

**E9 — nondeterministic `--ensure`.** `cmd_ensure` printed nothing on the
STARTED path: the parent process called `daemonize()` (double fork) and
`os._exit(0)` before any output, and the daemon's stdio went to `/dev/null`.
Callers saw empty output and could not tell «started» from «failed». No
`--status` existed: liveness checking required tailing a 40 MB journal
manually; no supervision of the supervisor.

**E10 — shared account pool unmodelled.** `zai-coding-plan/glm-5.3-flash`
and `zai-coding-plan/glm-5.3` draw from ONE coding-plan quota; the fact
lived in prose inside health-memory reasons. `resolve_next_worker` treats
every pin as an independent quota, so a quota death of the pool could
«fail over» onto the same dead pool.

**E11 — static memory vs dynamic owner truth.** Owner declared GLM alive
while health-memory still held cooldowns (glm-5.3 9h52m, flash 1h25m);
recovery required knowing `mark-alive` by heart, per model. Doctrine had no
«owner word outranks memory» rule, and stale doctrine (GLM REMOVAL RULE)
actively contradicted the owner.

---

## 2. Root causes (structural)

**(a) Multiple sources of truth.** Four writers with four string
conventions vs readers keyed by pin strings (E3/E4); chain config read
live from a churned worktree with no HEAD comparison (E6); pool membership
prose-only (E10).

**(b) Automation depending on the blocked.** Detection/abort discipline
lived in orchestrator prompts, but a foreground Task blocks the very agent
that should react. The independent path (watchdog) existed but was silent
(E9), quota-blind (E2), and its GC never existed (E1).

**(c) No GC.** Registry is append-mostly; `stuck` amplified noise instead of
retiring verified-gone entries (E1).

**(d) Config pins without drift protection or pool model.** E6, E8, E10.

**(e) Silent interfaces.** Empty SUCCESS/STARTED outputs (E9), banners
nowhere, exit codes not distinguishing STUCK from ORPHAN (E1).

**(f) Stale doctrine.** A superseded removal rule in AGENTS.md supplied
cover for reverting owner decisions (E6/E11); protocol numbers drifted
across three files with the consistency test deleted.

---

## 3. Target state + implementation plan

Design principles derived from the breaks:
1. ONE health store, ONE matching rule (symmetric full/bare id), ONE writer
   shape (`record_dead`) for mark-dead / classify-error / migrate / watchdog.
2. Cooldowns can grow, never shrink; provider reset timestamps are ground
   truth (+20 min margin).
3. Readers (preflight/migrate/models/resolve) are *incapable* of returning
   a cooldown model; `--force` is the explicit human override.
4. Account pools are first-class: quota death is pool-wide, provider
   timeout is not.
5. Worker config drift vs HEAD is loud, on every model-deciding command.
6. GC is verified-only (`GET /session/{id}` 404), age-gated (>24h),
   safe under parallel orchestrators (idempotent state flip, fresh re-read
   before save, never retire on «unavailable»).
7. Every interface is loud: ALIVE/STARTED lines, `--status`, ORPHAN ≠
   STUCK, dashboard.

### Status

**[A выполнено] A1 — единый источник истины**
`session-reuse.py`: `health_entry()` (symmetric matching), `record_dead()`
(single writer, keep-longer, pool stamping), `cooldown_remaining()` includes
pool-wide blocks; `preflight`/`migrate` defensive re-verification +
`--force`; `models`/`health` read the same store.
Tests: `HealthStoreConsistencyTests` (bare-spelling blocks pin + preflight;
migrate skips + --force; reset-timestamp cooldown; never-shrink).

**[A выполнено] A2 — CONFIG-DRIFT gate**
`config_drift()`/`drift_banner()` compare `.opencode/model-fallback.json` +
`opencode.jsonc` worktree vs HEAD (modified/untracked), fail-open without
git; banner printed by `preflight`, `migrate`, `models`, `health`,
`dashboard`. Env `SR_DRIFT_REPO` isolates tests.
Tests: `ConfigDriftTests` (clean/modified/untracked; banner only on drift).

**[A выполнено] A3 — доктрина GLM CODING PLAN RESTORED**
AGENTS.md: «GLM REMOVAL RULE» replaced — flash = primary worker #1
(`build` pin, order 1), glm-5.3 reserved (worker=null, order 11), removal
forbidden without a NEW owner directive, owner word outranks health memory
(with the `mark-alive ... [--pool P]` procedure). Protocol refs synced to
v18 (worktree had been silently downgraded to 16/15).

**[A выполнено] A4 — DECISIONS.md** entries for E1–E11 and A1–A3 (this
commit).

**[B1 выполнено] Orphan GC** — `stuck --gc` → `gc_orphans()`: verified-404
+ >24h → retired with `gcReason`; parallel-safe (fresh re-read before save);
«unavailable» never retires; plain `stuck` downgrades registry-only rows to
`ORPHAN` (exit code driven by status-backed STUCK only); called
best-effort from watchdog `--ensure`. Tests: `OrphanGcTests`.

**[B2 выполнено] Watchdog loudness** — `--ensure` prints
`watchdog ALIVE (pid=…)` / `watchdog STARTED (…)` (printed before
daemonize — the E9 empty-output path); `--status` reports pid/uptime/
heartbeat-age/aborts with exits 0/1/2; deaf-daemon replacement already
existed (`daemon_healthy`) and stays. Tests: `WatchdogLoudnessTests`.

**[B3 выполнено] Pool schema** — `"pool": "zai-coding-plan"` on both GLM
chain entries; `pool_of/pool_members/pool_wide_remaining`; quota-class
verdicts (`MODEL_QUOTA`, `FREE_USAGE_EXHAUSTED`) record `poolWide` and
block siblings; `mark-alive --pool`; provider timeouts stay per-model.
Tests: `PoolTests`.

**[B4 выполнено] E2E chaos-тест** — `ChaosFailoverTests`: retry-stuck →
watchdog abort → cooldown (observed delay) → migrate (same task_id) →
second model dies under a *different spelling* → second migrate skips it →
preflight consistent. All against the in-process mock server, zero real
network. Plus `test_dashboard_smoke`.

**[B5 выполнено] Dashboard** — `session-reuse.py dashboard`: CONFIG-DRIFT,
watchdog pid/heartbeat/aborts, model health with pools, next-worker,
session/orphan census. Verified against the live runtime during
development (watchdog RUNNING, 4 cooling models, 176 orphan candidates).

**[C — требует рестарта сервера opencode]** (agent files are read at
server start, no hot-reload — AGENTS.md §14.6):
1. Restart `opencode serve` / desktop app so the updated
   `.opencode/agents/orchestrator.md` (v18 checks, GLM primary wording)
   reaches the running orchestrator.
2. Re-issue the running orchestrator loop from a fresh session so it
   picks up AGENTS.md v18 protocol numbers.
3. Live-run `stuck --gc` against production (it already ran once via
   `--ensure` during B2 testing; re-run to drain the backlog) and
   `dashboard` for the first real census.
4. `ling-3.0-flash-fin` pin (E8): decide keep/demote on the next chain
   review — code-neutral, but it changes `opencode.jsonc` pins which only
   a restarted server honors.

### Residual known gaps (explicitly not hidden)

- E5 (cancelled Task loses task_id) — platform limitation; mitigation is
  registry bookkeeping + live discovery, unchanged by design.
- E7 (parallel churn actor) — outside the failover plane; the drift gate
  protects only the two worker-config files. Watch `git diff` on
  orchestration files before each Task (banner now reminds).
- Per-pin continuous liveness probing (E8 tail) — not implemented;
  `models --all` live-resolution + dashboard next-worker are the visible
  checks today.
- Watchdog still trusts /session/status + stalled-shape heuristics for
  abort decisions; a provider that fails with neither shape remains a
  Task-return-only event (E2's channel), now at least auto-classified
  with an exact reset cooldown when the text carries a timestamp.

### Test evidence

`python3 scripts/test-session-reuse.py` → **95 tests, OK** (was 71 with 3
failures). The 3 pre-existing failures were stale expectations (`build-b`
as first fallback) from before the GLM chain restoration — fixed to derive
the expected fallback from the chain instead of hardcoding; noted per the
mandate. The `ProtocolVersionConsistency` test (deleted from the worktree
during the churn) is restored and green with v18 everywhere.
