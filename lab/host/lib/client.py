"""Transport layer for the mavericks-lab host controller.

Two transports:
  LocalTransport — spawns the agent process locally (testing/simulation).
  SSHTransport  — connects via SSH forced-command (real hardware).
"""
import json
import os
import subprocess
import sys
import uuid


class LabError(Exception):
    pass


class LocalTransport:
    def __init__(self, agent_path, data_dir):
        self.agent_path = agent_path
        self.data_dir = data_dir

    def request(self, cmd, args=None, timeout=60):
        req = {"id": str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
        try:
            proc = subprocess.run(
                [sys.executable, self.agent_path, "serve"],
                input=json.dumps(req) + "\n",
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "MV_LAB_DATA": str(self.data_dir)},
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "agent timeout"}
        for line in proc.stdout.strip().splitlines():
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"ok": False, "error": f"no response: {proc.stderr.strip()}"}

    def boot(self):
        try:
            proc = subprocess.run(
                [sys.executable, self.agent_path, "boot"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "MV_LAB_DATA": str(self.data_dir)},
            )
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            return False


class SSHTransport:
    def __init__(self, host, user, key_path, agent_cmd="mavericks-lab-agent"):
        self.host = host
        self.user = user
        self.key_path = key_path
        self.agent_cmd = agent_cmd

    def request(self, cmd, args=None, timeout=60):
        req = {"id": str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
        try:
            proc = subprocess.run(
                [
                    "ssh",
                    "-i",
                    self.key_path,
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "ConnectTimeout=10",
                    f"{self.user}@{self.host}",
                    self.agent_cmd,
                ],
                input=json.dumps(req) + "\n",
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "ssh timeout"}
        except FileNotFoundError:
            return {"ok": False, "error": "ssh not available"}
        for line in proc.stdout.strip().splitlines():
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"ok": False, "error": f"no response: {proc.stderr.strip()}"}
