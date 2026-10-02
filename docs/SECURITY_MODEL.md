# Security Model

This document defines the threat model, isolation guarantees, and security boundaries for the Mavericks Linux contribution pipeline.

---

## 1. Threat Model

### Assets to Protect
- **Main branch integrity**: No unauthorized code in production ISO
- **Build infrastructure**: CI runners, local orchestrator, build agents
- **Secrets**: GitHub tokens, SSH keys, signing keys (none in repo)
- **Contributor IP**: Patch content before public merge
- **Hardware targets**: MacBook10,1 firmware/boot integrity

### Adversaries
| Actor | Capability | Goal |
|-------|------------|------|
| Malicious contributor | Submit PR with hidden payload | Code execution in CI, supply chain compromise |
| Compromised CI runner | Read/write runner filesystem, network | Exfiltrate tokens, poison artifacts |
| Supply chain attack | Malicious upstream dependency | Backdoor in built ISO |
| Insider (maintainer error) | Accidental merge of bad code | Regression, vulnerability in release |

### Attack Vectors Considered
1. **PR payload execution**: Contributor code runs during review (blocked by design)
2. **CI token theft**: `GITHUB_TOKEN` exfiltration (scoped, auto-rotating)
3. **Patch application exploits**: `git apply` vulnerabilities (mitigated by `--check`)
4. **Build script injection**: Malicious `PKGBUILD`, `meson.build`, etc. (sandboxed build)
5. **Artifact poisoning**: Modified ISO/kernel injected post-build (checksums, sigs)
6. **Dependency confusion**: Typosquatted packages in build (pinned deps, offline build)

---

## 2. Isolation Guarantees

### 2.1 Review Phase (Static Only)
**Contributor code is NEVER executed during review.**

| Step | Execution | Isolation |
|------|-----------|-----------|
| `discover.sh` | `gh pr list` (read-only API) | No code exec |
| `fetch-pr.sh` | `gh pr diff/view` (read-only API) | No code exec |
| `security-scan.sh` | `grep`/`jq` on patch text | **Static analysis only** |
| `triage.sh` | `jq`/pattern match on metadata | No code exec |

**No `git apply`, no build, no test, no script execution from patch.**

### 2.2 Build-Agent Phase (Isolated Execution)
If security scan = `SAFE_TO_TEST`, build-agent tests in ephemeral environment:

```
┌─────────────────────────────────────────────────────────┐
│  EPHEMERAL BUILD AGENT (container/VM, destroyed after)  │
├─────────────────────────────────────────────────────────┤
│  • Fresh base image (Arch Linux, pinned packages)       │
│  • No network access (offline build)                    │
│  • No host filesystem access (isolated workspace)       │
│  • No privileged containers (--security-opt=no-new-privs)│
│  • Resource limits: CPU 2, RAM 4G, disk 20G, time 30m   │
│  • Clean worktree: git clone → apply patch → build      │
│  • Artifacts extracted via controlled copy-out          │
└─────────────────────────────────────────────────────────┘
```

**Build-agent network policy**: **Zero egress**. All dependencies pre-cached in base image. No `curl`, `wget`, `git clone`, `pacman -Sy` during build.

### 2.3 CI Runner (GitHub Actions)
- `GITHUB_TOKEN`: Auto-provided, **read-only for PRs**, expires at job end
- No secrets in workflow YAML
- Self-hosted runners: **Not used** (only GitHub-hosted `ubuntu-latest`)
- Workflow permissions: `contents: read`, `pull-requests: read`, `checks: write`

---

## 3. No Secrets in CI / Repo

### 3.1 Repository
- **Zero secrets committed** — enforced by `git-secrets` / `truffleHog` in pre-commit
- `.gitignore` excludes: `*.key`, `*.pem`, `*.token`, `.env`, `secrets/`, `credentials/`
- `docs/SECURITY.md` documents responsible disclosure

### 3.2 CI Environment
| Secret | Where Stored | Scope | Access |
|--------|--------------|-------|--------|
| `GITHUB_TOKEN` | GitHub Actions runtime | `repo` (read PR), `checks:write` | Auto, per-job |
| Local orchestrator PAT | `~/.config/gh/hosts.yml` (user-only) | `repo` (read), `read:org` | Human only |

**No** `AWS_*`, `DOCKER_*`, `NPM_*`, `SSH_PRIVATE_KEY`, `GPG_KEY` in CI.

### 3.3 Local Orchestrator
- Uses `gh auth login` with **scoped PAT** (classic) or **SSH key** (hardware-backed)
- Token permissions: `repo` (read), `read:org` — **no `write:packages`, `delete_repo`, `admin:org`**
- Stored in user keyring / `~/.config/gh/`, **not in repo**
- Rotation: 90 days (calendar reminder in `docs/SECURITY_ROTATION.md`)

---

## 4. Security Scan Categories (security-scan.sh)

Each category maps to a threat vector. **High = reject, Medium = requires review, Low = note.**

