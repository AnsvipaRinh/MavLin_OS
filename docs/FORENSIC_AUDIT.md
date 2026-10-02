# FORENSIC_AUDIT.md — Independent Forensic Audit of Publication Readiness

**Date:** 2026-10-03
**Auditor:** new session (post chat-transfer), acting as independent verifier
**Trigger:** context recovery between chats. The previous agent's final
report was provided by the user as **claims, not facts**. This audit
re-verified every publication-relevant claim against the repository
itself, optimized for **finding problems**, not for publication polish.
**Constraints honored:** no GitHub auth, no remote, no push, no history
rewrite, no branch rename (all deferred to the publication step).

**Method:**

- Git metadata: full author/committer enumeration across all 329 commits
- Content sweep: all **1898 unique reachable blobs** (31.5 MB) dumped and
  scanned: credential patterns, high-entropy strings, emails, PII
  (phones/addresses/cards), absolute paths, personal names
- **Unreachable objects** included: `git fsck --unreachable` → 3 blobs
  + 7 commits (stash/index WIP) — dumped and swept separately
- Claim re-execution: check-sync, check-profile-sync, security-scan/triage
  fixtures, py_compile, bash -n, sim harness, full `test-mv-*.py` suite
- Size/count recomputation: `.git` size, tracked content size, tracked
  file count at parent vs HEAD, check-line counts, CI job enumeration

---

## 1. Previous agent's claims — verdicts

| # | Claim (from final report) | Verdict | Evidence |
|---|---------------------------|---------|----------|
| 1 | "audit 1112 tracked files" | **PARTLY FALSE — stale** | Parent commit `939c8ad` = 1112 files; publication commit `b27af3d` added 28 of its own files → **1140**. The count was taken at audit start; the 28 added files were never covered by the "complete inventory" claim (see §3) |
| 2 | "public/private boundary проверен" | **OVERCLAIM** | Worktree functional paths ARE sanitized. But history retains personal identity (F1, F2) and 204 `/home/builder` occurrences in old blobs (F3) — all public after push. The boundary was *sanitized in the worktree*, not *verified clean in history* |
| 3 | "`/home/builder` paths sanitized" | **TRUE for worktree; silent about history** | 0 functional occurrences in worktree (9 audit-doc mentions remain, which describe the sanitization). History: 204 line-occurrences in 136 unique blobs across 10 files' old revisions |
| 4 | "secret sweep across history CLEAN" | **TRUE — independently confirmed** | 1898 reachable + 3 unreachable blobs swept: 0 credentials/tokens/keys. All keyword hits are legitimate code/docs (password generators, libsecret mocks, sshd hardening notes). High-entropy sweep: only hashes (ISO sha256) and test strings |
| 5 | "generic/macbook10,1 separation исправлено" | **TRUE** | check-profile-sync: OK; check-sync: 142 OK / 0 FAIL |
| 6 | "contribution pipeline реализован" | **TRUE** | `scripts/contrib/{discover,fetch-pr,security-scan,triage}.sh`, `lab/tests/contrib/` (2 suites + 5 fixture PRs), both suites 5/5 — re-executed this session |
| 7 | "security scan 5/5; triage 5/5" | **TRUE — re-executed** | `python3 lab/tests/contrib/test_security_scan.py` → 5/5; `test_triage.py` → 5/5 |
| 8 | "check-sync/profile-sync проходят" | **TRUE, but count claims stale** | check-sync emits **142 OK lines** (not "221"/"227" as README/PROGRESS state — those figures predate script evolution). check-profile-sync OK |
| 9 | "commit b27af3d" | **TRUE** | HEAD = `b27af3d`, tree clean, single branch `master`, **no remotes**, no tags |
| 10 | "остаются только Git author identity и GitHub authentication" | **FALSE — incomplete** | At least F5 (Apple-derived assets), F6 (CI exit-code swallowing), F10 (build-host fingerprint) were unresolved and unreported |

## 2. The flagged contradiction — resolved

> "предыдущий агент заявил, что история/публичная граница чистая, но обнаружено 1707 исторических `/home/builder` и реальные имя/email"

Reconciliation (both numbers are real, different methodologies):

- **1707** = `git grep` per-commit matches across all 329 commits — the
  same blob counted once per commit that contains it. Inflated by design.
- **Actual unique-content scope:** 204 line-occurrences in **136 unique
  blobs**, mapping to **10 file paths** (old revisions of
  `archiso-profile/releng/pacman.conf`, `docs/{DECISIONS,ENVIRONMENT,
  HANDOFF,PROFILE_COUPLING,PROGRESS,PUBLIC_AUDIT,RELEASE_READINESS}.md`,
  `packages/mavericks-apps/.../tests/test_mv_launchpad.py`,
  `scripts/test-session-reuse.py`).
