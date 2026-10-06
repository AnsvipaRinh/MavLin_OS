from pathlib import Path


def test_password_dialog_contract():
    source = (Path(__file__).parents[1] / 'bin' / 'mv_dialogs.py').read_text(encoding='utf-8')
    assert 'def password_dialog(' in source
    assert 'entry.set_visibility(False)' in source


def test_timemachine_uses_shared_dialogs():
    source = (Path(__file__).parents[1] / 'bin' / 'mv-timemachine').read_text(encoding='utf-8')
    assert 'password_dialog(' in source
    assert 'confirm_delete(' in source
    assert 'Gtk.MessageDialog' not in source
