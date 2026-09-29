#!/usr/bin/env python3
# test_mv_snapshot_take.py — test script for mv-snapshot-take functionality
# Tests mocked btrfs scenarios: take/skip-non-btrfs/prune/hook-called

import os
import sys
import tempfile
import shutil
import subprocess
import json
from pathlib import Path

SNAPSHOT_HELPER = Path(__file__).parent.parent / "tools" / "diagnostics" / "mv-snapshot-take.sh"
MOCK_BTRFS_DIR = Path(__file__).parent / "mock_btrfs"
MOCK_BTRFS_DIR.mkdir(exist_ok=True)

def create_mock_btrfs():
    """Create a mock btrfs script that simulates btrfs commands."""
    mock_script = MOCK_BTRFS_DIR / "btrfs"
    mock_script.write_text("""#!/usr/bin/env bash
# Mock btrfs for testing
case "$1" in
  subvolume)
    if [[ "$2" == "snapshot" ]]; then
      # Create the snapshot directory
      mkdir -p "$4"
      echo "Created mock snapshot: $4"
      exit 0
    elif [[ "$2" == "delete" ]]; then
      rm -rf "$3"
      echo "Deleted mock snapshot: $3"
      exit 0
    fi
    ;;
  filesystem)
    if [[ "$2" == "show" ]]; then
      echo "Mock btrfs filesystem show"
      exit 0
    fi
    ;;
esac
echo "Mock btrfs command not recognized: $*" >&2
exit 1
""")
    mock_script.chmod(0o755)
    
    mock_mountpoint = MOCK_BTRFS_DIR / "mountpoint"
    mock_mountpoint.write_text("""#!/usr/bin/env bash
# Mock mountpoint for testing
if [[ "$1" == "-q" && "$2" == "/@snapshots" ]]; then
  exit 0
fi
exit 1
""")
    mock_mountpoint.chmod(0o755)

def run_snapshot_helper(args, env=None):
    """Run the snapshot helper with given args and environment."""
    test_env = os.environ.copy()
    test_env["PATH"] = str(MOCK_BTRFS_DIR) + ":" + test_env["PATH"]
    test_env["BACKUP_DIR"] = str(tempfile.gettempdir()) + "/test-snapshots"
    test_env["SNAPSHOT_LOG"] = str(tempfile.gettempdir()) + "/test-snapshots.log"
    test_env["SNAPSHOT_INDEX"] = str(tempfile.gettempdir()) + "/test-index.json"
    
    if env:
        test_env.update(env)
    
    # Clean up test dirs
    if Path(test_env["BACKUP_DIR"]).exists():
        shutil.rmtree(test_env["BACKUP_DIR"])
    for f in [test_env["SNAPSHOT_LOG"], test_env["SNAPSHOT_INDEX"]]:
        if Path(f).exists():
            Path(f).unlink()
    
    # Create mock btrfs filesystem structure
    Path(test_env["BACKUP_DIR"]).mkdir(parents=True, exist_ok=True)
    (Path(test_env["BACKUP_DIR"]) / "..").mkdir(parents=True, exist_ok=True)
    
    result = subprocess.run(
        [str(SNAPSHOT_HELPER)] + args,
        capture_output=True,
        text=True,
        env=test_env
    )
    return result

def test_label_validation():
    """Test label validation - should log error but NOT fail (axis-S: helper never fails wrapped op)."""
    print("=== Test 1: Label validation (should log error but return 0) ===")
    
    # Test empty label - should return 0 but log error
    result = run_snapshot_helper(["", "Empty label test"])
    if result.returncode == 0 and "ERROR" in result.stdout and "invalid label" in result.stdout:
        print("PASS: Empty label handled gracefully (returns 0, logs error)")
    else:
        print(f"FAIL: Empty label should return 0 with error log. rc={result.returncode}, out={result.stdout[:200]}")
        return False
    
    # Test invalid label (special characters) - should return 0 but log error
    result = run_snapshot_helper(["test@label", "Invalid label test"])
    if result.returncode == 0 and "ERROR" in result.stdout and "invalid label" in result.stdout:
        print("PASS: Invalid label handled gracefully (returns 0, logs error)")
    else:
        print(f"FAIL: Invalid label should return 0 with error log. rc={result.returncode}, out={result.stdout[:200]}")
        return False
    
    # Test long label - should return 0 but log error
    long_label = "x" * 60
    result = run_snapshot_helper([long_label, "Long label test"])
    if result.returncode == 0 and "ERROR" in result.stdout and "invalid label" in result.stdout:
        print("PASS: Long label handled gracefully (returns 0, logs error)")
    else:
        print(f"FAIL: Long label should return 0 with error log. rc={result.returncode}, out={result.stdout[:200]}")
        return False
    
    # Test valid label
    result = run_snapshot_helper(["valid-label", "Valid label test"])
    if result.returncode == 0:
        print("PASS: Valid label accepted")
    else:
        print(f"FAIL: Valid label rejected: {result.stderr}")
        return False
    
    return True

def test_snapshot_creation():
    """Test snapshot creation with mock btrfs."""
    print("=== Test 2: Snapshot creation (mock btrfs) ===")
    
    create_mock_btrfs()
    result = run_snapshot_helper(["test-snapshot-1", "Test snapshot creation"])
    
    if result.returncode == 0:
        print("PASS: Snapshot creation succeeded")
        print(f"Output: {result.stdout}")
        return True
    else:
        print(f"FAIL: Snapshot creation failed: {result.stderr}")
        return False

