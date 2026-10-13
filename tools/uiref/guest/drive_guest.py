#!/usr/bin/env python3
"""drive_guest.py - boot the Mavericks installer guest and type into it blind.

There is no serial console in Darwin, so commands go in as keystrokes over QMP
(send-key, batched) and results come back as files on the small FAT disk
labelled MAVLOG: the host reads them with mtools while the guest is running.
That makes every step verifiable without reading the framebuffer.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

OSK = "ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"
KEYMAP = {
    " ": "spc", "\n": "ret", "-": "minus", "=": "equal", "[": "bracket_left",
    "]": "bracket_right", ";": "semicolon", "'": "apostrophe",
    "`": "grave_accent", "\\": "backslash", ",": "comma", ".": "dot",
    "/": "slash", "$": "shift-4", ">": "shift-dot", "_": "shift-minus",
    "|": "shift-backslash", "+": "shift-equal", "(": "shift-9", ")": "shift-0",
    "*": "shift-8", "&": "shift-7", "!": "shift-1", "?": "shift-slash",
    "%": "shift-5", "#": "shift-3", "<": "shift-comma", "@": "shift-2",
    "^": "shift-6", "{": "shift-bracket_left", "}": "shift-bracket_right",
    "~": "shift-grave_accent", '"': "shift-apostrophe",
}


MODIFIERS = ("shift", "ctrl", "alt", "meta")


def to_keys(text):
    """QMP send-key takes qcode objects; modifiers are separate simultaneous keys."""
    keys = []
    for ch in text:
        if ch.isupper():
            name = "shift-" + ch.lower()
        elif ch in KEYMAP:
            name = KEYMAP[ch]
        elif ch.isalnum():
            name = ch
        else:
            raise SystemExit(f"unmapped character {ch!r} in typed text")
        for part in name.split("-"):
            keys.append({"type": "qcode", "data": part})
    return keys


class Qmp:
    def __init__(self, path, timeout=20):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(path)
                self.sock.settimeout(20)
                self._read()
                self.execute("qmp_capabilities")
                return
            except OSError as exc:
                last = exc
                time.sleep(1)
        raise SystemExit(f"cannot reach QMP at {path}: {last}")

    def _read(self):
        buf = b""
        while True:
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                return None
            if not chunk:
                return None
            buf += chunk
            while b"\r\n" in buf:
                line, buf = buf.split(b"\r\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if "return" in msg or "error" in msg:
                    return msg

    def execute(self, command, arguments=None):
        payload = {"execute": command}
        if arguments:
            payload["arguments"] = arguments
        self.sock.sendall((json.dumps(payload) + "\r\n").encode())
        reply = self._read()
        if reply and "error" in reply:
            raise SystemExit(f"QMP {command} failed: {reply['error']}")
        return reply

    def type_text(self, text, chunk=120):
        keys = to_keys(text)
        for i in range(0, len(keys), chunk):
            self.execute("send-key", {"keys": keys[i:i + chunk]})
            time.sleep(0.05)

    def powerdown(self):
        try:
            self.execute("system_powerdown")
        except SystemExit:
            pass


def read_log(disk, path="::/log"):
    out = subprocess.run(["mtype", "-i", disk, path],
                         capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--dvd", required=True)
    ap.add_argument("--logdisk", required=True)
    ap.add_argument("--script", required=True, help="file with one command per line")
    ap.add_argument("--boot-wait", type=int, default=300)
    ap.add_argument("--line-wait", type=float, default=6.0)
    ap.add_argument("--qmp", default="/tmp/opencode/qmp.sock")
    ap.add_argument("--poll", type=int, default=40, help="log polls after typing")
    ap.add_argument("--poll-wait", type=float, default=15.0)
    ap.add_argument("--keep", action="store_true", help="leave the guest running")
    ap.add_argument("--no-boot", action="store_true", help="guest is already running")
    ap.add_argument("--vars", default="/tmp/opencode/OVMF_VARS.fd")
    args = ap.parse_args()

    proc = None
    if not os.path.exists(args.vars):
        with open("/usr/share/edk2-ovmf/x64/OVMF_VARS.4m.fd", "rb") as src, \
                open(args.vars, "wb") as dst:
            dst.write(src.read())
    if not args.no_boot:
        if os.path.exists(args.qmp):
            os.unlink(args.qmp)
        cmd = [
            "qemu-system-x86_64",
            "-machine", "pc-q35-6.1,vmport=off",
            "-accel", "tcg,thread=multi",
            "-cpu", "Penryn,vendor=GenuineIntel,+sse4.1,+sse4.2,+ssse3",
            "-smp", "2,cores=2", "-m", "4G",
            "-drive", "if=pflash,format=raw,readonly=on,"
                     "file=/usr/share/edk2-ovmf/x64/OVMF_CODE.4m.fd",
            "-drive", f"if=pflash,format=raw,file={args.vars}",
            "-device", f"isa-applesmc,osk={OSK}",
            "-vga", "none", "-device", "vmware-svga",
            "-device", "e1000,netdev=net0",
            "-netdev", "user,id=net0,hostfwd=tcp::2222-:22",
            "-usb",
            "-device", "usb-kbd,bus=usb-bus.0",
            "-device", "usb-tablet,bus=usb-bus.0",
            "-device", "ide-hd,bus=ide.0,drive=ESP,bootindex=0",
            "-drive", f"if=none,id=ESP,file={args.esp},format=raw",
            "-device", "ide-hd,bus=ide.1,drive=TGT,bootindex=1",
            "-drive", f"if=none,id=TGT,file={args.target},format=raw",
            "-device", "ide-cd,bus=ide.2,drive=DVD,bootindex=2",
            "-drive", f"if=none,id=DVD,file={args.dvd},format=raw,readonly=on,media=cdrom",
            "-device", "ide-hd,bus=ide.3,drive=LOG,bootindex=3",
            "-drive", f"if=none,id=LOG,file={args.logdisk},format=raw",
            "-display", "none",
            "-qmp", f"unix:{args.qmp},server=on,wait=off",
        ]
        print("booting guest (TCG, no display)...")
        errlog = open("/tmp/opencode/qemu-guest.err", "wb")
        proc = subprocess.Popen(cmd, stdout=errlog, stderr=subprocess.STDOUT,
                                start_new_session=True)
        time.sleep(10)
        qmp = Qmp(args.qmp)
        print(f"waiting {args.boot_wait}s for the installer environment")
        for waited in range(0, args.boot_wait, 30):
            time.sleep(min(30, args.boot_wait - waited))
            print(f"  t+{waited}s", flush=True)
    else:
        qmp = Qmp(args.qmp)

    lines = [ln.rstrip("\n") for ln in open(args.script, encoding="utf-8")
             if ln.strip() and not ln.startswith("#")]
    print(f"typing {len(lines)} command line(s)")
    for line in lines:
        qmp.type_text(line + "\n")
        time.sleep(args.line_wait)
        print(f"  sent: {line[:78]}")

    log = None
    for _ in range(args.poll):
        time.sleep(args.poll_wait)
        log = read_log(args.logdisk + "@@1048576")
        if log and log.strip():
            break
    print("=== guest log (MAVLOG) ===")
    print(log if log else "(no log file yet)")
    if not args.keep:
        print("powering down")
        qmp.powerdown()
        time.sleep(20)
    if proc and proc.poll() is None and not args.keep:
        proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
