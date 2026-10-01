#!/usr/bin/env python3
"""Tests for orchestration scripts: SESSION != MODEL (protocol v7).

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
import re
import subprocess
import sys
import threading
import time as _time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE, "session-reuse.py")
REG = os.path.join(BASE, "..", ".opencode", "sessions", "registry.json")
HEALTH = os.path.join(BASE, "..", ".opencode", "sessions", "model-health.json")
LIMITS = os.path.join(BASE, "..", ".opencode", "sessions", "model-limits.json")
WDLOG = os.path.join(BASE, "..", ".opencode", "sessions", "watchdog.log")
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
    }
    SESSIONS = {"ses_LIVE", "ses_BUSY", "ses_QUIET", "ses_MSGBROKEN",
                "ses_WORKING", "ses_SOON", "ses_NEXT", "ses_ORPHAN",
                "ses_WAITWORD", "ses_STRANGER", "ses_ESC"}
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

    def setUp(self):
        self.saved = {}
        for p in (REG, HEALTH, LIMITS, WDLOG):
            try:
                with open(p, "rb") as f:
                    self.saved[p] = f.read()
            except OSError:
                self.saved[p] = None
        MockHandler.ABORTS = []

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
        self.run_script("mark-dead", "opencode/nemotron-3-ultra-free",
                        "--reason", "test")
        r = self.run_script("preflight")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRIMARY_COOLDOWN build", r.stdout)
        self.assertIn("PREFLIGHT_OK subagent_type=build-b", r.stdout)

    def test_preflight_all_cooling_waits(self):
        for m in ("opencode/nemotron-3-ultra-free",
                  "openrouter/cohere/north-mini-code:free",
                  "opencode/longcat-2.5-preview-free"):
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
        r = self.run_script("register", "ses_BUSY", "--agent", "build",
                            "--objective", "Busy Objective", "--task", "do Y",
                            "--model", "opencode/nemotron-3-ultra-free",
                            "--oid", "busy-o")
        self.assertEqual(r.returncode, 0, r.stderr)

    def journal_lines(self):
        try:
            with open(WDLOG) as f:
                return [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []

    def test_abort_dead_retry_over_threshold(self):
        self.reg_busy()
        r = self.run_watchdog("--once", "--session", "ses_BUSY",
                              "--threshold", "600")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("aborted ses_BUSY", r.stdout)
        self.assertIn("ses_BUSY", MockHandler.ABORTS)
        # Cooldown recorded with observed delay (~7000s).
        r2 = self.run_script("health")
        self.assertIn("nemotron-3-ultra-free", r2.stdout)
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
        self.reg_busy()
        self.run_watchdog("--once", "--session", "ses_BUSY",
                          "--threshold", "600")
        r = self.run_script("migrate", "ses_BUSY", "--objective",
                            "Busy Objective")
        self.assertIn("task_id=ses_BUSY", r.stdout, r.stdout + r.stderr)
        self.assertIn("subagent_type=build-b", r.stdout)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