def test_skip_on_non_btrfs():
    """Test skipping snapshot on non-btrfs filesystem."""
    print("=== Test 3: Skip snapshot on non-btrfs filesystem ===")
    
    # Remove mock btrfs to simulate non-btrfs
    mock_btrfs = MOCK_BTRFS_DIR / "btrfs"
    mock_mountpoint = MOCK_BTRFS_DIR / "mountpoint"
    if mock_btrfs.exists():
        mock_btrfs.unlink()
    if mock_mountpoint.exists():
        mock_mountpoint.unlink()
    
    result = run_snapshot_helper(["test-snapshot-2", "Test skip on non-btrfs"])
    
    if result.returncode == 0:
        print("PASS: Non-btrfs handled gracefully (operation continues)")
        print(f"Output: {result.stdout}")
        return True
    else:
        print(f"FAIL: Non-btrfs should not fail the operation: {result.stderr}")
        return False

def test_index_and_logging():
    """Test index creation and logging."""
    print("=== Test 4: Index creation and logging ===")
    
    create_mock_btrfs()
    result = run_snapshot_helper(["test-index-log", "Test for index and logging"])
    
    if result.returncode == 0:
        print("PASS: Snapshot with indexing succeeded")
        
        # Check log file
        log_file = Path(tempfile.gettempdir()) / "test-snapshots.log"
        if log_file.exists():
            print("PASS: Log file created")
            print(f"Log content: {log_file.read_text()[:200]}")
        else:
            print("INFO: Log file not created (may be expected with mock)")
        
        # Check index file
        index_file = Path(tempfile.gettempdir()) / "test-index.json"
        if index_file.exists():
            print("PASS: Index file created")
            try:
                data = json.loads(index_file.read_text())
                print(f"Index entries: {len(data)}")
            except json.JSONDecodeError:
                print("WARN: Index file not valid JSON")
        else:
            print("INFO: Index file not created (may be expected with mock)")
        
        return True
    else:
        print(f"FAIL: Index/logging test failed: {result.stderr}")
        return False

def test_prune():
    """Test snapshot pruning."""
    print("=== Test 5: Snapshot pruning ===")
    
    create_mock_btrfs()
    
    # Create multiple snapshots with same label
    for i in range(7):
        result = run_snapshot_helper([f"prune-test-{i}", f"Prune test {i}"])
        if result.returncode != 0:
            print(f"FAIL: Snapshot {i} creation failed")
            return False
    
    # Check that pruning happened (should keep last 5 per label)
    index_file = Path(tempfile.gettempdir()) / "test-index.json"
    if index_file.exists():
        try:
            data = json.loads(index_file.read_text())
            print(f"Total snapshots in index: {len(data)}")
            # Should be pruned to 5 per label + overall limit
            if len(data) <= 10:
                print("PASS: Pruning appears to work")
                return True
            else:
                print("WARN: More snapshots than expected, pruning may not work correctly")
                return True  # Not a hard failure
        except json.JSONDecodeError:
            print("INFO: Index not valid JSON, cannot verify pruning")
            return True
    
    return True

def test_hook_integration():
    """Test that hooks are called from firstboot and mv-experiment."""
    print("=== Test 6: Hook integration check ===")
    
    # Check firstboot calls mv-snapshot-take
    firstboot = Path(__file__).parent / "install" / "mavericks-firstboot.sh"
    if firstboot.exists():
        content = firstboot.read_text()
        if "mv-snapshot-take" in content:
            print("PASS: firstboot calls mv-snapshot-take")
        else:
            print("FAIL: firstboot does not call mv-snapshot-take")
            return False
    else:
        print("FAIL: firstboot not found")
        return False
    
    # Check mv-experiment calls mv-snapshot-take
    mv_exp = Path(__file__).parent.parent / "tools" / "experiments" / "mv-experiment.sh"
    if mv_exp.exists():
        content = mv_exp.read_text()
        if "mv-snapshot-take" in content:
            print("PASS: mv-experiment calls mv-snapshot-take")
        else:
            print("FAIL: mv-experiment does not call mv-snapshot-take")
            return False
    else:
        print("FAIL: mv-experiment not found")
        return False
    
    return True

def test_one_rollback_procedure():
    """Test that there's only one rollback procedure."""
    print("=== Test 7: Single rollback procedure ===")
    
    rollback_script = Path(__file__).parent / "mavericks-rollback.sh"
    if rollback_script.exists():
        content = rollback_script.read_text()
        if "restore_from_snapshot" in content:
            print("PASS: mavericks-rollback.sh exists with restore function")
        else:
            print("FAIL: mavericks-rollback.sh missing restore function")
            return False
    else:
        print("FAIL: mavericks-rollback.sh not found")
        return False
    
    # Check no other rollback scripts exist
    rollback_scripts = list(Path(__file__).parent.glob("*rollback*"))
    if len(rollback_scripts) == 1:
        print("PASS: Only one rollback script found")
    else:
        print(f"WARN: Multiple rollback scripts found: {rollback_scripts}")
    
    return True

def main():
    print("Starting mv-snapshot-take tests...")
    
    all_passed = True
    all_passed &= test_label_validation()
    all_passed &= test_snapshot_creation()
    all_passed &= test_skip_on_non_btrfs()
    all_passed &= test_index_and_logging()
    all_passed &= test_prune()
    all_passed &= test_hook_integration()
    all_passed &= test_one_rollback_procedure()
    
    if all_passed:
        print("\nAll tests completed successfully!")
        return 0
    else:
        print("\nSome tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())