#!/usr/bin/env python3
"""Tests for the mavericks-lab-agent protocol layer (NDJSON framing, dispatch, idempotency)."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
AGENT_PATH = REPO / "lab/agent/mavericks-lab-agent"

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print(f"ok - {name}")


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print(f"FAIL - {name} {detail}")


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_agent(data_dir):
    os.environ["MV_LAB_DATA"] = str(data_dir)
    loader = importlib.machinery.SourceFileLoader("lab_agent", str(AGENT_PATH))
    spec = importlib.util.spec_from_loader("lab_agent", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def call_agent(mod, cmd, args=None, job_id=None):
    """Simulate a serve-mode round-trip by calling the handler directly."""
    req = {"id": job_id or str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
    cached = mod.journal_find_job(req["id"])
    if cached:
        return {"id": req["id"], "ok": True, "result": cached["data"].get("result"), "replayed": True}
    handler = mod.COMMANDS.get(cmd)
    if not handler:
        return {"id": req["id"], "ok": False, "error": f"unknown command: {cmd}"}
    try:
        result = handler(args or {})
        if "error" in result:
            resp = {"id": req["id"], "ok": False, "error": result["error"]}
        else:
            resp = {"id": req["id"], "ok": True, "result": result}
    except Exception as e:
        resp = {"id": req["id"], "ok": False, "error": f"{type(e).__name__}: {e}"}
    mod.journal_append(
        "job_result",
        {"job_id": req["id"], "cmd": cmd, "result": result if "error" not in result else None, "error": resp.get("error")},
    )
    return resp


def main():
    tmp = tempfile.mkdtemp(prefix="lab-test-protocol-")
    mod = load_agent(tmp)

    # ping
    resp = call_agent(mod, "ping")
    check("ping ok", resp.get("ok") is True)
    check("ping pong", resp.get("result", {}).get("pong") is True)

    # status (initial)
    resp = call_agent(mod, "status")
    check("status ok", resp.get("ok") is True)
    check("initial state UNKNOWN", resp["result"]["state"] == "UNKNOWN")

    # unknown command
    resp = call_agent(mod, "no-such-cmd")
    check("unknown command rejected", resp.get("ok") is False)
    check("unknown command error", "unknown command" in resp.get("error", ""))

    # idempotent replay
    job_id = str(uuid.uuid4())
    resp1 = call_agent(mod, "ping", job_id=job_id)
    resp2 = call_agent(mod, "ping", job_id=job_id)
    check("idempotent replay", resp2.get("replayed") is True)
    check("idempotent same result", resp1.get("result") == resp2.get("result"))

    # journal has entries
    entries = mod.journal_read()
    check("journal populated", len(entries) > 0)
    check("journal has job_result", any(e["type"] == "job_result" for e in entries))

    # trace command
    resp = call_agent(mod, "trace", {"lines": 5})
    check("trace ok", resp.get("ok") is True)
    check("trace entries", len(resp["result"]["entries"]) > 0)

    # logs command
    resp = call_agent(mod, "logs", {"lines": 5})
    check("logs ok", resp.get("ok") is True)

    # run-test echo
    resp = call_agent(mod, "run-test", {"name": "echo", "args": {"text": "hello"}})
    check("run-test echo ok", resp.get("ok") is True)
    check("run-test echo result", resp["result"]["result"] == "pass")
    check("run-test echo metrics", resp["result"]["metrics"]["echo"] == "hello")

    # run-test unknown
    resp = call_agent(mod, "run-test", {"name": "no-such-test"})
    check("run-test unknown fails", resp["result"]["result"] == "fail")

    # benchmark
    resp = call_agent(mod, "benchmark", {"name": "disk-write"})
    check("benchmark ok", resp.get("ok") is True)
    check("benchmark result", resp["result"]["result"] == "pass")

    # inventory
    resp = call_agent(mod, "inventory")
    check("inventory ok", resp.get("ok") is True)
    check("inventory has cpu", "cpu" in resp["result"])

    # collect
    resp = call_agent(mod, "collect", {"lines": 10})
    check("collect ok", resp.get("ok") is True)
    check("collect has dmesg", "dmesg" in resp["result"])

    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
