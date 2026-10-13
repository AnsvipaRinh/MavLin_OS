#!/usr/bin/env python3
"""vm_ser.py - send commands to the QEMU guest console (serial unix socket)."""
import argparse
import socket
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", help="command to run; omit to just read")
    ap.add_argument("--sock", default="/tmp/opencode/ser.sock")
    ap.add_argument("--wait", type=float, default=8.0, help="seconds to collect output")
    ap.add_argument("--expect", default=None, help="string that ends the wait early")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(args.sock)
    sock.settimeout(1.0)
    if args.command:
        sock.sendall((args.command + "\n").encode())
    out = bytearray()
    end = time.time() + args.wait
    while time.time() < end:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if args.expect and args.expect.encode() in bytes(out):
            time.sleep(0.4)
            try:
                while True:
                    extra = sock.recv(65536)
                    if not extra:
                        break
                    out += extra
            except OSError:
                pass
            break
    sock.close()
    text = bytes(out).decode("utf-8", "replace")
    if not args.quiet:
        sys.stdout.write(text)
    print(f"[{len(out)} bytes]" if not args.quiet else "", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
