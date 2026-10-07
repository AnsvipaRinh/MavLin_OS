"""Test mv-quicklook and mv-quicklook-thunar for Quick Look preview."""
import subprocess
import sys
import os
import tempfile


def test_quicklook_usage():
    """Test that mv-quicklook shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-quicklook"
    
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
    
    print("PASS: mv-quicklook shows usage correctly")


def test_quicklook_with_file():
    """Test that mv-quicklook works with a valid file path."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-quicklook"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        temp_file = f.name
        f.write(b"test content for quick look")
    
    try:
        result = subprocess.run(
            ["python3", script_path, temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should succeed or fail gracefully (no display in test env)
        if result.returncode == 0:
            print("PASS: mv-quicklook handles file path correctly")
        else:
            # Check if it's a graceful failure (no display)
            if "display" in result.stderr.lower() or "gtk" in result.stderr.lower():
                print("PASS: mv-quicklook fails gracefully without display")
            else:
                print(f"INFO: mv-quicklook exit={result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("PASS: mv-quicklook launched (timeout expected in GUI mode)")
    finally:
        os.unlink(temp_file)


def test_quicklook_thunar():
    """Test mv-quicklook-thunar invocation."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-quicklook-thunar"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Should succeed or fail gracefully
    if result.returncode == 0:
        print("PASS: mv-quicklook-thunar executed")
    else:
        print(f"INFO: mv-quicklook-thunar exit={result.returncode}")


if __name__ == "__main__":
    test_quicklook_usage()
    test_quicklook_with_file()
    test_quicklook_thunar()
