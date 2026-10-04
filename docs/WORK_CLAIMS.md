# Work Claims Board — Active Claims

## Protocol (mandatory)

1. **Claim before first edit** — Before ANYONE (build worker, orchestrator task, human co-author, external contributor) starts editing a block (file group / subsystem / objective scope), they MUST claim it visibly on this board.
2. **One ACTIVE claim per block** — No parallel work on the same block.
3. **Release on completion** — When work is done (commit pushed), the claim is removed or marked DONE.
4. **Stale claims** — Claims >48h without commit activity may be challenged by any actor.
5. **Orchestrator duty** — Before assigning work, the orchestrator checks this board. Foreign ACTIVE claim on same block = WAIT, never double-assign.

---

## Active Claims Table

| Block / Scope | Who | Since (UTC) | Objective / Issue | Status |
|---|---|---|---|---|
| packages/mavericks-apps/.../bin/mv-diskutil + scripts/test-mv-diskutil.py | Qwen | 2026-10-05 | Portability: lazy-Gtk/DBus shim so unit tests run on non-Arch hosts | DONE (b42af1f) |
| packages/mavericks-apps/.../bin/mv-keychain + scripts/test-mv-keychain.py | Qwen | 2026-10-05 | Portability: lazy-Gtk/Secret shim, headless pure-logic tests on non-Arch hosts | DONE (b27634f) |
| packages/mavericks-apps/.../bin/mv-finder-columns + scripts/test-mv-finder-columns.py | Qwen | 2026-10-05 | Portability: lazy-Gtk factory so pure-logic tests run on non-Arch hosts | DONE |
| packages/mavericks-apps/.../bin/mv-finder-search + scripts/test-mv-finder-search.py | Qwen | 2026-10-05 | Portability: lazy-Gtk factory, headless suite (54 passed) | DONE |
| packages/mavericks-apps/.../bin/mv-power-ui + scripts/test-mv-power-ui.py | Qwen | 2026-10-05 | Portability: lazy-Gtk factory, headless suite (32 passed) | DONE |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-stickies + scripts/test-mv-stickies.py | Qwen | 2026-10-05 | Portability: lazy-Gtk factory so pure-logic tests run on non-Arch hosts | DONE |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-timemachine + scripts/test-mv-timemachine.py | Qwen | 2026-10-05 | Portability: lazy-Gtk factory so pure-logic tests run on non-Arch hosts | DONE (55 passed) |
| packages/mavericks-apps/src/mavericks-apps/bin/mv-voice + scripts/test-mv-voice.py | Qwen | 2026-10-05 | Portability: lazy-Gtk factory so pure-logic tests run on non-Arch hosts | ACTIVE |

Example row format (do not leave examples as ACTIVE):
`| Mission Control ISO deps | Grok | 2026-10-04 20:20 | #1 | DONE |`

---

**Instructions for claiming:**
- **Build workers / orchestrator tasks**: Add a row to this table via commit before starting work.
- **Human co-authors**: Add a row via commit, or comment on the relevant GitHub issue with "CLAIM: <block/scope>" for large blocks.
- **External contributors**: Comment "CLAIM: <block/scope>" on the GitHub issue/PR — maintainers will mirror to this board.

**Instructions for releasing:**
- Remove the row (or mark DONE with completion timestamp) in the same commit that completes the work.
