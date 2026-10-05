#!/usr/bin/env python3
"""Mission Control O5 — workspace model / Spaces-strip previews tests.

Acceptance criteria (docs/MISSION_CONTROL_PLAN.md §5 O5):
- shows all workspaces as thumbnails at top of overview
- active workspace highlighted
- clicking workspace thumbnail switches to it
- empty workspaces shown as empty placeholders
- workspace count matches wmctrl -d

Headless part covers the pure layout math and the GdkPixbuf collage
(no display needed). Xvfb :97 part covers real captures, wmctrl -d
parity and the live Overview widget (guarded like every MC test:
DISPLAY must be the pinned :97, never the host display).
"""
import ctypes
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import mission_control as mc
import mission_control_previews as mcp


# ---------------------------------------------------------------- pure math

def test_place_windows_scales_geometry():
    windows = [{"win_id": "0x1", "geometry": {"x": 0, "y": 0, "width": 800, "height": 600}}]
    placed = mcp.place_windows(windows, 1600, 1200, 128, 80)
    assert len(placed) == 1
    p = placed[0]
    assert p["win_id"] == "0x1"
    # scale = min(128/1600, 80/1200) = 1/15; content is letterboxed
    # horizontally (ox ~= 11) and pad-clamped vertically.
    assert 10 <= p["x"] <= 12, p
    assert p["y"] == 2, p
    assert 52 <= p["w"] <= 54, p
    assert 38 <= p["h"] <= 40, p
    print("PASS: place_windows scales geometry into the thumbnail")


def test_place_windows_clamps_into_thumb():
    windows = [
        {"win_id": "0x2", "geometry": {"x": -500, "y": 900, "width": 1600, "height": 400}},
        {"win_id": "0x3", "geometry": {"x": 10000, "y": 0, "width": 100, "height": 100}},
    ]
    placed = mcp.place_windows(windows, 1600, 1200, 128, 80)
    assert len(placed) == 2
    for p in placed:
        assert 0 <= p["x"] and p["x"] + p["w"] <= 128, p
        assert 0 <= p["y"] and p["y"] + p["h"] <= 80, p
    print("PASS: place_windows clamps rects into the thumbnail")


def test_place_windows_skips_broken_geometry():
    windows = [
        {"win_id": "0x4", "geometry": {"x": 5, "y": 5, "width": 0, "height": 10}},
        {"win_id": "0x5", "geometry": {}},
        {"win_id": "0x6"},
    ]
    assert mcp.place_windows(windows, 1600, 1200, 128, 80) == []
    assert mcp.place_windows([], 1600, 1200, 128, 80) == []
    assert mcp.place_windows(windows, 0, 0, 128, 80) == []
    print("PASS: place_windows skips broken geometry")


# ------------------------------------------------------- GdkPixbuf collage

def _pixbuf_mod():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    return GdkPixbuf


def test_compose_preview_placeholder_tile():
    GdkPixbuf = _pixbuf_mod()
    placed = [{"win_id": "0x1", "x": 10, "y": 10, "w": 40, "h": 30}]
    preview = mcp.compose_preview(placed, 64, 48, capture_fn=lambda wid, size: None)
    assert preview is not None and preview.get_width() == 64
    px = preview.get_pixels()
    stride = preview.get_rowstride()
    # centre of the placed rect is the grey placeholder tile
    off = 25 * stride + 30 * 3
    assert tuple(px[off:off + 3]) == (0x9A, 0x9A, 0x9A), tuple(px[off:off + 3])
    # corner outside the placed rect is the fallback background
    off_corner = 2 * stride + 2 * 3
    assert tuple(px[off_corner:off_corner + 3]) == (0x2C, 0x3E, 0x50), \
        tuple(px[off_corner:off_corner + 3])
    print("PASS: compose_preview renders placeholder tiles + background")


