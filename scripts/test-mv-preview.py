#!/usr/bin/env python3
"""mv-preview contract suite: static half always, GUI half on the pinned Xvfb.

Static half locks the Preview surface against regressions that previously
shipped unnoticed:
  * the dead poppler API (render_to_pixbuf) that made every PDF open fail
    on current poppler-glib,
  * stub annotation buttons ("stub" markers, Sign tool),
  * missing zoom/fit-width/rotation/export contracts.

GUI half (real GTK, dedicated Xvfb :97, never the host display) drives the
window: zoom, rotation (size swap + annotation survival in page space),
markup commit/undo, per-page annotation separation, text-file view switch,
markup toolbar visibility per view mode.
"""
import os
import py_compile
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-preview")
DESKTOP = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/desktop/mv-preview.desktop")
SHOT = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-shot")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the Windows desktop).  gui_display() pins the
# dedicated Xvfb :97 — or returns None when headless — and arms the
# fail-loud guard (scripts/gui-guard/sitecustomize.py) for children.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso  # noqa: E402

HAS_DISPLAY = mv_gui_iso.gui_display() is not None

text = open(PATH, encoding="utf-8").read()

ok_count = 0
failures = []


def ok(name):
    global ok_count
    ok_count += 1
    print("ok - %s" % name)


def bad(name):
    failures.append(name)
    print("FAIL - %s" % name)


def check(name, cond):
    ok(name) if cond else bad(name)


def headless_suite():
    # --- render backend ---
    check("dead poppler API render_to_pixbuf is absent",
          "render_to_pixbuf" not in text)
    check("cairo render path _poppler_page_pixbuf present",
          "_poppler_page_pixbuf" in text and "page.render(cr)" in text)
    check("pixbuf extraction from surface",
          "Gdk.pixbuf_get_from_surface" in text)

    # --- honest annotation surface (no stubs) ---
    check("no stub markers left in mv-preview", "stub" not in text.lower())
    check("Sign tool removed (was a stub)", "tool_sign" not in text
          and '("Sign"' not in text)
    for tool in ("rect", "oval", "arrow", "sketch", "text"):
        check("markup tool '%s' present" % tool, '"%s"' % tool in text)
    check("markup commit on button-release",
          "on_button_release" in text and "append(draft)" in text)
    check("undo markup + Ctrl+Z binding",
          "def undo_markup" in text and '"z", "Z"' in text)
    check("markup color palette (macOS Markup-like swatches)",
          "#ff3b30" in text and "#007aff" in text and "swatch" in text)
    check("stroke width selector (Thin/Medium/Thick)",
          "STROKES" in text and "Thin" in text and "Thick" in text)

    # --- annotation coordinate model ---
    check("annotations keyed per (path, page)",
          "_ann_key" in text and "(self.current_path, self.page)" in text)
    check("annotations stored in page space (rot helpers)",
          "_rot_point" in text and "_unrot_point" in text)

    # --- zoom / fit / rotation ---
    check("zoom keys + and - and 0",
          '"plus", "equal", "KP_Add"' in text
          and '"minus", "underscore", "KP_Subtract"' in text
          and '"0", "KP_0"' in text)
    check("zoom clamp range constants", "ZOOM_MIN" in text and "ZOOM_MAX" in text)
    check("fit-width (w key) computed from viewport width",
          '"w", "W"' in text and "get_allocation().width" in text)
    check("rotate keys r / Shift+R",
          'key == "r"' in text and 'key == "R"' in text)
    check("rotation via pixbuf.rotate_simple with all 3 mappings",
          "rotate_simple" in text and "CLOCKWISE" in text
          and "UPSIDEDOWN" in text and "COUNTERCLOCKWISE" in text)
    check("rotation is per-file view state (rotations dict by path)",
          "self.rotations = {}" in text
          and "self.rotations.get(self.current_path, 0)" in text)
    check("render size cap against pathological zoom",
          "RENDER_MAX_PX" in text)
    check("Ctrl+scroll zooms",
          "ScrollDirection.UP" in text and "CONTROL_MASK" in text)

    # --- export ---
    check("export_png flattens via cairo surface",
          "def export_png" in text and "write_to_png" in text)
    check("export honors current rotation and markup",
          "_draw_ann(cr, ann, s, rot)" in text)
    check("export dialog is SAVE with overwrite confirmation",
          'FileChooserAction.SAVE' in text
          and "set_do_overwrite_confirmation(True)" in text)
    check("Ctrl+E export binding", '"e", "E"' in text)

    # --- formats ---
    check("text files viewable (.txt/.md/.log/.csv/.conf)",
          '".txt"' in text and '".md"' in text and '".log"' in text
          and "load_text" in text)
    check("pixbuf-native extra image formats (.ico/.xpm)",
          '".ico"' in text and '".xpm"' in text)
    check("text view is read-only monospace TextView",
          "set_monospace(True)" in text and "set_editable(False)" in text)
    check("markup toolbar hidden for text view",
          "markup_toolbar.set_visible(False)" in text)

    # --- preserved contracts ---
    check("Escape/q closes window",
          '"Escape", "q", "Q"' in text)
    check("page nav keys preserved (arrows/Home/End/n/p/space)",
          '"Home", "KP_Home"' in text and '"n", "N", "space"' in text)
    check("file nav Ctrl+arrows preserved",
          '"Left", "KP_Left", "Up", "KP_Up", "p", "P"' in text)
    check("fullscreen preserved (f/F11)", '"f", "F", "F11"' in text)
    check("Alt+1..6 tool shortcuts", '"1": "select"' in text
          and '"6": "text"' in text)
    check("menu export/zoom/rotate actions wired",
          "app.export-png" in text and "app.fit-width" in text
          and "app.rotate-right" in text)
    check("lazy poppler import (image-only open never loads poppler)",
          "_ensure_poppler" in text)

    # --- desktop entry matches reality ---
    dt = open(DESKTOP, encoding="utf-8").read()
    check("desktop MimeType has pdf/png/text",
          "application/pdf" in dt and "image/png" in dt
          and "text/plain" in dt)
    check("desktop MimeType drops unsupported postscript",
          "postscript" not in dt)

    # --- mv-shot handoff intact ---
    shot = open(SHOT, encoding="utf-8").read()
    check("mv-shot still hands off to mv-preview",
          'PREVIEW_APP = "mv-preview"' in shot)

    # --- compile ---
    try:
        py_compile.compile(PATH, doraise=True)
        ok("py_compile mv-preview")
    except py_compile.PyCompileError as e:
        bad("py_compile mv-preview: %s" % e)


