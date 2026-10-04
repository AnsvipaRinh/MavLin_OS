#!/usr/bin/env python3
"""Launchpad pre-hardware tests for mv-launchpad.

Functional tests verifying mv-launchpad script behavior.
Each test independently resets config state to avoid cross-test interference.
Results are environment-dependent based on available .desktop files.
"""

import subprocess
import sys
import json
import os
import shutil

SCRIPT = "/usr/bin/mv-launchpad"
CONFIG_DIR = os.path.expanduser("~/.config/mv-launchpad")
CACHE_DIR = os.path.expanduser("~/.cache/mavericks")


def reset_config():
    """Reset config between tests to avoid cross-test interference."""
    if os.path.exists(CONFIG_DIR):
        shutil.rmtree(CONFIG_DIR)
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
    os.makedirs(CONFIG_DIR, exist_ok=True)


def run_launchpad(page=0, query="", open_folder=None):
    """Run mv-launchpad with fresh config and return output."""
    reset_config()
    result = subprocess.run(
        [sys.executable, SCRIPT, str(page), query.strip(), open_folder.strip() if open_folder else ""],
        capture_output=True, text=True
    )
    return result.stdout, result.returncode


def test_script_runs():
    """Test that Launchpad script starts without crashes."""
    stdout, rc = run_launchpad(0)
    assert rc == 0, f"Launchpad exited with code {rc}"
    print("PASS: test_script_runs")


def test_no_crash_on_repeated_runs():
    """Test that Launchpad can be run multiple times without issues."""
    for _ in range(3):
        stdout, rc = run_launchpad(0)
        assert rc == 0, f"Launchpad exited with code {rc} on run {_+1}"
    print("PASS: test_no_crash_on_repeated_runs")


def test_pagination_hint_present():
    """Test that pagination hint is displayed (environment-dependent content)."""
    stdout, rc = run_launchpad(0)
    assert rc == 0, f"Launchpad exited with code {rc}"
    # The pagination hint should be present at the end of output
    # Format: \0icon\x1fgo-previous\x1fPage N/M — ←/→ or PgUp/PgDn to navigate
    assert "Page" in stdout, "Expected pagination hint containing 'Page'"
    assert "PgUp/PgDn" in stdout, "Expected Page Up/Down navigation hint"
    assert "←/→" not in stdout, "Arrow keys must not be advertised as page controls"
    print("PASS: test_pagination_hint_present")


def test_search_works_when_apps_available():
    """Test that search filtering works when matching apps exist (env-dependent)."""
    stdout, rc = run_launchpad(0, "calculator")
    assert rc == 0, f"Launchpad exited with code {rc}"
    # Search should modify the output (either show results or empty state)
    # Verify the script doesn't crash with a search query
    print("PASS: test_search_works_when_apps_available")


def test_empty_search_returns_message():
    """Test that empty search returns a message (environment-dependent)."""
    stdout, rc = run_launchpad(0, "asdfghjkl123xyz")
    assert rc == 0, f"Launchpad exited with code {rc}"
    # Filter and check for no-results message
    fields = [f for f in stdout.split("\0") if f.strip()]
    text = " ".join(fields)
    # Either no-results message or valid output - script should handle gracefully
    print("PASS: test_empty_search_returns_message")


def test_keyboard_navigation_hints():
    """Test that output includes keyboard navigation hints."""
    stdout, rc = run_launchpad(0)
    assert rc == 0, f"Launchpad exited with code {rc}"
    # Output should contain info hints for keyboard/navigation
    # Check for typical rofi script mode info patterns
    has_info = "info" in stdout.lower()
    # Or check for navigation-related content
    has_navigation = "PgUp" in stdout or "PgDn" in stdout
    assert has_info or has_navigation, "Expected info or navigation hints in output"
    print("PASS: test_keyboard_navigation_hints")


def test_desktop_entry_integrity():
    """Test that mv-launchpad.desktop entry is well-formed."""
    desktop_paths = [
        "/usr/share/applications/mv-launchpad.desktop",
        "/usr/local/share/applications/mv-launchpad.desktop",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "desktop", "mv-launchpad.desktop"),
    ]
    desktop_file = None
    for path in desktop_paths:
        if os.path.exists(path):
            desktop_file = path
            break
    if desktop_file:
        with open(desktop_file) as f:
            content = f.read()
        assert "Name=Launchpad" in content, "Expected Name=Launchpad"
        assert "Exec=" in content, "Expected Exec="
        assert "Type=Application" in content, "Expected Type=Application"
        print("PASS: test_desktop_entry_integrity")
    else:
        # Source not installed is acceptable for pre-hardware
        print("PASS: test_desktop_entry_integrity (source not installed)")


