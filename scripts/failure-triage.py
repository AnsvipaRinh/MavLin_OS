#!/usr/bin/env python3
"""Deterministic triage of a failed worker Task: resume, migrate, or replace.

Owner rule (2026-10-08): a model counts as unavailable ONLY when the error text
itself says so: a reset timestamp, a stated pause in seconds/minutes/hours,
"until end of day", "free usage exceeded", or quota/billing exhaustion.
Everything else is transient and the right move is to wait a few seconds and
resume the SAME session on the SAME worker: "overloaded", "high load",
"no response from server", 429/5xx without a stated delay, timeouts without a
delay, per-minute quotas, network hiccups, and unknown wording.
Only after MAX_TRANSIENT consecutive transient failures inside WINDOW_SEC does
it escalate, and then with a SHORT cooldown (never the 3 h default).

Why this exists: session-reuse.py classify-error maps "overloaded", "capacity",
503 and similar to MODEL_QUOTA / PROVIDER_ERROR, which record the model dead for
3 hours (and, for MODEL_QUOTA, block its whole account pool). A short load spike
therefore removed workers until the chain was empty.

Usage:
  scripts/failure-triage.py --task-id <id> --model <provider/model> "<error text>"
  (error text may also come from stdin; --dry-run records nothing)
First output token is the action:
  RESUME_SAME wait=<s> attempt=<n>/<max> ...   sleep <wait>, then Task SAME task_id, SAME worker, prompt "resume"
  MIGRATE seconds=<n> ...                       model recorded dead for <n> s; now run session-reuse.py migrate --delay <n>
  FRESH_SESSION ...                             context/session is unusable: replacement session, minimal transfer
  AUTH ...                                      provider not connected: tell the owner
  AGENT_ERROR ...                               platform/config problem: fix config, do not rotate models
"""
import importlib.util
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

MAX_TRANSIENT = 8                 # consecutive transient failures before escalation
WINDOW_SEC = 900                  # failures further apart than this restart the count
ESCALATION_COOLDOWN_SEC = 600     # SHORT cooldown after escalation (not 3 h)
SHORT_WAIT_MAX_SEC = 120          # stated pauses up to this: just wait, same worker
STATED_MARGIN_SEC = 60            # margin added to long stated pauses

PER_MINUTE_PATTERNS = [r"per[ -]?(minute|second)", r"\brpm\b", r"\btpm\b",
                       r"requests? per min"]
DAILY_PATTERNS = [r"end of (the |this )?day", r"until tomorrow",
                  r"try again tomorrow", r"daily (limit|quota|usage)",
                  r"per day", r"(resets?|renews?) (daily|at midnight|tomorrow)",
                  r"no more (requests|usage).{0,20}today"]
LONG_PATTERNS = [r"free usage exceeded", r"free tier.+(exceed|exhaust|deplet)",
                 r"usage.?limit (reached|exceeded)",
                 r"(reached|exceeded).{0,30}usage.?limit",
                 r"quota (exceeded|exhausted|reached)",
                 r"(exceeded|exhausted).{0,20}quota",
                 r"insufficient.{0,20}(quota|credit|balance)",
                 r"payment required", r"\b402\b", r"billing",
                 r"credit.{0,20}(exhausted|expired|depleted)",
                 r"(monthly|weekly) (limit|quota)"]


