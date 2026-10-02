#!/usr/bin/env python3
"""
Test triage.sh with fixture patches.
Tests classification routing to objective IDs.
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "contrib")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Test cases: (fixture_prefix, expected_classification, expected_objectives_contains)
TEST_CASES = [
    ("pr-42", "cosmetic", ["OS-UI-COSMETIC"]),  # UI/cosmetic
    ("pr-45", "dangerous", ["OS-SEC-REJECT"]),  # Security rejected
    ("pr-46", "integration", ["OS-INTEGRATION", "OS-ARCH"]),  # systemd service
    ("pr-43", "hw", ["OS-HW"]),  # Hardware/kernel
    ("pr-44", "docs", ["OS-DOCS"]),  # Documentation
]

def setup_test_dir(fixture_prefix):
    """Create a test review directory with fixture files + security scan result."""
    test_dir = tempfile.mkdtemp(prefix=f"test-{fixture_prefix}-")
    
    # Copy fixture files
    for ext in ["metadata.json", "patch.diff", "files.jsonl"]:
        src = os.path.join(FIXTURES_DIR, f"{fixture_prefix}-{ext}")
        dst = os.path.join(test_dir, ext)
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            if ext == "metadata.json":
                with open(dst, "w") as f:
                    json.dump({"number": 0, "title": "Test", "changedFiles": 0, "additions": 0, "deletions": 0, "labels": []}, f)
            elif ext == "files.jsonl":
                with open(dst, "w") as f:
                    f.write('')
            elif ext == "patch.diff":
                with open(dst, "w") as f:
                    f.write('')
    
    # Run security scan first to generate security-scan.json
    script = os.path.join(SCRIPTS_DIR, "security-scan.sh")
    subprocess.run([script, test_dir], capture_output=True, text=True)
    
    return test_dir

def run_triage(test_dir):
    """Run triage.sh and return parsed result."""
    script = os.path.join(SCRIPTS_DIR, "triage.sh")
    result = subprocess.run([script, test_dir], capture_output=True, text=True)
    
    report_file = os.path.join(test_dir, "triage.json")
    if os.path.exists(report_file):
        with open(report_file) as f:
            report = json.load(f)
    else:
        report = {}
    
    return result.returncode, report, result.stdout, result.stderr

def main():
    print("=== Triage Tests ===\n")
    
    passed = 0
    failed = 0
    
    for fixture_prefix, expected_class, expected_objectives in TEST_CASES:
        print(f"Testing: {fixture_prefix}")
        print(f"  Expected classification: {expected_class}")
        print(f"  Expected objectives: {expected_objectives}")
        
        test_dir = setup_test_dir(fixture_prefix)
        try:
            exit_code, report, stdout, stderr = run_triage(test_dir)
            
            actual_class = report.get("classification", "UNKNOWN")
            actual_objectives = report.get("objectives", [])
            
            print(f"  Actual classification: {actual_class}")
            print(f"  Actual objectives: {actual_objectives}")
            
            class_ok = actual_class == expected_class
            obj_ok = all(obj in actual_objectives for obj in expected_objectives)
            
            if class_ok and obj_ok:
                print(f"  ✅ PASS")
                passed += 1
            else:
                print(f"  ❌ FAIL")
                if not class_ok:
                    print(f"    Classification mismatch: expected {expected_class}, got {actual_class}")
                if not obj_ok:
                    print(f"    Objectives mismatch: expected {expected_objectives} subset of {actual_objectives}")
                print(f"  Stdout: {stdout[:500]}")
                print(f"  Stderr: {stderr[:500]}")
                failed += 1
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
        print()
    
    print(f"=== Results: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())