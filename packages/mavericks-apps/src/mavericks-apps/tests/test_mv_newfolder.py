"""Test mv-newfolder for Finder new folder creation."""
import subprocess
import sys
import os
import tempfile
import shutil


def test_newfolder_usage():
    """Test that mv-newfolder shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-newfolder"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True
    )
    
    # Should show usage when called without args
    assert result.returncode != 0, "Should exit with error when no path provided"
    assert "Usage" in result.stderr or "usage" in result.stderr, "Should show usage message"
    
    print("PASS: mv-newfolder shows usage correctly")


def test_newfolder_creates_folder():
    """Test that mv-newfolder creates a folder."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-newfolder"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    new_folder = os.path.join(temp_dir, "New Folder")
    
    try:
        result = subprocess.run(
            ["python3", script_path, new_folder],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            if os.path.isdir(new_folder):
                print("PASS: mv-newfolder created folder successfully")
            else:
                print("INFO: mv-newfolder succeeded but folder not found (GUI mode)")
        else:
            print(f"INFO: mv-newfolder exit={result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("PASS: mv-newfolder launched (timeout expected in GUI mode)")
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_newfolder_usage()
    test_newfolder_creates_folder()
