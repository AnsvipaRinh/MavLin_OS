#!/usr/bin/env python3
"""test-thunar-finder-gui.py — Finder P0 live behaviour on the pinned Xvfb.

Runs the REAL Thunar 4.20 against the repo's seeded Finder configuration
(configs/desktop/xfce/thunar.xml + configs/desktop/thunar/accels.scm +
.gtk-bookmarks) inside a private D-Bus session on the pinned Xvfb :97, and
asserts through AT-SPI (not screenshots-of-hope):

  1. the seeded xfconf channel values are live in the session's own xfconfd
     (the mechanism itself: perchannel XML -> channel, which is how skel
     seeds reach the installed system's user);
  2. the sidebar is the SHORTCUTS pane (Places/Devices sections + the
     .gtk-bookmarks favourites: Documents, Downloads, Pictures) -- Finder's
     Favorites/Devices sidebar, not a filesystem tree;
  3. the status bar shows the Finder-style item summary;
  4. the toolbar exposes Back / Forward / Open Parent;
  5. the in-window search toggle produces a search entry (and closes again)
     -- Finder Cmd+F surface (Super+F via accels.scm; key synthesis of Super
     chords is impossible on this Xvfb, hardware item);
  6. navigation history: Go -> Open Parent navigates up, Back becomes
     available and returns, Forward becomes available and re-enters --
     AT-SPI actions, no keyboard needed;
  7. the list view switch renders rows as accessible table cells and
     activating the Reports row opens it (double-click/open behaviour);
  8. Return renames (Finder: Return never opens) -- opportunistic: needs
     keyboard focus on a shared display; skips loudly when focus is
     unavailable.

Known environment limits (shared :97): Super-modified chords cannot be
synthesised here, so Super+[/]/f bindings are validated structurally in
scripts/test-mv-finder-config.py and on hardware (NEEDS_HARDWARE_TEST).

Run: python3 scripts/test-thunar-finder-gui.py  (or via check-sync.sh)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))

THUNAR_XML = os.path.join(REPO, "configs/desktop/xfce/thunar.xml")
ACCELS = os.path.join(REPO, "configs/desktop/thunar/accels.scm")

PASS = 0
FAILS = []


def ok(msg):
    global PASS
    PASS += 1
    print("ok - {0}".format(msg))


def fail(msg):
    FAILS.append(msg)
    print("FAIL - {0}".format(msg))


def sh(args, env=None, timeout=30):
    r = subprocess.run(args, capture_output=True, text=True, env=env,
                       timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


INNER_SCRIPT = r"""
import os
import subprocess
import sys
import time

DOCS = $DOCS
HOME = $HOME

import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

RESULTS = []


def ok(msg):
    RESULTS.append("ok - " + msg)


def fail(msg):
    RESULTS.append("FAIL - " + msg)


def emit():
    with open(os.path.join(HOME, "result.txt"), "w") as fh:
        fh.write("\n".join(RESULTS) + "\n")
    try:
        for pat in ("thunar", "xfwm4"):
            subprocess.run(["pkill", "-u", str(os.getuid()), "-f",
                           "[" + pat[0] + "]" + pat[1:]],
                           capture_output=True)
    except Exception:
        pass


def sh(*args):
    return subprocess.run(list(args), capture_output=True, text=True).stdout.strip()


def app():
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        a = desktop.get_child_at_index(i)
        if a is not None and "thunar" in (a.get_name() or "").lower():
            return a
    return None


def frames():
    a = app()
    if a is None:
        return []
    out = []
    for i in range(a.get_child_count()):
        w = a.get_child_at_index(i)
        if w is not None and w.get_role_name() == "frame":
            out.append(w)
    return out


def fname():
    return [f.get_name() for f in frames()]


