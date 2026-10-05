#!/usr/bin/env python3
"""Mission Control O6 — damage-driven live thumbnail tests.

Headless part exercises the LiveThumbnails controller with a fake
capture backend and injected watch registrars (no X11, no display).
Xvfb :97 part runs the real XComposite/XDamage stack: a repaint must
flow through the controller into the callback pixbuf, and the whole
Overview widget must hold a live session while open and leave ZERO
state (no watch, no damage objects, no open display) after exit.
"""
import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import mission_control_thumbnail as mct
import mission_control_live as mcl


class FakeCapture:
    """Minimal ThumbnailCapture stand-in for headless controller tests."""

    def __init__(self, damage_events, live=True, fd=42, capture=None):
        self.live_available = live
        self._fd = fd
        self._events = list(damage_events)
        self._capture_result = capture or {
            "win_id": 1, "width": 2, "height": 2, "stride": 8,
            "data": bytes([
                255, 0, 0, 255, 0, 255, 0, 255,
                0, 0, 255, 255, 255, 255, 0, 255,
            ]),
            "placeholder": False,
        }
        self.started = False
        self.stopped = False
        self.closed = False
        self.captured = []

    @property
    def connection_fd(self):
        return self._fd

    def start_capture(self, win_ids, callback=None):
        self.started = True
        return True

    def poll_damage(self, timeout_ms=0):
        events, self._events = self._events, []
        return events

    def capture_window(self, win_id, max_w, max_h):
        self.captured.append((win_id, max_w, max_h))
        return dict(self._capture_result, win_id=win_id)

    def stop_capture(self):
        self.stopped = True

    def close(self):
        self.closed = True


def test_live_start_requires_damage():
    cap = FakeCapture([], live=False)
    added = []
    live = mcl.LiveThumbnails(cap, lambda w, p: None,
                              watch_add=lambda fd, cb: added.append(fd) or 1,
                              watch_remove=lambda wid: None)
    assert live.start({1: (10, 10)}) is False
    assert added == []
    assert live.started is False
    print("PASS: live start refuses unavailable damage (static fallback)")


def test_live_lifecycle_and_refresh():
    cap = FakeCapture([{"win_id": 7, "area": {"x": 0, "y": 0, "width": 4, "height": 4}},
                       {"win_id": 99, "area": {"x": 0, "y": 0, "width": 1, "height": 1}}])
    watches = []
    removed = []
    updates = []
    live = mcl.LiveThumbnails(
        cap, lambda w, p: updates.append((w, p)),
        watch_add=lambda fd, cb: watches.append((fd, cb)) or 77,
        watch_remove=lambda wid: removed.append(wid),
    )
    assert live.start({7: (20, 10)}) is True
    assert cap.started is True
    assert watches and watches[0][0] == 42      # fd watch on the connection
    assert live.started is True

    keep = watches[0][1](None, 0)               # io-watch callback signature
    assert keep is True                          # watch stays installed
    # only the tracked window (7) is recaptured; 99 is ignored
    assert cap.captured == [(7, 20, 10)]
    assert len(updates) == 1
    wid, pixbuf = updates[0]
    assert wid == 7 and pixbuf is not None
    assert (pixbuf.get_width(), pixbuf.get_height()) == (2, 2)
    px = pixbuf.get_pixels()
    assert px[0:3] == b"\xff\x00\x00", px[0:3]   # RGBA -> RGB conversion correct

    live.stop()
    assert removed == [77]
    assert cap.stopped and cap.closed
    assert live.started is False
    print("PASS: live lifecycle — fd watch, damage->recapture->callback, teardown")


def test_live_refresh_placeholder_is_silent():
    cap = FakeCapture([])
    cap._capture_result = {"win_id": 1, "width": 2, "height": 2, "stride": 8,
                           "data": b"\x00" * 16, "placeholder": True}
    updates = []
    live = mcl.LiveThumbnails(cap, lambda w, p: updates.append(w),
                              watch_add=lambda fd, cb: 1,
                              watch_remove=lambda wid: None)
    live.start({5: (8, 8)})
    live.refresh(5, (8, 8))
    assert updates == []                          # placeholder -> no callback
    print("PASS: placeholder recapture stays silent")


