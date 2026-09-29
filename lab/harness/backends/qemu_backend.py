"""QEMU backend — real guest boot via direct kernel boot.

Uses the same kernel + initramfs + cmdline as the EFI-stub approach, but
booted via QEMU -kernel/-initrd/-append (the EFI stub cmdline patching for
kernel 7.2.6-zen doesn't produce serial output in this QEMU/OVMF config —
documented in docs/LAB_HARNESS.md).

The guest init (guest_init.py) runs as PID 1, mounts the DATA disk
(virtio-blk, ext4), runs boot stages + the agent, and enters a command
loop. The host writes cmd.json to DATA, the guest processes it, the host
reads resp.json.

Disk: virtio-blk (CONFIG_VIRTIO_BLK=y built-in), ext4 (CONFIG_EXT4_FS=y).
Network: loopback ioctl (no route — network-up is a known limitation).
"""
import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from .base import TargetBackend

REPO = Path(__file__).resolve().parent.parent.parent.parent
KERNEL = Path("/tmp/mavericks-lab-kernel/vmlinuz-linux-zen")


class QemuBackend(TargetBackend):
    def __init__(self, fixture_dir, work_dir=None):
        self.fixture = Path(fixture_dir)
        self.data = self.fixture / "data"
        self.data_img = self.fixture / "data.img"
        self.serial_path = self.fixture / "serial.log"
        self.work = Path(work_dir) if work_dir else self.fixture / "qemu-work"
        self.work.mkdir(parents=True, exist_ok=True)
        self.proc = None
        self.monitor_sock = self.work / "monitor.sock"

    def _qemu_cmd(self):
        return [
            "qemu-system-x86_64",
            "-machine", "q35", "-m", "1024", "-smp", "2",
            "-kernel", str(KERNEL),
            "-initrd", str(self.fixture / "esp/EFI/BOOT/initramfs.img"),
            "-append", "console=ttyS0,115200",
            "-drive", f"if=none,file={self.data_img},format=raw,id=d0",
            "-device", "virtio-blk-pci,drive=d0",
            "-serial", f"file:{self.serial_path}",
            "-display", "none", "-no-reboot",
            "-monitor", f"unix:{self.monitor_sock},server,nowait",
        ]

    def start(self):
        self.stop()
        # reset serial log
        self.serial_path.write_text("")
        # ensure the ESP initramfs exists
        initrd = self.fixture / "esp/EFI/BOOT/initramfs.img"
        if not initrd.exists():
            from fixtures import builder
            builder.build_initramfs(initrd)
        self.proc = subprocess.Popen(
            self._qemu_cmd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return self._wait_for_boot()

    def _wait_for_boot(self, timeout=60):
        """Wait for BOOT_DONE or a failure marker in the serial log."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            serial = self.read_serial()
            if "BOOT_DONE" in serial:
                for line in serial.splitlines():
                    if line.startswith("BOOT_DONE"):
                        return line.split("state=")[-1].strip()
            if "ROOTFS_FAIL" in serial or "SYSTEMD_FAIL" in serial:
                return "FAIL"
            if "CMD_LOOP" in serial:
                return "TIMEOUT"
            if self.proc.poll() is not None:
                return "EXITED"
            time.sleep(0.5)
        return "TIMEOUT"

    def stop(self, sigkill=False):
        if self.proc and self.proc.poll() is None:
            if sigkill:
                self.proc.send_signal(signal.SIGKILL)
            else:
                self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def run_agent_cmd(self, cmd, args=None, timeout=60):
        req = {"id": str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
        cmd_file = self.data / "cmd.json"
        resp_file = self.data / "resp.json"
        cmd_file.write_text(json.dumps(req))
        # wait for resp.json to appear (guest processes cmd.json)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if resp_file.exists():
                try:
                    resp = json.loads(resp_file.read_text())
                    resp_file.unlink(missing_ok=True)
                    return resp
                except json.JSONDecodeError:
                    pass
            if self.proc and self.proc.poll() is not None:
                return {"ok": False, "error": "guest exited"}
            time.sleep(0.2)
        cmd_file.unlink(missing_ok=True)
        return {"ok": False, "error": "timeout waiting for resp.json"}

    def read_serial(self):
        try:
            return self.serial_path.read_text()
        except OSError:
            return ""

    def get_boot_state(self):
        # read from the DATA image via the guest's boot dir
        # (the host can't mount ext4 without root; use the agent status)
        resp = self.run_agent_cmd("status")
        if resp.get("ok"):
            r = resp["result"]
            return {"current_slot": r.get("active_slot"), "next_slot": r.get("next_slot")}
        return {"current_slot": "?", "next_slot": "?"}

    def read_journal(self):
        resp = self.run_agent_cmd("logs", {"lines": 500})
        if resp.get("ok"):
            return resp["result"].get("entries", [])
        return []

    def read_state(self):
        resp = self.run_agent_cmd("status")
        if resp.get("ok"):
            return resp["result"]
        return {}

    def write_deploy_image(self, name, data):
        # write to the DATA image via loop mount (root)
        mnt = self.work / "data-mnt"
        mnt.mkdir(parents=True, exist_ok=True)
        subprocess.run(["sudo", "mount", "-o", "loop", str(self.data_img), str(mnt)],
                       capture_output=True)
        try:
            inbox = mnt / "deploy-inbox"
            inbox.mkdir(exist_ok=True)
            (inbox / name).write_bytes(data)
        finally:
            subprocess.run(["sudo", "umount", str(mnt)], capture_output=True)

    def inject(self, action, **kw):
        if action == "network_down":
            self._set_fixture_env(network="down")
        elif action == "network_up":
            self._set_fixture_env(network="up")
        elif action == "agent_off":
            self._set_fixture_env(agent="off")
        elif action == "corrupt_rootfs":
            slot = kw.get("slot", "B")
            self._set_rootfs_marker(slot, "slot-ok", False)
        elif action == "systemd_fail":
            slot = kw.get("slot", "B")
            self._set_rootfs_marker(slot, "systemd-ok", False)

    def _set_fixture_env(self, **kw):
        # update fixture.env in the DATA image via loop mount
        mnt = self.work / "data-mnt"
        mnt.mkdir(parents=True, exist_ok=True)
        subprocess.run(["sudo", "mount", "-o", "loop", str(self.data_img), str(mnt)],
                       capture_output=True)
        try:
            env_file = mnt / "fixture.env"
            env = {}
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            env.update(kw)
            env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
        finally:
            subprocess.run(["sudo", "umount", str(mnt)], capture_output=True)

    def _set_rootfs_marker(self, slot, marker, present):
        mnt = self.work / "data-mnt"
        mnt.mkdir(parents=True, exist_ok=True)
        subprocess.run(["sudo", "mount", "-o", "loop", str(self.data_img), str(mnt)],
                       capture_output=True)
        try:
            m = mnt / f"rootfs-{slot}" / "etc/mavericks" / marker
            if present:
                m.parent.mkdir(parents=True, exist_ok=True)
                m.write_text("ok\n")
            elif m.exists():
                m.unlink()
        finally:
            subprocess.run(["sudo", "umount", str(mnt)], capture_output=True)
