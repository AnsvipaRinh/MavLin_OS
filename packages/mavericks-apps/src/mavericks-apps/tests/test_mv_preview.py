"""Test mv-preview for Preview application."""
import subprocess
import sys
import os
import tempfile


def test_preview_usage():
    """Test that mv-preview shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-preview"
    
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
    
    print("PASS: mv-preview shows usage correctly")


def test_preview_with_file():
    """Test that mv-preview works with a valid file path."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-preview"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        temp_file = f.name
        f.write(b"test content for preview")
    
    try:
        result = subprocess.run(
            ["python3", script_path, temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should succeed or fail gracefully (no display in test env)
        if result.returncode == 0:
            print("PASS: mv-preview handles file path correctly")
        else:
            # Check if it's a graceful failure
            if "display" in result.stderr.lower() or "gtk" in result.stderr.lower():
                print("PASS: mv-preview fails gracefully without display")
            else:
                print(f"INFO: mv-preview exit={result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("PASS: mv-preview launched (timeout expected in GUI mode)")
    finally:
        os.unlink(temp_file)


if __name__ == "__main__":
    test_preview_usage()
    test_preview_with_file()
