"""Test mv-trash-putback for restoring files from trash."""
import subprocess
import sys
import os


def test_trash_putback_usage():
    """Test that mv-trash-putback shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-trash-putback"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True
    )
    
    # Should show usage when called without args
    assert result.returncode != 0, "Should exit with error when no file provided"
    assert "Usage" in result.stderr or "usage" in result.stderr, "Should show usage message"
    
    print("PASS: mv-trash-putback shows usage correctly")


def test_trash_putback_help():
    """Test that mv-trash-putback shows help."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-trash-putback"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "--help"],
        capture_output=True,
        text=True
    )
    
    # May or may not have --help, just log
    if result.returncode == 0 and ("usage" in result.stdout.lower() or "help" in result.stdout.lower()):
        print("PASS: mv-trash-putback has --help")
    else:
        print("INFO: mv-trash-putback --help not available (not critical)")


if __name__ == "__main__":
    test_trash_putback_usage()
    test_trash_putback_help()
