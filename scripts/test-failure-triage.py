#!/usr/bin/env python3
"""Tests for scripts/failure-triage.py (owner rule 2026-10-08).

A model is unavailable ONLY when the error text states it (reset timestamp,
stated pause, end of day, free usage exceeded, quota/billing). Everything else
is transient: resume the same session on the same worker, no cooldown.

Usage: python3 scripts/test-failure-triage.py   (exit 0 = all passed)"""
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = tempfile.mkdtemp(prefix="triage-test-")
# Must be set BEFORE importing session-reuse: its health-store path is bound at import.
os.environ["SR_STATE_DIR"] = STATE


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sr = load("session_reuse_t", "session-reuse.py")
ft = load("failure_triage_t", "failure-triage.py")
NOW = time.mktime(time.strptime("2026-10-08 12:00:00", "%Y-%m-%d %H:%M:%S"))
FAILS = []
PASSED = [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print("ok - %s" % name)
    else:
        FAILS.append(name)
        print("FAIL - %s %s" % (name, detail))


def health():
    try:
        with open(sr.HEALTH, encoding="utf-8") as fh:
            return json.load(fh).get("models", {})
    except (OSError, ValueError):
        return {}


def reset():
    for name in ("model-health.json", "transient.json"):
        path = os.path.join(STATE, name)
        if os.path.exists(path):
            os.remove(path)


def run(text, task="ses_t", model="prov/model-x", now=NOW):
    return ft.triage(text, task, model, sr, now=now)


def main():
    transient = [
        "Model is overloaded due to high load, please try again later",
        "high load", "No response from server", "503 Service Unavailable",
        "Provider returned error: capacity exceeded", "Request timed out",
        "ECONNRESET socket hang up", "429 Too Many Requests, retry after 30 seconds",
        "Quota exceeded for metric: requests per minute",
    ]
    for text in transient:
        reset()
        action, _f = run(text)
        check("transient resumes same worker: %s" % text[:50],
              action == "RESUME_SAME" and not health(), "action=%s health=%s" % (action, health()))

    stated = {
        "Free usage exceeded, subscribe to Go": 10800,
        "Rate limit reached, retry in 8800 seconds": 8800,
        "Daily limit reached, try again tomorrow": 3600,
        "Insufficient quota: billing required": 10800,
    }
    for text, minimum in stated.items():
        reset()
        action, f = run(text)
        check("stated unavailability migrates: %s" % text[:50],
              action == "MIGRATE" and f.get("seconds", 0) >= minimum and bool(health()),
              "action=%s f=%s" % (action, f))

    reset()
    action, f = run("Usage limit reached for 5 hour window. Resets 2026-10-08 17:06:36 UTC")
    check("reset timestamp becomes the cooldown (+margin)",
          action == "MIGRATE" and 17000 < f.get("seconds", 0) < 20000, "f=%s" % (f,))

    for text, want in (("context length exceeded: maximum tokens", "FRESH_SESSION"),
                       ("session not found", "FRESH_SESSION"),
                       ("401 Unauthorized: invalid api key", "AUTH"),
                       ("subagent depth limit reached", "AGENT_ERROR")):
        reset()
        action, _f = run(text)
        check("%s -> %s" % (text[:40], want), action == want, "got %s" % action)

    reset()
    seq = []
    for k in range(1, 12):
        action, f = run("No response from server", task="ses_loop", now=NOW + k * 30)
        seq.append(action)
        if action == "MIGRATE":
            break
    entry = health().get("prov/model-x", {})
    check("8 transient failures then a SHORT escalation (not 3h)",
          seq[:8] == ["RESUME_SAME"] * 8 and seq[8] == "MIGRATE"
          and entry.get("cooldownSec") == ft.ESCALATION_COOLDOWN_SEC
          and not entry.get("poolWide"), "seq=%s entry=%s" % (seq, entry))

    reset()
    ok_window = True
    for k in range(10):
        action, f = run("high load", task="ses_slow", now=NOW + k * 1200)
        ok_window = ok_window and action == "RESUME_SAME" and f["attempt"].startswith("1/")
    check("failures 20 minutes apart never accumulate", ok_window)

    reset()
    action, _f = ft.triage("Free usage exceeded", "ses_d", "prov/model-z", sr, now=NOW, dry_run=True)
    check("dry-run records nothing", action == "MIGRATE" and not health())

    print("\n%d passed, %d failed" % (PASSED[0], len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
