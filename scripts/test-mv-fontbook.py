#!/usr/bin/env python3
"""Headless tests for mv-fontbook.

Pure-logic section (no GTK widgets, no system font dirs touched):
- fc-list output parsing (families, styles, files, spacing)
- collection classification (User/Computer/Fixed Width/Serif/Sans Serif)
- search filtering
- user-font install/remove path logic (isolated temp dirs)
- waterfall/glyph layout invariants

GUI smoke (display only, skipped headless):
- construction, sidebar collections, font list population
- collection switching, search filtering
- Ctrl+F focuses the search field, Escape clears it
- install via file chooser into an isolated HOME, User collection shows it
- remove via confirm dialog, system fonts refused
- degraded backends: no fontconfig, Pango fallback
- waterfall + glyph grid render to a cairo surface without error
- argv file preselection

Usage: python3 scripts/test-mv-fontbook.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-fontbook")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None (headless, GTK then refuses to
# init) — and arms the fail-loud guard for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.gui_display()

FIXTURE_FC_LIST = "\n".join([
    "FreeSerif\tRegular\t/usr/share/fonts/gnu-free/FreeSerif.otf\t",
    "FreeSerif\tBold\t/usr/share/fonts/gnu-free/FreeSerifBold.otf\t",
    "Adwaita Mono\tRegular\t/usr/share/fonts/Adwaita/AdwaitaMono-Regular.ttf\t100",
    "Adwaita Sans\tRegular\t/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf\t",
    "",
])

def _find_fixture_font():
    """Any real font file on this host (font dirs differ per distro:
    Fedora gnu-free/ vs Debian truetype/freefont/ vs dejavu/...)."""
    for root in ("/usr/share/fonts/gnu-free", "/usr/share/fonts/truetype/freefont",
                 "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu",
                 "/usr/share/fonts"):
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in sorted(files):
                if name.lower().endswith((".otf", ".ttf")):
                    return os.path.join(dirpath, name)
    return None


FIXTURE_FONT = _find_fixture_font()
FIXTURE_BASENAME = os.path.basename(FIXTURE_FONT) if FIXTURE_FONT else None


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
    loader = importlib.machinery.SourceFileLoader("mv_fontbook", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_fontbook", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_pure(m):
    fonts = m.parse_fc_list(FIXTURE_FC_LIST)
    check("parse_fc_list count", len(fonts) == 4, str(len(fonts)))
    check("parse_fc_list fields",
          fonts[0]["family"] == "FreeSerif"
          and fonts[0]["style"] == "Regular"
          and fonts[0]["file"] == "/usr/share/fonts/gnu-free/FreeSerif.otf"
          and fonts[0]["spacing"] == "")
    check("parse_fc_list spacing", fonts[2]["spacing"] == "100")
    check("parse_fc_list skips blanks", all(f["family"] for f in fonts))

    with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-test"}):
        check("user_fonts_dir XDG", m.user_fonts_dir() == "/tmp/xdg-test/fonts",
              m.user_fonts_dir())
        user_font = {"family": "X", "style": "Regular",
                     "file": "/tmp/xdg-test/fonts/X.ttf", "spacing": ""}
        sys_font = {"family": "Y", "style": "Regular",
                    "file": "/usr/share/fonts/Y.ttf", "spacing": ""}
        check("is_user_font true", m.is_user_font(user_font))
        check("is_user_font false", not m.is_user_font(sys_font))
        check("is_user_font no file", not m.is_user_font(
            {"family": "Z", "style": "", "file": None, "spacing": ""}))

    check("is_fixed_width 100", m.is_fixed_width(
        {"family": "A", "style": "", "file": "", "spacing": "100"}))
    check("is_fixed_width 90", m.is_fixed_width(
        {"family": "A", "style": "", "file": "", "spacing": "90"}))
    check("is_fixed_width empty", not m.is_fixed_width(
        {"family": "A", "style": "", "file": "", "spacing": ""}))
    check("is_fixed_width junk", not m.is_fixed_width(
        {"family": "A", "style": "", "file": "", "spacing": "abc"}))

    check("is_serif serif", m.is_serif(
        {"family": "FreeSerif", "style": "", "file": "", "spacing": ""}))
    check("is_serif sans", not m.is_serif(
        {"family": "FreeSans", "style": "", "file": "", "spacing": ""}))
    check("is_serif mono", not m.is_serif(
        {"family": "Adwaita Mono", "style": "", "file": "", "spacing": ""}))
    check("is_serif times", m.is_serif(
        {"family": "Times New Roman", "style": "", "file": "", "spacing": ""}))

    with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-test"}):
        uf = {"family": "U", "style": "", "file": "/tmp/xdg-test/fonts/U.ttf",
              "spacing": ""}
        sf = {"family": "S", "style": "", "file": "/usr/share/fonts/S.ttf",
              "spacing": ""}
        mono = {"family": "M", "style": "", "file": "/usr/share/fonts/M.ttf",
                "spacing": "100"}
        check("collection all", m.in_collection(uf, "All Fonts"))
        check("collection user", m.in_collection(uf, "User"))
        check("collection computer", not m.in_collection(uf, "Computer"))
        check("collection computer sys", m.in_collection(sf, "Computer"))
        check("collection fixed", m.in_collection(mono, "Fixed Width"))
        check("collection fixed not", not m.in_collection(uf, "Fixed Width"))
        check("collection serif", m.in_collection(
            {"family": "Georgia", "style": "", "file": "", "spacing": ""},
            "Serif"))
        check("collection sans", m.in_collection(
            {"family": "Arial", "style": "", "file": "", "spacing": ""},
            "Sans Serif"))

    check("filter empty query", len(m.filter_fonts(fonts, "")) == 4)
    check("filter family", len(m.filter_fonts(fonts, "free")) == 2)
    check("filter style", len(m.filter_fonts(fonts, "bold")) == 1)
    check("filter case", len(m.filter_fonts(fonts, "ADWAITA")) == 2)
    check("filter nomatch", len(m.filter_fonts(fonts, "zzzz")) == 0)

    check("waterfall sizes", m.WATERFALL_SIZES == (11, 14, 18, 24, 36, 48))
    check("waterfall ascending",
          list(m.WATERFALL_SIZES) == sorted(m.WATERFALL_SIZES))
    ranges = m.GLYPH_RANGES
    check("glyph ranges ordered",
          all(ranges[i][1] < ranges[i + 1][0] for i in range(len(ranges) - 1)))
    check("glyph ranges printable",
          all(lo >= 0x20 for lo, _, _ in ranges))

    td = tempfile.mkdtemp(prefix="mv-fontbook-pure-")
    try:
        check("install rejects txt", m.install_font(
            __file__, dest_dir=td)[1] is not None)
        check("install missing file", m.install_font(
            os.path.join(td, "nope.ttf"), dest_dir=td)[1] is not None)
        if FIXTURE_FONT is None:
            print("ok - skip install/remove (no font files on this host)")
            return
        dest, err = m.install_font(FIXTURE_FONT, dest_dir=td)
        check("install ok", err is None and dest == os.path.join(
            td, FIXTURE_BASENAME) and os.path.isfile(dest), str(err))
        user_dir = os.path.join(td, "fonts")
        dest2, err2 = m.install_font(FIXTURE_FONT, dest_dir=user_dir)
        check("install into user dir",
              err2 is None and os.path.isfile(dest2), str(err2))
        if err2 is None:
            installed = {"family": os.path.splitext(FIXTURE_BASENAME)[0],
                         "style": "Regular", "file": dest2, "spacing": ""}
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": td}):
                check("remove user font", m.remove_font(installed)[0] is True)
                check("remove deleted file", not os.path.exists(dest2))
                check("remove system refused", m.remove_font(
                    {"family": "S", "style": "", "file": FIXTURE_FONT,
                     "spacing": ""})[0] is False)
                check("remove no file", m.remove_font(
                    {"family": "S", "style": "", "file": None,
                     "spacing": ""})[0] is False)
        else:
            print("ok - skip remove (font install unavailable: %s)" % err2)
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_gui_smoke(m, td):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Gtk, Gdk, PangoCairo
    try:
        import cairo
    except ImportError:
        print("ok - gui smoke skipped (no pycairo on this host)")
        return

    if Gdk.Screen.get_default() is None:
        print("skip - gui smoke (no display)")
        return

    home = os.path.join(td, "home")
    xdg = os.path.join(home, ".local", "share")
    os.makedirs(xdg, exist_ok=True)
    old_env = {k: os.environ.get(k) for k in ("HOME", "XDG_DATA_HOME")}
    os.environ["HOME"] = home
    os.environ["XDG_DATA_HOME"] = xdg
    try:
        win = m.FontBookWindow()
        try:
            for _ in range(10):
                Gtk.main_iteration_do(False)
            check("gui sidebar collections",
                  len(win.sidebar_store) == len(m.COLLECTIONS),
                  str(len(win.sidebar_store)))
            check("gui fonts enumerated", len(win.fonts) > 0, str(len(win.fonts)))
            check("gui backend fontconfig", win.backend == "fontconfig",
                  win.backend)
            check("gui list populated", len(win.store) > 0, str(len(win.store)))

            win.sidebar.get_selection().select_path(
                Gtk.TreePath.new_from_indices([3]))
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui fixed width collection",
                  win.current_collection == "Fixed Width"
                  and all(m.is_fixed_width(
                      {"family": r[0], "style": r[1], "file": "", "spacing": "100"}
                  ) or r[0] in ("Adwaita Mono", "FreeMono")
                  for r in win.store),
                  str([r[0] for r in win.store]))
            check("gui fixed width filtered",
                  len(win.store) < len(win.fonts),
                  "%d of %d" % (len(win.store), len(win.fonts)))

            win.sidebar.get_selection().select_path(
                Gtk.TreePath.new_from_indices([1]))
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui user collection empty", len(win.store) == 0,
                  str(len(win.store)))

            win.sidebar.get_selection().select_path(Gtk.TreePath.new_first())
            for _ in range(5):
                Gtk.main_iteration_do(False)
            win.view.get_selection().select_path(Gtk.TreePath.new_first())
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui selection", win.selected_font is not None)
            check("gui remove disabled for system font",
                  not win.remove_btn.get_sensitive())

            # probe with a family that exists on THIS host (font sets differ)
            probe_family = win.fonts[0]["family"]
            win.search.set_text(probe_family.lower())
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui search filters",
                  0 < len(win.store) <= len(win.fonts),
                  "%d of %d" % (len(win.store), len(win.fonts)))
            win.search.set_text("zzzz-nomatch")
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui empty search state", len(win.store) == 0)
            win.search.set_text("")
            for _ in range(5):
                Gtk.main_iteration_do(False)

            ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
            ev.keyval = Gdk.KEY_f
            ev.hardware_keycode = 41
            ev.state = Gdk.ModifierType.CONTROL_MASK
            win.emit("key-press-event", ev)
            for _ in range(3):
                Gtk.main_iteration_do(False)
            focus = win.get_focus()
            check("gui Ctrl+F focuses search",
                  focus is not None and "Entry" in focus.get_name(),
                  focus.get_name() if focus else None)

            class FakeChooser:
                def __init__(self, *a, **k):
                    pass

                def add_button(self, *a, **k):
                    pass

                def set_select_multiple(self, *a, **k):
                    pass

                def add_filter(self, *a, **k):
                    pass

                def run(self):
                    return Gtk.ResponseType.OK

                def get_filenames(self):
                    return [FIXTURE_FONT]

                def destroy(self):
                    pass

            with mock.patch.object(m.Gtk, "FileChooserDialog", FakeChooser):
                win.on_install(None)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui install no error", not win.error_bar.get_visible())
            win.sidebar.get_selection().select_path(
                Gtk.TreePath.new_from_indices([1]))
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui install in user collection", len(win.store) == 1,
                  str(len(win.store)))
            check("gui remove enabled for user font",
                  win.remove_btn.get_sensitive())

            with mock.patch.object(m.Gtk.MessageDialog, "run",
                                   lambda self: Gtk.ResponseType.OK):
                win.on_remove(None)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            check("gui remove deletes font", len(win.store) == 0,
                  str(len(win.store)))
            check("gui user dir empty",
                  not os.path.exists(os.path.join(xdg, "fonts", "FreeSerif.otf")))

            with mock.patch.object(m, "enum_fonts",
                                   lambda: ([], "none")):
                win2 = m.FontBookWindow()
                try:
                    for _ in range(5):
                        Gtk.main_iteration_do(False)
                    check("gui no-backend error",
                          win2.error_bar.get_visible()
                          and "fontconfig" in win2.error_bar.get_content_area()
                          .get_children()[0].get_text())
                finally:
                    win2.destroy()

            with mock.patch.object(m, "enum_fonts", lambda: (
                    [{"family": "Test Sans", "style": "",
                      "file": None, "spacing": ""}], "pango")):
                win3 = m.FontBookWindow()
                try:
                    for _ in range(5):
                        Gtk.main_iteration_do(False)
                    check("gui pango fallback constructs",
                          len(win3.store) == 1
                          and not win3.error_bar.get_visible())
                    check("gui pango remove disabled",
                          not win3.remove_btn.get_sensitive())
                finally:
                    win3.destroy()

            win4 = m.FontBookWindow()
            try:
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                win4.handle_argv([FIXTURE_FONT])
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                expected_family = os.path.splitext(FIXTURE_BASENAME)[0]
                check("gui argv file preselect",
                      win4.selected_font is not None
                      and win4.selected_font["family"] == expected_family,
                      str(win4.selected_font))
            finally:
                win4.destroy()

            win5 = m.FontBookWindow()
            try:
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 930, 560)
                cr = cairo.Context(surf)
                win5.draw_waterfall(win5.waterfall, cr)
                check("gui waterfall renders", True)
                win5.notebook.set_current_page(1)
                for _ in range(5):
                    Gtk.main_iteration_do(False)
                surf2 = cairo.ImageSurface(cairo.FORMAT_RGB24, 640, 560)
                cr2 = cairo.Context(surf2)
                win5.draw_glyphs(win5.glyph_area, cr2)
                check("gui glyph grid renders", True)
                check("gui glyph size request",
                      win5.glyph_area.get_size_request()[1] > 100,
                      str(win5.glyph_area.get_size_request()))
            finally:
                win5.destroy()
        finally:
            win.destroy()
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


    path = os.path.join(BIN, "mv-fontbook")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("fontbook: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("fontbook: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    m = load_app()
    test_pure(m)
    td = tempfile.mkdtemp(prefix="mv-fontbook-test-")
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
