# FORENSIC_AUDIT.md — Independent Forensic Audit of Publication Readiness

**Date:** 2026-10-03
**Auditor:** new session (post chat-transfer), acting as independent verifier
**Trigger:** context recovery between chats. The previous agent's final
report was provided by the user as **claims, not facts**. This audit
re-verified every publication-relevant claim against the repository
itself, optimized for **finding problems**, not for publication polish.
**Constraints honored:** no GitHub auth, no remote, no push. No
history rewrite was executed on this repository — the rewrite
procedure was implemented as tooling and verified by dry-run on
throwaway clones only (§10). Branch renamed `master` → `main`
locally (decision D3).

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
| 9 | "commit b27af3d" | **TRUE** (stale SHA) | At audit time: HEAD = `b27af3d`, tree clean, single branch, **no remotes**, no tags. Since then the branch was renamed `master` → `main` (D3) and further commits landed — HEAD moves; the no-remotes/no-tags invariants still hold |
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

### F1 — Personal identity in commit metadata (4 commits, incl. root) — DECISION TAKEN; procedure VERIFIED (§10); only numeric ID pending

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
- **Dry-run verification (2026-10-03):** the full 4-pass procedure
  executed on a throwaway clone with a TEST identity passes all
  9 verification gates — see §10. Only the numeric GitHub ID
  remains pending.

### F2 — Personal identity in file content (17 historical + 13 current lines) — FIXED in worktree; history removal verified by dry-run (§10)

- Current docs (sanitized this session, audit facts preserved):
  `docs/DECISIONS.md` (2), `docs/ENVIRONMENT.md` (1),
  `docs/PUBLIC_AUDIT.md` (6), `docs/RELEASE_READINESS.md` (2).
- History: 17 occurrences of the personal email in old versions of
  DECISIONS/ENVIRONMENT/PUBLIC_AUDIT/RELEASE_READINESS blobs. Removed
  only by `git filter-repo --replace-text` in the publication procedure.

### F3 — `/home/builder` in history (204 occurrences / 136 blobs / 10 files) — disclosed; content-level cleanup is part of §3.1

- Low sensitivity (build username + local paths), but factually
  contradicts "history clean" after push. Worktree is functionally clean.
- **Publication purge (added 2026-10-03):** the rewrite now also
  neutralizes these — rule `/home/builder==><build-host>` (plus two
  single occurrences in superseded drafts: `/home/mavericks-lab` →
  `<target-host>`, `/home/custompkgs` → `<build-host>`). Verified
  absent from the rewritten history by a dedicated gate (§10).

### F4 — Stale audit figures in publication docs — FIXED this session

- See §3. Corrected in RELEASE_READINESS.md, README.md (2 spots),
  PROGRESS.md (OS-GH entry). Dated historical PROGRESS entries were left
  intact (they are point-in-time records; rewriting them would falsify
  the log).

### F5 — Apple-derived assets tracked for publication — **RESOLVED (D1: user chose option i — not published; executed 2026-10-03)**

- `docs/isolated-assets/apple-derived/` held 3 SVGs
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
- **Resolution (user decision 2026-10-03, option i):**
  (1) removed from the tree (`git rm docs/isolated-assets/apple-derived/`)
  and replaced by a provenance note (`docs/isolated-assets/README.md`);
  (2) `docs/LICENSES.md` §4/§6/§8/§9/§10 and `docs/DECISIONS.md`
  entry OS-4a updated to record the decision; (3) the archived
  originals are removed from ALL history by the publication rewrite
  (pass 3: `--invert-paths` on the directory; pass 4:
  `--strip-blobs-with-id` on the 30 pre-`522ab98` Apple-derived blob
  versions — IDs in
  `scripts/contrib/publication-rewrite/03-apple-derived-blob-ids.txt`,
  each independently proven to be an Apple-derived pre-replacement
  version). The theme ships generic replacements since `522ab98`, and
  the current tree's SVGs were diffed against the Apple originals to
  confirm zero Apple strings. Verified by dry-run gates 4–5 (§10).

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
| Commit metadata (4 commits) | Yes | No | Yes (mailmap) | **Procedure verified by dry-run (§10); execution pending the numeric GitHub ID** |
| Old doc-blob content (17 email occurrences) | Yes | No | Yes (`--replace-text`) | **Procedure verified by dry-run (§10)** |
| `builder` username (13 files) | Indirectly (build container account) | **Yes** — build env is functionally described | Placeholders would reduce clarity | **Kept (F9)** |
| `/home/builder` in 136 historical blob versions | Indirectly (build-container paths) | No (worktree is functionally clean without them) | Yes → `<build-host>` | **Purged by the publication rewrite — verified (§10)** |
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
8. **Continuation session (publication prep):** executed D1
   (Apple-asset removal + provenance note); completed the full
   public-identity/naming audit — project renamed to **MavLinOS**
   across README, CONTRIBUTING, templates, GITHUB_SETUP,
   project-meta.json, PKGBUILDs (url + maintainer line), boot
   entries, firstboot scripts, config headers (both sides of the
   sync pair), uBlock backup, orchestrator/agent docs; repo URL
   `github.com/Ansvipa_Rinh/MavLinOS`; internal package/ISO
   identifiers (`mavericks-*`) deliberately unchanged; renamed
   branch `master` → `main`; implemented the publication rewrite
   as tooling (`scripts/contrib/publication-rewrite/`) and
   verified it by dry-run — §10.

