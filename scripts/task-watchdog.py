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
    if sid not in (reg.get("sessions") or {}):
        # Live session the registry never saw (its Task never returned its
        # task_id — exactly the blocked case). Track it WITHOUT touching
        # anything else, so abort/cooldown/resume all work on it.
        title = ""
        try:
            _code, _obj = sr.api_probe("GET", f"/session/{sid}")
            if isinstance(_obj, dict):
                title = _obj.get("title", "") or ""
        except Exception:
            pass
        meta = sr.upsert_discovered(sid, title=title)
        journal("DISCOVERED", session=sid, title=title)
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
    quota_abort = False
    if etype not in ("retry",):
        # busy/running/waiting = normal work. NEVER abort on activity alone.
        # BUT: check for tool aborts indicating quota exhaustion
        # (Free usage exceeded causes tool aborts even when status is empty).
        tool_abort, abort_reason = sr.check_tool_abort_quota(sid)
        if tool_abort:
            quota_abort = True
            verdict, matched = "FREE_USAGE_EXHAUSTED", "tool-abort-quota"
            delay = threshold + 1.0
            attempt = "?"
            journal("QUOTA_ABORT_DETECTED", session=sid, verdict=verdict,
                    reason=abort_reason)
        else:
            return "ok", f"active ({etype}), untouched"
    if not quota_abort:
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
    # STUCK in a provider wait over threshold: abort the blocked attempt.
    # Cooldown = the OBSERVED provider delay (a timetable fact recorded for
    # every verdict: the backend provably cannot generate before it elapses).
    if not do_abort:
        journal("WOULD_ABORT", session=sid, verdict=verdict, delaySec=delay,
                attempt=attempt)
        return "watch", "dry run"
    model = meta.get("model", "")
    worker = meta.get("agent", "")
    if not model:
        # Unregistered/discovered child: learn the backend from the newest
        # message tail (bounded fetch, never the whole history) and persist.
        pid, mid = sr.session_tail_model(sid)
        if mid and pid:
            model = f"{pid}/{mid}"
            try:
                reg = sr.load_reg()
                reg["sessions"][sid]["model"] = model
                sr.save_reg(reg)
            except (OSError, ValueError, KeyError):
                pass
    code, _obj = sr.api_probe("POST", f"/session/{sid}/abort", {})
    if code is None:
        journal("ABORT_FAILED", session=sid, reason="server unreachable")
        return "api-down", "abort: server unreachable"
    if code == 404:
        journal("ABORT_FAILED", session=sid, reason="session vanished")
        return "gone", "abort: 404"
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
    return "aborted", (f"aborted provider wait ({verdict}, "
                       f"delay={delay:.0f}s); cooldown recorded; "
                       f"resume SAME task_id on a healthy worker")


def resolve_targets(oid=None, session=None, all_sessions=False,
                    directory=None):
    if session:
        return [session]
    try:
        reg = sr.load_reg()
    except (OSError, ValueError):
        return []
    sessions = reg.get("sessions") or {}
    if all_sessions:
        targets = [sid for sid, m in sessions.items()
                   if (m or {}).get("state") != "retired"]
        # PLUS live discovery: the session that needs the watchdog most is
        # the one whose Task never returned (hence never registered).
        # Only same-directory Task children (title marker or tracked).
        live = sr.discover_live_children(directory=directory)
        if live is None:
            journal("DISCOVERY_UNKNOWN",
                    note="GET /session unreachable; registry targets only")
        else:
            for sid, _title, _parent in live:
                if sid not in targets:
                    targets.append(sid)
        return targets
    q = (oid or "").strip().lower()
    return [sid for sid, m in sessions.items()
            if (m.get("oid", "") or "").lower() == q or
            (not m.get("oid") and (m.get("objective", "") or "").lower() == q)]


