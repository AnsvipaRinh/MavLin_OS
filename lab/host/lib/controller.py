"""Deploy controller + test orchestrator for the mavericks-lab host."""
import base64
import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from .scenarios import get_scenario


class LabError(Exception):
    pass


class LabController:
    def __init__(self, transport, store, host_key_dir=None):
        self.transport = transport
        self.store = store
        self.host_key_dir = Path(host_key_dir) if host_key_dir else None

    def status(self):
        return self.transport.request("status")

    def inventory(self):
        return self.transport.request("inventory")

    def ping(self):
        return self.transport.request("ping")

    def deploy(self, image_path, slot=None):
        image_data = Path(image_path).read_bytes()
        sha256 = hashlib.sha256(image_data).hexdigest()
        sig = self._sign(image_data)
        image_b64 = base64.b64encode(image_data).decode()
        sig_b64 = base64.b64encode(sig).decode() if sig else ""
        version = f"img-{time.strftime('%Y%m%dT%H%M%SZ')}-{sha256[:8]}"
        args = {
            "version": version,
            "sha256": sha256,
            "image_b64": image_b64,
            "signature_b64": sig_b64,
        }
        if slot:
            args["slot"] = slot
        return self.transport.request("deploy", args, timeout=120)

    def verify(self, slot):
        return self.transport.request("verify", {"slot": slot})

    def select_boot(self, slot):
        return self.transport.request("select-boot", {"slot": slot})

    def reboot(self):
        return self.transport.request("reboot", {})

    def shutdown(self):
        return self.transport.request("shutdown", {})

    def commit(self):
        return self.transport.request("commit", {})

    def rollback(self):
        return self.transport.request("rollback", {})

    def run_test(self, name, args=None):
        return self.transport.request("run-test", {"name": name, "args": args})

    def benchmark(self, name, args=None):
        return self.transport.request("benchmark", {"name": name, "args": args})

    def collect(self, lines=200):
        return self.transport.request("collect", {"lines": lines})

    def logs(self, lines=100):
        return self.transport.request("logs", {"lines": lines})

    def trace(self, lines=100):
        return self.transport.request("trace", {"lines": lines})

    def snapshot(self, name):
        return self.transport.request("snapshot", {"name": name})

    def restore(self, name):
        return self.transport.request("restore", {"name": name})

    def test_scenario(self, scenario_name, image_path=None):
        job_id = str(uuid.uuid4())
        start = time.time()
        start_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result = {
            "job_id": job_id,
            "scenario": scenario_name,
            "steps": [],
            "result": "fail",
        }
        machine_id = "local"
        boot_id = None
        image_version = None
        slot = None
        deployment_id = None
        try:
            status_resp = self.status()
            if status_resp.get("ok"):
                machine_id = status_resp["result"].get("machine_id") or "local"
                boot_id = status_resp["result"].get("boot_id")

            if image_path:
                deploy_resp = self.deploy(image_path)
                result["steps"].append({"step": "deploy", "resp": deploy_resp})
                if not deploy_resp.get("ok"):
                    raise LabError(f"deploy failed: {deploy_resp.get('error')}")
                slot = deploy_resp["result"]["slot"]
                image_version = deploy_resp["result"]["version"]
                deployment_id = deploy_resp["result"]["deployment_id"]
            else:
                status_resp = self.status()
                if status_resp.get("ok"):
                    slot = status_resp["result"].get("active_slot")

            if slot:
                self.select_boot(slot)
                result["steps"].append({"step": "select-boot", "slot": slot})
                self.reboot()
                result["steps"].append({"step": "reboot"})
                if hasattr(self.transport, "boot"):
                    self.transport.boot()
                    result["steps"].append({"step": "boot-oneshot"})
                healthy = self._wait_for_state("HEALTHY", timeout=30)
                if not healthy:
                    raise LabError("timeout waiting for HEALTHY")

            sc = get_scenario(scenario_name)
            if not sc:
                raise LabError(f"unknown scenario: {scenario_name}")
            test_resp = self.transport.request(sc["cmd"], sc["args"])
            result["steps"].append({"step": "test", "resp": test_resp})
            if not test_resp.get("ok"):
                raise LabError(f"test failed: {test_resp.get('error')}")

            collect_resp = self.collect(lines=100)
            result["steps"].append({"step": "collect", "resp": collect_resp})

            commit_resp = self.commit()
            result["steps"].append({"step": "commit", "resp": commit_resp})
            if not commit_resp.get("ok"):
                raise LabError(f"commit failed: {commit_resp.get('error')}")

            result["result"] = "pass"
        except LabError as e:
            result["failure_reason"] = str(e)
            try:
                self.rollback()
                result["steps"].append({"step": "rollback"})
            except Exception:
                pass
        except Exception as e:
            result["failure_reason"] = f"{type(e).__name__}: {e}"
        end_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result["duration_s"] = round(time.time() - start, 2)
        self.store.record_job(
            machine_id=machine_id,
            job_id=job_id,
            scenario=scenario_name,
            result=result["result"],
            failure_reason=result.get("failure_reason"),
            boot_id=boot_id,
            image_version=image_version,
            slot=slot,
            deployment_id=deployment_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        return result

    def _wait_for_state(self, target_state, timeout=30, interval=0.5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.status()
            if resp.get("ok") and resp["result"].get("state") == target_state:
                return True
            if resp.get("ok") and resp["result"].get("state") == "FAIL":
                return False
            time.sleep(interval)
        return False

    def _sign(self, data):
        if not self.host_key_dir:
            return None
        priv = self.host_key_dir / "host.pem"
        if not priv.exists():
            return None
        try:
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", str(priv)],
                input=data,
                capture_output=True,
                check=True,
            )
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
