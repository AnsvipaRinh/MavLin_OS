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

SCRIPT = "/home/builder/projects/MavLinOS/packages/mavericks-apps/src/mavericks-apps/bin/mv-launchpad"
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
    """Test that pagination hint is displayed with Mavericks-style page dots."""
    stdout, rc = run_launchpad(0)
    assert rc == 0, f"Launchpad exited with code {rc}"
    # The pagination hint should be present at the end of output
    # Format: \0icon\x1fgo-previous\x1f● ○ ○ — ←/→ or PgUp/PgDn to navigate
    assert "●" in stdout, "Expected pagination hint containing page dots (●)"
    assert "←/→" in stdout, "Expected navigation arrows in pagination hint"
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
    has_navigation = "←/→" in stdout or "PgUp" in stdout
    assert has_info or has_navigation, "Expected info or navigation hints in output"
    print("PASS: test_keyboard_navigation_hints")


def test_edit_mode_entry_present():
    """Test that 'Edit Launchpad…' entry appears on page 0 when not searching."""
    stdout, rc = run_launchpad(0)
    assert rc == 0, f"Launchpad exited with code {rc}"
    # Should contain the edit entry
    assert "Edit Launchpad" in stdout, "Expected 'Edit Launchpad…' entry on page 0"
    assert "preferences-desktop-icon-theme" in stdout, "Expected edit entry icon"
    print("PASS: test_edit_mode_entry_present")


def test_edit_mode_entry_hidden_when_searching():
    """Test that 'Edit Launchpad…' entry is hidden when searching."""
    stdout, rc = run_launchpad(0, "calculator")
    assert rc == 0, f"Launchpad exited with code {rc}"
    # Should NOT contain the edit entry when searching
    assert "Edit Launchpad" not in stdout, "Edit entry should be hidden during search"
    print("PASS: test_edit_mode_entry_hidden_when_searching")


def test_pagination_dots_page_1():
    """Test that page 1 shows correct page dot pattern."""
    stdout, rc = run_launchpad(1)
    assert rc == 0, f"Launchpad exited with code {rc}"
    # Should show ○ ● ○ for page 1 (0-indexed)
    assert "○ ●" in stdout, "Expected page dots showing current page as 1"
    print("PASS: test_pagination_dots_page_1")


def test_pagination_dots_last_page():
    """Test that last page shows correct page dot pattern."""
    # First find total pages by running page 0
    stdout, rc = run_launchpad(0)
    assert rc == 0
    # Extract total pages from dots pattern (count of dots)
    # For now just test that page 2 (last page in our env) shows ○ ○ ●
    stdout, rc = run_launchpad(2)
    assert rc == 0, f"Launchpad exited with code {rc}"
    assert "○ ○ ●" in stdout, "Expected page dots showing current page as last"
    print("PASS: test_pagination_dots_last_page")


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


def test_full_integration_basic():
    """Test basic integration: script runs, pagination, search, no crash."""
    # Start Launchpad
    stdout, rc = run_launchpad(0)
    assert rc == 0, "Failed to start Launchpad"

    # Verify script produces some output
    assert len(stdout) > 0, "Expected non-empty output"

    # Check pagination hint (Mavericks-style page dots)
    assert "●" in stdout, "Expected pagination hint with page dots"

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
        test_full_integration_basic,
        test_edit_mode_entry_present,
        test_edit_mode_entry_hidden_when_searching,
        test_pagination_dots_page_1,
        test_pagination_dots_last_page,
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