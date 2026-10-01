"""QEMU backend — real guest boot via direct kernel boot.

Uses the same kernel + initramfs + cmdline as the EFI-stub approach, but
booted via QEMU -kernel/-initrd/-append (the EFI stub cmdline patching for
kernel 7.2.6-zen doesn't produce serial output in this QEMU/OVMF config —
documented in docs/LAB_HARNESS.md).

The guest init (guest_init.py) runs as PID 1, mounts the DATA disk
(virtio-blk, ext4), runs boot stages + the agent, and enters a command
loop. The host communicates via 9p virtfs share (cmd-channel),
the guest processes commands, the host reads responses.

Disk: virtio-blk (CONFIG_VIRTIO_BLK=y built-in), ext4 (CONFIG_EXT4_FS=y).
Network: virtio-net-pci (CONFIG_VIRTIO_NET=y built-in), user-mode SLiRP
(no ICMP — agent comms use TCP/HTTP via DATA disk; guest health check
validates /proc/net/route presence).
Command channel: 9p virtfs (CONFIG_NET_9P_VIRTIO=m), /mnt/cmd in guest.

Serial logging: uses -serial stdio; QEMU stdout captured in append mode
to serial.log to persist across QEMU restarts (reboot persistence).
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
        self._serial_log_file = None
        self._serial_pos = 0

    def _qemu_cmd(self):
        # Create a directory for the 9p command channel
        cmd_dir = self.work / "cmd-channel"
        cmd_dir.mkdir(parents=True, exist_ok=True)
        # Use stdio for serial output; we'll capture QEMU's stdout to serial.log in append mode
        return [
            "qemu-system-x86_64",
            "-machine", "q35", "-m", "1024", "-smp", "2",
            "-kernel", str(KERNEL),
            "-initrd", str(self.fixture / "esp/EFI/BOOT/initramfs.img"),
            "-append", "console=ttyS0,115200",
            "-drive", f"if=none,file={self.data_img},format=raw,id=d0",
            "-device", "virtio-blk-pci,drive=d0",
            "-netdev", "user,id=net0",
            "-device", "virtio-net-pci,netdev=net0",
            "-virtfs", f"local,path={cmd_dir},mount_tag=cmd-channel,security_model=mapped-xattr",
            "-serial", "stdio",
            "-display", "none", "-no-reboot",
            "-monitor", f"unix:{self.monitor_sock},server,nowait",
        ]

    def start(self, reset_serial=True):
        self.stop()
        if reset_serial:
            self.serial_path.write_text("")
        self._serial_pos = 0
        # ensure the ESP initramfs exists
        initrd = self.fixture / "esp/EFI/BOOT/initramfs.img"
        if not initrd.exists():
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from fixtures import builder
            builder.build_initramfs(initrd)
        # Open serial log in append mode for QEMU's stdout (serial output via -serial stdio)
        self._serial_log_file = open(self.serial_path, "ab")
        self.proc = subprocess.Popen(
            self._qemu_cmd(), stdout=self._serial_log_file, stderr=subprocess.DEVNULL
        )
        return self._wait_for_boot()

    def _wait_for_boot(self, timeout=60):
        """Wait for BOOT_DONE or a failure marker in the serial log (new content only)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Read only new content since last check
            try:
                with open(self.serial_path, "rb") as f:
                    f.seek(self._serial_pos)
                    new_data = f.read()
                    self._serial_pos = f.tell()
            except OSError:
                new_data = b""
            if new_data:
                new_text = new_data.decode("utf-8", errors="replace")
                if "BOOT_DONE" in new_text:
                    for line in new_text.splitlines():
                        if line.startswith("BOOT_DONE"):
                            return line.split("state=")[-1].strip()
                if "ROOTFS_FAIL" in new_text or "SYSTEMD_FAIL" in new_text:
                    return "FAIL"
                if "CMD_LOOP" in new_text:
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
        # Close serial log file
        if hasattr(self, '_serial_log_file') and self._serial_log_file:
            self._serial_log_file.close()
            self._serial_log_file = None

    def run_agent_cmd(self, cmd, args=None, timeout=120):
        req = {"id": str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
        # Write cmd.json to the 9p command channel directory
        cmd_dir = self.work / "cmd-channel"
        cmd_dir.mkdir(parents=True, exist_ok=True)
        cmd_file = cmd_dir / "cmd.json"
        resp_file = cmd_dir / "resp.json"
        cmd_file.write_text(json.dumps(req))
        # wait for resp.json to appear (guest processes cmd.json)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if resp_file.exists():
                try:
                    resp = json.loads(resp_file.read_text())
                    resp_file.unlink(missing_ok=True)
                    # small delay to let agent return to polling loop
                    time.sleep(0.1)
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