def test_live_readability_keeps_watch_on_errors():
    cap = FakeCapture([])
    def boom(timeout_ms=0):
        raise RuntimeError("poll exploded")
    cap.poll_damage = boom
    live = mcl.LiveThumbnails(cap, lambda w, p: None,
                              watch_add=lambda fd, cb: 1,
                              watch_remove=lambda wid: None)
    live.start({1: (4, 4)})
    assert live._on_readable() is True            # error must not drop the watch
    print("PASS: poll errors do not drop the fd watch")


# ------------------------------------------------------------- Xvfb :97

def _x97_ok():
    if os.environ.get("DISPLAY") != ":97":
        return False
    try:
        c = ctypes
        x11 = mct._load_first_ctypes(mct._X11_LIB_NAMES)
        f_open = mct._bind_ctypes(x11, "XOpenDisplay", c.c_void_p, [c.c_char_p])
        f_close = mct._bind_ctypes(x11, "XCloseDisplay", c.c_int, [c.c_void_p])
        dpy = f_open(b":97")
        if not dpy:
            return False
        f_close(dpy)
        return True
    except Exception:
        return False


def _x11_funcs():
    c = ctypes
    x11 = mct._load_first_ctypes(mct._X11_LIB_NAMES)
    f = lambda n, r, a: mct._bind_ctypes(x11, n, r, a)
    return x11, f


def test_live_damage_refresh_xvfb():
    """Real stack: repaint -> controller recaptures -> callback sees new color."""
    if not _x97_ok():
        print("SKIP: test_live_damage_refresh_xvfb (DISPLAY != :97)")
        return
    c = ctypes
    x11, f = _x11_funcs()
    dpy = f("XOpenDisplay", c.c_void_p, [c.c_char_p])(b":97")
    root = f("XDefaultRootWindow", c.c_ulong, [c.c_void_p])(dpy)
    f_create = f("XCreateSimpleWindow", c.c_ulong,
        [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_ulong])
    f_map = f("XMapWindow", c.c_int, [c.c_void_p, c.c_ulong])
    f_sync = f("XSync", c.c_int, [c.c_void_p, c.c_int])
    f_gc = f("XCreateGC", c.c_ulong, [c.c_void_p, c.c_ulong, c.c_ulong, c.c_void_p])
    f_setfg = f("XSetForeground", c.c_int, [c.c_void_p, c.c_ulong, c.c_ulong])
    f_fill = f("XFillRectangle", c.c_int,
        [c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.c_uint, c.c_uint])
    win = f_create(dpy, root, 120, 120, 200, 120, 0, 0, 0xFF0000)
    f_map(dpy, win)
    f_sync(dpy, 0)
    gc_ = f_gc(dpy, win, 0, None)
    f_setfg(dpy, gc_, 0xFF0000)
    f_fill(dpy, win, gc_, 0, 0, 200, 120)
    f_sync(dpy, 0)

    tc = mct.ThumbnailCapture(display_name=":97")
    if not tc.live_available:
        tc.close()
        print("SKIP: test_live_damage_refresh_xvfb (no XDamage on :97)")
        return
    updates = []
    live = mcl.LiveThumbnails(tc, lambda w, p: updates.append((w, p)))
    try:
        assert live.start({win: (60, 36)}) is True
        live._on_readable()                       # drain initial damage
        updates.clear()

        f_setfg(dpy, gc_, 0x00FF00)               # repaint -> damage event
        f_fill(dpy, win, gc_, 0, 0, 200, 120)
        f_sync(dpy, 0)
        deadline = time.time() + 3
        while not updates and time.time() < deadline:
            live._on_readable()
            time.sleep(0.02)
        assert updates, "damage did not reach the controller"
        wid, pixbuf = updates[0]
        assert wid == win
        px = pixbuf.get_pixels()
        assert px[0:3] == b"\x00\xff\x00", px[0:3]
    finally:
        live.stop()
        assert tc._closed and not tc.capturing   # zero residual state
    print("PASS: live damage refresh through the controller on :97")


