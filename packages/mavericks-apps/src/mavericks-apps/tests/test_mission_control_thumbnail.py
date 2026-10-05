#!/usr/bin/env python3
"""Headless unit tests for Mission Control thumbnail capture."""
import os
import sys
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import mission_control_thumbnail as mct

def test_mask_shift():
    assert mct._mask_shift(0x00FF0000) == (16, 8)
    assert mct._mask_shift(0x0000FF00) == (8, 8)
    assert mct._mask_shift(0x000000FF) == (0, 8)
    assert mct._mask_shift(0) == (0, 0)

def test_scale_channel():
    assert mct._scale_channel(255, 8) == 255
    assert mct._scale_channel(31, 5) == 255
    assert mct._scale_channel(0, 5) == 0

def test_image_to_rgb_32bit():
    image = mct._XImage()
    image.width, image.height = 1, 1
    image.bits_per_pixel, image.bytes_per_line, image.byte_order = 32, 4, 0
    image.red_mask, image.green_mask, image.blue_mask = 0x00FF0000, 0x0000FF00, 0x000000FF
    pixel = (0x12 << 16) | (0x34 << 8) | 0x56
    image.data = (mct.ctypes.c_ubyte * 4).from_buffer_copy(pixel.to_bytes(4, "little"))
    assert bytes(mct._image_to_rgb(image)) == b"\x12\x34\x56"

def test_image_to_rgb_16bit():
    image = mct._XImage()
    image.width, image.height = 1, 1
    image.bits_per_pixel, image.bytes_per_line, image.byte_order = 16, 2, 0
    image.red_mask, image.green_mask, image.blue_mask = 0xF800, 0x07E0, 0x001F
    image.data = (mct.ctypes.c_ubyte * 2).from_buffer_copy((0xF800).to_bytes(2, "little"))
    assert bytes(mct._image_to_rgb(image)) == b"\xFF\x00\x00"

def test_capture_failure_without_x11():
    with patch.object(mct, "_load_x11", side_effect=RuntimeError("no X11")):
        assert mct.capture_window(1) is None


import ctypes
import time
from ctypes import c_int, c_uint, c_ulong, POINTER


class _FakeLib:
    """Attribute bag standing in for a CDLL: plain callables per symbol."""

    def __init__(self, **fns):
        self._fns = fns

    def __getattr__(self, name):
        # Only called for attributes not found normally; expose fns directly
        raise AttributeError(name)

    def add(self, name, fn):
        self._fns[name] = fn
        setattr(self, name, fn)


