#!/usr/bin/env python3
"""
Test security-scan.sh with fixture patches.
Tests: SAFE_TO_TEST (cosmetic), REJECTED (malicious), REQUIRES_SECURITY_REVIEW (systemd)
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "contrib")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Test cases: (fixture_prefix, expected_verdict, description)
TEST_CASES = [
    ("pr-42", "SAFE_TO_TEST", "Cosmetic/UI change - dock reflection"),
    ("pr-45", "REJECTED", "Malicious PR with curl/download/exec"),
    ("pr-46", "REQUIRES_SECURITY_REVIEW", "Systemd service + script with fs writes"),
    ("pr-43", "REQUIRES_SECURITY_REVIEW", "Hardware/kernel patch with PKGBUILD modify"),
    ("pr-44", "SAFE_TO_TEST", "Documentation only"),
]

def setup_test_dir(fixture_prefix):
    """Create a test review directory with fixture files."""
    test_dir = tempfile.mkdtemp(prefix=f"test-{fixture_prefix}-")
    
    # Copy fixture files
    for ext in ["metadata.json", "patch.diff", "files.jsonl"]:
        src = os.path.join(FIXTURES_DIR, f"{fixture_prefix}-{ext}")
        dst = os.path.join(test_dir, ext.replace("patch.diff", "patch.diff").replace("metadata.json", "metadata.json").replace("files.jsonl", "files.jsonl"))
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            # Create minimal files if missing
            if ext == "metadata.json":
                with open(dst, "w") as f:
                    json.dump({"number": 0, "title": "Test", "changedFiles": 0, "additions": 0, "deletions": 0}, f)
            elif ext == "files.jsonl":
                with open(dst, "w") as f:
                    f.write('')
            elif ext == "patch.diff":
                with open(dst, "w") as f:
                    f.write('')
    
    return test_dir

def run_security_scan(test_dir):
    """Run security-scan.sh and return (exit_code, verdict, findings)."""
    script = os.path.join(SCRIPTS_DIR, "security-scan.sh")
    result = subprocess.run([script, test_dir], capture_output=True, text=True)
    
    # Read the generated report
    report_file = os.path.join(test_dir, "security-scan.json")
    if os.path.exists(report_file):
        with open(report_file) as f:
            report = json.load(f)
        verdict = report.get("verdict", "UNKNOWN")
        findings = report.get("findings", [])
    else:
        verdict = "UNKNOWN"
        findings = []
    
    return result.returncode, verdict, findings, result.stdout, result.stderr

def main():
    print("=== Security Scan Tests ===\n")
    
    passed = 0
    failed = 0
    
    for fixture_prefix, expected_verdict, description in TEST_CASES:
        print(f"Testing: {description} ({fixture_prefix})")
        print(f"  Expected: {expected_verdict}")
        
        test_dir = setup_test_dir(fixture_prefix)
        try:
            exit_code, verdict, findings, stdout, stderr = run_security_scan(test_dir)
            print(f"  Actual:   {verdict} (exit={exit_code})")
            
            if verdict == expected_verdict:
                print(f"  ✅ PASS")
                passed += 1
            else:
                print(f"  ❌ FAIL")
                print(f"  Stdout: {stdout[:500]}")
                print(f"  Stderr: {stderr[:500]}")
                print(f"  Findings: {findings}")
                failed += 1
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
        print()
    
    print(f"=== Results: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())