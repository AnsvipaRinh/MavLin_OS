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

Reuse rule: same agent role (`build`) + same objective + coherent + >50% context remaining.
Objective boundary: Calendar -> Calendar refinement = SAME session;
Calendar -> Disk Utility = NEW session. Never resume on context pressure,
error state, or role/objective change.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(BASE, "..", ".opencode", "sessions", "registry.json")

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
            print(f"WAIT (session status={s.get('type')}, do not send yet)");
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


CMDS = {"register": cmd_register, "context": cmd_context, "decide": cmd_decide,
        "retire": cmd_retire, "delete": cmd_delete, "status": cmd_status,
        "children": cmd_children, "list": cmd_list}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(f"usage: {sys.argv[0]} {{{'|'.join(CMDS)}}}")
    CMDS[sys.argv[1]](sys.argv[2:])
