"""Test mv-workspace-count helper for workspace management."""
import subprocess
import sys
import os


def test_workspace_count_show():
    """Test that mv-workspace-count shows current count."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-workspace-count"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Should succeed, got: {result.stderr}"
    try:
        count = int(result.stdout.strip())
        assert 1 <= count <= 16, f"Count {count} out of bounds [1, 16]"
        print(f"PASS: Current workspace count: {count}")
    except ValueError:
        print(f"FAIL: Expected numeric output, got: {result.stdout}")
        sys.exit(1)


def test_workspace_count_get():
    """Test that mv-workspace-count get works."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-workspace-count"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "get"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Should succeed, got: {result.stderr}"
    try:
        count = int(result.stdout.strip())
        assert 1 <= count <= 16, f"Count {count} out of bounds [1, 16]"
        print(f"PASS: Workspace count get: {count}")
    except ValueError:
        print(f"FAIL: Expected numeric output, got: {result.stdout}")
        sys.exit(1)


def test_workspace_count_set_invalid():
    """Test that mv-workspace-count rejects invalid count."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-workspace-count"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Try to set count to 0 (below minimum)
    result = subprocess.run(
        ["python3", script_path, "set", "0"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should fail for count below minimum"
    assert "must be between" in result.stderr.lower(), "Should report bounds error"
    print("PASS: Workspace count set rejects below-minimum value")


def test_workspace_count_set_too_high():
    """Test that mv-workspace-count rejects count above maximum."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-workspace-count"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Try to set count to 17 (above Mavericks max)
    result = subprocess.run(
        ["python3", script_path, "set", "17"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should fail for count above maximum"
    assert "must be between" in result.stderr.lower(), "Should report bounds error"
    print("PASS: Workspace count set rejects above-maximum value")


if __name__ == "__main__":
    test_workspace_count_show()
    test_workspace_count_get()
    test_workspace_count_set_invalid()
    test_workspace_count_set_too_high()
