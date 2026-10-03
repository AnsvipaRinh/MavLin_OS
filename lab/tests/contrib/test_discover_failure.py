#!/usr/bin/env python3
"""
Test discover.sh failure classification.
Tests that gh failures are properly classified (not masked as empty backlog).
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "contrib")

def run_discover_with_mock_gh(test_case, tmpdir):
    """Run discover.sh with mocked gh command that returns specified stderr."""
    # Use the real project's state directory since discover.sh computes it from script location
    state_dir = os.path.join(REPO_ROOT, "lab", "contrib")
    state_file = os.path.join(state_dir, "state.json")
    backlog_file = os.path.join(state_dir, "backlog.json")
    
    # Backup existing state
    backup_state = None
    if os.path.exists(state_file):
        with open(state_file) as f:
            backup_state = f.read()
    
    # Initialize state file
    with open(state_file, "w") as f:
        json.dump({
            "last_pr_check": "1970-01-01T00:00:00Z",
            "last_issue_check": "1970-01-01T00:00:00Z",
            "processed_prs": {},
            "processed_issues": {}
        }, f)
    
    # Remove existing backlog
    if os.path.exists(backlog_file):
        os.remove(backlog_file)
    
    # Create a mock gh script that outputs the test stderr
    mock_gh = os.path.join(tmpdir, "gh")
    stderr_file = os.path.join(tmpdir, "gh_stderr.txt")
    with open(stderr_file, "w") as f:
        f.write(test_case["gh_stderr"])
    with open(mock_gh, "w") as f:
        f.write(f'''#!/usr/bin/env bash
cat "{stderr_file}" >&2
exit 1
''')
    os.chmod(mock_gh, 0o755)
    
    # Run discover.sh with mocked gh in PATH
    env = os.environ.copy()
    env["PATH"] = tmpdir + ":" + env["PATH"]
    env["GH_REPO"] = "test/repo"
    
    script = os.path.join(SCRIPTS_DIR, "discover.sh")
    result = subprocess.run(
        [script],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=15
    )
    
    # Read backlog.json from real location
    if os.path.exists(backlog_file):
        with open(backlog_file) as f:
            backlog = json.load(f)
    else:
        backlog = {}
    
    # Restore backup state
    if backup_state is not None:
        with open(state_file, "w") as f:
            f.write(backup_state)
    else:
        if os.path.exists(state_file):
            os.remove(state_file)
    if os.path.exists(backlog_file):
        os.remove(backlog_file)
    
    return result.returncode, backlog, result.stdout, result.stderr


def run_discover_success(tmpdir):
    """Run discover.sh with mocked gh that returns empty arrays."""
    state_dir = os.path.join(REPO_ROOT, "lab", "contrib")
    state_file = os.path.join(state_dir, "state.json")
    backlog_file = os.path.join(state_dir, "backlog.json")
    
    # Backup existing state
    backup_state = None
    if os.path.exists(state_file):
        with open(state_file) as f:
            backup_state = f.read()
    
    with open(state_file, "w") as f:
        json.dump({
            "last_pr_check": "1970-01-01T00:00:00Z",
            "last_issue_check": "1970-01-01T00:00:00Z",
            "processed_prs": {},
            "processed_issues": {}
        }, f)
    
    if os.path.exists(backlog_file):
        os.remove(backlog_file)
    
    mock_gh = os.path.join(tmpdir, "gh")
    with open(mock_gh, "w") as f:
        f.write('''#!/usr/bin/env bash
echo "[]"
''')
    os.chmod(mock_gh, 0o755)
    
    env = os.environ.copy()
    env["PATH"] = tmpdir + ":" + env["PATH"]
    env["GH_REPO"] = "test/repo"
    
    script = os.path.join(SCRIPTS_DIR, "discover.sh")
    result = subprocess.run([script], capture_output=True, text=True, env=env, cwd=REPO_ROOT, timeout=15)
    
    # Read backlog.json from real location
    if os.path.exists(backlog_file):
        with open(backlog_file) as f:
            backlog = json.load(f)
    else:
        backlog = {}
    
    # Restore backup state
    if backup_state is not None:
        with open(state_file, "w") as f:
            f.write(backup_state)
    else:
        if os.path.exists(state_file):
            os.remove(state_file)
    if os.path.exists(backlog_file):
        os.remove(backlog_file)
    
    return result.returncode, backlog, result.stdout, result.stderr


def main():
    print("=== Discover Failure Classification Tests ===\n")
    
    TEST_CASES = [
        {
            "name": "auth_failure",
            "gh_stderr": "error: authentication required\nYou need to log in to GitHub first. Run `gh auth login`.",
            "expected_status": "AUTH_INVALID",
            "expected_exit": 2,
        },
        {
            "name": "rate_limit",
            "gh_stderr": "API rate limit exceeded for user. Rate limit resets in 30 minutes.",
            "expected_status": "RATE_LIMITED",
            "expected_exit": 3,
        },
        {
            "name": "network_failure",
            "gh_stderr": "Could not resolve host: github.com",
            "expected_status": "UNAVAILABLE",
            "expected_exit": 1,
        },
        {
            "name": "generic_failure",
            "gh_stderr": "gh: command not found",
            "expected_status": "UNAVAILABLE",
            "expected_exit": 1,
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in TEST_CASES:
        print(f"Testing: {test_case['name']}")
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code, backlog, stdout, stderr = run_discover_with_mock_gh(test_case, tmpdir)
        
        actual_status = backlog.get("discovery_status", "MISSING")
        actual_exit = exit_code
        
        print(f"  Expected status: {test_case['expected_status']}, Got: {actual_status}")
        print(f"  Expected exit: {test_case['expected_exit']}, Got: {actual_exit}")
        
        status_ok = actual_status == test_case["expected_status"]
        exit_ok = actual_exit == test_case["expected_exit"]
        
        if status_ok and exit_ok:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
            if not status_ok:
                print(f"    Status mismatch: expected {test_case['expected_status']}, got {actual_status}")
            if not exit_ok:
                print(f"    Exit code mismatch: expected {test_case['expected_exit']}, got {actual_exit}")
            print(f"  Stdout: {stdout[:300]}")
            print(f"  Stderr: {stderr[:300]}")
            failed += 1
        print()
    
    # Test: successful discovery returns EMPTY status (OK with 0 items)
    print("Testing: success_case (empty but OK)")
    with tempfile.TemporaryDirectory() as tmpdir:
        exit_code, backlog, stdout, stderr = run_discover_success(tmpdir)
    
    actual_status = backlog.get("discovery_status", "MISSING")
    actual_exit = exit_code
    
    print(f"  Expected status: EMPTY (OK with 0 items), Got: {actual_status}")
    print(f"  Expected exit: 0, Got: {actual_exit}")
    
    # After fix, empty backlog should be EMPTY status with exit 0
    if actual_status in ("EMPTY", "OK") and actual_exit == 0:
        print(f"  ✅ PASS")
        passed += 1
    else:
        print(f"  ❌ FAIL")
        print(f"  Stdout: {stdout[:300]}")
        failed += 1
    print()
    
    print(f"=== Results: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())