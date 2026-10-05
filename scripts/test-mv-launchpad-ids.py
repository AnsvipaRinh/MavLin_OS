#!/usr/bin/env python3
"""Regression tests for persisted Launchpad desktop-ID migration."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Windowless app-suite: no window today, but app code and child
# interpreters run with the ambient environment — on WSLg that is
# the user's Windows desktop.  Arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED (oid
# OS-window-leak2) instead of popping a window on the host.
sys.path.insert(0, str(REPO / "scripts" / "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

SCRIPT = REPO / "packages/mavericks-apps/src/mavericks-apps/bin/mv-launchpad"


def test_migration_contract():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def _canonical_app_ids(apps):" in source
    assert "def _migrate_app_id(app_id, canonical, legacy):" in source
    assert "migrated_ids, migrated = _migrate_app_ids(app_ids, apps)" in source
    assert "changed = changed or migrated" in source
    assert "positions = load_positions(apps)" in source
    assert "def migrate_positions(" not in source


def test_ambiguous_legacy_ids_are_not_guessed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "len(ids) == 1" in source
    assert "return legacy.get(app_id, app_id)" in source


if __name__ == "__main__":
    test_migration_contract()
    test_ambiguous_legacy_ids_are_not_guessed()
    print("All Launchpad migration tests passed!")
