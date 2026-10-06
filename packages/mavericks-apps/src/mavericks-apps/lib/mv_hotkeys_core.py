#!/usr/bin/env python3
"""mv_hotkeys_core — the MavLinOS global keyboard shortcut layer core.

Design (P0 #23, AGENTS.md §6 "Keyboard shortcut architecture"):

  * ONE authoritative registry (`ACTIONS`) maps a conceptual action id to
    its Mavericks-style accelerator, the command it runs, the Xfce channel
    branch it lives in and the System Settings skill group it is shown
    under.  The registry is the source of truth: the packaged
    `xfce4-keyboard-shortcuts.xml` is checked against it (drift detection)
    and can be regenerated from it.
  * USER OVERRIDES live in `~/.config/mfkeys/overrides.json` (a small JSON
    file, not a second copy of the defaults).  Only the actions the user
    actually changed are recorded, so the shipped XML stays the pristine
    factory state and `reset` is always possible.
  * APPLICATION is via `xfconf-query` on the live channel, so a rebind
    takes effect immediately without restarting anything.  This repo runs
    a real xfconf on the default system profile, so the channel must NOT
    be unloaded by mistake.
  * NOTHING here is a daemon: every entry point is a one-shot CLI call.
  * Standard Linux shortcuts and the hardware function row are PROTECTED:
    rebinding them is refused unless `--force` is given, so the layer can
    never swallow Ctrl+Alt+T, Alt+Tab, brightness or audio keys.

Origin: architecture, action registry layout, conflict/protection model and
the CLI surface (`list/show/set/reset/verify/export/import`) were produced
by Qwen Code (qwen3.8-flash) driven through
`scripts/qwen-integration/qwen-web-worker.py` on 2026-10-06; its delivered
`mv-hotkeys` draft is kept in git history.  This module supersedes it after
review: the accelerator model was changed from "action -> xfconf property
name" (which cannot express a rebind, since the key *is* part of the
property name) to "action -> modifiers + key + command" (see
docs/DECISIONS.md), protected hardware keys were completed, and XML
rendering/drift detection was added.

Pure logic (registry, override merging, accelerator parsing/formatting,
conflict detection, XML rendering/parsing) is importable headless — no gi,
no GTK, no xfconf.  License: GPL-2.0-or-later.
"""
# NOTE: Full module body is restored from git history in this emergency
# commit path. If this file is incomplete, run:
#   git show 0e91a835:packages/mavericks-apps/src/mavericks-apps/lib/mv_hotkeys_core.py
# and re-apply the airdrop ACTIONS row after empty-trash-alt.
raise SystemExit(
    'mv_hotkeys_core: emergency stub — restore full module from '
    'commit 0e91a835 (blob 2c919a0) + airdrop ACTIONS row. '
    'Artifact: session CORE_RESTORE_FULL.py'
)
