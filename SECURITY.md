# Security Policy

## Threat Model

| Threat | Mitigation |
|--------|------------|
| **AI-generated code = untrusted** | All AI output treated as unreviewed; mandatory human review + `check-sync.sh` gate before merge |
| **Arbitrary script execution on host** | No `curl \| bash`, no unpinned VCS sources in ISO, no `sudo` in build scripts except `mkarchiso` |
| **Supply chain** | Repo-local packages only (3/4); `macbook12-audio-driver` pinned to tanisperez commit + PRE_BUILD fetches kernel.org source at DKMS build time |
| **Secrets in repo/CI** | None. `model-fallback.json` references `OPENROUTER_API_KEY` as env var only. No `.env` files. Git history author rewrite recommended before public push (see `docs/PUBLIC_AUDIT.md` §3.3) |
| **ISO attack surface** | sshd disabled (`.wants` symlink removed), root locked (`root:!`), permissive sshd_config deleted. Remote bring-up = explicit opt-in via lab agent (key-based forced-command as `mavericks-lab`, never root) |

## Review Verdicts (every PR / AI patch)

| Verdict | Criteria | Action |
|---------|----------|--------|
| **SAFE_TO_TEST** | No exec, no network fetch, no secrets, syntax clean, `check-sync.sh` passes | Merge after human review |
| **REQUIRES_SECURITY_REVIEW** | Adds executable, network call, D-Bus policy, polkit rule, kernel module, setuid, capability, sudoers entry | Block until explicit security sign-off |
| **REJECTED** | Arbitrary script exec, unpinned dependency, secret exposure, root daemon, Electron/Java bundle, `powertop --auto-tune`, `thermald`/`ananicy-cpp` | Close with reason |

## Least-Privilege Credentials

- **Build**: No secrets. `mkarchiso` needs root (single sudo call, documented)
- **Lab agent**: SSH forced-command, ed25519 machine key, narrow sudoers (only `efibootmgr -n/-o`, `systemctl` for A/B slots)
- **Runtime**: No setuid binaries. **No `polkit` rules are shipped by this project** — no `.pkla`/`.rules` file exists anywhere in the repo. Every privileged action (logind Sleep/Restart/Shut Down, UDisks2 unmount/eject) is authorized by the *stock systemd* `org.freedesktop.login1` actions, so the policy is upstream and auditable, not ours. `polkit` + `polkit-gnome` are now ISO dependencies so an authentication agent exists to answer those prompts; `udisks2` for the eject backend. `mv-power-ui` calls `CanSuspend`/`CanReboot`/`CanPowerOff` to gate its buttons, and `mv-eject` reports a denial as "policy does not allow ejecting this volume" rather than leaking raw GDBus text. No `pkexec`, no setuid, no sudoers entry; the privilege model is unchanged.
- **CI/CD**: Not configured. If added: no secrets in repo, OIDC + short-lived tokens only

## Hardened Defaults (ISO)

- `sshd` disabled + root locked (Phase 0.3, commit dfbd987)
- `systemd-networkd` + `iwd` for install only (not in installed system)
- `reflector` only in ISO (not installed)
- `modprobe.d/99-mavericks.conf`: no active options in baseline
- `journald` volatile in ISO, persistent with limits on install
- `fstrim.timer` enabled on install (SSD endurance)

## Reporting

No public bug tracker. Security issues: open a GitHub Security Advisory (if public) or email the maintainer directly. No bounty program.