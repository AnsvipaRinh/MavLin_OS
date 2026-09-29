#!/usr/bin/env python3
"""Independent watchdog for OpenCode child sessions (1.18.32, stdlib only).

WHY IT EXISTS: a foreground parent Task(...) blocks the orchestrator while a
child sits in a provider retry (e.g. `Free usage exceeded` ~4500s). No prompt
instruction can fire inside a blocked call, so an INDEPENDENT control path is
required. This script is that path: plain REST (verified endpoints only),
no LLM, no new sessions, no prompt replay.

LOOP PER TARGET SESSION (Objective -> task_id from registry, or --session):
  GET /session/{id}            -> 404: SESSION_GONE (drop target, exit 2 --once)
                                  unreachable: API_DOWN (skip; daemon retries)
  GET /session/status entry    -> idle/absent: nothing (absence = idle)
                                  busy: nothing (NEVER aborts normal work)
                                  retry + MODEL-dead message + delay>threshold:
                                    POST /session/{id}/abort
                                    mark model dead (cooldown = observed delay)
                                    record registry lastAbort + journal line
                                  retry otherwise: WATCH only (no abort)

ABORT SEMANTICS (verified vs 1.18.32 task.ts/prompt.ts): cancelling the child
prompt resolves the parent's blocked Task call with an error, so the
orchestrator regains its turn; persisted history survives; the SAME task_id
is then resumed on a healthy worker (migrate path). The watchdog itself
never sends prompts and never creates sessions.

SAFETY: aborts ONLY provider-retry states whose message classifies as a dead
MODEL_* verdict AND whose parsed retry delay exceeds --threshold. Normal
generation (busy), short/transient retries, network errors and unknown API
states are never aborted.

JOURNAL: JSON lines appended to .opencode/sessions/watchdog.log, incl.
periodic HEARTBEAT in daemon mode (proves liveness via `tail`).

USAGE:
  task-watchdog.py --daemon --all [--interval 20] [--threshold 600]
  task-watchdog.py --once --oid <objective-id> | --session <id> [--all]
"""
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "session_reuse", os.path.join(BASE, "session-reuse.py"))
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)

SESSIONS_DIR = os.path.join(BASE, "..", ".opencode", "sessions")
JOURNAL = os.path.join(SESSIONS_DIR, "watchdog.log")
LOCKFILE = os.path.join(SESSIONS_DIR, "watchdog.lock")

# MODEL_* verdicts that mean "this backend is dead, abort the wait".
DEAD_BACKEND = {"MODEL_QUOTA", "MODEL_RATE_LIMIT", "MODEL_TIMEOUT",
                "PROVIDER_ERROR", "FREE_USAGE_EXHAUSTED"}

# Generic provider-wait wording (the observed 4500-8800s
# "agent unavailable, retry in Ns" shape): a retry entry carrying this
# wording PLUS a parsed delay over threshold is definitively a provider-side
# wait, not generation — abortable even without quota-specific wording.
# Without a parsed long delay it is WATCH-only (never abort on words alone).
PROVIDER_WAIT_PATTERNS = [
    "unavailable", "retry", "retrying", "backoff", "waiting",
    "try again", "temporarily",
]


