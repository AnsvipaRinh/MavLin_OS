"""Regression contracts for Global Dialogs migration batch 4."""

from pathlib import Path

BIN = Path(__file__).parents[1] / "bin"


def test_voice_and_diskutil_use_shared_dialogs():
    voice = (BIN / "mv-voice").read_text(encoding="utf-8")
    disk = (BIN / "mv-diskutil").read_text(encoding="utf-8")
    assert "from mv_dialogs import alert, confirm_delete" in voice
    assert "Gtk.MessageDialog" not in voice
    assert "def _dialogs_module" in disk
    assert "raise RuntimeError(\"mv_dialogs shared helper is unavailable\")" in disk
    assert "Gtk.MessageDialog" not in disk


def test_voice_delete_uses_destructive_shared_contract():
    source = (BIN / "mv-voice").read_text(encoding="utf-8")
    assert "confirm_delete(" in source
    assert 'delete_label="Delete"' in source
