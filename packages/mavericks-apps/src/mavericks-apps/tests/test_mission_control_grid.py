"""Test mv-mc-grid helper for Mission Control grid layout."""
import subprocess
import json
import sys
import os


def test_grid_usage():
    """Test that mv-mc-grid shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-grid"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should exit with error when no args provided"
    assert "Usage" in result.stderr, "Should show usage message"
    
    print("PASS: mv-mc-grid shows usage correctly")


def test_grid_invalid_count():
    """Test that mv-mc-grid rejects invalid window count."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-grid"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "invalid"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0, "Should exit with error for invalid count"
    assert "Invalid window count" in result.stderr, "Should report invalid count"
    
    print("PASS: mv-mc-grid rejects invalid window count")


def test_grid_output_structure():
    """Test that mv-mc-grid outputs valid JSON with expected structure."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-grid"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "5"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Should succeed: {result.stderr}"
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON: {e}")
        sys.exit(1)
    
    # Check required keys
    assert "rows" in data, "Missing 'rows'"
    assert "cols" in data, "Missing 'cols'"
    assert "cell_width" in data, "Missing 'cell_width'"
    assert "cell_height" in data, "Missing 'cell_height'"
    assert "windows" in data, "Missing 'windows'"
    
    # Check windows array
    assert isinstance(data["windows"], list), "'windows' should be a list"
    assert len(data["windows"]) == 5, "Should have 5 windows"
    
    for win in data["windows"]:
        assert "index" in win, "Window missing 'index'"
        assert "x" in win, "Window missing 'x'"
        assert "y" in win, "Window missing 'y'"
        assert "row" in win, "Window missing 'row'"
        assert "col" in win, "Window missing 'col'"
    
    print("PASS: mv-mc-grid outputs valid grid structure")


def test_grid_zero_windows():
    """Test that mv-mc-grid handles zero windows."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-grid"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "0"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Should succeed: {result.stderr}"
    
    try:
        data = json.loads(result.stdout)
        assert data["rows"] == 0, "Should have 0 rows"
        assert data["cols"] == 0, "Should have 0 cols"
        assert len(data["windows"]) == 0, "Should have 0 windows"
    except (json.JSONDecodeError, KeyError, AssertionError) as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    
    print("PASS: mv-mc-grid handles zero windows")


if __name__ == "__main__":
    test_grid_usage()
    test_grid_invalid_count()
    test_grid_output_structure()
    test_grid_zero_windows()