- **Real identity in history:** 4 commits (author=committer) under the
  original author's personal name + personal email — including the **root
  commit** `82386e5` — plus 17 occurrences of the dotless personal email
  inside old doc-blob *content* (the email has no dot-TLD, so generic
  email regexes miss it; targeted grep found it).
- **Why the previous audit said "clean":** its secret scan looked for
  credentials (correctly found none), and its boundary sanitization
  targeted the *working tree*. History-level identity/path exposure was
  listed as "USER DECISION / INVESTIGATE" in PUBLIC_AUDIT.md §3.2–3.3 —
  so it was *disclosed but unresolved*, while RELEASE_READINESS.md's
  headline said "READY FOR PUBLICATION". The overclaim is one of emphasis,
  not concealment — but a reader of the headline alone would be misled.

## 3. Root cause: 1112 vs 1140 tracked files

- `git ls-tree -r 939c8ad` (parent of HEAD) = **1112** files — exactly
  the number in the report.
- `git diff --name-status 939c8ad b27af3d` = **28 added, 14 modified,
  0 deleted** → 1140 at HEAD.
- The 28 added files are the publication pipeline itself: `LICENSE`,
  `CODE_OF_CONDUCT.md`, `docs/{CONTRIBUTION_PROTOCOL,SECURITY_MODEL,
  RELEASE_READINESS}.md`, `scripts/contrib/*.sh` (4),
  `lab/tests/contrib/*` (2 suites + 13 fixtures).
- **Conclusion:** the report was drafted mid-session before its own
  commit's additions landed. The "complete file inventory reviewed ✅"
  claim was computed on the pre-commit state and never updated. Other
  figures from the same session are likewise stale: `.git` 7.9M → actual
  **5.4M**; working tree "~10M" → tracked content **6.2M** (2.8G with
  the gitignored ISO in `out/`, built later); "221/227 checks" → **142**
  actual check lines. **Lesson: every count in an audit report is only
  valid for the exact commit it was measured at.**

## 4. Findings (problem-first, as instructed)

### F1 — Personal identity in commit metadata (4 commits, incl. root) — USER DECISION TAKEN, execution deferred

- Commits: `82386e5` (root, "init project skeleton"), `020723d`,
  `87f5122`, `a1f13a6`. Author **and** committer carry the personal
  name + personal email. The other 325 commits carry the temporary local
  alias `Mavericks Linux Agent <agent@mavericks-linux.local>`.
- **Scope consequence:** the affected set includes the root commit, so a
  mailmap rewrite changes **all 329 commit IDs**, not 4. Documented in
  RELEASE_READINESS.md §3.1; user chose option (b) with target identity
  `Ansvipa_Rinh <ID+Ansvipa_Rinh@users.noreply.github.com>`; the numeric
  GitHub ID must come from the authenticated profile (must not be
  fabricated) — hence execution is a publication step.

### F2 — Personal identity in file content (17 historical + 13 current lines) — FIXED in worktree; history via §3.1 step 2

- Current docs (sanitized this session, audit facts preserved):
  `docs/DECISIONS.md` (2), `docs/ENVIRONMENT.md` (1),
  `docs/PUBLIC_AUDIT.md` (6), `docs/RELEASE_READINESS.md` (2).
- History: 17 occurrences of the personal email in old versions of
  DECISIONS/ENVIRONMENT/PUBLIC_AUDIT/RELEASE_READINESS blobs. Removed
  only by `git filter-repo --replace-text` in the publication procedure.

### F3 — `/home/builder` in history (204 occurrences / 136 blobs / 10 files) — disclosed; content-level cleanup is part of §3.1

- Low sensitivity (build username + local paths), but factually
  contradicts "history clean" after push. Worktree is functionally clean.

### F4 — Stale audit figures in publication docs — FIXED this session

- See §3. Corrected in RELEASE_READINESS.md, README.md (2 spots),
  PROGRESS.md (OS-GH entry). Dated historical PROGRESS entries were left
  intact (they are point-in-time records; rewriting them would falsify
  the log).

### F5 — Apple-derived assets tracked for publication — **REQUIRES USER DECISION (D1)**

- `docs/isolated-assets/apple-derived/` holds 3 SVGs
  (`help-about.svg`, `preferences-desktop-display.svg`,
  `preferences-desktop-mouse.svg`) containing explicit Apple logo vector
  paths and "Mac OS X 10.9 Mavericks" text. `docs/LICENSES.md` §6 marks
  all three **NON-redistributable** ("ISOLATE").
- The isolation procedure (LICENSES.md §8) moved them out of the
  *installed* theme — which prevents installation but **not
  redistribution**. In a public repository they would be published, and
  they also exist in history inside the theme tree (pre-isolation
  commits). This conflicts with the project's own legal rule (AGENTS.md
  §5: no copying Apple proprietary assets).