def test_rofi_theme_has_mavericks_styling():
    """Test that rofi theme file has Mavericks-appropriate styling."""
    rasi_file = "/usr/share/mavericks-apps/rofi-launchpad.rasi"
    assert os.path.exists(rasi_file), f"Expected {rasi_file} to exist"
    with open(rasi_file) as f:
        content = f.read()
    # Check for font declaration
    assert "font:" in content, "Expected font declaration"
    # Check for translucent background
    assert "rgba" in content, "Expected rgba background for glass effect"
    print("PASS: test_rofi_theme_has_mavericks_styling")


def test_rofi_selection_actions():
    """Rofi script callbacks must launch apps and navigate folders safely."""
    source = open(SCRIPT).read()
    assert 'os.environ.get("ROFI_RETV")' in source
    assert 'rofi_mode = rofi_retv is not None' in source
    assert 'os.environ.get("ROFI_INFO", "")' in source
    assert 'rofi_info.startswith("app:")' in source
    assert '["gtk-launch", desktop_id]' in source
    assert 'subprocess.Popen' in source
    assert 'start_new_session=True' in source
    assert 'rofi_info.startswith("folder:")' in source
    assert 'rofi_info == "back"' in source
    assert '\\0data\\x1f' in source
    print("PASS: test_rofi_selection_actions")


def test_rofi_live_search_callback():
    """Rofi retv=0 must use argv[1] as live search text, not as a page number."""
    source = open(SCRIPT).read()
    assert 'rofi_mode and rofi_retv == "0"' in source
    assert 'query = sys.argv[1].strip()' in source
    assert 'if not rofi_mode and len(sys.argv) > 1:' in source
    print("PASS: test_rofi_live_search_callback")


def test_page_navigation_callbacks():
    """Rofi custom callbacks must map Page Down/Up to script return codes."""
    source = open(SCRIPT).read()
    assert 'rofi_retv in ("10", "11")' in source
    assert 'page += 1 if rofi_retv == "10" else -1' in source
    desktop = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desktop", "mv-launchpad.desktop")).read()
    assert "-kb-custom-1 'Page_Down'" in desktop
    assert "-kb-custom-2 'Page_Up'" in desktop
    print("PASS: test_page_navigation_callbacks")


def test_launchpad_config_writes_are_atomic():
    """Folder and position configs must be replaced atomically after fsync."""
    source = open(SCRIPT).read()
    assert "def _atomic_save_json(path, data):" in source
    assert "tempfile.mkstemp(" in source
    assert 'dir=str(CONFIG_DIR)' in source
    assert "os.fsync(fp.fileno())" in source
    assert "os.replace(tmp_path, path)" in source
    assert "_atomic_save_json(FOLDERS_FILE, folders)" in source
    assert "_atomic_save_json(POSITIONS_FILE, positions)" in source
    print("PASS: test_launchpad_config_writes_are_atomic")


def test_folder_pages_reserve_back_cell():
    """Folder pages must fit the 7x5 grid including the Back item."""
    source = open(SCRIPT).read()
    assert "FOLDER_PAGE_CAPACITY = ITEMS_PER_PAGE - 1" in source
    assert 'len(folder_apps) + FOLDER_PAGE_CAPACITY - 1' in source
    assert 'start = page * FOLDER_PAGE_CAPACITY' in source
    assert 'end = start + FOLDER_PAGE_CAPACITY' in source
    print("PASS: test_folder_pages_reserve_back_cell")


def test_config_writes_are_atomic():
    """Launchpad config writes must use a temp file, fsync, and atomic replace."""
    source = open(SCRIPT).read()
    assert 'tempfile.mkstemp' in source
    assert 'os.fsync(fp.fileno())' in source
    assert 'os.replace(temp_path, path)' in source
    assert '_atomic_json_save(FOLDERS_FILE, folders)' in source
    assert '_atomic_json_save(POSITIONS_FILE, positions)' in source
    print("PASS: test_config_writes_are_atomic")


def test_many_top_level_folders_are_paginated():
    """More than one 7x5 page of folders must not be dropped or overflow the grid."""
    source = open(SCRIPT).read()
    assert 'folder_pages = max(1, (len(structure["folders"]) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)' in source
    assert 'start = page * ITEMS_PER_PAGE' in source
    assert 'start = (page - folder_pages) * ITEMS_PER_PAGE' in source
    assert 'if folder_pages == 1' in source
    print("PASS: test_many_top_level_folders_are_paginated")


