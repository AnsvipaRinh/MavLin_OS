#!/usr/bin/env python3
"""Regression test for persisted Launchpad ID migration."""

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "packages/mavericks-apps/src/mavericks-apps/bin/mv-launchpad"


def test_folder_migration_marks_config_changed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "app_ids, migrated = _migrate_app_ids(app_ids, apps)" in source
    assert "changed = changed or migrated" in source


if __name__ == "__main__":
    test_folder_migration_marks_config_changed()
    print("Launchpad migration persistence test passed!")
