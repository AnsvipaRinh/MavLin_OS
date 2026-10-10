# Qwen Web Worker — orchestrator protocol

How the OpenCode Orchestrator (or any Build worker) drives Qwen Code
(coder.qwen.ai) as an executing worker and interprets its feedback.

## Sub-agent integration

The orchestrator invokes the dedicated hidden subagent `qwen`
(`.opencode/agents/qwen.md`, allowed in the orchestrator's task list):
it relays objectives verbatim through this CLI, reads the JSON
feedback, and applies Qwen-produced code to THIS repo locally (Qwen's
sandbox is remote). Note: running OpenCode servers do not hot-reload
agents — the `qwen` subagent appears after the next server/session
start with cwd=repo (see AGENTS.md 14.6).

## Architecture

```
Orchestrator
  → scripts/qwen-integration/qwen-web-worker.py <mode> --json
    → INVISIBLE headless Chromium (persistent profile ~/.config/mavlinos/qwen-chromium-profile)
      → coder.qwen.ai (authenticated session)
        → POST /coder/api/v2/task/completions  (SSE, network-level capture)
        → GET  /coder/api/v2/task/{chat_id}    (authoritative completion+artifacts)
  ← JSON: {ok, completed, chat_id, response, files, commit_id, model}
```

- NO visible browser window, ever (enforced invariant since
  2026-10-07: `headless=new` on every launch, host DISPLAY /
  WAYLAND_DISPLAY scrubbed from the browser environment, pinned
  Xvfb virtual framebuffer as the only display fallback; any path
  that would open a visible window fails loudly instead). The
  `auth` mode is DISABLED — the persistent profile is established
  and migrated automatically and restored from the auth snapshot.
- Responses are extracted at the NETWORK level (SSE stream + REST task
  object). No DOM scraping.
- IMPORTANT: Qwen Code executes in Qwen's OWN cloud sandbox. `files`
  and `commit_id` refer to that sandbox, not to this repository. To
  apply Qwen's work here, a local Build worker must take the returned
  `response` (which contains the code/patch text) and apply it to the
  repo itself.

## Commands (machine interface — always pass --json)

### check — auth state gate
```
python3 scripts/qwen-integration/qwen-web-worker.py check --json
→ {"mode":"check","authenticated":true,"state":"authenticated"}
→ {"mode":"check","authenticated":false,"state":"needs_auth"}
```
Run `check` before delegating work. On `needs_auth` → the login
is lost AND unrecoverable from the snapshot: REPORT that to the
repository owner (the worker never opens a visible browser and
cannot log in itself). Do NOT loop retries.

### send — objective → answer
```
python3 scripts/qwen-integration/qwen-web-worker.py send --json \
  --timeout 600 \
  [--repo AnsvipaRinh/MavLin_OS] [--chat <chat_id>] \
  --prompt "<objective text, verbatim>"
→ {"mode":"send","ok":true,"completed":true,"chat_id":"<uuid>",
   "response":"<final answer text>",
   "repo":"MavLinOS",
   "files":["src/main.py"],"commit_id":"<sha>","model":"qwen3-coder-plus"}
```
`send` internally performs start → (optional repo/chat selection) →
submit → wait-for-completion, then closes the browser cleanly. Typical
latency: ~30s first answer in a conversation (environment init), ~10s
followups.

Options:
- `--repo <owner/name | name>` — select the connected GitHub repository
  for the task BEFORE submitting (clicks it in the `.repo-selector`
  panel and verifies the selector). WITHOUT a selected repository Qwen
  works in a blank sandbox and answers are useless for repo-bound
  objectives — always pass --repo for work on a real codebase. The
  repo must be connected to the Qwen account (it appears under
  "Recent repositories" in the selector). Verified live: with
  `--repo AnsvipaRinh/MavLin_OS` the model itself answered
  "AnsvipaRinh/MavLin_OS" when asked which repo it is connected to.
  NOTE: the app keeps ONE persistent workspace conversation per repo
  ("Repository Working Environment") — repo-bound prompts append there
  (context accumulates across sends; check chat_id in the response to
  know where the work landed).
- `--chat <chat_id>` — continue that exact conversation. Omit to start
  a fresh one (clean context per objective).

### status — local metadata (no browser)
```
→ {"mode":"status","chat_id":null,"profile_path":"...","auth_backup_present":true}
```

## Feedback semantics

| field       | meaning                                                        |
|-------------|----------------------------------------------------------------|
| ok          | an answer text was received                                    |
| completed   | Qwen itself marked the answer phase finished (not a timeout)   |
| chat_id     | conversation id — pass context via followups in the same chat  |
| response    | the final user-facing answer (draft/reasoning/log excluded)    |
| repo        | the repository label active for the task (None = blank sandbox)|
| files       | files Qwen created/changed IN ITS SANDBOX                      |
| commit_id   | sandbox commit of Qwen's work                                  |
| model       | the model that produced the answer                             |

Failure states:
- `ok:false, completed:false` + stderr "needs_auth" → session lost AND
  snapshot restore failed/absent → REPORT the login loss to the
  repository owner (auth mode is disabled; the worker never opens a
  visible browser and never attempts a login).
- stderr "Profile is already in use" → another browser holds the
  profile; close it, retry once. Never start a second browser anyway
  (the worker refuses by design — concurrent browsers corrupt the
  session; see Session-loss protection below).
- timeout (`ok:false` after --timeout) → check status; the conversation
  may still complete server-side; re-poll by sending a followup in the
  same chat instead of re-submitting the whole objective.

## Prompting rules (transport transparency)

The transport layer MUST NOT rewrite or embellish objectives. Pass the
user's objective verbatim. For ambiguous/short objectives, do not
invent a project — ask Qwen for clarification IN the same conversation
(a followup), just like a human would.

Deterministic transport test (use for health checks, NOT for coding
ability):
```
Reply with exactly the single string QWEN_TRANSPORT_TEST_7F3A. Do not
create files. Do not browse. Do not perform any other action. Do not
explain anything.
```

## Conversation continuity

Followups continue the SAME conversation automatically when sent from
the same worker process, and across restarts the app reopens the last
conversation (verified live). For an explicit new conversation, start a
fresh `send` after navigating the worker away (or simply accept the
default continuation — chat_id in the response tells you where you
are).

## Session-loss protection (why the profile survives restarts)

Root cause fixed on 2026-10-05: concurrent Chromium instances on one
profile + hard process kills corrupted localStorage and destroyed a
valid session. Root cause fixed on 2026-10-07: the profile lived
under /tmp (tmpfs), so every reboot wiped the login — it now lives
on persistent storage. Protections now in place:
1. Persistent profile at `~/.config/mavlinos/qwen-chromium-profile`;
   a volatile (/tmp) profile is migrated automatically (by COPY —
   the source is never deleted) with metadata repointed at the
   persistent copy.
2. SingletonLock liveness check — the worker refuses to share a profile
   with a running browser.
3. Clean browser close in every code path (Chromium flushes storage
   only on orderly shutdown).
4. Auth snapshot at `~/.config/mavlinos/qwen-auth-backup` after every
   verified session; automatic restore when the live profile loses its
   token or when the profile directory itself is missing (no user
   re-login needed for recoverable cases).

## Login loss reporting (visible auth mode DISABLED)

The `auth` mode is permanently disabled (2026-10-07): this worker
NEVER opens a visible browser window — `auth` fails loudly with
exit code 2 instead. The login is established on persistent storage
and survives reboots; if it is ever lost, the worker restores the
auth snapshot automatically, and if that fails too, the loss must
be REPORTED to the repository owner. Do not attempt an interactive
login from this worker.

## Tests

- Offline (no auth needed): `python3 -m pytest scripts/qwen-integration/test_qwen_web_worker.py -v`
  — 15 tests: REAL captured stream samples (parser, completion
  semantics, artifact collection, same-chat followup) + invisibility
  and persistence invariants (launch choke point rejects visible
  launches, host display scrubbed from the browser environment,
  volatile-path detection, profile migration copies-never-deletes,
  auth mode fails loudly without a browser).
- Live acceptance (needs authenticated profile):
  `python3 scripts/qwen-integration/test_qwen_live.py` — tests A–D
  (headless startup, deterministic request, same-conversation followup,
  restart without re-auth). 8/8 passed on 2026-10-05.
