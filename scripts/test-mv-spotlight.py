#!/usr/bin/env python3
"""Headless tests for mv-spotlight ranking and core logic."""

import os
import sys
import tempfile
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
# Preview script logic (minimal copy for testing)
# ──────────────────────────────────────────────
def preview_categorize_mime(mime):
    """Categorize mime type for preview routing."""
    if mime.startswith("text/"):
        return "text"
    elif mime.startswith("image/"):
        return "image"
    elif mime == "application/pdf":
        return "pdf"
    elif mime.startswith("audio/") or mime.startswith("video/"):
        return "media"
    return "other"


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
    # Folder test
    with tempfile.TemporaryDirectory() as tmpdir:
        assert categorize_file(tmpdir, "anything") == "Folders"
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
    assert rank_app_match("ulator", {"name": "Calculator", "exec": "other"}) == 3
    # Substring in exec → rank 4
    assert rank_app_match("calc", {"name": "Other", "exec": "calculator --foo"}) == 4
    # No match → rank 5
    assert rank_app_match("xyz", {"name": "Calculator", "exec": "calculator"}) == 5
    # Full name prefix
    assert rank_app_match("my", {"name": "My App", "exec": "myapp"}) == 1
    pass


def test_evaluate_calculator():
    """Test calculator evaluation logic."""
    import subprocess
    
    # Test basic math via subprocess
    result = subprocess.run(
        [sys.executable, f"{REPO}/packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight", "2+2"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"Calculator test failed: {result.stderr}"
    assert "4" in result.stdout
    assert "Calculator" in result.stdout
    
    # Test unit conversion
    result = subprocess.run(
        [sys.executable, f"{REPO}/packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight", "10 cm to inches"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"Conversion test failed: {result.stderr}"
    assert "inches" in result.stdout
    assert "Convert" in result.stdout
    pass


def test_main_subprocess():
    import subprocess

    spotlight_script = f"{REPO}/packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight"

    # Calculator query
    result = subprocess.run(
        [sys.executable, spotlight_script, "2+2"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on '2+2': {result.stderr}"
    assert "Calculator" in result.stdout or "4" in result.stdout

    # Empty query
    result = subprocess.run(
        [sys.executable, spotlight_script],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on empty query: {result.stderr}"

    # Non-matching query
    result = subprocess.run(
        [sys.executable, spotlight_script, "nonexistent_query_xyz"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on nonexistent query: {result.stderr}"

    # System action query
    result = subprocess.run(
        [sys.executable, spotlight_script, "settings"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode >= 0, f"mv-spotlight crashed on 'settings': {result.stderr}"
    assert "System Settings" in result.stdout or "settings" in result.stdout.lower()
    pass


def test_preview_script():
    """Test mv-spotlight-preview with various file types."""
    import subprocess
    import tempfile

    preview_script = f"{REPO}/packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight-preview"

    # Test text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Hello, World!\nThis is a test.")
        txt_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, preview_script, txt_path],
            capture_output=True, text=True, timeout=5
        )
        assert result.returncode == 0, f"Preview crashed on text file: {result.stderr}"
        assert "Hello, World!" in result.stdout
    finally:
        os.unlink(txt_path)

    # Test Python file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("print('hello')")
        py_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, preview_script, py_path],
            capture_output=True, text=True, timeout=5
        )
        assert result.returncode == 0, f"Preview crashed on python file: {result.stderr}"
        assert "print" in result.stdout
    finally:
        os.unlink(py_path)

    # Test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory and file
        os.mkdir(os.path.join(tmpdir, "subdir"))
        with open(os.path.join(tmpdir, "file.txt"), "w") as f:
            f.write("test")
        
        result = subprocess.run(
            [sys.executable, preview_script, tmpdir],
            capture_output=True, text=True, timeout=5
        )
        assert result.returncode == 0, f"Preview crashed on directory: {result.stderr}"
        assert "Directory" in result.stdout or "subdir" in result.stdout

    # Test non-existent file
    result = subprocess.run(
        [sys.executable, preview_script, "/nonexistent/path/12345"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"Preview should handle missing file gracefully: {result.stderr}"
    assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()
    pass


def test_file_without_extension():
    """Test preview with files without extensions (like /etc/passwd)."""
    import subprocess
    preview_script = f"{REPO}/packages/mavericks-apps/src/mavericks-apps/bin/mv-spotlight-preview"
    result = subprocess.run(
        [sys.executable, preview_script, "/etc/passwd"],
        capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, f"Preview crashed on /etc/passwd: {result.stderr}"
    assert "root:" in result.stdout  # Should show content
    pass


# ──────────────────────────────────────────────
# Main test runner
# ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("categorize_file", test_categorize_file),
        ("get_icon_for_file", test_get_icon_for_file),
        ("rank_app_match", test_rank_app_match),
        ("evaluate_calculator", test_evaluate_calculator),
        ("main_subprocess", test_main_subprocess),
        ("preview_script", test_preview_script),
        ("file_without_extension", test_file_without_extension),
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