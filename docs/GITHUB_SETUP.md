# GitHub Setup Guide for Mavericks Linux

> Beginner-friendly path from zero to contributing. Commands marked `[ORCHESTRATOR]` can be run by the autonomous agent; others require human with GitHub credentials.

## Prerequisites
- GitHub account
- `git` installed
- `gh` CLI installed (`pacman -S github-cli` / `brew install gh` / `apt install gh`)

---

## 1. Create GitHub Account & Repository

**Human:**
1. Go to https://github.com → Sign up
2. Create new repository: `macbook12-macos-linux`
   - Public or Private (your choice)
   - Do NOT initialize with README, .gitignore, license (we have our own)

---

## 2. Authenticate `gh` CLI

**Human:**
```bash
gh auth login
# Follow prompts: GitHub.com → HTTPS → Login with browser/token
# Scopes needed: repo, workflow, admin:repo_hook (for branch protection)
```

**Verify:**
```bash
gh auth status
```

---

## 3. Connect Local Repo to GitHub

**[ORCHESTRATOR]** (run in project root):
```bash
# Check current remotes
git remote -v

# Rename local branch master → main (CI and branch protection target `main`)
git branch -m master main

# Add GitHub remote (replace YOUR_USER)
git remote add origin https://github.com/YOUR_USER/macbook12-macos-linux.git

# Verify
git remote -v
git branch --show-current   # must print: main
```

**Human** (first push requires auth):
```bash
# Push main branch
git push -u origin main

# Push all tags (if any)
git push --tags
```

---

## 4. Verify GitHub Actions Work

**[ORCHESTRATOR]**
```bash
# Trigger a workflow run by pushing a trivial commit
git commit --allow-empty -m "ci: trigger initial workflow run"
git push
```

**Human:** Check Actions tab on GitHub — should see "CI" workflow run.

---

## 5. Create Labels

**Human** (run once after repo exists):
```bash
# Option A: Use the script from docs/LABELS.md (copy-paste all commands)
# Option B: Run this helper (requires gh auth)
gh repo clone YOUR_USER/macbook12-macos-linux /tmp/mavericks-labels && cd /tmp/mavericks-labels && bash -c "$(cat docs/LABELS.md | grep '^gh label create')"
```

**Verify:**
```bash
gh label list --repo YOUR_USER/macbook12-macos-linux
```

---

## 6. Configure Branch Protection (main)

**Human** (requires admin access):
```bash
# Protect main branch
gh api repos/YOUR_USER/macbook12-macos-linux/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Static Analysis","Secret Scan","Unit Tests","Profile Sync","Contribution Format"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

**Or via UI:** Settings → Branches → Add rule for `main` → Enable:
- Require status checks to pass before merging (select all 5 CI jobs)
- Require pull request reviews (1 approval)
- Dismiss stale reviews
- Include administrators
- Do NOT allow force pushes/deletions

---

## 7. Create First Issue

**Human** (or [ORCHESTRATOR] via `gh issue create`):
```bash
gh issue create \
  --title "[UI] Finder sidebar missing Devices section" \
  --body-file .github/ISSUE_TEMPLATE/ui-discrepancy.yml \
  --label "ui-discrepancy,P0,hw:pre-hardware,status:not-started"
```

---

## 8. Create First PR

**Workflow:**
```bash
# [ORCHESTRATOR] Create feature branch
git checkout -b feat/finder-sidebar-devices

# [ORCHESTRATOR] Make changes, commit
git add -A
git commit -m "feat(finder): add Devices section to Thunar sidebar"

# [ORCHESTRATOR] Push branch
git push -u origin feat/finder-sidebar-devices

# Human: Open PR via gh or web
gh pr create \
  --title "feat(finder): add Devices section to sidebar" \
  --body-file .github/pull_request_template.md \
  --base main \
  --head feat/finder-sidebar-devices
```

**PR will:**
1. Run all CI jobs (Static Analysis, Secret Scan, Unit Tests, Profile Sync, Contribution Format)
2. Require all checks green + 1 approval
3. Auto-merge when enabled (Settings → Pull Requests → Allow auto-merge)

---

## 9. Orchestrator Automation Notes

The autonomous agent (**Orchestrator role**) can:
- ✅ Read repo state (`git status`, `git log`, `gh api`)
- ✅ Create commits on feature branches
- ✅ Push feature branches (`git push`)
- ✅ Run CI locally (`act` or scripted checks)
- ✅ Create issues via `gh issue create` (if `gh` token with `repo` scope provided)
- ✅ Update labels on issues/PRs via `gh issue edit` / `gh pr edit`
- ✅ Read CI logs via `gh run view`

The Orchestrator **CANNOT**:
- ❌ Create the GitHub repository (human)
- ❌ Run `gh auth login` (human)
- ❌ Configure branch protection (human admin)
- ❌ Create labels initially (human, one-time)
- ❌ Merge PRs (requires approval + CI green)
- ❌ Manage secrets/environments (human)

**To give Orchestrator `gh` access:** Provide a `GH_TOKEN` env var with `repo`, `workflow`, `admin:repo_hook` scopes. Store in secure secret manager, not in repo.

---

## 10. Repository Settings Checklist

After setup, verify in GitHub UI (Settings):

- [ ] **General** → Features: Issues, Wiki, Projects, Discussions (as needed)
- [ ] **Branches** → Branch protection for `main` (see §6)
- [ ] **Actions** → General: Allow all actions / Allow select actions (reuse workflows)
- [ ] **Actions** → Workflow permissions: Read/write (for PR comments, labels)
- [ ] **Pages** → (Optional) Deploy docs from `gh-pages` branch
- [ ] **Security** → Code scanning: Enable CodeQL (optional, for C/C++ packages)
- [ ] **Security** → Secret scanning: Enable (free for public repos)
- [ ] **Webhooks** → (Optional) For external CI mirrors

---

## 11. Daily Workflow Commands

**[ORCHESTRATOR] Common operations:**
```bash
# Sync with upstream
git fetch origin
git rebase origin/main

# Check CI status of current branch
gh run list --branch $(git branch --show-current) --limit 5

# View latest CI failure logs
gh run view --log-failed

# Update issue status
gh issue edit 123 --add-label "status:in-progress" --remove-label "status:not-started"

# Link PR to issue
gh pr edit 456 --add-label "P0" --body "$(cat .github/pull_request_template.md)"

# Search issues by label
gh issue list --label "P0,ui-discrepancy" --state open
```

---

## 12. Troubleshooting

| Problem | Solution |
|---------|----------|
| `gh: command not found` | Install: `pacman -S github-cli` / `brew install gh` / `apt install gh` |
| `Permission denied (publickey)` on push | `gh auth login` or add SSH key: `gh ssh-key add ~/.ssh/id_ed25519.pub` |
| CI fails on `check-sync` | Run `./scripts/check-sync.sh` locally, fix divergences, commit |
| Branch protection blocks push | Ensure PR workflow: push to feature branch, open PR, don't push directly to `main` |
| `gh label create` fails | Need `admin:repo_hook` scope: `gh auth refresh -s admin:repo_hook` |

---

## 13. Security Notes

- **Never commit secrets** (tokens, keys, passwords). CI secret-scan job will catch them.
- **Use `gh secret set`** for CI secrets (not needed for this project currently).
- **Rotate tokens** periodically: `gh auth refresh`.
- **Audit third-party actions** in `.github/workflows/ci.yml` — pin to SHA, not tags.