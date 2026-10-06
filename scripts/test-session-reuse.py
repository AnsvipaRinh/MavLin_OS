#!/usr/bin/env python3
"""Tests for orchestration scripts: SESSION != MODEL (protocol v11).

Pure unit tests (classifier, delay parser, worker resolution) + integration
tests against an in-process mock OpenCode REST server (no live server, no
provider, no network). Hermetic by construction: $SR_STATE_DIR points all
state files (registry/health/limits/journal/lock) at a temp dir, so a live
watchdog daemon running in parallel can neither pollute results nor be
touched by them. Per-test wipe keeps a clean slate without backup/restore.

Run: python3 scripts/test-session-reuse.py
"""
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time as _time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["SR_STATE_DIR"] = tempfile.mkdtemp(prefix="sr-state-test-")

BASE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE, "session-reuse.py")


def _sp(name):
    return os.path.join(os.environ["SR_STATE_DIR"], name)


REG = _sp("registry.json")
HEALTH = _sp("model-health.json")
LIMITS = _sp("model-limits.json")
WDLOG = _sp("watchdog.log")
WATCHDOG = os.path.join(BASE, "task-watchdog.py")

spec = importlib.util.spec_from_file_location("sr", SCRIPT)
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)


class MockHandler(BaseHTTPRequestHandler):
    # ses_QUIET: exists + has history, but ABSENT from /session/status
    # (post-restart idle shape). ses_MSGBROKEN: exists, token endpoint 404.
    STATUS = {
        "ses_LIVE": {"type": "idle"},
        "ses_BUSY": {"type": "retry",
                     "error": "agent unavailable, retry in 7000 seconds"},
        "ses_WORKING": {"type": "busy"},
        "ses_SOON": {"type": "retry", "attempt": 1,
                     "message": "rate limited, retry in 60 seconds"},
        "ses_ORPHAN": {"type": "retry", "attempt": 2,
                       "message": "Free usage exceeded",
                       "next": int(_time.time() * 1000) + 4500 * 1000},
        "ses_WAITWORD": {"type": "retry", "attempt": 1,
                         "message": "agent unavailable"},
        "ses_ESC": {"type": "retry", "attempt": 1,
                    "message": "agent unavailable"},
        "ses_TOOLABORT": {"type": "busy"},
    }
    SESSIONS = {"ses_LIVE", "ses_BUSY", "ses_QUIET", "ses_MSGBROKEN",
                "ses_WORKING", "ses_SOON", "ses_NEXT", "ses_ORPHAN",
                "ses_WAITWORD", "ses_STRANGER", "ses_ESC", "ses_TOOLABORT",
                "ses_STALLED", "ses_FRESHSTALL", "ses_ANCIENT",
                "ses_DEEPSTALL"}
    # Live-store metadata for GET /session[/{id}]: directory/title/parent.
    META = {
        "ses_ORPHAN": {"directory": "/proj",
                       "title": "Do thing (@build subagent)",
                       "parentID": "ses_PARENT",
                       "agent": "build"},
        "ses_STRANGER": {"directory": "/proj", "title": "user notes",
                         "parentID": "",
                         "agent": "user"},
    }
    ABORTS = []
    MSGS = {
        "ses_LIVE": [{"info": {"role": "assistant",
                               "tokens": {"input": 1000}}}],
        "ses_QUIET": [{"info": {"role": "assistant",
                                "tokens": {"input": 200000}}}],
        "ses_ORPHAN": [{"info": {"role": "assistant",
                                 "tokens": {"input": 50000},
                                 "modelID": "longcat-2.5-preview-free",
                                 "providerID": "opencode"}}],
        "ses_ANCIENT": [{"info": {"role": "user"},
                          "parts": [{"type": "text", "text": "old work"}]},
                         {"info": {"role": "assistant", "finish": None,
                                   "tokens": {"input": 90000, "output": 0},
                                   "modelID": "cohere/north-mini-code:free",
                                   "providerID": "openrouter",
                                   "time": {"created": int(_time.time() * 1000)
                                            - 3 * 24 * 3600 * 1000}},
                          "parts": []}],
        "ses_TOOLABORT": [{"info": {"role": "assistant", "finish": None,
                                    "tokens": {"input": 1000},
                                    "modelID": "longcat-2.5-preview-free",
                                    "providerID": "opencode"},
                           "parts": [{"type": "tool", "tool": "bash",
                                      "state": {"status": "error",
                                                "error": "Tool execution aborted",
                                                "metadata": {"interrupted": True}}}]}],
        "ses_STALLED": [{"info": {"role": "user"},
                         "parts": [{"type": "text", "text": "do work"}]},
                        {"info": {"role": "assistant", "finish": None,
                                  "tokens": {"input": 150000, "output": 0,
                                             "reasoning": 0},
                                  "modelID": "longcat-2.5-preview-free",
                                  "providerID": "opencode",
                                  "time": {"created": int(_time.time() * 1000)
                                           - 3600 * 1000}},
                         "parts": []}],
        "ses_FRESHSTALL": [{"info": {"role": "user"},
                            "parts": [{"type": "text", "text": "do work"}]},
                           {"info": {"role": "assistant", "finish": None,
                                     "tokens": {"input": 10, "output": 0},
                                     "modelID": "longcat-2.5-preview-free",
                                     "providerID": "opencode",
                                     "time": {"created": int(_time.time() * 1000)
                                              - 30 * 1000}},
                            "parts": []}],
        # Prompt buried 7 messages back behind tool-call rounds (live case).
        "ses_DEEPSTALL": [{"info": {"role": "user"},
                           "parts": [{"type": "text", "text": "do work"}]}] + [
            {"info": {"role": "assistant", "finish": "tool-calls",
                      "tokens": {"input": 500, "output": 42}},
             "parts": []} for _ in range(6)] + [
            {"info": {"role": "assistant", "finish": None,
                      "tokens": {"input": 200000, "output": 0},
                      "modelID": "nemotron-3-ultra-free",
                      "providerID": "opencode",
                      "time": {"created": int(_time.time() * 1000)
                               - 3600 * 1000}},
             "parts": []}],
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
        if self.path == "/session/status" or \
                self.path.startswith("/session/status?"):
            return self._send(200, MockHandler.STATUS)
        if self.path == "/session" or self.path.startswith("/session?"):
            return self._send(200, [
                dict({"id": s}, **MockHandler.META.get(s, {}))
                for s in sorted(MockHandler.SESSIONS)])
        if self.path == "/session":
            return self._send(200, [{"id": s} for s in
                                    sorted(MockHandler.SESSIONS)])
        bare = self.path.split("?", 1)[0]
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        if bare.startswith("/session/") and bare.endswith("/message"):
            sid = bare.split("/")[2]
            if sid in MockHandler.MSGS:
                msgs = MockHandler.MSGS[sid]
                m = re.search(r"limit=(\d+)", query)
                if m:
                    msgs = msgs[-int(m.group(1)):]
                return self._send(200, msgs)
            return self._send(404, {"error": "no such session"})
        if bare.startswith("/session/") and bare.endswith("/children"):
            return self._send(200, [])
        if bare.startswith("/session/"):
            sid = bare.split("/")[2]
            if sid in MockHandler.SESSIONS:
                return self._send(200, dict(
                    {"id": sid, "title": sid},
                    **MockHandler.META.get(sid, {})))
            return self._send(404, {"error": "no such session"})
        if self.path == "/provider":
            return self._send(200, {"all": [
                {"id": "opencode", "models": {
                    "longcat-2.5-preview-free": {"limit": {"context": 1000000}},
                    "nemotron-3-ultra-free": {"limit": {"context": 256000}}}},
                {"id": "openrouter", "models": {
                    "cohere/north-mini-code:free": {"limit": {"context": 256000}}}},
            ]})
        return self._send(404, {"error": "unknown"})

    def do_POST(self):
        if self.path.startswith("/session/") and self.path.endswith("/abort"):
            sid = self.path.split("/")[2]
            if sid in MockHandler.SESSIONS:
                return self._send(200, {"aborted": True})
            return self._send(404, {"error": "no such session"})
        return self._send(404, {"error": "unknown"})

    def do_POST(self):
        if self.path.startswith("/session/") and self.path.endswith("/abort"):
            sid = self.path.split("/")[2]
            if sid in MockHandler.SESSIONS:
                MockHandler.ABORTS.append(sid)
                return self._send(200, {"aborted": True})
            return self._send(404, {"error": "no such session"})
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
        cls.server.server_close()

    def setUp(self):
        # Hermetic slate: wipe the temp state dir (no backup/restore needed —
        # production files are untouched by construction via $SR_STATE_DIR).
        for name in ("registry.json", "model-health.json",
                     "model-limits.json", "watchdog.log"):
            try:
                os.remove(os.path.join(os.environ["SR_STATE_DIR"], name))
            except OSError:
                pass
        MockHandler.ABORTS = []

    def run_script(self, *args, port=None):
        env = dict(os.environ)
        env["OPENCODE_SERVER_HOST"] = "127.0.0.1"
        env["OPENCODE_SERVER_PORT"] = str(
            port if port is not None else self.port)
        env["OPENCODE_SERVER_USERNAME"] = "u"
        env["OPENCODE_SERVER_PASSWORD"] = "p"
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True, env=env)

    def run_watchdog(self, *args):
        env = dict(os.environ)
        env["OPENCODE_SERVER_HOST"] = "127.0.0.1"
        env["OPENCODE_SERVER_PORT"] = str(self.port)
        env["OPENCODE_SERVER_USERNAME"] = "u"
        env["OPENCODE_SERVER_PASSWORD"] = "p"
        return subprocess.run([sys.executable, WATCHDOG, *args],
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
        # Live provider wordings observed 2026-10-02 (were PROJECT_ERROR).
        self.assertEqual(self.v(
            "Streaming response failed: [504] Upstream idle timeout exceeded"),
            "MODEL_TIMEOUT")
        self.assertEqual(self.v(
            "Streaming response failed: [503] Upstream error from Nvidia: "
            "Service temporarily overloaded"), "MODEL_QUOTA")
        self.assertEqual(self.v(
            "Rate limit exceeded: free-models-per-day. Add 10 credits"),
            "MODEL_RATE_LIMIT")

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

    def test_free_usage_exceeded(self):
        self.assertEqual(self.v("Free usage exceeded, retry in 5600s"),
                         "FREE_USAGE_EXHAUSTED")
        self.assertEqual(sr.VERDICTS["FREE_USAGE_EXHAUSTED"][0], 18)
        self.assertTrue(sr.VERDICTS["FREE_USAGE_EXHAUSTED"][1])

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
        # Register a session on the CURRENT primary model, migrate after
        # a simulated provider delay -> cooldown recorded, next healthy
        # worker (first fallback by CHAIN ORDER — build-j since the GLM
        # restoration; never hardcode the role) becomes the new backend.
        primary_model = sr.worker_pins()[0][1]
        expected_role, _m, _w = sr.resolve_next_worker([primary_model])
        self.assertTrue(expected_role)
        self.register_live(agent="build", model=primary_model)
        r = self.run_script("migrate", "ses_LIVE", "--objective",
                            "Test Objective", "--delay", "7000")
        self.assertIn("task_id=ses_LIVE", r.stdout, r.stdout + r.stderr)
        self.assertIn(f"subagent_type={expected_role}", r.stdout)
        self.assertNotIn("NO `task_id`", r.stdout)
        with open(REG) as f:
            reg = json.load(f)
        meta = reg["sessions"]["ses_LIVE"]
        self.assertEqual(meta["agent"], expected_role)  # backend switched
        self.assertEqual(meta["state"], "reusable")  # session NOT killed
        self.assertIn("migratedFrom", meta)
        # Cooldown recorded for the dead model with provider delay.
        r2 = self.run_script("health")
        self.assertIn(primary_model.split("/")[-1], r2.stdout)
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


class ExistenceTests(ScriptCase):
    """Acceptance: status absence != nonexistence; API down != NEW."""

    def reg(self, sid, objective="Test Objective"):
        r = self.run_script("register", sid, "--agent", "build",
                            "--objective", objective, "--task", "do X")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_status_absent_but_exists_resumes(self):
        # ses_QUIET: GET /session works, /session/status has NO entry
        # (post-restart idle shape). Must RESUME, never NEW.
        self.reg("ses_QUIET")
        r = self.run_script("decide", "ses_QUIET", "--objective",
                            "Test Objective")
        self.assertIn("RESUME ses_QUIET", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("SESSION_UNAVAILABLE", r.stdout)

    def test_token_endpoint_down_no_duplicate(self):
        # ses_MSGBROKEN: exists, history endpoint 404. Must NOT fork.
        self.reg("ses_MSGBROKEN")
        r = self.run_script("decide", "ses_MSGBROKEN", "--objective",
                            "Test Objective")
        self.assertIn("RESUME ses_MSGBROKEN", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("\nNEW", "\n" + r.stdout)

    def test_exists_command_idle(self):
        r = self.run_script("exists", "ses_LIVE")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SESSION_EXISTS_IDLE", r.stdout)

    def test_exists_command_retrying(self):
        r = self.run_script("exists", "ses_BUSY")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SESSION_EXISTS_RETRYING", r.stdout)
        self.assertIn("7000s", r.stdout)

    def test_exists_command_missing(self):
        r = self.run_script("exists", "ses_NOPE")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("SESSION_DOES_NOT_EXIST", r.stdout)

    def test_exists_command_unreachable(self):
        r = self.run_script("exists", "ses_LIVE", port=1)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("SESSION_API_UNAVAILABLE", r.stdout)

    def test_find_objective_status_absent(self):
        self.run_script("register", "ses_QUIET", "--agent", "build",
                        "--objective", "Quiet", "--task", "do X",
                        "--oid", "quiet-o")
        r = self.run_script("find-objective", "quiet-o")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("LIVE ses_QUIET", r.stdout)
        self.assertIn("task_id=ses_QUIET", r.stdout)


class AbortTests(ScriptCase):
    def test_abort_live(self):
        r = self.run_script("abort", "ses_BUSY")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ABORTED (ses_BUSY", r.stdout)
        self.assertIn("history preserved", r.stdout)

    def test_abort_missing(self):
        r = self.run_script("abort", "ses_NOPE")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("does not exist", r.stdout)


class PreflightTests(ScriptCase):
    def test_preflight_ready(self):
        r = self.run_script("preflight")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRIMARY_READY build", r.stdout)
        self.assertIn("PREFLIGHT_OK subagent_type=build", r.stdout)

    def test_preflight_skips_cooldown_primary(self):
        # Primary model in cooldown -> next healthy worker BEFORE any Task.
        # Expected fallback derived from the chain (never hardcoded).
        primary_model = sr.worker_pins()[0][1]
        expected_role = sr.resolve_next_worker([primary_model])[0]
        self.assertTrue(expected_role)
        self.run_script("mark-dead", primary_model, "--reason", "test")
        r = self.run_script("preflight")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRIMARY_COOLDOWN build", r.stdout)
        self.assertIn(f"PREFLIGHT_OK subagent_type={expected_role}", r.stdout)

    def test_preflight_all_cooling_waits(self):
        # ALL worker pins must cool (pool size comes from live config,
        # not a hardcoded triple — the pool grew before).
        for _role, m in sr.worker_pins():
            self.run_script("mark-dead", m, "--reason", "test")
        r = self.run_script("preflight")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("PREFLIGHT_WAIT", r.stdout)


class NextFieldTests(unittest.TestCase):
    """The 1.18.32 retry status is {type:retry, attempt, message, next}."""

    def test_next_ms_epoch(self):
        import time
        nxt = int(time.time() * 1000) + 4500 * 1000
        d = sr.extract_delay_sec({"type": "retry", "attempt": 3,
                                  "message": "Free usage exceeded",
                                  "next": nxt})
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 4500, delta=120)

    def test_next_seconds(self):
        self.assertEqual(sr.extract_delay_sec({"type": "retry",
                                               "next": 4500}), 4500.0)

    def test_next_past(self):
        import time
        self.assertIsNone(sr.extract_delay_sec(
            {"type": "retry", "next": int(time.time() * 1000) - 60000}))


class WatchdogTests(ScriptCase):
    def reg_busy(self):
        # Register a busy session on the CURRENT primary model so the
        # watchdog learns that model from the registry meta.
        r = self.run_script("register", "ses_BUSY", "--agent", "build",
                            "--objective", "Busy Objective", "--task", "do Y",
                            "--model", sr.worker_pins()[0][1],
                            "--oid", "busy-o")
        self.assertEqual(r.returncode, 0, r.stderr)

    def journal_lines(self):
        # Tolerant reader: a live daemon may append mid-read (torn tail
        # line); skip unparseable lines instead of failing.
        try:
            with open(WDLOG) as f:
                content = f.read()
        except OSError:
            return []
        out = []
        for line in content.split("\n"):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    def test_abort_dead_retry_over_threshold(self):
        self.reg_busy()
        r = self.run_watchdog("--once", "--session", "ses_BUSY",
                              "--threshold", "600")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("aborted ses_BUSY", r.stdout)
        self.assertIn("ses_BUSY", MockHandler.ABORTS)
        # Cooldown recorded with observed delay (~7000s).
        r2 = self.run_script("health")
        primary_model = sr.worker_pins()[0][1]
        self.assertIn(primary_model.split("/")[-1], r2.stdout)
        self.assertIn("1h56m", r2.stdout)
        # Registry lastAbort recorded, session NOT killed/replaced.
        with open(REG) as f:
            meta = json.load(f)["sessions"]["ses_BUSY"]
        self.assertIn("lastAbort", meta)
        self.assertAlmostEqual(meta["lastAbort"]["delaySec"], 7000, delta=60)
        self.assertEqual(meta["state"], "reusable")
        evs = self.journal_lines()
        self.assertTrue(any(e.get("event") == "ABORTED" and
                            e.get("session") == "ses_BUSY" for e in evs))

    def test_no_abort_busy(self):
        self.run_script("register", "ses_WORKING", "--agent", "build",
                        "--objective", "W", "--task", "do W")
        r = self.run_watchdog("--once", "--session", "ses_WORKING")
        self.assertIn("ok ses_WORKING", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("ses_WORKING", MockHandler.ABORTS)

    def test_no_abort_short_retry(self):
        self.run_script("register", "ses_SOON", "--agent", "build",
                        "--objective", "S", "--task", "do S")
        r = self.run_watchdog("--once", "--session", "ses_SOON",
                              "--threshold", "600")
        self.assertIn("watch ses_SOON", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("ses_SOON", MockHandler.ABORTS)

    def test_abort_tool_quota_without_status_retry(self):
        # Busy status (no retry entry) + interrupted tool abort in the
        # message tail = quota exhaustion the status endpoint hides.
        self.run_script("register", "ses_TOOLABORT", "--agent", "build",
                        "--objective", "T", "--task", "do T",
                        "--model", "opencode/longcat-2.5-preview-free")
        r = self.run_watchdog("--once", "--session", "ses_TOOLABORT",
                              "--threshold", "600")
        self.assertIn("aborted ses_TOOLABORT", r.stdout, r.stdout + r.stderr)
        self.assertIn("ses_TOOLABORT", MockHandler.ABORTS)

    def test_no_abort_idle(self):
        self.register_live()
        r = self.run_watchdog("--once", "--session", "ses_LIVE")
        self.assertIn("ok ses_LIVE", r.stdout, r.stdout + r.stderr)
        self.assertEqual(MockHandler.ABORTS, [])

    def test_gone_session(self):
        r = self.run_watchdog("--once", "--session", "ses_NOPE")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("gone ses_NOPE", r.stdout)

    def test_migrate_uses_abort_delay(self):
        # migrate without --delay picks up a fresh watchdog abort record.
        # Primary model is aborted -> cooldown recorded with observed delay
        # -> migrate picks next healthy worker by chain order (derived,
        # not hardcoded — build-j since the GLM restoration).
        expected_role = sr.resolve_next_worker(
            [sr.worker_pins()[0][1]])[0]
        self.assertTrue(expected_role)
        self.reg_busy()
        self.run_watchdog("--once", "--session", "ses_BUSY",
                          "--threshold", "600")
        r = self.run_script("migrate", "ses_BUSY", "--objective",
                            "Busy Objective")
        self.assertIn("task_id=ses_BUSY", r.stdout, r.stdout + r.stderr)
        self.assertIn(f"subagent_type={expected_role}", r.stdout)
        r2 = self.run_script("health")
        self.assertIn("1h56m", r2.stdout)  # abort delay, not 3h default


class DiscoveryTests(ScriptCase):
    """The stuck session whose Task never returned is unregistered by
    definition. The watchdog must still find, abort and track it."""

    def test_orphan_discovered_aborted_upserted(self):
        # ses_ORPHAN is NOT in the registry: straight --all discovery.
        r = self.run_watchdog("--once", "--all", "--directory", "/proj",
                              "--threshold", "600")
        self.assertIn("aborted ses_ORPHAN", r.stdout, r.stdout + r.stderr)
        self.assertIn("ses_ORPHAN", MockHandler.ABORTS)
        with open(REG) as f:
            meta = json.load(f)["sessions"]["ses_ORPHAN"]
        # Model learned from the bounded message tail, not guessed.
        self.assertEqual(meta["model"], "opencode/longcat-2.5-preview-free")
        self.assertIn("lastAbort", meta)
        r2 = self.run_script("health")
        self.assertIn("longcat-2.5-preview-free", r2.stdout)
        # Follow-up migrate reuses the SAME id with no --objective needed.
        r3 = self.run_script("migrate", "ses_ORPHAN")
        self.assertIn("task_id=ses_ORPHAN", r3.stdout, r3.stdout + r.stderr)

    def test_stranger_ignored(self):
        # Same directory but no subagent marker and untracked: not ours.
        r = self.run_watchdog("--once", "--all", "--directory", "/proj")
        self.assertNotIn("ses_STRANGER", r.stdout)
        self.assertNotIn("ses_STRANGER", MockHandler.ABORTS)
        with open(REG) as f:
            self.assertNotIn("ses_STRANGER", json.load(f)["sessions"])

    def test_waitword_without_delay_never_aborts(self):
        # Words alone ("agent unavailable", no parseable delay) must not
        # abort: only proven-long provider waits are interrupted.
        self.run_script("register", "ses_WAITWORD", "--agent", "build",
                        "--objective", "W", "--task", "do W")
        r = self.run_watchdog("--once", "--session", "ses_WAITWORD",
                              "--threshold", "600")
        self.assertIn("watch ses_WAITWORD", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("ses_WAITWORD", MockHandler.ABORTS)

    def with_mock_server(self):
        os.environ["OPENCODE_SERVER_HOST"] = "127.0.0.1"
        os.environ["OPENCODE_SERVER_PORT"] = str(self.port)
        os.environ["OPENCODE_SERVER_USERNAME"] = "u"
        os.environ["OPENCODE_SERVER_PASSWORD"] = "p"
        # Purge cached auto-discovery so direct in-process calls hit mock.
        sr._server_cache.update(at=0.0, port="")
        self.addCleanup(os.environ.pop, "OPENCODE_SERVER_HOST", None)
        self.addCleanup(os.environ.pop, "OPENCODE_SERVER_PORT", None)
        self.addCleanup(os.environ.pop, "OPENCODE_SERVER_USERNAME", None)
        self.addCleanup(os.environ.pop, "OPENCODE_SERVER_PASSWORD", None)

    def test_stalled_old_zero_output(self):
        self.with_mock_server()
        stalled, age, model = sr.stalled_generation("ses_STALLED", 600)
        self.assertTrue(stalled)
        self.assertGreater(age, 600)
        self.assertEqual(model, "opencode/longcat-2.5-preview-free")

    def test_stalled_fresh_is_not_stalled(self):
        self.with_mock_server()
        stalled, age, _m = sr.stalled_generation("ses_FRESHSTALL", 600)
        self.assertFalse(stalled)
        self.assertLess(age, 600)

    def test_stalled_with_progress_is_not_stalled(self):
        # ses_LIVE: assistant message but no preceding user prompt.
        self.with_mock_server()
        stalled, _a, _m = sr.stalled_generation("ses_LIVE", 600)
        self.assertFalse(stalled)

    def test_stalled_prompt_buried_behind_tool_rounds(self):
        # Live case: 9 completed tool rounds hide the user prompt;
        # limit=3 missed it, limit=8 must catch the stall.
        self.with_mock_server()
        stalled, age, model = sr.stalled_generation("ses_DEEPSTALL", 600)
        self.assertTrue(stalled)
        self.assertGreater(age, 600)
        self.assertEqual(model, "opencode/nemotron-3-ultra-free")

    def test_stalled_unknown_session(self):
        self.with_mock_server()
        stalled, _a, _m = sr.stalled_generation("ses_NOPE", 600)
        self.assertFalse(stalled)

    def test_stalled_cmd_exit_codes(self):
        r = self.run_script("stalled", "ses_STALLED", "--threshold", "600")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("STALLED ses_STALLED", r.stdout)
        r = self.run_script("stalled", "ses_FRESHSTALL", "--threshold", "600")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_watchdog_aborts_status_blind_stall(self):
        # No status entry (idle map) + 0-token shell older than threshold
        # = abort, even though /session/status shows nothing.
        self.run_script("register", "ses_STALLED", "--agent", "build",
                        "--objective", "ST", "--task", "do ST",
                        "--model", "opencode/longcat-2.5-preview-free")
        r = self.run_watchdog("--once", "--session", "ses_STALLED",
                              "--threshold", "600")
        self.assertIn("aborted ses_STALLED", r.stdout, r.stdout + r.stderr)
        self.assertIn("ses_STALLED", MockHandler.ABORTS)
        with open(REG) as f:
            meta = json.load(f)["sessions"]["ses_STALLED"]
        self.assertIn("lastAbort", meta)
        self.assertEqual(meta["state"], "reusable")

    def test_ancient_stall_aborts_without_cooldown(self):
        # 3-day-old 0-token shell: abort is harmless, but the evidence is
        # too stale to judge today's backend — no cooldown may be recorded.
        self.run_script("register", "ses_ANCIENT", "--agent", "build",
                        "--objective", "ANC", "--task", "do ANC",
                        "--model", "openrouter/cohere/north-mini-code:free")
        r = self.run_watchdog("--once", "--session", "ses_ANCIENT",
                              "--threshold", "600")
        self.assertIn("aborted ses_ANCIENT", r.stdout, r.stdout + r.stderr)
        self.assertIn("ses_ANCIENT", MockHandler.ABORTS)
        r2 = self.run_script("health")
        self.assertNotIn("north-mini", r2.stdout)

    def test_no_reabort_when_tail_unchanged(self):
        # First abort records lastAbort; second run sees the same tail and
        # must NOT abort again (no cooldown creep, no journal spam).
        self.run_script("register", "ses_STALLED", "--agent", "build",
                        "--objective", "ST", "--task", "do ST",
                        "--model", "opencode/longcat-2.5-preview-free")
        r1 = self.run_watchdog("--once", "--session", "ses_STALLED",
                               "--threshold", "600")
        self.assertIn("aborted ses_STALLED", r1.stdout, r1.stdout + r1.stderr)
        n1 = MockHandler.ABORTS.count("ses_STALLED")
        r2 = self.run_watchdog("--once", "--session", "ses_STALLED",
                               "--threshold", "600")
        self.assertIn("already aborted", r2.stdout, r2.stdout + r2.stderr)
        self.assertEqual(MockHandler.ABORTS.count("ses_STALLED"), n1)

    def test_unclassified_wait_still_cools_down(self):
        # "agent unavailable" has no quota wording (verdict UNKNOWN), but a
        # PROVEN 7000s provider wait is a timetable fact: abort + cooldown.
        self.run_script("register", "ses_BUSY", "--agent", "build",
                        "--objective", "B", "--task", "do B",
                        "--model", "opencode/nemotron-3-ultra-free")
        r = self.run_watchdog("--once", "--session", "ses_BUSY",
                              "--threshold", "600")
        self.assertIn("aborted ses_BUSY", r.stdout, r.stdout + r.stderr)
        self.assertIn("ses_BUSY", MockHandler.ABORTS)
        r2 = self.run_script("health")
        self.assertIn("nemotron-3-ultra-free", r2.stdout)
        self.assertIn("1h56m", r2.stdout)


class ServerDiscoveryTests(unittest.TestCase):
    def test_ps_parse(self):
        sample = ("root 1 /sbin/init\n"
                  "user 6321 /home/user/.opencode/bin/opencode "
                  "--print-logs --log-level WARN serve --hostname 0.0.0.0 "
                  "--port 51950\n"
                  "builder 6591 grep -i opencode\n")
        import subprocess
        real_run = subprocess.run

        class FakeDone:
            stdout = sample

        def fake_run(*a, **k):
            return FakeDone()

        subprocess.run = fake_run
        try:
            self.assertEqual(sr._ps_opencode_ports(), ["51950"])
        finally:
            subprocess.run = real_run

    def test_ps_parse_none(self):
        import subprocess
        real_run = subprocess.run

        class FakeDone:
            stdout = "root 1 /sbin/init\nbuilder 9 grep foo\n"

        def fake_run(*a, **k):
            return FakeDone()

        subprocess.run = fake_run
        try:
            self.assertEqual(sr._ps_opencode_ports(), [])
        finally:
            subprocess.run = real_run

    def test_env_wins_over_ps(self):
        os.environ["OPENCODE_SERVER_PORT"] = "1234"
        try:
            self.assertEqual(sr.server_port(ttl=0), "1234")
        finally:
            del os.environ["OPENCODE_SERVER_PORT"]

    def test_default_without_env_or_ps(self):
        import subprocess
        real_run = subprocess.run
        saved = os.environ.pop("OPENCODE_SERVER_PORT", None)

        def boom(*a, **k):
            raise OSError("no ps")

        subprocess.run = boom
        try:
            sr._server_cache.update(at=0.0, port="")
            self.assertEqual(sr.server_port(ttl=0), "4096")
        finally:
            subprocess.run = real_run
            if saved is not None:
                os.environ["OPENCODE_SERVER_PORT"] = saved


class WatchdogEnsureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tw", os.path.join(BASE, "task-watchdog.py"))
        cls.tw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tw)

    def test_parse_serve_processes(self):
        tw = self.__class__.tw
        text = ("  PID ARGS\n"
                "    1 /sbin/init\n"
                " 6321 /home/user/.opencode/bin/opencode --print-logs "
                "serve --hostname 0.0.0.0 --port 51950\n"
                " 6591 grep -i opencode\n")
        self.assertEqual(tw.sr._parse_serve_processes(text),
                         [(6321, "51950")])
        self.assertEqual(tw.sr._parse_serve_processes("  1 /sbin/init\n"), [])

    def test_read_proc_environ(self):
        import subprocess
        tw = self.__class__.tw
        # Child inherits the marker in its INITIAL env (like a server
        # process); /proc reflects initial env, not runtime setenv.
        env = dict(os.environ, WD_TEST_MARKER_XYZ="hello42")
        p = subprocess.Popen(["sleep", "30"], env=env)
        import time as _wt
        _wt.sleep(0.3)  # let fork/exec settle before reading /proc
        try:
            got = tw.sr._read_proc_environ(p.pid)
            self.assertEqual(got.get("WD_TEST_MARKER_XYZ"), "hello42")
        finally:
            p.kill()
            p.wait()
        self.assertEqual(tw.sr._read_proc_environ(999999999), {})

    def _write_journal(self, tw, tmp, events):
        import time as _t
        import datetime as _dt
        now = _t.time()
        with open(tmp, "w") as f:
            for i, ev in enumerate(events):
                ts = _dt.datetime.fromtimestamp(
                    now - ev[1], tz=_dt.timezone.utc).isoformat(
                        timespec="seconds")
                f.write('{"ts": "%s", "event": "%s"}\n' % (ts, ev[0]))

    def test_daemon_healthy_live(self):
        import tempfile
        tw = self.__class__.tw
        real_log, real_lock = tw.JOURNAL, tw.lock_held_by_live_process
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            tmp = f.name
        try:
            tw.JOURNAL = tmp
            tw.lock_held_by_live_process = lambda: True
            # Fresh heartbeat + recent WATCH = healthy.
            self._write_journal(tw, tmp, [("WATCH", 30), ("HEARTBEAT", 5)])
            self.assertTrue(tw.daemon_healthy(90))
        finally:
            tw.JOURNAL = real_log
            tw.lock_held_by_live_process = real_lock
            os.remove(tmp)

    def test_daemon_healthy_api_down_streak(self):
        import tempfile
        tw = self.__class__.tw
        real_log, real_lock = tw.JOURNAL, tw.lock_held_by_live_process
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            tmp = f.name
        try:
            tw.JOURNAL = tmp
            tw.lock_held_by_live_process = lambda: True
            # Fresh heartbeats but only API_DOWN lately = deaf, not alive.
            self._write_journal(tw, tmp, [("WATCH", 300), ("API_DOWN", 60),
                                          ("API_DOWN", 30), ("HEARTBEAT", 5)])
            self.assertFalse(tw.daemon_healthy(90))
        finally:
            tw.JOURNAL = real_log
            tw.lock_held_by_live_process = real_lock
            os.remove(tmp)

    def test_daemon_healthy_fresh_start(self):
        import tempfile
        tw = self.__class__.tw
        real_log, real_lock = tw.JOURNAL, tw.lock_held_by_live_process
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            tmp = f.name
        try:
            tw.JOURNAL = tmp
            tw.lock_held_by_live_process = lambda: True
            self._write_journal(tw, tmp, [("START", 10), ("HEARTBEAT", 5)])
            self.assertTrue(tw.daemon_healthy(90))
        finally:
            tw.JOURNAL = real_log
            tw.lock_held_by_live_process = real_lock
            os.remove(tmp)

    def test_terminate_lock_holder(self):
        import subprocess
        import tempfile
        tw = self.__class__.tw
        real_lock = tw.LOCKFILE
        with tempfile.NamedTemporaryFile("w+", suffix=".lock",
                                         delete=False) as f:
            tmp = f.name
        try:
            tw.LOCKFILE = tmp
            p = subprocess.Popen(["sleep", "30"])
            import time as _wt
            _wt.sleep(0.2)
            with open(tmp, "w") as f:
                json.dump({"pid": p.pid}, f)
            self.assertTrue(tw.terminate_lock_holder())
            p.wait(timeout=10)
            self.assertIsNotNone(p.returncode)
            # No lock / foreign pid / self pid -> False, no signal.
            with open(tmp, "w") as f:
                json.dump({"pid": 999999999}, f)
            self.assertFalse(tw.terminate_lock_holder())
        finally:
            tw.LOCKFILE = real_lock
            try:
                p.kill()
            except Exception:
                pass
            os.remove(tmp)

    def test_heartbeat_fresh_and_stale(self):
        import tempfile
        tw = self.__class__.tw
        real_log = tw.JOURNAL
        with tempfile.NamedTemporaryFile("w+", suffix=".log",
                                         delete=False) as f:
            tmp = f.name
        try:
            tw.JOURNAL = tmp
            self.assertFalse(tw.heartbeat_fresh(90))
            now = __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(
                    timespec="seconds")
            with open(tmp, "w") as f:
                f.write('{"ts": "%s", "event": "HEARTBEAT"}\n' % now)
            self.assertTrue(tw.heartbeat_fresh(90))
            self.assertFalse(tw.heartbeat_fresh(-1))
        finally:
            tw.JOURNAL = real_log
            os.remove(tmp)

    def _tmp_journal(self, tw, events):
        # Hermetic journal: NEVER let ensure/daemon_healthy touch the real
        # watchdog.log (a stale-path bug here once SIGTERMd the live daemon
        # mid-suite and os._exit(0)'d the whole run).
        import tempfile
        import time as _t
        import datetime as _dt
        with tempfile.NamedTemporaryFile("w+", suffix=".log",
                                         delete=False) as f:
            tmp = f.name
        now = _t.time()
        with open(tmp, "w") as f:
            for ev, age in events:
                ts = _dt.datetime.fromtimestamp(
                    now - age, tz=_dt.timezone.utc).isoformat(
                        timespec="seconds")
                f.write('{"ts": "%s", "event": "%s"}\n' % (ts, ev))
        return tmp

    def test_ensure_alive_path_does_not_spawn(self):
        tw = self.__class__.tw
        real_log, real_lock = tw.JOURNAL, tw.lock_held_by_live_process
        tmp = self._tmp_journal(tw, [("WATCH", 30), ("HEARTBEAT", 5)])
        tw.JOURNAL = tmp
        tw.lock_held_by_live_process = lambda: True
        try:
            self.assertEqual(tw.cmd_ensure([], []), 0)
        finally:
            tw.JOURNAL = real_log
            tw.lock_held_by_live_process = real_lock
            os.remove(tmp)

    def test_ensure_stale_path_spawns_daemon(self):
        import tempfile
        tw = self.__class__.tw
        real_log = tw.JOURNAL
        tmp_log = self._tmp_journal(tw, [("WATCH", 300), ("API_DOWN", 60),
                                          ("API_DOWN", 30), ("HEARTBEAT", 5)])
        tw.JOURNAL = tmp_log
        real_lockfile = tw.LOCKFILE
        with tempfile.NamedTemporaryFile("w+", suffix=".lock",
                                         delete=False) as f:
            tmp_lock = f.name
        tw.LOCKFILE = tmp_lock
        real_daemonize, real_execv = tw.daemonize, os.execv
        real_hb, real_lockfn = tw.heartbeat_fresh, tw.lock_held_by_live_process
        calls = {}
        tw.heartbeat_fresh = lambda max_age: False
        tw.lock_held_by_live_process = lambda: False
        def fake_daemonize():
            calls["daemonized"] = True

        def fake_execv(*a):
            calls["exec"] = a
            raise SystemExit(99)

        tw.daemonize = fake_daemonize
        os.execv = fake_execv
        try:  # NOTE: heartbeat/lock left REAL here on purpose would be
            # lethal (SIGTERM to the live daemon + os._exit); journal and
            # lockfile above are tmp, and the fake journal forces the
            # stale path deterministically.
            with self.assertRaises(SystemExit) as cm:
                tw.cmd_ensure([], ["--threshold", "600"])
            self.assertEqual(cm.exception.code, 99)
            self.assertTrue(calls.get("daemonized"))
            argv = calls["exec"][1]
            self.assertIn("--daemon", argv)
            self.assertIn("--all", argv)
        finally:
            tw.daemonize = real_daemonize
            os.execv = real_execv
            tw.heartbeat_fresh, tw.lock_held_by_live_process = real_hb, real_lockfn
            tw.LOCKFILE = real_lockfile
            tw.JOURNAL = real_log
            try:
                os.remove(tmp_lock)
            except OSError:
                pass
            try:
                os.remove(tmp_log)
            except OSError:
                pass


class HealthStoreConsistencyTests(ScriptCase):
    """A1 (E3/E4 split-brain): ONE health store for every writer and
    reader. Writers may use any spelling (bare or full model id); readers
    (preflight/migrate/models) resolve symmetrically and never return a
    cooldown model without an explicit --force."""

    def test_mark_dead_bare_spelling_blocks_pin(self):
        # The E3 incident shape: classify-error --record-model used the
        # BARE id while preflight resolves the FULL pin.
        primary = sr.worker_pins()[0]
        fallbacks = [(r, m) for r, m in sr.worker_pins() if r != "build"]
        fb_role, fb_model = fallbacks[0]
        bare = fb_model.split("/")[-1]
        r = self.run_script("classify-error", "rate limited, retry later",
                            "--record-model", bare)
        self.assertEqual(r.returncode, 11, r.stdout + r.stderr)
        self.assertGreater(sr.cooldown_remaining(fb_model), 0,
                           "bare-id record must block the full pin")
        # Primary also dead -> preflight must NOT return the fallback.
        self.run_script("mark-dead", primary[1], "--reason", "test")
        r = self.run_script("preflight")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(f"PREFLIGHT_OK subagent_type={fb_role}", r.stdout)
        chosen = [l for l in r.stdout.splitlines()
                  if l.startswith("PREFLIGHT_OK")]
        self.assertTrue(chosen)
        # Defensive: the model actually recommended is cooldown-free.
        m = chosen[0].split("model=")[1]
        self.assertEqual(sr.cooldown_remaining(m), 0)

    def test_migrate_skips_cooldown_model_and_force_overrides(self):
        # E4 shape: migrate must not select a model whose cooldown was
        # recorded under a different spelling; --force is the human escape.
        primary_model = sr.worker_pins()[0][1]
        fb1_role = sr.resolve_next_worker([primary_model])[0]  # chain rank
        fb1_model = dict((r, m) for r, m in sr.worker_pins())[fb1_role]
        self.assertTrue(fb1_role)
        self.register_live(agent="build", model=primary_model)
        self.run_script("mark-dead", primary_model, "--reason", "dead")
        self.run_script("mark-dead", fb1_model.split("/")[-1],
                        "--reason", "bare-spelling death")
        r = self.run_script("migrate", "ses_LIVE", "--objective",
                            "Test Objective", "--delay", "7000")
        self.assertIn("task_id=ses_LIVE", r.stdout, r.stdout + r.stderr)
        self.assertNotIn(f"subagent_type={fb1_role}", r.stdout)
        chosen = [l for l in r.stdout.splitlines()
                  if l.startswith("subagent_type=")][0].split("=")[1]
        # --force explicitly overrides cooldowns (owner directive only):
        # with the new backend now excluded as old_model, the ranking puts
        # the (cooling) PRIMARY first — force hands it out anyway.
        r2 = self.run_script("migrate", "ses_LIVE", "--objective",
                             "Test Objective", "--delay", "7000",
                             "--force")
        self.assertIn("task_id=ses_LIVE", r2.stdout, r2.stdout + r2.stderr)
        self.assertIn("subagent_type=build", r2.stdout)
        self.assertNotIn("subagent_type=" + chosen, r2.stdout)

    def test_reset_timestamp_becomes_cooldown(self):
        # E2: "Usage limit reached for 5 hour ... reset <ts>" — the exact
        # revival time (+20 min margin) becomes the cooldown, not 3h.
        import datetime as _dt
        primary_model = sr.worker_pins()[0][1]
        reset = (_dt.datetime.now(_dt.timezone.utc) +
                 _dt.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        r = self.run_script(
            "classify-error",
            f"Usage limit reached for 5 hour window, reset {reset} UTC",
            "--record-model", primary_model)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        rem = sr.cooldown_remaining(primary_model)
        self.assertGreater(rem, 3 * 3600)          # not the flat 3h default
        self.assertLess(rem, 3 * 3600 + 25 * 60)   # reset + 20m margin

    def test_cooldown_never_shrinks(self):
        # A re-migrate with a shorter delay must not cut a longer
        # provider cooldown (record_dead keep_longer).
        m = sr.worker_pins()[0][1]
        self.run_script("mark-dead", m, "--in", "7200", "--reason", "long")
        self.run_script("mark-dead", m, "--in", "300", "--reason", "short")
        self.assertGreater(sr.cooldown_remaining(m), 7000)


class ConfigDriftTests(ScriptCase):
    """A2 (E6 tug-of-war): models/preflight compare the live worker config
    with HEAD and print a loud banner when they diverge."""

    def setUp(self):
        super().setUp()
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="sr-drift-")
        self.run_cmd(["git", "init", "-q"], {})
        self.run_cmd(["git", "config", "user.email", "t@t"], {})
        self.run_cmd(["git", "config", "user.name", "t"], {})
        for name in (".opencode/model-fallback.json", "opencode.jsonc"):
            path = os.path.join(self.tmp, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write('{}\n')
        self.run_cmd(["git", "add", "-A"], {})
        self.run_cmd(["git", "commit", "-qm", "init"], {})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def run_cmd(self, cmd, _extra):
        import subprocess
        return subprocess.run(cmd, cwd=self.tmp, capture_output=True)

    def test_no_drift_when_clean(self):
        self.assertEqual(sr.config_drift(repo=self.tmp), [])

    def test_modified_drift_detected(self):
        with open(os.path.join(self.tmp, ".opencode/model-fallback.json"),
                  "a") as f:
            f.write('\n{"silently": "rewritten"}\n')
        d = sr.config_drift(repo=self.tmp)
        self.assertIn((".opencode/model-fallback.json", "modified"), d)
        self.assertIn("CONFIG-DRIFT", _banner_for(self.tmp))

    def test_untracked_drift_detected(self):
        with open(os.path.join(self.tmp, "x-new.json"), "w") as f:
            f.write("{}")
        self.assertIn(("x-new.json", "untracked"),
                      sr.config_drift(repo=self.tmp, files=["x-new.json"]))

    def test_preflight_prints_banner_only_on_drift(self):
        import subprocess
        base_env = dict(os.environ)
        base_env.update({"OPENCODE_SERVER_HOST": "127.0.0.1",
                         "OPENCODE_SERVER_PORT": str(self.port),
                         "OPENCODE_SERVER_USERNAME": "u",
                         "OPENCODE_SERVER_PASSWORD": "p"})
        clean = dict(base_env, SR_DRIFT_REPO=self.tmp)
        r = subprocess.run([sys.executable, SCRIPT, "preflight"],
                           capture_output=True, text=True, env=clean)
        self.assertNotIn("CONFIG-DRIFT", r.stdout)
        with open(os.path.join(self.tmp, "opencode.jsonc"), "a") as f:
            f.write('\n{"pin": "changed"}\n')
        dirty = dict(base_env, SR_DRIFT_REPO=self.tmp)
        r2 = subprocess.run([sys.executable, SCRIPT, "preflight"],
                            capture_output=True, text=True, env=dirty)
        self.assertIn("CONFIG-DRIFT", r2.stdout)
        self.assertIn("opencode.jsonc", r2.stdout)


def _banner_for(repo):
    saved = os.environ.get("SR_DRIFT_REPO")
    os.environ["SR_DRIFT_REPO"] = repo
    try:
        return sr.drift_banner()
    finally:
        if saved is None:
            os.environ.pop("SR_DRIFT_REPO", None)
        else:
            os.environ["SR_DRIFT_REPO"] = saved


class OrphanGcTests(ScriptCase):
    """B1 (E1): verified-only orphan GC; registry-only rows are ORPHAN
    noise, not STUCK signal."""

    def _write_reg(self, sessions):
        with open(REG, "w") as f:
            json.dump({"$schema": "session-registry v1",
                       "sessions": sessions}, f)

    @staticmethod
    def _meta(age_sec, model="opencode/longcat-2.5-preview-free"):
        from datetime import datetime, timezone, timedelta
        return {"agent": "build", "objective": "o", "task": "t",
                "model": model, "oid": "", "state": "reusable",
                "lastUsed": (datetime.now(timezone.utc) -
                             timedelta(seconds=age_sec)).isoformat(
                                 timespec="seconds")}

    def test_gc_retires_verified_gone_only(self):
        # 'ses_LIVE' EXISTS on the mock server; the others do not.
        self._write_reg({
            "ses_GONE_OLD": self._meta(2 * 24 * 3600),   # absent + old
            "ses_LIVE": self._meta(2 * 24 * 3600),       # exists on server
            "ses_GONE_FRESH": self._meta(3600),          # absent but fresh
        })
        r = self.run_script("stuck", "--gc", "--threshold", "600")
        # Exit may be 2: the mock server always carries genuinely stuck
        # sessions (ses_BUSY retry 7000s) — not this test's concern.
        self.assertIn(r.returncode, (0, 2), r.stdout + r.stderr)
        with open(REG) as f:
            reg = json.load(f)["sessions"]
        self.assertEqual(reg["ses_GONE_OLD"]["state"], "retired")
        self.assertIn("gcReason", reg["ses_GONE_OLD"])
        self.assertEqual(reg["ses_LIVE"]["state"], "reusable")
        self.assertEqual(reg["ses_GONE_FRESH"]["state"], "reusable")

    def test_orphan_rows_are_not_stuck(self):
        # The E1 noise: 150 registry-only rows used to be verdict=STUCK and
        # drove exit 2. Status absence = idle: ORPHAN, and THIS row never
        # makes the run exit 2 (mock's own stuck sessions may).
        self._write_reg({"ses_GONE_OLD": self._meta(50 * 3600)})
        r = self.run_script("stuck", "--threshold", "600")
        self.assertIn(r.returncode, (0, 2), r.stdout + r.stderr)
        self.assertIn("ORPHAN ses_GONE_OLD", r.stdout)
        self.assertNotIn("STUCK ses_GONE_OLD", r.stdout)

    def test_gc_never_retires_when_api_blind(self):
        self._write_reg({"ses_GONE_OLD": self._meta(2 * 24 * 3600)})
        r = self.run_script("stuck", "--gc", "--threshold", "600",
                            port=self.port + 1)  # nothing listens there
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        with open(REG) as f:
            reg = json.load(f)["sessions"]
        self.assertEqual(reg["ses_GONE_OLD"]["state"], "reusable")


class PoolTests(ScriptCase):
    """B3 (E10): account pools — a quota death blocks failover INSIDE the
    pool; provider timeouts stay per-model."""

    FLASH = "zai-coding-plan/glm-5.3-flash"
    GLM = "zai-coding-plan/glm-5.3"

    def test_chain_declares_glm_pool(self):
        self.assertEqual(sr.pool_of(self.FLASH), "zai-coding-plan")
        self.assertEqual(sr.pool_of(self.GLM), "zai-coding-plan")

    def test_quota_death_is_pool_wide(self):
        r = self.run_script("classify-error",
                            "usage limit exceeded, billing required",
                            "--record-model", self.FLASH)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertGreater(sr.cooldown_remaining(self.GLM), 0,
                           "sibling pool member must be blocked")
        self.assertGreater(sr.pool_wide_remaining("zai-coding-plan"), 0)
        # mark-alive --pool clears the whole pool (owner word > memory).
        r2 = self.run_script("mark-alive", "--pool", "zai-coding-plan")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(sr.cooldown_remaining(self.GLM), 0)
        self.assertEqual(sr.cooldown_remaining(self.FLASH), 0)

    def test_timeout_death_is_not_pool_wide(self):
        self.run_script("mark-dead", self.FLASH, "--in", "7200",
                        "--reason", "provider timeout")
        self.assertGreater(sr.cooldown_remaining(self.FLASH), 0)
        self.assertEqual(sr.cooldown_remaining(self.GLM), 0,
                         "per-model timeout must not block the sibling")

    def test_preflight_avoids_dead_pool(self):
        self.run_script("mark-dead", self.FLASH, "--in", "7200",
                        "--reason", "quota", "--pool-wide")
        r = self.run_script("preflight")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRIMARY_COOLDOWN", r.stdout)
        self.assertNotIn("zai-coding-plan", r.stdout.split("PREFLIGHT_OK")[1])


class ChaosFailoverTests(ScriptCase):
    """B4: end-to-end failover chain against the mock server — detection,
    cooldown, migration skipping cooldown models, all without real
    network."""

    def reg_busy(self):
        r = self.run_script("register", "ses_BUSY", "--agent", "build",
                            "--objective", "Busy Objective", "--task",
                            "do Y", "--model", sr.worker_pins()[0][1],
                            "--oid", "busy-o")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_retry_stuck_to_migration_skipping_cooldowns(self):
        # 1. Detection: watchdog aborts the provider-retry session and
        #    records the observed delay as cooldown.
        self.reg_busy()
        r = self.run_watchdog("--once", "--session", "ses_BUSY",
                              "--threshold", "600")
        self.assertIn("aborted ses_BUSY", r.stdout, r.stdout + r.stderr)
        primary_model = sr.worker_pins()[0][1]
        self.assertGreater(sr.cooldown_remaining(primary_model), 6000)
        # 2. Migration: same task_id on the next healthy worker.
        r = self.run_script("migrate", "ses_BUSY", "--objective",
                            "Busy Objective")
        self.assertIn("task_id=ses_BUSY", r.stdout, r.stdout + r.stderr)
        first_role = [l for l in r.stdout.splitlines()
                      if l.startswith("subagent_type=")][0].split("=")[1]
        self.assertNotEqual(first_role, "build")
        # 3. Chaos: the fallback also dies (recorded under a BARE spelling —
        #    the E4 shape); the next migrate must skip it too.
        fb_model = dict((r_, m) for r_, m in sr.worker_pins())[first_role]
        self.run_script("mark-dead", fb_model.split("/")[-1],
                        "--in", "7200", "--reason", "chaos kill")
        r2 = self.run_script("migrate", "ses_BUSY", "--objective",
                             "Busy Objective")
        self.assertIn("task_id=ses_BUSY", r2.stdout, r2.stdout + r2.stderr)
        second_role = [l for l in r2.stdout.splitlines()
                       if l.startswith("subagent_type=")][0].split("=")[1]
        self.assertNotEqual(second_role, first_role)
        self.assertNotEqual(second_role, "build")
        # 4. Preflight stays consistent with the two deaths.
        r3 = self.run_script("preflight")
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertNotIn(f"subagent_type={first_role}", r3.stdout)

    def test_dashboard_smoke(self):
        self.reg_busy()
        r = self.run_script("dashboard")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("next-worker:", r.stdout)
        self.assertIn("model-health:", r.stdout)


class WatchdogLoudnessTests(unittest.TestCase):
    """B2 (E9): --ensure is ALWAYS loud; --status reports pid/heartbeat/
    aborts; supervision of the supervisor exists."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tw_loud", os.path.join(BASE, "task-watchdog.py"))
        cls.tw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tw)

    def test_status_not_running(self):
        import tempfile
        tw = self.__class__.tw
        real_j, real_l = tw.JOURNAL, tw.LOCKFILE
        tw.JOURNAL = os.path.join(tempfile.mkdtemp(), "nope.log")
        tw.LOCKFILE = os.path.join(tempfile.mkdtemp(), "nope.lock")
        try:
            with open(os.devnull, "w") as devnull, \
                    _redirect_stdout(devnull):
                code = tw.cmd_status()
            self.assertEqual(code, 1)
        finally:
            tw.JOURNAL, tw.LOCKFILE = real_j, real_l

    def test_status_stale(self):
        import tempfile
        tw = self.__class__.tw
        tmp = tempfile.mkdtemp()
        real_j, real_l = tw.JOURNAL, tw.LOCKFILE
        tw.JOURNAL = os.path.join(tmp, "wd.log")
        tw.LOCKFILE = os.path.join(tmp, "wd.lock")
        real_hb = tw.daemon_healthy
        try:
            with open(tw.JOURNAL, "a") as f:
                f.write('{"ts": "%s", "event": "HEARTBEAT"}\n'
                        % (_dt_now_minus(3600)))
            with open(tw.LOCKFILE, "w") as f:
                json.dump({"pid": 999999999,
                           "at": _dt_now_minus(3600).isoformat()}, f)
            tw.daemon_healthy = lambda m=90: False
            with open(os.devnull, "w") as devnull, \
                    _redirect_stdout(devnull):
                code = tw.cmd_status()
            self.assertEqual(code, 2)
        finally:
            tw.daemon_healthy = real_hb
            tw.JOURNAL, tw.LOCKFILE = real_j, real_l

    def test_ensure_started_path_is_loud(self):
        import tempfile
        import io
        tw = self.__class__.tw
        tmp = tempfile.mkdtemp()
        real_j, real_l = tw.JOURNAL, tw.LOCKFILE
        tw.JOURNAL = os.path.join(tmp, "wd.log")
        tw.LOCKFILE = os.path.join(tmp, "wd.lock")
        real_daemonize, real_execv = tw.daemonize, os.execv
        real_hb, real_lockfn = tw.heartbeat_fresh, tw.lock_held_by_live_process
        real_gc = tw.sr.gc_orphans
        calls = {}
        tw.sr.gc_orphans = lambda *a, **k: ([], 0)
        tw.heartbeat_fresh = lambda max_age: False
        tw.lock_held_by_live_process = lambda: False
        tw.daemonize = lambda: calls.__setitem__("daemonized", True)

        def fake_execv(*a):
            calls["exec"] = a
            raise SystemExit(99)
        os.execv = fake_execv
        try:
            buf = io.StringIO()
            with _redirect_stdout(buf):
                with self.assertRaises(SystemExit) as cm:
                    tw.cmd_ensure([], ["--threshold", "600"])
            self.assertEqual(cm.exception.code, 99)
            self.assertIn("watchdog STARTED", buf.getvalue())
            self.assertTrue(calls.get("daemonized"))
        finally:
            tw.sr.gc_orphans = real_gc
            tw.daemonize, os.execv = real_daemonize, real_execv
            tw.heartbeat_fresh, tw.lock_held_by_live_process = real_hb, real_lockfn
            tw.JOURNAL, tw.LOCKFILE = real_j, real_l


def _dt_now_minus(sec):
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).replace(
        microsecond=0) - _dt.timedelta(seconds=sec)


try:
    from contextlib import redirect_stdout as _redirect_stdout
except ImportError:  # pragma: no cover
    import contextlib
    _redirect_stdout = contextlib.redirect_stdout


class ProtocolVersionConsistency(unittest.TestCase):
    """Issue #84: docs must require the SAME orchestrator-protocol version
    that session-reuse.py implements (sr.ORCHESTRATOR_PROTOCOL). Stale
    numbers (e.g. 'need v16', 'orchestrator-protocol: 15') caused wrong
    STALE-AGENT decisions. (Restored 2026-10-06 after being silently
    deleted from the worktree while the numbers were in flux.)"""

    AGENTS_MD = os.path.join(BASE, "..", "AGENTS.md")
    ORCH_MD = os.path.join(BASE, "..", ".opencode", "agents", "orchestrator.md")

    def _refs(self, path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        pairs = re.findall(r"orchestrator-protocol: (\d+)|need v(\d+)", text)
        return [int(a or b) for a, b in pairs]

    def test_version_constant_is_int(self):
        self.assertIsInstance(sr.ORCHESTRATOR_PROTOCOL, int)

    def test_orchestrator_md_requires_current_version(self):
        refs = self._refs(self.ORCH_MD)
        self.assertTrue(refs, "orchestrator.md must state 'orchestrator-protocol: N'")
        for n in refs:
            self.assertEqual(n, sr.ORCHESTRATOR_PROTOCOL,
                             f"orchestrator.md requires v{n}, script implements v{sr.ORCHESTRATOR_PROTOCOL}")

    def test_agents_md_requires_current_version(self):
        refs = self._refs(self.AGENTS_MD)
        self.assertTrue(refs, "AGENTS.md must reference the orchestrator protocol version")
        for n in refs:
            self.assertEqual(n, sr.ORCHESTRATOR_PROTOCOL,
                             f"AGENTS.md requires v{n}, script implements v{sr.ORCHESTRATOR_PROTOCOL}")

    def test_version_subcommand_prints_current(self):
        out = subprocess.run([sys.executable, SCRIPT, "version"],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn(f"orchestrator-protocol: {sr.ORCHESTRATOR_PROTOCOL}", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