def find_all(node, role=None, name=None, acc=None, depth=0, maxdepth=10):
    if acc is None:
        acc = []
    if node is None:
        return acc
    try:
        r = node.get_role_name()
        n = node.get_name() or ""
    except Exception:
        return acc
    if (role is None or r == role) and (name is None or name in n):
        acc.append(node)
    if depth < maxdepth:
        try:
            for i in range(node.get_child_count() or 0):
                c = node.get_child_at_index(i)
                if c is not None:
                    find_all(c, role, name, acc, depth + 1, maxdepth)
        except Exception:
            pass
    return acc


def states(node):
    try:
        return {Atspi.StateType.get_name(s)
                for s in node.get_state_set().get_states()}
    except Exception:
        return set()


def do_action(node, i=0):
    try:
        return bool(node.do_action(i))
    except Exception:
        return False


def action_names(node):
    try:
        return [node.get_action_name(a) for a in range(node.get_n_actions())]
    except Exception:
        return []


# ---------------- wait for the window ----------------
frame = None
for _ in range(80):
    fs = frames()
    for f in fs:
        if "MavDocs" in (f.get_name() or ""):
            frame = f
            break
    if frame is not None:
        break
    time.sleep(0.25)

if frame is None:
    fail("Thunar frame for MavDocs never appeared (got frames: {0})".format(fname()))
    emit()
    sys.exit(0)

ok("Thunar window opened: {0}".format(fname()[0]))

# ---------------- 1. live channel values ----------------
q = sh("xfconf-query", "-c", "thunar", "-p", "/last-side-pane")
if "ThunarShortcutsPane" in q:
    ok("channel live: last-side-pane=ThunarShortcutsPane (seeded perchannel XML honoured)")
elif q:
    fail("channel last-side-pane={0} (want ThunarShortcutsPane)".format(q))
else:
    fail("xfconf-query returned nothing for /last-side-pane")
q = sh("xfconf-query", "-c", "thunar", "-p", "/last-icon-view-zoom-level")
if "150" in q:
    ok("channel live: icon zoom 150% (Finder 64px default)")
else:
    fail("channel zoom={0} (want THUNAR_ZOOM_LEVEL_150_PERCENT)".format(q))
q = sh("xfconf-query", "-c", "thunar", "-p", "/misc-confirm-move-to-trash")
if "false" in q:
    ok("channel live: trash without confirmation (Finder Cmd+Delete)")
else:
    fail("channel misc-confirm-move-to-trash={0} (want false)".format(q))

# ---------------- 2. sidebar = shortcuts + favourites ----------------
f = frames()[0]
cells = find_all(f, "table cell")
names = [c.get_name() or "" for c in cells]
flat = " | ".join(names)
for section in ("Places", "Devices"):
    if section in names:
        ok("sidebar section {0} present (shortcuts pane structure)".format(section))
    else:
        fail("sidebar section {0} missing -- pane is not the shortcuts pane (cells: {1})"
             .format(section, flat[:200]))
for fav in ("MavDocs", "Pictures", "Downloads"):
    if fav in names:
        ok("sidebar favourite {0} from .gtk-bookmarks present".format(fav))
    else:
        fail("sidebar favourite {0} missing (cells: {1})".format(fav, flat[:200]))

# ---------------- 3. status bar ----------------
sb = find_all(f, "status bar")
if sb and "folder" in (sb[0].get_name() or ""):
    ok("status bar shows item summary: {0}".format((sb[0].get_name() or "")[:60]))
else:
    fail("status bar missing or empty (got {0})"
         .format([s.get_name() for s in sb]))

# ---------------- 4. toolbar buttons ----------------
for label in ("Back", "Forward", "Open Parent"):
    if find_all(f, "button", label):
        ok("toolbar has {0}".format(label))
    else:
        fail("toolbar button {0} not found".format(label))

# ---------------- 5. search toggle ----------------
before = len(find_all(f, "text")) + len(find_all(f, "entry"))
toggles = find_all(f, "toggle button", "Search")
if not toggles:
    fail("search toggle button not found in toolbar")