def test_compose_preview_captures_rendered():
    GdkPixbuf = _pixbuf_mod()

    def fake_capture(win_id, size):
        pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, size[0], size[1])
        pb.fill(0xFF0000FF if win_id == "0x1" else 0x00FF00FF)
        return pb

    placed = [
        {"win_id": "0x1", "x": 0, "y": 0, "w": 40, "h": 40},
        {"win_id": "0x2", "x": 40, "y": 0, "w": 40, "h": 40},
    ]
    preview = mcp.compose_preview(placed, 80, 40, capture_fn=fake_capture)
    px = preview.get_pixels()
    stride = preview.get_rowstride()
    assert tuple(px[20 * stride + 20 * 3:20 * stride + 20 * 3 + 3]) == (255, 0, 0)
    assert tuple(px[20 * stride + 60 * 3:20 * stride + 60 * 3 + 3]) == (0, 255, 0)
    print("PASS: compose_preview renders captures at placed positions")


def test_build_previews_all_desktops_and_empty_placeholder():
    GdkPixbuf = _pixbuf_mod()
    saved_candidates = mcp.WALLPAPER_CANDIDATES
    mcp.WALLPAPER_CANDIDATES = ()  # force the solid fallback background
    try:
        by_desktop = {
            0: [{"win_id": "0x1", "geometry": {"x": 10, "y": 10, "width": 400, "height": 300}}],
            1: [],
        }
        previews = mcp.build_workspace_previews(
            by_desktop, 1600, 1200, (64, 48),
            capture_fn=lambda wid, size: None, desktop_count=3,
            wallpaper_path="/nonexistent.png",
        )
    finally:
        mcp.WALLPAPER_CANDIDATES = saved_candidates
    # every desktop (incl. the trailing empty one) gets a thumbnail
    assert sorted(previews.keys()) == [0, 1, 2], sorted(previews.keys())
    for preview in previews.values():
        assert preview is not None and preview.get_width() == 64
    # empty desktops: pure background, no placeholder tiles
    empty_px = previews[1].get_pixels()
    empty_stride = previews[1].get_rowstride()
    for x, y in ((5, 5), (32, 24), (58, 42)):
        off = y * empty_stride + x * 3
        assert tuple(empty_px[off:off + 3]) == (0x2C, 0x3E, 0x50), (x, y)
    # desktop 0 has exactly one grey placeholder tile over the background
    grey = sum(
        1
        for i in range(0, len(previews[0].get_pixels()), 3)
        if previews[0].get_pixels()[i:i + 3] == b"\x9a\x9a\x9a"
    )
    assert grey > 0, "expected a placeholder tile on desktop 0"
    print("PASS: build_workspace_previews covers all desktops; empty = background only")


# ------------------------------------------------------------- Xvfb :97

def _x97_ready():
    if os.environ.get("DISPLAY") != ":97":
        return False
    try:
        import mission_control_thumbnail as mct
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


def _wm_running():
    """True when a WM manages :97 (EWMH check window present)."""
    try:
        out = subprocess.run(
            ["xprop", "-root", "_NET_SUPPORTING_WM_CHECK"],
            capture_output=True, text=True, timeout=5,
            env=dict(os.environ, DISPLAY=":97"),
        )
        return "window id" in out.stdout
    except Exception:
        return False


def _x11_helpers():
    import mission_control_thumbnail as mct
    c = ctypes
    x11 = mct._load_first_ctypes(mct._X11_LIB_NAMES)
    f = lambda name, rest, args: mct._bind_ctypes(x11, name, rest, args)
    return x11, f


