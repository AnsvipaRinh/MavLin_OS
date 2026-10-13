agent: opencode:ui-platform-spec
task: wire the UI data contract checks into the pre-commit gate (additive, non-failing report) and add the L2 design-token compiler (tools/uiplatform/tokens.py -> design/**)
paths: scripts/check-sync.sh, .github/workflows/ci.yml, tools/uiplatform/**, design/**, tests/uiplatform/**, docs/UI_PLATFORM/**, docs/DECISIONS.md, docs/PROGRESS.md
notes: protected files changed only to ADD two gate lines (contract validate + informational conformance report); extraction paths (docs/UI_REFERENCE/**, tools/uiref/**, tests/uiref/**) stay untouched.
expires: 2026-10-14T00:00Z
