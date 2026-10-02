# Contribution Protocol

This document defines the end-to-end flow for external contributions to the MavLinOS project — from PR/issue discovery through human merge. **No auto-merge is ever performed.**

---

## 1. Principles

- **Least privilege**: CI and tooling use scoped `gh` tokens / SSH keys with minimal permissions (read PRs, read issues, write comments). No passwords. No credentials in repo.
- **Human gate**: Every integration decision requires explicit human approval. Automation prepares, classifies, and audits — humans decide.
- **Branch protection**: `main` branch is protected. Required status checks: CI build, security scan pass, triage classification.
- **Isolation**: Contributor code is never executed during review. Static analysis only. Build-agent testing happens in isolated ephemeral environments.
- **Traceability**: Every PR/issue gets a persistent review session with stable IDs (repo/PR#/SHA/issue#/comment-id). Same `task_id` across worker failover.

---

## 2. Flow Overview

```
External PR/Issue
       │
       ▼
┌──────────────────┐
│  CI (GitHub)     │  ─► Standard checks (lint, build, unit tests)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Local Orchestrator Discovery (discover.sh)
│  • gh pr list / issue list (scoped token/SSH)
│  • State stored in lab/contrib/state.json
│  • Stable IDs: never reprocess same SHA
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Fetch & Package (fetch-pr.sh <n>)
│  • Patch + metadata + file list → lab/contrib/reviews/pr-<n>-<timestamp>/
│  • NO apply, NO execution
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Static Security Scan (security-scan.sh <patchdir>)
│  • 14+ check categories (shell, FS, priv-esc, systemd, udev, network,
│    downloads, pkg-install, creds, persistence, dbus/polkit, kernel,
│    unsafe-parse, archive/path-traversal/injection)
│  • Verdict: SAFE_TO_TEST | REQUIRES_SECURITY_REVIEW | REJECTED
│  • NEVER executes contributor code
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Triage & Classification (triage.sh <patchdir>)
│  • Categories: irrelev/dup/docs/cosmetic/UI/UX/backend/integration/
│    perf/security/hw/arch/dangerous
│  • Routes to review-session objective IDs (OS-*)
│  • Considers security verdict + file types + labels + content
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Build-Agent Review (isolated env)
│  • Ephemeral container/VM per PR
│  • Applies patch, builds, runs regression suite
│  • Fidelity audit: visual, behavioral, performance
│  • Regression audit: boot, apps, hardware sims
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Integration Proposal
│  • Summary: classification, security verdict, test results,
│    fidelity/regression findings, risk assessment
│  • Presented to human maintainer
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Human Merge Decision
│  • Approve → merge to main (squash or rebase)
│  • Request changes → comment on PR, iterate
│  • Reject → close with reason
└──────────────────┘
```

---

## 3. Branch Protection Rules (main)

Enforced via GitHub branch protection:

- **Require status checks to pass before merging**:
  - `ci/build` — Arch package build + ISO smoke test
  - `ci/security-scan` — Static security scan = `SAFE_TO_TEST`
  - `ci/triage` — Classification ≠ `dangerous` / `irrelev`
- **Require pull request reviews**: 1 approval from maintainer
- **Dismiss stale approvals** on new commits
- **Require linear history** (squash or rebase merge)
- **No force pushes** to main
- **No deletions** of main

---

## 4. CI Pipeline (`.github/workflows/ci.yml`)

Actual jobs in CI (runs on every PR to `main` and push to `main`):

| Job | What it does |
|-----|--------------|
| `static-analysis` | `bash -n` all `.sh`, `py_compile` all `.py`, `xmllint` all `.xml`, `desktop-file-validate` all `.desktop`, PKGBUILD `bash -n`, `check-profile-sync.sh`, `check-sync.sh` |
| `secret-scan` | gitleaks if available; otherwise documented regex fallback (AWS/GitHub/Slack/Stripe/Google keys, private keys, hardcoded passwords) |
| `unit-tests` | pytest over all `test-mv-*.py` per-app suites; Firefox chrome CSS gates via `check-sync.sh` |
| `profile-sync` | `check-profile-sync.sh` — validates `configs/profiles/` ↔ `archiso-profile` mirror |
| `contribution-format` | PR body must contain all 12 required sections (see `.github/pull_request_template.md`) |
| `hardware-tests` | `if: false` — explicitly skipped; requires physical MacBook10,1 |

**Note**: CI uses `GITHUB_TOKEN` (auto-provided, read-only for PRs). No secrets needed.

The contrib pipeline (`discover.sh` / `fetch-pr.sh` / `security-scan.sh` /
`triage.sh`) runs on the **local orchestrator**, not in CI — it needs the
maintainer's scoped `gh` credentials (see §5). CI enforces the gates that
are credential-free: syntax, format, secrets, unit tests, profile sync.

---

## 5. Local Orchestrator Discovery

Run periodically (cron) or on-demand:

```bash
# Discover new/updated PRs and issues
./scripts/contrib/discover.sh

# For each PR of interest:
./scripts/contrib/fetch-pr.sh <PR_NUMBER>
./scripts/contrib/security-scan.sh lab/contrib/reviews/pr-<PR_NUMBER>-*
./scripts/contrib/triage.sh lab/contrib/reviews/pr-<PR_NUMBER>-*
```

**State persistence**: `lab/contrib/state.json` tracks:
- `last_pr_check`, `last_issue_check` timestamps
- `processed_prs`: `{ "PR_NUMBER": "HEAD_SHA" }` — never reprocess same SHA
- `processed_issues`: similar

---

## 6. Review Session Persistence

Each PR gets a **persistent review session** identified by Objective ID (e.g., `OS-UI-COMPONENT`, `OS-BACKEND`, `OS-HW`).

- Session state stored via `scripts/session-reuse.py` registry
- Same `task_id` used across worker failover (build → build-b → … → build-h)
- If worker fails (model quota, network, crash), session resumes on next healthy worker
- Context preserved: patch, scan results, triage, test logs, fidelity screenshots

---

## 7. Build-Agent Isolated Testing

When triage routes to a build-agent objective:

1. **Ephemeral environment**: Fresh container/VM per PR (no shared state)
2. **Patch apply**: `git apply --check` then `git apply` in clean worktree
3. **Build**: Full package rebuild + ISO generation
4. **Test suite**:
   - Unit tests (existing)
   - Regression: boot in QEMU+OVMF, DE starts, theme applies
   - Fidelity: screenshot comparison (visual regression)
   - Hardware sims: mock logind, udisks2, network, audio
5. **Artifacts**: Logs, screenshots, JSON results → attached to review session

---

## 8. Fidelity & Regression Audit

**Fidelity** (visual/behavioral):
- GTK theme adherence (Mavericks skeuomorphism)
- Icon consistency, spacing, typography
- Dock/menu bar/Launchpad/Mission Control behavior
- Dialog/file chooser/context menu coherence

**Regression** (functional):
- Boot to desktop < 10s (QEMU)
- All P0 apps launch: Finder, Spotlight, Settings, Control Center, etc.
- No new systemd units failing
- Memory/CPU baseline within 5% of pre-patch

---

## 9. Integration Proposal Format

Presented to human as GitHub PR comment + local review package:

```markdown
## Integration Proposal: PR #123

**Classification**: UI (confidence: 80%)
**Security Verdict**: SAFE_TO_TEST
**Objectives**: OS-UI-COMPONENT, OS-UX

### Changes
- Modified: configs/gtk-3.0/gtk.css (+245/-12)
- Added: configs/icons/mavericks-dock.svg

### Test Results
- ✅ CI build pass
- ✅ Security scan: SAFE_TO_TEST
- ✅ QEMU boot: 8.2s (baseline 8.1s)
- ✅ Visual regression: 0 diffs (screenshots attached)
- ⚠️ Dock icon spacing: 2px deviation (see fidelity report)

### Risk Assessment
- Low: Theme-only change, no backend modification
- No hardware dependencies
- Reversible: single config file

### Recommendation
**APPROVE** — merges cleanly, passes all gates, improves visual fidelity.
```

---

## 10. Human Merge Checklist

Before merging, maintainer verifies:

- [ ] Security scan = `SAFE_TO_TEST` (or `REQUIRES_SECURITY_REVIEW` with manual audit done)
- [ ] CI build + QEMU smoke test pass
- [ ] Triage classification appropriate
- [ ] Fidelity audit: no visual regressions
- [ ] Regression audit: no functional regressions
- [ ] Hardware dependencies documented in `NEEDS_HARDWARE_TEST.md`
- [ ] Documentation updated (APPS.md, PROGRESS.md, DECISIONS.md if architectural)
- [ ] Changelog entry added

Then: **Squash and merge** (or rebase + fast-forward) via GitHub UI or `gh pr merge --squash`.

---

## 11. Rejected / Deferred Handling

- **REJECTED (security)**: Close PR with security reasons. Log in `docs/SECURITY_REJECTIONS.md`.
- **dangerous classification**: Close with explanation.
- **irrelev**: Close with explanation.
- **hw / NEEDS_HARDWARE_TEST**: Label `hardware-validation`, keep open, document in `NEEDS_HARDWARE_TEST.md`.
- **Deferred**: Label `deferred`, milestone `future`, document reason.

---

## 12. Credential Management

| Component | Credential | Scope | Rotation |
|-----------|------------|-------|----------|
| GitHub Actions | `GITHUB_TOKEN` | Read PR, write comments, status | Auto (per-run) |
| Local orchestrator | `gh auth login` (scoped PAT or SSH) | `repo` (read), `read:org` | Manual (90 days) |
| Build-agent | None (ephemeral, no network) | N/A | N/A |

**Never** store tokens in repo. Use `gh auth setup-git` + credential helper.

---

## 13. Scripts Reference

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `discover.sh` | List new/updated PRs/issues | `state.json` | Triage tables, updated `state.json` |
| `fetch-pr.sh <n>` | Package PR for review | PR number | `lab/contrib/reviews/pr-<n>-<ts>/` |
| `security-scan.sh <dir>` | Static security analysis | Review dir | `security-scan.json`, verdict |
| `triage.sh <dir>` | Classify & route | Review dir + scan | `triage.json`, objectives |

All scripts: `set -euo pipefail`, POSIX-compatible bash, no external deps beyond `gh`, `jq`, standard coreutils.

---

## 14. Related Documents

- `docs/SECURITY_MODEL.md` — Threat model, isolation guarantees, no-secrets-in-CI
- `docs/NEEDS_HARDWARE_TEST.md` — Hardware-dependent items tracking
- `docs/DECISIONS.md` — Architectural decisions log
- `scripts/session-reuse.py` — Session persistence & failover