def test_workspace_count_matches_wmctrl_xvfb():
    """O5 acceptance: overview workspace count == wmctrl -d desktop count."""
    if not _x97_ready():
        print("SKIP: test_workspace_count_matches_wmctrl_xvfb (DISPLAY != :97)")
        return
    # Bare Xvfb (no WM): drive the root properties directly — wmctrl -d
    # reads the same EWMH properties, so parity is checkable without a WM.
    if _wm_running():
        print("SKIP: test_workspace_count_matches_wmctrl_xvfb (WM running; "
              "covered by the xfwm4 UI test below)")
        return
    from Xlib import display as xdisplay, Xatom
    d = xdisplay.Display(":97")
    root = d.screen().root
    try:
        for count in (1, 2, 3):
            root.change_property(
                d.intern_atom("_NET_NUMBER_OF_DESKTOPS"), Xatom.CARDINAL, 32, [count])
            root.change_property(
                d.intern_atom("_NET_CURRENT_DESKTOP"), Xatom.CARDINAL, 32, [0])
            d.sync()
            ws = mc.get_workspaces()
            out = subprocess.run(
                ["wmctrl", "-d"], capture_output=True, text=True, timeout=5,
                env=dict(os.environ, DISPLAY=":97"),
            )
            lines = len([l for l in out.stdout.splitlines() if l.strip()])
            assert ws["count"] == count, (ws, count)
            assert lines == count, (out.stdout, out.returncode, count)
    finally:
        root.change_property(
            d.intern_atom("_NET_NUMBER_OF_DESKTOPS"), Xatom.CARDINAL, 32, [1])
        d.sync()
        d.close()
    print("PASS: workspace count matches wmctrl -d for 1/2/3 desktops")


def test_workspace_previews_live_capture_xvfb():
    """Pixel-level: composed previews show real window content per Space."""
    if not _x97_ready():
        print("SKIP: test_workspace_previews_live_capture_xvfb (DISPLAY != :97)")
        return
    if _wm_running():
        print("SKIP: test_workspace_previews_live_capture_xvfb (needs bare Xvfb)")
        return

    import mission_control_thumbnail as mct
    from Xlib import display as xdisplay, Xatom

    d = xdisplay.Display(":97")
    root = d.screen().root
    c = ctypes
    x11, f = _x11_helpers()
    dpy = f("XOpenDisplay", c.c_void_p, [c.c_char_p])(b":97")
    root_id = f("XDefaultRootWindow", c.c_ulong, [c.c_void_p])(dpy)
    f_create = f("XCreateSimpleWindow", c.c_ulong,
        [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_ulong])
    f_map = f("XMapWindow", c.c_int, [c.c_void_p, c.c_ulong])
    f_sync = f("XSync", c.c_int, [c.c_void_p, c.c_int])
    f_creategc = f("XCreateGC", c.c_ulong, [c.c_void_p, c.c_ulong, c.c_ulong, c.c_void_p])
    f_setfg = f("XSetForeground", c.c_int, [c.c_void_p, c.c_ulong, c.c_ulong])
    f_fill = f("XFillRectangle", c.c_int,
        [c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.c_uint, c.c_uint])

    # Two desktops; a solid red window on 0, a solid green one on 1.
    root.change_property(d.intern_atom("_NET_NUMBER_OF_DESKTOPS"), Xatom.CARDINAL, 32, [2])
    root.change_property(d.intern_atom("_NET_CURRENT_DESKTOP"), Xatom.CARDINAL, 32, [0])
    d.sync()

    def make_window(x, y, w, h, color, desktop):
        win = f_create(dpy, root_id, x, y, w, h, 0, 0, color)
        f_map(dpy, win)
        f_sync(dpy, 0)
        gc = f_creategc(dpy, win, 0, None)
        f_setfg(dpy, gc, color)
        f_fill(dpy, win, gc, 0, 0, w, h)
        f_sync(dpy, 0)
        winobj = d.create_resource_object("window", win)
        winobj.change_property(
            d.intern_atom("_NET_WM_DESKTOP"), Xatom.CARDINAL, 32, [desktop])
        d.sync()
        return win

    red_win = make_window(100, 100, 320, 240, 0xFF0000, 0)
    green_win = make_window(500, 300, 320, 240, 0x00FF00, 1)
    # Bare Xvfb has no WM, so maintain _NET_CLIENT_LIST ourselves —
    # enumerate_windows() reads exactly this EWMH property.
    root.change_property(
        d.intern_atom("_NET_CLIENT_LIST"), Xatom.WINDOW, 32, [red_win, green_win])
    d.sync()
    time.sleep(0.2)

    try:
        windows = [w for w in mc.enumerate_windows()
                   if w["win_id"] in (hex(red_win), hex(green_win))]
        assert len(windows) == 2, [w["win_id"] for w in windows]
        by_desktop = {}
        for w in windows:
            by_desktop.setdefault(int(w["desktop"]), []).append(w)
        assert sorted(by_desktop.keys()) == [0, 1], by_desktop.keys()

        tc = mct.ThumbnailCapture(display_name=":97")

        def capture(win_id, size):
            r = tc.capture_window(win_id, size[0], size[1])
            if r["placeholder"]:
                return None
            return mcp.rgba_to_pixbuf(r)

        previews = mcp.build_workspace_previews(
            by_desktop, 1680, 1050, (84, 52),
            capture_fn=capture, desktop_count=2,
            wallpaper_path="/nonexistent.png",
        )
        assert sorted(previews.keys()) == [0, 1]

        def has_color(pb, rgb):
            px, stride = pb.get_pixels(), pb.get_rowstride()
            target = bytes(rgb)
            step = 3 * 4  # sample every 4th pixel — plenty for a solid fill
            for off in range(0, len(px) - 3, step):
                if px[off:off + 3] == target:
                    return True
            return False

        assert has_color(previews[0], (255, 0, 0)), "desktop 0 preview lacks red window"
        assert has_color(previews[1], (0, 255, 0)), "desktop 1 preview lacks green window"
        assert not has_color(previews[0], (0, 255, 0)), "red preview contaminated with green"
        assert not has_color(previews[1], (255, 0, 0)), "green preview contaminated with red"
        tc.close()
    finally:
        root.change_property(
            d.intern_atom("_NET_NUMBER_OF_DESKTOPS"), Xatom.CARDINAL, 32, [1])
        root.change_property(d.intern_atom("_NET_CURRENT_DESKTOP"), Xatom.CARDINAL, 32, [0])
        root.change_property(d.intern_atom("_NET_CLIENT_LIST"), Xatom.WINDOW, 32, [])
        d.sync()
        d.close()
    print("PASS: workspace previews compose real per-Space captures on :97")


