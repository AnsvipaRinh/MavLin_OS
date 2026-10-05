"""Test mv-mc-thumbnail helper for Mission Control thumbnails."""
import subprocess
import sys
import os


def test_thumbnail_usage():
    """Test that mv-mc-thumbnail shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-thumbnail"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should exit with error when no window ID provided"
    assert "Usage" in result.stderr, "Should show usage message"
    
    print("PASS: mv-mc-thumbnail shows usage correctly")


def test_thumbnail_invalid_id():
    """Test that mv-mc-thumbnail rejects invalid window ID."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-thumbnail"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "invalid"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should exit with error for invalid window ID"
    assert "Invalid window ID" in result.stderr, "Should report invalid window ID"
    
    print("PASS: mv-mc-thumbnail rejects invalid window ID")


def test_thumbnail_invalid_width():
    """Test that mv-mc-thumbnail rejects invalid width."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-thumbnail"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "123", "invalid"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should exit with error for invalid width"
    assert "Invalid width" in result.stderr, "Should report invalid width"
    
    print("PASS: mv-mc-thumbnail rejects invalid width")


if __name__ == "__main__":
    test_thumbnail_usage()
    test_thumbnail_invalid_id()
    test_thumbnail_invalid_width()
