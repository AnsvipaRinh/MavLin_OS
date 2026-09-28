#!/usr/bin/env python3
"""Tests for the mavericks-lab-agent A/B state machine."""
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
    tmp = tempfile.mkdtemp(prefix="lab-test-state-")
    mod = load_agent(tmp)

    # Initial state
    state = mod.load_state()
    check("initial state UNKNOWN", state["state"] == "UNKNOWN")
    check("initial attempt 0", state["attempt"] == 0)
    check("max_attempts 3", state["max_attempts"] == 3)

    # Valid transitions
    state, err = mod.transition_state(state, "BOOTING")
    check("UNKNOWN->BOOTING", err is None and state["state"] == "BOOTING")
    state, err = mod.transition_state(state, "NETWORK_READY")
    check("BOOTING->NETWORK_READY", err is None)
    state, err = mod.transition_state(state, "AGENT_READY")
    check("NETWORK_READY->AGENT_READY", err is None)
    state, err = mod.transition_state(state, "HEALTH_CHECK")
    check("AGENT_READY->HEALTH_CHECK", err is None)
    state, err = mod.transition_state(state, "HEALTHY")
    check("HEALTH_CHECK->HEALTHY", err is None)
    state, err = mod.transition_state(state, "COMMITTED")
    check("HEALTHY->COMMITTED", err is None)

    # Invalid transition
    state2 = mod.load_state()
    state2, err = mod.transition_state(state2, "UNKNOWN")
    check("COMMITTED->UNKNOWN rejected", err is not None)

    # FAIL path
    state3 = mod.load_state()
    state3["state"] = "HEALTH_CHECK"
    state3, err = mod.transition_state(state3, "FAIL")
    check("HEALTH_CHECK->FAIL", err is None and state3["state"] == "FAIL")
    state3, err = mod.transition_state(state3, "ROLLBACK")
    check("FAIL->ROLLBACK", err is None)
    state3, err = mod.transition_state(state3, "BOOTING")
    check("ROLLBACK->BOOTING", err is None)

    # Attempt counter is managed by boot(), not transition_state
    state4 = mod.load_state()
    state4["state"] = "HEALTH_CHECK"
    state4, err = mod.transition_state(state4, "FAIL")
    check("transition to FAIL ok", err is None and state4["state"] == "FAIL")
    check("attempt unchanged by transition", state4["attempt"] == 0)

    # State persistence (atomic write)
    state5 = mod.load_state()
    state5["state"] = "HEALTHY"
    mod.save_state(state5)
    state6 = mod.load_state()
    check("state persists", state6["state"] == "HEALTHY")
    check("updated_at set", state6["updated_at"] is not None)

    # Journal records state changes
    entries = mod.journal_read()
    state_changes = [e for e in entries if e["type"] == "state_change"]
    check("journal records state changes", len(state_changes) > 0)

    # Boot mode: fresh boot advances state
    tmp2 = tempfile.mkdtemp(prefix="lab-test-boot-")
    mod2 = load_agent(tmp2)
    # Deploy a slot first so boot has metadata
    import base64
    image_data = b"test image content"
    sha256 = __import__("hashlib").sha256(image_data).hexdigest()
    image_b64 = base64.b64encode(image_data).decode()
    dep_id, err = mod2.deploy_image("v1", "A", sha256, image_b64, "")
    check("deploy for boot test", err is None)
    # Simulate boot
    mod2.boot()
    state = mod2.load_state()
    check("boot advances to HEALTHY", state["state"] == "HEALTHY")
    check("boot sets active_slot", state["active_slot"] == "A")
    check("boot sets deployment_id", state["deployment_id"] == dep_id)
    check("boot resets attempt", state["attempt"] == 0)

    # Boot mode: interrupted boot resumes
    mod2.boot()
    state = mod2.load_state()
    check("re-boot stays HEALTHY", state["state"] == "HEALTHY")

    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
