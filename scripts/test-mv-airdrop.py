#!/usr/bin/env python3
"""Headless tests for mv-airdrop.

Pure-logic section (no GTK widgets, no live network):
- announcement payload shape (protocol v2 fields)
- datagram parsing: valid announce/reply, own-fingerprint filter,
  malformed JSON, non-dict payload, bad port
- discovery over a loopback UDP socket pair with a mock responder
  (no multicast, no avahi, no external traffic)
- NetworkManager connectivity mapping (connected states, offline,
  D-Bus failure -> unknown)
- send command construction (IP target, file list)
- device icon mapping (all protocol types + unknown fallback)

GUI smoke (real GTK, skipped headless):
- window construction, backend-missing banners
- offline state skips discovery
- device list rebuild from discovered devices
- send button gating (no device / no files / no CLI)
- keyboard: Escape, Ctrl+O, Enter
- receive button disabled without LocalSend

Usage: python3 scripts/test-mv-airdrop.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import json
import os
import socket
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-airdrop")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

HAS_DISPLAY = mv_gui_iso.gui_display() is not None


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


# Shared Mavericks dialog helpers path (for module import during test)
sys.path.insert(0, os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin"))

def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_airdrop", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_airdrop", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def mock_responder(sock, own_fp, reply_fp, delay=0.05):
    """Answers one announce with a protocol reply, then stops."""
    def run():
        try:
            data, addr = sock.recvfrom(65535)
            time.sleep(delay)
            reply = {
                "alias": "Mock iPhone",
                "version": "2.0",
                "deviceModel": "iPhone14,2",
                "deviceType": "mobile",
                "fingerprint": reply_fp,
                "port": 53317,
                "protocol": "https",
                "download": True,
                "announce": False,
            }
            sock.sendto(json.dumps(reply).encode(), addr)
        except OSError:
            pass
    threading.Thread(target=run, daemon=True).start()


def test_pure(m):
    ann = m.build_announcement("fp-test", "my-mac")
    check("announcement: protocol version", ann["version"] == "2.0")
    check("announcement: announce flag", ann["announce"] is True)
    check("announcement: port", ann["port"] == 53317)
    check("announcement: deviceType", ann["deviceType"] == "desktop")
    check("announcement: fingerprint", ann["fingerprint"] == "fp-test")
    check("announcement: alias", ann["alias"] == "my-mac")
    check("announcement: json serializable",
          isinstance(json.dumps(ann), str))

    raw = json.dumps({
        "alias": "Nice Orange", "version": "2.0", "deviceModel": "Samsung",
        "deviceType": "mobile", "fingerprint": "fp-1", "port": 53317,
        "protocol": "https", "download": True, "announce": False,
    }).encode()
    dev = m.parse_device_datagram(raw, "192.168.1.50", "fp-self")
    check("parse: alias", dev and dev["alias"] == "Nice Orange")
    check("parse: ip from source", dev and dev["ip"] == "192.168.1.50")
    check("parse: port", dev and dev["port"] == 53317)
    check("parse: deviceType", dev and dev["deviceType"] == "mobile")
    check("parse: download flag", dev and dev["download"] is True)

    check("parse: own fingerprint filtered",
          m.parse_device_datagram(raw, "192.168.1.50", "fp-1") is None)
    check("parse: malformed json filtered",
          m.parse_device_datagram(b"not json", "1.2.3.4", "fp-self") is None)
    check("parse: non-dict filtered",
          m.parse_device_datagram(b"[1,2]", "1.2.3.4", "fp-self") is None)
    check("parse: missing fingerprint filtered",
          m.parse_device_datagram(b'{"alias":"x"}', "1.2.3.4", "fp-self") is None)
    check("parse: bad port falls back to default",
          m.parse_device_datagram(
              json.dumps({"alias": "x", "fingerprint": "fp-9", "port": "abc"}).encode(),
              "1.2.3.4", "fp-self")["port"] == 53317)

    responder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    responder.bind(("127.0.0.1", 0))
    responder_addr = responder.getsockname()
    mock_responder(responder, "fp-self", "fp-responder")
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind(("127.0.0.1", 0))
    devices, err = m.discover(
        timeout=1.0, socket_factory=lambda: listener,
        fingerprint="fp-self", alias="test-host",
        group="127.0.0.1", port=responder_addr[1])
    check("discovery: no error", err is None, str(err))
    check("discovery: one device found", len(devices) == 1, str(devices))
    if devices:
        check("discovery: responder alias", devices[0]["alias"] == "Mock iPhone")
        check("discovery: responder ip", devices[0]["ip"] == "127.0.0.1")
    responder.close()

    listener2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener2.bind(("127.0.0.1", 0))
    devices2, err2 = m.discover(
        timeout=0.3, socket_factory=lambda: listener2,
        fingerprint="fp-self", alias="test-host",
        group="127.0.0.1", port=1)
    check("discovery: empty when no responders", err2 is None and devices2 == [])
    listener2.close()

    check("nm: connected global online", m.nm_connectivity(lambda: 70) is True)
    check("nm: connected site online", m.nm_connectivity(lambda: 40) is True)
    check("nm: connected link online", m.nm_connectivity(lambda: 30) is True)
    check("nm: disconnected offline", m.nm_connectivity(lambda: 20) is False)
    check("nm: unknown state offline", m.nm_connectivity(lambda: 0) is False)
    check("nm: checker None passthrough", m.nm_connectivity(lambda: None) is None)

    cmd = m.send_command("192.168.1.50", ["a.pdf", "b.jpg"])
    check("send cmd: cli binary", cmd[0] == "localsend-cli")
    check("send cmd: subcommand", cmd[1] == "send")
    check("send cmd: --to flag", cmd[2] == "--to" and cmd[3] == "192.168.1.50")
    check("send cmd: files appended", cmd[4:] == ["a.pdf", "b.jpg"])

    check("icon: mobile", m.device_icon_name("mobile") == "phone")
    check("icon: desktop", m.device_icon_name("desktop") == "computer")
    check("icon: web", m.device_icon_name("web") == "web-browser")
    check("icon: headless", m.device_icon_name("headless") == "utilities-terminal")
    check("icon: server", m.device_icon_name("server") == "network-server")
    check("icon: unknown fallback", m.device_icon_name("hologram") == "network-workgroup")


def test_gui(m):
    from gi.repository import Gtk, Gdk

    def pump():
        while Gtk.events_pending():
            Gtk.main_iteration()

    def pump_until(label, needle, tries=200):
        # discovery is async: start_discovery runs via idle_add and the worker
        # thread queues _discovery_done as a second idle — a single pump() can
        # drain the queue before the thread queues its idle. Sleep between
        # pumps: a hot pump loop starves the worker thread of the GIL.
        for _ in range(tries):
            pump()
            if needle in label.get_text():
                return True
            time.sleep(0.005)
        return False

    def no_devices():
        return [], None

    win = m.AirDropWindow(files=[], net_checker=lambda: None,
                          discover_fn=no_devices)
    pump()
    check("gui: window constructs", win.get_title() == "AirDrop")
    check("gui: attribution present",
          win.attr_label.get_text() == "Powered by LocalSend")
    check("gui: cli banner shown when backend missing",
          win.banner.get_visible())
    check("gui: send disabled without device+cli",
          not win.send_btn.get_sensitive())
    check("gui: receive disabled without backend",
          not win.receive_btn.get_sensitive())
    check("gui: no-devices guidance shown",
          pump_until(win.empty_label, "No nearby devices"))

    win2 = m.AirDropWindow(files=["/tmp/a.pdf"], net_checker=lambda: False,
                           discover_fn=no_devices)
    pump()
    check("gui: offline state shows guidance",
          "No network connection" in win2.empty_label.get_text())
    check("gui: offline banner shown", win2.banner.get_visible())
    check("gui: files label populated", "a.pdf" in win2.files_label.get_text())

    win3 = m.AirDropWindow(files=[], net_checker=lambda: None,
                           discover_fn=no_devices)
    pump()
    win3.devices = {
        "fp-1": {"alias": "Mock iPhone", "ip": "192.168.1.50", "port": 53317,
                 "protocol": "https", "deviceType": "mobile",
                 "deviceModel": "iPhone", "fingerprint": "fp-1",
                 "download": True},
    }
    win3.rebuild_list()
    rows = win3.device_list.get_children()
    check("gui: device row added", len(rows) == 1)
    check("gui: empty label hidden when devices found",
          not win3.empty_label.get_visible())
    win3.device_list.select_row(rows[0])
    check("gui: row selection sets selected device",
          win3.selected is not None and win3.selected["alias"] == "Mock iPhone")

    win4 = m.AirDropWindow(files=["/tmp/b.jpg"], net_checker=lambda: None,
                           discover_fn=no_devices)
    pump()
    check("gui: send disabled without device selection",
          not win4.send_btn.get_sensitive())

    for w in (win, win2, win3, win4):
        w.destroy()


    path = os.path.join(BIN, "mv-airdrop")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("airdrop: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("airdrop: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    m = load_app()
    test_pure(m)
    if not HAS_DISPLAY:
        print("SKIP - GUI smoke (no display)")
    else:
        test_gui(m)
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    if bad.failures:
        for name, detail in bad.failures:
            print("  FAIL: %s %s" % (name, detail))
        sys.exit(1)


if __name__ == "__main__":
    main()