def _make_fake_libs(damage_base=88, composite_ok=True):
    """Build a coherent set of fake x11/composite/damage/fixes libraries.

    Returns (libs_dict, calls_list) where calls_list accumulates
    (symbol, args-tuple) records for flow assertions.
    """
    calls = []

    def rec(name):
        def wrapper(*args):
            calls.append((name, args))
            return None
        return wrapper

    x11 = _FakeLib()
    comp = _FakeLib()
    dmg = _FakeLib()
    fx = _FakeLib()

    x11.add("XOpenDisplay", lambda name: 0x0D15)
    x11.add("XCloseDisplay", rec("XCloseDisplay"))
    x11.add("XSync", rec("XSync"))
    x11.add("XFlush", rec("XFlush"))
    x11.add("XPending", lambda dpy: 0)
    x11.add("XNextEvent", rec("XNextEvent"))
    x11.add("XConnectionNumber", lambda dpy: -1)
    x11.add("XFree", rec("XFree"))
    x11.add("XFreePixmap", rec("XFreePixmap"))
    x11.add("XSetErrorHandler", lambda h: 0x1234)
    x11.add("XDestroyImage", rec("XDestroyImage"))

    def fake_geometry(dpy, d, root_p, x_p, y_p, w_p, h_p, bw_p, depth_p):
        calls.append(("XGetGeometry", (dpy, d)))
        ctypes.cast(w_p, POINTER(c_uint)).contents.value = 8
        ctypes.cast(h_p, POINTER(c_uint)).contents.value = 6
        ctypes.cast(depth_p, POINTER(c_uint)).contents.value = 24
        return 1
    x11.add("XGetGeometry", fake_geometry)

    def fake_composite_version(dpy, maj_p, mnr_p):
        return 1 if composite_ok else 0
    comp.add("XCompositeQueryVersion", fake_composite_version)
    comp.add("XCompositeRedirectWindow", rec("XCompositeRedirectWindow"))
    comp.add("XCompositeUnredirectWindow", rec("XCompositeUnredirectWindow"))
    comp.add("XCompositeNameWindowPixmap", lambda dpy, w: 0)

    def fake_damage_query(dpy, ev_p, err_p):
        ctypes.cast(ev_p, POINTER(c_int)).contents.value = damage_base
        ctypes.cast(err_p, POINTER(c_int)).contents.value = damage_base + 1
        return 1
    dmg.add("XDamageQueryExtension", fake_damage_query)

    def fake_damage_create(dpy, w, lvl):
        calls.append(("XDamageCreate", (dpy, w, lvl)))
        return 0x99
    dmg.add("XDamageCreate", fake_damage_create)
    dmg.add("XDamageDestroy", rec("XDamageDestroy"))
    dmg.add("XDamageSubtract", rec("XDamageSubtract"))

    fx.add("XFixesQueryVersion", lambda dpy, a, b: 1)

    def fake_create_region(dpy, r, n):
        calls.append(("XFixesCreateRegion", (dpy, r, n)))
        return 0x77
    fx.add("XFixesCreateRegion", fake_create_region)
    fx.add("XFixesDestroyRegion", rec("XFixesDestroyRegion"))
    fx.add("XFixesFetchRegion", lambda dpy, r, n_p: None)
    fx.add("XFixesSubtractRegion", rec("XFixesSubtractRegion"))

    libs = {"x11": x11, "composite": comp, "damage": dmg, "fixes": fx}
    return libs, calls


def _build_ximage(w, h, pixels_bgra, depth=24):
    """Build a real _XImage struct backed by pixels_bgra; return (address, keepalive_tuple)."""
    import mission_control_thumbnail as mct
    data = ctypes.create_string_buffer(bytes(pixels_bgra), len(pixels_bgra))
    img = mct._XImage()
    img.width, img.height = w, h
    img.xoffset, img.format = 0, 2
    img.data = ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte))
    img.byte_order = 0
    img.bitmap_unit = img.bitmap_bit_order = img.bitmap_pad = 32
    img.depth = depth
    img.bytes_per_line = w * 4
    img.bits_per_pixel = 32
    img.red_mask, img.green_mask, img.blue_mask = 0xFF0000, 0xFF00, 0xFF
    return ctypes.addressof(img), (img, data)


def test_thumbnail_fit_dimensions():
    """Aspect-preserving fit: bounds, aspect, min 1, degenerate input."""
    import mission_control_thumbnail as mct
    fd = mct.fit_dimensions
    assert fd(800, 600, 200, 200) == (200, 150)
    assert fd(400, 300, 200, 100) == (133, 100)
    assert fd(100, 50, 400, 400) == (400, 200)      # upscale fills cell
    assert fd(64, 48, 32, 32) == (32, 24)
    assert fd(1, 1000, 100, 100) == (1, 100)
    assert fd(0, 100, 50, 50) == (1, 1)             # degenerate source
    assert fd(10, 10, 0, 0) == (1, 1)               # degenerate cell
    for (sw, sh, mw, mh) in [(800, 600, 200, 200), (1366, 768, 320, 240), (17, 33, 5, 5)]:
        w, h = fd(sw, sh, mw, mh)
        assert 1 <= w <= mw and 1 <= h <= mh
        # each axis within ~1px of the exact scaled size (int truncation)
        scale = min(mw / sw, mh / sh)
        assert abs(w - sw * scale) <= 1.25, (sw, sh, w, h)
        assert abs(h - sh * scale) <= 1.25, (sw, sh, w, h)
    print("PASS: test_thumbnail_fit_dimensions")