def heartbeat_fresh(max_age=90):
    """True when watchdog.log ends with a recent HEARTBEAT (daemon alive)."""
    try:
        with open(JOURNAL) as f:
            lines = f.read().strip().split("\n")[-15:]
    except OSError:
        return False
    now = time.time()
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("event") != "HEARTBEAT":
            continue
        try:
            ts = datetime.fromisoformat(rec.get("ts", "").replace(
                "Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            continue
        return (now - ts) <= max_age
    return False


def daemonize():
    """Detach fully (double fork + fd redirect) so the CALLER RETURNS.

    Plain `&` backgrounding hangs some tool runtimes waiting on child fds;
    this does not: stdio goes to /dev/null and the parent exits at once.
    """
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    try:
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            try:
                os.dup2(devnull, fd)
            except OSError:
                pass
    except OSError:
        pass


def cmd_ensure(args, carry_argv):
    """One self-maintaining entrypoint: alive? -> print + exit 0.
    Stale/missing? -> spawn a detached daemon and exit at once.
    Synchronous, returns immediately either way (no `&` needed)."""
    interval, max_age = 20.0, 90.0
    i = 0
    while i < len(args):
        if args[i] == "--interval" and i + 1 < len(args):
            try:
                interval = float(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif args[i] == "--max-age" and i + 1 < len(args):
            try:
                max_age = float(args[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1
    if daemon_healthy(max_age):
        print("watchdog ALIVE (fresh HEARTBEAT + server reachable, "
              "nothing to do)")
        return 0
    if terminate_lock_holder():
        print("stopped previous deaf daemon; starting a fresh one")
    try:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
    except OSError:
        pass
    daemonize()
    # Child continues here: re-exec as a real daemon process.
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__),
                              "--daemon", "--all", "--interval",
                              str(interval)] + carry_argv)


def recent_events(limit=60):
    """Journal records, newest first (empty list when no journal)."""
    try:
        with open(JOURNAL) as f:
            lines = f.read().strip().split("\n")[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    out.reverse()
    return out


# Events proving the daemon REACHED the server (any answer, even 404, means
# the API talks to us). API_DOWN / ABORT_FAILED / STATUS_UNKNOWN /
# HEARTBEAT prove nothing and are skipped by the health check.
HEALTHY_EVENTS = {"WATCH", "ABORTED", "DISCOVERED", "SESSION_GONE",
                  "TIMEOUT", "WOULD_ABORT"}


def _rec_ts(rec):
    try:
        return datetime.fromisoformat(rec.get("ts", "").replace(
            "Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def daemon_healthy(max_age=90):
    """A daemon counts as alive only if it BOTH heartbeats AND actually
    reaches the server. A daemon stuck in API_DOWN (deaf to a restarted
    server) looks alive by heartbeat alone — this catches that, so
    --ensure replaces it instead of reporting ALIVE."""
    recs = recent_events()
    now = time.time()
    if not any(rec.get("event") == "HEARTBEAT"
               and (_rec_ts(rec) or 0) >= now - max_age for rec in recs):
        return False
    if not lock_held_by_live_process():
        return False
    # Newest signal event decides: a real server answer (or a fresh START
    # with no cycle yet) = healthy; pure API_DOWN streak = deaf.
    for rec in recs:
        ev, ts = rec.get("event"), _rec_ts(rec)
        if ev in ("HEARTBEAT", "API_DOWN", "ABORT_FAILED",
                  "STATUS_UNKNOWN"):
            continue
        if ev == "START":
            return ts is not None and (now - ts) <= max_age
        if ev in HEALTHY_EVENTS:
            # Only a FRESH server answer counts; an old WATCH followed by
            # an API_DOWN streak means the daemon went deaf since.
            if ts is not None and (now - ts) <= max_age:
                return True
            return False
        # Unknown future event kinds: do not judge, keep waiting for signal.
    return False


def lock_holder_pid():
    try:
        with open(LOCKFILE) as f:
            return int((json.load(f) or {}).get("pid") or 0)
    except (OSError, ValueError):
        return 0


def terminate_lock_holder():
    """SIGTERM a stale lock holder (never self). Returns True if signalled."""
    pid = lock_holder_pid()
    if not pid or pid == os.getpid():
        return False
    try:
        os.kill(pid, 15)
    except (OSError, ValueError):
        return False
    for _ in range(20):  # up to ~2s for a clean exit
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.1)
    return True  # signalled; proceeding anyway (lock will be replaced)


def lock_held_by_live_process():
    try:
        with open(LOCKFILE) as f:
            pid = int((json.load(f) or {}).get("pid") or 0)
    except (OSError, ValueError):
        return False
    if not pid or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def main(argv):
    import argparse
    # --ensure is handled before the target group (it takes no target).
    # Only --interval/--threshold pass through to the spawned daemon.
    if "--ensure" in argv:
        rest = [x for x in argv if x != "--ensure"]
        keep, carry = [], []
        i = 0
        while i < len(rest):
            if rest[i] in ("--interval", "--threshold") and i + 1 < len(rest):
                carry += [rest[i], rest[i + 1]]
                i += 2
            else:
                keep += [rest[i]]
                i += 1
        return cmd_ensure(keep, carry)
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
    p.add_argument("--directory", default="",
                   help="Project directory for live child discovery "
                        "(default: this repo root)")
    p.add_argument("--no-abort", action="store_true",
                   help="Observe only, never POST abort")
    a = p.parse_args(argv)
    mode_daemon = a.daemon and not a.once
    if mode_daemon and not lock_acquire():
        print("another watchdog daemon holds the lock; exiting")
        return 0
    targets = resolve_targets(oid=a.oid, session=a.session,
                              all_sessions=a.all,
                              directory=a.directory or None)
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
