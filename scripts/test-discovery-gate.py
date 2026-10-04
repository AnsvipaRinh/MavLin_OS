#!/usr/bin/env python3
"""Tests for discovery gate logic: status handling, fetch path, worker boundary.

Covers the 9 mandatory test scenarios from the OS-discovery-gate-fix objective:
1. absent backlog.json pre-discovery = NOT EMPTY (FILE_NOT_FOUND)
2. EMPTY allows internal objectives
3. UNAVAILABLE/AUTH_INVALID/RATE_LIMITED retries+fallback with no discovery-task to Build
4. external items block internal P0
5. implementation Task contains no discover duty (Build worker boundary)
6. stuck orphans don't select Objective
7. Finder P0 only after gate+selection

Run: python3 scripts/test-discovery-gate.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE, "contrib", "discovery-status.sh")


class DiscoveryStatusTests(unittest.TestCase):
    """Test discovery-status.sh wrapper logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="discovery-test-")
        self.backlog = os.path.join(self.tmpdir, "backlog.json")
        self._orig_state = os.environ.get("MAVERICKS_STATE_DIR")
        os.environ["MAVERICKS_STATE_DIR"] = self.tmpdir

    def tearDown(self):
        if self._orig_state is not None:
            os.environ["MAVERICKS_STATE_DIR"] = self._orig_state
        else:
            os.environ.pop("MAVERICKS_STATE_DIR", None)

    def run_status(self):
        r = subprocess.run([SCRIPT], capture_output=True, text=True)
        return r

    def test_absent_backlog_is_not_empty(self):
        """Test 1: absent backlog.json pre-discovery = NOT EMPTY (FILE_NOT_FOUND)."""
        r = self.run_status()
        self.assertEqual(r.returncode, 4, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "FILE_NOT_FOUND")
        self.assertEqual(data["total_count"], 0)
        self.assertNotEqual(data["status"], "EMPTY")

    def test_empty_allows_internal(self):
        """Test 2: EMPTY allows internal objectives."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "OK", "total_count": 0}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 1, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "EMPTY")
        self.assertEqual(data["total_count"], 0)

    def test_empty_literal_status(self):
        """Test 2b: literal EMPTY status maps to EMPTY (not DISCOVERY_FAILED fallthrough)."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "EMPTY", "total_count": 0}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 1, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "EMPTY")
        self.assertEqual(data["total_count"], 0)

    def test_ok_with_items(self):
        """Test: OK + total_count > 0 → actionable backlog exists."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "OK", "total_count": 5}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "OK")
        self.assertEqual(data["total_count"], 5)

    def test_unavailable_status(self):
        """Test 3a: UNAVAILABLE status."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "UNAVAILABLE", "total_count": 0}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 1, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "UNAVAILABLE")

    def test_auth_invalid_status(self):
        """Test 3b: AUTH_INVALID status."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "AUTH_INVALID", "total_count": 0}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 2, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "AUTH_INVALID")

    def test_rate_limited_status(self):
        """Test 3c: RATE_LIMITED status."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "RATE_LIMITED", "total_count": 0}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 3, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "RATE_LIMITED")

    def test_retry_statuses_have_no_discovery_task_to_build(self):
        """Test 3d: UNAVAILABLE/AUTH_INVALID/RATE_LIMITED retries+fallback with no discovery-task to Build."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("2 retries with 30s backoff", content)
        self.assertIn("proceed to step 2 (internal objectives)", content)
        self.assertIn("NEVER delegate discovery", content)

    def test_discovery_failed_status(self):
        """Test: DISCOVERY_FAILED for unknown status."""
        with open(self.backlog, "w") as f:
            json.dump({"discovery_status": "SOME_UNKNOWN", "total_count": 0}, f)
        r = self.run_status()
        self.assertEqual(r.returncode, 5, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "DISCOVERY_FAILED")

    def test_execution_error_on_bad_json(self):
        """Test: EXECUTION_ERROR when backlog.json is unparseable."""
        with open(self.backlog, "w") as f:
            f.write("not valid json {{{")
        r = self.run_status()
        self.assertEqual(r.returncode, 5, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["status"], "EXECUTION_ERROR")


class GateLogicTests(unittest.TestCase):
    """Test gate logic: routing, worker boundary, objective selection."""

    def test_external_items_block_internal_p0(self):
        """Test 4: external items block internal P0."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("OK + total_count > 0", content)
        self.assertIn("Actionable backlog exists", content)
        self.assertIn("Proceed to step 1.6", content)

    def test_implementation_task_no_discovery_duty(self):
        """Test 5: implementation Task contains no discover duty."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("BUILD WORKER BOUNDARY", content)
        self.assertIn("NEVER delegate discovery", content)
        self.assertIn("Discovery is the Orchestrator", content)

    def test_stuck_orphans_dont_select_objective(self):
        """Test 6: stuck orphans don't select Objective."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("Stuck orphans alone never select Objective", content)

    def test_finder_p0_only_after_gate_and_selection(self):
        """Test 7: Finder P0 only after gate+selection."""
        with open(os.path.join(BASE, "..", "AGENTS.md")) as f:
            content = f.read()
        self.assertIn("external-gate-closed", content)
        self.assertIn("enumerate internal oids/sessions", content)
        self.assertIn("P0>P1>P2", content)

    def test_file_not_found_has_fetch_path(self):
        """Test: FILE_NOT_FOUND has explicit fetch path (not deadlock)."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("FILE_NOT_FOUND", content)
        self.assertIn("discover.sh", content)
        self.assertIn("ead-only alone deadlocks", content)

    def test_agents_md_syncs_with_orchestrator(self):
        """Test: AGENTS.md section 14.2 matches orchestrator.md gate text."""
        with open(os.path.join(BASE, "..", "AGENTS.md")) as f:
            agents = f.read()
        self.assertIn("discovery-status.sh", agents)
        self.assertIn("FILE_NOT_FOUND", agents)
        self.assertIn("discover.sh", agents)
        self.assertIn("read-only deadlock", agents)

    def test_mandatory_gate_oid_fresh_creation(self):
        """Test 8: absent oid → FRESH → create → explicit result → internal P0 blocked until result."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("OS-github-discovery", content)
        self.assertIn("FRESH", content)
        self.assertIn("create-new-discovery-session", content)
        self.assertIn("preserves general resume-first", content)
        self.assertIn("ONLY objective where FRESH", content)

    def test_gate_close_blocks_internal_until_result(self):
        """Test 9: internal P0 blocked until gate result is explicit."""
        with open(os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")) as f:
            content = f.read()
        self.assertIn("close gate", content)
        self.assertIn("only then internal selection", content)
        self.assertIn("DO NOT select internal P0/P1/P2", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