def test_thumbnail_bgra_to_rgba():
    """Channel swap, alpha forcing for depth 24, row stride padding."""
    import mission_control_thumbnail as mct
    # BGRA blue pixel -> RGBA (0,0,255)
    assert mct._bgra_to_rgba(bytes([255, 0, 0, 255]), 1, 1, 4, has_alpha=True) == bytes([0, 0, 255, 255])
    # depth-24: undefined 4th byte forced opaque
    assert mct._bgra_to_rgba(bytes([1, 2, 3, 0]), 1, 1, 4, has_alpha=False) == bytes([3, 2, 1, 255])
    # two pixels with per-row padding (stride 12 > 2*4)
    row = bytes([10, 20, 30, 0, 40, 50, 60, 0, 99, 99, 99, 99])
    out = mct._bgra_to_rgba(row, 2, 1, 12, has_alpha=True)
    assert out == bytes([30, 20, 10, 0, 60, 50, 40, 0]), out
    # two rows with padding: padding bytes ignored
    buf = row + row
    out2 = mct._bgra_to_rgba(buf, 2, 2, 12, has_alpha=False)
    assert out2 == bytes([30, 20, 10, 255, 60, 50, 40, 255]) * 2, out2
    print("PASS: test_thumbnail_bgra_to_rgba")


def test_thumbnail_scale_rgba():
    """Nearest rescale: identity, uniform step, general case, row pick."""
    import mission_control_thumbnail as mct
    sr = mct._scale_rgba
    red = bytes([255, 0, 0, 255])
    # identity
    assert sr(red * 4, 2, 2, 2, 2) == red * 4
    # 4x4 -> 2x2 solid stays solid
    assert sr(red * 16, 4, 4, 2, 2) == red * 4
    # uniform column step 4->2 picks every 2nd pixel
    row = bytes([10, 20, 30, 40]) * 4
    assert sr(row, 4, 1, 2, 1) == bytes([10, 20, 30, 40]) * 2
    # general non-uniform 3->2 (floor mapping [0,1])
    row3 = bytes([1, 1, 1, 255, 2, 2, 2, 255, 3, 3, 3, 255])
    assert sr(row3, 3, 1, 2, 1) == bytes([1, 1, 1, 255, 2, 2, 2, 255])
    # row nearest pick 6->2
    col = bytes([1, 1, 1, 255] * 3 + [9, 9, 9, 255] * 3)
    assert sr(col, 1, 6, 1, 2) == bytes([1, 1, 1, 255, 9, 9, 9, 255])
    # upscales row 2->4 (nearest duplicates pixels)
    two = bytes([5, 6, 7, 255]) * 2
    assert sr(two, 2, 1, 4, 1) == bytes([5, 6, 7, 255]) * 4
    # degenerate
    assert sr(b"", 0, 0, 4, 4) == b""
    assert sr(red, 1, 1, 0, 0) == b""
    print("PASS: test_thumbnail_scale_rgba")


def test_thumbnail_placeholder_pattern():
    """Deterministic checkerboard, correct size, cheap regeneration."""
    import mission_control_thumbnail as mct
    ph = mct._placeholder_rgba
    a = ph(64, 48)
    assert len(a) == 64 * 48 * 4
    assert a == ph(64, 48)                     # deterministic
    def px(buf, w, x, y): return tuple(buf[(y * w + x) * 4:(y * w + x) * 4 + 4])
    assert px(a, 64, 0, 0) == (214, 214, 214, 255)
    assert px(a, 64, 16, 0) == (152, 152, 152, 255)
    assert px(a, 64, 0, 16) == (152, 152, 152, 255)
    assert px(a, 64, 16, 16) == (214, 214, 214, 255)
    # odd sizes clamp fine
    b = ph(7, 5)
    assert len(b) == 7 * 5 * 4
    print("PASS: test_thumbnail_placeholder_pattern")


def test_thumbnail_parse_window_id():
    """int / '0x...' / decimal / garbage normalization."""
    import mission_control_thumbnail as mct
    n = mct._parse_window_id
    assert n("0x1a") == 26
    assert n("0X2B") == 43
    assert n(42) == 42
    assert n(" 7 ") == 7
    assert n(0) == 0
    assert n("zz") is None
    assert n("") is None
    assert n(None) is None
    assert n(-5) is None
    assert n(True) is None
    print("PASS: test_thumbnail_parse_window_id")


