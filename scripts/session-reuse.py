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
  version                   print orchestrator protocol version (v3 required
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
                            pause a STUCK task and continue the SAME task on
                            the next HEALTHY worker (runtime subagent_type
                            switch, no restart). Records the dead model with
                            cooldown = delay when known, else 3h default.
  models [--exclude M,...] [--all] [--ignore-cooldown] [--format text|json]
                            ordered fallback candidates, CHAIN-ONLY by default
                            (user chain matched live vs GET /provider).
                            --all adds config pins, registry last-good,
                            remaining live models. Chain 'never' list is
                            always excluded. No hardcoding.
  classify-error [TEXT...]  QUOTA_EXHAUSTED(10)/CONTEXT_EXHAUSTED(12) vs
                            AUTH_ERROR(40, connect provider) vs
                            ORDINARY_ERROR(20)/UNKNOWN(30). Only 10/12 trigger
                            model fallback (reads stdin when no args).

Reuse rule: same agent role (`build`) + same objective + coherent + >50% context remaining.
Objective boundary: Calendar -> Calendar refinement = SAME session;
Calendar -> Disk Utility = NEW session. Never resume on context pressure,
error state, or role/objective change.

Model fallback (2026-09-26): a QUOTA/CONTEXT Task failure is never a project
blocker. Resolve next model via `models --exclude <dead,...>`, ping it with a
trivial Task, continue the SAME objective there (RESUME if `decide` allows,
else NEW session carrying prior result + remaining gaps). Chain order lives in
.opencode/model-fallback.json, never in this script.

Stuck-task failover (2026-09-29): a provider retry/unavailable backoff longer
than STUCK_THRESHOLD_SEC (default 600 = 10 min, e.g. the observed 8800s
"agent unavailable" hang) is never waited out. The task is paused in the
registry (state=paused-stuck, same objective+task preserved) and continued
on the next chain model: `stuck` detects, `migrate` pauses + prints the
rotate one-liner + continuation prompt for the SAME task.
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
REG = os.path.join(BASE, "..", ".opencode", "sessions", "registry.json")
CHAIN = os.path.join(BASE, "..", ".opencode", "model-fallback.json")

# Orchestrator protocol version. The orchestrator prompt requires THIS version:
# if `version` prints anything older (or the subcommand is unknown = stale
# agent file cached by a long-lived server), the orchestrator must report
# STALE-AGENT and stop instead of silently running the old loop.
ORCHESTRATOR_PROTOCOL = 4

# Cooldown memory for dead models (.opencode/sessions/model-health.json).
# A model observed dead (provider retry/unavailable > stuck threshold, or
# QUOTA/CONTEXT Task failure) is skipped for COOLDOWN_SEC unless the provider
# gave an explicit retry delay (then that delay is used). Default 3h per user
# spec when no explicit time is known; after expiry the model is retried.
HEALTH = os.path.join(BASE, "..", ".opencode", "sessions", "model-health.json")
DEFAULT_COOLDOWN_SEC = 10800

HOST = os.environ.get("OPENCODE_SERVER_HOST", "localhost")
PORT = os.environ.get("OPENCODE_SERVER_PORT", "4096")
USER = os.environ.get("OPENCODE_SERVER_USERNAME", "opencode")
PASS = os.environ.get("OPENCODE_SERVER_PASSWORD", "")


def api(method, path, body=None):
    import base64
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": "Basic " + base64.b64encode(
                     f"{USER}:{PASS}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        sys.exit(f"API {method} {path} -> HTTP {e.code}: {e.read().decode()[:200]}")


def load_reg():
    with open(REG) as f:
        return json.load(f)


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
    a = p.parse_args(args)
    reg = load_reg()
    reg["sessions"][a.id] = {
        "agent": a.agent, "objective": a.objective, "task": a.task,
        "model": a.model, "state": "reusable",
        "lastUsed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lastResult": "",
    }
    save_reg(reg)
    print(f"registered {a.id} ({a.agent}/{a.objective})")


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
    used, _ = live_context(a.id)
    limit = a.limit or model_limit(model)
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
    if a.objective != meta.get("objective"):
        print(f"NEW (objective boundary: {meta.get('objective')} -> {a.objective})");
        return
    if a.agent and a.agent != meta.get("agent"):
        print(f"NEW (role change: {meta.get('agent')} -> {a.agent})");
        return
    try:
        st = api("GET", "/session/status") or {}
        s = st.get(a.id, {"type": "idle"})
        if s.get("type") != "idle":
            print(f"WAIT (session status={s.get('type')}: previous Task still "
                  f"active — do NOT launch a duplicate Task for this objective; "
                  f"wait for its result or run stuck --threshold 600)");
            return
    except SystemExit as e:
        print(f"NEW (status unreachable: {e})");
        return
    used, _ = live_context(a.id)
    limit = a.limit or model_limit(meta.get("model", ""))
    if not limit:
        print(f"NEW (context unverifiable, used_input={used})");
        return
    if 1.0 - used / limit > 0.5:
        print(f"RESUME {a.id} (same objective, remaining={1.0 - used / limit:.1%})")
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


# ---- Model fallback helpers (2026-09-26; chain lives in CHAIN file) ----

QUOTA_PATTERNS = [
    r"429", r"rate.?limit", r"quota", r"usage.?limit", r"limit.?exceeded",
    r"too many requests", r"resource.?exhausted", r"capacity",
    r"over.?loaded", r"try again later", r"retry later",
    r"payment required", r"\b402\b", r"billing",
    r"insufficient.+(quota|credit|balance)", r"credit.+(exhausted|expired|depleted)",
    r"throttl", r"throughput",
]
CONTEXT_PATTERNS = [
    r"context.+(length|limit|exceed|too.?long|full|exhausted|window)",
    r"token.+(limit|exceed|too many|maximum)",
    r"max(imum)?.+tokens",
]
AUTH_PATTERNS = [
    r"\b401\b", r"\b403\b", r"unauthorized", r"unauthenticated",
    r"invalid.+(api.?key|credential|token)", r"missing.+(api.?key|credential)",
    r"forbidden", r"/connect", r"sign.?in",
]


def classify_text(text):
    low = text or ""
    low = low.lower()
    for pat in CONTEXT_PATTERNS:
        if re.search(pat, low):
            return "CONTEXT_EXHAUSTED", pat
    for pat in AUTH_PATTERNS:
        if re.search(pat, low):
            return "AUTH_ERROR", pat
    for pat in QUOTA_PATTERNS:
        if re.search(pat, low):
            return "QUOTA_EXHAUSTED", pat
    if not (text or "").strip():
        return "UNKNOWN", "empty error text"
    return "ORDINARY_ERROR", "no quota/rate-limit signal"


def cmd_classify_error(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Classify a Task/agent error: quota/rate-limit (fallback) "
                    "vs ordinary project error (no fallback).")
    p.add_argument("text", nargs="*", help="Error text (else read stdin)")
    p.add_argument("--record-model", default="",
                   help="When given WITH a QUOTA/CONTEXT verdict, record this "
                        "model as dead (3h cooldown) in health memory")
    a = p.parse_args(args)
    text = " ".join(a.text) if a.text else sys.stdin.read()
    verdict, matched = classify_text(text)
    print(f"{verdict} (matched: {matched})")
    if a.record_model and verdict in ("QUOTA_EXHAUSTED", "CONTEXT_EXHAUSTED"):
        h = load_health()
        h["models"][a.record_model.lower()] = {
            "model": a.record_model, "state": "dead",
            "deadAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "retryAfter": time.time() + DEFAULT_COOLDOWN_SEC,
            "cooldownSec": DEFAULT_COOLDOWN_SEC,
            "reason": f"{verdict} ({matched})",
        }
        save_health(h)
        print(f"marked-dead {a.record_model} "
              f"(retry-in {fmt_dur(DEFAULT_COOLDOWN_SEC)})")
    raise SystemExit({"QUOTA_EXHAUSTED": 10, "CONTEXT_EXHAUSTED": 12,
                      "AUTH_ERROR": 40,
                      "UNKNOWN": 30}.get(verdict, 20))


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
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/provider",
        headers={"Authorization": "Basic " + base64.b64encode(
            f"{USER}:{PASS}".encode()).decode()})
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
        avail = [m for m, _s, e, c in ordered
                 if not e and (a.ignore_cooldown or c <= 0)]
        workers = worker_pins()
        if workers and not a.all:
            # Runtime worker pool: rotation = subagent_type switch, no restart.
            excl = [e for e in a.exclude.split(",") if e.strip()]
            role, model, wait = resolve_next_worker(excl)
            if role:
                print(f"next-worker: {role} ({model}) — NO server restart needed "
                      f"(Task subagent_type={role})")
            else:
                soon, soon_m = wait if wait else (0, "?")
                print(f"next-worker: NONE (all workers in cooldown, "
                      f"earliest {soon_m} in {fmt_dur(soon)})")
            return
        pins = [m for _r, m in workers] or \
               [m for m, s in config_models()
                if s.startswith("project:") and s.endswith("agent.build")]
        if avail:
            if pins and not is_excluded(pins[0]) \
                    and pins[0].lower() in [m.lower() for m in avail]:
                print(f"next-available: {pins[0]} "
                      "(current build pin, alive — no rotation)")
            else:
                print(f"next-available: {avail[0]}")
                if pins and pins[0].lower() != avail[0].lower():
                    print(f"rotate: sed -i 's#\"model\": \"{pins[0]}\""
                          f"#\"model\": \"{avail[0]}\"#' opencode.jsonc"
                          "  # then restart server (no hot-reload)")
        else:
            print("next-available: NONE (all candidates exhausted)")


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
    # 1. Explicit second-fields (most reliable).
    for key in ("delaySec", "delay_sec", "retryAfterSec", "retry_after_sec",
                "retryAfter", "retry_after", "retryInSec", "retry_in_sec",
                "retryIn", "retry_in", "unavailableSec", "unavailable_sec",
                "waitSec", "wait_sec", "backoffSec", "backoff_sec",
                "seconds", "secs", "delay", "wait"):
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
                "nextAttempt", "next_attempt", "resetAt", "reset_at"):
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
    for sid, entry in (st.items() if isinstance(st, dict) else []):
        etype = entry.get("type", "?") if isinstance(entry, dict) else "?"
        if etype == "idle":
            continue
        delay = extract_delay_sec(entry) if isinstance(entry, dict) else None
        meta = reg.get(sid, {})
        age = _busy_age_sec(meta) if meta else None
        stuck = (delay is not None and delay > a.threshold) or \
                (delay is None and age is not None and age > a.threshold
                 and etype in ("busy", "retry", "running", "waiting"))
        rows.append({"session": sid, "status": etype,
                     "delaySec": delay, "busyAgeSec": age,
                     "objective": meta.get("objective", ""),
                     "verdict": "STUCK" if stuck else "WAIT"})
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
                print(f"  -> migrate: scripts/session-reuse.py migrate "
                      f"{r['session']} --objective \"{r['objective'] or '<OBJECTIVE>'}\"")
        if stuck_rows and not rows == stuck_rows:
            pass
    raise SystemExit(2 if stuck_rows else 0)