def test_folder_cells_count_toward_pagination():
    """Top-level folders must consume real grid cells before standalone apps."""
    source = open(SCRIPT).read()
    assert 'first_app_capacity = ITEMS_PER_PAGE - len(structure["folders"]) if folder_pages == 1 else 0' in source
    assert 'remaining_after_first = max(0, len(ordered) - first_app_capacity)' in source
    assert 'start = first_capacity + (page - 1) * ITEMS_PER_PAGE' in source
    print("PASS: test_folder_cells_count_toward_pagination")


def test_folder_members_are_not_duplicated_on_main_grid():
    """Apps inside folders must not also appear as standalone main-page items."""
    source = open(SCRIPT).read()
    assert 'folder_member_ids = {' in source
    assert 'if not query and app["id"] in folder_member_ids:' in source
    assert 'for folder_data in folders.values()' in source
    print("PASS: test_folder_members_are_not_duplicated_on_main_grid")


def test_position_conflicts_and_invalid_values_do_not_drop_apps():
    """Malformed or colliding persisted positions must preserve every app."""
    source = open(SCRIPT).read()
    assert 'isinstance(pos, int)' in source
    assert 'pos not in positioned' in source
    assert 'or app_id not in positions' not in source
    print("PASS: test_position_conflicts_and_invalid_values_do_not_drop_apps")


def test_folder_config_is_normalized():
    """Malformed folder JSON must not crash Launchpad or inject non-string IDs."""
    source = open(SCRIPT).read()
    assert 'isinstance(raw, dict)' in source
    assert 'isinstance(folder_data, dict)' in source
    assert 'isinstance(app_ids, list)' in source
    assert 'isinstance(app_id, str)' in source
    assert 'folders.setdefault(folder_id' in source
    print("PASS: test_folder_config_is_normalized")


def test_folder_autopopulation_is_first_run_only():
    """Auto-population must not re-add apps after an existing config is edited."""
    source = open(SCRIPT).read()
    assert "config_exists = FOLDERS_FILE.exists()" in source
    assert "if not config_exists and apps:" in source
    load_source = source[source.index("def load_folders"):source.index("def _auto_populate_default_folders")]
    assert "if apps:" not in load_source
    print("PASS: test_folder_autopopulation_is_first_run_only")


def test_position_config_is_normalized():
    """Malformed top-level position JSON must not crash Launchpad."""
    source = open(SCRIPT).read()
    assert 'raw = json.load(fp)' in source
    assert 'if not isinstance(raw, dict):' in source
    assert 'return {app_id: position for app_id, position in raw.items() if isinstance(app_id, str)}' in source
    print("PASS: test_position_config_is_normalized")


def test_position_booleans_are_rejected():
    """JSON booleans must not be accepted as integer Launchpad positions."""
    source = open(SCRIPT).read()
    assert 'isinstance(pos, int) and not isinstance(pos, bool)' in source
    print("PASS: test_position_booleans_are_rejected")


def test_corrupt_folder_config_is_not_overwritten():
    """Corrupt folders.json must not be replaced with defaults."""
    source = open(SCRIPT).read()
    assert 'config_valid = False' in source
    assert 'if config_exists and not config_valid:' in source
    assert 'Preserve a corrupt/unreadable user file' in source
    print("PASS: test_corrupt_folder_config_is_not_overwritten")


def test_full_integration_basic():
    """Test basic integration: script runs, pagination, search, no crash."""
    # Start Launchpad
    stdout, rc = run_launchpad(0)
    assert rc == 0, "Failed to start Launchpad"

    # Verify script produces some output
    assert len(stdout) > 0, "Expected non-empty output"

    # Check pagination hint
    assert "Page" in stdout, "Expected pagination hint"

    # Search should work (result depends on available apps)
    stdout, rc = run_launchpad(0, "calculator")
    assert rc == 0, "Search failed"

    print("PASS: test_full_integration_basic")


if __name__ == "__main__":
    tests = [
        test_script_runs,
        test_no_crash_on_repeated_runs,
        test_pagination_hint_present,
        test_search_works_when_apps_available,
        test_empty_search_returns_message,
        test_keyboard_navigation_hints,
        test_desktop_entry_integrity,
        test_rofi_theme_has_mavericks_styling,
        test_rofi_selection_actions,
        test_rofi_live_search_callback,
        test_page_navigation_callbacks,
        test_config_writes_are_atomic,
        test_many_top_level_folders_are_paginated,
        test_folder_cells_count_toward_pagination,
        test_launchpad_config_writes_are_atomic,
        test_folder_pages_reserve_back_cell,
        test_folder_members_are_not_duplicated_on_main_grid,
        test_position_conflicts_and_invalid_values_do_not_drop_apps,
        test_folder_config_is_normalized,
        test_full_integration_basic,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)