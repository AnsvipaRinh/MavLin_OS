"""Test mv-mc-gui helper for Mission Control GUI overlay."""
import subprocess
import sys
import os


def test_gui_help():
    """Test that mv-mc-gui shows help."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-gui"
    
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
    assert "GUI" in result.stdout, "Should mention GUI"
    
    print("PASS: mv-mc-gui shows help")


def test_gui_import_check():
    """Test that mv-mc-gui has GTK3 available."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-mc-gui"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Try to import GTK
    result = subprocess.run(
        ["python3", "-c", "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK OK')"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("SKIP: GTK3 not available for GUI test")
        return
    
    print("PASS: GTK3 available for GUI")


if __name__ == "__main__":
    test_gui_help()
    test_gui_import_check()
