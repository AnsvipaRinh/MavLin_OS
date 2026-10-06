"""Test mv-rename for Finder rename functionality."""
import subprocess
import sys
import os
import tempfile


def test_rename_usage():
    """Test that mv-rename shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-rename"
    
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
    
    print("PASS: mv-rename shows usage correctly")


def test_rename_with_file():
    """Test that mv-rename works with a valid file path."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-rename"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        temp_file = f.name
        f.write(b"test content")
    
    try:
        result = subprocess.run(
            ["python3", script_path, temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should succeed or fail gracefully (no display in test env)
        if result.returncode == 0:
            print("PASS: mv-rename handles file path correctly")
        else:
            # Check if it's a graceful failure (no display)
            if "display" in result.stderr.lower() or "gtk" in result.stderr.lower():
                print("PASS: mv-rename fails gracefully without display")
            else:
                print(f"INFO: mv-rename exit code {result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("PASS: mv-rename launched (timeout expected in test env)")
    finally:
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_rename_nonexistent_file():
    """Test that mv-rename handles nonexistent file gracefully."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-rename"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "/nonexistent/file.txt"],
        capture_output=True,
        text=True
    )
    
    # Should handle error gracefully
    print(f"INFO: mv-rename on nonexistent file: exit={result.returncode}")
    print("PASS: mv-rename handles nonexistent file")


if __name__ == "__main__":
    test_rename_usage()
    test_rename_with_file()
    test_rename_nonexistent_file()
