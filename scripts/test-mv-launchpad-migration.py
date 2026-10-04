#!/usr/bin/env python3
"""Regression tests for Launchpad legacy application-ID migration."""

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "packages/mavericks-apps/src/mavericks-apps/bin/mv-launchpad"

def load_module():
    fake_gi = types.ModuleType("gi")
    fake_gi.require_version = lambda *args: None
    fake_repo = types.ModuleType("gi.repository")
    fake_repo.Gtk = types.SimpleNamespace(IconTheme=types.SimpleNamespace(get_default=lambda: None))
    fake_gi.repository = fake_repo
    sys.modules["gi"] = fake_gi
    sys.modules["gi.repository"] = fake_repo
    cache = types.ModuleType("mv_desktop_cache")
    cache.load_desktop_entries = lambda: []
    sys.modules["mv_desktop_cache"] = cache
    spec = importlib.util.spec_from_file_location("mv_launchpad_migration_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_unique_legacy_id_migrates():
    module = load_module()
    apps = [{"id": "foo-bar.desktop", "legacy_id": "bar"}, {"id": "calculator.desktop", "legacy_id": "calculator"}]
    ids, changed = module._migrate_app_ids(["bar", "calculator"], apps)
    assert ids == ["foo-bar.desktop", "calculator"]
    assert changed is True

def test_ambiguous_legacy_id_is_not_guessed():
    module = load_module()
    apps = [{"id": "foo-bar.desktop", "legacy_id": "bar"}, {"id": "baz-bar.desktop", "legacy_id": "bar"}]
    ids, changed = module._migrate_app_ids(["bar"], apps)
    assert ids == ["bar"]
    assert changed is False

def test_positions_migrate_unique_legacy_id():
    module = load_module()
    apps = [{"id": "foo-bar.desktop", "legacy_id": "bar"}]
    positions, changed = module.migrate_positions({"bar": 7}, apps)
    assert positions == {"foo-bar.desktop": 7}
    assert changed is True

def test_positions_do_not_guess_ambiguous_id():
    module = load_module()
    apps = [{"id": "foo-bar.desktop", "legacy_id": "bar"}, {"id": "baz-bar.desktop", "legacy_id": "bar"}]
    positions, changed = module.migrate_positions({"bar": 7}, apps)
    assert positions == {"bar": 7}
    assert changed is False
