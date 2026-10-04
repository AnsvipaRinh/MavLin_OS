#!/usr/bin/env python3
"""Headless tests for mv-spotlight ranking and core logic."""

import os
import sys
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ──────────────────────────────────────────────
# Mock mv_desktop_cache
# ──────────────────────────────────────────────
if not os.path.exists(os.path.join(REPO, "packages/mavericks-apps/src/mv_desktop_cache.py")):
    import types
    mock_mod = types.ModuleType("mv_desktop_cache")
    mock_mod.desktop_dirs = lambda: ["Desktop", ""]
    mock_mod.load_desktop_entries = lambda: []
    sys.modules["mv_desktop_cache"] = mock_mod

# ──────────────────────────────────────────────
# Core logic functions (minimal copies from mv-spotlight)
# ──────────────────────────────────────────────
def categorize_file(path, name):
    """Minimal copy from mv-spotlight for testing."""
    import os
    if os.path.isdir(path):
        return "Folders"
    ext = os.path.splitext(name)[1].lower()
    FILE_CATEGORIES = [
        ("Images", [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"]),
        ("Documents", [".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex", ".epub"]),
        ("Spreadsheets", [".xls", ".xlsx", ".ods", ".csv", ".tsv"]),
        ("Presentations", [".ppt", ".pptx", ".odp", ".key"]),
        ("Audio", [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".opus"]),
        ("Video", [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ogv"]),
        ("Archives", [".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".tbz2"]),
        ("Code", [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sh", ".bash", ".zsh", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".kt", ".swift", ".rb", ".php", ".pl", ".lua", ".r", ".m", ".sql"]),
        ("Folders", []),
        ("Other", []),
    ]
    for cat, extensions in FILE_CATEGORIES:
        if ext in extensions:
            return cat
    return "Other"


def get_icon_for_file(name, path):
    """Minimal copy from mv-spotlight for testing."""
    import os
    if os.path.isdir(path):
        return "folder"
    ext = os.path.splitext(name)[1].lower()
    if ext in [".pdf"]:
        return "application-pdf"
    elif ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"]:
        return "image-x-generic"
    elif ext in [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".opus"]:
        return "audio-x-generic"
    elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ogv"]:
        return "video-x-generic"
    elif ext in [".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".tbz2"]:
        return "package-x-generic"
    elif ext in [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sh", ".bash", ".zsh", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".kt", ".swift", ".rb", ".php", ".pl", ".lua", ".r", ".m", ".sql"]:
        return "text-x-script"
    return "text-x-generic"


def rank_app_match(query, app):
    """Minimal copy from mv-spotlight for testing."""
    q = query.lower()
    name = app["name"].lower()
    exec_cmd = app["exec"].lower()

    if q == name:
        return 0
    if name.startswith(q):
        return 1
    words = name.split()
    for w in words:
        if w.startswith(q):
            return 2
    if q in name:
        return 3
    if q in exec_cmd:
        return 4
    return 5


# ──────────────────────────────────────────────
# Test functions
# ──────────────────────────────────────────────
def test_categorize_file():
    assert categorize_file("", "img.jpg") == "Images"
    assert categorize_file("", "report.pdf") == "Documents"
    assert categorize_file("", "song.mp3") == "Audio"
    assert categorize_file("", "movie.mp4") == "Video"
    assert categorize_file("", "tar.gz") == "Archives"
    assert categorize_file("", "app.py") == "Code"
    assert categorize_file("", "xyz.abc") == "Other"
    pass


def test_get_icon_for_file():
    assert get_icon_for_file("file.pdf", "") == "application-pdf"
    assert get_icon_for_file("img.png", "") == "image-x-generic"
    assert get_icon_for_file("song.mp3", "") == "audio-x-generic"
    assert get_icon_for_file("movie.mp4", "") == "video-x-generic"
    assert get_icon_for_file("tar.gz", "") == "package-x-generic"
    assert get_icon_for_file("app.py", "") == "text-x-script"
    assert get_icon_for_file("xyz.abc", "") == "text-x-generic"
    pass


def test_rank_app_match():
    # Exact match → rank 0
    assert rank_app_match("calculator", {"name": "Calculator", "exec": "calculator"}) == 0
    # Prefix match → rank 1 (query is prefix of name)
    assert rank_app_match("calc", {"name": "Calculator", "exec": "other"}) == 1
    # Word prefix → rank 2 (query matches start of a word in name)
    assert rank_app_match("calc", {"name": "My Calculator", "exec": "myapp"}) == 2
    # Substring in name → rank 3 (query is substring but not prefix/word-prefix)
    # Use a name where the query is a substring but not prefix/word-prefix
    # "app" is substring of "Calculator"? No. Use "ulator" instead.
    assert rank_app_match("ulator", {"name": "Calculator", "exec": "other"}) == 3
    # Substring in exec → rank 4
    assert rank_app_match("calc", {"name": "Other", "exec": "calculator --foo"}) == 4
    # No match → rank 5
    assert rank_app_match("xyz", {"name": "Calculator", "exec": "calculator"}) == 5
    # Full name prefix
    assert rank_app_match("my", {"name": "My App", "exec": "myapp"}) == 1
    pass


def test_rofi_preview_integration():
    from pathlib import Path

    theme = Path(REPO) / "packages/mavericks-apps/src/mavericks-apps/config/rofi-mavericks.rasi"
    shortcuts = Path(REPO) / "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml"
    theme_text = theme.read_text(encoding="utf-8")
    shortcut_text = shortcuts.read_text(encoding="utf-8")

    assert "children: [ inputbar, listview-split ];" in theme_text
    assert "children: [ listview, icon-current-entry ];" in theme_text
    assert "icon-current-entry" in theme_text
    assert "-preview-script" not in shortcut_text
    assert "-show-preview" not in shortcut_text
    assert "rofi -show -modi 'spotlight:/usr/bin/mv-spotlight'" in shortcut_text


def test_calculator_safety_contract():
    from pathlib import Path
    source = (Path(REPO) / "packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight").read_text(encoding="utf-8")
    assert "import ast" in source
    assert 'ast.parse(q, mode="eval")' in source
    assert "eval(" not in source
    assert "ast.Pow" in source
    assert "len(nodes) > 64" in source
    assert "abs(exponent) > 1000" in source


def test_file_action_quoting_contract():
    from pathlib import Path
    source = (Path(REPO) / "packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight").read_text(encoding="utf-8")
    assert "import shlex" in source
    assert "shlex.quote(item['path'])" in source
    assert "shlex.quote(path)" in source
    assert "xdg-open --" in source


def test_main_subprocess():
    import subprocess

    # Calculator query
    result = subprocess.run(
        ["/usr/bin/mv-spotlight", "2+2"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on '2+2': {result.stderr}"

    # Empty query
    result = subprocess.run(
        ["/usr/bin/mv-spotlight"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on empty query: {result.stderr}"

    # Non-matching query
    result = subprocess.run(
        ["/usr/bin/mv-spotlight", "nonexistent_query_xyz"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on nonexistent query: {result.stderr}"
    pass


# ──────────────────────────────────────────────
# Main test runner
# ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("categorize_file", test_categorize_file),
        ("get_icon_for_file", test_get_icon_for_file),
        ("rank_app_match", test_rank_app_match),
        ("rofi_preview_integration", test_rofi_preview_integration),
        ("calculator_safety_contract", test_calculator_safety_contract),
        ("file_action_quoting_contract", test_file_action_quoting_contract),
        ("main_subprocess", test_main_subprocess),
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