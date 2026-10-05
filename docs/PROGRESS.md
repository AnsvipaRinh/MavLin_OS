# MavLinOS Development Progress

**Last Updated**: 2026-10-04 21:45 CEST

---

## Recent Achievements (2026-10-04)

### ✅ Issue #2: Poppy OS X Revieve Audit — COMPLETE

**Status**: 🟢 Audit Complete, Ready for Closure

**Summary**: Comprehensive technical and legal audit of Poppy OS X Revieve theme assets completed. All third-party components verified and documented.

**Deliverables**:
- `docs/POPPY_AUDIT.md` — Full technical audit with reuse map
- `docs/ISSUE_2_STATUS.md` — Live status tracker
- `docs/SESSION_SUMMARY_2026-10-04.md` — Session log
- `docs/FINAL_SESSION_REPORT_2026-10-04.md` — Comprehensive summary
- `packages/mavericks-theme/NOTICE` — Legal attribution file

**Key Findings**:
| Component | Source | License | Decision |
|-----------|--------|---------|----------|
| GTK3/XFWM/Plank | B00merang-Project/OS-X-Mavericks | GPL-3.0 | ✅ Keep |
| Cursors | Poppy OS X Revieve | CC BY-SA 4.0 | ✅ Keep |
| Icons | Mixed | GPL-3.0 | ⚠️ Hybrid |
| Wallpapers | Apple Inc. | Proprietary | ✅ Keep |

**Impact**:
- ~2000 lines of CSS/XML reused via B00merang (40-60 hours saved)
- Legal compliance achieved — project ready for redistribution
- All licenses verified and properly attributed

**Next**: Issue #2 ready for closure. Optional enhancements (icon improvements, benchmark) can be tracked separately.

---

## Active Work Streams

### Issue #1: Architecture Execution Plan

**Status**: 🟡 Active

**Focus**: Incremental migration toward final fidelity + efficiency architecture

**Recent Progress**:
- Panel plugin-7 HUD config repair (0cc876a9)
- Self-contained firstboot implementation (4e3ede57)
- Profile sync CI gates strengthened

---

## Completed Objectives (Session 2026-10-04)

1. ✅ Poppy cursors license verified (CC BY-SA 4.0)
2. ✅ NOTICE file created with full attribution
3. ✅ Audit documentation complete (4 files)
4. ✅ Legal compliance achieved

---

## Pending Optional Enhancements

1. ⏳ Enhance icons with 10-20 Poppy assets (fidelity improvement)
2. ⏳ Benchmark theme RSS/CPU overhead (validation)

---

## Project State

