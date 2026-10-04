#!/usr/bin/env python3
"""Tests for the mavericks-lab harness (scenario runner + backends)."""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO / "lab/harness"))
# The tests import package paths like `lab.harness.fixtures.builder`, so the
# repo root must be importable regardless of how the file is invoked
# (CI runs `python3 lab/harness/tests/test_harness.py` with no PYTHONPATH).
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

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


def test_scenario_files_valid():
    import yaml
    sc_dir = REPO / "lab/harness/scenarios"
    files = sorted(sc_dir.glob("*.yaml"))
    check("25 scenario files", len(files) == 25, f"got {len(files)}")
    for f in files:
        with open(f) as fh:
            sc = yaml.safe_load(fh)
        check(f"{f.name} has name", "name" in sc)
        check(f"{f.name} has steps", len(sc.get("steps", [])) > 0)
        check(f"{f.name} has expected", "expected" in sc)
        check(f"{f.name} has backends", "backends" in sc)


def test_sim_backend_boot():
    from lab.harness.fixtures import builder
    from lab.harness.backends.sim_backend import SimBackend
    tmp = tempfile.mkdtemp(prefix="harness-test-")
    builder.create_fixture(tmp + "/fixture", {"slot_a_image": "v1", "network": "up"})
    backend = SimBackend(tmp + "/fixture")
    state = backend.start()
    check("sim boot HEALTHY", state == "HEALTHY", f"got {state}")
    serial = backend.read_serial()
    check("sim serial has BOOT", "BOOT slot=A" in serial)
    check("sim serial has AGENT_BOOT", "AGENT_BOOT state=HEALTHY" in serial)


def test_sim_backend_deploy():
    from lab.harness.fixtures import builder
    from lab.harness.backends.sim_backend import SimBackend
    tmp = tempfile.mkdtemp(prefix="harness-test-")
    builder.create_fixture(tmp + "/fixture", {"slot_a_image": "v1", "network": "up"})
    backend = SimBackend(tmp + "/fixture")
    backend.start()
    image = b"test-image-v2" * 100
    backend.write_deploy_image("image.tar", image)
    import hashlib, base64
    sha = hashlib.sha256(image).hexdigest()
    resp = backend.run_agent_cmd("deploy", {
        "version": "v2", "slot": "B", "sha256": sha,
        "image_b64": base64.b64encode(image).decode(), "signature_b64": "",
    })
    check("sim deploy ok", resp.get("ok") is True, resp.get("error", ""))


def test_sim_backend_network_down():
    from lab.harness.fixtures import builder
    from lab.harness.backends.sim_backend import SimBackend
    tmp = tempfile.mkdtemp(prefix="harness-test-")
    builder.create_fixture(tmp + "/fixture", {"slot_a_image": "v1", "network": "down"})
    backend = SimBackend(tmp + "/fixture")
    state = backend.start()
    check("sim network-down fails", state in ("FAIL", "ROLLBACK"), f"got {state}")
    serial = backend.read_serial()
    check("sim serial NETWORK down", "NETWORK down" in serial)


def test_harness_runner():
    from harness import Harness
    tmp = tempfile.mkdtemp(prefix="harness-test-")
    h = Harness("sim", result_db=tmp + "/results.sqlite")
    scs = {s["name"]: s for s in h.list_scenarios()}
    check("harness lists 25 scenarios", len(scs) == 25, f"got {len(scs)}")
    r = h.run_scenario(scs["01_successful_a_boot"])
    check("harness 01 passes", r["result"] == "pass", r.get("failure_reason", ""))


def test_mac_backend_stub():
    try:
        from backends.mac_backend import MacBackend
        MacBackend()
        check("mac backend raises", False, "should have raised")
    except NotImplementedError:
        ok("mac backend raises NotImplementedError")


def main():
    test_scenario_files_valid()
    test_sim_backend_boot()
    test_sim_backend_deploy()
    test_sim_backend_network_down()
    test_harness_runner()
    test_mac_backend_stub()
    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    if FAILURES:
        sys.exit(1)


if __name__ == "__main__":
    main()