def test_thumbnail_no_display_raises():
    """No DISPLAY and no display_name -> RuntimeError (headless discipline)."""
    import mission_control_thumbnail as mct
    libs, _ = _make_fake_libs()
    saved = os.environ.pop("DISPLAY", None)
    try:
        try:
            mct.ThumbnailCapture(libs=libs)
            raise AssertionError("should have raised RuntimeError")
        except RuntimeError as e:
            assert "DISPLAY" in str(e)
    finally:
        if saved is not None:
            os.environ["DISPLAY"] = saved
    print("PASS: test_thumbnail_no_display_raises")


def test_thumbnail_forbidden_display_raises():
    """Displays in $MV_FORBIDDEN_DISPLAYS are refused (host display guard)."""
    import mission_control_thumbnail as mct
    libs, _ = _make_fake_libs()
    saved = os.environ.get("MV_FORBIDDEN_DISPLAYS")
    os.environ["MV_FORBIDDEN_DISPLAYS"] = ":0"
    try:
        try:
            mct.ThumbnailCapture(display_name=":0", libs=libs)
            raise AssertionError("should have raised RuntimeError")
        except RuntimeError as e:
            assert "forbidden" in str(e)
    finally:
        if saved is None:
            os.environ.pop("MV_FORBIDDEN_DISPLAYS", None)
        else:
            os.environ["MV_FORBIDDEN_DISPLAYS"] = saved
    print("PASS: test_thumbnail_forbidden_display_raises")


def test_thumbnail_placeholder_when_composite_missing():
    """XComposite unavailable -> deterministic placeholder, never an exception."""
    import mission_control_thumbnail as mct
    libs, calls = _make_fake_libs(composite_ok=False)
    tc = mct.ThumbnailCapture(display_name=":97", libs=libs)
    assert tc.available is False
    r = tc.capture_window("0x2a", 40, 30)
    assert r["placeholder"] is True
    assert r["width"] == 40 and r["height"] == 30 and r["stride"] == 160
    assert len(r["data"]) == 40 * 30 * 4
    assert "error" in r
    # no capture calls happened (only open/probes recorded)
    syms = [c[0] for c in calls]
    assert "XCompositeNameWindowPixmap" not in syms
    tc.close()
    print("PASS: test_thumbnail_placeholder_when_composite_missing")


def test_thumbnail_capture_flow_mock():
    """Happy-path capture flow via fake libs + a real XImage struct.

    Window 0x2a (42), pixmap 8x6 depth 24, blue pixels BGRA.
    Expect: redirect -> name pixmap -> geometry -> get image ->
    destroy image -> free pixmap -> unredirect, result 4x3 RGBA.
    """
    import mission_control_thumbnail as mct
    libs, calls = _make_fake_libs()

    # 8x6 solid blue BGRA (B=255, G=0, R=0, X=255)
    pixels = bytes([255, 0, 0, 255]) * (8 * 6)
    img_addr, keepalive = _build_ximage(8, 6, pixels)

    def fake_get_image(dpy, d, x, y, w, h, mask, fmt):
        calls.append(("XGetImage", (dpy, d, w, h)))
        return img_addr
    libs["x11"].add("XGetImage", fake_get_image)

    def fake_name_pixmap(dpy, w):
        calls.append(("XCompositeNameWindowPixmap", (dpy, w)))
        return 0xABC
    libs["composite"].add("XCompositeNameWindowPixmap", fake_name_pixmap)

    tc = mct.ThumbnailCapture(display_name=":97", libs=libs)
    r = tc.capture_window("0x2a", 4, 4)

    assert r["placeholder"] is False, r.get("error")
    assert r["win_id"] == 42
    assert (r["width"], r["height"]) == (4, 3), (r["width"], r["height"])
    assert r["stride"] == 16
    assert len(r["data"]) == 4 * 3 * 4
    assert tuple(r["data"][0:4]) == (0, 0, 255, 255), r["data"][0:4]  # RGBA blue

    syms = [c[0] for c in calls]
    for expected in ["XCompositeRedirectWindow", "XCompositeNameWindowPixmap",
                     "XGetGeometry", "XGetImage", "XDestroyImage",
                     "XFreePixmap", "XCompositeUnredirectWindow"]:
        assert expected in syms, f"missing call {expected} in {syms}"
    # redirect/unredirect got the normalized window id
    redir = [c for c in calls if c[0] == "XCompositeRedirectWindow"][0]
    assert redir[1][1] == 42
    unredir = [c for c in calls if c[0] == "XCompositeUnredirectWindow"][0]
    assert unredir[1][1] == 42
    tc.close()
    print("PASS: test_thumbnail_capture_flow_mock")


