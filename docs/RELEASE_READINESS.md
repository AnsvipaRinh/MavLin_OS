# Release Readiness Report — First Public Release

**Date:** 2026-10-03
**HEAD:** master (no remotes yet)
**Tracked files:** 1112
**Status:** READY FOR PUBLICATION (pending 2 user decisions below)

---

## 1. Final public-release audit checklist

| # | Check | Result |
|---|-------|--------|
| 1 | `git status` clean (no unintended WIP) | ✅ (only intended changes staged) |
| 2 | Complete file inventory reviewed | ✅ 1112 tracked files audited |
| 3 | Secret scan (regex sweep, all history) | ✅ CLEAN (0 findings) |
| 4 | License scan | ✅ All OSI-approved; matrix in `docs/LICENSES.md`; root LICENSE = GPL-3.0-or-later |
| 5 | Private-data scan | ✅ No credentials, cookies, session data, tokens |
| 6 | Absolute-path scan | ✅ All `/home/builder` paths sanitized (see §2) |
| 7 | Generated-artifact scan | ✅ `out/` (2.7G ISO), `*.pkg.tar.zst`, `pkg/`, sassc output gitignored |
| 8 | Repository size | ✅ `.git` 7.9M, working tree ~10M (no binaries) |
| 9 | Build reproducibility | ⚠️ Packages build repo-local; ISO build requires Arch host + root (documented) |
| 10 | Tests | ✅ security-scan 5/5, triage 5/5, check-sync ALL PASSED, py_compile clean, bash -n clean |
| 11 | CI configuration | ✅ `.github/workflows/ci.yml` (6 jobs, no secrets required) |
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

## 3. User decisions required (NOT done automatically)

### 3.1 Git author identity (4 commits)

History contains 4 commits by `Vsevolod Avdonkin <vsevolod@archlinux>` (personal email).
Options:
- **(a) Keep as-is** — transparent history, personal email public.
- **(b) Rewrite before first push** (recommended):
  ```bash
  git filter-repo --mailmap <(echo "Vsevolod Avdonkin <vsevolod@archlinux> Mavericks Linux Agent <agent@mavericks-linux.local>")
  ```
  Preserves commit count/timestamps; maps identity to the project alias. Requires `git-filter-repo` (pip). **Destructive to history** — only run before the first push, on a fresh clone, after backing up.
- Decision owner: user. Not performed by the agent (history rewrite requires explicit consent).

### 3.2 GitHub authentication

`gh` CLI is NOT installed in this environment; no GitHub credentials available.
No push attempted (per protocol: never ask for passwords, never push without confirmed ownership).
Onboarding procedure: `docs/GITHUB_SETUP.md` (browser-based `gh auth login`, no password entry).

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

## 5. Remaining blockers

1. **User decision 3.1** — git author identity rewrite (optional, recommended before first push)
2. **User action 3.2** — install `gh`, `gh auth login`, create repo, add remote, push (procedure in `docs/GITHUB_SETUP.md`)

No other blockers. All offline work is complete.
