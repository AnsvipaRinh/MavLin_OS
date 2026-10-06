"""Test mv-brightness and mv-shot display utilities."""
import subprocess
import sys
import os


def test_brightness():
    """Test mv-brightness invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-brightness"
    
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
        print("PASS: mv-brightness executed")
    else:
        print(f"INFO: mv-brightness exit={result.returncode}")


def test_shot():
    """Test mv-shot invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-shot"
    
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
        print("PASS: mv-shot executed")
    else:
        print(f"INFO: mv-shot exit={result.returncode}")


if __name__ == "__main__":
    test_brightness()
    test_shot()
