from pathlib import Path


SOURCE = Path("packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns")


def test_finder_exposes_uri_drag_source():
    text = SOURCE.read_text()
    assert 'row.drag_source_set' in text
    assert 'selection_data.set_uris' in text
    assert 'Gdk.DragAction.MOVE' in text


def test_finder_drops_into_directory_and_moves_files():
    text = SOURCE.read_text()
    assert '_drop_directory' in text
    assert 'shutil.move(source_abs, destination)' in text
    assert 'os.path.exists(destination)' in text


def test_finder_rejects_recursive_directory_drop():
    text = SOURCE.read_text()
    assert 'os.path.commonpath' in text
    assert 'source_abs, target_abs' in text


def test_finder_refreshes_after_successful_drop():
    text = SOURCE.read_text()
    assert 'context.drag_finish(bool(moved), False, time_)' in text
    assert 'if moved:' in text
    assert 'self.rebuild_columns()' in text