def load_sr():
    spec = importlib.util.spec_from_file_location(
        "session_reuse", os.path.join(HERE, "session-reuse.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _any(patterns, low):
    return any(re.search(p, low) for p in patterns)


def seconds_to_utc_midnight(now=None):
    now = time.time() if now is None else now
    dt = datetime.fromtimestamp(now, timezone.utc)
    nxt = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp() + 86400
    return nxt - now


def stated_unavailability(text, sr, now=None):
    """(seconds, kind) when the error itself states unavailability, else (None, '')."""
    low = (text or "").lower()
    reset = sr.extract_reset_sec(text, now=now)
    if reset:
        return reset, "reset-timestamp"
    if _any(DAILY_PATTERNS, low):
        return max(3600.0, seconds_to_utc_midnight(now) + 1200), "until-end-of-day"
    if _any(PER_MINUTE_PATTERNS, low):
        return 60.0, "per-minute-quota"
    delay = sr.extract_delay_sec({"error": text})
    if delay:
        return (delay + STATED_MARGIN_SEC if delay > SHORT_WAIT_MAX_SEC else delay), "stated-delay"
    if _any(LONG_PATTERNS, low):
        return float(sr.DEFAULT_COOLDOWN_SEC), "quota-exhausted"
    return None, ""


def _counter_path(sr):
    d = sr._state_dir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "transient.json")


def bump_transient(sr, task_id, now):
    path = _counter_path(sr)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    entry = data.get(task_id) or {}
    n = int(entry.get("n", 0)) if now - float(entry.get("last", 0)) <= WINDOW_SEC else 0
    n += 1
    data = {k: v for k, v in data.items()
            if isinstance(v, dict) and now - float(v.get("last", 0)) < 86400}
    data[task_id] = {"n": n, "last": now}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
    except OSError:
        pass
    return n


def reset_transient(sr, task_id, now):
    path = _counter_path(sr)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data[task_id] = {"n": 0, "last": now}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
    except (OSError, ValueError, TypeError):
        pass


def triage(text, task_id, model, sr, now=None, dry_run=False):
    """Return (action, fields-dict)."""
    now = time.time() if now is None else now
    verdict, _matched = sr.classify_text(text)
    if verdict in ("CONTEXT_EXHAUSTED", "SESSION_ERROR"):
        return "FRESH_SESSION", {"verdict": verdict,
                                 "reason": "session unusable; replacement with minimal transfer"}
    if verdict == "AUTH_ERROR":
        return "AUTH", {"verdict": verdict, "reason": "provider not connected; tell the owner"}
    if verdict == "AGENT_ERROR":
        return "AGENT_ERROR", {"verdict": verdict, "reason": "platform/config problem; do not rotate models"}

    secs, kind = stated_unavailability(text, sr, now)
    if secs is not None and secs > SHORT_WAIT_MAX_SEC:
        if not dry_run:
            sr.record_dead(model, secs, "%s (%s, stated by the provider)" % (verdict, kind),
                           pool_wide=verdict in sr.POOL_WIDE_VERDICTS)
        return "MIGRATE", {"seconds": int(math.ceil(secs)), "verdict": verdict, "kind": kind,
                           "reason": "unavailability is stated in the error"}

    # transient: wait and resume the SAME session on the SAME worker
    n = bump_transient(sr, task_id, now) if not dry_run else 1
    if n > MAX_TRANSIENT:
        if not dry_run:
            sr.record_dead(model, ESCALATION_COOLDOWN_SEC,
                           "%d consecutive transient failures (%s)" % (n, verdict),
                           pool_wide=False)
            reset_transient(sr, task_id, now)
        return "MIGRATE", {"seconds": ESCALATION_COOLDOWN_SEC, "verdict": verdict,
                           "kind": "escalation",
                           "reason": "%d transient failures in a row; short cooldown only" % n}
    wait = min(10 * n, 60)
    if secs is not None:
        wait = max(wait, int(math.ceil(secs)) + 5)
    return "RESUME_SAME", {"wait": wait, "attempt": "%d/%d" % (n, MAX_TRANSIENT),
                           "verdict": verdict,
                           "reason": "no stated unavailability; keep using this worker"}


def main(argv):
    import argparse
    p = argparse.ArgumentParser(description="Triage a failed worker Task.")
    p.add_argument("text", nargs="*", help="error text (else stdin)")
    p.add_argument("--task-id", default="unknown")
    p.add_argument("--model", default="")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    text = " ".join(a.text) if a.text else sys.stdin.read()
    sr = load_sr()
    action, fields = triage(text[:2000], a.task_id, a.model, sr, dry_run=a.dry_run)
    reason = fields.pop("reason", "")
    print(" ".join([action] + ["%s=%s" % (k, v) for k, v in fields.items()]
                   + (["reason=" + reason.replace(" ", "_")] if reason else [])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
