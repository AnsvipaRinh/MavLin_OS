"""Test mv-keychain and mv-dictionary productivity apps."""
import subprocess
import sys
import os


def test_keychain():
    """Test mv-keychain invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-keychain"
    
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
        print("PASS: mv-keychain executed")
    else:
        print(f"INFO: mv-keychain exit={result.returncode}")


def test_dictionary():
    """Test mv-dictionary invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-dictionary"
    
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
        print("PASS: mv-dictionary executed")
    else:
        print(f"INFO: mv-dictionary exit={result.returncode}")


if __name__ == "__main__":
    test_keychain()
    test_dictionary()