def _start_xfwm4():
    """Start a private xfwm4 on :97; returns (proc, owned) or (None, False)."""
    if _wm_running():
        return None, False
    try:
        proc = subprocess.Popen(
            ["xfwm4", "--display", ":97"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except OSError:
        return None, False
    for _ in range(40):
        time.sleep(0.25)
        if _wm_running():
            return proc, True
        if proc.poll() is not None:
            return None, False
    proc.terminate()
    return None, False


def test_overview_strip_ui_xvfb():
    """Widget-level O5 acceptance on a real EWMH WM (xfwm4 on :97):
    thumbnails for all Spaces at top, active highlighted, click switches,
    empty Space = background-only placeholder."""
    if not _x97_ready():
        print("SKIP: test_overview_strip_ui_xvfb (DISPLAY != :97)")
        return
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except (ImportError, ValueError):
        print("SKIP: test_overview_strip_ui_xvfb (GTK3 unavailable)")
        return

    wm_proc, owned = _start_xfwm4()
    if not _wm_running():
        print("SKIP: test_overview_strip_ui_xvfb (could not start xfwm4)")
        return

    env97 = dict(os.environ, DISPLAY=":97")
    created = []
    try:
        import mission_control_thumbnail as mct
        c = ctypes
        x11, f = _x11_helpers()
        dpy = f("XOpenDisplay", c.c_void_p, [c.c_char_p])(b":97")
        root_id = f("XDefaultRootWindow", c.c_ulong, [c.c_void_p])(dpy)
        f_create = f("XCreateSimpleWindow", c.c_ulong,
            [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_ulong])
        f_map = f("XMapWindow", c.c_int, [c.c_void_p, c.c_ulong])
        f_sync = f("XSync", c.c_int, [c.c_void_p, c.c_int])
        for i, x in enumerate((60, 620)):
            win = f_create(dpy, root_id, x, 100 + 60 * i, 300, 200, 0, 0, 0x4466AA + i)
            f_map(dpy, win)
            f_sync(dpy, 0)
            created.append(win)
        subprocess.run(["wmctrl", "-n", "3"], env=env97, capture_output=True, timeout=5)
        # xfwm4 finishes its own EWMH setup asynchronously and may briefly
        # overwrite the count — re-assert until it settles.
        for _ in range(20):
            time.sleep(0.25)
            if mc.get_workspaces().get("count") == 3:
                break
            subprocess.run(["wmctrl", "-n", "3"], env=env97, capture_output=True, timeout=5)
        subprocess.run(["wmctrl", "-i", "-r", hex(created[1]), "-t", "1"],
                       env=env97, capture_output=True, timeout=5)
        for _ in range(10):
            time.sleep(0.2)
            windows = mc.enumerate_windows()
            if any(int(w.get("desktop", -1)) == 1 for w in windows):
                break
            subprocess.run(["wmctrl", "-i", "-r", hex(created[1]), "-t", "1"],
                           env=env97, capture_output=True, timeout=5)

        ws = mc.get_workspaces()
        assert ws["count"] == 3, ws
        out = subprocess.run(["wmctrl", "-d"], capture_output=True, text=True,
                             timeout=5, env=env97)
        lines = len([l for l in out.stdout.splitlines() if l.strip()])
        assert lines == 3, out.stdout

        import importlib.util
        import importlib.machinery
        mod_path = os.path.join(HERE, "..", "bin", "mv-mc-overview")
        loader = importlib.machinery.SourceFileLoader("mv_mc_overview", mod_path)
        spec = importlib.util.spec_from_file_location("mv_mc_overview", mod_path, loader=loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        assert mod._GTK_OK, "GTK import failed in mv-mc-overview"

        overview = mod.Overview()
        overview.show_all()
        deadline = time.time() + 5
        while Gtk.events_pending() and time.time() < deadline:
            Gtk.main_iteration()
        try:
            # 1. all workspaces have thumbnails in the strip
            previews = overview._workspace_preview_pixbufs
            assert sorted(previews.keys()) == [0, 1, 2], sorted(previews.keys())
            assert all(pb is not None for pb in previews.values())

            # 2. active workspace highlighted (toggle state)
            current = int(mc.get_workspaces().get("current", 0))
            active_buttons = [i for i, b in enumerate(overview._workspace_buttons)
                              if b.get_active()]
            assert active_buttons == [current], (active_buttons, current)

            # 3. empty Space = background-only placeholder (no grey tiles)
            empty_px = previews[2].get_pixels()
            assert b"\x9a\x9a\x9a" not in empty_px, "empty Space shows placeholder tiles"
            assert len(empty_px) == previews[2].get_rowstride() * previews[2].get_height()

            # 4. clicking a Space thumbnail switches to it
            target = 1 if current == 0 else 0
            overview._workspace_buttons[target].clicked()
            deadline = time.time() + 3
            while Gtk.events_pending() and time.time() < deadline:
                Gtk.main_iteration()
            time.sleep(0.3)
            after = int(mc.get_workspaces().get("current", -1))
            assert after == target, (after, target)
        finally:
            overview.destroy()
            while Gtk.events_pending():
                Gtk.main_iteration()
    finally:
        for win in created:
            try:
                f_kill = f("XDestroyWindow", None, [c.c_void_p, c.c_ulong])
                f_kill(dpy, win)
                f_sync(dpy, 0)
            except Exception:
                pass
        subprocess.run(["wmctrl", "-n", "1"], env=env97, capture_output=True, timeout=5)
        if owned and wm_proc and wm_proc.poll() is None:
            wm_proc.terminate()
            try:
                wm_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                wm_proc.kill()
    print("PASS: overview Spaces strip satisfies O5 acceptance on xfwm4/:97")


TESTS = [
    test_place_windows_scales_geometry,
    test_place_windows_clamps_into_thumb,
    test_place_windows_skips_broken_geometry,
    test_compose_preview_placeholder_tile,
    test_compose_preview_captures_rendered,
    test_build_previews_all_desktops_and_empty_placeholder,
    test_workspace_count_matches_wmctrl_xvfb,
    test_workspace_previews_live_capture_xvfb,
    test_overview_strip_ui_xvfb,
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
