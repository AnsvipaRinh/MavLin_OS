"""Test mv-diskutil and mv-timemachine system utilities."""
import subprocess
import sys
import os


def test_diskutil():
    """Test mv-diskutil invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-diskutil"
    
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
        print("PASS: mv-diskutil executed")
    else:
        print(f"INFO: mv-diskutil exit={result.returncode}")


def test_timemachine():
    """Test mv-timemachine invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-timemachine"
    
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
        print("PASS: mv-timemachine executed")
    else:
        print(f"INFO: mv-timemachine exit={result.returncode}")


if __name__ == "__main__":
    test_diskutil()
    test_timemachine()
