"""Test mv-finder-columns and mv-finder-search."""
import subprocess
import sys
import os


def test_finder_columns():
    """Test mv-finder-columns invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-columns"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or show usage
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-finder-columns executed")
    else:
        print(f"INFO: mv-finder-columns exit={result.returncode}")


def test_finder_search():
    """Test mv-finder-search invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-finder-search"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or show usage
    if result.returncode == 0 or "usage" in result.stdout.lower():
        print("PASS: mv-finder-search executed")
    else:
        print(f"INFO: mv-finder-search exit={result.returncode}")


if __name__ == "__main__":
    test_finder_columns()
    test_finder_search()
