"""Regression contracts for Global Dialogs migration batch 2."""

from pathlib import Path

BIN = Path(__file__).parents[1] / "bin"
CONSUMERS = ("mv-finder-search", "mv-force-quit", "mv-hotkeys-gui")


def test_batch2_consumers_use_shared_dialogs():
    for name in CONSUMERS:
        source = (BIN / name).read_text(encoding="utf-8")
        assert "from mv_dialogs import alert" in source
        assert "Gtk.MessageDialog" not in source


def test_batch2_uses_mavericks_error_surfaces():
    search = (BIN / "mv-finder-search").read_text(encoding="utf-8")
    force = (BIN / "mv-force-quit").read_text(encoding="utf-8")
    hotkeys = (BIN / "mv-hotkeys-gui").read_text(encoding="utf-8")
    assert 'msg_type=Gtk.MessageType.ERROR' in search
    assert 'msg_type=Gtk.MessageType.ERROR' in force
    assert 'default=Gtk.ResponseType.CANCEL' in hotkeys
    assert 'destructive=True' in hotkeys