def test_thumbnail_capture_badpixmap_mock():
    """NameWindowPixmap -> 0 (unmapped window) -> placeholder + cleanup."""
    import mission_control_thumbnail as mct
    libs, calls = _make_fake_libs()
    libs["composite"].add("XCompositeNameWindowPixmap", lambda dpy, w: 0)
    libs["x11"].add("XGetImage", lambda *a: 0)

    tc = mct.ThumbnailCapture(display_name=":97", libs=libs)
    r = tc.capture_window(0x55, 20, 10)
    assert r["placeholder"] is True
    assert r["win_id"] == 0x55
    assert "error" in r
    syms = [c[0] for c in calls]
    assert "XGetImage" not in syms          # failed before pixel read
    assert "XCompositeUnredirectWindow" in syms  # cleanup still happens
    tc.close()
    print("PASS: test_thumbnail_capture_badpixmap_mock")


def test_thumbnail_capture_invalid_wid():
    """Unparseable window id -> placeholder without any X capture calls."""
    import mission_control_thumbnail as mct
    libs, calls = _make_fake_libs()
    tc = mct.ThumbnailCapture(display_name=":97", libs=libs)
    r = tc.capture_window("not-a-window", 8, 8)
    assert r["placeholder"] is True
    assert "error" in r
    syms = [c[0] for c in calls]
    assert "XCompositeRedirectWindow" not in syms
    assert "XCompositeNameWindowPixmap" not in syms
    tc.close()
    print("PASS: test_thumbnail_capture_invalid_wid")


def test_thumbnail_lifecycle_start_stop():
    """start_capture: redirect + damage + fixes region per window; stop undoes all."""
    import mission_control_thumbnail as mct
    libs, calls = _make_fake_libs()
    tc = mct.ThumbnailCapture(display_name=":97", libs=libs)
    assert tc.available

    cb = []
    ok = tc.start_capture([0x10, "0x20"], callback=lambda w, a: cb.append((w, a)))
    assert ok is True
    assert tc.capturing is True
    syms = [c[0] for c in calls]
    assert syms.count("XCompositeRedirectWindow") == 2
    assert syms.count("XDamageCreate") == 2
    assert syms.count("XFixesCreateRegion") == 2

    # idempotent: second start on same windows does not duplicate
    calls.clear()
    tc.start_capture([0x10, 0x20])
    syms = [c[0] for c in calls]
    assert syms.count("XDamageCreate") == 0

    tc.stop_capture()
    assert tc.capturing is False
    syms = [c[0] for c in calls]
    assert syms.count("XDamageDestroy") == 2
    assert syms.count("XFixesDestroyRegion") == 2
    assert syms.count("XCompositeUnredirectWindow") == 2

    # double stop is a no-op
    calls.clear()
    tc.stop_capture()
    assert [c[0] for c in calls] == []
    tc.close()
    assert "XCloseDisplay" in [c[0] for c in calls]
    print("PASS: test_thumbnail_lifecycle_start_stop")


