# LIVE ACCEPTANCE: same-session model failover (protocol v5)

Goal: prove on the LIVE server that MODEL FAILURE ≠ SESSION FAILURE —
`Task(task_id=S, subagent_type=<other worker>)` continues S with history
intact. Run in the user environment (needs OpenCode server + providers).
Cheap models only; no large contexts; do NOT provoke a real 7000s retry.

Conventions: `<oid>` = test objective id, e.g. `probe-a`. Every step prints
its verdict; stop at the first FAIL and paste the output.

## Test A — same session, same worker

1. Fresh Task `build`: prompt «Reply with the single token PROBE-ALPHA and stop.»
2. Note returned `task_id` → S1. `register S1 --agent build --objective "probe" --task "alpha" --model <m> --oid probe-a`.
3. Task `build`, `task_id=S1`, prompt «Продолжай: repeat the token from your previous reply, then reply PROBE-BETA.»
4. **PASS:** reply contains PROBE-ALPHA (history visible) + result returns SAME S1.

## Test B — same session, different worker (core requirement)

1. `migrate S1 --objective "probe" --delay 60` → prints `subagent_type=build-b` (or build-c) + `task_id=S1`.
2. Task printed `subagent_type`, `task_id=S1`, prompt = printed continue text.
3. **PASS:** reply references PROBE-ALPHA/BETA (history survived the model switch) + session id still S1. `register S1 --agent build-b ...` (same id, new backend).

## Test C — Objective isolation

1. Fresh Task `build` for objective `probe-c2` (token PROBE-GAMMA) → S2, `--oid probe-b`.
2. `find-objective probe-a` → must print ONLY S1; `find-objective probe-b` → ONLY S2.
3. **PASS:** Continue A never resolves S2 (exact-oid match, no cross-talk).

## Test D — duplicate prevention

1. Stop the server network briefly OR call `decide <id>` with a wrong port (simulated unreachable).
2. **PASS:** verdict UNKNOWN/VERIFY, never NEW; no second session created for the same oid.

## Test E — failure classification

1. `classify-error` on samples: "429 rate limit" → MODEL_RATE_LIMIT(11); "socket hang up" → NETWORK_ERROR(15); "generation timed out" → MODEL_TIMEOUT(13); "no such session" → SESSION_ERROR(16); "test failed" → PROJECT_ERROR(20).
2. **PASS:** distinct verdicts; MODEL_* with `--record-model` writes cooldown (`health` shows it); NETWORK/PROJECT write nothing.

## Test F — stale session

1. `decide <dead-id> --objective <anything>` and `find-objective <ghost-oid>`.
2. **PASS:** SESSION_UNAVAILABLE (structured, exit 0/2), no traceback, no duplicate session.

## After live PASS

Record results + date in `docs/DECISIONS.md` (which tests, which workers/models).
The offline suite `scripts/test-session-reuse.py` (22 checks, mock server)
covers the same logic offline and must stay green.
