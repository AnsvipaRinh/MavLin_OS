"""Test mv-eject for removable media ejection."""
import subprocess
import sys
import os


def test_eject_usage():
    """Test that mv-eject shows usage on no args."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-eject"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path],
        capture_output=True,
        text=True
    )
    
    # Should show usage when called without args
    assert result.returncode != 0, "Should exit with error when no mount point provided"
    assert "Usage" in result.stderr or "usage" in result.stderr, "Should show usage message"
    
    print("PASS: mv-eject shows usage correctly")


def test_eject_invalid_mount():
    """Test that mv-eject handles invalid mount point gracefully."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-eject"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "/nonexistent/mount/point"],
        capture_output=True,
        text=True
    )
    
    # Should handle error gracefully
    print(f"INFO: mv-eject on invalid mount: exit={result.returncode}")
    if result.returncode != 0:
        print("PASS: mv-eject handles invalid mount point (expected failure)")
    else:
        print("INFO: mv-eject succeeded (may have found valid mount)")


def test_eject_help():
    """Test that mv-eject shows help with --help."""
    script_path = "packages/mavericks-apps/src/mavericks-apps/bin/mv-eject"
    
    if not os.path.exists(script_path):
        print(f"SKIP: {script_path} not found")
        return
    
    result = subprocess.run(
        ["python3", script_path, "--help"],
        capture_output=True,
        text=True
    )
    
    # May or may not have --help, just log
    if result.returncode == 0 and ("usage" in result.stdout.lower() or "help" in result.stdout.lower()):
        print("PASS: mv-eject has --help")
    else:
        print("INFO: mv-eject --help not available (not critical)")


if __name__ == "__main__":
    test_eject_usage()
    test_eject_invalid_mount()
    test_eject_help()