def test_thumbnail_damage_poll_mock():
    """poll_damage: parses XDamageNotifyEvent, subtracts, fetches region bbox,
    fires callback; non-damage events skipped."""
    import mission_control_thumbnail as mct
    libs, calls = _make_fake_libs(damage_base=88)

    def craft_event(ev_type, drawable, x, y, w, h):
        ev = mct._XDamageNotifyEvent()
        ev.type = ev_type
        ev.drawable = drawable
        ev.area.x, ev.area.y, ev.area.width, ev.area.height = x, y, w, h
        return ctypes.string_at(ctypes.addressof(ev), ctypes.sizeof(ev))

    src_holder = [craft_event(88, 0x10, 1, 2, 3, 4)]

    def fake_next_event(dpy, buf):
        calls.append(("XNextEvent", (dpy,)))
        src = src_holder[0]
        ctypes.memmove(buf, src, len(src))
        return 0

    pending_returns = []

    def fake_pending(dpy):
        return pending_returns.pop(0) if pending_returns else 0

    # XFixesFetchRegion: 2 rectangles -> bbox (1,2)-(7,11) i.e. 6x9
    rects = (mct._XRectangle * 2)()
    rects[0].x, rects[0].y, rects[0].width, rects[0].height = 1, 2, 3, 4
    rects[1].x, rects[1].y, rects[1].width, rects[1].height = 4, 5, 3, 6

    def fake_fetch(dpy, region, n_p):
        calls.append(("XFixesFetchRegion", (dpy, region)))
        ctypes.cast(n_p, POINTER(c_int)).contents.value = 2
        return ctypes.addressof(rects)

    # NB: overrides must be installed BEFORE ThumbnailCapture binds them
    libs["x11"].add("XNextEvent", fake_next_event)
    libs["x11"].add("XPending", fake_pending)
    libs["fixes"].add("XFixesFetchRegion", fake_fetch)

    tc = mct.ThumbnailCapture(display_name=":97", libs=libs)
    cb = []
    tc.start_capture([0x10], callback=lambda w, a: cb.append((w, a)))

    # 1) damage event with fixes-region bbox
    pending_returns.extend([1, 0])
    events = tc.poll_damage()
    assert len(events) == 1, events
    e = events[0]
    assert e["win_id"] == 0x10
    assert e["area"] == {"x": 1, "y": 2, "width": 6, "height": 9}, e["area"]
    syms = [c[0] for c in calls]
    assert "XDamageSubtract" in syms
    assert "XFixesSubtractRegion" in syms       # parts region emptied
    assert "XFree" in syms                      # fetched rects freed
    assert cb and cb[0][0] == 0x10, cb

    # 2) non-damage event (type != damage_base) is skipped silently
    calls.clear()
    src_holder[0] = craft_event(999, 0x10, 0, 0, 5, 5)
    pending_returns.extend([1, 0])
    assert tc.poll_damage() == []
    assert "XDamageSubtract" not in [c[0] for c in calls]

    # 3) no events pending -> empty list, no X calls
    calls.clear()
    assert tc.poll_damage() == []
    assert [c[0] for c in calls] == []

    tc.stop_capture()
    tc.close()
    print("PASS: test_thumbnail_damage_poll_mock")


