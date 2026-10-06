#!/usr/bin/env python3
"""Regression contract for Mavericks-style controls in native System Settings."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/mavericks-apps/src/mavericks-apps/bin/mv-settings"
TEXT = SOURCE.read_text(encoding="utf-8")
ast.parse(TEXT)

assert "Gtk.Switch" not in TEXT
assert "Gtk.CheckButton()" in TEXT
assert 'toggle.set_active(st.get_boolean(key))' in TEXT
assert 'wrap.set_active(ch.get_bool("general/wrap_workspaces", False))' in TEXT
assert 'lock.set_active(st.get_boolean("lock-enabled"))' in TEXT
assert 'mute.set_active("yes" in mute_raw.lower())' in TEXT
assert 'notify::active' in TEXT

print("test-mv-settings-controls: passed")
