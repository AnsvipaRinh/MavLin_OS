#!/usr/bin/env python3
"""Final orchestrator-grade validation: transport + real coding objective."""
import asyncio
import importlib.util
import json
import subprocess
import sys

CLI = ["python3", "/home/builder/projects/MavLinOS/scripts/qwen-integration/qwen-web-worker.py"]

results = []


def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    results.append(ok)


def run_cli(args, timeout):
    p = subprocess.run(
        CLI + args, capture_output=True, text=True, timeout=timeout)
    line = None
    for ln in p.stdout.splitlines()[::-1]:
        if ln.startswith("{"):
            line = ln
            break
    return (json.loads(line) if line else None), p.stderr


def main():
    # 1. auth gate
    print("=== Gate: check --json ===")
    out, err = run_cli(["check", "--json"], timeout=120)
    report("check returns authenticated", bool(out and out.get("authenticated")))

    # 2. deterministic transport
    print("=== Deterministic transport ===")
    out, err = run_cli([
        "send", "--json", "--timeout", "300",
        "--prompt",
        "Reply with exactly the single string QWEN_TRANSPORT_TEST_7F3A. "
        "Do not create files. Do not browse. Do not perform any other action. "
        "Do not explain anything.",
    ], timeout=400)
    report("transport answer exact",
           bool(out and out.get("response") == "QWEN_TRANSPORT_TEST_7F3A"),
           f"resp={out.get('response') if out else None!r}")
    report("transport completed flag", bool(out and out.get("completed")))
    report("chat_id returned", bool(out and out.get("chat_id")))
    chat_1 = out.get("chat_id") if out else None

    # 3. REAL coding objective — transparent scope, no embellishment
    print("=== Real coding objective (transparent scope) ===")
    objective = (
        "Write a Python function `slugify(text: str) -> str` that converts text "
        "to a URL slug: lowercase ASCII, words separated by single hyphens, "
        "strip leading/trailing hyphens, drop all other characters. Include 3 "
        "short assert examples. Reply with the code only, no explanations."
    )
    out, err = run_cli(["send", "--json", "--timeout", "420", "--prompt", objective],
                       timeout=520)
    resp = (out or {}).get("response") or ""
    report("coding answer received", bool(resp), f"len={len(resp)}")
    report("answer contains def slugify", "def slugify" in resp)
    report("answer contains asserts", "assert" in resp)
    report("completed flag", bool(out and out.get("completed")))
    report("model feedback present", bool(out and out.get("model")),
           f"model={out.get('model') if out else None}")
    print(f"    files={out.get('files') if out else None} "
          f"commit_id={(out.get('commit_id') or '')[:12] if out else None}")
    print("    answer preview:", resp[:300].replace("\n", "\\n"))

    # 4. followup IN THE SAME conversation — refinement, transparent
    print("=== Followup refinement (same conversation) ===")
    followup = (
        "Now make slugify also collapse multiple consecutive hyphens into one. "
        "Reply with the updated function only."
    )
    out2, err2 = run_cli(["send", "--json", "--timeout", "420", "--prompt", followup],
                         timeout=520)
    resp2 = (out2 or {}).get("response") or ""
    report("followup answer received", bool(resp2), f"len={len(resp2)}")
    report("followup same chat_id",
           bool(out2 and chat_1 and out2.get("chat_id") == chat_1),
           f"{chat_1} == {out2.get('chat_id') if out2 else None}")

    print("\n=== SUMMARY ===")
    print(f"{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


main()
