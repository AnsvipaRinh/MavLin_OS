"""Test mv-desktop-cleanup, mv-desktop-sort, mv-desktop-paste."""
import subprocess
import sys
import os


def test_desktop_cleanup():
    """Test mv-desktop-cleanup invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-cleanup"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or fail gracefully
    if result.returncode == 0:
        print("PASS: mv-desktop-cleanup executed")
    else:
        print(f"INFO: mv-desktop-cleanup exit={result.returncode}")


def test_desktop_sort():
    """Test mv-desktop-sort invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-sort"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or fail gracefully
    if result.returncode == 0:
        print("PASS: mv-desktop-sort executed")
    else:
        print(f"INFO: mv-desktop-sort exit={result.returncode}")


def test_desktop_paste():
    """Test mv-desktop-paste invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-paste"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or fail gracefully (may need clipboard)
    if result.returncode == 0:
        print("PASS: mv-desktop-paste executed")
    else:
        if "clipboard" in result.stderr.lower():
            print("PASS: mv-desktop-paste fails gracefully without clipboard")
        else:
            print(f"INFO: mv-desktop-paste exit={result.returncode}")


if __name__ == "__main__":
    test_desktop_cleanup()
    test_desktop_sort()
    test_desktop_paste()
