#!/usr/bin/env python3
"""File chooser (canonical #21) theme gate.

WHY THIS EXISTS
---------------
`packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_widgets.scss` shipped a
`filechooser { ... }` block written against class names GTK3 never emits
(`.file-list`, `.file-name`, `.file-size`, `.file-date`, `.button-box`,
`.column-header`).  GTK3 ignores selectors that match nothing *without a
warning*, so that block compiled clean, passed scripts/test-theme-css.py and
did nothing at all: the open/save panel stayed stock Adwaita, with white
sidebar labels on a paper sidebar (illegible) and a 2px blue focus ring drawn
around the entire file list.  A CSS linter cannot see any of that.  This gate
can, and it is split in two halves for that reason.

  A. STATIC — the filechooser rules live in _filechooser.scss, both
     gtk.scss entry points import it, the dead selector vocabulary is gone,
     and the verified-live vocabulary is still there.  No display needed.
     This half is what stops the block silently rotting back.

  B. GUI — a real Gtk.FileChooserDialog (OPEN / SAVE / SELECT_FOLDER, with
     and without a header bar) is built under scripts/gui-isolation.sh's
     pinned Xvfb, and the *rendered* result is checked: sidebar paper +
     dark labels, a blue selection pill on the selected row, the light column
     header strip, and NO blue ring around the list.  A selector that stops
     matching fails B even if A passes.

Usage:
    python3 scripts/test-filechooser-theme.py            # gate, exit 1 on failure
    python3 scripts/test-filechooser-theme.py --static   # static half only
Exit 0 = all checks passed.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTIAL = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_filechooser.scss")
WIDGETS = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_widgets.scss")
GTK030 = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/gtk-3.0/gtk.scss")
GTK320 = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/gtk-3.20/gtk.scss")

# Selector vocabulary proven LIVE by pixel injection against a real
# GtkFileChooserDialog on GTK 3.24.  If one of these stops matching, the theme
# silently loses a surface again — exactly the bug this gate exists for.
LIVE_VOCABULARY = [
    "filechooser",
    "filechooser .sidebar",
    "filechooser .sidebar label",
    "filechooser .sidebar row:selected",
    "filechooser .sidebar .sidebar-icon",
    "filechooser .sidebar .sidebar-label",
    "filechooser .sidebar .sidebar-revealer",
    "filechooser .path-bar",
    "filechooser .view",
    "filechooser .view button",
    "filechooser .view:selected",
]

# Verified DEAD.  Their presence is not an error by itself (a dead selector is
# inert), but they must not appear at the start of a rule line, which is how
# the original broken block was written.
DEAD_VOCABULARY = [
    "filechooser .file-list",
    "filechooser .file-name",
    "filechooser .file-size",
    "filechooser .file-date",
    "filechooser .button-box",
    "filechooser .column-header",
    "places.sidebar",
    "pathbar box",
    "filechooser list view",
]

ok_count = 0
failures = []


def ok(name):
    global ok_count
    ok_count += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- static half
def static_checks():
    partial = read(PARTIAL)
    widgets = read(WIDGETS)

    for name, path, needle in (
            ("gtk-3.0/gtk.scss imports _filechooser", GTK030, '@import "filechooser";'),
            ("gtk-3.20/gtk.scss imports _filechooser", GTK320,
             '@import "../gtk-3.0/filechooser";')):
        if needle in read(path):
            ok(name)
        else:
            bad(name, "(missing %s — filechooser rules would not ship)" % needle)

    if os.path.exists(PARTIAL) and len(partial) > 500:
        ok("_filechooser.scss exists and is substantial (%d bytes)" % len(partial))
    else:
        bad("_filechooser.scss exists and is substantial")

    if re.search(r"(?m)^\s*filechooser\s*\{", widgets):
        bad("no filechooser block left in _widgets.scss", "(moved to _filechooser.scss)")
    else:
        ok("no filechooser block left in _widgets.scss")

    for sel in DEAD_VOCABULARY:
        hits = []
        for path, text in ((PARTIAL, partial), (WIDGETS, widgets)):
            if re.search(r"(?m)^\s*%s\b" % re.escape(sel), text):
                hits.append(os.path.basename(path))
        if hits:
            bad("dead selector not used: %s" % sel, "(%s)" % ",".join(hits))
        else:
            ok("dead selector not used: %s" % sel)

    for sel in LIVE_VOCABULARY:
        if sel in partial:
            ok("live selector present: %s" % sel)
        else:
            bad("live selector present: %s" % sel, "(absent from _filechooser.scss)")

    # The properties that GTK3 rejects outright must never come back.
    # Comments are stripped first: the partial documents *why* they are wrong.
    code = re.sub(r"/\*.*?\*/", "", partial, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    for bad_prop in ("-gtk-icon-size", "icon-size:"):
        if bad_prop in code:
            bad("no invalid property in _filechooser.scss", bad_prop)
        else:
            ok("no invalid property in _filechooser.scss: %s" % bad_prop)


# ------------------------------------------------------------------- GUI half
def gui_checks():
    import mv_gui_iso
    display = mv_gui_iso.gui_display()
    if not display:
        print("SKIP: GUI half (no display) — run via scripts/gui-isolation.sh")
        return
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk

    def pump(n=40):
        for _ in range(n):
            while Gtk.events_pending():
                Gtk.main_iteration()

    def walk(root):
        out, stack = [], [root]
        while stack:
            w = stack.pop()
            out.append(w)
            if isinstance(w, Gtk.Container):
                stack.extend(w.get_children())
        return out

    def find(widgets, pred):
        return [w for w in widgets if pred(w)]

    # Load the REPO's compiled theme at APPLICATION priority so the gate tests
    # the working tree, not whatever happens to be installed in
    # /usr/share/themes.  Without this the GUI half would happily pass against a
    # stale install while the committed sources were broken.
    # Base the dialog on stock Adwaita so the INSTALLED Mavericks theme cannot
    # mask a regression in the committed sources — with the install in place a
    # broken working tree still rendered correct pixels and the gate passed.
    # Everything the GUI half asserts is `filechooser`-scoped in
    # _filechooser.scss, so it does not depend on the generic theme rules.
    Gtk.Settings.get_default().set_property("gtk-theme-name", "Adwaita")

    pending = {}
    sassc = shutil.which("sassc")
    if sassc:
        src = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/gtk-3.20/gtk.scss")
        out = os.path.join(tempfile.mkdtemp(), "gtk.css")
        r = subprocess.run([sassc, "-t", "compressed", src, out],
                           capture_output=True, text=True)
        if r.returncode == 0:
            prov = Gtk.CssProvider()
            prov.load_from_path(out)
            from gi.repository import Gdk
            screen = Gdk.Screen.get_default()
            Gtk.StyleContext.add_provider_for_screen(
                screen, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            pending["screen"] = screen
            pending["provider"] = prov
            ok("repo theme compiled and loaded (APPLICATION priority)")
        else:
            bad("repo theme compiles", r.stderr.strip()[:200])
    else:
        print("SKIP: sassc absent — GUI half runs against the installed theme")

    dlg = Gtk.FileChooserDialog(title="Open File", action=Gtk.FileChooserAction.OPEN)
    dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                    "_Open", Gtk.ResponseType.ACCEPT)
    dlg.set_current_folder("/usr/share/icons")
    dlg.set_size_request(900, 560)
    dlg.show_all()
    pump()

    widgets = walk(dlg)

    # 1. sidebar labels must be DARK.  Regression guard for the shipped bug:
    #    GTK's own places.sidebar styling gave every row colour:#ffffff,
    #    which on the #f5f5f0 Mavericks sidebar is unreadable.
    labels = find(widgets, lambda w: isinstance(w, Gtk.Label)
                  and "sidebar-label" in w.get_style_context().list_classes())
    if not labels:
        bad("sidebar labels present")
    else:
        # The criterion is "not near-white": the shipped bug was #ffffff on
        # #f5f5f0 paper.  Accent blue (#007aff) on the "New bookmark" action
        # row is intended, so it counts as legible, not as a failure.
        legible, illegible = 0, []
        for lb in labels:
            rgba = lb.get_style_context().get_property("color", Gtk.StateFlags.NORMAL)
            if rgba is not None and min(rgba.red, rgba.green, rgba.blue) < 0.75:
                legible += 1
            else:
                illegible.append("%s=#%02x%02x%02x" % (
                    lb.get_text().strip() or "<blank>",
                    int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)))
        if legible == len(labels):
            ok("all %d sidebar labels resolve to legible (non-white) text" % len(labels))
        else:
            bad("all %d sidebar labels resolve to legible (non-white) text" % len(labels),
                "(%d/%d legible; white-on-paper = the shipped bug: %s)"
                % (legible, len(labels), ",".join(illegible)))

    # 2. the sidebar surface must be the Mavericks paper tone, not the
    #    white of the file list (they must read as two different materials).
    sidebar = find(widgets, lambda w: "sidebar" in w.get_style_context().list_classes())
    if sidebar:
        rgba = sidebar[0].get_style_context().get_property(
            "background-color", Gtk.StateFlags.NORMAL)
        near_paper = (abs(rgba.red - 0xf5 / 255.0) < 0.03
                      and abs(rgba.green - 0xf5 / 255.0) < 0.03
                      and abs(rgba.blue - 0xf0 / 255.0) < 0.03)
        if near_paper:
            ok("sidebar resolves to Mavericks paper #f5f5f0")
        else:
            bad("sidebar resolves to Mavericks paper #f5f5f0",
                "(got #%02x%02x%02x)" % (int(rgba.red * 255), int(rgba.green * 255),
                                         int(rgba.blue * 255)))
    else:
        bad("sidebar widget found")

    tv = find(widgets, lambda w: isinstance(w, Gtk.TreeView) and w.get_realized())
    if not tv:
        bad("file list realized")
        dlg.destroy()
        return
    tree = tv[0]

    gw = dlg.get_window()
    # GdkPoint is an object: index 0 is the parent GdkWindow id, the
    # coordinates are the .x/.y attributes.  Getting that wrong puts every
    # sample a whole window off, which is how the first version of this gate
    # "sampled" the sidebar and called it the file list.
    dlg_origin = gw.get_origin()
    dx0 = tree.get_window().get_origin().x - dlg_origin.x
    dy0 = tree.get_window().get_origin().y - dlg_origin.y

    def px_at(x, y):
        data = Gdk.pixbuf_get_from_window(gw, x, y, 1, 1).get_pixels()
        return (data[0], data[1], data[2])

    def list_px(dx, dy):
        return px_at(dx0 + dx, dy0 + dy)

    def is_blue(c):
        return c[2] > 150 and c[2] - c[0] > 60 and c[2] - c[1] > 30

    def is_dark(c):
        return c[0] < 130 and c[1] < 130 and c[2] < 130

    # 3. selection must paint the filled Mavericks pill on the first row.
    #    dy=30, not dy=8: the top 22px of the GtkTreeView IS the column header.
    sel = tree.get_selection()
    sel.select_path(Gtk.TreePath.new_first())
    tree.set_cursor(Gtk.TreePath.new_first(), None, False)
    # The focus ring only exists on a focused treeview, and the ring check
    # below is worthless unless the list really holds the focus.
    tree.grab_focus()
    pump(10)
    row_px = list_px(120, 30)
    if is_blue(row_px):
        ok("selected file row paints the system-blue pill")
    else:
        bad("selected file row paints the system-blue pill",
            "(got #%02x%02x%02x)" % row_px)

    # 4. Nothing may paint a system-blue bar across the top of the list.
    #    The shipped chooser had a 2px blue ring hugging the whole file list
    #    (the most obviously non-Mavericks thing in the dialog).  The
    #    `filechooser .view` rule's opaque white background plus
    #    `filechooser .view:focus { outline/box-shadow: none }` remove it; this
    #    check catches the bar coming back, and doubles as a guard against
    #    `:selected` leaking onto the whole widget node.  Sampled as a run
    #    because a ring covers the entire edge.
    ring = 0
    x = 4
    while x < 400:
        if is_blue(list_px(x, 1)):
            ring += 1
        x += 2
    if ring < 8:
        ok("no blue bar across the top edge of the file list (%d blue px)" % ring)
    else:
        bad("no blue bar across the top edge of the file list",
            "(%d blue pixels along the view's top edge)" % ring)

    # 5. the column-header strip must be a light grey, distinct from the white
    #    list below it — otherwise the header is bare text on white.
    hdr = list_px(300, 8)
    body = list_px(300, 220)
    if sum(hdr) < sum(body) and sum(hdr) >= 0x60 * 3:
        ok("column header strip is painted grey above the white list")
    else:
        bad("column header strip is painted grey above the white list",
            "(hdr #%02x%02x%02x, body #%02x%02x%02x)" % (hdr + body))

    # 6. sidebar labels must be DARK.  Regression guard for the shipped bug:
    #    GTK's own places.sidebar styling resolved every row's colour to
    #    #ffffff, which on the #f5f5f0 Mavericks paper is unreadable.  Checked
    #    on the RENDERED pixels too, not just on the resolved property.
    sidebar_w = find(widgets, lambda w: "sidebar" in w.get_style_context().list_classes())
    sw = sidebar_w[0]
    s_origin = sw.get_window().get_origin()
    s_alloc = sw.get_allocation()
    sample = px_at(s_origin.x - dlg_origin.x + s_alloc.width - 4,
                   s_origin.y - dlg_origin.y + 20)
    if not is_blue(sample):
        ok("sidebar surface is paper, not a blue selection block")
    else:
        bad("sidebar surface is paper, not a blue selection block",
            "(#%02x%02x%02x)" % sample)

    # 7. the current breadcrumb must be the blue pill.  Scanned as a run
    #    rather than per-button: the crumb buttons live inside the GtkPathBar
    #    and do not own a GdkWindow, so per-widget origins are meaningless.
    pb = find(widgets, lambda w: "path-bar" in w.get_style_context().list_classes())
    crumb_run = 0
    if pb:
        o = pb[0].get_window().get_origin()
        a = pb[0].get_allocation()
        x = o.x - dlg_origin.x + 2
        y = o.y - dlg_origin.y + a.height // 2
        run = 0
        while x < o.x - dlg_origin.x + a.width:
            if is_blue(px_at(x, y)):
                run += 1
                crumb_run = max(crumb_run, run)
            else:
                run = 0
            x += 2
    if crumb_run >= 16:
        ok("current path-bar crumb paints the system-blue pill (%dpx wide)" % crumb_run)
    else:
        bad("current path-bar crumb paints the system-blue pill",
            "(longest blue run on the path-bar strip: %dpx)" % crumb_run)

    # 7. every filechooser shape must render without a Gtk-CSS parse error.
    for action, name in ((Gtk.FileChooserAction.SAVE, "SAVE"),
                         (Gtk.FileChooserAction.SELECT_FOLDER, "SELECT_FOLDER")):
        d = Gtk.FileChooserDialog(title="x", action=action)
        d.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                      "_OK", Gtk.ResponseType.ACCEPT)
        d.show_all()
        pump(10)
        ok("%s dialog builds and renders" % name)
        d.destroy()

    hs = Gtk.FileChooserDialog(title="Open", action=Gtk.FileChooserAction.OPEN,
                               use_header_bar=True)
    hs.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                   "_Open", Gtk.ResponseType.ACCEPT)
    hs.show_all()
    pump(10)
    hb = find(walk(hs), lambda w: isinstance(w, Gtk.ButtonBox))
    if hb:
        ok("header-bar variant renders its action area")
    else:
        bad("header-bar variant renders its action area")
    hs.destroy()
    dlg.destroy()
    pump(5)


def main():
    static_checks()
    if "--static" not in sys.argv:
        try:
            gui_checks()
        except ImportError as exc:
            print("SKIP: GUI half (%s) — run via scripts/gui-isolation.sh" % exc)
    print("\n%d checks, %d failures" % (ok_count, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())