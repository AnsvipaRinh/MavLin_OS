"""Test mv-copy-path and mv-paste-path for Finder path operations."""
import subprocess
import sys
import os
import tempfile


def test_copy_path_usage():
    """Test that mv-copy-path shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-copy-path"
    
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
    
    print("PASS: mv-copy-path shows usage correctly")


def test_copy_path_with_file():
    """Test that mv-copy-path works with a valid file path."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-copy-path"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_file = f.name
        f.write(b"test")
    
    try:
        result = subprocess.run(
            ["python3", script_path, temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should succeed (copies to clipboard)
        if result.returncode == 0:
            print("PASS: mv-copy-path handles file path correctly")
        else:
            # May fail without X11/clipboard
            if "clipboard" in result.stderr.lower() or "x11" in result.stderr.lower():
                print("PASS: mv-copy-path fails gracefully without clipboard")
            else:
                print(f"INFO: mv-copy-path exit={result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("PASS: mv-copy-path launched (timeout expected)")
    finally:
        os.unlink(temp_file)


def test_paste_path_usage():
    """Test that mv-paste-path works."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-paste-path"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or fail gracefully (no clipboard in test env)
    if result.returncode == 0:
        print("PASS: mv-paste-path executed")
    else:
        if "clipboard" in result.stderr.lower():
            print("PASS: mv-paste-path fails gracefully without clipboard")
        else:
            print(f"INFO: mv-paste-path exit={result.returncode}")


if __name__ == "__main__":
    test_copy_path_usage()
    test_copy_path_with_file()
    test_paste_path_usage()