else:
    if do_action(toggles[0]):
        time.sleep(1.2)
        g = frames()[0]
        after = len(find_all(g, "text")) + len(find_all(g, "entry"))
        if after > before:
            ok("search toggle opens an in-window search entry ({0} -> {1} text widgets)"
               .format(before, after))
            if do_action(toggles[0]):
                time.sleep(0.8)
                g2 = frames()[0]
                off = len(find_all(g2, "text")) + len(find_all(g2, "entry"))
                if off <= before:
                    ok("search closes again (Finder Esc/cancel surface)")
                else:
                    fail("search entry stays after toggle-off ({0} vs {1})".format(off, before))
        else:
            fail("search toggle produced no entry widget ({0} -> {1})".format(before, after))
    else:
        fail("search toggle action failed")

# ---------------- 6. navigation history via menus ----------------
def menu_item(menuname, itemname):
    f = frames()[0]
    menus = find_all(f, "menu", menuname)
    if not menus:
        return None
    if not do_action(menus[0]):
        return None
    time.sleep(0.8)
    f = frames()[0]
    for m in find_all(f, "menu", menuname):
        for it in find_all(m, "menu item", itemname, maxdepth=4):
            if itemname.lower() in (it.get_name() or "").lower():
                return it
    return None

parent_item = menu_item("Go", "parent")
if parent_item is None:
    parent_item = menu_item("Go", "Open Parent")
if parent_item is not None and do_action(parent_item):
    time.sleep(1.5)
    names_now = fname()
    if names_now and "MavDocs" not in names_now[0]:
        ok("Go > Open Parent navigates up (title now {0})".format(names_now[0][:40]))
        f = frames()[0]
        backs = find_all(f, "button", "Back")
        enabled = [b for b in backs if "enabled" in states(b)]
        if enabled:
            ok("Back becomes enabled after navigation (history exists)")
            if do_action(enabled[0]):
                time.sleep(1.5)
                if fname() and "MavDocs" in fname()[0]:
                    ok("Back returns to MavDocs")
                    f = frames()[0]
                    fwds = find_all(f, "button", "Forward")
                    en_f = [b for b in fwds if "enabled" in states(b)]
                    if en_f:
                        ok("Forward becomes enabled (forward history)")
                        if do_action(en_f[0]):
                            time.sleep(1.5)
                            if fname() and "MavDocs" not in fname()[0]:
                                ok("Forward re-enters the parent (title {0})"
                                   .format(fname()[0][:40]))
                            else:
                                fail("Forward did not re-navigate (title {0})".format(fname()))
                        else:
                            fail("Forward action failed")
                    else:
                        fail("Forward stays disabled after Back (states: {0})"
                             .format(sorted(states(fwds[0])) if fwds else "no button"))
                else:
                    fail("Back did not return to MavDocs (title {0})".format(fname()))
            else:
                fail("Back action failed")
        else:
            fail("Back stays disabled after navigation (history broken)")
    else:
        fail("Open Parent did not navigate up (title {0})".format(fname()))
else:
    fail("Go menu has no activatable 'Open Parent' item")

# ---------------- 7. list view + row activation ----------------
lv = menu_item("View", "detailed list")
if lv is None:
    lv = menu_item("View", "list")
if lv is not None and do_action(lv):
    time.sleep(1.2)
    f = frames()[0]
    rows = [c for c in find_all(f, "table cell") if "Reports" == (c.get_name() or "")]
    if rows:
        ok("list view renders rows as accessible cells (Reports row present)")
        target = None
        for r in rows:
            if "activate" in action_names(r):
                target = r
                break
        f = frames()[0]
        backs = [b for b in find_all(f, "button", "Back") if "enabled" in states(b)]
        if fname() and "MavDocs" not in fname()[0] and backs:
            do_action(backs[0])
            time.sleep(1.2)
            f = frames()[0]
            rows = [c for c in find_all(f, "table cell")
                    if "Reports" == (c.get_name() or "")]
            target = None
            for r in rows:
                if "activate" in action_names(r):
                    target = r
                    break
        if target is not None and do_action(target):
            time.sleep(1.5)
            if fname() and "Reports" in fname()[0]:
                ok("activating the Reports row opens it (title {0})".format(fname()[0][:40]))
            else:
                fail("Reports row activation did not open it (title {0})".format(fname()))
        else:
            fail("no activatable Reports row in list view")
    else:
        cells_all = [c.get_name() or "" for c in find_all(f, "table cell")]
        fail("list view rows not accessible (cells: {0})".format(cells_all[:10]))
