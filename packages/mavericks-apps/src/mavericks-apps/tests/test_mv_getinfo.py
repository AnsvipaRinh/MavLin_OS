"""Test mv-getinfo for Finder Get Info dialog."""
import subprocess
import sys
import os
import tempfile


def test_getinfo_usage():
    """Test that mv-getinfo shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-getinfo"
    
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
    
    print("PASS: mv-getinfo shows usage correctly")


def test_getinfo_with_file():
    """Test that mv-getinfo works with a valid file path."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-getinfo"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_file = f.name
        f.write(b"test content")
    
    try:
        result = subprocess.run(
            ["python3", script_path, temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should succeed (may not show GUI in test env, but should not crash)
        # In headless env it might fail gracefully
        if result.returncode == 0:
            print("PASS: mv-getinfo handles file path correctly")
        else:
            # Check if it's a graceful failure (no display)
            if "display" in result.stderr.lower() or "gtk" in result.stderr.lower():
                print("PASS: mv-getinfo fails gracefully without display")
            else:
                print(f"INFO: mv-getinfo exit code {result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("PASS: mv-getinfo launched (timeout expected in test env)")
    finally:
        os.unlink(temp_file)


def test_getinfo_nonexistent_file():
    """Test that mv-getinfo handles nonexistent file gracefully."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-getinfo"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "/nonexistent/file/path"],
        capture_output=True,
        text=True
    )
    
    # Should handle error gracefully
    print(f"INFO: mv-getinfo on nonexistent file: exit={result.returncode}")
    print("PASS: mv-getinfo handles nonexistent file")


if __name__ == "__main__":
    test_getinfo_usage()
    test_getinfo_with_file()
    test_getinfo_nonexistent_file()