def journal(event, **fields):
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "event": event}
    rec.update(fields)
    try:
        with open(JOURNAL, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def lock_acquire():
    """Single-daemon guard. Returns True if we hold the lock."""
    try:
        with open(LOCKFILE) as f:
            old = json.load(f)
        pid = old.get("pid")
        if pid:
            try:
                os.kill(int(pid), 0)  # alive?
                if int(pid) != os.getpid():
                    return False
            except (OSError, ValueError):
                pass  # stale lock: previous daemon is gone
    except (OSError, ValueError):
        pass
    try:
        with open(LOCKFILE, "w") as f:
            json.dump({"pid": os.getpid(),
                       "at": datetime.now(timezone.utc).isoformat(
                           timespec="seconds")}, f)
    except OSError:
        return False
    return True


def lock_release():
    try:
        os.remove(LOCKFILE)
    except OSError:
        pass


def check_session(sid, threshold, do_abort=True):
    """One inspection cycle. Returns (action, detail). Actions: ok, watch,
    aborted, gone, api-down."""
    try:
        reg = sr.load_reg()
    except (OSError, ValueError):
        return "api-down", "registry unreadable"
    meta = (reg.get("sessions") or {}).get(sid, {})
    estate, _eobj = sr.session_exists(sid)
    if estate == "unavailable":
        journal("API_DOWN", session=sid)
        return "api-down", "server unreachable"
    if estate == "not-exist":
        journal("SESSION_GONE", session=sid,
                objective=meta.get("objective", ""))
        return "gone", "404 from GET /session/{id}"
    try:
        st = sr.api("GET", "/session/status") or {}
    except SystemExit:
        journal("STATUS_UNKNOWN", session=sid)
        return "ok", "exists, activity unknown"
    entry = st.get(sid)
    if entry is None:
        return "ok", "exists, no status entry = idle"
    etype = entry.get("type", "?") if isinstance(entry, dict) else "?"
    if etype == "idle":
        return "ok", "idle"
    if etype not in ("retry",):
        # busy/running/waiting = normal work. NEVER abort on activity alone.
        return "ok", f"active ({etype}), untouched"
    msg = (entry.get("message", "") or "") if isinstance(entry, dict) else ""
    # Both status shapes exist in the wild: 1.18.32 uses `message`, older
    # surfaces used `error`. Scan both for wait wording.
    msg_all = " ".join(
        str((entry or {}).get(k, "") or "")
        for k in ("message", "error", "reason")).lower() \
        if isinstance(entry, dict) else ""
    verdict, matched = sr.classify_text(msg)
    delay = sr.extract_delay_sec(entry) if isinstance(entry, dict) else None
    attempt = (entry.get("attempt") or "?") if isinstance(entry, dict) else "?"
    provider_wait = any(w in msg_all for w in PROVIDER_WAIT_PATTERNS)
    if verdict not in DEAD_BACKEND and not (
            provider_wait and delay is not None and delay > threshold):
        journal("WATCH", session=sid, status=etype, verdict=verdict,
                delaySec=delay, attempt=attempt)
        return "watch", f"retry but {verdict} (not an abortable wait)"
    if delay is None or delay <= threshold:
        journal("WATCH", session=sid, status=etype, verdict=verdict,
                delaySec=delay, attempt=attempt,
                note="below threshold, no abort")
        return "watch", f"retry but delay {delay} <= {threshold}"
    # STUCK in a dead-backend retry: abort the blocked attempt.
    if not do_abort:
        journal("WOULD_ABORT", session=sid, verdict=verdict, delaySec=delay,
                attempt=attempt)
        return "watch", "dry run"
    code, _obj = sr.api_probe("POST", f"/session/{sid}/abort", {})
    if code is None:
        journal("ABORT_FAILED", session=sid, reason="server unreachable")
        return "api-down", "abort: server unreachable"
    if code == 404:
        journal("ABORT_FAILED", session=sid, reason="session vanished")
        return "gone", "abort: 404"
    model = meta.get("model", "")
    worker = meta.get("agent", "")
    if model:
        h = sr.load_health()
        h["models"][model.lower()] = {
            "model": model, "state": "dead",
            "deadAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "retryAfter": time.time() + delay,
            "cooldownSec": delay,
            "reason": f"watchdog abort {sid}: {verdict} delay={delay:.0f}s",
        }
        sr.save_health(h)
    try:
        reg = sr.load_reg()
        m = reg["sessions"][sid]
        m["lastAbort"] = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": verdict, "delaySec": delay, "worker": worker,
            "model": model, "abortHttp": code,
        }
        sr.save_reg(reg)
    except (OSError, ValueError, KeyError):
        pass
    journal("ABORTED", session=sid, verdict=verdict, delaySec=delay,
            attempt=attempt, worker=worker, model=model, abortHttp=code)
    return "aborted", (f"aborted dead-backend retry ({verdict}, "
                       f"delay={delay:.0f}s); cooldown recorded; "
                       f"resume SAME task_id on a healthy worker")


def resolve_targets(oid=None, session=None, all_sessions=False):
    if session:
        return [session]
    try:
        reg = sr.load_reg()
    except (OSError, ValueError):
        return []
    sessions = reg.get("sessions") or {}
    if all_sessions:
        return [sid for sid, m in sessions.items()
                if (m or {}).get("state") != "retired"]
    q = (oid or "").strip().lower()
    return [sid for sid, m in sessions.items()
            if (m.get("oid", "") or "").lower() == q or
            (not m.get("oid") and (m.get("objective", "") or "").lower() == q)]


def main(argv):
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--oid", default="")
    g.add_argument("--session", default="")
    g.add_argument("--all", action="store_true")
    p.add_argument("--threshold", type=float, default=600)
    p.add_argument("--interval", type=float, default=20)
    p.add_argument("--timeout", type=float, default=7200,
                   help="Max wall-clock seconds (0 = unlimited)")
    p.add_argument("--once", action="store_true")
    p.add_argument("--daemon", action="store_true")
    p.add_argument("--no-abort", action="store_true",
                   help="Observe only, never POST abort")
    a = p.parse_args(argv)
    mode_daemon = a.daemon and not a.once
    if mode_daemon and not lock_acquire():
        print("another watchdog daemon holds the lock; exiting")
        return 0
    targets = resolve_targets(oid=a.oid, session=a.session,
                              all_sessions=a.all)
    if not targets:
        print("no target sessions (oid has no registered live mapping?)")
        if mode_daemon:
            lock_release()
        return 2
    journal("START", mode="daemon" if mode_daemon else "once",
            targets=targets, threshold=a.threshold)
    deadline = time.time() + a.timeout if a.timeout and a.timeout > 0 else None
    initial_count = len(targets)
    gone_count = 0
    try:
        while True:
            for sid in list(targets):
                action, detail = check_session(
                    sid, a.threshold, do_abort=not a.no_abort)
                print(f"{action} {sid}: {detail}")
                if action == "gone":
                    gone_count += 1
                    if not a.all:
                        targets.remove(sid)
            journal("HEARTBEAT", targets=targets,
                    interval=a.interval, threshold=a.threshold)
            if a.once or not targets:
                break
            if deadline is not None and time.time() >= deadline:
                journal("TIMEOUT", note="max wall-clock reached, exiting")
                break
            time.sleep(max(1.0, a.interval))
    finally:
        if mode_daemon:
            lock_release()
    # --once with every target gone: nothing to watch.
    if a.once and initial_count and gone_count >= initial_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