def test_thumbnail_integration_xvfb():
    """Integration on the pinned Xvfb :97 (auto-gated, no host display).

    Exercises the real XComposite/XDamage/XFixes stack: window content
    capture with pixel-exact assertions, damage lifecycle, multi-cycle
    stability (XEvent-192 heap-corruption regression) and read-only
    window state after captures.
    """
    import mission_control_thumbnail as mct
    disp = os.environ.get("DISPLAY", "")
    enabled = (disp == ":97") or os.environ.get("MV_MC_INTEGRATION") == "1"
    if not enabled:
        print("SKIP: test_thumbnail_integration_xvfb (DISPLAY=%r, set DISPLAY=:97 via gui-isolation.sh)" % disp)
        return

    c = ctypes
    x11 = mct._load_first_ctypes(mct._X11_LIB_NAMES)
    f_open = mct._bind_ctypes(x11, "XOpenDisplay", c.c_void_p, [c.c_char_p])
    f_root = mct._bind_ctypes(x11, "XDefaultRootWindow", c.c_ulong, [c.c_void_p])
    f_create = mct._bind_ctypes(x11, "XCreateSimpleWindow", c.c_ulong,
        [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_ulong])
    f_map = mct._bind_ctypes(x11, "XMapWindow", c.c_int, [c.c_void_p, c.c_ulong])
    f_sync = mct._bind_ctypes(x11, "XSync", c.c_int, [c.c_void_p, c.c_int])
    f_creategc = mct._bind_ctypes(x11, "XCreateGC", c.c_ulong,
                                 [c.c_void_p, c.c_ulong, c.c_ulong, c.c_void_p])
    f_setfg = mct._bind_ctypes(x11, "XSetForeground", c.c_int,
                              [c.c_void_p, c.c_ulong, c.c_ulong])
    f_fill = mct._bind_ctypes(x11, "XFillRectangle", c.c_int,
        [c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.c_uint, c.c_uint])

    probe = f_open(b":97")
    if not probe:
        print("SKIP: test_thumbnail_integration_xvfb (Xvfb :97 not reachable)")
        return
    mct._bind_ctypes(x11, "XCloseDisplay", c.c_int, [c.c_void_p])(probe)

    dpy = f_open(b":97")
    root = f_root(dpy)
    win = f_create(dpy, root, 0, 0, 64, 48, 0, 0, 0xFFFFFF)
    f_map(dpy, win)
    f_sync(dpy, 0)
    gc_ = f_creategc(dpy, win, 0, None)
    f_setfg(dpy, gc_, 0xFF0000)
    f_fill(dpy, win, gc_, 20, 20, 20, 20)
    f_sync(dpy, 0)

    tc = mct.ThumbnailCapture(display_name=":97")
    if not tc.available:
        tc.close()
        print("SKIP: test_thumbnail_integration_xvfb (no COMPOSITE on :97)")
        return

    try:
        # --- capture: dims + pixel-exact content
        r = tc.capture_window(win, 32, 32)
        assert r["placeholder"] is False, r.get("error")
        assert (r["width"], r["height"]) == (32, 24)
        data = r["data"]
        assert len(data) == 32 * 24 * 4
        px = lambda x, y: tuple(data[(y * 32 + x) * 4:(y * 32 + x) * 4 + 4])
        assert px(2, 2) == (255, 255, 255, 255), px(2, 2)
        assert px(15, 15) == (255, 0, 0, 255), px(15, 15)

        # --- capture: hex-string window id accepted
        r_hex = tc.capture_window(hex(win), 16, 16)
        assert r_hex["placeholder"] is False and r_hex["win_id"] == win

        # --- capture: fullscreen-size window within latency budget
        big = f_create(dpy, root, 0, 0, 1680, 1050, 0, 0, 0x3366CC)
        f_map(dpy, big)
        f_sync(dpy, 0)
        t0 = time.time()
        rb = tc.capture_window(big, 400, 400)
        dt_ms = (time.time() - t0) * 1000
        assert rb["placeholder"] is False, rb.get("error")
        assert (rb["width"], rb["height"]) == (400, 250)
        assert tuple(rb["data"][0:4]) == (0x33, 0x66, 0xCC, 255)
        assert dt_ms < 1500, f"capture too slow: {dt_ms:.0f}ms"

        # --- damage lifecycle
        cb = []
        assert tc.start_capture([win], callback=lambda w, a: cb.append((w, a))) is True
        tc.poll_damage(timeout_ms=1000)          # drain initial damage
        f_setfg(dpy, gc_, 0x00FF00)
        f_fill(dpy, win, gc_, 0, 0, 10, 10)
        f_sync(dpy, 0)
        evs = tc.poll_damage(timeout_ms=3000)
        assert any(e["win_id"] == win for e in evs), evs
        assert cb, "damage callback not fired"
        area = [e for e in evs if e["win_id"] == win][-1]["area"]
        assert area["x"] < 10 and area["y"] < 10 and area["width"] <= 10, area

        # --- recapture reflects damaged content
        r2 = tc.capture_window(win, 64, 64)
        assert r2["placeholder"] is False
        assert tuple(r2["data"][0:4]) == (0, 255, 0, 255), tuple(r2["data"][0:4])

        # --- multi-cycle stability (XEvent-192 heap-corruption regression)
        total = 0
        for i in range(30):
            f_fill(dpy, win, gc_, (i * 5) % 40, (i * 3) % 30, 6, 6)
            f_sync(dpy, 0)
            total += len(tc.poll_damage(timeout_ms=500))
        assert total >= 20, total
        junk = [dict(a=i, b=str(i)) for i in range(20000)]  # heap churn
        assert sum(d["a"] for d in junk) > 0

        # --- read-only guarantee: window still alive, geometry intact
        f_geom = mct._bind_ctypes(x11, "XGetGeometry", c.c_int,
            [c.c_void_p, c.c_ulong, POINTER(c_ulong), POINTER(c.c_int), POINTER(c.c_int),
             POINTER(c_uint), POINTER(c_uint), POINTER(c_uint), POINTER(c_uint)])
        root_p = c_ulong(0)
        gx, gy = c.c_int(0), c.c_int(0)
        gw, gh, gbw, gdepth = c_uint(0), c_uint(0), c_uint(0), c_uint(0)
        assert f_geom(dpy, win, ctypes.byref(root_p), ctypes.byref(gx), ctypes.byref(gy),
                      ctypes.byref(gw), ctypes.byref(gh), ctypes.byref(gbw),
                      ctypes.byref(gdepth)) != 0
        assert (gw.value, gh.value) == (64, 48), (gw.value, gh.value)

        tc.stop_capture()
        assert tc.capturing is False
        r3 = tc.capture_window(win, 32, 32)
        assert r3["placeholder"] is False
    finally:
        tc.close()

    # --- union: co-author's one-shot GdkPixbuf path on the same window.
    # Its precondition: the window is (manually or automatically) redirected
    # by a compositing manager (xfwm4 compositing is on in the production
    # config). Bare Xvfb has no compositor, so satisfy it explicitly.
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf  # noqa: F401
    except (ImportError, ValueError):
        print("SKIP: pixbuf one-shot path (PyGObject unavailable)")
    else:
        comp = mct._load_first_ctypes(mct._XCOMPOSITE_LIB_NAMES)
        f_redirect = mct._bind_ctypes(comp, "XCompositeRedirectWindow", c.c_int,
                                      [c.c_void_p, c.c_ulong, c.c_int])
        f_unredirect = mct._bind_ctypes(comp, "XCompositeUnredirectWindow", c.c_int,
                                        [c.c_void_p, c.c_ulong, c.c_int])
        f_redirect(dpy, win, 0)            # Automatic, like a compositor
        f_setfg(dpy, gc_, 0x3366CC)        # repaint AFTER redirect so the
        f_fill(dpy, win, gc_, 0, 0, 64, 48)  # new backing pixmap has content
        f_sync(dpy, 0)
        try:
            pb = mct.capture_window(win, (32, 32))
        finally:
            f_unredirect(dpy, win, 0)
            f_sync(dpy, 0)
        assert pb is not None, "pixbuf capture_window returned None on :97"
        assert pb.get_width() == 32 and pb.get_height() == 24, \
            (pb.get_width(), pb.get_height())
        assert pb.get_colorspace() == GdkPixbuf.Colorspace.RGB
        assert pb.get_n_channels() == 3, "alpha intentionally flattened to RGB"
        # solid 0x3366CC window: corners + center are (0x33, 0x66, 0xCC)
        px = pb.get_pixels()
        stride, nch = pb.get_rowstride(), pb.get_n_channels()
        offsets = [0, 23 * stride + 31 * nch, 12 * stride + 16 * nch]
        for off in offsets:
            assert px[off:off + 3] == b"\x33\x66\xcc", (off, px[off:off + 3].hex())
        print("PASS: pixbuf one-shot path on :97 (%dx%d)" % (pb.get_width(), pb.get_height()))

    print("PASS: test_thumbnail_integration_xvfb (%.0fms fullscreen capture)" % dt_ms)


TESTS = [test_mask_shift, test_scale_channel, test_image_to_rgb_32bit,
         test_image_to_rgb_16bit, test_capture_failure_without_x11,
         test_thumbnail_fit_dimensions, test_thumbnail_bgra_to_rgba,
         test_thumbnail_scale_rgba, test_thumbnail_placeholder_pattern,
         test_thumbnail_parse_window_id, test_thumbnail_no_display_raises,
         test_thumbnail_forbidden_display_raises,
         test_thumbnail_placeholder_when_composite_missing,
         test_thumbnail_capture_flow_mock, test_thumbnail_capture_badpixmap_mock,
         test_thumbnail_capture_invalid_wid, test_thumbnail_lifecycle_start_stop,
         test_thumbnail_damage_poll_mock, test_thumbnail_integration_xvfb]

if __name__ == "__main__":
    passed = 0
    failed = 0
    for test in TESTS:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"{passed}/{len(TESTS)} mission control thumbnail tests passed")
    if failed:
        raise SystemExit(1)