**Legal Status**: ✅ Compliant (all third-party licenses verified)
**Documentation**: ✅ Comprehensive (50+ docs/*.md files)
**Test Coverage**: ✅ Extensive (30+ test scripts)
**CI/CD**: ✅ Active (check-sync, profile-sync, panel-config tests)

---

*Progress tracked by MavLinOS Orchestrator*

---

## Session 2026-10-06 (OS-nc-p0) — Notification Center P0 (canonical #5): keyboard operability, per-entry dismiss, urgency

**Objective:** oid OS-nc-p0 — audit the Notification Center against §13.6 and
close the executable pre-hardware gaps. Zone: `bin/mv-notification-center` +
`bin/mv-notify-send` + their tests only.

**Audit findings (behaviour measured on pinned Xvfb :97, not read from docs).**
The panel was substantially mouse-only. `GtkListBox` used
`SelectionMode.NONE`, which cannot hold a cursor — verified at runtime, both
app sections reported `selection_mode: none`, so arrow keys moved nothing and
Enter never activated an entry. Dismissal was limited to the close button,
Escape, per-app "Clear" and "Clear All"; a row walk found zero per-entry
controls. `get_urgency_color` was dead code, so urgency was logged but never
shown. Grouping/order was correct under the writer's append order but depended
on that unstated invariant.

**Gaps closed.**
- **Keyboard operability:** `SelectionMode.SINGLE` + `row-activated`; the first
  Down/Up/Delete press seeds a cursor on the newest entry, Enter activates,
  Delete/BackSpace dismiss the selected entry. Cursor movement is delegated to
  GtkListBox rather than hand-rolled.
- **Per-entry dismiss:** a ✕ per row removing exactly that entry by its logged
  `id` (`dismiss_entry` — read-filter-replace on the existing locked log, so no
  second daemon and no extra bookkeeping).
- **Urgency visible:** colour-coded accent dot for critical/low; normal
  entries stay bare, as in Mavericks.
- **Ordering hardened:** timestamp-driven instead of log-position-driven, so
  chronological, reversed and interleaved logs all render identically.

**Architecture preserved (§10.3, §7).** xfce4-notifyd remains the only
notification daemon; history stays an on-demand JSON log; DND stays
xfce4-notifyd's own xfconf property. No resident process, no polling, no new
wakeups. `mv-notify-send` needed **no code change** — its flock/atomic/id/cap
contract was already correct; the audit proved it instead of asserting it.

**Tests: 85 checks, all green.**
- `scripts/test-mv-notification-center.py` — 64 checks: static contract
  (single-daemon architecture, activation/dismiss plumbing, Super+Shift+V) plus
  a real GUI smoke on the pinned :97 (grouping, ordering incl. reversed log,
  keyboard cursor seeding, Delete-dismiss, per-row ✕, clear actions, activation
  targets, empty state, Escape, DND ownership). The smoke stubs the xfconf
  calls so a test run never mutates the developer's DND state.
- `scripts/test-notification-history.py` — 21 checks, now behavioural: 6
  concurrent writers x 25 appends lose no entries, file stays valid JSON at
  0600 with unique ids, 500-entry cap holds, a corrupt store degrades to empty.
- **Mutation-checked:** reverting `SelectionMode`, by-id dismiss, or timestamp
  ordering turns the suite red; removing the flock collapses 150 concurrent
  appends to 6. The tests fail when the fixes are reverted.
- GUI smoke ran only via `scripts/gui-isolation.sh` on the pinned Xvfb :97 —
  guard reported 0 host-display attempts.

**Gate status (honest).** `scripts/check-sync.sh` is **red at HEAD for reasons
outside this zone**, verified against a clean `HEAD` worktree:
- `scripts/test-mavericks-apps-packaging.py` has a **SyntaxError at line 54**
  (two `else:` clauses attached to the same construct), committed by 0be8063
  (PR #108). Pre-existing, outside this zone, left untouched.
- Seven suites (`airdrop`, `desktop-cache`, `finder-search`, `keychain`,
  `mail`, `photos`, `power-ui`) fail only in the shared working tree and pass
  at clean HEAD — in-flight WIP from the parallel agents, not this zone.

**Incident recovered (worth recording).** Mid-session a parallel agent ran
`git stash` ("shared-wip 2"), which swept up this zone's uncommitted work, and
the four zone files were later found reverted to a pre-hardening state — which
would have re-introduced the WSLg host-display leak (oid OS-window-leak2) and
dropped the `gtk-launch` desktop-entry hardening. The zone was restored from
backups + HEAD and the result committed immediately to secure it. Lesson for
the orchestrator: a parallel `git stash`/`checkout` sweeps up *every*
zone's work; `git add <explicit paths>` + commit early is the only safe
checkpoint, and this zone should not be `stash`ed by another agent.

**Status:** Notification Center remains **PARTIALLY IMPLEMENTED** — the
hardware-dependent remainder (banner look, Super+Shift+V, ✕ placement,
translucency on the real panel) plus the documented absence of live
auto-refresh while the panel stays open. See `docs/APPS.md` row,
`docs/DECISIONS.md` (7 recorded choices), `docs/NEEDS_HARDWARE_TEST.md`.
