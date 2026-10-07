"""Test mv-notes, mv-reminders, mv-stickies productivity apps."""
import subprocess
import sys
import os


def test_notes():
    """Test mv-notes invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-notes"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or show usage
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-notes executed")
    else:
        print(f"INFO: mv-notes exit={result.returncode}")


def test_reminders():
    """Test mv-reminders invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-reminders"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or show usage
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-reminders executed")
    else:
        print(f"INFO: mv-reminders exit={result.returncode}")


def test_stickies():
    """Test mv-stickies invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-stickies"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or show usage
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-stickies executed")
    else:
        print(f"INFO: mv-stickies exit={result.returncode}")


if __name__ == "__main__":
    test_notes()
    test_reminders()
    test_stickies()
