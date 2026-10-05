#!/usr/bin/env python3
"""Session lifecycle helper for the Orchestrator (OpenCode 1.18.x, real APIs only).

Reads live state from the opencode server (env: OPENCODE_SERVER_HOST=localhost,
OPENCODE_SERVER_PORT=4096, OPENCODE_SERVER_USERNAME=opencode, OPENCODE_SERVER_PASSWORD)
and keeps lightweight metadata in .opencode/sessions/registry.json.

  register <id> --agent A --objective O --task T [--model p/m]  track a session
  context  <id> [--limit N]     live context usage + REUSABLE/RETIRE verdict
  decide   <id> --objective O   resume same session or create new?
  retire   <id> [--delete]      mark retired; optionally DELETE via API
  delete   <id>                 DELETE via API (only after result processed!)
  status                    live status of all sessions (idle/busy/retry)
  children <id>             list child (sub-agent) sessions
  list                      registry contents
  exists <id>               authoritative existence + activity via
                            GET /session/{id} + status: SESSION_EXISTS_IDLE/
                            BUSY/RETRYING, SESSION_DOES_NOT_EXIST,
                            SESSION_API_UNAVAILABLE
  abort <id>                cancel a blocked generation
                            (POST /session/{id}/abort); history survives
  preflight [--exclude M]   offline worker/health decision BEFORE every Task:
                            PRIMARY_READY/COOLDOWN + PREFLIGHT_OK/WAIT,
                            zero API calls
  version                   print orchestrator protocol version (v4 required
                            by the current orchestrator prompt; unknown
                            subcommand = stale agent file -> STALE-AGENT)
  health                    show model cooldown memory (dead models + retry-in)
  mark-dead <model> [--in Sec] [--reason R]
                            record a model as dead: skip it for Sec seconds
                            (default 10800 = 3h when the provider gave no
                            explicit retry time)
  mark-alive <model>        clear a model's cooldown (call after a good result)
  stuck [--threshold 600] [--format text|json]
                            stuck-task watchdog: parse live /session/status
                            retry/unavailable delays; any non-idle session
                            with delay > threshold (default 600s = 10min)
                            is STUCK -> must be paused + migrated.
  migrate <id> --objective O [--task T] [--exclude M,...] [--delay Sec]
                            same-session model migration (SESSION != MODEL):
                            keep task_id, record dead-model cooldown
                            (= delay when known, else 3h), print a Task block
                            resuming the SAME session on the next worker.
  find-objective <oid-or-text>
                            resume-first lookup: Objective -> live child
                            session + ready Task invocation (one status call,
                            no message download).
  link-objective <id> --oid X [--objective T]
                            attach a stable Objective ID to a session without
                            wiping metadata (safe for old records).
  models [--exclude M,...] [--all] [--ignore-cooldown] [--format text|json]
                            ordered fallback candidates, CHAIN-ONLY by default
                            (user chain matched live vs GET /provider).
                            --all adds config pins, registry last-good,
                            remaining live models. Chain 'never' list is
                            always excluded. No hardcoding.
  classify-error [TEXT...]  failure taxonomy (SESSION != MODEL):
                            MODEL_QUOTA(10)/RATE_LIMIT(11)/TIMEOUT(13)/
                            PROVIDER(14) -> same-session failover;
                            CONTEXT(12)/SESSION(16) -> replacement session;
                            NETWORK(15) -> same session, no cooldown;
                            AGENT(17)/PROJECT(20)/AUTH(40)/UNKNOWN(30).
                            Only MODEL_* record dead models.

Reuse rule: same agent role (`build`) + same objective + coherent + >50% context remaining.
Objective boundary: Calendar -> Calendar refinement = SAME session;
Calendar -> Disk Utility = NEW session. Never resume on context pressure,
error state, or role/objective change.

Model fallback (2026-09-26): a QUOTA/CONTEXT Task failure is never a project
blocker. Resolve next model via `models --exclude <dead,...>`, ping it with a
trivial Task, continue the SAME objective there (RESUME if `decide` allows,
else NEW session carrying prior result + remaining gaps). Chain order lives in
.opencode/model-fallback.json, never in this script.

Stuck-task failover (2026-09-29, corrected 2026-09-30: SESSION != MODEL).
A provider retry/unavailable backoff longer than STUCK_THRESHOLD_SEC
(default 600 = 10 min) is never waited out. The logical session is
PRESERVED: `stuck` detects, `migrate` records the dead-model cooldown and
prints a Task block resuming the SAME task_id on the next healthy worker
(per-prompt model switch — no replacement session, no prompt replay).
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))


def _state_dir():
    """State directory: $SR_STATE_DIR override (test isolation) else repo."""
    d = os.environ.get("SR_STATE_DIR", "")
    if d:
        return d
    return os.path.join(BASE, "..", ".opencode", "sessions")


REG = os.path.join(_state_dir(), "registry.json")
CHAIN = os.path.join(BASE, "..", ".opencode", "model-fallback.json")

# Orchestrator protocol version. The orchestrator prompt requires THIS version:
# if `version` prints anything older (or the subcommand is unknown = stale
# agent file cached by a long-lived server), the orchestrator must report
# STALE-AGENT and stop instead of silently running the old loop.
# v17 bump (2026-10-05): pure synchronization with .opencode/agents/orchestrator.md
# — that file already requires v17 while the script implemented the full v17
# subcommand surface (all 22 commands incl. stalled/link-objective/children/
# list/retire/delete). No behavior change; closing the false STALE-AGENT gate.
ORCHESTRATOR_PROTOCOL = 17

# Cooldown memory for dead models (.opencode/sessions/model-health.json).
# A model observed dead (provider retry/unavailable > stuck threshold, or
# QUOTA/CONTEXT Task failure) is skipped for COOLDOWN_SEC unless the provider
# gave an explicit retry delay (then that delay is used). Default 3h per user
# spec when no explicit time is known; after expiry the model is retried.
HEALTH = os.path.join(_state_dir(), "model-health.json")
DEFAULT_COOLDOWN_SEC = 10800

# Server endpoint auto-discovery (2026-10-02: the OpenCode server port AND
# password change on every restart, so nothing may be hardcoded or required
# by hand). Resolution order: explicit env wins -> live `opencode serve`
# process command line -> compiled-in default. No manual lookup needed.
_server_cache = {"at": 0.0, "port": ""}


def _ps_table():
    """[(pid, args)] of all processes (pure parse helper needs text)."""
    import subprocess
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                             text=True, timeout=10).stdout or ""
    except Exception:
        return []
    rows = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(.*)$", line)
        if m:
            rows.append((int(m.group(1)), m.group(2)))
    return rows


def _parse_serve_processes(ps_text):
    """[(pid, port-or-None)] for `opencode ... serve ...` lines. Pure."""
    out = []
    for line in (ps_text or "").splitlines():
        m = re.match(r"\s*(\d+)\s+(.*)$", line)
        if not m:
            continue
        pid, args = int(m.group(1)), m.group(2)
        if "opencode" in args and "serve" in args and "grep" not in args:
            pm = re.search(r"--port\s+(\d+)", args)
            out.append((pid, pm.group(1) if pm else None))
    return out


def _ps_opencode_ports():
    """Ports parsed from live `opencode ... serve ...` processes.

    Pure string parsing (no connection attempts); testable without a server.
    """
    import subprocess
    try:
        out = subprocess.run(["ps", "-eo", "args"], capture_output=True,
                             text=True, timeout=10).stdout or ""
    except Exception:
        return []
    ports = []
    for line in out.splitlines():
        if "opencode" in line and "serve" in line:
            m = re.search(r"--port\s+(\d+)", line)
            if m and m.group(1) not in ports:
                ports.append(m.group(1))
    return ports


def _read_proc_environ(pid):
    """Environ dict of a live process (Linux /proc). Same-user only."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            raw = f.read().split(b"\0")
    except (OSError, ValueError):
        return {}
    out = {}
    for item in raw:
        if b"=" in item:
            k, v = item.split(b"=", 1)
            try:
                out[k.decode()] = v.decode()
            except UnicodeDecodeError:
                pass
    return out


def _proc_credentials():
    """(user, password) from the live server process environment.

    Long-lived processes (watchdog daemon) outlive server restarts: their
    own env holds a STALE password while the new server generated a fresh
    one. /proc/<serve-pid>/environ is the authoritative current source.
    Returns (None, None) when unavailable (non-Linux, no permission).
    """
    for pid, _port in _parse_serve_processes("\n".join(
            f"{p} {a}" for p, a in _ps_table())):
        env = _read_proc_environ(pid)
        pw = env.get("OPENCODE_SERVER_PASSWORD", "")
        if pw:
            return env.get("OPENCODE_SERVER_USERNAME", "opencode"), pw
    return None, None


def server_host():
    return os.environ.get("OPENCODE_SERVER_HOST", "localhost")