def gui_suite():
    import cairo
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("mv_preview_mod", PATH)
    spec = importlib.util.spec_from_loader("mv_preview_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="mv-preview-suite.")
    png = os.path.join(tmp, "s.png")
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 400, 300)
    pix.fill(0x3a70b8ff)
    pix.savev(png, "png", [], [])
    txt = os.path.join(tmp, "s.txt")
    with open(txt, "w") as fh:
        fh.write("one\ntwo\nthree\n")

    win = mod.Preview([png, txt])
    win.show_all()
    state = {"rc": 0}

    class _E:
        button = 1

    def fail(name):
        state["rc"] = 1
        bad(name)

    def step():
        try:
            if win.view_mode != "graphic":
                fail("gui: graphic mode")
            else:
                ok("gui: graphic mode")
            win.zoom_in(None)
            good = win.zoom > 1.0
            win.zoom_actual(None)
            good = good and abs(win.zoom - 1.0) < 1e-9
            ok("gui: zoom in/actual") if good else fail("gui: zoom in/actual")

            win.set_tool("rect")
            win._draft = {"tool": "rect", "points": [(10, 10), (200, 150)],
                          "color": (1, 0, 0, 1), "width": 4.0}
            win.on_button_release(None, _E())
            n = len(win.annotations.get(win._ann_key(), []))
            ok("gui: markup committed") if n == 1 else fail("gui: markup committed")
            win.undo_markup(None)
            n = len(win.annotations.get(win._ann_key(), []))
            ok("gui: undo markup") if n == 0 else fail("gui: undo markup")

            win.rotate_right(None)
            swapped = (win.page_pixbuf.get_width(),
                       win.page_pixbuf.get_height()) == (600, 800)
            win.rotate_left(None)
            ok("gui: rotation swaps 400x300 -> 600x800") if swapped \
                else fail("gui: rotation swap")

            win.set_tool("arrow")
            win._draft = {"tool": "arrow", "points": [(5, 5), (380, 280)],
                          "color": (1, 0, 0, 1), "width": 4.0}
            win.on_button_release(None, _E())
            win.rotate_right(None)
            kept = len(win.annotations.get(win._ann_key(), [])) == 1
            win.rotate_left(None)
            ok("gui: annotation survives rotation (page space)") if kept \
                else fail("gui: annotation survives rotation")

            out = os.path.join(tmp, "export.png")
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32, win.page_pixbuf.get_width(),
                win.page_pixbuf.get_height())
            cr = cairo.Context(surface)
            Gdk.cairo_set_source_pixbuf(cr, win.page_pixbuf, 0, 0)
            cr.paint()
            for ann in win.annotations.get(win._ann_key(), []):
                win._draw_ann(cr, ann, win.render_scale_value,
                              win.rotations.get(win.current_path, 0))
            surface.write_to_png(out)
            ok("gui: flatten export written") if os.path.getsize(out) > 5000 \
                else fail("gui: flatten export written")

            win.navigate_file(1)
            text_ok = (win.view_mode == "text"
                       and win.text_view.get_buffer().get_line_count() == 4
                       and not win.markup_toolbar.get_visible())
            ok("gui: text view + hidden markup toolbar") if text_ok \
                else fail("gui: text view + hidden markup toolbar")
            win.navigate_file(-1)
            ok("gui: back to graphic") if win.view_mode == "graphic" \
                else fail("gui: back to graphic")
        finally:
            Gtk.main_quit()
        return False

    GLib.idle_add(step)
    GLib.timeout_add_seconds(20, Gtk.main_quit)
    Gtk.main()
    win.destroy()


def main():
    headless_suite()
    if HAS_DISPLAY:
        gui_suite()
    else:
        print("SKIP GUI smoke (headless)")
    print("passed %d, failed %d" % (ok_count, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
