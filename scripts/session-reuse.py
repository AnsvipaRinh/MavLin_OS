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
  models [--exclude M,...] [--all] [--format text|json]
                            ordered fallback candidates, CHAIN-ONLY by default
                            (user chain matched live vs GET /provider).
                            --all adds config pins, registry last-good,
                            remaining live models. Chain 'never' list is
                            always excluded. No hardcoding.
  classify-error [TEXT...]  QUOTA_EXHAUSTED(10)/CONTEXT_EXHAUSTED(12) vs
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
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(BASE, "..", ".opencode", "sessions", "registry.json")
CHAIN = os.path.join(BASE, "..", ".opencode", "model-fallback.json")

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


def classify_text(text):
    low = text or ""
    low = low.lower()
    for pat in CONTEXT_PATTERNS:
        if re.search(pat, low):
            return "CONTEXT_EXHAUSTED", pat
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
    a = p.parse_args(args)
    text = " ".join(a.text) if a.text else sys.stdin.read()
    verdict, matched = classify_text(text)
    print(f"{verdict} (matched: {matched})")
    raise SystemExit({"QUOTA_EXHAUSTED": 10, "CONTEXT_EXHAUSTED": 12,
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
            ordered.append((full, source, is_excluded(full)))

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
            [{"model": m, "source": s, "excluded": e}
             for m, s, e in ordered], indent=1))
    else:
        for m, s, e in ordered:
            tag = ""
            if e:
                tag = ("  [FORBIDDEN-never-list]" if is_never(m, never)
                       else "  [EXHAUSTED-skip]")
            print(f"{m}  source={s}" + tag)
        avail = [m for m, _s, e in ordered if not e]
        if avail:
            print(f"next-available: {avail[0]}")
        else:
            print("next-available: NONE (all candidates exhausted)")


CMDS = {"register": cmd_register, "context": cmd_context, "decide": cmd_decide,
        "retire": cmd_retire, "delete": cmd_delete, "status": cmd_status,
        "children": cmd_children, "list": cmd_list,
        "models": cmd_models, "classify-error": cmd_classify_error}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit(f"usage: {sys.argv[0]} {{{'|'.join(CMDS)}}}")
    CMDS[sys.argv[1]](sys.argv[2:])
