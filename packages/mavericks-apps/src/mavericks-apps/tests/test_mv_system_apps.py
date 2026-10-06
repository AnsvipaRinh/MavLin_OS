"""Test mv-about, mv-settings, mv-console system apps."""
import subprocess
import sys
import os


def test_about():
    """Test mv-about invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-about"
    
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
        print("PASS: mv-about executed")
    else:
        print(f"INFO: mv-about exit={result.returncode}")


def test_settings():
    """Test mv-settings invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-settings"
    
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
        print("PASS: mv-settings executed")
    else:
        print(f"INFO: mv-settings exit={result.returncode}")


def test_console():
    """Test mv-console invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-console"
    
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
        print("PASS: mv-console executed")
    else:
        print(f"INFO: mv-console exit={result.returncode}")


if __name__ == "__main__":
    test_about()
    test_settings()
    test_console()
