#!/usr/bin/env python3
"""Tests for scripts/session-reuse.py: SESSION != MODEL (protocol v5).

Pure unit tests (classifier, delay parser, worker resolution) + integration
tests against an in-process mock OpenCode REST server (no live server, no
provider, no network). State files (.opencode/sessions/*) are backed up
byte-exact before the run and restored after every test.

Run: python3 scripts/test-session-reuse.py
"""
import base64
import importlib.util
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE, "session-reuse.py")
REG = os.path.join(BASE, "..", ".opencode", "sessions", "registry.json")
HEALTH = os.path.join(BASE, "..", ".opencode", "sessions", "model-health.json")
LIMITS = os.path.join(BASE, "..", ".opencode", "sessions", "model-limits.json")

spec = importlib.util.spec_from_file_location("sr", SCRIPT)
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)


class MockHandler(BaseHTTPRequestHandler):
    STATUS = {
        "ses_LIVE": {"type": "idle"},
        "ses_BUSY": {"type": "retry",
                     "error": "agent unavailable, retry in 7000 seconds"},
    }
    MSGS = {
        "ses_LIVE": [{"info": {"role": "assistant",
                               "tokens": {"input": 1000}}}],
    }

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/session/status":
            return self._send(200, MockHandler.STATUS)
        if self.path == "/provider":
            return self._send(200, {"all": [
                {"id": "opencode", "models": {
                    "longcat-2.5-preview-free": {"limit": {"context": 1000000}},
                    "nemotron-3-ultra-free": {"limit": {"context": 256000}}}},
                {"id": "openrouter", "models": {
                    "cohere/north-mini-code:free": {"limit": {"context": 256000}}}},
            ]})
        if self.path.startswith("/session/") and self.path.endswith("/message"):
            sid = self.path.split("/")[2]
            if sid in MockHandler.MSGS:
                return self._send(200, MockHandler.MSGS[sid])
            return self._send(404, {"error": "no such session"})
        if self.path.startswith("/session/") and self.path.endswith("/children"):
            return self._send(200, [])
        return self._send(404, {"error": "unknown"})

    def do_DELETE(self):
        return self._send(200, None)


class ScriptCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.saved = {}
        for p in (REG, HEALTH, LIMITS):
            try:
                with open(p, "rb") as f:
                    self.saved[p] = f.read()
            except OSError:
                self.saved[p] = None

    def tearDown(self):
        for p, data in self.saved.items():
            if data is None:
                try:
                    os.remove(p)
                except OSError:
                    pass
            else:
                with open(p, "wb") as f:
                    f.write(data)

    def run_script(self, *args, port=None):
        env = dict(os.environ)
        env["OPENCODE_SERVER_HOST"] = "127.0.0.1"
        env["OPENCODE_SERVER_PORT"] = str(
            port if port is not None else self.port)
        env["OPENCODE_SERVER_USERNAME"] = "u"
        env["OPENCODE_SERVER_PASSWORD"] = "p"
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True, env=env)

    def register_live(self, agent="build",
                      model="opencode/nemotron-3-ultra-free",
                      oid=""):
        args = ["register", "ses_LIVE", "--agent", agent,
                "--objective", "Test Objective", "--task", "do X",
                "--model", model]
        if oid:
            args += ["--oid", oid]
        r = self.run_script(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r


class TaxonomyTests(unittest.TestCase):
    def v(self, text):
        return sr.classify_text(text)[0]

    def test_quota(self):
        self.assertEqual(self.v("monthly quota exhausted, "
                                "insufficient credit balance"), "MODEL_QUOTA")
        # 429 is the stronger signal: rate-limit wins on mixed wording.
        self.assertEqual(self.v("429 quota exceeded"), "MODEL_RATE_LIMIT")

    def test_rate_limit(self):
        self.assertEqual(self.v("429 Too Many Requests, retry later"),
                         "MODEL_RATE_LIMIT")
        self.assertEqual(self.v("rate limit, slow down"), "MODEL_RATE_LIMIT")

    def test_timeout(self):
        self.assertEqual(self.v("generation timed out after 120s"),
                         "MODEL_TIMEOUT")

    def test_network(self):
        self.assertEqual(self.v("socket hang up ECONNRESET"), "NETWORK_ERROR")
        self.assertEqual(self.v("fetch failed, offline?"), "NETWORK_ERROR")

    def test_session(self):
        self.assertEqual(self.v("no such session ses_abc"), "SESSION_ERROR")

    def test_auth(self):
        self.assertEqual(self.v("401 unauthorized, sign in"), "AUTH_ERROR")

    def test_provider(self):
        self.assertEqual(self.v("provider unavailable 503"), "PROVIDER_ERROR")

    def test_agent(self):
        self.assertEqual(self.v("Subagent depth limit reached (1)"),
                         "AGENT_ERROR")

    def test_project_fallback(self):
        self.assertEqual(self.v("test failed: file not found"), "PROJECT_ERROR")
        self.assertEqual(sr.classify_text("   ")[0], "UNKNOWN")

    def test_verdict_table(self):
        self.assertEqual(sr.VERDICTS["MODEL_QUOTA"][0], 10)
        self.assertEqual(sr.VERDICTS["MODEL_RATE_LIMIT"][0], 11)
        self.assertEqual(sr.VERDICTS["CONTEXT_EXHAUSTED"][0], 12)
        self.assertEqual(sr.VERDICTS["MODEL_TIMEOUT"][0], 13)
        self.assertEqual(sr.VERDICTS["PROVIDER_ERROR"][0], 14)
        self.assertEqual(sr.VERDICTS["NETWORK_ERROR"][0], 15)
        self.assertEqual(sr.VERDICTS["SESSION_ERROR"][0], 16)
        self.assertEqual(sr.VERDICTS["AGENT_ERROR"][0], 17)
        self.assertEqual(sr.VERDICTS["PROJECT_ERROR"][0], 20)
        # Only MODEL_* record dead models; network/project must not.
        for name in ("MODEL_QUOTA", "MODEL_RATE_LIMIT", "MODEL_TIMEOUT",
                     "PROVIDER_ERROR"):
            self.assertTrue(sr.VERDICTS[name][1], name)
        for name in ("NETWORK_ERROR", "PROJECT_ERROR", "SESSION_ERROR",
                     "AGENT_ERROR", "AUTH_ERROR", "UNKNOWN",
                     "CONTEXT_EXHAUSTED"):
            self.assertFalse(sr.VERDICTS[name][1], name)


class DelayTests(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(sr.extract_delay_sec(
            {"error": "agent unavailable, retry in 7000 seconds"}), 7000.0)
        self.assertEqual(sr.extract_delay_sec({"retryAfterSec": 7000}), 7000.0)
        self.assertEqual(sr.extract_delay_sec({"nextRetryMs": 610000}), 610.0)
        self.assertIsNone(sr.extract_delay_sec({"type": "idle"}))
        self.assertIsNone(sr.extract_delay_sec({"type": "busy"}))


class DecideTests(ScriptCase):
    def test_resume_same_worker(self):
        self.register_live()
        r = self.run_script("decide", "ses_LIVE", "--objective",
                            "Test Objective", "--limit", "100000")
        self.assertIn("RESUME ses_LIVE", r.stdout, r.stdout + r.stderr)

    def test_resume_different_worker_is_not_new(self):
        # SESSION != MODEL: worker change is failover, not a new session.
        self.register_live(agent="build")
        r = self.run_script("decide", "ses_LIVE", "--objective",
                            "Test Objective", "--agent", "build-b",
                            "--limit", "100000")
        self.assertIn("RESUME ses_LIVE", r.stdout, r.stdout + r.stderr)
        self.assertIn("build-b", r.stdout)
        self.assertNotIn("\nNEW", "\n" + r.stdout)

    def test_stale_id_structured_verdict(self):
        self.run_script("register", "ses_DEAD", "--agent", "build",
                        "--objective", "Test Objective", "--task", "do X")
        r = self.run_script("decide", "ses_DEAD", "--objective",
                            "Test Objective", "--limit", "100000")
        self.assertIn("SESSION_UNAVAILABLE", r.stdout, r.stdout + r.stderr)

    def test_status_unreachable_is_not_new(self):
        self.register_live()
        r = self.run_script("decide", "ses_LIVE", "--objective",
                            "Test Objective", port=1)
        self.assertIn("UNKNOWN", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("\nNEW", "\n" + r.stdout)

    def test_wait_on_busy(self):
        self.run_script("register", "ses_BUSY", "--agent", "build",
                        "--objective", "Test Objective", "--task", "do X")
        r = self.run_script("decide", "ses_BUSY", "--objective",
                            "Test Objective")
        self.assertIn("WAIT", r.stdout, r.stdout + r.stderr)


class MigrateTests(ScriptCase):
    def test_migrate_preserves_session(self):
        self.register_live(agent="build",
                            model="opencode/nemotron-3-ultra-free")
        r = self.run_script("migrate", "ses_LIVE", "--objective",
                            "Test Objective", "--delay", "7000")
        self.assertIn("task_id=ses_LIVE", r.stdout, r.stdout + r.stderr)
        self.assertIn("subagent_type=build-b", r.stdout)
        self.assertNotIn("NO `task_id`", r.stdout)
        with open(REG) as f:
            reg = json.load(f)
        meta = reg["sessions"]["ses_LIVE"]
        self.assertEqual(meta["agent"], "build-b")  # backend switched
        self.assertEqual(meta["state"], "reusable")  # session NOT killed
        self.assertIn("migratedFrom", meta)
        # Cooldown recorded for the dead model with provider delay.
        r2 = self.run_script("health")
        self.assertIn("nemotron-3-ultra-free", r2.stdout)
        self.assertIn("1h56m", r2.stdout)


class ObjectiveTests(ScriptCase):
    def test_find_objective_live(self):
        self.register_live(oid="finder")
        r = self.run_script("find-objective", "finder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("LIVE ses_LIVE", r.stdout)
        self.assertIn("task_id=ses_LIVE", r.stdout)

    def test_find_objective_stale(self):
        self.run_script("register", "ses_DEAD", "--agent", "build",
                        "--objective", "Old", "--task", "do X",
                        "--oid", "ghost")
        r = self.run_script("find-objective", "ghost")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("SESSION_UNAVAILABLE", r.stdout)

    def test_find_objective_isolation(self):
        self.register_live(oid="obj-a")
        self.run_script("register", "ses_BUSY", "--agent", "build",
                        "--objective", "Other", "--task", "do Y",
                        "--oid", "obj-b")
        r = self.run_script("find-objective", "obj-a")
        self.assertIn("ses_LIVE", r.stdout)
        self.assertNotIn("ses_BUSY", r.stdout)

    def test_link_preserves_metadata(self):
        self.register_live()
        with open(REG) as f:
            reg = json.load(f)
        reg["sessions"]["ses_LIVE"]["lastResult"] = "partial work done"
        with open(REG, "w") as f:
            json.dump(reg, f, indent=2)
            f.write("\n")
        r = self.run_script("link-objective", "ses_LIVE", "--oid", "finder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(REG) as f:
            meta = json.load(f)["sessions"]["ses_LIVE"]
        self.assertEqual(meta["oid"], "finder")
        self.assertEqual(meta["lastResult"], "partial work done")

    def test_reregister_preserves_history(self):
        self.register_live()
        with open(REG) as f:
            reg = json.load(f)
        reg["sessions"]["ses_LIVE"]["lastResult"] = "had context"
        with open(REG, "w") as f:
            json.dump(reg, f, indent=2)
            f.write("\n")
        # Re-register after a FAILED generation must not wipe task_id context.
        self.register_live()
        with open(REG) as f:
            meta = json.load(f)["sessions"]["ses_LIVE"]
        self.assertEqual(meta["lastResult"], "had context")


if __name__ == "__main__":
    unittest.main(verbosity=2)
