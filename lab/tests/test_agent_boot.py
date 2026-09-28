#!/usr/bin/env python3
"""Tests for the mavericks-lab-agent boot backend (QEMU simulation)."""
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
    tmp = tempfile.mkdtemp(prefix="lab-test-bootbackend-")
    mod = load_agent(tmp)

    boot = mod.get_boot_backend()

    # Initial state
    state = boot.get_boot_state()
    check("initial current A", state["current_slot"] == "A")
    check("initial next A", state["next_slot"] == "A")
    check("backend qemu", state["backend"] == "qemu")

    # Select boot B
    boot.select_boot("B")
    state = boot.get_boot_state()
    check("select B", state["next_slot"] == "B")
    check("current still A", state["current_slot"] == "A")

    # Reboot simulation
    boot.reboot()
    state = boot.get_boot_state()
    check("reboot updates current", state["current_slot"] == "B")
    check("next still B", state["next_slot"] == "B")

    # Select A + reboot
    boot.select_boot("A")
    boot.reboot()
    state = boot.get_boot_state()
    check("back to A", state["current_slot"] == "A")

    # Invalid slot
    try:
        boot.select_boot("C")
        check("invalid slot rejected", False)
    except ValueError:
        check("invalid slot rejected", True)

    # Entries exist
    entries_dir = Path(tmp) / "boot" / "entries"
    check("entry A exists", (entries_dir / "A.conf").exists())
    check("entry B exists", (entries_dir / "B.conf").exists())

    # Full A/B lifecycle via boot mode
    tmp2 = tempfile.mkdtemp(prefix="lab-test-ablifecycle-")
    mod2 = load_agent(tmp2)

    import base64, hashlib
    image = b"lifecycle test image"
    sha = hashlib.sha256(image).hexdigest()
    b64 = base64.b64encode(image).decode()

    # Deploy to B
    dep_id, err = mod2.deploy_image("v1", "B", sha, b64, "")
    check("deploy B", err is None)

    # Select B + reboot + boot
    mod2.get_boot_backend().select_boot("B")
    mod2.get_boot_backend().reboot()
    mod2.boot()

    state = mod2.load_state()
    check("booted into B", state["active_slot"] == "B")
    check("state HEALTHY", state["state"] == "HEALTHY")
    check("deployment matches", state["deployment_id"] == dep_id)

    # Commit
    resp = mod2.cmd_commit({})
    check("commit", "error" not in resp and resp["state"] == "COMMITTED")

    # Deploy to A (rollback target)
    image2 = b"rollback image"
    sha2 = hashlib.sha256(image2).hexdigest()
    b642 = base64.b64encode(image2).decode()
    dep_id2, err = mod2.deploy_image("v2", "A", sha2, b642, "")
    check("deploy A", err is None)

    # Select A + reboot + boot
    mod2.get_boot_backend().select_boot("A")
    mod2.get_boot_backend().reboot()
    mod2.boot()

    state = mod2.load_state()
    check("booted into A", state["active_slot"] == "A")
    check("state HEALTHY after A", state["state"] == "HEALTHY")

    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
