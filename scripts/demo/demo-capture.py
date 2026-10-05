#!/usr/bin/env python3
"""demo-capture.py — capture the demo Xvfb root window to a PNG.

Part of the visual-demo harness (scripts/demo/). Runs ONLY against the
display given via --display (a dedicated local Xvfb started by
run-demo.sh, never the ambient host display). Fails loud if the target
display equals a forbidden (host) display, mirroring the gui-guard rule.
License: GPL-2.0-or-later.
"""
import argparse
import os
import sys

FORBIDDEN = {":0", "wayland-0", ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", required=True, help="X display to capture")
    ap.add_argument("--output", required=True, help="output PNG path")
    args = ap.parse_args()

    if args.display in FORBIDDEN or "wayland" in args.display:
        print(f"REFUSED: display {args.display!r} looks like a host display",
              file=sys.stderr)
        return 125

    os.environ["DISPLAY"] = args.display
    os.environ["GDK_BACKEND"] = "x11"
    os.environ.pop("WAYLAND_DISPLAY", None)

    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    display = Gdk.Display.open(args.display)
    if display is None:
        print(f"FAIL: cannot open display {args.display}", file=sys.stderr)
        return 1
    screen = display.get_default_screen()
    window = screen.get_root_window()
    w, h = window.get_width(), window.get_height()
    pb = Gdk.pixbuf_get_from_window(window, 0, 0, w, h)
    if pb is None:
        print("FAIL: root capture returned None", file=sys.stderr)
        return 1
    pb.savev(args.output, "png", [], [])
    print(f"ok - captured {w}x{h} -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
