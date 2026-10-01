"""Harness driver — loads scenario YAMLs, executes steps, asserts, records.

Usage:
    python3 lab/harness/harness.py [--backend sim|qemu] [--scenario NAME] [--all]

Each scenario YAML declares:
    name, description, backends, fixture (initial conditions), steps, expected

The runner:
    1. Builds a fresh fixture from the scenario's fixture params
    2. Executes steps via the backend
    3. Asserts on serial log + journal + boot state + result DB
    4. Records pass/fail in the result DB (SQLite)
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent.parent
HARNESS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = HARNESS_DIR / "scenarios"
TEMP = Path("/tmp/mavericks-lab-harness")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario TEXT NOT NULL,
    backend TEXT NOT NULL,
    result TEXT NOT NULL,
    failure_reason TEXT,
    started_at TEXT,
    finished_at TEXT,
    duration_s REAL,
    evidence TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_scenario ON runs(scenario);
CREATE INDEX IF NOT EXISTS idx_runs_result ON runs(result);
"""


class HarnessError(Exception):
    pass


class Harness:
    def __init__(self, backend_name, result_db=None):
        self.backend_name = backend_name
        self.result_db = result_db or str(TEMP / "results.sqlite")
        Path(self.result_db).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.result_db)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def list_scenarios(self):
        scenarios = []
        for f in sorted(SCENARIOS_DIR.glob("*.yaml")):
            with open(f) as fh:
                sc = yaml.safe_load(fh)
            scenarios.append(sc)
        return scenarios

    def run_scenario(self, scenario, keep_fixture=False):
        name = scenario["name"]
        backends = scenario.get("backends", ["sim"])
        if self.backend_name not in backends:
            return {"scenario": name, "backend": self.backend_name,
                    "result": "skip", "reason": "backend not in scenario"}

        fixture_dir = TEMP / f"{name}-{self.backend_name}-{uuid.uuid4().hex[:8]}"
        from fixtures import builder
        builder.create_fixture(fixture_dir, scenario.get("fixture", {}))

        backend = self._make_backend(fixture_dir)
        started = time.time()
        started_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result = "pass"
        failure_reason = None
        evidence = {"serial": "", "journal": [], "state": {}, "boot": {}}

        try:
            for step in scenario.get("steps", []):
                self._exec_step(backend, step, scenario)
            # assertions
            evidence = self._collect_evidence(backend)
            self._assert(scenario.get("expected", {}), evidence)
        except HarnessError as e:
            result = "fail"
            failure_reason = str(e)
        except Exception as e:
            result = "fail"
            failure_reason = f"{type(e).__name__}: {e}"
        finally:
            try:
                backend.stop()
            except Exception:
                pass
            if not keep_fixture:
                shutil.rmtree(fixture_dir, ignore_errors=True)

        finished_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        duration = round(time.time() - started, 2)
        ev_paths = {"fixture_dir": str(fixture_dir)}
        self.conn.execute(
            "INSERT INTO runs (scenario, backend, result, failure_reason, started_at, finished_at, duration_s, evidence) VALUES (?,?,?,?,?,?,?,?)",
            (name, self.backend_name, result, failure_reason, started_ts, finished_ts,
             duration, json.dumps(ev_paths)),
        )
        self.conn.commit()
        return {"scenario": name, "backend": self.backend_name,
                "result": result, "failure_reason": failure_reason,
                "duration_s": duration}

    def _make_backend(self, fixture_dir):
        if self.backend_name == "sim":
            from backends.sim_backend import SimBackend
            return SimBackend(fixture_dir)
        elif self.backend_name == "qemu":
            from backends.qemu_backend import QemuBackend
            return QemuBackend(fixture_dir)
        else:
            raise HarnessError(f"unknown backend: {self.backend_name}")

    def _exec_step(self, backend, step, scenario):
        if "boot" in step:
            expect = step["boot"].get("expect_state")
            state = backend.start()
            if expect and state != expect:
                raise HarnessError(f"boot expected {expect}, got {state}")
        elif "reboot" in step:
            backend.stop()
            time.sleep(0.5)
            backend.start(reset_serial=False)
        elif "deploy" in step:
            d = step["deploy"]
            image = self._make_image(d.get("image", "test-image"), d.get("corrupt", False))
            backend.write_deploy_image(d.get("name", "image.tar"), image)
            sha = hashlib.sha256(image).hexdigest()
            resp = backend.run_agent_cmd("deploy", {
                "version": d.get("version", "v1"),
                "slot": d.get("slot"),
                "sha256": d.get("sha256", sha),
                "image_b64": self._b64(image),
                "signature_b64": d.get("signature_b64", ""),
            })
            # deploy failure is recorded but not raised (scenarios assert on it)
        elif "select_boot" in step:
            resp = backend.run_agent_cmd("select-boot", {"slot": step["select_boot"]})
            if not resp.get("ok"):
                raise HarnessError(f"select-boot failed: {resp.get('error')}")
        elif "commit" in step:
            resp = backend.run_agent_cmd("commit", {})
            if not resp.get("ok"):
                raise HarnessError(f"commit failed: {resp.get('error')}")
        elif "rollback" in step:
            resp = backend.run_agent_cmd("rollback", {})
            if not resp.get("ok"):
                raise HarnessError(f"rollback failed: {resp.get('error')}")
        elif "status" in step:
            resp = backend.run_agent_cmd("status", {})
            if not resp.get("ok"):
                raise HarnessError(f"status failed: {resp.get('error')}")
        elif "verify" in step:
            resp = backend.run_agent_cmd("verify", {"slot": step["verify"]})
            if not resp.get("ok"):
                raise HarnessError(f"verify failed: {resp.get('error')}")
        elif "inject" in step:
            backend.inject(step["inject"], **step.get("inject_args", {}))
        elif "power_loss" in step:
            backend.stop(sigkill=True)
        elif "host_crash" in step:
            backend.stop(sigkill=True)
        elif "wait" in step:
            time.sleep(step["wait"])
        else:
            raise HarnessError(f"unknown step: {list(step.keys())}")

    def _make_image(self, content, corrupt=False):
        data = f"fixture-image-{content}".encode() * 100
        if corrupt:
            data = b"\xde\xad\xbe\xef" + data[4:]
        return data

    def _b64(self, data):
        import base64
        return base64.b64encode(data).decode()

    def _collect_evidence(self, backend):
        return {
            "serial": backend.read_serial(),
            "journal": backend.read_journal(),
            "state": backend.read_state(),
            "boot": backend.get_boot_state(),
        }

    def _assert(self, expected, evidence):
        serial = evidence["serial"]
        journal = evidence["journal"]
        state = evidence["state"]
        boot = evidence["boot"]

        for key, want in expected.items():
            if key == "serial_contains":
                for s in want:
                    if s not in serial:
                        raise HarnessError(f"serial missing: {s}")
            elif key == "serial_not_contains":
                for s in want:
                    if s in serial:
                        raise HarnessError(f"serial should not contain: {s}")
            elif key == "state":
                if state.get("state") != want:
                    raise HarnessError(f"state expected {want}, got {state.get('state')}")
            elif key == "active_slot":
                if state.get("active_slot") != want:
                    raise HarnessError(f"active_slot expected {want}, got {state.get('active_slot')}")
            elif key == "journal_contains":
                types = [e.get("type") for e in journal]
                for t in want:
                    if t not in types:
                        raise HarnessError(f"journal missing event: {t}")
            elif key == "boot_current":
                if boot.get("current_slot") != want:
                    raise HarnessError(f"boot current expected {want}, got {boot.get('current_slot')}")
            elif key == "boot_next":
                if boot.get("next_slot") != want:
                    raise HarnessError(f"boot next expected {want}, got {boot.get('next_slot')}")
            else:
                raise HarnessError(f"unknown assertion: {key}")

    def run_all(self, scenario_filter=None):
        results = []
        for sc in self.list_scenarios():
            if scenario_filter and sc["name"] != scenario_filter:
                continue
            r = self.run_scenario(sc)
            results.append(r)
            status = r["result"]
            print(f"  {status:4s}  {sc['name']:40s}  {r.get('failure_reason', '')}")
        return results

    def summary(self):
        rows = self.conn.execute(
            "SELECT scenario, backend, result, failure_reason FROM runs ORDER BY id"
        ).fetchall()
        passed = sum(1 for r in rows if r["result"] == "pass")
        failed = sum(1 for r in rows if r["result"] == "fail")
        skipped = sum(1 for r in rows if r["result"] == "skip")
        return {"total": len(rows), "passed": passed, "failed": failed, "skipped": skipped,
                "rows": [dict(r) for r in rows]}


def main():
    parser = argparse.ArgumentParser(description="mavericks-lab harness")
    parser.add_argument("--backend", default="sim", choices=["sim", "qemu"])
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--result-db", default=None)
    args = parser.parse_args()

    h = Harness(args.backend, args.result_db)

    if args.list:
        for sc in h.list_scenarios():
            print(f"  {sc['name']:40s}  {sc.get('description', '')}")
        return

    if args.all or not args.scenario:
        print(f"Running all scenarios on backend={args.backend}")
        results = h.run_all()
        s = h.summary()
        print(f"\n{s['passed']} passed, {s['failed']} failed, {s['skipped']} skipped")
        if s["failed"]:
            print("\nFailures:")
            for r in s["rows"]:
                if r["result"] == "fail":
                    print(f"  {r['scenario']}: {r['failure_reason']}")
            sys.exit(1)
    else:
        scs = {s["name"]: s for s in h.list_scenarios()}
        if args.scenario not in scs:
            print(f"unknown scenario: {args.scenario}")
            sys.exit(1)
        r = h.run_scenario(scs[args.scenario])
        print(json.dumps(r, indent=2))
        if r["result"] != "pass":
            sys.exit(1)


if __name__ == "__main__":
    main()
