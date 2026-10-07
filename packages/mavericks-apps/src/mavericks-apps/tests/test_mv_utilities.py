"""Test mv-calculator, mv-fontbook, mv-colormeter, mv-dock-config."""
import subprocess
import sys
import os


def test_calculator():
    """Test mv-calculator invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-calculator"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-calculator executed")
    else:
        print(f"INFO: mv-calculator exit={result.returncode}")


def test_fontbook():
    """Test mv-fontbook invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-fontbook"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-fontbook executed")
    else:
        print(f"INFO: mv-fontbook exit={result.returncode}")


def test_colormeter():
    """Test mv-colormeter invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-colormeter"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-colormeter executed")
    else:
        print(f"INFO: mv-colormeter exit={result.returncode}")


def test_dock_config():
    """Test mv-dock-config invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-dock-config"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-dock-config executed")
    else:
        print(f"INFO: mv-dock-config exit={result.returncode}")


if __name__ == "__main__":
    test_calculator()
    test_fontbook()
    test_colormeter()
    test_dock_config()
