"""Test Mission Control window listing by workspace."""
import subprocess
import json
import sys


def test_window_spaces_output():
    """Test that mv-mc-window-spaces outputs valid JSON with workspace structure."""
    try:
        result = subprocess.run(
            ["python3", "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-window-spaces"],
            capture_output=True,
            text=True,
            timeout=5
        )
    except FileNotFoundError:
        print("SKIP: mv-mc-window-spaces not found or not executable")
        return
    
    # Should output valid JSON
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON output: {e}")
        print(f"STDOUT: {result.stdout[:500]}")
        sys.exit(1)
    
    # Should have workspaces key
    assert "workspaces" in data, "Missing 'workspaces' key in output"
    
    # Should have at least one workspace
    workspaces = data["workspaces"]
    assert isinstance(workspaces, list), "'workspaces' should be a list"
    assert len(workspaces) > 0, "Should have at least one workspace"
    
    # Each workspace should have id, name, windows
    for ws in workspaces:
        assert "id" in ws, "Workspace missing 'id'"
        assert "name" in ws, "Workspace missing 'name'"
        assert "windows" in ws, "Workspace missing 'windows'"
        assert isinstance(ws["windows"], list), "'windows' should be a list"
        
        # Each window should have required fields
        for win in ws["windows"]:
            required_fields = ["wid", "title", "app", "x", "y", "width", "height", "visible", "minimized"]
            for field in required_fields:
                assert field in win, f"Window missing '{field}' field"
    
    print("PASS: mv-mc-window-spaces outputs valid workspace window structure")


if __name__ == "__main__":
    test_window_spaces_output()
