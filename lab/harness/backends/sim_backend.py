"""Simulated virtual-target backend (always works, rootless).

Represents the guest boot environment as directories on the host:
    fixture/data/       — agent DATA dir (state, journal, slots, boot/)
    fixture/rootfs-A/   — slot A rootfs markers
    fixture/rootfs-B/   — slot B rootfs markers
    fixture/serial.log  — serial log (ground truth)

The agent runs on the host via `agent serve` / `agent boot` (like Phase 1
LocalTransport). Network state is controlled by running the agent inside
`unshare -rn` (network-down) or normally (network-up).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .base import TargetBackend

REPO = Path(__file__).resolve().parent.parent.parent.parent
AGENT = REPO / "lab/agent/mavericks-lab-agent"


class SimBackend(TargetBackend):
    def __init__(self, fixture_dir):
        self.fixture = Path(fixture_dir)
        self.data = self.fixture / "data"
        self.serial_path = self.fixture / "serial.log"
        self._serial_lines = []
        self._boot_count = 0

    def _serial(self, msg):
        line = str(msg)
        self._serial_lines.append(line)
        with open(self.serial_path, "a") as f:
            f.write(line + "\n")

    def _env(self, network=None):
        env = dict(os.environ)
        env["MV_LAB_DATA"] = str(self.data)
        env["PYTHONHASHSEED"] = "0"
        return env

    def _run_agent(self, mode, timeout=30):
        return subprocess.run(
            [sys.executable, str(AGENT), mode],
            env=self._env(), capture_output=True, text=True, timeout=timeout,
        )

    def _run_agent_netns(self, mode, timeout=30):
        """Run agent inside a network namespace (network-down)."""
        return subprocess.run(
            ["unshare", "-rn", sys.executable, str(AGENT), mode],
            env=self._env(), capture_output=True, text=True, timeout=timeout,
        )

    def start(self, reset_serial=True):
        self._boot_count += 1
        fixture_env = self._read_fixture_env()
        slot = self._read_slot()
        # simulate reboot: advance current-boot.txt from next-boot.txt
        (self.data / "boot/current-boot.txt").write_text(slot + "\n")
        self._serial(f"BOOT slot={slot}")
        # rootfs stage
        rdir = self.data / f"rootfs-{slot}" / "etc/mavericks"
        if not (rdir / "slot-ok").exists():
            self._serial("ROOTFS_FAIL")
            return "ROOTFS_FAIL"
        self._serial("ROOTFS_MOUNT ok")
        # systemd stage
        if not (rdir / "systemd-ok").exists():
            self._serial("SYSTEMD_FAIL")
            return "SYSTEMD_FAIL"
        self._serial("SYSTEMD ok")
        # network stage
        if fixture_env.get("network", "up") == "up":
            self._serial("NETWORK up")
        else:
            self._serial("NETWORK down")
        # agent stage
        if fixture_env.get("agent", "on") == "off":
            self._serial("AGENT_SKIP")
            return "SKIP"
        # run agent boot (network-down -> netns)
        if fixture_env.get("network", "up") == "down":
            self._run_agent_netns("boot")
        else:
            self._run_agent("boot")
        state = self.read_state()
        st = state.get("state", "UNKNOWN") if state else "UNKNOWN"
        self._serial(f"AGENT_BOOT state={st}")
        self._serial(f"BOOT_DONE state={st}")
        # detect boot-loop protection halt
        if st == "FAIL":
            attempt = state.get("attempt", 0)
            max_attempts = state.get("max_attempts", 3)
            if attempt >= max_attempts:
                self._serial("BOOT_LOOP_HALT")
        return st

    def stop(self, sigkill=False):
        pass

    def run_agent_cmd(self, cmd, args=None, timeout=60):
        import uuid
        req = {"id": str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
        proc = subprocess.run(
            [sys.executable, str(AGENT), "serve"],
            input=json.dumps(req) + "\n",
            env=self._env(), capture_output=True, text=True, timeout=timeout,
        )
        for line in proc.stdout.strip().splitlines():
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"ok": False, "error": f"no response: {proc.stderr.strip()}"}

    def read_serial(self):
        try:
            return self.serial_path.read_text()
        except OSError:
            return ""

    def get_boot_state(self):
        cur = (self.data / "boot/current-boot.txt").read_text().strip()
        nxt = (self.data / "boot/next-boot.txt").read_text().strip()
        return {"current_slot": cur, "next_slot": nxt}

    def read_journal(self):
        try:
            lines = (self.data / "journal.jsonl").read_text().splitlines()
            return [json.loads(l) for l in lines if l.strip()]
        except (OSError, json.JSONDecodeError):
            return []

    def read_state(self):
        try:
            return json.loads((self.data / "state.json").read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def write_deploy_image(self, name, data):
        inbox = self.data / "deploy-inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / name).write_bytes(data)

    def inject(self, action, **kw):
        if action == "network_down":
            self._write_fixture_env(network="down")
        elif action == "network_up":
            self._write_fixture_env(network="up")
        elif action == "agent_off":
            self._write_fixture_env(agent="off")
        elif action == "corrupt_rootfs":
            slot = kw.get("slot", "B")
            marker = self.data / f"rootfs-{slot}" / "etc/mavericks/slot-ok"
            if marker.exists():
                marker.unlink()
        elif action == "systemd_fail":
            slot = kw.get("slot", "B")
            marker = self.data / f"rootfs-{slot}" / "etc/mavericks/systemd-ok"
            if marker.exists():
                marker.unlink()

    def _read_fixture_env(self):
        env = {}
        try:
            for line in (self.data / "fixture.env").read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        except OSError:
            pass
        return env

    def _write_fixture_env(self, **kw):
        env = self._read_fixture_env()
        env.update(kw)
        lines = [f"{k}={v}" for k, v in env.items()]
        (self.data / "fixture.env").write_text("\n".join(lines) + "\n")

    def _read_slot(self):
        try:
            return (self.data / "boot/next-boot.txt").read_text().strip()
        except OSError:
            return "A"

    def wait_for_agent_ready(self, timeout=30):
        """Sim backend is always ready immediately after start()."""
        return True
