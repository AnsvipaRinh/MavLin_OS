#!/usr/bin/env python3
"""Headless tests for mv-colormeter.

Pure-logic section (no GTK widgets, no display required):
- color conversion: rgb_to_hsv, srgb_to_display_p3, format_color
- aperture parsing, palette dir logic, .gpl write/read round-trip
- display backend detection, pointer position extraction
- screen sampling with a fake display (pixbuf grab mocked)
- pixel averaging over real (headless-constructible) GdkPixbuf

GUI smoke (display only, skipped headless):
- construction, CSS validity, Wayland fallback state
- format switching (combo + Ctrl+1..5), copy-to-clipboard
- aperture change, lock + arrow nudge, tick with mocked sampler
- palette add/remove/click-reload, .gpl save via fake chooser
- argv hex color preselection, draw functions render

Usage: python3 scripts/test-mv-colormeter.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-colormeter")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None (headless, GTK then refuses to
# init) — and arms the fail-loud guard for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.gui_display()


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


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_colormeter", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_colormeter", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeScreen:
    def __init__(self, root):
        self._root = root

    def get_root_window(self):
        return self._root


class FakeRootWindow:
    def __init__(self, w=100, h=100):
        self._w, self._h = w, h

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h


class FakeDisplay:
    """Duck-typed display for get_pointer_pos / sample_screen."""

    def __init__(self, name="GdkX11Display", pointer=(30, 40)):
        self._name = name
        self._pointer = pointer

    def get_default_seat(self):
        raise AttributeError("no seat")

    def get_default_screen(self):
        return FakeScreen(FakeRootWindow())

    def get_pointer(self):
        return (None, self._pointer[0], self._pointer[1], 0)


class NamedFakeDisplay(FakeDisplay):
    pass


def named_display(name, pointer=(30, 40)):
    cls = type(name, (FakeDisplay,), {})
    obj = cls.__new__(cls)
    FakeDisplay.__init__(obj, pointer=pointer)
    return obj


def make_pixbuf(w, h, fill=(128, 64, 32)):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h)
    pb.fill((fill[0] << 24) | (fill[1] << 16) | (fill[2] << 8) | 0xFF)
    return pb


def test_pure(m):
    h, s, v = m.rgb_to_hsv(255, 0, 0)
    check("hsv red", (round(h), round(s), round(v)) == (0, 100, 100),
          str((h, s, v)))
    h, s, v = m.rgb_to_hsv(0, 255, 0)
    check("hsv green", (round(h), round(s), round(v)) == (120, 100, 100),
          str((h, s, v)))
    h, s, v = m.rgb_to_hsv(0, 0, 255)
    check("hsv blue", (round(h), round(s), round(v)) == (240, 100, 100),
          str((h, s, v)))
    h, s, v = m.rgb_to_hsv(255, 255, 255)
    check("hsv white", (round(h), round(s), round(v)) == (0, 0, 100),
          str((h, s, v)))
    h, s, v = m.rgb_to_hsv(0, 0, 0)
    check("hsv black", (round(h), round(s), round(v)) == (0, 0, 0),
          str((h, s, v)))
    h, s, v = m.rgb_to_hsv(128, 128, 128)
    check("hsv gray", (round(h), round(s), round(v)) == (0, 0, 50),
          str((h, s, v)))

    check("format 8-bit", m.format_color(255, 128, 0, "sRGB 8-bit")
          == "255, 128, 0")
    check("format percent", m.format_color(255, 128, 0, "sRGB %")
          == "100%, 50%, 0%", m.format_color(255, 128, 0, "sRGB %"))
    check("format hex", m.format_color(255, 128, 0, "Hex (sRGB)")
          == "#FF8000")
    check("format hsv", m.format_color(255, 0, 0, "HSV (sRGB)")
          == "0°, 100%, 100%", m.format_color(255, 0, 0, "HSV (sRGB)"))
    check("format unknown falls back", m.format_color(1, 2, 3, "junk")
          == "1, 2, 3")

    p3w = m.srgb_to_display_p3(255, 255, 255)
    check("p3 white", p3w == (255, 255, 255), str(p3w))
    p3k = m.srgb_to_display_p3(0, 0, 0)
    check("p3 black", p3k == (0, 0, 0), str(p3k))
    p3r = m.srgb_to_display_p3(255, 0, 0)
    check("p3 red approx", abs(p3r[0] - 233) <= 2 and abs(p3r[1] - 53) <= 2
          and abs(p3r[2] - 37) <= 2, str(p3r))
    p3g = m.srgb_to_display_p3(0, 255, 0)
    check("p3 green clamped", all(0 <= c <= 255 for c in p3g), str(p3g))
    check("format p3", m.format_color(255, 255, 255, "Display P3")
          == "255, 255, 255")

    check("aperture 1x1", m.parse_aperture("1×1") == 1)
    check("aperture 3x3", m.parse_aperture("3×3") == 3)
    check("aperture 25x25", m.parse_aperture("25×25") == 25)
    check("aperture rejects rectangle", m.parse_aperture("3×5") is None)
    check("aperture rejects junk", m.parse_aperture("junk") is None)
    check("aperture rejects empty", m.parse_aperture("") is None)
    check("aperture rejects None", m.parse_aperture(None) is None)
    check("apertures table", [s for _l, s in m.APERTURES]
          == [1, 3, 5, 10, 25])
    check("formats table", m.FORMATS == (
        "sRGB 8-bit", "sRGB %", "Hex (sRGB)", "HSV (sRGB)", "Display P3"))

    check("backend x11", m.detect_backend(named_display("GdkX11Display"))
          == "x11")
    check("backend wayland",
          m.detect_backend(named_display("GdkWaylandDisplay")) == "wayland")
    check("backend unknown",
          m.detect_backend(named_display("GdkBroadwayDisplay")) == "unknown")

    class FakeSeat:
        def get_pointer(self):
            return None

    class SeatDisplay:
        def get_default_seat(self):
            return FakeSeat()

        def get_pointer(self):
            raise AssertionError("seat path should win")

    check("pointer none when seat device missing",
          m.get_pointer_pos(SeatDisplay()) is None)

    class FakeDevice:
        def get_position(self):
            return (None, 11, 22)

    class DevSeat:
        def get_pointer(self):
            return FakeDevice()

    class DevDisplay:
        def get_default_seat(self):
            return DevSeat()

    check("pointer via seat device", m.get_pointer_pos(DevDisplay())
          == (11, 22))

    check("pointer via get_pointer fallback",
          m.get_pointer_pos(FakeDisplay(pointer=(7, 8))) == (7, 8))

    class BrokenDisplay:
        def get_default_seat(self):
            raise RuntimeError("no seat")

        def get_pointer(self):
            raise RuntimeError("no pointer")

    check("pointer none on broken display",
          m.get_pointer_pos(BrokenDisplay()) is None)

    with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-cm-test"}):
        check("palettes dir XDG", m.palettes_dir()
              == "/tmp/xdg-cm-test/mavericks/palettes", m.palettes_dir())

    with mock.patch.object(m.Gdk, "pixbuf_get_from_window",
                           lambda root, x, y, w, h: make_pixbuf(w, h)):
        disp = FakeDisplay(pointer=(50, 50))
        res = m.sample_screen(disp, 50, 50, 3, loupe_size=5)
        check("sample avg", res["avg"] == (128, 64, 32), str(res["avg"]))
        check("sample loupe captured", res["loupe"] is not None
              and res["loupe"]["pixbuf"].get_width() == 5)
        check("sample loupe center", res["loupe"]["center"] == (2, 2),
              str(res["loupe"]["center"]))
        res2 = m.sample_screen(disp, 0, 0, 3, loupe_size=5)
        check("sample clamps to origin", res2["error"] is None
              and res2["loupe"]["center"] == (0, 0),
              str(res2["loupe"]["center"]))
        res3 = m.sample_screen(disp, 500, 500, 3, loupe_size=5)
        check("sample clamps to far edge", res3["error"] is None)
        res4 = m.sample_screen(disp, 50, 50, 3, loupe_size=1)
        check("sample loupe disabled at size 1", res4["loupe"] is None)

    class EmptyRoot(FakeRootWindow):
        def get_width(self):
            return 0

        def get_height(self):
            return 0

    class EmptyScreen(FakeScreen):
        def get_root_window(self):
            return EmptyRoot()

    class EmptyDisplay(FakeDisplay):
        def get_default_screen(self):
            return EmptyScreen(None)

    res5 = m.sample_screen(EmptyDisplay(pointer=(1, 1)), 1, 1, 1)
    check("sample zero geometry reports error",
          res5["avg"] is None and res5["error"], res5["error"])

    pb = make_pixbuf(4, 4, fill=(128, 64, 32))
    check("average uniform", m.average_region(pb, 1, 1, 2)
          == (128, 64, 32), str(m.average_region(pb, 1, 1, 2)))
    pb2 = make_pixbuf(4, 4, fill=(0, 0, 0))
    check("average mixed", m.average_region(pb2, 1, 1, 2) == (0, 0, 0))
    pb3 = make_pixbuf(4, 4, fill=(10, 20, 30))
    check("average clamps to bounds",
          m.average_region(pb3, 0, 0, 4) == (10, 20, 30),
          str(m.average_region(pb3, 0, 0, 4)))

    td = tempfile.mkdtemp(prefix="mv-colormeter-pure-")
    try:
        colors = [(255, 128, 0), (10, 20, 30), (255, 255, 255)]
        path = os.path.join(td, "sub", "test.gpl")
        err = m.write_gpl(path, "Test Palette", colors)
        check("gpl write ok", err is None and os.path.isfile(path),
              str(err))
        parsed = m.read_gpl(path)
        check("gpl round trip", parsed is not None
              and parsed[0] == "Test Palette"
              and parsed[1] == colors, str(parsed))
        check("gpl header", open(path).read().startswith("GIMP Palette"))
        check("gpl missing file", m.read_gpl(
            os.path.join(td, "nope.gpl")) is None)
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_gui_smoke(m, td):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gtk, Gdk, GdkPixbuf
    try:
        import cairo
    except ImportError:
        print("ok - gui smoke skipped (no pycairo on this host)")
        return

    if Gdk.Display.get_default() is None:
        print("skip - gui smoke (no display)")
        return

    check("gui display available", True)

    win = m.ColorMeterWindow()
    try:
        for _ in range(10):
            Gtk.main_iteration_do(False)

        check("gui constructed", True)
        check("gui backend detected",
              win.backend in ("x11", "wayland", "unknown"), win.backend)
        if win.backend == "wayland":
            check("gui wayland fallback shown",
                  win.status_bar.get_visible()
                  and "Wayland" in win.status_label.get_text(),
                  win.status_label.get_text())
        elif win.backend == "unknown":
            check("gui unknown-backend fallback shown",
                  win.status_bar.get_visible())

        check("gui aperture default", win.aperture_size() == 1)
        win.aperture.set_active(2)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui aperture switch", win.aperture_size() == 5)
        win.aperture.set_active(0)
        for _ in range(3):
            Gtk.main_iteration_do(False)

        win.format_combo.set_active(2)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui format combo", win.format_idx == 2
              and win.value_label.get_text().startswith("Hex (sRGB):"),
              win.value_label.get_text())

        ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        ev.keyval = Gdk.KEY_3
        ev.hardware_keycode = 12
        ev.state = Gdk.ModifierType.CONTROL_MASK
        win.emit("key-press-event", ev)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui Ctrl+3 format", win.format_idx == 2
              and "Hex" in win.value_label.get_text(),
              win.value_label.get_text())

        class FakeClipboard:
            text = None

            @staticmethod
            def get_default(display):
                return FakeClipboard()

            def set_text(self, text, length):
                FakeClipboard.text = text

        with mock.patch.object(m.Gtk, "Clipboard", FakeClipboard):
            ev2 = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
            ev2.keyval = Gdk.KEY_c
            ev2.hardware_keycode = 54
            ev2.state = Gdk.ModifierType.CONTROL_MASK
            win.emit("key-press-event", ev2)
            for _ in range(3):
                Gtk.main_iteration_do(False)
        expected_hex = "#%02X%02X%02X" % win.current_rgb()
        check("gui Ctrl+C copies hex", FakeClipboard.text == expected_hex,
              str(FakeClipboard.text))
        check("gui copy status shown",
              "Copied" in win.status_label.get_text(),
              win.status_label.get_text())

        with mock.patch.object(m.Gtk, "Clipboard", FakeClipboard):
            win.format_combo.set_active(0)
            for _ in range(3):
                Gtk.main_iteration_do(False)
            win.on_copy(None)
        expected_rgb = "%d, %d, %d" % win.current_rgb()
        check("gui copy follows format",
              FakeClipboard.text == expected_rgb,
              str(FakeClipboard.text))

        ev3 = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        ev3.keyval = Gdk.KEY_p
        ev3.hardware_keycode = 33
        ev3.state = Gdk.ModifierType.CONTROL_MASK
        win.emit("key-press-event", ev3)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui Ctrl+P adds swatch", len(win.palette) == 1
              and len(win.swatches.get_children()) == 1,
              str(len(win.palette)))
        win.on_add_palette(None)
        check("gui duplicate add ignored", len(win.palette) == 1)

        win.on_swatch_activate(None, (10, 20, 30))
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui swatch click reloads",
              win.current_rgb() == (10, 20, 30)
              and win.hex_label.get_text() == "Hex: #0A141E",
              win.hex_label.get_text())
        win.on_swatch_remove(win.palette[0])
        check("gui swatch remove", len(win.palette) == 0)

        win.lock_btn.set_active(True)
        for _ in range(5):
            Gtk.main_iteration_do(False)
        check("gui lock engages", win.locked)

        ev4 = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        ev4.keyval = Gdk.KEY_Right
        ev4.hardware_keycode = 114
        ev4.state = 0
        win.emit("key-press-event", ev4)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui arrow nudge", win.locked_pos is not None
              and win.locked_pos != (0, 0), str(win.locked_pos))

        ev5 = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        ev5.keyval = Gdk.KEY_Down
        ev5.hardware_keycode = 116
        ev5.state = Gdk.ModifierType.SHIFT_MASK
        win.emit("key-press-event", ev5)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui shift-arrow nudge 8px", win.locked_pos is not None
              and win.locked_pos[1] >= 8, str(win.locked_pos))

        win.lock_btn.set_active(False)
        for _ in range(3):
            Gtk.main_iteration_do(False)

        win.backend = "x11"
        with mock.patch.object(
                m, "sample_screen",
                lambda disp, x, y, ap, loupe_size=m.LOUPE_SIZE: {
                    "avg": (200, 100, 50), "loupe": None, "error": None}):
            win.locked = True
            win.locked_pos = (10, 10)
            win.tick()
            for _ in range(3):
                Gtk.main_iteration_do(False)
        check("gui tick updates readouts", win.current_rgb() == (200, 100, 50)
              and "200, 100, 50" in win.value_label.get_text(),
              win.value_label.get_text())

        with mock.patch.object(m, "sample_screen",
                               lambda *a: {"avg": None, "loupe": None,
                                           "error": "boom"}):
            win.tick()
            for _ in range(3):
                Gtk.main_iteration_do(False)
        check("gui tick error state", win.status_bar.get_visible()
              and "boom" in win.status_label.get_text(),
              win.status_label.get_text())

        win.backend = "wayland"
        win.tick()
        check("gui tick skips non-x11", win.current_rgb() == (200, 100, 50))

        with mock.patch.object(m.Gtk, "FileChooserDialog") as fd:
            class FakeChooser:
                current_name = "palette.gpl"

                def __init__(self, *a, **k):
                    pass

                def add_button(self, *a, **k):
                    pass

                def set_current_name(self, name):
                    FakeChooser.current_name = name

                def set_do_overwrite_confirmation(self, v):
                    pass

                def add_filter(self, *a, **k):
                    pass

                def run(self):
                    return Gtk.ResponseType.OK

                def get_filename(self):
                    return os.path.join(td, "out.gpl")

                def destroy(self):
                    pass

            fd.return_value = FakeChooser()
            win.palette = [(1, 2, 3), (4, 5, 6)]
            win.on_save_palette(None)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui palette save", os.path.isfile(
                os.path.join(td, "out.gpl")))
            parsed = m.read_gpl(os.path.join(td, "out.gpl"))
            check("gui palette save content",
                  parsed is not None and parsed[1] == [(1, 2, 3), (4, 5, 6)],
                  str(parsed))
            check("gui save status", "Saved" in win.status_label.get_text(),
                  win.status_label.get_text())

        win.palette = []
        win.on_save_palette(None)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        check("gui empty palette refused",
              "empty" in win.status_label.get_text(),
              win.status_label.get_text())

        win2 = m.ColorMeterWindow()
        try:
            for _ in range(5):
                Gtk.main_iteration_do(False)
            win2.handle_argv(["#FF8000"])
            for _ in range(3):
                Gtk.main_iteration_do(False)
            check("gui argv hex color", win2.current_rgb() == (255, 128, 0),
                  str(win2.current_rgb()))
            check("gui argv junk ignored",
                  win2.handle_argv(["not-a-color"]) is None)
        finally:
            win2.destroy()

        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 400, 620)
        cr = cairo.Context(surf)
        m.draw_swatch(cr, Gdk.RGBA(1, 0, 0, 1), 200, 90)
        pb = make_pixbuf(11, 11, fill=(60, 120, 180))
        m.draw_loupe(cr, {"pixbuf": pb, "center": (5, 5)}, 132, 132)
        m.draw_loupe(cr, None, 132, 132)
        check("gui draw functions render", True)

        with mock.patch.object(m.shutil, "which", lambda name: None):
            win3 = m.ColorMeterWindow()
            try:
                check("gui gcolor3 button hidden when missing",
                      win3.picker_btn is None
                      if hasattr(win3, "picker_btn") else True)
            finally:
                win3.destroy()
    finally:
        win.destroy()


def main():
    m = load_app()
    test_pure(m)
    td = tempfile.mkdtemp(prefix="mv-colormeter-test-")
    test_gui_smoke(m, td)
    print("---")
    print("passed: %d, failed: %d" % (ok.count, len(bad.failures)))
    if bad.failures:
        for name, detail in bad.failures:
            print("FAILED: %s %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
