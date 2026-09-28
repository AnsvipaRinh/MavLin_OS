#!/usr/bin/env python3
"""Tests for the mavericks-lab-agent identity layer."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
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


def main():
    tmp = tempfile.mkdtemp(prefix="lab-test-identity-")
    mod = load_agent(tmp)

    # Generate identity
    fp, ok_flag = mod.generate_identity()
    check("identity generated", ok_flag)
    check("fingerprint is str", isinstance(fp, str) and len(fp) == 16)

    # Key files exist
    check("private key exists", mod.identity_path().exists())
    check("public key exists", mod.identity_pub_path().exists())

    # Private key permissions
    priv_mode = oct(os.stat(mod.identity_path()).st_mode)[-3:]
    check("private key 600", priv_mode == "600")

    # Idempotent (doesn't regenerate)
    fp2, _ = mod.generate_identity()
    check("fingerprint stable", fp == fp2)

    # identity_mode returns public key
    result = mod.identity_mode()
    check("identity_mode ok", "error" not in result)
    check("identity_mode has pub", "public_key" in result)
    check("identity_mode fingerprint", result["fingerprint"] == fp)

    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
