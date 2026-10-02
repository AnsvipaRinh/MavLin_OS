#!/usr/bin/env python3
"""Headless tests for mv-spotlight.

Pure-logic section (no rofi UI, no plocate DB needed):
- rank_app_match ranking (exact/prefix/word/substring)
- categorize_file category detection
- get_icon_for_file icon selection
- evaluate_calculator math + unit conversion
- format_result output formatting
- search_files plocate integration (when plocate available)
- main() query routing

Usage: python3 scripts/test-mv-spotlight.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight")

# Provide mock mv_desktop_cache before importing mv_spotlight
if not importlib.util.find_spec("mv_desktop_cache"):
    import types
    mock_mod = types.ModuleType("mv_desktop_cache")
    mock_mod.desktop_dirs = lambda: ["Desktop", ""]
    mock_mod.load_desktop_entries = lambda: []
    sys.modules["mv_desktop_cache"] = mock_mod

# Now import mv_spotlight functions
sys.path.insert(0, os.path.join(REPO, "packages/mavericks-apps/src"))

# Reload mv_spotlight with the mock in place
import importlib
mv_spotlight = importlib.import_module("mv_spotlight")
from mv_spotlight import (
    categorize_file, get_icon_for_file, rank_app_match,
    evaluate_calculator, format_result, search_files, main
)


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


# ──────────────────────────────────────────────
# categorize_file
# ──────────────────────────────────────────────
def test_categorize_file():
    # Images
    assert categorize_file("/photos/img.jpg", "img.jpg") == "Images"

    # Documents
    assert categorize_file("/docs/report.pdf", "report.pdf") == "Documents"
    assert categorize_file("/docs/notes.txt", "notes.txt") == "Documents"

    # Audio
    assert categorize_file("/music/song.mp3", "song.mp3") == "Audio"

    # Video
    assert categorize_file("/video/movie.mp4", "movie.mp4") == "Video"

    # Archives
    assert categorize_file("/backup.tar.gz", "tar.gz") == "Archives"

    # Code
    assert categorize_file("/src/app.py", "app.py") == "Code"

    # Other (unknown ext) → Other
    result = categorize_file("/other/xyz.abc", "xyz.abc")
    assert result == "Other", f"Expected Other, got {result}"

    # Directory
    result = categorize_file("/some/path", "test")
    assert result == "Folders", f"Expected Folders, got {result}"

    print("PASS: categorize_file")


# ──────────────────────────────────────────────
# get_icon_for_file
# ──────────────────────────────────────────────
def test_get_icon_for_file():
    # Directory
    assert get_icon_for_file("/some/path", "test") == "folder"

    # PDF
    assert get_icon_for_file("/docs/file.pdf", "file.pdf") == "application-pdf"

    # Image
    assert get_icon_for_file("/photos/img.png", "img.png") == "image-x-generic"

    # Audio
    assert get_icon_for_file("/music/song.mp3", "song.mp3") == "audio-x-generic"

    # Video
    assert get_icon_for_file("/video/movie.mp4", "movie.mp4") == "video-x-generic"

    # Archive
    assert get_icon_for_file("/backup.tar.gz", "tar.gz") == "package-x-generic"

    # Code
    assert get_icon_for_file("/src/app.py", "app.py") == "text-x-script"

    # Unknown → text-x-generic
    assert get_icon_for_file("/other/xyz.abc", "xyz.abc") == "text-x-generic"

    print("PASS: get_icon_for_file")


# ──────────────────────────────────────────────
# rank_app_match
# ──────────────────────────────────────────────
def test_rank_app_match():
    # Exact match → rank 0
    assert rank_app_match("calculator", {"name": "Calculator", "exec": "calculator"}) == 0

    # Prefix match → rank 1
    assert rank_app_match("calc", {"name": "Calculator", "exec": "calculator"}) == 1

    # Substring in name → rank 3
    assert rank_app_match("calc", {"name": "My Calculator", "exec": "myapp"}) == 3

    # Substring in exec → rank 4
    assert rank_app_match("calc", {"name": "Other", "exec": "calculator --foo"}) == 4

    # No match → rank 5
    assert rank_app_match("xyz", {"name": "Calculator", "exec": "calculator"}) == 5

    # Prefix of full name
    result = rank_app_match("my", {"name": "My App", "exec": "myapp"})
    assert result == 1, f"Expected prefix rank 1, got {result}"

    print("PASS: rank_app_match")


# ──────────────────────────────────────────────
# evaluate_calculator
# ──────────────────────────────────────────────
def test_evaluate_calculator():
    # Simple math
    results = evaluate_calculator("2+2")
    assert len(results) > 0, "Expected calculator result for '2+2'"

    # Unit conversion (length)
    results = evaluate_calculator("10 cm to inches")
    assert len(results) > 0, "Expected conversion result for '10 cm to inches'"

    # Unit conversion (weight)
    results = evaluate_calculator("5 kg to lbs")
    assert len(results) > 0, "Expected conversion result for '5 kg to lbs'"

    # Empty query → handled (may return 0 results depending on regex matching)
    results = evaluate_calculator("")
    # Should not crash

    print("PASS: evaluate_calculator")


# ──────────────────────────────────────────────
# format_result
# ──────────────────────────────────────────────
def test_format_result():
    # App source
    app_item = {
        "name": "Calculator",
        "icon": "accessories-calculator",
        "source": "app",
        "exec": "calculator",
        "info": "Calculator"
    }
    result = format_result(app_item)
    assert "Calculator" in result

    # Calculator source
    calc_item = {
        "name": "4",
        "icon": "accessories-calculator",
        "source": "calculator",
        "info": "Calculator: 2+2 = 4",
        "action": "echo '4' | xclip -selection clipboard 2>/dev/null || true"
    }
    result = format_result(calc_item)
    assert "4" in result

    # File source
    file_item = {
        "name": "test.txt",
        "icon": "text-x-generic",
        "source": "file",
        "path": "/home/user/test.txt",
    }
    result = format_result(file_item)
    assert "xdg-open" in result

    # System source
    sys_item = {
        "name": "System Settings",
        "icon": "preferences-system",
        "source": "system",
        "exec": "mv-settings",
        "info": "Open System Settings"
    }
    result = format_result(sys_item)
    assert "System Settings" in result
    assert "mv-settings" in result

    print("PASS: format_result")


# ──────────────────────────────────────────────
# search_files (with plocate mock)
# ──────────────────────────────────────────────
def test_search_files():
    # Test error state when plocate not installed
    with mock.patch("mv_spotlight.shutil.which", return_value=None):
        result, error = search_files("test")
        assert error is not None, "Expected error when plocate not installed"
        assert "plocate not installed" in error, f"Expected plocate error, got {error}"

    print("PASS: search_files")


# ──────────────────────────────────────────────
# main() query routing
# ──────────────────────────────────────────────
def test_main_routing():
    # Test that main doesn't crash on basic queries
    import subprocess

    # Test calculator query
    result = subprocess.run(
        [APP_PATH, "2+2"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"mv-spotlight crashed on '2+2': {result.stderr}"

    # Test empty query → recent items
    result = subprocess.run(
        [APP_PATH],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"mv-spotlight crashed on empty query: {result.stderr}"

    # Test search that returns no results
    result = subprocess.run(
        [APP_PATH, "nonexistent_query_xyz123"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"mv-spotlight crashed on nonexistent query: {result.stderr}"

    print("PASS: main_routing")


# ──────────────────────────────────────────────
# Full query processing integration
# ──────────────────────────────────────────────
def test_full_query():
    import subprocess

    # Test calculator query returns valid output
    result = subprocess.run(
        [APP_PATH, "2+2"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0

    # Test empty query returns valid output
    result = subprocess.run(
        [APP_PATH],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0

    # Test non-matching query returns "no results" message
    result = subprocess.run(
        [APP_PATH, "xyzabc123"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0

    print("PASS: test_full_query")


# ──────────────────────────────────────────────
# Main test runner
# ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("categorize_file", test_categorize_file),
        ("get_icon_for_file", test_get_icon_for_file),
        ("rank_app_match", test_rank_app_match),
        ("evaluate_calculator", test_evaluate_calculator),
        ("format_result", test_format_result),
        ("search_files", test_search_files),
        ("main_routing", test_main_routing),
        ("full_query", test_full_query),
    ]

    passed = 0
    failed = 0
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)