else:
    fail("View menu has no 'as detailed list' item")

# ---------------- 8. Return renames (opportunistic) ----------------
f = frames()[0]
backs = [b for b in find_all(f, "button", "Back") if "enabled" in states(b)]
if fname() and "Reports" in fname()[0] and backs:
    do_action(backs[0])
    time.sleep(1.2)
f = frames()[0]
rows = [c for c in find_all(f, "table cell") if "Reports" == (c.get_name() or "")]
target = None
for r in rows:
    if "activate" in action_names(r):
        target = r
        break
if target is None:
    print("SKIP - Return-rename: no list row to focus (list view not active)")
else:
    focused = False
    try:
        comp = target.query_component()
        focused = bool(comp.grab_focus())
    except Exception:
        focused = False
    if not focused:
        print("SKIP - Return-rename: could not grab focus on the row "
              "(shared display); structural accel checks cover the binding, "
              "key behaviour is a hardware item")
    else:
        title_before = fname()
        dirpane_texts = len(find_all(frames()[0], "text"))
        sh("xdotool", "key", "--clearmodifiers", "Return")
        time.sleep(1.2)
        title_after = fname()
        texts_after = len(find_all(frames()[0], "text")) if frames() else -1
        renamed = (title_after == title_before and texts_after > dirpane_texts)
        opened = title_after != title_before
        if renamed:
            ok("Return enters rename mode, does NOT open (Finder Return "
               "semantics; entry widgets {0} -> {1}, title {2})"
               .format(dirpane_texts, texts_after, title_after[0][:30] if title_after else ""))
            sh("xdotool", "key", "--clearmodifiers", "Escape")
            time.sleep(0.6)
            gone = len(find_all(frames()[0], "text")) if frames() else -1
            if gone <= dirpane_texts:
                ok("Escape leaves rename mode")
            else:
                fail("rename entry did not close on Escape")
        elif opened:
            fail("Return OPENED the selection ({0} -> {1}): accels.scm "
                 "Return=rename binding not honoured".format(title_before, title_after))
        else:
            fail("Return had no measurable effect (titles {0}/{1}, texts {2}/{3})"
                 .format(title_before, title_after, dirpane_texts, texts_after))

