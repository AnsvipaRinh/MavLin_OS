"""QEMU backend — real guest boot via direct kernel boot.

Uses the same kernel + initramfs + cmdline as the EFI-stub approach, but
booted via QEMU -kernel/-initrd/-append (the EFI stub cmdline patching for
kernel 7.2.6-zen doesn't produce serial output in this QEMU/OVMF config —
documented in docs/LAB_HARNESS.md).

The guest init (guest_init.py) runs as PID 1, mounts the DATA disk
(virtio-blk, ext4), runs boot stages + the agent, and enters a command
loop. The host communicates via virtio-serial port (org.mavericks.cmd),
the guest processes commands, the host reads responses.

Disk: virtio-blk (CONFIG_VIRTIO_BLK=y built-in), ext4 (CONFIG_EXT4_FS=y).
Network: virtio-net-pci (CONFIG_VIRTIO_NET=y built-in), user-mode SLiRP
(no ICMP — agent comms use TCP/HTTP via DATA disk; guest health check
validates /proc/net/route presence).
Command channel: virtio-serial (CONFIG_VIRTIO_CONSOLE=y built-in),
/dev/virtio-ports/org.mavericks.cmd in guest, Unix socket on host.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import threading
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
        # virtio-serial command channel
        self.cmd_sock = self.work / "cmd.sock"
        self._cmd_sock_conn = None
        self._cmd_lock = threading.Lock()

    def _qemu_cmd(self):
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
            "-device", "virtio-serial-pci",
            "-chardev", f"socket,id=char0,path={self.cmd_sock},server=on,wait=on",
            "-device", "virtserialport,chardev=char0,name=org.mavericks.cmd",
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
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from fixtures import builder
            builder.build_initramfs(initrd)
        # clean up old socket
        if self.cmd_sock.exists():
            self.cmd_sock.unlink()
        self.proc = subprocess.Popen(
            self._qemu_cmd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # wait for socket to appear (QEMU creates it) and connect (wait=on)
        deadline = time.time() + 10
        while time.time() < deadline:
            if self.cmd_sock.exists():
                try:
                    self._cmd_sock_conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self._cmd_sock_conn.settimeout(5)
                    self._cmd_sock_conn.connect(str(self.cmd_sock))
                    break
                except (ConnectionRefusedError, FileNotFoundError):
                    time.sleep(0.1)
            time.sleep(0.1)
        if self._cmd_sock_conn is None:
            self.stop()
            raise RuntimeError("Failed to connect to virtio-serial socket")
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
        if self._cmd_sock_conn:
            self._cmd_sock_conn.close()
            self._cmd_sock_conn = None
        if self.cmd_sock.exists():
            self.cmd_sock.unlink()

    def _send_recv(self, req, timeout=60):
        """Send request and receive response on the persistent socket connection."""
        if not self._cmd_sock_conn:
            return {"ok": False, "error": "not connected to virtio-serial"}
        with self._cmd_lock:
            try:
                self._cmd_sock_conn.sendall((json.dumps(req) + "\n").encode())
                # Read response (JSON + newline)
                buf = b""
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        data = self._cmd_sock_conn.recv(4096)
                        if not data:
                            return {"ok": False, "error": "connection closed"}
                        buf += data
                        if b"\n" in buf:
                            line, _ = buf.split(b"\n", 1)
                            if line:
                                return json.loads(line.decode())
                    except socket.timeout:
                        continue
            except Exception as e:
                return {"ok": False, "error": f"socket error: {e}"}
        return {"ok": False, "error": "timeout waiting for resp"}

    def run_agent_cmd(self, cmd, args=None, timeout=60):
        req = {"id": str(uuid.uuid4()), "cmd": cmd, "args": args or {}}
        return self._send_recv(req, timeout)

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