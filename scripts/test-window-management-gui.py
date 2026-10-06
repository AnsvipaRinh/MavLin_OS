#!/usr/bin/env python3
"""Window Management P0 (canonical #25) — live xfwm4 measurement + static audit.

Why this suite exists
---------------------
`docs/APPS.md` claimed a finished Mavericks window chrome: "67 XPM assets
covering all button states ... traffic-light XPMs with Mavericks gradients and
symbols".  That claim was never checked against a *running* window manager.
Reading the config proved nothing, because this repository has already shipped
three config-level illusions (dead panel theme, dead plank INI, chooser CSS
naming widgets GTK3 never emits).

So this suite starts the **real** xfwm4 4.20 on the project's pinned Xvfb
(:97, via scripts/gui-isolation.sh — never the host display), with a private
HOME / XDG tree / private D-Bus, and measures what it actually decorates:

  1. settings are live        — every declared xfwm4 property equals the value
                                 the settings daemon holds, which catches dead
                                 config AND a polluted test environment;
  2. traffic lights exist     — the title bar is grabbed through GDK and the
                                 red/amber/green discs are located in PIXELS,
                                 left to right, proving close-left ordering;
  3. an unfocused window keeps all three, muted to grey — macOS never removes
                                 them from a background window;
  4. the detector is not      — the same detector is run against a theme with
     vacuous                   the button pixmaps deleted and MUST find nothing;
  5. the buttons work         — real clicks: leftmost closes, middle iconifies,
                                 rightmost maximizes (macOS semantics);
  6. a zoomed window keeps a title bar — macOS 10.9 zoom, not full screen; with
                                 titleless_maximize the maximised window had no
                                 frame at all and no way to close itself;
  7. double-click zooms       — double_click_action=maximize, measured through
                                 _NET_WM_STATE on the live client;
  8. focus follows click      — clicking an unfocused window's title makes it
                                 _NET_ACTIVE_WINDOW (macOS click-to-focus model);
  9. Alt+Tab switches windows — through xfwm4's own key handler;
 10. snapping is OFF          — Mavericks never tiles; a real mouse drag to the
                                 screen edge must leave the window where it was
                                 dropped, while a snap-enabled control run
                                 proves the drag test is capable of detecting
                                 snapping at all;
 11. frame geometry is the theme's — borders match the artwork width, the title
                                 strip matches title-1-active.xpm, and themerc
                                 carries no inert frame_border_* keys;
 12. every XPM parses         — through GdkPixbuf, the same library xfwm4 uses,
                                 and matches tools/gen-xfwm-buttons.py, so the
                                 artwork cannot drift back into being broken.

What it cannot check here, and says so instead of pretending: the appearance of
the window shadow (the pinned display is shared, another suite's full-screen
window sits behind the test window, so a root grab cannot separate a 50%-opacity
shadow from the paint underneath) and Super-modified key grabs (a Super chord
never reaches the grab on this Xvfb, though Alt+Tab does).  Both are hardware
items in docs/NEEDS_HARDWARE_TEST.md § Window Management.

Run: python3 scripts/test-window-management-gui.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XFWM4_SRC = os.path.join(REPO, "configs/desktop/xfce/xfwm4.xml")
THEME_SRC = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/xfwm4")
SKEL_XFWM4 = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
          "xfce-perchannel-xml/xfwm4.xml")

PACKAGED_KEYS_XML = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/config/"
          "xfce4-keyboard-shortcuts.xml")
SKEL_KEYS_XML = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
          "xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml")

SCREEN_W, SCREEN_H = 1680, 1050

errors = []
checks = [0]


def ok(message):
    checks[0] += 1
    print("ok - %s" % message)


def fail(message):
    checks[0] += 1
    errors.append(message)
    print("FAIL - %s" % message)


def have(binary):
    return shutil.which(binary) is not None


def run(cmd, env=None, timeout=40):
    if isinstance(cmd, str):
        cmd = ["bash", "-c", cmd]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def sh(cmd, env=None):
    return run(cmd, env=env).stdout.strip()


# ---------------------------------------------------------------------------
# Static half: XPM integrity + config integrity (no display needed)
# ---------------------------------------------------------------------------

def xpm_entries(path):
    """Return (w, h, ncolors, cpp, color_lines, pixel_lines) for an XPM.

    The closing ``};`` is accepted glued to the last array element on the same
    line, because that is the form every distro-shipped xfwm4 pixmap uses and
    the form GdkPixbuf's current XPM decoder accepts (with ``};`` on its own
    line it fails with "Failed to parse array end").
    """
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        st = line.strip()
        if not st or st.startswith("/*") or st.startswith("static") or st.startswith("}"):
            continue
        st = st.rstrip(",")
        if st.endswith("};"):
            st = st[:-2].rstrip()
        if not (st.startswith('"') and st.endswith('"')):
            return None
        out.append(st[1:-1])
    if not out:
        return None
    try:
        w, h, nc, cpp = (int(x) for x in out[0].split()[:4])
    except ValueError:
        return None
    return w, h, nc, cpp, out[1:1 + nc], out[1 + nc:]


def audit_xpm_integrity():
    """Every theme pixmap must be loadable by the library xfwm4 actually uses.

    xfwm4 opens <name>-active.xpm etc. and hands the bytes to GdkPixbuf; a
    malformed palette makes it bail and the button is drawn as *nothing*.  A
    structural check catches the same class of defect without a display, and a
    GdkPixbuf check proves it against the real decoder.
    """
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        have_pixbuf = True
    except Exception:
        have_pixbuf = False

    files = sorted(f for f in os.listdir(THEME_SRC) if f.endswith(".xpm"))
    if not files:
        fail("xfwm4 theme dir has no XPM assets: %s" % THEME_SRC)
        return

    broken = 0
    for name in files:
        path = os.path.join(THEME_SRC, name)
        parsed = xpm_entries(path)
        if parsed is None:
            fail("%s is not a well-formed XPM (header/quoting)" % name)
            broken += 1
            continue
        w, h, nc, cpp, colors, pixels = parsed
        problems = []
        if len(colors) != nc:
            problems.append("%d colour lines, header says %d" % (len(colors), nc))
        if len(pixels) != h:
            problems.append("%d pixel rows, header says %d" % (len(pixels), h))
        need = w * cpp
        for i, row in enumerate(pixels):
            if len(row) != need:
                problems.append("pixel row %d is %d chars, needs %d"
                                % (i, len(row), need))
        keys = []
        for c in colors:
            # Greedy key: a single-space colour key (" c #fff") is legal XPM and
            # common in these assets, so the key must be everything left of the
            # LAST "<class> <value>" pair rather than a \S+ token.
            m = re.match(r"^(?P<key>.*)\s+(?P<cls>[cmgs])\s+(?P<val>\S+)$", c)
            if not m:
                problems.append("colour line %r has no colour class" % c)
                keys.append(None)
            else:
                keys.append(m.group("key"))
        if None not in keys:
            used = set()
            for row in pixels:
                used |= {row[i:i + cpp] for i in range(0, len(row) - cpp + 1, cpp)}
            for k in keys:
                if len(k) != cpp:
                    problems.append("colour key %r is not %d char(s)" % (k, cpp))
            missing = sorted(u for u in used if u not in keys)
            if missing:
                problems.append("pixel rows use undefined colour keys %r" % (missing[:4],))
        if problems:
            fail("%s: %s" % (name, "; ".join(problems[:3])))
            broken += 1
            continue
        if have_pixbuf:
            try:
                GdkPixbuf.Pixbuf.new_from_file(path)
            except Exception as exc:
                fail("%s is rejected by GdkPixbuf (the xfwm4 decoder): %s"
                     % (name, " ".join(str(exc).split())[:70]))
                broken += 1
    if broken == 0:
        ok("all %d xfwm4 XPM assets are structurally valid" % len(files))
        if have_pixbuf:
            ok("all xfwm4 XPM assets decode through GdkPixbuf (xfwm4's own loader)")

    # The button artwork is generated (tools/gen-xfwm-buttons.py): a checked-in
    # hand-edited pixmap is exactly how this theme lost its buttons, so drift
    # between generator and assets is a failure, not a preference.
    gen = os.path.join(REPO, "tools/gen-xfwm-buttons.py")
    if os.path.isfile(gen):
        r = run([sys.executable, gen, "--check"])
        if r.returncode != 0:
            fail("generated button assets are stale — re-run "
                 "tools/gen-xfwm-buttons.py (%s)"
                 % " ".join(r.stdout.split()[-6:]))
        else:
            ok("button assets match tools/gen-xfwm-buttons.py output")
    else:
        fail("tools/gen-xfwm-buttons.py is missing: the button artwork would "
             "be hand-edited again")

    # Button assets xfwm4 demonstrably asks for (names proven by strace on
    # 4.20.0, not guessed from documentation).
    required = []
    for base in ("close", "hide", "maximize"):
        for state in ("active", "inactive", "prelight", "pressed"):
            required.append("%s-%s.xpm" % (base, state))
    for base in ("maximize", "shade", "stick"):
        for state in ("active", "inactive", "prelight", "pressed"):
            required.append("%s-toggled-%s.xpm" % (base, state))
    missing = [n for n in required if not os.path.isfile(os.path.join(THEME_SRC, n))]
    if missing:
        fail("xfwm4 button assets missing: %s" % " ".join(missing))
    else:
        ok("every button state xfwm4 opens is present (%d files)" % len(required))


def audit_config():
    src = open(XFWM4_SRC, encoding="utf-8").read()
    skel = open(SKEL_XFWM4, encoding="utf-8").read()
    if src != skel:
        fail("xfwm4.xml skel mirror differs from configs/desktop/xfce/xfwm4.xml")
    else:
        ok("xfwm4.xml skel mirror is byte-identical")

    def prop(name):
        m = re.search(r'name="%s" type="[^"]+" value="([^"]*)"' % re.escape(name), src)
        return m.group(1) if m else None

    layout = prop("button_layout")
    # xfwm4 button_layout alphabet (theme.c): O menu, C close, H hide,
    # M maximize, S stick, T shade, '|' separator.  Anything else is ignored.
    legal = set("OCHMST|")
    if layout is None:
        fail("button_layout missing")
    elif any(ch not in legal for ch in layout):
        fail("button_layout %r contains characters xfwm4 ignores (%s)"
             % (layout, "".join(sorted(set(layout) - legal))))
    else:
        ok("button_layout %r uses only xfwm4 button characters" % layout)
        if layout.startswith("CHM"):
            ok("button_layout puts Close/Hide/Maximize on the LEFT (macOS)")
        else:
            fail("button_layout %r does not put close first" % layout)

    theme_rc = os.path.join(THEME_SRC, "themerc")
    rc = open(theme_rc, encoding="utf-8").read()
    rc_layout = re.search(r"^button_layout=(.*)$", rc, re.M)
    rc_layout = rc_layout.group(1).strip() if rc_layout else None
    if rc_layout and any(ch not in legal for ch in rc_layout):
        fail("themerc button_layout %r contains characters xfwm4 ignores" % rc_layout)
    elif rc_layout:
        ok("themerc button_layout %r uses only xfwm4 button characters" % rc_layout)

    # Title font must agree with the GTK UI font the rest of the desktop uses.
    xs = os.path.join(REPO, "configs/desktop/xfce/xsettings.xml")
    gtk_font = None
    m = re.search(r'name="FontName" type="string" value="([^"]*)"',
                  open(xs, encoding="utf-8").read())
    gtk_font = m.group(1) if m else None
    title_font = prop("title_font")
    if title_font and gtk_font and title_font != gtk_font:
        fail("window title font %r differs from the desktop UI font %r — title "
             "bars would render in a different face than every application"
             % (title_font, gtk_font))
    elif title_font:
        ok("window title font matches the desktop UI font (%s)" % title_font)

    # macOS has no tiling/snapping: the whole concept must be off explicitly
    # rather than left to whatever this xfwm4 build defaults to.
    for key in ("snap_to_windows", "snap_to_border", "tile_on_move"):
        value = prop(key)
        if value is None:
            fail("%s not set — snapping state is left to the xfwm4 build default" % key)
        elif value != "false":
            fail("%s=%s but Mavericks does not snap/tile windows" % (key, value))
        else:
            ok("%s=false (Mavericks does not snap or tile)" % key)

    # A maximised window must keep its title bar: macOS 10.9 reserves "hide the
    # title bar" for true full screen, and a zoomed window whose traffic lights
    # are gone can no longer be closed or minimised from its own chrome.
    if prop("titleless_maximize") != "false":
        fail("titleless_maximize=%s — a zoomed window would lose its title "
             "bar and therefore its close/minimise buttons, which macOS 10.9 "
             "keeps" % prop("titleless_maximize"))
    else:
        ok("titleless_maximize=false — a zoomed window keeps its title bar "
           "(macOS 10.9 zoom, not full screen)")

    # Shadows come from the compositor; §4 wants them on and heavy effects off,
    # so each shadow switch is stated rather than inherited from a build default.
    for key, want in (("use_compositing", "true"), ("show_frame_shadow", "true"),
                      ("show_dock_shadow", "true"), ("show_popup_shadow", "true"),
                      ("shadow_opacity", "50"), ("vblank_mode", "off"),
                      ("unredirect_overlays", "true")):
        value = prop(key)
        if value != want:
            fail("xfwm4 %s=%s, expected %s" % (key, value, want))
    ok("compositor shadows are switched on explicitly (frame, dock, popup) "
       "with heavy effects off (vblank off, unredirected overlays)")

    for key, want in (("click_to_focus", "true"), ("focus_delay", "0"),
                      ("raise_on_click", "true"), ("raise_on_focus", "false"),
                      ("double_click_action", "maximize"),
                      ("title_alignment", "center"),
                      ("use_compositing", "true")):
        value = prop(key)
        if value != want:
            fail("xfwm4 %s=%s, expected %s" % (key, value, want))
    ok("focus-follows-click model, centred title, zoom-on-double-click and "
       "compositing (for shadows) all set as Mavericks needs")


def audit_window_bindings():
    """The macOS window operations this layer owns must be bound exactly once.

    Window Management (#25) does not own the hotkey registry — mv_hotkeys_core
    does — so these bindings are asserted *through* the registry: the same
    accelerator must appear exactly once across every managed action, and it
    must be an xfwm4-branch action (xfwm4's own key handler, no resident
    process).  A second row with the same chord would make one of them dead.
    """
    core_path = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/lib",
                             "mv_hotkeys_core.py")
    if not os.path.isfile(core_path):
        fail("mv_hotkeys_core.py is missing — window bindings cannot be checked")
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("mv_hotkeys_core", core_path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)

    wanted = {
        "switch_window_key": "Super+grave",      # macOS Command-`
        "fullscreen_key": "Super+Ctrl+F",        # macOS Control-Command-F
    }
    seen = {}
    for row in core.ACTIONS:
        accel = core.modifier_identity(
            core.normalize_accelerator(row)["modifiers"])
        seen.setdefault((accel, core.normalize_accelerator(row)["key"]),
                        []).append(row["action"])
    for command, expected in wanted.items():
        rows = [r for r in core.ACTIONS if r["command"] == command]
        if len(rows) != 1:
            fail("%s is bound %d times in the registry, expected once"
                 % (command, len(rows)))
            continue
        row = rows[0]
        got = core.display_accelerator(row)
        accel = core.modifier_identity(
            core.normalize_accelerator(row)["modifiers"])
        if got != expected:
            fail("%s is bound to %s, expected %s" % (command, got, expected))
            continue
        if row["branch"] != core.BRANCH_XFWM4:
            fail("%s must live in the xfwm4 branch (xfwm4's own key handler), "
                 "not %s" % (command, row["branch"]))
            continue
        key = (accel, core.normalize_accelerator(row)["key"])
        clashes = [a for a in seen.get(key, []) if a != row["action"]]
        if clashes:
            fail("%s (%s) collides with %s — one of them can never fire"
                 % (command, got, ", ".join(clashes)))
            continue
        ok("%s bound once to %s (macOS equivalent), xfwm4 branch"
           % (command, got))

    # The two chords must also be present in both shipped XML copies.
    for path in (PACKAGED_KEYS_XML, SKEL_KEYS_XML):
        text = open(path, encoding="utf-8").read()
        for command, expected in wanted.items():
            needle = 'value="%s"' % command
            if needle not in text:
                fail("%s missing from %s" % (command, os.path.basename(path)))
        if text.count('value="switch_window_key"') != 1 or \
                text.count('value="fullscreen_key"') != 1:
            fail("%s does not carry each new binding exactly once"
                 % os.path.basename(path))
    if open(PACKAGED_KEYS_XML, encoding="utf-8").read() == \
            open(SKEL_KEYS_XML, encoding="utf-8").read():
        ok("both keyboard-shortcuts mirrors carry the new window bindings")
    else:
        fail("packaged and skel keyboard-shortcuts XML differ")


# ---------------------------------------------------------------------------
# Live half: real xfwm4 on the pinned Xvfb
# ---------------------------------------------------------------------------

GRAB_HELPER = r'''
import sys
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11
wid, w, h, path = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
# Gdk.pixbuf_get_from_window is (window, sx, sy, w, h) in GTK3 — GTK4 added a
# display argument — and a bare XID must be wrapped in a GdkX11Window first.
win = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), wid)
pb = Gdk.pixbuf_get_from_window(win, 0, 0, w, h)
if pb is None:
    sys.exit(2)
pb.savev(path, "png", [], [])
sys.stdout.write("%d %d" % (pb.get_width(), pb.get_height()))
'''


class WMSession:
    """A real xfwm4 on the pinned Xvfb, with an isolated environment.

    The theme is staged into ``$XDG_DATA_DIRS/themes/Mavericks/xfwm4`` — exactly
    the layout mavericks-theme installs into /usr/share — because that is the
    only path xfwm4 4.20 actually scans (strace-proven: a theme placed under
    ~/.themes/Mavericks/xfwm4/<name>/ is never opened).
    """

    def __init__(self, drop_buttons=False, config=None, theme_src=THEME_SRC):
        self.drop_buttons = drop_buttons
        self.config = config
        self.theme_src = theme_src
        self.procs = []

    def __enter__(self):
        self.display = mv_gui_display()
        if not self.display:
            raise RuntimeError("no pinned Xvfb display")
        self.home = tempfile.mkdtemp(prefix="mv-wm-")
        for d in (".config/xfce4/xfconf/xfce-perchannel-xml",
                  "share/themes/Mavericks/xfwm4", "run"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        os.chmod(os.path.join(self.home, "run"), 0o700)
        stage = os.path.join(self.home, "share/themes/Mavericks/xfwm4")
        shutil.copytree(self.theme_src, stage, dirs_exist_ok=True)
        if self.drop_buttons:
            for f in os.listdir(stage):
                if re.match(r"^(close|hide|maximize|maximize-toggled|minimize)\b", f):
                    os.remove(os.path.join(stage, f))
        shutil.copy2(self.config or XFWM4_SRC,
                     os.path.join(self.home, ".config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml"))
        self.env = dict(os.environ)
        self.env.update(
            HOME=self.home,
            XDG_CONFIG_HOME=os.path.join(self.home, ".config"),
            XDG_CACHE_HOME=os.path.join(self.home, ".cache"),
            XDG_DATA_HOME=os.path.join(self.home, ".local/share"),
            XDG_DATA_DIRS=os.path.join(self.home, "share") + ":/usr/share",
            XDG_RUNTIME_DIR=os.path.join(self.home, "run"),
            GDK_BACKEND="x11",
        )
        self.dbus = subprocess.Popen(
            ["dbus-daemon", "--session", "--print-address", "--nofork"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            env=self.env, start_new_session=True)
        # The bus MUST be started with the private environment: D-Bus hands
        # activated services the *daemon's* environment, so a bus launched from
        # the ambient shell makes xfconfd read the developer's real
        # ~/.config — which silently substitutes another machine's window
        # settings for the ones under test.
        self.procs.append(self.dbus)
        self.env["DBUS_SESSION_BUS_ADDRESS"] = self.dbus.stdout.readline().strip()
        self.wm = subprocess.Popen(["xfwm4", "-r"], env=self.env,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        self.procs.append(self.wm)
        time.sleep(1.5)
        if self.wm.poll() is not None:
            raise RuntimeError("xfwm4 exited immediately")
        return self

    def __exit__(self, *exc):
        for p in self.procs:
            try:
                os.killpg(os.getpgid(p.pid), 15)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        for p in self.procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        shutil.rmtree(self.home, ignore_errors=True)
        return False

    # -- window helpers ---------------------------------------------------
    def spawn_window(self, title, size=(420, 260), extra=""):
        path = os.path.join(self.home, "win-%d.py" % abs(hash(title)) )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                "import gi\n"
                "gi.require_version('Gtk','3.0')\n"
                "from gi.repository import Gtk\n"
                "w=Gtk.Window(title=%r)\n"
                "l=Gtk.Label(label='%s')\n"
                "w.add(l)\n"
                "w.set_default_size(%d,%d)\n"
                "w.show_all()\n"
                "Gtk.main()\n" % (title, title, size[0], size[1]))
        proc = subprocess.Popen([sys.executable, path], env=self.env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        self.procs.append(proc)
        time.sleep(1.5)
        cid = self.client_id(title)
        if cid is None:
            raise RuntimeError("window %r never mapped" % title)
        return proc, cid

    def client_id(self, title):
        ids = [int(x) for x in sh("xdotool search --name %s" % _q(title), self.env).split()
               if x.strip()]
        return ids[-1] if ids else None

    def activate(self, client):
        """Make our window the focused one, deterministically.

        The pinned Xvfb is shared with other test runs in this container, so
        focus is not something a suite may assume: a background window renders
        the *inactive* button pixmaps, which would silently turn the
        traffic-light assertions into a measurement of the wrong artwork.
        """
        for _ in range(12):
            self.active_window()
            sh("wmctrl -i -a %s" % _q_title_hex(client), self.env)
            sh("xdotool windowactivate --sync %d" % client, self.env)
            time.sleep(0.35)
            if self.active_window() == client:
                return True
        return False

    def frame_id(self, client):
        """The reparenting frame window xfwm4 wraps the client in.

        The root tree is a flat list indented by depth, so the parent of a
        window is the nearest shallower entry above it.
        """
        tree = sh("xwininfo -root -tree", self.env).splitlines()
        stack = []
        parent = {}
        for line in tree:
            st = line.strip()
            m = re.match(r"^(0x[0-9a-fA-F]+)\b", st)
            if not m:
                continue
            wid = int(m.group(1), 16)
            indent = len(line) - len(line.lstrip())
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                parent[wid] = stack[-1][1]
            stack.append((indent, wid))
        return parent.get(client)

    def geometry(self, wid):
        out = sh("xwininfo -id %d" % wid, self.env)
        def field(name):
            m = re.search(r"%s:\s*(-?\d+)" % name, out)
            return int(m.group(1)) if m else None
        return dict(x=field("Absolute upper-left X"), y=field("Absolute upper-left Y"),
                    w=field("Width"), h=field("Height"))

    def grab(self, wid, path, w, h):
        helper = os.path.join(self.home, "grab.py")
        with open(helper, "w", encoding="utf-8") as fh:
            fh.write(GRAB_HELPER)
        r = run([sys.executable, helper, str(wid), str(w), str(h), path],
                env=self.env)
        if r.returncode != 0 or not os.path.isfile(path):
            return None
        return r.stdout.strip()

    def wm_state(self, client):
        out = sh("xprop -id %d WM_STATE _NET_WM_STATE" % client, self.env)
        return out

    def active_window(self):
        out = sh("xprop -root _NET_ACTIVE_WINDOW", self.env)
        m = re.search(r"window id # (0x[0-9a-fA-F]+)", out)
        return int(m.group(1), 16) if m else None

    # -- measurement helpers ---------------------------------------------
    def lights(self, client, focus=True):
        """Traffic-light centres in absolute screen coordinates.

        Re-measured from the live frame every time, because every click that
        changes the window state also moves it: clicking coordinates captured
        before a maximise lands on the wrong pixels afterwards.

        `focus=False` measures the window *without* raising it — needed for the
        unfocused artwork, since activating the window would overwrite exactly
        the state under test.
        """
        if focus:
            self.activate(client)
        frame = self.frame_id(client)
        fg = self.geometry(frame)
        cg = self.geometry(client)
        title_h = cg["y"] - fg["y"]
        png = os.path.join(self.home, "frame.png")
        if not self.grab(frame, png, fg["w"], fg["h"]):
            return None, []
        found = find_lights(load_png(png), title_h,
                            require_saturation=focus)
        centres = [(fg["x"] + (l["x0"] + l["x1"]) // 2,
                    fg["y"] + (l["y0"] + l["y1"]) // 2,
                    classify(l["rgb"])) for l in found]
        return fg, centres

    def net_wm_state(self, client):
        return sh("xprop -id %d _NET_WM_STATE" % client, self.env)

    def is_maximized(self, client):
        out = self.net_wm_state(client)
        return "_NET_WM_STATE_MAXIMIZED_HORZ" in out and \
            "_NET_WM_STATE_MAXIMIZED_VERT" in out

    def wm_state_word(self, client):
        m = re.search(r"window state:\s*(\w+)", sh("xprop -id %d WM_STATE" % client,
                                                   self.env))
        return m.group(1) if m else "?"

    def window_exists(self, client):
        return sh("xdotool search --id %d" % client, self.env).strip() != ""

    def unmaximize(self, client):
        """Return a window to a plain, un-maximised, restored state."""
        for _ in range(3):
            if not self.is_maximized(client):
                break
            sh("wmctrl -i -r %s -b remove,maximized_vert,maximized_horz"
               % _q_title_hex(client), self.env)
            time.sleep(0.5)
        sh("wmctrl -i -a %s" % _q_title_hex(client), self.env)
        time.sleep(0.4)

    def drag_to_edge(self, client, tx=2, ty=500):
        """Drag the window by its title bar to a screen edge.

        The pointer is moved in graded steps: xfwm4 only tracks the drag while
        motion events arrive, so a single jump leaves the window where it was
        and a snap assertion would then be testing nothing.
        """
        frame = self.frame_id(client)
        fg = self.geometry(frame)
        x0, y0 = fg["x"] + fg["w"] // 2, fg["y"] + 10
        sh("xdotool mousemove --sync %d %d mousedown 1" % (x0, y0), self.env)
        time.sleep(0.15)
        for step in range(1, 13):
            nx = x0 + (tx - x0) * step // 12
            ny = y0 + (ty - y0) * step // 12
            sh("xdotool mousemove --sync %d %d" % (nx, ny), self.env)
            time.sleep(0.07)
        # xfwm4 only tiles once the pointer has settled at the edge.
        time.sleep(0.6)
        sh("xdotool mouseup 1", self.env)
        time.sleep(0.9)

    def move(self, client, x, y):
        """Place a window explicitly.

        placement_mode=center puts every new window in the middle of the
        screen, so two test windows overlap and a click aimed at the
        background one lands on the window above it.  Click-to-focus can only
        be tested on windows that are not covered.
        """
        sh("wmctrl -i -r %s -e 0,%d,%d,0,0" % (_q_title_hex(client), x, y), self.env)
        time.sleep(0.6)

    def double_click_title(self, client):
        frame = self.frame_id(client)
        fg = self.geometry(frame)
        x, y = fg["x"] + fg["w"] // 2, fg["y"] + 10
        sh("xdotool mousemove --sync %d %d click 1" % (x, y), self.env)
        time.sleep(0.12)
        sh("xdotool click 1", self.env)
        time.sleep(1.0)

    def declared_properties(self):
        text = open(XFWM4_SRC, encoding="utf-8").read()
        return re.findall(
            r'<property name="([^"]+)" type="(\w+)" value="([^"]*)"\s*/>', text)


def _q(text):
    return "'%s'" % text.replace("'", "'\\''")


def _q_title_hex(wid):
    return "0x%x" % wid


def mv_gui_display():
    sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
    import mv_gui_iso
    return mv_gui_iso.gui_display()


# ---------------------------------------------------------------------------
# Traffic-light detection (pixels, not config)
# ---------------------------------------------------------------------------

def load_png(path):
    from PIL import Image
    return Image.open(path).convert("RGB")


MIN_BLOB = 8     # a traffic light is a 12-14px disc; anything smaller is text
MAX_BLOB = 20    # wider than that is a run of title text, not one button


def find_lights(img, title_h, require_saturation=True):
    """Locate button-sized blobs in the top `title_h` rows.

    Returns a list of dicts sorted left→right, each with the blob's bounding
    box and mean colour, so the caller can assert the macOS red→amber→green
    order and that all three sit on the left.  Sub-MIN_BLOB specks are dropped:
    antialiased window-title text is saturated enough to match otherwise, and
    keeping it would make the "three lights" assertion pass for the wrong reason.

    `require_saturation=False` is for an *unfocused* window, whose lights are
    grey by design: saturation is the wrong filter there, so blobs are found by
    differing from the title bar's background colour instead.
    """
    width = img.size[0]
    top = img.crop((0, 0, width, min(title_h, img.size[1])))
    pixels = top.load()
    background = (232, 232, 224)
    if not require_saturation:
        from collections import Counter
        hist = Counter(pixels[x, y] for x in range(0, width, 2)
                       for y in range(top.size[1]))
        background = hist.most_common(1)[0][0]
    columns = {}
    for x in range(width):
        for y in range(top.size[1]):
            r, g, b = pixels[x, y]
            if require_saturation:
                if max(r, g, b) < 90:
                    continue
                if max(r, g, b) - min(r, g, b) < 45:
                    continue
            else:
                if max(abs(r - background[0]), abs(g - background[1]),
                       abs(b - background[2])) < 22:
                    continue
            columns.setdefault(x, []).append((y, r, g, b))
    if not columns:
        return []
    xs = sorted(columns)
    groups = [[xs[0]]]
    for x in xs[1:]:
        if x - groups[-1][-1] <= 3:
            groups[-1].append(x)
        else:
            groups.append([x])
    out = []
    for grp in groups:
        rs = gs = bs = n = 0
        ymin, ymax = 10 ** 6, -1
        for x in grp:
            for (y, r, g, b) in columns[x]:
                rs += r; gs += g; bs += b; n += 1
                ymin = min(ymin, y); ymax = max(ymax, y)
        width_px = grp[-1] - grp[0] + 1
        height_px = (ymax - ymin + 1) if ymax >= 0 else 0
        mean = (rs // n, gs // n, bs // n)
        # A button is a single 14px disc drawn 12px wide; anything much wider
        # is window-title text (which is what an unfocused scan picks up once
        # saturation stops being the filter).
        if not (MIN_BLOB <= width_px <= MAX_BLOB) or height_px < MIN_BLOB:
            continue
        # Antialiased title text also contains scattered saturated pixels; its
        # per-blob mean comes out grey, so a mean-saturation test rejects it
        # without hard-coding where the text is.  (Only in the saturated mode:
        # an unfocused window's buttons are legitimately grey.)
        if require_saturation and max(mean) - min(mean) < 40:
            continue
        out.append(dict(x0=grp[0], x1=grp[-1], n=n, y0=ymin, y1=ymax,
                        rgb=mean, w=width_px, h=height_px))
    return out


def classify(rgb):
    """Name a traffic light by hue.  Amber is tested before red because a
    Mavericks amber (#febc2e) has a high red channel, and a naive 'red is
    dominant' test claims it."""
    r, g, b = rgb
    if g > 110 and g > r + 30 and g > b + 30:
        return "green"
    if r > 120 and g > 90 and b < 150 and g > b + 25:
        return "amber"
    if r > 120 and g < 120 and r > g + 40 and r > b + 40:
        return "red"
    return "other"


def click(x, y, button=1, env=None):
    """Move the pointer and click, waiting for the move to be processed.

    The pinned display is shared with other test runs in this container, so a
    click issued before the pointer has actually arrived can land on whatever
    window is under the old position.
    """
    sh("xdotool mousemove --sync %d %d" % (x, y), env)
    time.sleep(0.15)
    sh("xdotool click %d" % button, env)


def main():
    for binary in ("xfwm4", "xwininfo", "xdotool", "xprop", "dbus-daemon"):
        if not have(binary):
            print("SKIP - %s not available; live measurement skipped" % binary)
            break
    audit_xpm_integrity()
    audit_config()
    audit_window_bindings()
    if not (have("xfwm4") and have("xwininfo") and have("xdotool") and have("xprop")):
        print("\n%d checks, %d failures (live half skipped)" % (checks[0], len(errors)))
        return 1 if errors else 0
    try:
        live()
    except Exception as exc:  # noqa: BLE001
        fail("live measurement crashed: %r" % (exc,))
    print("\n%d checks, %d failures" % (checks[0], len(errors)))
    for e in errors:
        print("  FAIL - %s" % e)
    return 1 if errors else 0


def audit_declared_properties_are_live(wms):
    """Every property we declare must be the value xfwm4 actually runs with.

    This is the check that catches both dead config and a polluted test
    environment: if the settings daemon is reading somebody else's
    ~/.config, the live values disagree with the shipped file and the suite
    says so instead of quietly measuring the wrong configuration.
    """
    mismatched = []
    for name, _typ, declared in wms.declared_properties():
        live = sh("xfconf-query -c xfwm4 -p /general/%s" % name, wms.env)
        if live != declared:
            mismatched.append("%s: file says %r, xfconfd says %r"
                              % (name, declared, live))
    if mismatched:
        for line in mismatched:
            fail("declared setting is not what xfwm4 runs with — %s" % line)
    else:
        ok("all %d declared xfwm4 settings are live values in the settings "
           "daemon (no dead config, no environment leakage)"
           % len(wms.declared_properties()))


def live():
    with WMSession() as wms:
        audit_declared_properties_are_live(wms)

        app, client = wms.spawn_window("WMTEST LIVE")
        frame = wms.frame_id(client)
        if not frame:
            fail("xfwm4 did not reparent the client into a frame window")
            return
        ok("xfwm4 decorates the client: frame 0x%x around client 0x%x"
           % (frame, client))

        fg = wms.geometry(frame)
        cg = wms.geometry(client)
        border_x = cg["x"] - fg["x"]
        title_h = cg["y"] - fg["y"]
        ok("frame geometry measured: %dx%d frame around %dx%d client "
           "(left border %dpx, title strip %dpx)"
           % (fg["w"], fg["h"], cg["w"], cg["h"], border_x, title_h))
        if border_x <= 0:
            fail("frame has no left border: title bar would touch the window edge")
        rc = open(os.path.join(THEME_SRC, "themerc"), encoding="utf-8").read()
        right_border = fg["w"] - cg["w"] - border_x
        # The border width comes from the artwork, not from themerc: measured,
        # a themerc asking for 4px still rendered 5px.
        art = xpm_entries(os.path.join(THEME_SRC, "left-active.xpm"))
        art_w = art[0] if art else None
        if art_w == border_x == right_border:
            ok("frame borders are %dpx, matching the theme artwork "
               "(left-active.xpm is %dpx wide)" % (border_x, art_w))
        else:
            fail("frame borders are %d/%dpx but the artwork is %s px wide"
                 % (border_x, right_border, art_w))
        inert = re.findall(r"^frame_border_\w+=", rc, re.M)
        if inert:
            fail("themerc declares %s again — those keys are inert on xfwm4 "
                 "4.20 and will contradict the artwork" % ", ".join(inert))
        else:
            ok("themerc carries no inert frame_border_* keys")
        title_px = None
        for f in sorted(os.listdir(THEME_SRC)):
            if re.match(r"^title-1-active\.xpm$", f):
                parsed = xpm_entries(os.path.join(THEME_SRC, f))
                if parsed:
                    title_px = parsed[1]
        if title_px and title_h != title_px:
            fail("title strip measured %dpx but title-1-active.xpm is %dpx "
                 "tall — the theme is not being used for the title bar"
                 % (title_h, title_px))
        elif title_px:
            ok("title strip height matches the theme artwork (%dpx)" % title_px)

        if not wms.activate(client):
            fail("could not make the test window the focused window on the "
                 "shared pinned display — button-state measurement unreliable")
        else:
            ok("test window is the focused window, so the *active* button "
               "artwork is what gets measured")

        fg, lights = wms.lights(client)
        if len(lights) != 3:
            fail("expected exactly 3 button-sized colour blobs in the title "
                 "bar, found %d — the macOS close/minimise/zoom buttons are "
                 "not all being drawn" % len(lights))
        else:
            names = [l[2] for l in lights]
            ok("traffic lights measured in the rendered title bar at %s"
               % ", ".join("%s (%d,%d)" % (n, l[0], l[1]) for n, l in
                           zip(names, lights)))
            if names != ["red", "amber", "green"]:
                fail("traffic-light order/colour is %s, expected red, amber, "
                     "green left to right (close on the left, macOS)" % names)
            else:
                ok("traffic lights read red -> amber -> green left to right: "
                   "close, minimise, zoom (macOS order)")
            if lights[2][0] - fg["x"] > fg["w"] // 2:
                fail("traffic lights sit in the right half of the title bar")
            else:
                ok("all three traffic lights sit in the left half of the "
                   "title bar (rightmost at x=%d of a %dpx frame)"
                   % (lights[2][0] - fg["x"], fg["w"]))

        # --- unfocused windows keep their buttons, muted -------------------
        # macOS keeps all three lights on an unfocused window and desaturates
        # them; a theme that only drew active artwork would leave the background
        # window with no way to close it, so this is measured, not assumed.
        app6, client6 = wms.spawn_window("WMTEST INACTIVE", size=(340, 200))
        wms.move(client6, 950, 620)
        wms.activate(client)
        time.sleep(0.6)
        if wms.active_window() != client:
            wms.activate(client)
        fg6, dim = wms.lights(client6, focus=False)
        if len(dim) == 3 and [d[2] for d in dim] != ["red", "amber", "green"]:
            ok("an unfocused window still shows three traffic lights, muted to "
               "grey — macOS never removes them from a background window")
        elif len(dim) != 3:
            fail("an unfocused window shows %d traffic lights, expected 3 — a "
                 "background window would have no way to close itself" % len(dim))
        else:
            fail("an unfocused window's traffic lights are still fully "
                 "coloured; macOS mutes them with the inactive artwork")
        app6.kill()
        time.sleep(0.4)
        wms.activate(client)
        time.sleep(0.4)

        # --- the buttons must actually do the macOS things ----------------
        by_name = dict((l[2], l) for l in lights)
        if "green" in by_name:
            click(by_name["green"][0], by_name["green"][1], env=wms.env)
            time.sleep(0.9)
            if wms.is_maximized(client):
                ok("green traffic light maximises the window "
                   "(_NET_WM_STATE_MAXIMIZED_HORZ+VERT) — macOS zoom/fullscreen")
            else:
                fail("green traffic light did not maximise the window")
            max_frame = wms.geometry(wms.frame_id(client))
            max_client = wms.geometry(client)
            strip = max_client["y"] - max_frame["y"]
            if strip > 0:
                ok("a zoomed window keeps a %dpx title strip, so its traffic "
                   "lights stay reachable (macOS 10.9 zoom, not full screen)"
                   % strip)
            else:
                fail("a zoomed window has no title bar at all — it cannot be "
                     "closed or minimised from its own chrome")
            wms.unmaximize(client)
        if "amber" in by_name:
            click(by_name["amber"][0], by_name["amber"][1], env=wms.env)
            time.sleep(0.9)
            if wms.wm_state_word(client) == "Iconic":
                ok("amber traffic light minimises the window (WM_STATE=Iconic)")
            else:
                fail("amber traffic light did not minimise the window (state=%s)"
                     % wms.wm_state_word(client))
            sh("wmctrl -i -a %s" % _q_title_hex(client), wms.env)
            time.sleep(0.8)
        if "red" in by_name:
            click(by_name["red"][0], by_name["red"][1], env=wms.env)
            time.sleep(1.2)
            if wms.window_exists(client):
                fail("red traffic light did not close the window")
            else:
                ok("red traffic light closes the window (client unmapped)")
        else:
            fail("no red traffic light — there is no close button to click")

        # --- double-click the title bar = zoom ----------------------------
        app2, client2 = wms.spawn_window("WMTEST DBL", size=(360, 220))
        wms.activate(client2)
        wms.double_click_title(client2)
        if wms.is_maximized(client2):
            ok("double-clicking the title bar zooms the window (macOS)")
        else:
            fail("double-clicking the title bar did not zoom the window")
        wms.unmaximize(client2)
        app2.kill()
        time.sleep(0.4)

        # --- focus follows click -----------------------------------------
        app3, client3 = wms.spawn_window("WMTEST FOCUS A", size=(340, 200))
        app4, client4 = wms.spawn_window("WMTEST FOCUS B", size=(340, 200))
        wms.move(client3, 60, 120)
        wms.move(client4, 900, 600)
        wms.activate(client3)
        if wms.active_window() != client3:
            fail("could not establish initial focus for the focus test")
        else:
            # Retried: another test run sharing the pinned display can steal
            # focus between the click and the read, and that is not a window
            # manager defect.
            focused = False
            for _ in range(4):
                wms.activate(client3)
                f4 = wms.frame_id(client4)
                g4 = wms.geometry(f4)
                click(g4["x"] + g4["w"] // 2, g4["y"] + 10, env=wms.env)
                time.sleep(0.9)
                if wms.active_window() == client4:
                    focused = True
                    break
            if focused:
                ok("clicking a background window focuses it and raises it "
                   "(macOS click-to-focus model)")
            else:
                fail("clicking a background window did not focus it "
                     "(active=0x%x, clicked=0x%x)"
                     % (wms.active_window() or 0, client4))
        app3.kill()
        app4.kill()
        time.sleep(0.4)

        # --- window switching through the window manager's own key handler --
        sw_a, sw_a_client = wms.spawn_window("WMTEST SWITCH A", size=(300, 180))
        sw_b, sw_b_client = wms.spawn_window("WMTEST SWITCH B", size=(300, 180))
        wms.move(sw_a_client, 80, 140)
        wms.move(sw_b_client, 950, 620)
        switched = False
        for _ in range(5):
            wms.activate(sw_a_client)
            if wms.active_window() != sw_a_client:
                # Another suite sharing the pinned display took focus; retry.
                time.sleep(0.5)
                continue
            sh("xdotool key --clearmodifiers alt+Tab", wms.env)
            time.sleep(1.0)
            if wms.active_window() == sw_b_client:
                switched = True
                break
        if switched:
            ok("Alt+Tab switches the focused window (xfwm4's own key "
               "handler, no resident switcher process)")
        else:
            fail("Alt+Tab did not move focus to the other window "
                 "(active=0x%x, expected 0x%x)"
                 % (wms.active_window() or 0, sw_b_client))
        sw_a.kill()
        sw_b.kill()
        time.sleep(0.4)

        # --- snapping must be OFF, and the test must be able to see it ----
        app5, client5 = wms.spawn_window("WMTEST SNAP", size=(360, 220))
        wms.activate(client5)
        before = wms.geometry(client5)
        wms.drag_to_edge(client5, tx=2, ty=500)
        after = wms.geometry(client5)
        if before["w"] == after["w"] and before["h"] == after["h"]:
            ok("dragging a window to the screen edge does not resize it "
               "(%dx%d kept) — Mavericks never snaps or tiles"
               % (after["w"], after["h"]))
        else:
            fail("dragging to the screen edge snapped the window from "
                 "%dx%d to %dx%d — macOS never does this"
                 % (before["w"], before["h"], after["w"], after["h"]))
        app5.kill()
        time.sleep(0.4)

    # Control: with snapping explicitly enabled the very same drag MUST
    # resize the window, otherwise the assertion above proves nothing.
    with WMSession(config=snap_override_config()) as ctl:
        _, ctl_client = ctl.spawn_window("WMTEST SNAPCTL", size=(360, 220))
        ctl.activate(ctl_client)
        was = ctl.geometry(ctl_client)
        ctl.drag_to_edge(ctl_client, tx=2, ty=500)
        now = ctl.geometry(ctl_client)
        if now["w"] != was["w"] or now["h"] != was["h"]:
            ok("detector control: with snapping+tile_on_move enabled the same "
               "drag resizes the window (%dx%d -> %dx%d), so the snap "
               "assertion above is real" % (was["w"], was["h"], now["w"], now["h"]))
        else:
            fail("the drag never resizes the window even with snapping "
                 "enabled — the snap assertion cannot detect anything")

    # Control: the traffic-light detector must find nothing without the
    # button pixmaps, otherwise the pixel assertions above are vacuous.
    with WMSession(drop_buttons=True) as wms2:
        app2, client2 = wms2.spawn_window("WMTEST NOLIGHTS")
        _, found = wms2.lights(client2)
        if len(found) >= 3:
            fail("the traffic-light detector finds %d blobs even with the "
                 "button pixmaps deleted — it is not a real check" % len(found))
        else:
            ok("detector control: with the button pixmaps deleted the title "
               "bar has %d traffic lights (assertion is not vacuous)"
               % len(found))
        app2.kill()
        time.sleep(0.3)


def snap_override_config():
    """A copy of the shipped xfwm4.xml with tiling/snapping fully on.

    Measured: enabling only snap_to_border or only snap_to_windows changes
    nothing; xfwm4 4.20 tiles the window on drop only when the snap switches
    *and* tile_on_move are on together.  The control therefore turns all three
    on, so a drag that still does not resize the window means the drag itself
    is not being tracked.
    """
    fd, path = tempfile.mkstemp(prefix="mv-wm-snap-", suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        text = open(XFWM4_SRC, encoding="utf-8").read()
        for key in ("snap_to_border", "snap_to_windows", "tile_on_move"):
            text = text.replace(
                '<property name="%s" type="bool" value="false"/>' % key,
                '<property name="%s" type="bool" value="true"/>' % key)
        fh.write(text)
    return path


if __name__ == "__main__":
    sys.exit(main())