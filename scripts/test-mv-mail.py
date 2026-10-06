#!/usr/bin/env python3
"""Headless tests for mv-mail backend selection + global-menu contract.

mv-mail is a lightweight wrapper that launches the real mail backend
(Geary or any desktop entry declaring Mail UserAgent). No mail protocol
code runs here: backend selection is pure and fully mocked, and the
application-menu builder is exercised against real Gio without a display.

Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-mail")

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_mail", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_mail", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run_backend_tests(mv):
    # geary preferred when installed
    with tempfile.TemporaryDirectory() as td:
        mv.DESKTOP_DIRS = [td]
        with mock.patch.object(mv.shutil, "which", return_value="/usr/bin/geary"):
            check("backend: geary preferred", mv.find_mail_backend() == ["geary"])

    # falls back to a desktop entry declaring Mail UserAgent
    with tempfile.TemporaryDirectory() as td:
        mv.DESKTOP_DIRS = [td]
        with open(os.path.join(td, "geary.desktop"), "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nName=Geary Mail\n"
                    "Mail UserAgent=geary\nExec=my-geary %u\n")

        def which_fallback(name):
            return "/usr/bin/my-geary" if name == "my-geary" else None

        with mock.patch.object(mv.shutil, "which", side_effect=which_fallback):
            check("backend: UserAgent fallback",
                  mv.find_mail_backend() == ["my-geary"])

    # no backend at all -> None (UI shows install hint instead of crashing)
    with tempfile.TemporaryDirectory() as td:
        mv.DESKTOP_DIRS = [td]
        with mock.patch.object(mv.shutil, "which", return_value=None):
            check("backend: absent -> None", mv.find_mail_backend() is None)

    # matching UserAgent whose Exec binary is missing is ignored
    with tempfile.TemporaryDirectory() as td:
        mv.DESKTOP_DIRS = [td]
        with open(os.path.join(td, "geary.desktop"), "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nMail UserAgent=geary\n"
                    "Exec=ghost-geary %u\n")
        with mock.patch.object(mv.shutil, "which", return_value=None):
            check("backend: matching UA without binary ignored",
                  mv.find_mail_backend() is None)

    # non-geary UserAgent is not a Mail backend for us
    with tempfile.TemporaryDirectory() as td:
        mv.DESKTOP_DIRS = [td]
        with open(os.path.join(td, "thunderbird.desktop"), "w",
                  encoding="utf-8") as f:
            f.write("[Desktop Entry]\nMail UserAgent=thunderbird\n"
                    "Exec=thunderbird\n")
        def which_tb(name):
            return "/usr/bin/thunderbird" if name == "thunderbird" else None

        with mock.patch.object(mv.shutil, "which", side_effect=which_tb):
            check("backend: non-geary UA ignored",
                  mv.find_mail_backend() is None)

    mv.DESKTOP_DIRS = ["/usr/share/applications",
                       os.path.expanduser("~/.local/share/applications")]


def run_factory_tests(mv):
    check("factory: window factory present", callable(mv.get_window_class))
    check("factory: lazy class builder present",
          callable(mv.build_window_class))
    # The Geary launcher method the menu action calls must exist in source.
    src = open(APP_PATH, encoding="utf-8").read()
    check("factory: launch_backend implemented", "def launch_backend" in src)
    preamble = src.split("def ", 1)[0]
    check("factory: no eager gi import at module level",
          "gi.require_version" not in preamble
          and "from gi.repository" not in preamble)


def run_menu_tests(mv):
    """Exercise build_mail_menu against real Gio (no display needed)."""
    try:
        from gi.repository import Gio
    except Exception as e:  # pragma: no cover - gi always present in CI
        bad("menu: gi unavailable", str(e))
        return

    created = []

    class FakeApp:
        def quit(self):
            created.append("quit")

    def add_action(name, callback):
        created.append("action:" + name)

    menu = mv.build_mail_menu(FakeApp(), "Mail", lambda: None, add_action)
    check("menu: built a Gio.Menu", isinstance(menu, Gio.Menu))
    for action in ("launch", "close", "quit"):
        check("menu: action registered: %s" % action,
              "action:%s" % action in created)
    check("menu: shared About not overridden",
          "action:about" not in created)

    labels = []

    def walk(m):
        for i in range(m.get_n_items()):
            sub = m.get_item_link(i, "submenu")
            if sub is not None:
                walk(sub)
            else:
                try:
                    from gi.repository import GLib
                    v = m.get_item_attribute_value(
                        i, "label", GLib.VariantType.new("s"))
                    if v is not None:
                        labels.append(v.get_string())
                except Exception:
                    pass

    walk(menu)
    for label in ("Open Mail", "Close Window", "About Mail", "Quit Mail"):
        check("menu: label present: %s" % label, label in labels, str(labels))

    # actions referenced by the menu must exist in the window class
    win_src = open(APP_PATH, encoding="utf-8").read()
    check("menu: launch action targets launch_backend",
          'add_action("launch"' in win_src and "launch_backend" in win_src)


def run_contract_tests(mv):
    src = open(APP_PATH, encoding="utf-8").read()
    check("contract: uses run_application runner", "run_application" in src)
    check("contract: no private Gtk.main loop", "Gtk.main()" not in src)
    check("contract: application id", "com.mavlinos.Mail" in src)
    check("contract: menu builder exported", "def build_mail_menu" in src)


    path = os.path.join(BIN, "mv-mail")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("mail: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("mail: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    mv = load_app()
    run_backend_tests(mv)
    run_factory_tests(mv)
    run_menu_tests(mv)
    run_contract_tests(mv)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