- Options (documented in RELEASE_READINESS.md §3.3-D1): (i) remove from
  tree + history before push, replaced by a provenance note —
  **recommended** (the theme already ships replacement generics since
  `522ab98`); (ii) keep with documented license rationale (legal risk);
  (iii) move to a private repository.

### F6 — CI job swallowed check-sync exit code — FIXED this session

- `.github/workflows/ci.yml` unit-tests job ran
  `./scripts/check-sync.sh 2>&1 | grep -A5 "firefox chrome css" || true`:
  the pipeline's exit status is grep's (1 when no match), and `|| true`
  masked even that — check-sync could never fail the job. The step was
  also redundant: the static-analysis job already runs check-sync fully.
  Removed; a comment marks why.

### F7 — CI verification gaps (not bugs; unproven until first run)

- The secret-scan job's gitleaks path is inert on stock GitHub runners
  (gitleaks not preinstalled) → the regex fallback runs; it was never
  executed against the repo's own fixtures (e.g., keychain test mocks
  use `secret=b"..."`, which the fallback's quote-anchored pattern does
  not match — likely no false positive, but unproven).
- The unit-tests job runs pytest, which collects only the pytest-style
  subset (e.g., 2 of ~140 checks in `test-mv-calculator.py`); the full
  inline suites execute only when scripts run directly. Wiring all
  `test-mv-*.py` into CI was **not** done blindly because
  `test-mv-photos.py` has 2 known pre-existing headless failures
  ("rotate graceful no backend", "open editor graceful no gthumb" —
  documented in PROGRESS.md 2026-09-30 as host artifacts, not a
  regression; re-confirmed this session).
- **First real GitHub Actions run: REQUIRES EXTERNAL EVIDENCE.**

### F8 — Unreachable objects (local-only; clean) — no action

- `git fsck --unreachable`: 3 blobs (superseded test-file versions),
  7 stash/index WIP commits — all authored by the temporary agent
  identity, all content-clean. Never transferred by `git push` (push
  sends reachable objects only). Noted for completeness of the forensic
  record.

### F9 — `builder` username in docs — classified, kept deliberately

- `builder` is the build-container user (13 files mention it, always as
  the functional build user, e.g. sudoers notes in ENVIRONMENT.md). It is
  not a personal name and is functionally necessary to describe the build
  environment. Classification: **functional, low-sensitivity, keep**.
  The personal local account (`vsevolod`) was the sensitive one and is
  sanitized (F2).

### F10 — Build-host hardware fingerprint in tracked benchmark data — FIXED conservatively (user may override, D2)

- 14 tracked `docs/benchmarks/*.json` recorded the build host verbatim:
  `/host/cpu_model = "AMD Ryzen 7 5800HS with Radeon Graphics"`,
  `/host/container = "WSL2"`, WSL kernel signature
  (`6.18.33.2-microsoft-standard-WSL2`), plus one prose "5800HS-relative"
  note. The previous audit was **self-contradictory** on these files
  (PUBLIC_AUDIT.md §3.2: "PRIVATE-KEEP-LOCAL" vs §3.4: "kept tracked").
- A hardware model + platform string is a fingerprint of the maintainer's
  machine. This session: replaced with `<build-host-cpu>` /
  `<build-host-platform>` placeholders; **all measurement numbers and
  notes preserved**; JSON validity re-verified for all 14 files. If the
  user considers CPU model non-personal, originals are recoverable from
  history.

## 5. Identity-mention classification (per user's 4-question framework)

| Location (original) | Refers to user? | Needed for reproducibility? | Replaceable w/o false info? | Disposition |
|---|---|---|---|---|
| DECISIONS.md auth-inventory (Windows profile name) | Yes | No (the provider-presence constraint is the functional part) | Yes → "Windows profile of the project author" | **Sanitized** |
| DECISIONS.md history-identity decision entry | Yes | No (decision + scope are the facts) | Yes → "the original author's personal identity (redacted)" | **Sanitized + decision recorded** |
| ENVIRONMENT.md sudoers trap note (`vsevolod` user) | Yes (personal local account) | No (the last-match-wins lesson is the fact) | Yes → `<build-user-2>` | **Sanitized** |
| PUBLIC_AUDIT.md §1.9/§3.2/§3.3 (author listing, verdicts, mailmap example) | Yes | No | Yes → `<original-author-name> <original-author-email>` | **Sanitized; verdicts updated to the user's actual decision** |
| RELEASE_READINESS.md §3.1 (identity + mailmap example) | Yes | No | Yes → placeholders + target identity | **Sanitized; procedure rewritten to user's decision** |
| Commit metadata (4 commits) | Yes | No | Yes (mailmap) | **Deferred to publication step (needs GitHub numeric ID)** |
| Old doc-blob content (17 email occurrences) | Yes | No | Yes (`--replace-text`) | **Deferred to publication step** |
| `builder` username (13 files) | Indirectly (build container account) | **Yes** — build env is functionally described | Placeholders would reduce clarity | **Kept (F9)** |
| Benchmark host strings (14 JSONs) | Indirectly (machine fingerprint) | Partially (host context matters for interpreting numbers, but exact model is not required) | Yes → `<build-host-cpu>`/`<build-host-platform>` | **Sanitized (D2, overridable)** |