emit()
sys.exit(0)
"""


class Session:
    """Private D-Bus session with the seeded HOME; xfwm4 only if no WM."""

    def __init__(self, display):
        self.display = display
        self.home = tempfile.mkdtemp(prefix="mv-thunar-gui-")
        self.xdg = tempfile.mkdtemp(prefix="mv-thunar-xdg-")
        os.chmod(self.xdg, 0o700)
        self.docs = os.path.join(self.home, "MavDocs")
        self.reports = os.path.join(self.docs, "Reports")
        os.makedirs(self.reports)
        os.makedirs(os.path.join(self.home, "Pictures"), exist_ok=True)
        os.makedirs(os.path.join(self.home, "Downloads"), exist_ok=True)
        with open(os.path.join(self.docs, "notes.txt"), "w") as fh:
            fh.write("hello finder\n")
        with open(os.path.join(self.reports, "q1.txt"), "w") as fh:
            fh.write("q1\n")
        # seeded config: xfconf channel + accels + bookmarks
        xfdir = os.path.join(self.home, ".config/xfce4/xfconf/"
                             "xfce-perchannel-xml")
        os.makedirs(xfdir)
        shutil.copy(THUNAR_XML, os.path.join(xfdir, "thunar.xml"))
        os.makedirs(os.path.join(self.home, ".config/Thunar"))
        shutil.copy(ACCELS, os.path.join(self.home, ".config/Thunar/accels.scm"))
        with open(os.path.join(self.home, ".gtk-bookmarks"), "w") as fh:
            fh.write("file://{0} MavDocs MavDocs\n".format(self.docs))
            fh.write("file://{0}/Pictures Pictures Pictures\n".format(self.home))
            fh.write("file://{0}/Downloads Downloads Downloads\n".format(self.home))
        self.inner = os.path.join(self.home, "inner.py")
        self.bus = None
        self.wm = None

    def start(self):
        code, out, _ = sh(["pgrep", "-u", str(os.getuid()), "-f",
                           "[T]hunar --daemon"])
        if code == 0:
            for pid in out.split():
                try:
                    os.kill(int(pid), 15)
                except OSError:
                    pass
            time.sleep(1.0)

        # Write the inner script with substituted paths
        inner_script = INNER_SCRIPT.replace("$DOCS", repr(self.docs)).replace("$HOME", repr(self.home))
        with open(self.inner, "w") as fh:
            fh.write(inner_script)
        
        # Write the session launcher script
        launcher = os.path.join(self.home, "inner-session.sh")
        with open(launcher, "w") as fh:
            fh.write("""#!/usr/bin/env bash
export DISPLAY={display} GDK_BACKEND=x11 LANG=C
if ! xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id'; then
  xfwm4 >/dev/null 2>&1 &
  for i in $(seq 1 60); do
    xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id' && break
    sleep 0.5
  done
fi
thunar {docs} >/dev/null 2>&1 &
exec python3 {inner}
""".format(display=self.display, docs=self.docs, inner=self.inner))
        
        os.chmod(launcher, 0o755)
        
        env = dict(os.environ)
        env.update({
            "HOME": self.home,
            "XDG_RUNTIME_DIR": self.xdg,
            "DISPLAY": self.display,
            "GDK_BACKEND": "x11",
            "LANG": "C",
            "MV_GUI_ISOLATED": os.environ.get("MV_GUI_ISOLATED", "1"),
            "MV_FORBIDDEN_DISPLAYS": os.environ.get("MV_FORBIDDEN_DISPLAYS", ""),
            "MV_GUARD_LOG": os.environ.get("MV_GUARD_LOG", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        })
        self.bus = subprocess.Popen(
            ["dbus-run-session", "--", "bash", launcher],
            env=env, cwd=self.home,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)

    def result(self, timeout=160):
        deadline = time.time() + timeout
        result_path = os.path.join(self.home, "result.txt")
        while time.time() < deadline:
            if os.path.isfile(result_path):
                time.sleep(0.3)
                with open(result_path) as fh:
                    return fh.read()
            if self.bus.poll() is not None:
                break
            time.sleep(0.5)
        return None

    def stop(self):
        if self.bus and self.bus.poll() is None:
            try:
                os.killpg(os.getpgid(self.bus.pid), 15)
            except OSError:
                self.bus.terminate()
            try:
                self.bus.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.bus.pid), 9)
                except OSError:
                    self.bus.kill()
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.xdg, ignore_errors=True)


def main():
    import mv_gui_iso
    display = mv_gui_iso.gui_display()
    if not display:
        print("SKIP: no isolated display -- run under scripts/gui-isolation.sh")
        return 0

    session = Session(display)
    session.start()
    try:
        result = session.result(timeout=160)
    finally:
        session.stop()
    if result is None:
        fail("live session produced no result (timeout/abort)")
    else:
        print(result.rstrip())
        for line in result.splitlines():
            if line.startswith("FAIL - "):
                FAILS.append(line[7:])
            elif line.startswith("ok - "):
                PASS += 1
                print(line)
            elif line.startswith("SKIP"):
                print(line)
    print()
    if FAILS:
        print("FAILED: {0} checks".format(len(FAILS)))
        return 1
    print("PASSED: {0} live checks".format(PASS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
