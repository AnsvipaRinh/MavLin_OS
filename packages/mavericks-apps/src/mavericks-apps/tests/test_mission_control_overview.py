"""Test mv-mc-overview integration."""
import subprocess
import sys
import os


def test_overview_help():
    """Test that mv-mc-overview shows help."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-overview"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Should succeed: {result.stderr}"
    assert "Mission Control" in result.stdout, "Should mention Mission Control"
    
    print("PASS: mv-mc-overview shows help")


def test_overview_keyboard_navigation_contract():
    """Mission Control must support keyboard selection and activation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-overview"

    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return

    source = open(script_path, encoding="utf-8").read()
    assert 'if key in ("Left", "Up"):' in source
    assert 'if key in ("Right", "Down"):' in source
    assert 'if key in ("Return", "KP_Enter", "space"):' in source
    assert 'if key == "Home":' in source
    assert 'if key == "End":' in source
    assert "self._activate_selected()" in source

    print("PASS: Mission Control keyboard navigation contract")


def test_overview_list_mode():
    """Test that mv-mc-overview list mode works."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-overview"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "--list"],
        capture_output=True,
        text=True
    )
    
    # Should succeed (may have no windows, but should not crash)
    assert result.returncode == 0, f"Should succeed: {result.stderr}"
    
    print("PASS: mv-mc-overview list mode works")


def test_overview_debug_mode():
    """Test that mv-mc-overview debug mode works."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-overview"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "--debug"],
        capture_output=True,
        text=True
    )
    
    # Should succeed (may have no windows, but should not crash)
    assert result.returncode == 0, f"Should succeed: {result.stderr}"
    
    # Debug output should include workspace info
    assert "Workspaces" in result.stdout or "Mission Control" in result.stdout, "Should show debug info"
    
    print("PASS: mv-mc-overview debug mode works")


if __name__ == "__main__":
    test_overview_help()
    test_overview_list_mode()
    test_overview_debug_mode()


def test_overview_uses_wallpaper_backdrop():
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-overview"
    source = open(script_path, encoding="utf-8").read()
    assert "xfconf-query" in source
    assert "_load_wallpaper" in source
    assert "mav-backdrop-dim" in source
    assert "new_subpixbuf" in source