def _resolve_next_model(excluded):
    """Shared chain resolution returning (avail, pins, rotate_line)."""
    excluded_l = {e.strip().lower() for e in excluded if e.strip()}
    never = load_never()

    def is_excluded(full):
        low = full.lower()
        return low in excluded_l or low.split("/", 1)[-1] in excluded_l \
            or is_never(full, never)

    ordered, seen = [], set()

    def add(full, source):
        if full not in seen:
            seen.add(full)
            ordered.append((full, source, is_excluded(full)))

    live = live_provider_models()
    live_index = {}
    if live is not None:
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
        add(resolved or want, f"fallback-chain:{entry.get('order', '?')}")
    avail = [m for m, _s, e in ordered if not e]
    pins = [m for m, s in config_models()
            if s.startswith("project:") and s.endswith("agent.build")]
    rotate = ""
    if avail and pins and pins[0].lower() != avail[0].lower():
        rotate = (f"sed -i 's#\"model\": \"{pins[0]}\""
                  f"#\"model\": \"{avail[0]}\"#' opencode.jsonc"
                  "  # then restart server (no hot-reload)")
    return (avail[0] if avail else "", pins[0] if pins else "", rotate,
            [m for m, _s, _e in ordered])


def cmd_migrate(args):
    import argparse
    p = argparse.ArgumentParser(
        description="Pause a STUCK task and continue the SAME task on the "
                    "next HEALTHY worker (runtime subagent_type switch — no "
                    "server restart). Records the dead model in cooldown "
                    "memory (provider delay when known, else 3h default). "
                    "Never deletes transcripts.")
    p.add_argument("id")
    p.add_argument("--objective", required=True)
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
    if old_model:
        excluded.append(old_model)
    # 1. Cooldown memory: provider-known delay wins, else 3h default.
    cd = a.delay if a.delay and a.delay > 0 else DEFAULT_COOLDOWN_SEC
    if old_model:
        h = load_health()
        h["models"][old_model.lower()] = {
            "model": old_model, "state": "dead",
            "deadAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "retryAfter": time.time() + cd,
            "cooldownSec": cd,
            "reason": f"stuck {a.id} delay>{a.threshold:g}s",
        }
        save_health(h)
    reg["sessions"][a.id] = {
        "agent": old_worker, "objective": objective, "task": task,
        "model": old_model, "state": "paused-stuck",
        "lastUsed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lastResult": (meta.get("lastResult", "") or "") +
                      f" [PAUSED-STUCK delay>{a.threshold:g}s, migrating]",
        "migrateTo": "",
    }
    save_reg(reg)
    print(f"paused {a.id} (state=paused-stuck, objective={objective})")
    print(f"old-worker: {old_worker} old-model: {old_model or '?'} "
          f"(cooldown {fmt_dur(cd)})")
    # 2. Runtime rotation: next healthy worker, no restart.
    role, model, wait = resolve_next_worker(excluded)
    if role:
        reg = load_reg()
        reg["sessions"][a.id]["migrateTo"] = f"{role} ({model})"
        save_reg(reg)
        print(f"next-worker: {role} ({model}) — NO server restart needed")
        print("--- Task call (SAME task, different worker; paste as next Task) ---")
        print(f"subagent_type={role} (do NOT pass task_id: the old session "
              f"is stuck on a dead model, re-attaching would wait again)")
        print(f"description: {objective[:60] or task[:60]}")
        print(f"prompt: SAME task as paused session {a.id}: {task}. "
              f"Prior result where available (do not repeat finished work); "
              f"continue only the remaining gaps. "
              f"Do not invoke subagents, do the work directly.")
        print(f"after result: register the returned task_id, then retire {a.id}")
    else:
        soon, soon_m = wait if wait else (0, "?")
        print("next-worker: NONE (all workers in cooldown)")
        print(f"genuine wait: earliest retry {soon_m} in {fmt_dur(soon)} — "
              f"do NOT spin fresh Tasks until then; report and wait.")


CMDS = {"register": cmd_register, "context": cmd_context, "decide": cmd_decide,
        "retire": cmd_retire, "delete": cmd_delete, "status": cmd_status,
        "children": cmd_children, "list": cmd_list, "version": cmd_version,
        "health": cmd_health, "mark-dead": cmd_mark_dead,
        "mark-alive": cmd_mark_alive,
        "stuck": cmd_stuck, "migrate": cmd_migrate,
        "models": cmd_models, "classify-error": cmd_classify_error}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(f"usage: {sys.argv[0]} {{{'|'.join(CMDS)}}}")
    CMDS[sys.argv[1]](sys.argv[2:])
