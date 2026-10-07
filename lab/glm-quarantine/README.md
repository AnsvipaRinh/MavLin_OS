# GLM Eternal Quarantine

**Date:** 2026-10-07
**Reason:** Owner directive — forget GLM ever existed until a new API key arrives. All GLM-related config purged from live runtime paths. Historical docs (DECISIONS/PROGRESS) remain untouched (append-only).

## Backed up files

| File | Description |
|------|-------------|
| `model-fallback.json.bak` | Last state of `.opencode/model-fallback.json` before purge |
| `opencode.jsonc.bak` | Last state of `opencode.jsonc` before purge |
| `orchestrator.md.bak` | Last state of `.opencode/agents/orchestrator.md` before purge |
| `qwen.md.bak` | Last state of `.opencode/agents/qwen.md` before purge |
| `session-reuse.py.bak` | Last state of `scripts/session-reuse.py` before purge |
| `model-health.json.bak` | Last state of `.opencode/sessions/model-health.json` before purge |

## Restoration

To restore any file, copy the `.bak` file back to its original path.
No GLM entries were in the chain itself (already removed 2026-10-04);
only text fields (notes, history, comments, health keys) contained references.