**Not done (by explicit instruction):** history rewrite, branch rename,
remote add, GitHub auth, push, Apple-asset removal (D1 awaits user),
`agent@mavericks-linux.local` is NOT used as the public identity — the
publication procedure remaps it to the `Ansvipa_Rinh` identity.

## 9. Residual risk register (before first push)

1. D1 Apple-derived SVGs — **RESOLVED** (removed from tree + all
   history; provenance note; §10).
2. Publication procedure §3.1 — **VERIFIED by dry-run (§10)**;
   execution needs the numeric GitHub ID from the authenticated
   profile (must not be fabricated); changes all commit IDs; run
   only on a backed-up copy.
3. First CI run may surface fixture/environment issues (F7).
4. ISO rebuild + QEMU boot — re-verify on an Arch host with root.

## 10. Publication rewrite — verified dry-run evidence (2026-10-03)

The publication procedure (RELEASE_READINESS.md §3.1) was
implemented as reproducible tooling
(`scripts/contrib/publication-rewrite/`) and verified end-to-end
on a throwaway clone with a **TEST identity**
(`TEST+Ansvipa_Rinh@users.noreply.github.com` — deliberately not
a real GitHub address). The dry-run is repeatable:

```bash
./scripts/contrib/publication-rewrite/publication-rewrite.sh \
  "<numeric-id>+Ansvipa_Rinh@users.noreply.github.com"
```

**Procedure (4 filter-repo passes on a fresh clone):**

1. `--mailmap` — both source identities (the personal identity
   on 4 commits incl. the root, and the local agent alias on
   325 commits) → the public identity.
2. `--replace-text` — 6 literal rules (`02-replace-text.txt`):
   personal name, personal email, bare personal username,
   `/home/builder`, `/home/mavericks-lab`, `/home/custompkgs`
   → neutral placeholders; applied to every historical blob
   version.
3. `--path … --invert-paths` — removes the archived
   Apple-derived originals directory from ALL history (D1).
4. `--strip-blobs-with-id` — removes the 30 pre-`522ab98`
   Apple-derived icon blob versions still reachable in history
   (IDs in `03-apple-derived-blob-ids.txt`, each independently
   proven to be an Apple-derived pre-replacement version).

**Verification gates — all 9 passed:**

1. commit count preserved (334 at dry-run time);
2. single author+committer identity (the public one);
3. personal name/email/username absent from all history
   content (case-insensitive);
4. Apple-derived path absent from all history;
5. all 30 target blobs stripped (0 remain);
6. private absolute build paths (`/home/builder` et al.)
   absent from all history content;
7. HEAD tree identical to source after EXACTLY the intended
   neutralizations — verified by `git archive` of both trees,
   a sed replication DERIVED from the rules file itself, and
   `diff -r --no-dereference` (the archiso profile ships
   symlinks);
8. commit messages identical modulo rewritten commit-ID
   references (positional 7-char remap);
9. `git fsck --full` clean.

**The gates caught two real corruption modes during
development** (both fixed before any real execution — the
safety design works):

- *mailmap bracket loss:* an early sed dropped the angle
  brackets around the new email, so the mailmap parser read
  the whole line as one name and silently kept the old emails
  — caught by gate 2.
- *replace-text comments:* `git-filter-repo --replace-text`
  does not support comments; a bare `#` comment line became a
  rule replacing every `#` in every file with `***REMOVED***`
  — caught by gate 7. The rules file now contains only rule
  lines (documentation lives in the script header).

**Unavoidable, documented consequences of the rewrite (by
design, not bugs):**

- ALL commit IDs change (the root commit is in the affected
  set). Commit messages are byte-identical except 7-char
  references to other commits, which necessarily point to the
  new IDs (gate 8 proves nothing else changed).
- The published copy's own tooling/audit files are themselves
  redacted: the mailmap's old-identity keys and the replace
  rules contain the personal strings — they must, to function;
  the published versions show the neutralized placeholders.
  The tooling in the published repo is therefore
  reference-only; the functional copy lives in this local
  repository.

**Remaining before the real run:** the numeric GitHub ID from
the authenticated profile (must not be fabricated), then the
manual steps printed by the script (the branch is already
`main`; `remote add` + `push` are authenticated,
user-performed actions — never performed by the agent).