## 6. `.opencode/` security/privacy audit (user-requested)

Tracked (public by user decision): `agents/orchestrator.md` (299 lines),
`model-fallback.json`.

- **Credentials/API keys/tokens: NONE.** No `OPENROUTER_API_KEY` values,
  no bearer tokens, no secrets. Auth is external (env var / `/connect`).
- **Session data: NONE tracked.** `.opencode/sessions/`
  (registry.json 57 KB, watchdog.log 5.3 MB, model-health.json,
  watchdog.lock) is gitignored and stays local — verified in
  `git status --ignored`.
- **Absolute local paths: NONE** in tracked files.
- **Account/quota details: none quantitative.** Two benign qualitative
  mentions, flagged for awareness: model-fallback.json records a
  "quota event 2026-09-26 handled via cooldown memory" (no numbers, no
  account info) and user preference statements ("User 2026-09-26: Muse
  Spark is NOT an allowed worker"). DECISIONS.md records provider
  *presence* per profile (openrouter/google/groq/opencode) — presence
  only, no keys.
- **Local-only (never pushed):** `~/.local/share/opencode/auth.json`
  (credentials — exists locally, not tracked), global
  `~/.config/opencode/opencode.jsonc` (28 lines, differs from the repo
  copy — local agent config), `.opencode/node_modules/`,
  `.opencode/package*.json`, `.opencode/.gitignore`.
- **Verdict: clean for publication** per the user's keep-public decision.

## 7. NOT PROVEN / REQUIRES EXTERNAL EVIDENCE

| Item | Why it cannot be proven here |
|---|---|
| ISO build reproducibility | `mkarchiso` exists in this env but a full rebuild needs hours + root; last proven 2026-09-29 (sha256 in PROGRESS.md) |
| QEMU+OVMF boot | Last container attempt BLOCKED at boot menu (no KVM / UEFI CD emulation — documented in PROGRESS.md); README's "25/25" refers to the sim harness, which **was** verified (110 assertions) |
| First GitHub Actions run | CI never executed on real runners (F7) |
| Real-hardware behavior | Entire NEEDS_HARDWARE_TEST.md (Wi-Fi/audio/applespi/S3X/HiDPI/thermal/power) |
| "221/227 checks" historical figures | Superseded — current check-sync emits 142 OK lines; earlier counts are point-in-time records |
| gitleaks-based secret scan in CI | gitleaks not installed on stock runners; regex fallback unproven against own fixtures |

## 8. What was changed this session (software-side fixes only)

1. Sanitized personal name/email from 4 current docs → neutral
   placeholders; audit facts and decision records preserved (F2, §5).
2. Corrected stale figures: 1112→1140 (with root-cause note),
   `.git` 7.9M→5.4M, "~10M"→6.2M tracked, 221/227→142 (F4).
3. Redacted build-host fingerprint from 14 benchmark JSONs (F10/D2).
4. Removed the exit-code-swallowing CI step (F6).
5. Rewrote RELEASE_READINESS.md §3 into the actual publication
   procedure (mailmap + replace-text + branch rename + push, with the
   ID-pending warning) and recorded open decisions D1–D3.
6. Updated DECISIONS.md entry 7 to the user's taken decision (option b,
   expanded scope, root-commit consequence).
7. Added this report; updated PROGRESS.md (OS-FORENSIC section).

**Not done (by explicit instruction):** history rewrite, branch rename,
remote add, GitHub auth, push, Apple-asset removal (D1 awaits user),
`agent@mavericks-linux.local` is NOT used as the public identity — the
publication procedure remaps it to the `Ansvipa_Rinh` identity.

## 9. Residual risk register (before first push)

1. D1 Apple-derived SVGs — user decision (recommended: remove +
   provenance note, also via history rewrite).
2. Publication procedure §3.1 — needs authenticated GitHub numeric ID;
   changes all 329 commit IDs; run only on a backed-up copy.
3. First CI run may surface fixture/environment issues (F7).
4. ISO rebuild + QEMU boot — re-verify on an Arch host with root.
