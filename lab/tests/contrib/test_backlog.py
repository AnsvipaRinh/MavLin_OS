#!/usr/bin/env python3
"""
Test backlog.sh work queue computation.
Tests: prioritization, deduplication by objective, scope classification, sorting.
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "contrib")

def create_test_backlog(state_dir, items):
    """Create a test backlog.json with given items."""
    backlog = {
        "discovered_at": "2026-10-03T12:00:00Z",
        "discovery_status": "OK",
        "exit_code": 0,
        "pr_count": len([i for i in items if i["type"] == "pr"]),
        "issue_count": len([i for i in items if i["type"] == "issue"]),
        "total_count": len(items),
        "prs": [i for i in items if i["type"] == "pr"],
        "issues": [i for i in items if i["type"] == "issue"],
        "objectives": list(set(i["objective"] for i in items))
    }
    backlog_file = os.path.join(state_dir, "backlog.json")
    with open(backlog_file, "w") as f:
        json.dump(backlog, f)
    return backlog_file


def run_backlog(state_dir, output_file=None):
    """Run backlog.sh and return parsed result."""
    script = os.path.join(SCRIPTS_DIR, "backlog.sh")
    args = [script]
    if output_file:
        args.extend(["--output", output_file])
    
    env = os.environ.copy()
    env["MAVERICKS_STATE_DIR"] = state_dir
    
    result = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    
    output_path = output_file or os.path.join(state_dir, "workqueue.json")
    if os.path.exists(output_path):
        with open(output_path) as f:
            workqueue = json.load(f)
    else:
        workqueue = {}
    
    return result.returncode, workqueue, result.stdout, result.stderr


def test_prioritization():
    """Test that P0 objectives come before P1/P2."""
    print("Testing: prioritization (P0 before P1 before P2)")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, "lab", "contrib")
        os.makedirs(state_dir, exist_ok=True)
        
        items = [
            {"type": "pr", "number": 1, "title": "Backend fix", "labels": "", "head_sha": "abc", "updated_at": "2026-10-03T10:00:00Z", "classification": "backend", "objective": "OS-BACKEND"},
            {"type": "pr", "number": 2, "title": "UI component", "labels": "", "head_sha": "def", "updated_at": "2026-10-03T11:00:00Z", "classification": "UI", "objective": "OS-UI-COMPONENT"},
            {"type": "pr", "number": 3, "title": "UX improvement", "labels": "", "head_sha": "ghi", "updated_at": "2026-10-03T12:00:00Z", "classification": "UX", "objective": "OS-UX"},
            {"type": "pr", "number": 4, "title": "Docs update", "labels": "", "head_sha": "jkl", "updated_at": "2026-10-03T09:00:00Z", "classification": "docs", "objective": "OS-DOCS"},
        ]
        
        create_test_backlog(state_dir, items)
        exit_code, workqueue, stdout, stderr = run_backlog(state_dir)
        
        queue = workqueue.get("work_queue", [])
        objectives = [item["objective"] for item in queue]
        
        print(f"  Queue order: {objectives}")
        
        # P0 objectives (priority 10): OS-UI-COMPONENT, OS-UX, OS-INTEGRATION
        # Should come before P1 (priority 20): OS-BACKEND, OS-PERF
        # Should come before P2 (priority 40): OS-DOCS
        
        expected_order = ["OS-UX", "OS-UI-COMPONENT", "OS-BACKEND", "OS-DOCS"]
        # Note: exact order among same priority depends on updated_at (newest first)
        
        # Check that P0 objectives are before P1/P2
        ux_idx = objectives.index("OS-UX") if "OS-UX" in objectives else 99
        ui_idx = objectives.index("OS-UI-COMPONENT") if "OS-UI-COMPONENT" in objectives else 99
        backend_idx = objectives.index("OS-BACKEND") if "OS-BACKEND" in objectives else 99
        docs_idx = objectives.index("OS-DOCS") if "OS-DOCS" in objectives else 99
        
        ok = (ux_idx < backend_idx and ux_idx < docs_idx and
              ui_idx < backend_idx and ui_idx < docs_idx)
        
        if ok:
            print("  ✅ PASS")
            return True
        else:
            print("  ❌ FAIL")
            print(f"  Expected P0 before P1/P2")
            return False


def test_deduplication():
    """Test that items with same objective are deduplicated (keep highest priority/newest)."""
    print("Testing: deduplication by objective")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, "lab", "contrib")
        os.makedirs(state_dir, exist_ok=True)
        
        items = [
            {"type": "pr", "number": 1, "title": "UI fix v1", "labels": "", "head_sha": "abc", "updated_at": "2026-10-01T10:00:00Z", "classification": "UI", "objective": "OS-UI-COMPONENT"},
            {"type": "pr", "number": 2, "title": "UI fix v2 (newer)", "labels": "", "head_sha": "def", "updated_at": "2026-10-03T10:00:00Z", "classification": "UI", "objective": "OS-UI-COMPONENT"},
            {"type": "issue", "number": 3, "title": "UI issue", "labels": "", "updated_at": "2026-10-02T10:00:00Z", "comments": 5, "classification": "UI", "objective": "OS-UI-COMPONENT"},
        ]
        
        create_test_backlog(state_dir, items)
        exit_code, workqueue, stdout, stderr = run_backlog(state_dir)
        
        queue = workqueue.get("work_queue", [])
        ui_items = [item for item in queue if item["objective"] == "OS-UI-COMPONENT"]
        
        print(f"  Total items in queue: {len(queue)}")
        print(f"  OS-UI-COMPONENT items: {len(ui_items)}")
        
        # Should keep only 1 item per objective (the highest priority, newest)
        if len(ui_items) == 1 and ui_items[0]["number"] == 2:
            print("  ✅ PASS (kept newest PR #2)")
            return True
        else:
            print("  ❌ FAIL")
            print(f"  Kept: {[item['number'] for item in ui_items]}")
            return False


def test_scope_classification():
    """Test hardware-profile vs core scope classification."""
    print("Testing: scope classification (core vs hardware-profile)")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, "lab", "contrib")
        os.makedirs(state_dir, exist_ok=True)
        
        # Use different objectives for each hardware item to avoid deduplication
        items = [
            {"type": "pr", "number": 1, "title": "Theme update", "labels": "", "head_sha": "abc", "updated_at": "2026-10-03T10:00:00Z", "classification": "cosmetic", "objective": "OS-UI-COSMETIC"},
            {"type": "pr", "number": 2, "title": "MacBook keyboard fix", "labels": "macbook,hardware", "head_sha": "def", "updated_at": "2026-10-03T11:00:00Z", "classification": "hw", "objective": "OS-HW-KEYBOARD"},
            {"type": "pr", "number": 3, "title": "SPI driver for applespi", "labels": "", "head_sha": "ghi", "updated_at": "2026-10-03T12:00:00Z", "classification": "hw", "objective": "OS-HW-SPI"},
            {"type": "issue", "number": 4, "title": "WiFi BCM43602", "labels": "wifi,hardware", "updated_at": "2026-10-03T09:00:00Z", "comments": 0, "classification": "hw", "objective": "OS-HW-WIFI"},
        ]
        
        create_test_backlog(state_dir, items)
        exit_code, workqueue, stdout, stderr = run_backlog(state_dir)
        
        queue = workqueue.get("work_queue", [])
        core_items = [item for item in queue if item["scope"] == "core"]
        hw_items = [item for item in queue if item["scope"] == "hardware-profile"]
        
        print(f"  Core items: {len(core_items)}, Hardware-profile items: {len(hw_items)}")
        print(f"  Core objectives: {[item['objective'] for item in core_items]}")
        print(f"  HW objectives: {[item['objective'] for item in hw_items]}")
        
        ok = (len(core_items) == 1 and core_items[0]["objective"] == "OS-UI-COSMETIC" and
              len(hw_items) == 3 and all(item["scope"] == "hardware-profile" for item in hw_items))
        
        if ok:
            print("  ✅ PASS")
            return True
        else:
            print("  ❌ FAIL")
            return False


def test_empty_backlog():
    """Test backlog.sh with EMPTY discovery status."""
    print("Testing: empty backlog handling")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, "lab", "contrib")
        os.makedirs(state_dir, exist_ok=True)
        
        # Create backlog with EMPTY status
        backlog = {
            "discovered_at": "2026-10-03T12:00:00Z",
            "discovery_status": "EMPTY",
            "exit_code": 0,
            "pr_count": 0,
            "issue_count": 0,
            "total_count": 0,
            "prs": [],
            "issues": [],
            "objectives": []
        }
        backlog_file = os.path.join(state_dir, "backlog.json")
        with open(backlog_file, "w") as f:
            json.dump(backlog, f)
        
        exit_code, workqueue, stdout, stderr = run_backlog(state_dir)
        
        queue = workqueue.get("work_queue", [])
        total = workqueue.get("summary", {}).get("total", -1)
        
        print(f"  Work queue length: {len(queue)}, Total: {total}")
        
        if len(queue) == 0 and total == 0:
            print("  ✅ PASS")
            return True
        else:
            print("  ❌ FAIL")
            return False


def test_unavailable_backlog():
    """Test backlog.sh with UNAVAILABLE discovery status."""
    print("Testing: unavailable backlog handling")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, "lab", "contrib")
        os.makedirs(state_dir, exist_ok=True)
        
        backlog = {
            "discovered_at": "2026-10-03T12:00:00Z",
            "discovery_status": "UNAVAILABLE",
            "exit_code": 1,
            "pr_count": 0,
            "issue_count": 0,
            "total_count": 0,
            "prs": [],
            "issues": [],
            "objectives": []
        }
        backlog_file = os.path.join(state_dir, "backlog.json")
        with open(backlog_file, "w") as f:
            json.dump(backlog, f)
        
        exit_code, workqueue, stdout, stderr = run_backlog(state_dir)
        
        source_status = workqueue.get("source_discovery_status", "MISSING")
        queue = workqueue.get("work_queue", [])
        
        print(f"  Source status: {source_status}, Queue length: {len(queue)}")
        
        if source_status == "UNAVAILABLE" and len(queue) == 0:
            print("  ✅ PASS")
            return True
        else:
            print("  ❌ FAIL")
            return False


def main():
    print("=== Backlog Work Queue Tests ===\n")
    
    tests = [
        test_prioritization,
        test_deduplication,
        test_scope_classification,
        test_empty_backlog,
        test_unavailable_backlog,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ FAIL (exception: {e})")
            failed += 1
        print()
    
    print(f"=== Results: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())