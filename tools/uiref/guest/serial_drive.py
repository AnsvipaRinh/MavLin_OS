#!/usr/bin/env python3
"""serial_drive.py - boot a Linux initramfs in QEMU and drive it over serial.

The rescue guest has no display, so the whole install is driven and observed
through ttyS0: every command and every line of output is text, so nothing has
to be read off a screenshot.

Usage:
  serial_drive.py --kernel K --initrd I --append "console=ttyS0 ..." \
                   --disk payload.img --disk mavericks-hdd.raw \
                   --cmd "mount -t ext4 /dev/sda2 /mnt/p" --cmd "..."
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import time

PROMPT = re.compile(rb"[\r\n]# $")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--initrd", required=True)
    ap.add_argument("--append", required=True)
    ap.add_argument("--disk", action="append", default=[])
    ap.add_argument("--cmd", action="append", default=[])
    ap.add_argument("--sock", default="/tmp/opencode/ser.sock")
    ap.add_argument("--log", default="/tmp/opencode/ser.log")
    ap.add_argument("--mem", default="4G")
    ap.add_argument("--boot-timeout", type=int, default=900)
    ap.add_argument("--qemu-timeout", type=int, default=7200)
    args = ap.parse_args()

    if os.path.exists(args.sock):
        os.unlink(args.sock)
    log = open(args.log, "w+b")

    cmd = [
        "qemu-system-x86_64",
        "-machine", "pc", "-accel", "tcg,thread=multi", "-cpu", "max",
        "-m", args.mem, "-smp", "2",
        "-kernel", args.kernel, "-initrd", args.initrd,
        "-append", args.append,
        "-display", "none",
        "-serial", "unix:%s,server=on,wait=off" % args.sock,
        "-monitor", "none",
    ]
    for i, disk in enumerate(args.disk):
        cmd += ["-drive", "file=%s,format=raw,if=ide,index=%d,media=disk" % (disk, i + 1)]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    deadline = time.time() + args.boot_timeout
    sock = None
    while time.time() < deadline:
        if proc.poll() is not None:
            print("qemu exited early with %s" % proc.returncode)
            return 3
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(args.sock)
            break
        except OSError:
            sock.close()
            sock = None
            time.sleep(2)
    if sock is None:
        print("could not attach to the serial socket")
        proc.kill()
        return 3
    sock.settimeout(5)

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            try:
                data = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return
            log.write(data)
            log.flush()

    # wait for the initramfs root shell
    boot_deadline = time.time() + args.boot_timeout
    ready = False
    while time.time() < boot_deadline:
        pump(3)
        log.flush()
        log.seek(0)
        tail = log.read()[-4000:]
        log.seek(0, os.SEEK_END)
        if PROMPT.search(tail) or b"/ #" in tail:
            ready = True
            break
    if not ready:
        print("no shell prompt appeared; see %s" % args.log)
        pump(5)
        proc.kill()
        return 4

    print("shell ready, sending %d command(s)" % len(args.cmd))
    for command in args.cmd:
        sock.sendall((command + "\n").encode())
        pump(1.5)
        done = False
        end = time.time() + max(60, args.qemu_timeout // max(1, len(args.cmd)))
        while time.time() < end and not done:
            pump(3)
            log.flush()
            log.seek(0)
            blob = log.read()
            log.seek(0, os.SEEK_END)
            marker = ("__DONE__%d__" % args.cmd.index(command)).encode()
            if marker in blob:
                done = True
            if b"poweroff" in command.encode() and not done and time.time() > end:
                break
        print("  sent (%d/%d): %s" % (args.cmd.index(command) + 1, len(args.cmd),
                                       command[:70]))
    pump(5)
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("log: %s" % args.log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
