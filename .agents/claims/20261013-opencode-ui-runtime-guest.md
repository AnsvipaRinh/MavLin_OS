# Claim: opencode-ui-runtime-guest

- Agent: opencode (MavLinOS extraction workstream)
- Scope: `tools/uiref/**`, `tests/uiref/**`, `docs/UI_REFERENCE/**`
- Started: 2026-10-13
- Task: Phase 2 extraction — repair the runtime probe, rebuild the reference
  guest (off-line install + blind QMP driving), integrate runtime measurements
- Note: `tools/uiref/build-probe.sh`, `tests/uiref/test_probe_json.py` and part
  of `mvprobe.c` were removed from the shared worktree during this session and
  restored; please do not clean or reset this checkout while this claim is open.
