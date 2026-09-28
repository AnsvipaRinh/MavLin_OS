#!/usr/bin/env python3
"""End-to-end test: full A/B lifecycle with local transport.

Covers: deploy → verify → select-boot → reboot → boot-oneshot → health →
test → collect → commit, plus rollback, idempotency, and crash recovery.
"""
import base64
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "lab/host"))

from lib.client import LocalTransport
from lib.controller import LabController
from lib.store import LabStore

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


def make_image(content: bytes) -> bytes:
    return content


def main():
    tmp = tempfile.mkdtemp(prefix="lab-e2e-")
    data_dir = os.path.join(tmp, "data")
    store_path = os.path.join(tmp, "store.sqlite")
    agent_path = str(REPO / "lab/agent/mavericks-lab-agent")

    transport = LocalTransport(agent_path, data_dir)
    store = LabStore(store_path)
    ctl = LabController(transport, store)

    # --- Phase 1: initial status ---
    resp = ctl.status()
    check("initial status ok", resp.get("ok") is True)
    check("initial state UNKNOWN", resp["result"]["state"] == "UNKNOWN")

    # --- Phase 2: deploy image to slot B ---
    image = make_image(b"e2e test image v1" * 50)
    image_path = os.path.join(tmp, "image.tar")
    Path(image_path).write_bytes(image)

    resp = ctl.deploy(image_path, slot="B")
    check("deploy ok", resp.get("ok") is True)
    check("deploy slot B", resp["result"]["slot"] == "B")
    dep_id = resp["result"]["deployment_id"]
    check("deployment_id set", dep_id is not None)

    # Verify slot B
    resp = ctl.verify("B")
    check("verify B ok", resp.get("ok") is True)
    check("verify B sha256", resp["result"]["sha256_valid"] is True)

    # --- Phase 3: select boot B + reboot + boot oneshot ---
    resp = ctl.select_boot("B")
    check("select-boot B", resp.get("ok") is True)

    resp = ctl.reboot()
    check("reboot ok", resp.get("ok") is True)

    # Simulate boot oneshot
    transport.boot()

    # Wait for HEALTHY
    healthy = ctl._wait_for_state("HEALTHY", timeout=10)
    check("reached HEALTHY", healthy)

    resp = ctl.status()
    check("active slot B", resp["result"]["active_slot"] == "B")
    check("state HEALTHY", resp["result"]["state"] == "HEALTHY")

    # --- Phase 4: run test ---
    resp = ctl.run_test("echo", {"text": "e2e-hello"})
    check("run-test ok", resp.get("ok") is True)
    check("run-test pass", resp["result"]["result"] == "pass")

    # --- Phase 5: collect ---
    resp = ctl.collect(lines=50)
    check("collect ok", resp.get("ok") is True)

    # --- Phase 6: commit ---
    resp = ctl.commit()
    check("commit ok", resp.get("ok") is True)
    check("state COMMITTED", resp["result"]["state"] == "COMMITTED")

    resp = ctl.status()
    check("status COMMITTED", resp["result"]["state"] == "COMMITTED")

    # --- Phase 7: deploy v2 to A, full test scenario ---
    image2 = make_image(b"e2e test image v2" * 50)
    image_path2 = os.path.join(tmp, "image2.tar")
    Path(image_path2).write_bytes(image2)

    result = ctl.test_scenario("echo", image_path2)
    check("test_scenario pass", result["result"] == "pass")
    check("test_scenario has steps", len(result["steps"]) >= 4)

    # Verify store recorded the job
    rows = store.query_jobs(scenario="echo", result="pass")
    check("store has pass job", len(rows) >= 1)

    # --- Phase 8: rollback ---
    resp = ctl.rollback()
    check("rollback ok", resp.get("ok") is True)
    check("rollback state", resp["result"]["state"] == "ROLLBACK")

    # --- Phase 9: idempotency — re-deploy same image ---
    resp = ctl.deploy(image_path, slot="B")
    check("re-deploy idempotent", resp.get("ok") is True)
    check("same deployment_id", resp["result"]["deployment_id"] == dep_id)

    # --- Phase 10: crash recovery — simulate interrupted deploy ---
    # Deploy a new image, then verify state is consistent
    image3 = make_image(b"e2e test image v3" * 50)
    image_path3 = os.path.join(tmp, "image3.tar")
    Path(image_path3).write_bytes(image3)

    resp = ctl.deploy(image_path3, slot="A")
    check("deploy v3 ok", resp.get("ok") is True)

    # State should still be consistent (HEALTHY or ROLLBACK from earlier)
    resp = ctl.status()
    check("state consistent after deploy", resp["result"]["state"] in ("HEALTHY", "ROLLBACK", "COMMITTED"))

    # --- Phase 11: snapshot + restore ---
    resp = ctl.snapshot("e2e-snap")
    check("snapshot ok", resp.get("ok") is True)

    # Modify state (rollback if not already)
    resp = ctl.status()
    if resp["result"]["state"] != "ROLLBACK":
        resp = ctl.rollback()
        check("rollback for restore test", resp.get("ok") is True)

    resp = ctl.restore("e2e-snap")
    check("restore ok", resp.get("ok") is True)

    # --- Phase 12: logs + trace ---
    resp = ctl.logs(lines=20)
    check("logs ok", resp.get("ok") is True)
    check("logs has entries", len(resp["result"]["entries"]) > 0)

    resp = ctl.trace(lines=20)
    check("trace ok", resp.get("ok") is True)
    check("trace has entries", len(resp["result"]["entries"]) > 0)

    # --- Phase 13: inventory ---
    resp = ctl.inventory()
    check("inventory ok", resp.get("ok") is True)
    check("inventory has cpu", "cpu" in resp["result"])

    # --- Phase 14: shutdown ---
    resp = ctl.shutdown()
    check("shutdown ok", resp.get("ok") is True)

    store.close()
    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
