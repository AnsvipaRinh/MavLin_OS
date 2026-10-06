"""Regression contracts for Global Dialogs migration batch 3."""

from pathlib import Path

BIN = Path(__file__).parents[1] / "bin"
CONSUMERS = ("mv-shot", "mv-keychain", "mv-airdrop")


def test_batch3_consumers_use_shared_dialogs():
    for name in CONSUMERS:
        source = (BIN / name).read_text(encoding="utf-8")
        assert "mv_dialogs" in source
        assert "/usr/share/mavericks-apps" in source
        assert "Gtk.MessageDialog" not in source


def test_batch3_preserves_nonblocking_screenshot_error_path():
    source = (BIN / "mv-shot").read_text(encoding="utf-8")
    assert 'if not HAVE_GTK or not interactive:' in source
    assert 'alert(' in source
