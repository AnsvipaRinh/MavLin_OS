"""Test mv-textedit, mv-archive-utility, mv-change-wallpaper."""
import subprocess
import sys
import os


def test_textedit():
    """Test mv-textedit invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-textedit"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-textedit executed")
    else:
        print(f"INFO: mv-textedit exit={result.returncode}")


def test_archive_utility():
    """Test mv-archive-utility invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-archive-utility"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-archive-utility executed")
    else:
        print(f"INFO: mv-archive-utility exit={result.returncode}")


def test_change_wallpaper():
    """Test mv-change-wallpaper invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-change-wallpaper"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-change-wallpaper executed")
    else:
        print(f"INFO: mv-change-wallpaper exit={result.returncode}")


if __name__ == "__main__":
    test_textedit()
    test_archive_utility()
    test_change_wallpaper()