def test_overview_live_session_lifecycle_xvfb():
    """The Overview holds a live session while open; exit leaves nothing."""
    if not _x97_ok():
        print("SKIP: test_overview_live_session_lifecycle_xvfb (DISPLAY != :97)")
        return
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib
    except (ImportError, ValueError):
        print("SKIP: test_overview_live_session_lifecycle_xvfb (GTK3 unavailable)")
        return

    c = ctypes
    x11, f = _x11_funcs()
    dpy = f("XOpenDisplay", c.c_void_p, [c.c_char_p])(b":97")
    root = f("XDefaultRootWindow", c.c_ulong, [c.c_void_p])(dpy)
    f_create = f("XCreateSimpleWindow", c.c_ulong,
        [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_ulong])
    f_map = f("XMapWindow", c.c_int, [c.c_void_p, c.c_ulong])
    f_sync = f("XSync", c.c_int, [c.c_void_p, c.c_int])
    win = f_create(dpy, root, 90, 90, 260, 160, 0, 0, 0x4466AA)
    f_map(dpy, win)
    f_sync(dpy, 0)

    from Xlib import display as xdisplay, Xatom
    d = xdisplay.Display(":97")
    d.screen().root.change_property(
        d.intern_atom("_NET_CLIENT_LIST"), Xatom.WINDOW, 32, [win])
    d.sync()

    import importlib.util
    import importlib.machinery
    mod_path = os.path.join(HERE, "..", "bin", "mv-mc-overview")
    loader = importlib.machinery.SourceFileLoader("mv_mc_overview", mod_path)
    spec = importlib.util.spec_from_file_location("mv_mc_overview", mod_path, loader=loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)

    overview = mod.Overview()
    overview.show_all()
    GLib.idle_add(overview._start_entrance)
    deadline = time.time() + 5
    while time.time() < deadline:
        if Gtk.events_pending():
            Gtk.main_iteration()
        elif overview._anim_tick_id is None and not overview._animator.active:
            break
        else:
            time.sleep(0.01)
    try:
        if mct.ThumbnailCapture(display_name=":97").live_available:
            assert overview._live is not None and overview._live.started
            assert overview._live_capture.capturing
        else:
            assert overview._live is None           # graceful static fallback
        overview._begin_exit()
        deadline = time.time() + 3
        while time.time() < deadline:
            if Gtk.events_pending():
                Gtk.main_iteration()
            else:
                time.sleep(0.005)
                try:
                    if not overview.get_realized():
                        break
                except Exception:
                    break
        assert not overview.get_realized(), "exit choreography must destroy"
        assert overview._live is None
        assert overview._live_capture is None      # _teardown_live ran
    finally:
        try:
            overview.destroy()
        except Exception:
            pass
        while Gtk.events_pending():
            Gtk.main_iteration()
        d.screen().root.change_property(
            d.intern_atom("_NET_CLIENT_LIST"), Xatom.WINDOW, 32, [])
        d.sync()
        d.close()
    print("PASS: overview live session lifecycle + zero residual after exit")


TESTS = [
    test_live_start_requires_damage,
    test_live_lifecycle_and_refresh,
    test_live_refresh_placeholder_is_silent,
    test_live_readability_keeps_watch_on_errors,
    test_live_damage_refresh_xvfb,
    test_overview_live_session_lifecycle_xvfb,
]

if __name__ == "__main__":
    passed = failed = 0
    for test in TESTS:
        try:
            test()
            passed += 1
        except AssertionError as exc:
            print(f"FAIL: {test.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"ERROR: {test.__name__}: {type(exc).__name__}: {exc}")
            failed += 1
    print(f"Results: {passed} passed, {failed} failed out of {len(TESTS)}")
    raise SystemExit(1 if failed else 0)
