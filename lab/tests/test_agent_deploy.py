#!/usr/bin/env python3
"""Tests for the mavericks-lab-agent deployment layer."""
import base64
import hashlib
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
    tmp = tempfile.mkdtemp(prefix="lab-test-deploy-")
    mod = load_agent(tmp)

    image_data = b"test image content v1" * 100
    sha256 = hashlib.sha256(image_data).hexdigest()
    image_b64 = base64.b64encode(image_data).decode()

    # Deploy to slot A
    dep_id, err = mod.deploy_image("v1", "A", sha256, image_b64, "")
    check("deploy ok", err is None)
    check("deployment_id format", dep_id.startswith("img-"))

    # Verify slot A
    result, err = mod.verify_slot("A")
    check("verify ok", err is None)
    check("verify sha256 valid", result["sha256_valid"] is True)
    check("verify deployment_id", result["deployment_id"] == dep_id)

    # Verify empty slot
    result, err = mod.verify_slot("B")
    check("verify empty slot fails", err is not None)

    # Idempotent re-deploy
    dep_id2, err = mod.deploy_image("v1", "A", sha256, image_b64, "")
    check("re-deploy idempotent", err is None and dep_id2 == dep_id)

    # SHA mismatch
    bad_sha = "0" * 64
    dep_id3, err = mod.deploy_image("v1", "B", bad_sha, image_b64, "")
    check("sha mismatch rejected", err is not None and "sha256 mismatch" in err)

    # Invalid slot
    dep_id4, err = mod.deploy_image("v1", "C", sha256, image_b64, "")
    check("invalid slot rejected", err is not None)

    # Deploy to slot B
    image_data_b = b"test image content v2" * 100
    sha256_b = hashlib.sha256(image_data_b).hexdigest()
    image_b64_b = base64.b64encode(image_data_b).decode()
    dep_id_b, err = mod.deploy_image("v2", "B", sha256_b, image_b64_b, "")
    check("deploy B ok", err is None)

    # Both slots have images
    result_a, _ = mod.verify_slot("A")
    result_b, _ = mod.verify_slot("B")
    check("slot A intact", result_a["sha256_valid"] is True)
    check("slot B intact", result_b["sha256_valid"] is True)
    check("slots independent", result_a["deployment_id"] != result_b["deployment_id"])

    # Snapshot + restore
    snap, err = mod.create_snapshot("test-snap")
    check("snapshot ok", err is None)
    check("snapshot has name", snap["name"] == "test-snap")

    # Modify state, then restore
    state = mod.load_state()
    state["state"] = "FAIL"
    mod.save_state(state)
    check("state modified", mod.load_state()["state"] == "FAIL")

    restore, err = mod.restore_snapshot("test-snap")
    check("restore ok", err is None)
    check("state restored", mod.load_state()["state"] != "FAIL")

    # Snapshot duplicate
    snap2, err = mod.create_snapshot("test-snap")
    check("duplicate snapshot rejected", err is not None)

    # Restore missing
    restore2, err = mod.restore_snapshot("no-such-snap")
    check("restore missing rejected", err is not None)

    # Commit/rollback protocol
    tmp2 = tempfile.mkdtemp(prefix="lab-test-commit-")
    mod2 = load_agent(tmp2)
    mod2.boot()
    state = mod2.load_state()
    check("boot HEALTHY for commit", state["state"] == "HEALTHY")

    # commit from HEALTHY
    resp = mod2.cmd_commit({})
    check("commit ok", "error" not in resp)
    check("commit state", resp["state"] == "COMMITTED")
    check("state is COMMITTED", mod2.load_state()["state"] == "COMMITTED")

    # rollback from COMMITTED
    resp = mod2.cmd_rollback({})
    check("rollback ok", "error" not in resp)
    check("rollback state", resp["state"] == "ROLLBACK")

    # commit from wrong state
    resp = mod2.cmd_commit({})
    check("commit from ROLLBACK rejected", "error" in resp)

    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