def server_port(ttl=60):
    """Server port: env -> live serve process -> 4096 default."""
    env = (os.environ.get("OPENCODE_SERVER_PORT") or "").strip()
    if env:
        return env
    now = time.time()
    if now - _server_cache["at"] < ttl and _server_cache["port"]:
        return _server_cache["port"]
    for p in _ps_opencode_ports():
        _server_cache.update(at=now, port=p)
        return p
    return "4096"


def server_user():
    return os.environ.get("OPENCODE_SERVER_USERNAME", "opencode")


def server_pass():
    return os.environ.get("OPENCODE_SERVER_PASSWORD", "")


def _api_once(method, path, body, use_proc_creds):
    import base64
    if use_proc_creds:
        user, pwd = _proc_credentials()
        if user is None:
            return ("unreachable", None)
    else:
        user, pwd = server_user(), server_pass()
    req = urllib.request.Request(
        f"http://{server_host()}:{server_port() if not use_proc_creds else server_port(ttl=-1)}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": "Basic " + base64.b64encode(
                     f"{user}:{pwd}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return ("ok", json.loads(r.read().decode() or "null"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return ("auth", None)
        return ("http-%d" % e.code,
                e.read().decode()[:200])
    except urllib.error.URLError as e:
        return ("unreachable", str(getattr(e, "reason", e)))


def api(method, path, body=None):
    status, payload = _api_once(method, path, body, False)
    if status in ("auth", "unreachable"):
        # Server restarted under us (new port/password): refresh from the
        # live process and retry once before giving up.
        _server_cache["at"] = 0
        status, payload = _api_once(method, path, body, True)
    if status == "ok":
        return payload
    if status == "unreachable":
        # Connection refused / DNS / offline: structured exit, never a
        # traceback — callers map this to UNKNOWN/VERIFY, never NEW.
        sys.exit(f"API {method} {path} -> unreachable: {payload}")
    if status == "auth":
        sys.exit(f"API {method} {path} -> HTTP 401 (auth failed even "
                 f"with live server credentials)")
    sys.exit(f"API {method} {path} -> HTTP {status}: {payload}")


def api_probe(method, path, body=None):
    """Low-level call returning (http_code_or_None, parsed_or_None).

    http_code None = server unreachable (refused/DNS/offline).
    Used for existence checks where 404 is a VALID answer
    (SESSION_DOES_NOT_EXIST), not an error.
    """
    # First attempt: configured credentials. On 401 (password rotated by a
    # server restart) or unreachable (port moved), refresh from the live
    # server process and retry ONCE. This is what keeps long-lived daemons
    # working across restarts with zero manual steps.
    code, obj = _api_probe_once(method, path, body, use_proc_creds=False)
    if code == 401 or code is None:
        _server_cache["at"] = 0  # force fresh ps discovery too
        code2, obj2 = _api_probe_once(method, path, body, use_proc_creds=True)
        # A retry that still fails is the real answer (wrong creds everywhere
        # looks identical to server-down from here: report unreachable).
        if code2 is not None:
            return code2, obj2
    return code, obj


def _api_probe_once(method, path, body, use_proc_creds=False):
    import base64
    if use_proc_creds:
        user, pwd = _proc_credentials()
        if user is None:
            return None, None
    else:
        user, pwd = server_user(), server_pass()
    req = urllib.request.Request(
        f"http://{server_host()}:{server_port() if not use_proc_creds else server_port(ttl=-1)}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": "Basic " + base64.b64encode(
                     f"{user}:{pwd}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except urllib.error.URLError:
        return None, None


def session_exists(session_id):
    """Authoritative existence check via GET /session/{id} (1.18.32 SDK).

    Returns ("exists", obj) / ("not-exist", None) / ("unavailable", None).
    Persistent sessions survive server restart (local DB + UI-visible);
    absence from /session/status means IDLE, never nonexistence.
    """
    code, obj = api_probe("GET", f"/session/{session_id}")
    if code is None:
        return "unavailable", None
    if code == 404:
        return "not-exist", None
    if 200 <= code < 300:
        return "exists", obj
    return "unavailable", None


def api_list_sessions(directory=None):
    """GET /session[?directory=...] -> list (or None when unreachable).

    The persistent session store: restarted servers still list old sessions.
    Used for discovering live child sessions the registry never saw
    (their task_id is learned only when a Task returns — which never
    happens while the Task is blocked in a provider retry).
    """
    import urllib.parse
    path = "/session"
    if directory:
        path += "?directory=" + urllib.parse.quote(directory, safe="")
    code, obj = api_probe("GET", path)
    if code is None or not 200 <= code < 300 or not isinstance(obj, list):
        return None
    return obj


def repo_root():
    import os as _os
    # Project directory (this repo). Used as the explicit ?directory= scope
    # for GET /session: the server's unfiltered list is project-scoped and
    # SILENTLY OMITS sessions outside its own default scope (verified live:
    # 6 sessions unfiltered vs 100 with ?directory=<repo>, including the
    # stuck child). Never rely on the unfiltered list for discovery.
    return _os.path.realpath(_os.path.join(BASE, ".."))


def discover_live_children(directory=None):
    """Live child (subagent) sessions of this project, registry or not.

    Filter: same directory AND agent is a known worker (build, build-b, build-c).
    Returns [(id, title, parentID)].
    """
    root = directory or repo_root()
    try:
        reg = load_reg()
        known = set((reg.get("sessions") or {}).keys())
    except (OSError, ValueError):
        known = set()
    workers = set()
    for role, model in worker_pins():
        workers.add(role)
    # Explicit directory scope: the server's default list omits sessions
    # outside its own scope WITHOUT any signal (verified live).
    sessions = api_list_sessions(directory=root)
    if sessions is None:
        return None
    out = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", "")
        if not sid:
            continue
        if (s.get("directory", "") or "") != root:
            continue
        agent = s.get("agent", "") or ""
        if agent not in workers and sid not in known:
            continue
        out.append((sid, s.get("title", "") or "", s.get("parentID", "")))
    return out


def session_tail_model(session_id, limit=5):
    """(providerID, modelID) from the newest message carrying model info.

    Bounded tail fetch (?limit=) — never downloads a 200k-token history
    just to learn which backend is stuck.
    """
    code, msgs = api_probe("GET", f"/session/{session_id}/message"
                                  f"?limit={int(limit)}")
    if code is None or not 200 <= code < 300 or not isinstance(msgs, list):
        return None, None
    for m in reversed(msgs):
        info = (m or {}).get("info", {}) if isinstance(m, dict) else {}
        mid = info.get("modelID") or ""
        pid = info.get("providerID") or ""
        if mid and pid:
            return pid, mid
    return None, None


def check_tool_abort_quota(session_id):
    """Check if the session's latest active generation has tool aborts
    indicating quota exhaustion (Free usage exceeded).

    Returns (True, reason) if quota abort detected, else (False, "").
    """
    code, msgs = api_probe("GET", f"/session/{session_id}/message?limit=5")
    if code is None or not 200 <= code < 300 or not isinstance(msgs, list):
        return False, ""
    for m in msgs:
        info = (m or {}).get("info", {}) if isinstance(m, dict) else {}
        if info.get("role") == "assistant" and info.get("finish") is None:
            # Active generation — check tool parts for aborts
            for p in m.get("parts", []):
                if p.get("type") == "tool":
                    state = p.get("state", {})
                    if state.get("status") == "error":
                        error = state.get("error", "") or ""
                        # "Tool execution aborted" with interrupted=true often wraps quota exhaustion
                        # Check for explicit quota keywords OR interrupted abort in active generation
                        if "aborted" in error.lower():
                            if ("free usage" in error.lower() or
                                "usage exceeded" in error.lower() or
                                "subscribe to go" in error.lower() or
                                "quota" in error.lower()):
                                return True, f"tool abort indicates quota: {error}"
                            # Interrupted abort in active generation = likely quota
                            if state.get("metadata", {}).get("interrupted") is True:
                                return True, f"tool interrupted abort (likely quota): {error}"
    return False, ""


def stalled_generation(session_id, threshold=600, now=None):
    """Detect a provider wait that /session/status does NOT show.

    Proven live shape (2026-10-02): an assistant message shell is created
    (~100ms after the user prompt) with ZERO tokens, ZERO parts,
    finish=None — and stays that way for 4000+s while the parent Task
    stays `running` and the status map stays EMPTY. The provider wait is
    invisible to status-based detection, so the watchdog would idle forever.

    Returns (is_stalled, age_sec, model_str). Stalled IFF: newest message
    is assistant AND finish is None AND output tokens == 0 AND no tool
    parts AND no error recorded AND its age exceeds threshold. Any real
    generation progress (output tokens, tool parts, finish set, error
    recorded) = not stalled.
    No user-prompt window check by design: an assistant message cannot
    exist without a preceding user prompt somewhere in history (platform
    invariant — every assistant has a parent chain to a user message), so
    scanning windows (3, then 8 — both missed live stalls buried behind
    tool-call rounds) is pure downside. Bounded (?limit=3) tail fetch.
    """
    import time as _time
    now_ms = int((now if now is not None else _time.time()) * 1000)
    code, msgs = api_probe("GET", f"/session/{session_id}/message?limit=3")
    if code is None or not 200 <= code < 300 or not isinstance(msgs, list):
        return False, 0, ""
    if not msgs:
        return False, 0, ""
    last = msgs[-1]
    if not isinstance(last, dict):
        return False, 0, ""
    info = last.get("info", {}) or {}
    if info.get("role") != "assistant" or info.get("finish") is not None:
        return False, 0, ""
    if info.get("error"):
        return False, 0, ""  # failed attempt, not a silent stall
    toks = info.get("tokens") or {}
    if (toks.get("output") or 0) > 0:
        return False, 0, ""
    if any((p or {}).get("type") == "tool" for p in (last.get("parts") or [])):
        return False, 0, ""  # tool work in flight = progress, not a stall
    created = ((info.get("time") or {}).get("created")) or 0
    if not created:
        return False, 0, ""  # no timestamp: cannot prove age, stay silent
    try:
        age = (now_ms - int(created)) / 1000.0
    except (TypeError, ValueError):
        return False, 0, ""
    if age <= threshold:
        return False, age, ""
    model = "%s/%s" % (info.get("providerID") or "",
                        info.get("modelID") or "")
    model = model if model != "/" else ""
    return True, age, model


def cmd_stalled(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Detect a stalled generation invisible to /session/status: "
                    "newest message is an assistant shell with zero output "
                    "tokens, no finish, preceded by a user prompt, older "
                    "than --threshold. Exit 2 = STALLED.")
    p.add_argument("id")
    p.add_argument("--threshold", type=float, default=600)
    a = p.parse_args(args)
    stalled, age, model = stalled_generation(a.id, a.threshold)
    if stalled:
        print(f"STALLED {a.id} (zero output for {age:.0f}s > "
              f"{a.threshold:g}s; model={model or '?'}; abort + migrate "
              f"same task_id)")
        raise SystemExit(2)
    print(f"OK ({a.id}: latest generation shows progress or is fresh)")


def upsert_discovered(session_id, title="", model=""):
    """Track a live-discovered child WITHOUT touching existing metadata.

    Registry entries for sessions the orchestrator never saw (blocked Task
    never returned its task_id). Creates a minimal reusable record, or fills
    in a missing model on an existing one. Returns the entry.
    """
    try:
        reg = load_reg()
    except (OSError, ValueError):
        return {}
    sessions = reg.setdefault("sessions", {})
    meta = sessions.get(session_id)
    if meta is None:
        meta = {
            "agent": "?", "objective": title or "discovered-child",
            "task": title or "discovered-child",
            "model": model, "oid": "", "state": "reusable",
            "lastUsed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lastResult": "", "failure": "", "discovered": True,
        }
        sessions[session_id] = meta
    else:
        if not meta.get("model") and model:
            meta["model"] = model
        meta["discovered"] = bool(meta.get("discovered", False))
    try:
        save_reg(reg)
    except OSError:
        pass
    return meta


def load_reg():
    """Load the registry; missing/corrupt file = empty (never raises).

    The registry is a cache of task_id metadata, not the source of truth
    (OpenCode owns sessions). Mutating commands recreate it on save.
    """
    try:
        with open(REG) as f:
            reg = json.load(f)
        if isinstance(reg, dict):
            reg.setdefault("sessions", {})
            return reg
    except (OSError, ValueError):
        pass
    return {"$schema": "session-registry v1", "sessions": {}}


def save_reg(reg):
    with open(REG, "w") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")


def model_limit(model):
    """Find model limit.context via provider list; None if unknown."""
    if not model or "/" not in model:
        return None
    pid, mid = model.split("/", 1)
    try:
        provs = api("GET", "/provider")
    except SystemExit:
        return None
    for p in provs.get("all", []):
        if p.get("id") == pid:
            models = p.get("models", {})
            m = models.get(mid) if isinstance(models, dict) else next(
                (x for x in models if isinstance(x, dict) and x.get("id") == mid), None)
            if isinstance(m, dict):
                return (m.get("limit") or {}).get("context")
    return None


LIMITS_CACHE = os.path.join(_state_dir(), "model-limits.json")
LIMITS_TTL_SEC = 24 * 3600


def cached_limit(model):
    """Model limit.context with a 24h file cache (avoids GET /provider per call)."""
    try:
        with open(LIMITS_CACHE) as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    entry = cache.get(model or "")
    if isinstance(entry, dict) and \
            time.time() - float(entry.get("at", 0)) < LIMITS_TTL_SEC:
        return entry.get("limit")
    limit = model_limit(model)
    if limit:
        cache[model] = {"limit": limit, "at": time.time()}
        try:
            with open(LIMITS_CACHE, "w") as f:
                json.dump(cache, f, indent=1)
                f.write("\n")
        except OSError:
            pass
    return limit


def live_context(session_id):
    """Return (used_input_tokens, limit_or_None) from last assistant message."""
    msgs = api("GET", f"/session/{session_id}/message") or []
    used = 0
    for m in msgs:
        info = m.get("info", {})
        if info.get("role") == "assistant":
            toks = info.get("tokens") or {}
            used = max(used, toks.get("input", 0))
    return used, msgs


def cmd_register(args):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--agent", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--model", default="")
    p.add_argument("--oid", default="",
                   help="Stable logical Objective ID (find-objective key). "
                        "Re-registering the same id preserves oid/lastResult "
                        "unless explicitly overridden.")
    p.add_argument("--failure", default="",
                   help="Failure class of the last generation on this session "
                        "(taxonomy verdict or empty). Preserved across calls.")
    a = p.parse_args(args)
    reg = load_reg()
    prev = reg["sessions"].get(a.id, {})
    reg["sessions"][a.id] = {
        "agent": a.agent, "objective": a.objective, "task": a.task,
        "model": a.model or prev.get("model", ""),
        "oid": a.oid or prev.get("oid", ""),
        "state": "reusable",
        "lastUsed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Never wipe history metadata on re-register: task_id survival must
        # not depend on whether the last generation succeeded.
        "lastResult": prev.get("lastResult", ""),
        "failure": a.failure or prev.get("failure", ""),
    }
    # Preserve migration trail if present.
    if "migratedFrom" in prev:
        reg["sessions"][a.id]["migratedFrom"] = prev["migratedFrom"]
    save_reg(reg)
    print(f"registered {a.id} ({a.agent}/{a.objective})")


def cmd_link_objective(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Attach a stable Objective ID (and optionally objective "
                    "text) to an existing session WITHOUT wiping lastResult "
                    "or other metadata. Safe for old records.")
    p.add_argument("id")
    p.add_argument("--oid", required=True)
    p.add_argument("--objective", default="")
    a = p.parse_args(args)
    reg = load_reg()
    meta = reg["sessions"].get(a.id)
    if not meta:
        sys.exit(f"unknown session {a.id} (register first)")
    meta["oid"] = a.oid
    if a.objective:
        meta["objective"] = a.objective
    meta["lastUsed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_reg(reg)
    print(f"linked {a.id} -> objective {a.oid}")


def cmd_find_objective(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Resume-first lookup: Objective ID (or legacy objective "
                    "text) -> live child session + ready Task invocation. "
                    "One status call, no message download. Exit 0 = LIVE "
                    "(resumable now), 2 = STALE/SESSION_UNAVAILABLE "
                    "(needs fresh with minimal transfer), "
                    "3 = status unreachable (verify, do NOT duplicate).")
    p.add_argument("objective")
    a = p.parse_args(args)
    reg = load_reg()
    q = (a.objective or "").strip().lower()
    hits = [sid for sid, m in reg["sessions"].items()
            if (m.get("oid", "") or "").lower() == q or
            (not m.get("oid") and (m.get("objective", "") or "").lower() == q)]
    # Fallback to live discovery when registry has no matches
    if not hits:
        live = discover_live_children()
        if live is None:
            print(f"FRESH (session API unreachable; cannot discover live children)")
            raise SystemExit(3)
        for sid, title, _parent in live:
            # Match by oid in title or by objective text
            if (f"oid:{q}" in title.lower() or q in title.lower()):
                hits.append(sid)
        if not hits:
            print(f"FRESH (no session registered or live for objective '{a.objective}'; "
                  f"create one with a fresh Task, then register its task_id)");
            return
    if len(hits) > 1:
        print(f"AMBIGUOUS ({len(hits)} sessions match '{a.objective}'; "
              f"attach distinct --oid via link-objective, then retry)");
        for sid in hits:
            print(f"  - {sid} worker={reg.get('sessions', {}).get(sid, {}).get('agent', '?')}")
        raise SystemExit(4)
    sid = hits[0]
    meta = reg["sessions"].get(sid, {})
    # Authoritative existence first: post-restart sessions answer here
    # even with no status entry (status absence = idle, never gone).
    estate, _eobj = session_exists(sid)
    if estate == "unavailable":
        print(f"VERIFY (session API unreachable; session {sid} may still be "
              f"alive — do NOT create a duplicate)");
        raise SystemExit(3)
    if estate == "not-exist":
        if meta.get("state") != "stale":
            meta["state"] = "stale"
            save_reg(reg)
        print(f"SESSION_UNAVAILABLE (session {sid} for objective "
              f"'{a.objective}' genuinely absent from OpenCode store; "
              f"start FRESH with minimal state transfer, then "
              f"register the new task_id under the same oid)");
        raise SystemExit(2)
    if meta.get("state") == "stale":
        meta["state"] = "reusable"
        save_reg(reg)
    try:
        st = api("GET", "/session/status") or {}
    except SystemExit:
        print(f"WAIT (session {sid} proven to exist; activity unknown — "
              f"WAIT, do NOT duplicate)");
        return
    entry = st.get(sid)
    if entry is None:
        etype = "idle"  # proven to exist, no status entry = idle
    elif isinstance(entry, dict):
        etype = entry.get("type", "?")
    else:
        etype = "?"
    if etype != "idle":
        print(f"WAIT (session {sid} status={etype}; previous Task still "
              f"active — wait or run stuck --threshold 600)");
        return
    print(f"LIVE {sid} worker={meta.get('agent')} model={meta.get('model')} "
          f"state={meta.get('state')}")
    print("--- Task call (resume SAME session, full context preserved) ---")
    print(f"subagent_type={meta.get('agent')}")
    print(f"task_id={sid}")
    print("prompt: Продолжай с места остановки (remaining gaps only). "
          "Do not invoke subagents, do the work directly.")


def cmd_context(args):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--model", default="")
    a = p.parse_args(args)
    reg = load_reg()
    meta = reg["sessions"].get(a.id, {})
    model = a.model or meta.get("model", "")
    try:
        used, _ = live_context(a.id)
    except SystemExit as e:
        print(f"UNKNOWN (context unreadable for {a.id}: {e}; session may "
              f"still exist — verify with exists, do NOT duplicate)")
        return
    limit = a.limit or cached_limit(model)
    if not limit:
        print(f"used_input={used} limit=UNKNOWN(model '{model}' not resolvable) "
              f"-> cannot prove >50% remaining: treat as RETIRE for substantial work")
        return
    remaining = 1.0 - used / limit
    verdict = "REUSABLE" if remaining > 0.5 else "RETIRE"
    print(f"used_input={used} limit={limit} remaining={remaining:.1%} -> {verdict}")


def cmd_decide(args):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--objective", required=True)
    p.add_argument("--agent", default="")
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args(args)
    reg = load_reg()
    meta = reg["sessions"].get(a.id)
    if not meta:
        print("NEW (unknown session, register first)");
        return
    if meta.get("state") == "retired":
        print("NEW (session retired)");
        return
    if a.objective != meta.get("objective") and \
            a.objective != meta.get("oid", ""):
        print(f"NEW (objective boundary: {meta.get('objective')} -> {a.objective})");
        return
    # SESSION != MODEL: a different requested worker is a model failover,
    # never a reason for a new session. It is noted, not punished.
    worker_note = ""
    if a.agent and a.agent != meta.get("agent"):
        worker_note = (f" [failover {meta.get('agent')} -> {a.agent}, "
                       f"same session preserved]")
    # 1. AUTHORITATIVE EXISTENCE via GET /session/{id} (survives restart;
    #    UI-visible sessions answer here even with no status entry).
    estate, _eobj = session_exists(a.id)
    if estate == "unavailable":
        # API down: the session may still be alive.
        # NEVER answer NEW here (that would fork a duplicate).
        print(f"UNKNOWN (session API unreachable for {a.id}; the session "
              f"may still exist — verify before any Task call, "
              f"do NOT create a duplicate session)");
        return
    if estate == "not-exist":
        # Genuinely gone (deleted, or never existed). Only here is NEW safe.
        # Mark stale but preserve all metadata for minimal-transfer rebuild.
        if meta.get("state") != "stale":
            meta["state"] = "stale"
            save_reg(reg)
        print(f"SESSION_UNAVAILABLE (id {a.id} absent from OpenCode store; "
              f"replacement with minimal transfer allowed; do NOT pass "
              f"this task_id)");
        return
    if meta.get("state") == "stale":
        # Was marked stale, but the session is back/proven live: heal.
        meta["state"] = "reusable"
        save_reg(reg)
    # 2. ACTIVITY via /session/status. Absent entry = IDLE (never nonexistence
    #    — existence is already proven above).
    try:
        st = api("GET", "/session/status") or {}
    except SystemExit:
        print(f"UNKNOWN (activity unverifiable for live session {a.id}; "
              f"WAIT, do NOT duplicate)");
        return
    entry = st.get(a.id)
    if entry is not None:
        etype = entry.get("type", "?") if isinstance(entry, dict) else "?"
        if etype != "idle":
            print(f"WAIT (session status={etype}: previous Task still "
                  f"active — do NOT launch a duplicate Task for this objective; "
                  f"wait for its result or run stuck --threshold 600)");
            return
    # 3. CONTEXT budget. Unreadable history on a PROVEN-LIVE session must
    #    NOT fork a duplicate: proceed resumable with short prompts.
    try:
        used, _ = live_context(a.id)
    except SystemExit as e:
        print(f"RESUME {a.id} (history intact but token accounting "
              f"unreadable: {e}; proceed with short prompts, "
              f"do NOT duplicate){worker_note}");
        return
    limit = a.limit or cached_limit(meta.get("model", ""))
    if not limit:
        print(f"RESUME {a.id} (used_input={used}, model limit unknown; "
              f"history intact — proceed with short prompts, "
              f"do NOT duplicate){worker_note}");
        return
    if 1.0 - used / limit > 0.5:
        print(f"RESUME {a.id} (same objective, remaining={1.0 - used / limit:.1%})"
              f"{worker_note}")
    else:
        print(f"NEW (context pressure, remaining={1.0 - used / limit:.1%})")


def cmd_retire(args):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--delete", action="store_true")
    a = p.parse_args(args)
    reg = load_reg()
    if a.id in reg["sessions"]:
        reg["sessions"][a.id]["state"] = "retired"
        save_reg(reg)
    print(f"retired {a.id}")
    if a.delete:
        api("DELETE", f"/session/{a.id}")
        print(f"deleted {a.id}")


def cmd_delete(args):
    sid = args[0]
    api("DELETE", f"/session/{sid}")
    reg = load_reg()
    reg["sessions"].pop(sid, None)
    save_reg(reg)
    print(f"deleted {sid}")


def cmd_status(args):
    print(json.dumps(api("GET", "/session/status"), indent=1))


def cmd_children(args):
    kids = api("GET", f"/session/{args[0]}/children") or []
    for s in kids:
        print(s.get("id"), "|", s.get("title"))


def cmd_list(args):
    reg = load_reg()
    print(json.dumps(reg["sessions"], indent=1, ensure_ascii=False))


def cmd_version(args):
    print(f"orchestrator-protocol: {ORCHESTRATOR_PROTOCOL}")
    print("task_id rule: Task output task_id == subagent session id. "
          "Register EXACTLY that id; resume via Task task_id=<id>, never "
          "by re-issuing the initial prompt as a fresh Task.")


def cmd_exists(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Authoritative session existence + activity: "
                    "GET /session/{id} (exists?) joined with /session/status "
                    "(idle/busy/retry?). Exit 0 = exists, 2 = does not exist, "
                    "3 = API unavailable.")
    p.add_argument("id")
    a = p.parse_args(args)
    state, _obj = session_exists(a.id)
    if state == "unavailable":
        print("SESSION_API_UNAVAILABLE (cannot reach server; WAIT, "
              "do NOT create a duplicate)");
        raise SystemExit(3)
    if state == "not-exist":
        print(f"SESSION_DOES_NOT_EXIST ({a.id} genuinely absent; "
              f"replacement session allowed)");
        raise SystemExit(2)
    try:
        st = api("GET", "/session/status") or {}
    except SystemExit:
        # Exists (proven above) but activity unknown -> safe side is WAIT.
        print(f"SESSION_EXISTS_IDLE ({a.id} exists; activity unverifiable, "
              f"treat as idle-resumable, do NOT duplicate)");
        return
    entry = st.get(a.id)
    if entry is None:
        # Absent from status = idle, NEVER nonexistence (existence proven).
        print(f"SESSION_EXISTS_IDLE ({a.id} exists, no status entry = idle; "
              f"resume it)");
        return
    etype = entry.get("type", "?") if isinstance(entry, dict) else "?"
    delay = extract_delay_sec(entry) if isinstance(entry, dict) else None
    if etype == "idle":
        print(f"SESSION_EXISTS_IDLE ({a.id} exists and idle; resume it)")
    elif etype in ("busy", "running", "waiting"):
        print(f"SESSION_EXISTS_BUSY ({a.id} active; WAIT, do NOT duplicate; "
              f"stuck check if it outlasts 600s)")
    else:
        d = f" delay={delay:.0f}s" if delay else ""
        print(f"SESSION_EXISTS_RETRYING ({a.id} status={etype}{d}; "
              f"delay>600s -> abort + migrate same task_id, else WAIT)")


def cmd_abort(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Abort a blocked generation on an existing session "
                    "(POST /session/{id}/abort). The session and its history "
                    "survive; the pending attempt is cancelled so the same "
                    "task_id can be resumed on a healthy worker.")
    p.add_argument("id")
    a = p.parse_args(args)
    code, _obj = api_probe("POST", f"/session/{a.id}/abort", {})
    if code is None:
        print(f"ABORT_FAILED ({a.id}: server unreachable; WAIT, retry abort)");
        raise SystemExit(3)
    if code == 404:
        print(f"ABORT_FAILED ({a.id}: session does not exist)");
        raise SystemExit(2)
    print(f"ABORTED ({a.id}: pending attempt cancelled, history preserved; "
          f"resume same task_id now)")
    if not 200 <= code < 300:
        print(f"  (server returned HTTP {code}; verify before resuming)")


def cmd_preflight(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Preflight BEFORE every Task: offline worker/health "
                    "decision, zero API calls. If the primary worker's model "
                    "is in cooldown, the next healthy worker is chosen NOW — "
                    "never launch-then-fail. Exit 0 = worker available, "
                    "2 = all cooling (wait, do NOT launch).")
    p.add_argument("--exclude", default="")
    a = p.parse_args(args)
    excl = [e for e in a.exclude.split(",") if e.strip()]
    workers = worker_pins()
    primary = workers[0] if workers else ("build", "?")
    prem = cooldown_remaining(primary[1])
    if prem > 0:
        print(f"PRIMARY_COOLDOWN {primary[0]} ({primary[1]} retry-in "
              f"{fmt_dur(prem)}): do NOT launch primary")
    else:
        print(f"PRIMARY_READY {primary[0]} ({primary[1]})")
    role, model, wait = resolve_next_worker(excl)
    if role:
        print(f"PREFLIGHT_OK subagent_type={role} model={model}")
    else:
        soon, soon_m = wait if wait else (0, "?")
        print(f"PREFLIGHT_WAIT no healthy worker; earliest {soon_m} in "
              f"{fmt_dur(soon)} — do NOT launch any Task until then")
        raise SystemExit(2)


# ---- Model health memory (2026-09-29 v3; cooldowns with 3h default) ----

def load_health():
    try:
        with open(HEALTH) as f:
            h = json.load(f)
        if isinstance(h, dict) and isinstance(h.get("models"), dict):
            return h
    except (OSError, ValueError):
        pass
    return {"$schema": "model-health v1",
            "defaultCooldownSec": DEFAULT_COOLDOWN_SEC, "models": {}}


def save_health(h):
    with open(HEALTH, "w") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)
        f.write("\n")


def cooldown_remaining(model):
    """Seconds until a dead model may be retried; 0 = healthy/unknown."""
    h = load_health()
    entry = h.get("models", {}).get((model or "").lower())
    if not isinstance(entry, dict):
        return 0
    try:
        return max(0.0, float(entry.get("retryAfter", 0)) - time.time())
    except (TypeError, ValueError):
        return 0


def fmt_dur(sec):
    sec = max(0, int(sec))
    h, sec = divmod(sec, 3600)
    m, s = divmod(sec, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def cmd_health(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Show model cooldown memory (dead models + retry-in).")
    p.add_argument("--format", choices=("text", "json"), default="text")
    a = p.parse_args(args)
    h = load_health()
    rows = []
    for model, e in h.get("models", {}).items():
        rem = cooldown_remaining(model)
        rows.append({"model": model, "reason": (e or {}).get("reason", ""),
                     "state": "COOLDOWN" if rem > 0 else "eligible",
                     "retryInSec": rem})
    if a.format == "json":
        print(json.dumps(rows, indent=1))
    else:
        if not rows:
            print("health: no dead models recorded (all eligible)")
        for r in rows:
            extra = f" retry-in {fmt_dur(r['retryInSec'])}" \
                if r["retryInSec"] > 0 else ""
            print(f"{r['state']} {r['model']}{extra} "
                  f"reason={r['reason'] or '?'}")
        print(f"default-cooldown: {fmt_dur(h.get('defaultCooldownSec', DEFAULT_COOLDOWN_SEC))} "
              f"(used when the provider gave no explicit retry time)")


def cmd_mark_dead(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Record a model as dead for --in seconds "
                    f"(default {DEFAULT_COOLDOWN_SEC} = 3h).")
    p.add_argument("model")
    p.add_argument("--in", dest="cd", type=float, default=0,
                   help="Cooldown seconds (provider retry delay when known, "
                        "else default 3h)")
    p.add_argument("--reason", default="")
    a = p.parse_args(args)
    cd = a.cd if a.cd and a.cd > 0 else DEFAULT_COOLDOWN_SEC
    h = load_health()
    h["models"][a.model.lower()] = {
        "model": a.model, "state": "dead",
        "deadAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "retryAfter": time.time() + cd,
        "cooldownSec": cd, "reason": a.reason or "marked dead",
    }
    save_health(h)
    print(f"marked-dead {a.model} (retry-in {fmt_dur(cd)}) reason={a.reason or '?'}")


def cmd_mark_alive(args):
    m = args[0] if args else ""
    if not m:
        sys.exit("usage: mark-alive <model>")
    h = load_health()
    if h["models"].pop(m.lower(), None) is not None:
        save_health(h)
        print(f"marked-alive {m} (cooldown cleared)")
    else:
        print(f"already-eligible {m} (nothing recorded)")


def worker_pins():
    """[(role, model)] for runtime worker pool: build + build-* pins.

    Parsed DIRECTLY from project opencode.jsonc/json agent.* (never via the
    deduped config_models(): a fallback worker may share its model with
    small_model or another pin and must still be listed). Never hardcoded, so
    a pin edit is picked up without touching this script. Requires one server
    restart to take effect (agents are read at server start, no hot-reload).
    """
    import os as _os
    out = []
    root = _os.path.dirname(BASE)
    for name in ("opencode.jsonc", "opencode.json"):
        cfg = load_jsonc(_os.path.join(root, name))
        if not isinstance(cfg, dict):
            continue
        agents = cfg.get("agent") or {}
        if not isinstance(agents, dict):
            continue
        for role, spec in agents.items():
            if not isinstance(spec, dict):
                continue
            if role != "build" and not role.startswith("build-"):
                continue
            if spec.get("disable"):
                continue
            m = spec.get("model")
            if isinstance(m, str) and "/" in m and (role, m) not in out:
                out.append((role, m))
        break  # project file found; do not merge a second one
    # Stable order: build first, then build-b, build-c, ...
    out.sort(key=lambda rm: (0 if rm[0] == "build" else 1, rm[0]))
    return out


def chain_order_index():
    """{model-lower: order} for chain entries (for worker ranking)."""
    idx = {}
    for e in load_chain():
        w = (e.get("want") or "").lower()
        if w and w not in idx:
            idx[w] = e.get("order", 99)
    return idx


def resolve_next_worker(excluded_models=()):
    """Next healthy worker (role, model): chain order minus cooldown/dead.

    Returns (role, model, earliest_retry) where earliest_retry is None when a
    worker is available, else (None, None, seconds-until-first-eligible).
    """
    excl = {e.strip().lower() for e in excluded_models if e.strip()}
    never = load_never()
    order = chain_order_index()
    cands = []
    for role, model in worker_pins():
        low = model.lower()
        if low in excl or low.split("/", 1)[-1] in excl \
                or is_never(model, never):
            continue
        rem = cooldown_remaining(model)
        if rem > 0:
            continue
        # Primary `build` first when eligible (no gratuitous rotation);
        # fallbacks ranked by chain order.
        cands.append((0 if role == "build" else 1, order.get(low, 50),
                      role, model))
    if cands:
        cands.sort()
        return cands[0][2], cands[0][3], None
    # All workers cooling down: report nearest retry (genuine wait, not silent).
    soonest, soonest_m = None, ""
    for role, model in worker_pins():
        rem = cooldown_remaining(model)
        if rem > 0 and (soonest is None or rem < soonest):
            soonest, soonest_m = rem, model
    return None, None, (soonest, soonest_m)


# ---- Failure taxonomy (2026-09-30 v5; SESSION != MODEL) ----
#
# MODEL_* = execution backend failed, session usually intact -> same-session
#   failover (resume task_id on another worker). PROJECT_ERROR = our code is
#   wrong -> fix code, NO model rotation. SESSION_ERROR = the conversation
#   itself is gone -> replacement session with minimal state transfer.
#   NETWORK_ERROR = connectivity, not model death -> same session, NO cooldown.
#   CONTEXT_EXHAUSTED = session too full -> replacement session (session-level).
# Order matters: specific session/context/auth first, then network/timeout,
# then rate/quota/provider, agent-platform, project fallback last.

CONTEXT_PATTERNS = [
    r"context.+(length|limit|exceed|too.?long|full|exhausted|window)",
    r"token.+(limit|exceed|too many|maximum)",
    r"max(imum)?.+tokens",
]
SESSION_PATTERNS = [
    r"no such session", r"session (not found|expired|deleted|missing|invalid)",
    r"unknown session", r"session.+does not exist",
]
AUTH_PATTERNS = [
    r"\b401\b", r"\b403\b", r"unauthorized", r"unauthenticated",
    r"invalid.+(api.?key|credential|token)", r"missing.+(api.?key|credential)",
    r"forbidden", r"/connect", r"sign.?in",
]
NETWORK_PATTERNS = [
    r"network.?error", r"network.?unavailable", r"socket hang up",
    r"ECONNRESET", r"ECONNREFUSED", r"ECONNABORTED", r"EAI_AGAIN",
    r"ENOTFOUND", r"ETIMEDOUT", r"EPIPE", r"ENETUNREACH", r"EHOSTUNREACH",
    r"connection (reset|refused|aborted|lost|failed|closed)",
    r"fetch failed", r"failed to fetch", r"offline", r"dns",
    r"TLS.+error", r"SSL.+error", r"certificate",
]
TIMEOUT_PATTERNS = [
    r"generation (timed out|timeout|stalled)",
    r"request timed out", r"deadline exceeded",
    r"timed out after", r"generation timeout",
    r"timeout exceeded", r"idle timeout", r"upstream.+timeout",
    r"504",
]
RATE_PATTERNS = [
    r"\b429\b", r"rate.?limit", r"too many requests",
    r"throttl", r"retry later", r"try again later",
]
FREE_USAGE_PATTERNS = [
    r"free usage exceeded", r"free tier.+(exceed|exhausted|depleted)",
    r"usage exceeded.+free", r"free.+quota.+exceed",
]
QUOTA_PATTERNS = [
    r"quota", r"usage.?limit", r"limit.?exceeded",
    r"resource.?exhausted", r"capacity",
    r"over.?loaded", r"payment required", r"\b402\b", r"billing",
    r"insufficient.+(quota|credit|balance)", r"credit.+(exhausted|expired|depleted)",
]
PROVIDER_PATTERNS = [
    r"provider (error|unavailable|failed|overloaded)",
    r"model (unavailable|not available|failed)",
    r"bad gateway", r"\b502\b", r"service unavailable", r"\b503\b",
    r"internal server error", r"\b500\b",
    r"upstream (error|overloaded|unavailable|failed)",
    r"service temporarily (overloaded|unavailable)",
]
AGENT_PATTERNS = [
    r"subagent depth limit", r"depth limit reached",
    r"unknown agent type", r"agent (crashed|failed|errored)",
    r"tool execution aborted",
]

# verdict -> (exit code, records model dead?, recovery)
VERDICTS = {
    "MODEL_QUOTA": (10, True, "failover: same session, another worker"),
    "MODEL_RATE_LIMIT": (11, True, "failover: same session, another worker"),
    "FREE_USAGE_EXHAUSTED": (18, True, "failover: same session, another worker"),
    "CONTEXT_EXHAUSTED": (12, False, "session-level: replacement session, minimal transfer"),
    "MODEL_TIMEOUT": (13, True, "failover: same session, another worker"),
    "PROVIDER_ERROR": (14, True, "failover: same session, another worker"),
    "NETWORK_ERROR": (15, False, "recoverable: same session, same worker when back"),
    "SESSION_ERROR": (16, False, "replacement session, minimal transfer"),
    "AGENT_ERROR": (17, False, "fix platform/config, then same session if live"),
    "PROJECT_ERROR": (20, False, "fix code, NO model rotation"),
    "AUTH_ERROR": (40, False, "connect provider, not a blocker"),
    "UNKNOWN": (30, False, "re-ping once, then decide by evidence"),
}


def classify_text(text):
    low = text or ""
    low = low.lower()
    for pat in CONTEXT_PATTERNS:
        if re.search(pat, low):
            return "CONTEXT_EXHAUSTED", pat
    for pat in SESSION_PATTERNS:
        if re.search(pat, low):
            return "SESSION_ERROR", pat
    for pat in AUTH_PATTERNS:
        if re.search(pat, low):
            return "AUTH_ERROR", pat
    for pat in NETWORK_PATTERNS:
        if re.search(pat, low):
            return "NETWORK_ERROR", pat
    for pat in TIMEOUT_PATTERNS:
        if re.search(pat, low):
            return "MODEL_TIMEOUT", pat
    for pat in RATE_PATTERNS:
        if re.search(pat, low):
            return "MODEL_RATE_LIMIT", pat
    for pat in FREE_USAGE_PATTERNS:
        if re.search(pat, low):
            return "FREE_USAGE_EXHAUSTED", pat
    for pat in QUOTA_PATTERNS:
        if re.search(pat, low):
            return "MODEL_QUOTA", pat
    for pat in PROVIDER_PATTERNS:
        if re.search(pat, low):
            return "PROVIDER_ERROR", pat
    for pat in AGENT_PATTERNS:
        if re.search(pat, low):
            return "AGENT_ERROR", pat
    if not (text or "").strip():
        return "UNKNOWN", "empty error text"
    return "PROJECT_ERROR", "no model/session failure signal"


def cmd_classify_error(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Classify a Task/agent error into the failure taxonomy "
                    "(SESSION != MODEL). MODEL_* -> same-session failover; "
                    "PROJECT_ERROR -> fix code, no rotation.")
    p.add_argument("text", nargs="*", help="Error text (else read stdin)")
    p.add_argument("--record-model", default="",
                   help="Model to record dead on MODEL_* verdicts "
                        "(cooldown --cooldown, default 3h)")
    p.add_argument("--cooldown", type=float, default=0,
                   help="Cooldown seconds for --record-model "
                        "(provider retry delay when known, else 3h)")
    a = p.parse_args(args)
    text = " ".join(a.text) if a.text else sys.stdin.read()
    verdict, matched = classify_text(text)
    code, recordable, recovery = VERDICTS[verdict]
    print(f"{verdict} (matched: {matched}) recovery={recovery}")
    if a.record_model and recordable:
        cd = a.cooldown if a.cooldown and a.cooldown > 0 else DEFAULT_COOLDOWN_SEC
        h = load_health()
        h["models"][a.record_model.lower()] = {
            "model": a.record_model, "state": "dead",
            "deadAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "retryAfter": time.time() + cd,
            "cooldownSec": cd,
            "reason": f"{verdict} ({matched})",
        }
        save_health(h)
        print(f"marked-dead {a.record_model} "
              f"(retry-in {fmt_dur(cd)})")
    raise SystemExit(code)


def strip_jsonc(s):
    out, i, n = [], 0, len(s)
    in_str, esc = False, False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def load_jsonc(path):
    try:
        with open(path) as f:
            raw = f.read()
    except OSError:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        try:
            return json.loads(strip_jsonc(raw))
        except ValueError:
            return None


def load_chain():
    cfg = load_jsonc(CHAIN)
    if isinstance(cfg, dict) and isinstance(cfg.get("chain"), list):
        return [e for e in cfg["chain"]
                if isinstance(e, dict) and e.get("match")]
    return []


def config_models():
    """Model pins from live config files (never hardcoded). [(model, source)]."""
    root = os.path.dirname(BASE)
    found = []
    for path, tag in [
            (os.path.join(root, "opencode.jsonc"), "project:opencode.jsonc"),
            (os.path.join(root, "opencode.json"), "project:opencode.json"),
            (os.path.expanduser("~/.config/opencode/opencode.jsonc"),
             "global:opencode.jsonc"),
            (os.path.expanduser("~/.config/opencode/opencode.json"),
             "global:opencode.json")]:
        cfg = load_jsonc(path)
        if not isinstance(cfg, dict):
            continue
        for key in ("model", "small_model"):
            m = cfg.get(key)
            if isinstance(m, str) and "/" in m \
                    and m not in [x[0] for x in found]:
                found.append((m, f"{tag}:{key}"))
        agents = cfg.get("agent") or {}
        if isinstance(agents, dict):
            for role, spec in agents.items():
                if isinstance(spec, dict):
                    m = spec.get("model")
                    if isinstance(m, str) and "/" in m \
                            and m not in [x[0] for x in found]:
                        found.append((m, f"{tag}:agent.{role}"))
    orch = os.path.join(root, ".opencode", "agents", "orchestrator.md")
    try:
        with open(orch) as f:
            head = f.read(2000)
    except OSError:
        head = ""
    m = re.search(r"^model:\s*(\S+)", head, re.M)
    if m and "/" in m.group(1) and m.group(1) not in [x[0] for x in found]:
        found.append((m.group(1), "orchestrator.md frontmatter"))
    return found


def live_provider_models():
    """[(provider, model)] from live GET /provider; None when unreachable."""
    import base64
    user, pwd = server_user(), server_pass()
    req = urllib.request.Request(
        f"http://{server_host()}:{server_port()}/provider",
        headers={"Authorization": "Basic " + base64.b64encode(
            f"{user}:{pwd}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            provs = json.loads(r.read().decode() or "null")
    except Exception:
        return None
    out = []
    items = provs.get("all", []) if isinstance(provs, dict) else []
    for p in items:
        pid = p.get("id", "")
        models = p.get("models", {})
        if isinstance(models, dict):
            for mid in models:
                out.append((pid, mid))
        elif isinstance(models, list):
            for m in models:
                mid = m.get("id") if isinstance(m, dict) else m
                if mid:
                    out.append((pid, mid))
    return out


def registry_models():
    try:
        reg = load_reg()
    except (OSError, ValueError):
        return []
    ms = []
    for _sid, meta in reg.get("sessions", {}).items():
        m = (meta or {}).get("model", "")
        if m and "/" in m and m not in ms:
            ms.append(m)
    return ms


def load_never():
    """Substrings (lowercase) that must never run as Task workers."""
    cfg = load_jsonc(CHAIN)
    if isinstance(cfg, dict) and isinstance(cfg.get("never"), list):
        return [str(x).lower() for x in cfg["never"] if x]
    return []


def is_never(full, never):
    low = full.lower()
    return any(n and n in low for n in never)


def cmd_models(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Resolve model fallback candidates: user chain "
                    "(.opencode/model-fallback.json) matched live against "
                    "GET /provider. CHAIN-ONLY by default; --all adds config "
                    "pins, registry last-good and remaining live models. "
                    "The chain 'never' list is always excluded.")
    p.add_argument("--exclude", default="",
                   help="Comma-separated exhausted models to skip "
                        "(full provider/model or bare id)")
    p.add_argument("--all", action="store_true",
                   help="Include ambient sources (config pins, registry, "
                        "rest of live). Default: chain entries only.")
    p.add_argument("--ignore-cooldown", action="store_true",
                   help="Include models currently in cooldown "
                        "(default: auto-excluded from next-available)")
    p.add_argument("--format", choices=("text", "json"), default="text")
    a = p.parse_args(args)
    excluded = {e.strip().lower() for e in a.exclude.split(",") if e.strip()}
    never = load_never()

    def is_excluded(full):
        low = full.lower()
        return low in excluded or low.split("/", 1)[-1] in excluded \
            or is_never(full, never)

    ordered, seen = [], set()

    def add(full, source):
        if full not in seen:
            seen.add(full)
            ordered.append((full, source, is_excluded(full),
                            cooldown_remaining(full)))

    live = live_provider_models()
    if live is None:
        print("warning: server /provider unreachable, "
              "using chain want-ids + config + registry only",
              file=sys.stderr)
        live_index = {}
    else:
        live_index = {}
        for pid, mid in live:
            live_index.setdefault((pid, mid.lower()), f"{pid}/{mid}")

    for entry in sorted(load_chain(), key=lambda e: e.get("order", 99)):
        prov = (entry.get("provider") or "").lower()
        match = (entry.get("match") or "").lower()
        want = entry.get("want") or ""
        resolved = ""
        if live is not None:
            for (pid, mid_low), full in sorted(live_index.items()):
                if prov and pid.lower() != prov:
                    continue
                if match and match in mid_low:
                    resolved = full
                    if want and full.lower() == want.lower():
                        break
            if not resolved and want:
                wl = want.lower()
                for (_pid, _mid), full in sorted(live_index.items()):
                    if full.lower() == wl:
                        resolved = full
                        break
        add(resolved or want,
            f"fallback-chain:{entry.get('order', '?')}"
            f"{' (unverified, server unreachable)' if not resolved else ''}")
    if a.all:
        for m, src in config_models():
            add(m, src)
        for m in registry_models():
            add(m, "registry:last-good")
        if live is not None:
            for _key, full in sorted(live_index.items()):
                add(full, "live:/provider")
    elif live is None:
        pass  # chain want-ids already added above; nothing ambient offline
    if a.format == "json":
        print(json.dumps(
            [{"model": m, "source": s, "excluded": e,
              "cooldownSec": c}
             for m, s, e, c in ordered], indent=1))
    else:
        for m, s, e, c in ordered:
            tag = ""
            if e:
                tag = ("  [FORBIDDEN-never-list]" if is_never(m, never)
                       else "  [EXHAUSTED-skip]")
            elif c > 0 and not a.ignore_cooldown:
                tag = f"  [COOLDOWN retry-in {fmt_dur(c)}]"
            print(f"{m}  source={s}" + tag)
        workers = worker_pins()
        # Runtime worker pool: rotation = subagent_type switch on the SAME
        # session, no restart, no config paste (SESSION != MODEL). The legacy
        # pin-rotation (sed + restart) is retired and not printed anymore.
        excl = [e for e in a.exclude.split(",") if e.strip()]
        role, model, wait = resolve_next_worker(excl)
        if role:
            print(f"next-worker: {role} ({model}) — NO server restart needed "
                  f"(Task subagent_type={role} on the SAME task_id)")
        else:
            soon, soon_m = wait if wait else (0, "?")
            print(f"next-worker: NONE (all workers in cooldown, "
                  f"earliest {soon_m} in {fmt_dur(soon)})")
        return


# ---- Stuck-task watchdog + failover (2026-09-29; threshold default 600s) ----

STUCK_THRESHOLD_SEC = 600

DELAY_TEXT_PATTERNS = [
    # "agent unavailable ... 8800 seconds", "retry in 8800s", "retry after 600 sec"
    (re.compile(r"(\d[\d,]*)\s*(?:seconds?|secs?|s)\b", re.I), 1.0),
    (re.compile(r"(\d[\d,]*)\s*(?:minutes?|mins?|m)\b", re.I), 60.0),
    (re.compile(r"(\d[\d,]*)\s*(?:hours?|hrs?|h)\b", re.I), 3600.0),
]


def _num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def extract_delay_sec(entry):
    """Best-effort retry/unavailable delay in seconds from a status entry.

    Handles every shape observed or plausible from GET /session/status
    (flat int/str fields, nested dicts, ms timestamps, free-form error
    text like "agent unavailable for 8800 seconds"). Returns float or None.
    Pure function — unit-testable without a live server.
    """
    if entry is None:
        return None
    if isinstance(entry, (int, float)):
        v = float(entry)
        return v if v > 0 else None
    if isinstance(entry, str):
        return extract_delay_sec({"error": entry})
    if not isinstance(entry, dict):
        return None
    # 1. Explicit second-fields (most reliable). `next` included: the
    # 1.18.32 retry status is {type:retry, attempt, message, next}; `next`
    # is a seconds delay when small, an epoch when large (branch 3 sorts
    # out magnitudes — values >= 1e6 are skipped here, never misread).
    for key in ("delaySec", "delay_sec", "retryAfterSec", "retry_after_sec",
                "retryAfter", "retry_after", "retryInSec", "retry_in_sec",
                "retryIn", "retry_in", "unavailableSec", "unavailable_sec",
                "waitSec", "wait_sec", "backoffSec", "backoff_sec",
                "seconds", "secs", "delay", "wait", "next"):
        if key in entry:
            v = _num(entry[key])
            if v is not None and v > 0:
                # Heuristic: values > 1e6 are ms-epoch, not delays; skip here.
                if v < 1000000:
                    return float(v)
    # 2. Millisecond fields.
    for key in ("retryAfterMs", "retry_after_ms", "nextRetryMs",
                "next_retry_ms", "retryInMs", "retry_in_ms", "delayMs",
                "delay_ms", "waitMs", "wait_ms", "backoffMs", "backoff_ms"):
        if key in entry:
            v = _num(entry[key])
            if v is not None and v > 0 and v < 1000000000000:
                return float(v) / 1000.0
    # 3. Absolute timestamps (ms or s epoch): delay = ts - now.
    now_ms = time.time() * 1000.0
    for key in ("nextRetry", "next_retry", "retryAt", "retry_at",
                "retryTime", "retry_time", "availableAt", "available_at",
                "nextAttempt", "next_attempt", "resetAt", "reset_at",
                "next"):
        if key in entry:
            v = _num(entry[key])
            if v is not None and v > 0:
                ts_ms = v * 1000.0 if v < 10000000000 else v  # s vs ms epoch
                d = (ts_ms - now_ms) / 1000.0
                if d > 0:
                    return float(d)
    # 4. Nested dicts (one level): {"retry": {"afterSec": 8800}, ...}.
    for key in ("retry", "status", "error", "detail", "details", "info"):
        sub = entry.get(key)
        if isinstance(sub, dict):
            d = extract_delay_sec(sub)
            if d is not None:
                return d
    # 5. Free-form text: scan error/message/type strings for N seconds.
    texts = []
    for key in ("error", "message", "reason", "type", "statusText",
                "status_text", "description", "title"):
        v = entry.get(key)
        if isinstance(v, str) and v.strip():
            texts.append(v)
    # Also scan the whole JSON dump as a last resort (catches unknown keys).
    blob = " ".join(texts)
    if not blob:
        try:
            blob = json.dumps(entry)[:2000]
        except (TypeError, ValueError):
            blob = ""
    best = None
    low = blob.lower()
    # Only trust time-like numbers when the text actually talks about
    # waiting/retry/unavailability — avoids mistaking attempt counts.
    if any(w in low for w in ("retry", "unavailable", "available in",
                              "wait", "backoff", "rate", "quota", "limit",
                              "try again", "seconds", "minutes", "hours")):
        for pat, mult in DELAY_TEXT_PATTERNS:
            for m in pat.finditer(blob):
                v = _num(m.group(1))
                if v is not None and v > 0:
                    cand = v * mult
                    # Ignore epoch-looking numbers; keep plausible backoffs.
                    if 1 <= cand <= 7 * 24 * 3600:
                        best = cand if best is None else max(best, cand)
    return best


def _busy_age_sec(meta):
    """Seconds since registry lastUsed (None when unparseable)."""
    try:
        ts = datetime.fromisoformat(str(meta.get("lastUsed", "")).replace(
            "Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
    except (ValueError, TypeError):
        return None


def cmd_stuck(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Stuck-task watchdog: list non-idle sessions whose "
                    "retry/unavailable delay exceeds --threshold seconds "
                    f"(default {STUCK_THRESHOLD_SEC}). Exit 0 when clean, "
                    "exit 2 when at least one STUCK session exists.")
    p.add_argument("--threshold", type=float, default=STUCK_THRESHOLD_SEC,
                   help="Delay in seconds above which a busy/retry session "
                        "counts as STUCK (default 600 = 10 min)")
    p.add_argument("--format", choices=("text", "json"), default="text")
    a = p.parse_args(args)
    try:
        st = api("GET", "/session/status") or {}
    except SystemExit as e:
        print(f"status unreachable: {e}")
        raise SystemExit(3)
    reg = {}
    try:
        reg = load_reg().get("sessions", {})
    except (OSError, ValueError):
        pass
    rows = []
    # Check sessions from status (including orphans not in registry)
    for sid, entry in (st.items() if isinstance(st, dict) else []):
        etype = entry.get("type", "?") if isinstance(entry, dict) else "?"
        if etype == "idle":
            continue
        delay = extract_delay_sec(entry) if isinstance(entry, dict) else None
        meta = reg.get(sid, {})
        age = _busy_age_sec(meta) if meta else None
        # Also check time.updated from status entry for orphans
        if age is None and isinstance(entry, dict):
            updated = entry.get("timeUpdated") or entry.get("updated")
            if updated:
                try:
                    ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                    age = max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
                except (ValueError, TypeError):
                    pass
        stuck = (delay is not None and delay > a.threshold) or \
                (delay is None and age is not None and age > a.threshold
                 and etype in ("busy", "retry", "running", "waiting"))
        rows.append({"session": sid, "status": etype,
                     "delaySec": delay, "busyAgeSec": age,
                     "objective": meta.get("objective", ""),
                     "verdict": "STUCK" if stuck else "WAIT"})
    # Also check registry sessions that might be stuck but not in status (orphans)
    for sid, meta in reg.items():
        if sid in st:
            continue
        age = _busy_age_sec(meta) if meta else None
        if age is not None and age > a.threshold:
            rows.append({"session": sid, "status": "orphan",
                         "delaySec": None, "busyAgeSec": age,
                         "objective": meta.get("objective", ""),
                         "verdict": "STUCK"})
    stuck_rows = [r for r in rows if r["verdict"] == "STUCK"]
    if a.format == "json":
        print(json.dumps({"threshold": a.threshold, "sessions": rows,
                          "stuck": len(stuck_rows)}, indent=1))
    else:
        if not rows:
            print(f"OK (all sessions idle, threshold={a.threshold:g}s)")
        for r in rows:
            d = f"{r['delaySec']:.0f}s" if r["delaySec"] is not None else "?"
            age = f"{r['busyAgeSec']:.0f}s" if r["busyAgeSec"] is not None else "?"
            print(f"{r['verdict']} {r['session']} status={r['status']} "
                  f"delay={d} busyAge={age} objective={r['objective'] or '?'}")
            if r["verdict"] == "STUCK":
                obj = r['objective'] or '<OBJECTIVE>'
                print(f"  -> migrate: scripts/session-reuse.py migrate "
                      f"{r['session']} --objective \"{obj}\"")
        if stuck_rows and not rows == stuck_rows:
            pass
    raise SystemExit(2 if stuck_rows else 0)


def cmd_migrate(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Same-session model migration (SESSION != MODEL): keep the "
                    "existing child task_id, record the dead model in cooldown "
                    "memory (provider delay when known, else 3h default), and "
                    "print a Task block that resumes the SAME session on the "
                    "next healthy worker. No replacement session, no prompt "
                    "replay. Never deletes transcripts.")
    p.add_argument("id")
    p.add_argument("--objective", default="",
                   help="Objective text (defaults to the registry record; "
                        "only required for untracked sessions)")
    p.add_argument("--task", default="")
    p.add_argument("--exclude", default="",
                   help="Comma-separated exhausted models to skip")
    p.add_argument("--delay", type=float, default=0,
                   help="Observed retry/unavailable delay in seconds "
                        "(used as the dead-model cooldown; default: 3h)")
    p.add_argument("--threshold", type=float, default=STUCK_THRESHOLD_SEC)
    a = p.parse_args(args)
    reg = load_reg()
    meta = reg["sessions"].get(a.id, {})
    task = a.task or meta.get("task", "<TASK>")
    objective = a.objective or meta.get("objective", "")
    old_model = meta.get("model", "")
    old_worker = meta.get("agent", "build")
    excluded = [e for e in a.exclude.split(",") if e.strip()]
    # If no model in registry, try to learn from message tail (bounded fetch)
    if not old_model:
        pid, mid = session_tail_model(a.id)
        if mid and pid:
            old_model = f"{pid}/{mid}"
            meta["model"] = old_model
    if old_model:
        excluded.append(old_model)
    # 1. Cooldown memory: explicit --delay wins; else a fresh watchdog
    # abort record on this session; else 3h default.
    cd = 0
    if a.delay and a.delay > 0:
        cd = a.delay
    else:
        try:
            abort_rec = (meta.get("lastAbort") or {})
            cd = float(abort_rec.get("delaySec") or 0)
        except (TypeError, ValueError):
            cd = 0
    if not cd or cd <= 0:
        cd = DEFAULT_COOLDOWN_SEC
    if old_model:
        h = load_health()
        h["models"][old_model.lower()] = {
            "model": old_model, "state": "dead",
            "deadAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "retryAfter": time.time() + cd,
            "cooldownSec": cd,
            "reason": f"migrated from {a.id} delay>{a.threshold:g}s",
        }
        save_health(h)
    # 2. Runtime rotation that PRESERVES the session: the next Task reuses
    # this task_id with a different subagent_type (per-prompt model).
    role, model, wait = resolve_next_worker(excluded)
    if not role:
        soon, soon_m = wait if wait else (0, "?")
        print(f"paused {a.id} (no healthy worker; session preserved, "
              f"retry {soon_m} in {fmt_dur(soon)})")
        print("genuine wait: do NOT spin fresh Tasks until then; report and wait.")
        return
    reg["sessions"][a.id] = {
        "agent": role, "objective": objective, "task": task,
        "model": model,
        "oid": meta.get("oid", ""),
        "state": "reusable",
        "lastUsed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lastResult": (meta.get("lastResult", "") or "") +
                      f" [MIGRATED {old_worker}/{old_model} -> {role}/{model}]",
        "failure": meta.get("failure", ""),
        "migratedFrom": {"worker": old_worker, "model": old_model,
                         "at": datetime.now(timezone.utc).isoformat(
                             timespec="seconds")},
    }
    save_reg(reg)
    print(f"migrated {a.id}: session preserved, backend "
          f"{old_worker}/{old_model or '?'} -> {role}/{model} "
          f"(dead-model cooldown {fmt_dur(cd)})")
    print("--- Task call (SAME session, different worker; history preserved) ---")
    print(f"subagent_type={role}")
    print(f"task_id={a.id}")
    print("prompt: Continue the existing Objective from the current session "
          "state. Inspect the current repository state and proceed from where "
          "the previous generation stopped. Do not restart the task from scratch. "
          "Do not invoke subagents, do the work directly.")


CMDS = {"register": cmd_register, "context": cmd_context, "decide": cmd_decide,
        "retire": cmd_retire, "delete": cmd_delete, "status": cmd_status,
        "children": cmd_children, "list": cmd_list, "version": cmd_version,
        "exists": cmd_exists, "abort": cmd_abort, "preflight": cmd_preflight,
        "health": cmd_health, "mark-dead": cmd_mark_dead,
        "mark-alive": cmd_mark_alive,
        "find-objective": cmd_find_objective,
        "link-objective": cmd_link_objective,
        "stalled": cmd_stalled,
        "stuck": cmd_stuck, "migrate": cmd_migrate,
        "models": cmd_models, "classify-error": cmd_classify_error}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(f"usage: {sys.argv[0]} {{{'|'.join(CMDS)}}}")
    CMDS[sys.argv[1]](sys.argv[2:])