| Category | Threat | Patterns Detected |
|----------|--------|-------------------|
| `SHELL_EXEC` | Arbitrary command execution | `$()`, `` ` ``, `eval`, `exec`, interpreter calls |
| `FS_WRITE` | Unauthorized filesystem modification | Redirection, `tee`, `dd`, `cp`, `install` outside `/tmp` |
| `PRIV_ESCALATION` | Root/escalation | `sudo`, `su`, `setuid`, capabilities |
| `SYSTEMD_UNIT` | Persistent service installation | `.service`, `.timer`, `systemctl enable` |
| `UDEV_RULES` | Hardware access persistence | `udev`, `rules.d`, `RUN+=` |
| `NETWORK_OPS` | Data exfil / C2 | `curl`, `wget`, sockets, SSH |
| `REMOTE_FETCH` | Supply chain / RCE | Download + execute from URL |
| `PKG_INSTALL` | Unauthorized software | `pacman`, `pip`, `npm`, `cargo`, `make install` |
| `CRED_EXPOSURE` | Secret leakage | Env vars with `PASSWORD`, `TOKEN`, `KEY`, `SECRET` |
| `PERSISTENCE` | Survive reboot | `autostart`, `crontab`, `systemctl enable` |
| `DBUS_POLKIT` | Privilege escalation via IPC | `dbus-send`, `pkexec`, `polkit` |
| `KERNEL_OPS` | Kernel compromise | `modprobe`, `sysctl`, `/proc`, `/sys/kernel` |
| `UNSAFE_PARSE` | Deserialization RCE | `eval()`, `pickle`, `yaml.load`, `marshal` |
| `ARCHIVE_EXTRACT` | Path traversal | `tar`, `unzip` without `--strip`/validation |
| `PATH_TRAVERSAL` | Escape sandbox | `../`, `..\`, URL-encoded variants |
| `INJECTION` | Code/SQL/command injection | String concat in queries, `system()`, `subprocess` |

---

## 5. Verdict Definitions

| Verdict | Meaning | Action |
|---------|---------|--------|
| `SAFE_TO_TEST` | No high/medium findings | Proceed to build-agent |
| `REQUIRES_SECURITY_REVIEW` | Medium findings present | Manual security audit required |
| `REJECTED` | High findings present | **Block** — close PR, log reasons |

**No "auto-approve" path.** Even `SAFE_TO_TEST` requires human merge approval.

---

## 6. Supply Chain Hardening

### 6.1 Base Image (Build Agent)
- Pinned Arch Linux image: `archlinux:base-<YYYYMMDD>.<digest>`
- All build deps pre-installed: `base-devel`, `git`, `meson`, `ninja`, `pkgconf`, `python`, `rust`, `go`
- No package installation during build (`pacman -S` blocked by no-network)

### 6.2 Dependency Pinning
- All Arch packages: exact version in `PKGBUILD` (`pkgver=X.Y.Z`, `pkgrel=N`)
- Python: `requirements.txt` with hashes (`pip install --require-hashes`)
- Rust: `Cargo.lock` committed
- Go: `go.sum` committed
- Node: `package-lock.json` committed

### 6.3 Verification
- `makepkg --verifysource` — checksums match
- `gpg --verify` — upstream signatures where available
- `sbom` generation: `syft` on final ISO

---

## 7. Artifact Integrity

### 7.1 Build Outputs
- ISO: `sha256sum` + `gpg --detach-sign` (maintainer key)
- Packages: `.pkg.tar.zst` with `sha256sums` in `.PKGINFO`
- Logs: Immutable, appended to review session

### 7.2 Verification Before Merge
Human maintainer verifies:
```bash
# Check ISO signature
gpg --verify mavericks-linux-<ver>.iso.sig mavericks-linux-<ver>.iso
sha256sum -c mavericks-linux-<ver>.iso.sha256
```

---

## 8. Incident Response

### 8.1 Suspected Compromise in PR
1. **Immediate**: `gh pr close <n> --reason "security"` + comment with findings
2. **Containment**: Revoke any tokens used in review (rotate local PAT)
3. **Investigation**: Audit `security-scan.json`, `triage.json`, build logs
4. **Notification**: `security@` (if defined) + maintainers
5. **Recovery**: Rebuild from last known-good commit, verify ISO sigs

### 8.2 CI Runner Compromise
- GitHub-hosted runners: GitHub manages isolation
- If self-hosted ever added: immediate decommission, rotate all tokens

---

## 9. Security Boundaries Summary

| Boundary | Enforcement |
|----------|-------------|
| Repo ↔ CI | `GITHUB_TOKEN` (read-only, auto-expiry) |
| CI ↔ Build Agent | No network, offline base image, resource limits |
| Review ↔ Contributor Code | **Static only** — never executed |
| Human ↔ Automation | Human gate required for merge |
| Secrets ↔ Code | Zero secrets in repo; tokens in user keyring only |

---

## 10. Compliance Checklist (Per PR)

- [ ] Security scan = `SAFE_TO_TEST` or manual audit done
- [ ] No secrets in patch (scan category `CRED_EXPOSURE`)
- [ ] No network calls in build (offline base image verified)
- [ ] Dependencies pinned + verified (checksums, sigs)
- [ ] ISO signed + checksummed
- [ ] Review session persisted (session-reuse registry)
- [ ] `NEEDS_HARDWARE_TEST.md` updated for hw-deps
- [ ] `DECISIONS.md` updated if architectural change

---

## 11. Related Documents

- `docs/CONTRIBUTION_PROTOCOL.md` — Full flow, branch protection, CI
- `scripts/contrib/security-scan.sh` — Implementation of scan categories
- `scripts/session-reuse.py` — Session persistence & failover
- `docs/NEEDS_HARDWARE_TEST.md` — Hardware-dependent items
- `docs/DECISIONS.md` — Architectural decisions