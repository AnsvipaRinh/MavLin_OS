# Release Readiness Report — First Public Release

**Date:** 2026-10-03 (forensic-audit correction: 2026-10-03, see `docs/FORENSIC_AUDIT.md`)
**HEAD:** master (no remotes yet)
**Tracked files:** 1140
**Status:** PRE-PUBLICATION — publication procedure defined (§3), user decisions in §3.3 pending; forensic audit passed with findings (see `docs/FORENSIC_AUDIT.md`)

> **Correction note (forensic audit 2026-10-03):** this report originally
> stated "1112 tracked files". That count was taken at audit START
> (parent commit `939c8ad` = 1112 files); the publication commit `b27af3d`
> then added 28 files of its own pipeline (contribution pipeline, licenses,
> fixtures) which were authored in the same session but never covered by the
> "complete inventory" claim. Current verified count: **1140**. Other stale
> figures in the original report (`.git` size, working-tree size, check
> counts) are corrected in §1 below.

---

## 1. Final public-release audit checklist

| # | Check | Result |
|---|-------|--------|
| 1 | `git status` clean (no unintended WIP) | ✅ (only intended changes staged) |
| 2 | Complete file inventory reviewed | ✅ 1140 tracked files (1112 at audit start + 28 added by the publication commit itself — see correction note) |
| 3 | Secret scan (regex sweep, all history) | ✅ CLEAN — independently re-verified by forensic audit: 1898 reachable blobs + 3 unreachable blobs (31.5 MB) swept; 0 credentials/tokens/keys; all keyword hits are legitimate code/docs |
| 4 | License scan | ✅ All OSI-approved; matrix in `docs/LICENSES.md`; root LICENSE = GPL-3.0-or-later — ⚠️ BUT 3 Apple-derived SVGs are tracked in `docs/isolated-assets/apple-derived/` and marked NON-redistributable in `docs/LICENSES.md` §6 (open decision §3.3-D1) |
| 5 | Private-data scan | ✅ No credentials, cookies, session data, tokens — ⚠️ build-host hardware fingerprint found in `docs/benchmarks/*.json` (redacted this session, see §3.3-D2) |
| 6 | Absolute-path scan | ✅ All functional `/home/builder` paths sanitized in worktree (see §2); ⚠️ 204 line-occurrences remain in 136 historical blob versions (10 files' old revisions) — public after push unless content-level history rewrite is applied (§3.1 step 3) |
| 7 | Generated-artifact scan | ✅ `out/` (ISO), `*.pkg.tar.zst`, `pkg/`, sassc output gitignored |
| 8 | Repository size | ✅ `.git` 5.4M (verified); tracked content 6.2M; working tree 2.8G including gitignored `out/` ISO (original "~10M" claim predates the ISO build) |
| 9 | Build reproducibility | ⚠️ Packages build repo-local (verified 2026-09-29); ISO build requires Arch host + root — `mkarchiso` present in build env but a full rebuild was NOT re-run this session (last proven 2026-09-29, sha256 recorded in PROGRESS.md) |
| 10 | Tests | ✅ security-scan 5/5, triage 5/5, check-sync 142 OK / 0 FAIL, check-profile-sync OK, py_compile clean, bash -n clean, sim harness 25 scenarios / 110 assertions pass, spot-run test-mv-calculator (141) + test-mv-notes (41) pass — ⚠️ test-mv-photos has 2 known pre-existing headless failures (documented in PROGRESS.md, not a regression) |
| 11 | CI configuration | ✅ `.github/workflows/ci.yml` (6 jobs, no secrets required) — ⚠️ never executed on real GitHub Actions (REQUIRES EXTERNAL EVIDENCE); one broken step removed this session (unit-tests job ran check-sync through `grep ... || true`, swallowing its exit code — redundant with static-analysis job) |
| 12 | README | ✅ Public-audience rewrite present |
| 13 | Contribution documentation | ✅ CONTRIBUTING.md, CONTRIBUTION_PROTOCOL.md, VIBE_CODING.md, UI_UX_CONTRIBUTION.md, SECURITY.md, SECURITY_MODEL.md, CODE_OF_CONDUCT.md, PR template, 6 issue templates |
| 14 | Hardware profile separation | ✅ `configs/profiles/{generic,macbook10,1}` + `archiso-profile` mirror + sync gate |

## 2. Public/private boundary (final)

**PUBLIC (tracked):** all source, configs, themes, packages, scripts, lab harness, docs, CI, agent protocol config (`.opencode/agents/`, `model-fallback.json` — no provider secrets, auth is external).

**PRIVATE-KEEP-LOCAL (gitignored, never pushed):**
- `.opencode/sessions/` — orchestrator runtime session state
- `.opencode/node_modules/` — runtime dependencies
- `out/` — 2.7G ISO build output
- `packages/macbook12-audio-driver/{macbook12-audio-driver,src}/` — nested git clone residue (contains local absolute paths in `.git` internals)
- `*.log`, `*.pkg.tar.zst`, `pkg/`, `__pycache__/`, `.pytest_cache/`

**SANITIZED this session (were tracked, now generic):**
- `archiso-profile/releng/pacman.conf` — `/home/builder/mavericks-repo` → `/tmp/mavericks-repo`
- `scripts/test-session-reuse.py` — mock ps output → `/home/user`
- `packages/mavericks-apps/.../test_mv_launchpad.py` — `__file__`-relative path
- `lab/tests/contrib/test_security_scan.py` — `__file__`-relative REPO_ROOT
- `docs/{DECISIONS,ENVIRONMENT,PROGRESS}.md` — `<build-host>` placeholder

## 3. User decisions + publication procedure

### 3.1 Git author identity — DECISION TAKEN (option b, expanded scope), execution deferred

User decision (2026-10-03): rewrite history before the first public push so
that NO personal identity remains — neither in commit metadata nor in file
content. Target public identity: `Ansvipa_Rinh <ID+Ansvipa_Rinh@users.noreply.github.com>`.
The numeric GitHub ID must be read from the authenticated GitHub profile at
publication time — it must NOT be guessed or fabricated.

**Scope (verified by forensic audit):**

1. **Metadata:** 4 commits carry the original author's personal identity
   (name + personal email): `82386e5` (ROOT commit), `020723d`, `87f5122`,
   `a1f13a6` — author AND committer fields. The other 325 commits carry the
   temporary local alias `Mavericks Linux Agent <agent@mavericks-linux.local>`
   (not a public identity either — remap it too).
2. **Critical consequence:** because the personal-identity set includes the
   ROOT commit, a mailmap rewrite changes **ALL 329 commit IDs**, not just 4.
   This is expected; document it in the publication PR/notes.
3. **Content:** the personal name appears in 13 lines across 4 current docs
   (sanitized in the worktree this session) and in 17 occurrences inside old
   doc-blob versions (DECISIONS/ENVIRONMENT/PUBLIC_AUDIT/RELEASE_READINESS
   history). Content-level removal requires `--replace-text` in the same rewrite.

**Procedure (publication step only — NOT executed now):**

```bash
# 0. Backup first (fresh clone + bundle); work ONLY on the publication copy
git clone --no-local /path/to/repo mavericks-publish && cd mavericks-publish

# 1. mailmap: BOTH current identities -> public identity (ID from gh auth status)
git filter-repo --mailmap <(cat <<'EOF'
<original-author-name> <original-author-email> Ansvipa_Rinh <ID+Ansvipa_Rinh@users.noreply.github.com>
Mavericks Linux Agent <agent@mavericks-linux.local> Ansvipa_Rinh <ID+Ansvipa_Rinh@users.noreply.github.com>
EOF
)

# 2. content: strip personal name/email from every historical blob version
git filter-repo --replace-text <(cat <<'EOF'
<original-author-name>==><project author>
<original-author-email>==><project-author@local>
EOF
)

# 3. branch rename (CI + GITHUB_SETUP.md expect main)
git branch -m master main

# 4. remote + push (separate authenticated step — never performed by the agent)
git remote add origin https://github.com/Ansvipa_Rinh/MavLinOS.git
git push -u origin main
```

Requires `git-filter-repo` (pip). **Destructive to history** — only on a
backed-up copy, immediately before the first push.

### 3.2 GitHub authentication

`gh` CLI is NOT installed in this environment; no GitHub credentials available.
No push attempted (per protocol: never ask for passwords, never push without
confirmed ownership). Remote NOT added. Onboarding procedure:
`docs/GITHUB_SETUP.md` (browser-based `gh auth login`, no password entry).

### 3.3 Open decisions from forensic audit (2026-10-03)

- **D1 — Apple-derived assets (REQUIRES USER DECISION).** 3 SVGs in
  `docs/isolated-assets/apple-derived/` contain explicit Apple logo vector
  paths and "Mac OS X 10.9 Mavericks" text; `docs/LICENSES.md` §6 marks them
  NON-redistributable. Isolation prevents *installation* but not
  *redistribution* — in a public repo they would still be published (and they
  exist in history inside the theme tree). Options: (i) remove from tree +
  history before push (replace with a provenance note; the theme already uses
  replacement generics since commit `522ab98`) — recommended; (ii) keep with
  documented license rationale (legal risk); (iii) move to a private repo.
- **D2 — Build-host hardware fingerprint in benchmark data (FIXED conservatively
  this session — user may override).** `docs/benchmarks/*.json` (14 files)
  recorded the build host verbatim: `AMD Ryzen 7 5800HS with Radeon Graphics`,
  `WSL2`, WSL kernel signature. The forensic audit redacted these to
  `<build-host-cpu>` / `<build-host-platform>` placeholders (all measurement
  numbers preserved). If the user considers CPU model non-personal, the
  original strings can be restored from history. Note: the previous audit was
  self-contradictory on this (§3.2 "PRIVATE-KEEP-LOCAL" vs §3.4 "kept tracked").
- **D3 — Branch rename timing (DECIDED: at publication step).** `master` →
  `main` happens inside the §3.1 procedure (step 3), not before — so the
  history rewrite and the rename land in the same publication pass.

## 4. What was changed this session

- Sanitized 7 tracked files + 1 untracked test of machine-specific paths
- Added `LICENSE` (GPL-3.0-or-later), `CODE_OF_CONDUCT.md` (CC 2.1)
- Committed contribution pipeline: `docs/CONTRIBUTION_PROTOCOL.md`, `docs/SECURITY_MODEL.md`, `scripts/contrib/*.sh`, `lab/tests/contrib/`
- Calibrated `security-scan.sh` (1/5 → 5/5 fixture verdicts)
- Fixed `triage.sh` (PATH clobber bug, routing model, word-boundary regexes; 1/5 → 5/5)
- Fixed `test_triage.py` REPO_ROOT
- Corrected `CONTRIBUTION_PROTOCOL.md` §4 to match actual `ci.yml`
- `project-meta.json`: `MacBook9,1` → `MacBook10,1`
- `docs/RELEASE_READINESS.md` (this report), `docs/PUBLIC_AUDIT.md` refresh, `docs/PROGRESS.md`, `docs/DECISIONS.md`

## 4a. Forensic-audit pass (2026-10-03, this session)

- Sanitized personal name/email from 4 current docs (DECISIONS, ENVIRONMENT, PUBLIC_AUDIT, RELEASE_READINESS) → neutral placeholders; audit facts preserved
- Corrected stale figures: tracked files 1112 → 1140 (root-caused: count taken pre-commit; the publication commit added 28 of its own files), `.git` 7.9M → 5.4M, working tree "~10M" → 6.2M tracked content (2.8G with gitignored ISO), check-sync "221/227 checks" → 142 verified OK lines
- Redacted build-host hardware fingerprint from `docs/benchmarks/*.json` (14 files; measurements preserved)
- Fixed `.github/workflows/ci.yml` unit-tests job: removed step that piped check-sync through `grep ... || true` (swallowed exit code; redundant with static-analysis job's full check-sync)
- Added `docs/FORENSIC_AUDIT.md` (full independent audit: verified claims, contradictions resolved, classifications, NOT-PROVEN items)

## 5. Remaining blockers

1. **Publication procedure §3.1** — history rewrite (mailmap + replace-text) on a backed-up copy; needs the numeric GitHub ID from authenticated profile; changes all 329 commit IDs (root commit is in the affected set)
2. **Open decisions §3.3** — D1 Apple-derived assets (user decision required), D2 benchmark fingerprint redaction (done, may be overridden), D3 branch rename (scheduled inside §3.1)
3. **User action §3.2** — install `gh`, `gh auth login`, create repo, add remote, push (procedure in `docs/GITHUB_SETUP.md`)

No other blockers. All offline work is complete.
