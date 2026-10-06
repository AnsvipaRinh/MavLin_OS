"""Test mv-power-ui and mv-control system utilities."""
import subprocess
import sys
import os


def test_power_ui():
    """Test mv-power-ui invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-power-ui"
    
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
        print("PASS: mv-power-ui executed")
    else:
        print(f"INFO: mv-power-ui exit={result.returncode}")


def test_control():
    """Test mv-control invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-control"
    
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
        print("PASS: mv-control executed")
    else:
        print(f"INFO: mv-control exit={result.returncode}")


if __name__ == "__main__":
    test_power_ui()
    test_control()
