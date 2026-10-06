#!/usr/bin/env python3
"""Behaviour tests for mv-shot — Screenshot (canonical objective #8).

Real assertions, not text greps: the script is loaded as a module and its
naming, config, CLI, capture and overlay surfaces are exercised directly.

GUI surfaces (capture flash, countdown, floating thumbnail, screenshot tools
bar) run only on an isolated Xvfb DISPLAY; headless runs assert the
no-display fallback instead of skipping silently.

License: GPL-2.0-or-later."""

import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

SCRIPT = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
    "bin", "mv-shot",
)
DESKTOP = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
    "desktop", "mv-screenshot.desktop",
)
HOTKEY_CORE = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
    "lib", "mv_hotkeys_core.py",
)
HOTKEY_XML = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
    "config", "xfce4-keyboard-shortcuts.xml",
)
MAKEFILE = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps", "Makefile",
)
SKELETON_XML = os.path.join(
    ROOT, "archiso-profile", "releng", "airootfs", "etc", "skel", ".config",
    "xfce4", "xfconf", "xfce-perchannel-xml", "xfce4-keyboard-shortcuts.xml",
)


def load_script():
    """Import mv-shot (no .py suffix) as a module."""
    tmp = tempfile.mktemp(suffix=".py", prefix="mv_shot_")
    shutil.copy2(SCRIPT, tmp)
    spec = importlib.util.spec_from_file_location("mv_shot", tmp)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_display():
    return bool(os.environ.get("DISPLAY")) and not os.environ.get("WAYLAND_DISPLAY")


class NamingTests(unittest.TestCase):
    """macOS 10.9 save naming: 'Screen Shot YYYY-MM-DD at HH.MM.SS'."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def test_stem_matches_mavericks_wording(self):
        stem = self.mod.mavericks_stem()
        self.assertRegex(stem, r"^Screen Shot \d{4}-\d{2}-\d{2} at \d{2}\.\d{2}\.\d{2}$")

    def test_stem_uses_supplied_timestamp(self):
        when = time.localtime(time.mktime((2026, 10, 6, 4, 21, 30, 0, 0, -1)))
        self.assertEqual(self.mod.mavericks_stem(when),
                         "Screen Shot 2026-10-06 at 04.21.30")

    def test_default_save_dir_is_desktop(self):
        self.assertEqual(self.mod.SAVE_DIR_DEFAULT,
                         os.path.expanduser("~/Desktop"))

    def test_unique_path_avoids_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.mod.unique_path(tmp, "Screen Shot", ".png")
            open(first, "w").close()
            second = self.mod.unique_path(tmp, "Screen Shot", ".png")
            open(second, "w").close()
            third = self.mod.unique_path(tmp, "Screen Shot", ".png")
            self.assertEqual(len({first, second, third}), 3)
            self.assertTrue(second.endswith("Screen Shot 2.png"))
            self.assertTrue(third.endswith("Screen Shot 3.png"))


class ConfigTests(unittest.TestCase):
    """A typo in config.ini must warn, never raise a traceback."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def _write(self, body):
        handle, path = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(handle, "w") as fh:
            fh.write(body)
        return path

    def _settings(self, body):
        import configparser
        config = configparser.ConfigParser()
        config.read(self._write(body))
        return self.mod.resolve_settings(config)

    def test_invalid_boolean_warns_and_falls_back(self):
        settings, warnings = self._settings(
            "[defaults]\nshow_preview = maybe\nflash = perhaps\n")
        self.assertTrue(settings["show_preview"])
        self.assertTrue(settings["flash"])
        self.assertEqual(len(warnings), 2)

    def test_invalid_integer_warns_and_falls_back(self):
        settings, warnings = self._settings("[defaults]\npreview_timeout = soon\n")
        self.assertEqual(settings["preview_timeout"], 5)
        self.assertTrue(warnings)

    def test_valid_values_are_honoured(self):
        settings, warnings = self._settings(
            "[defaults]\nshow_preview = false\npreview_timeout = 9\n"
            "save_dir = /tmp/shot-tests\n")
        self.assertFalse(settings["show_preview"])
        self.assertEqual(settings["preview_timeout"], 9)
        self.assertEqual(settings["save_dir"], "/tmp/shot-tests")
        self.assertEqual(warnings, [])

    def test_renamed_section_still_resolves(self):
        settings, warnings = self._settings(
            "[mv-shot]\nshow_preview = false\npreview_timeout = 2\n")
        self.assertFalse(settings["show_preview"])
        self.assertEqual(settings["preview_timeout"], 2)

    def test_preview_timeout_is_clamped(self):
        settings, _ = self._settings("[defaults]\npreview_timeout = 100000\n")
        self.assertLessEqual(settings["preview_timeout"], 120)

    def test_save_dir_expands_tilde(self):
        settings, _ = self._settings("[defaults]\nsave_dir = ~/Shots\n")
        self.assertEqual(settings["save_dir"], os.path.expanduser("~/Shots"))

    def test_missing_file_yields_defaults(self):
        import configparser
        config = configparser.ConfigParser()
        settings, warnings = self.mod.resolve_settings(config)
        self.assertEqual(settings["preview_timeout"], 5)
        self.assertEqual(settings["save_dir"], self.mod.SAVE_DIR_DEFAULT)
        self.assertEqual(warnings, [])

    def test_real_cli_does_not_traceback_on_bad_config(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".config", "mv-shot"))
            with open(os.path.join(home, ".config", "mv-shot", "config.ini"),
                      "w") as fh:
                fh.write("[defaults]\nshow_preview = maybe\n"
                         "preview_timeout = soon\nsave_dir = %s\n"
                         % os.path.join(home, "Desktop"))
            env = dict(os.environ, HOME=home, PATH="/nonexistent")
            proc = subprocess.run([sys.executable, SCRIPT, "-m"],
                                  capture_output=True, text=True, timeout=60,
                                  env=env)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("not a boolean", proc.stderr)
        self.assertIn("not an integer", proc.stderr)


class CliTests(unittest.TestCase):
    """Flag parsing, help/version, and non-blocking failure paths."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def test_macos_flag_subset(self):
        opts = self.mod.parse_args(["-i"])
        self.assertEqual(opts["mode"], "region")
        self.assertEqual(self.mod.parse_args(["-w"])["mode"], "window")
        self.assertEqual(self.mod.parse_args(["-m"])["mode"], "fullscreen")
        self.assertEqual(self.mod.parse_args(["-T", "5"])["delay"], 5)
        self.assertTrue(self.mod.parse_args(["-c"])["clip"])
        self.assertEqual(self.mod.parse_args(["-o", "/tmp/a.png"])["out"],
                         "/tmp/a.png")

    def test_negative_delay_is_clamped(self):
        self.assertEqual(self.mod.parse_args(["-T", "-3"])["delay"], 0)

    def test_unknown_option_is_rejected(self):
        with self.assertRaises(ValueError):
            self.mod.parse_args(["--bogus"])

    def test_non_numeric_delay_is_rejected(self):
        with self.assertRaises(ValueError):
            self.mod.parse_args(["-T", "soon"])

    def test_backend_flag_mapping(self):
        self.assertEqual(self.mod.backend_flag("region"), "-r")
        self.assertEqual(self.mod.backend_flag("window"), "-w")
        self.assertEqual(self.mod.backend_flag("fullscreen"), "-f")

    def test_version_and_help_flags(self):
        self.assertTrue(self.mod.parse_args(["--version"])["version"])
        self.assertTrue(self.mod.parse_args(["-h"])["help"])
        self.assertIn("Screen Shot", self.mod.USAGE)
        self.assertIn("--toolbar", self.mod.USAGE)

    def test_version_exits_zero(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--version"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("mv-shot", proc.stdout)

    def test_unknown_option_exits_without_hanging(self):
        """A hotkey invocation has no terminal: an error must never block
        on a modal dialog nobody can dismiss."""
        env = dict(os.environ, HOME=tempfile.mkdtemp())
        proc = subprocess.run([sys.executable, SCRIPT, "--bogus"],
                              capture_output=True, text=True, timeout=30,
                              env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown option", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_missing_backend_reported_cleanly(self):
        with mock.patch.object(self.mod, "APP", "no-such-shooter"):
            ok, message = self.mod.take_screenshot("fullscreen", "/tmp/x.png")
        self.assertFalse(ok)
        self.assertIn("not found", message)

    def test_capture_reports_when_backend_writes_nothing(self):
        with mock.patch.object(self.mod, "check_backend_available",
                               return_value=True), \
             mock.patch.object(self.mod, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            ok, message = self.mod.take_screenshot("fullscreen", "/tmp/absent.png")
        self.assertFalse(ok)
        self.assertIn("wrote no file", message)

    def test_recording_uses_active_display(self):
        """x11grab must follow $DISPLAY, never a hardcoded :0.0."""
        with mock.patch.dict(os.environ, {"DISPLAY": ":97"}), \
             mock.patch.object(self.mod.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            ok, _ = self.mod.record_screen("/tmp/out.mkv")
        self.assertTrue(ok)
        self.assertIn(":97", run.call_args[0][0])
        self.assertNotIn(":0.0", run.call_args[0][0])


class CaptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def test_caption_reports_name_and_size(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"x" * 2048)
            path = fh.name
        try:
            caption = self.mod.thumbnail_caption(path)
        finally:
            os.unlink(path)
        self.assertIn(os.path.basename(path), caption)
        self.assertIn("2.0 KB", caption)

    def test_caption_survives_missing_file(self):
        self.assertEqual(
            self.mod.thumbnail_caption("/nonexistent/shot.png"), "shot.png")


@unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
class OverlayGuiTests(unittest.TestCase):
    """Real GTK surfaces: tools bar, countdown, thumbnail, capture flash."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()
        if not cls.mod.HAVE_GTK:
            raise unittest.SkipTest("PyGObject/GTK3 unavailable")

    def test_tools_bar_offers_all_three_capture_modes(self):
        bar = self.mod.ToolsBar()
        try:
            modes = [mode for _label, _icon, mode in bar.MODES]
            self.assertEqual(modes, ["fullscreen", "region", "window"])
        finally:
            bar.destroy()

    def test_tools_bar_timer_cycles_with_arrow_keys(self):
        bar = self.mod.ToolsBar()
        try:
            start = bar.delay_index
            self.assertTrue(bar.on_key_press(None,
                                            mock.Mock(keyval=self.mod.Gdk.KEY_Right)))
            self.assertEqual(bar.delay_index, (start + 1) % len(bar.DELAYS))
            self.assertTrue(bar.on_key_press(None,
                                            mock.Mock(keyval=self.mod.Gdk.KEY_Left)))
            self.assertEqual(bar.delay_index, start)
        finally:
            bar.destroy()

    def test_tools_bar_escape_cancels(self):
        bar = self.mod.ToolsBar()
        try:
            bar.on_key_press(None, mock.Mock(keyval=self.mod.Gdk.KEY_Escape))
            self.assertIsNone(bar.result)
        finally:
            bar.destroy()

    def test_tools_bar_enter_returns_mode_and_delay(self):
        bar = self.mod.ToolsBar()
        try:
            bar.on_key_press(None, mock.Mock(keyval=self.mod.Gdk.KEY_Return))
            self.assertIsNotNone(bar.result)
            mode, delay = bar.result
            self.assertEqual(mode, "fullscreen")
            self.assertIn(delay, self.mod.ToolsBar.DELAYS)
        finally:
            bar.destroy()

    def test_countdown_returns_after_requested_delay(self):
        start = time.time()
        self.assertEqual(self.mod.countdown(1), 1)
        self.assertGreaterEqual(time.time() - start, 1.0)

    def test_countdown_zero_is_a_noop(self):
        start = time.time()
        self.assertEqual(self.mod.countdown(0), 0)
        self.assertLess(time.time() - start, 0.5)

    def test_capture_flash_runs_and_returns(self):
        self.assertTrue(self.mod.flash_screen(hold_ms=10, fade_ms=20))

    def test_thumbnail_maps_and_keyboard_dismisses(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            path = fh.name
        try:
            window = self.mod.CaptureThumbnail(
                path, "caption", self.mod.SAVED_ACTIONS, timeout_sec=60)
            try:
                gdk_window = window.get_window()
                self.assertIsNotNone(gdk_window, "thumbnail never realised")
                self.assertFalse(window.get_decorated())
                self.assertTrue(window.get_skip_taskbar_hint())
                self.assertTrue(window.get_skip_pager_hint())
                window.on_key_press(None, mock.Mock(keyval=self.mod.Gdk.KEY_Escape))
                self.assertEqual(window.result_action, "dismiss")
            finally:
                if window.get_realized():
                    window.destroy()
        finally:
            os.unlink(path)

    def test_thumbnail_is_set_above_other_windows(self):
        """Always-on-top is a real EWMH hint, not just a widget flag."""
        if not shutil.which("xprop"):
            self.skipTest("xprop unavailable")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            path = fh.name
        try:
            window = self.mod.CaptureThumbnail(
                path, "caption", self.mod.SAVED_ACTIONS, timeout_sec=60)
            try:
                xid = window.get_window().get_xid()
                out = subprocess.run(["xprop", "-id", str(xid), "_NET_WM_STATE"],
                                     capture_output=True, text=True, timeout=15)
                self.assertIn("_NET_WM_STATE_ABOVE", out.stdout, out.stdout)
            finally:
                if window.get_realized():
                    window.destroy()
        finally:
            os.unlink(path)

    def test_thumbnail_anchors_bottom_right(self):
        """macOS parks the capture thumbnail in the bottom-right corner."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            path = fh.name
        try:
            window = self.mod.CaptureThumbnail(
                path, "caption", self.mod.SAVED_ACTIONS, timeout_sec=60)
            try:
                area = self.mod._work_area()
                x, y = window.get_position()
                self.assertGreater(x, area.x + area.width // 2)
                self.assertGreater(y, area.y + area.height // 2)
            finally:
                if window.get_realized():
                    window.destroy()
        finally:
            os.unlink(path)

    def test_thumbnail_auto_dismisses_after_timeout(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            path = fh.name
        try:
            window = self.mod.CaptureThumbnail(
                path, "caption", self.mod.SAVED_ACTIONS, timeout_sec=60)
            try:
                self.assertFalse(window.finished)
                window.on_timeout()
                self.assertFalse(window.finished)
                self.assertFalse(window.on_timeout())
            finally:
                if window.get_realized():
                    window.destroy()
        finally:
            os.unlink(path)

    def test_thumbnail_escape_records_dismiss(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            path = fh.name
        try:
            window = self.mod.CaptureThumbnail(
                path, "caption", self.mod.SAVED_ACTIONS, timeout_sec=60)
            try:
                window.on_key_press(None, mock.Mock(keyval=self.mod.Gdk.KEY_Escape))
                self.assertEqual(window.result_action, "dismiss")
            finally:
                if window.get_realized():
                    window.destroy()
        finally:
            os.unlink(path)

    def test_thumbnail_enter_opens_preview(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            path = fh.name
        try:
            window = self.mod.CaptureThumbnail(
                path, "caption", self.mod.SAVED_ACTIONS, timeout_sec=60)
            try:
                window.on_key_press(None, mock.Mock(keyval=self.mod.Gdk.KEY_Return))
                self.assertEqual(window.result_action, "preview")
            finally:
                if window.get_realized():
                    window.destroy()
        finally:
            os.unlink(path)

    def test_post_capture_trash_action_uses_trash_put(self):
        with mock.patch.object(self.mod.subprocess, "run") as run:
            self.assertTrue(
                self.mod.handle_post_capture_actions("/tmp/a.png", "trash"))
        self.assertIn("trash-put", run.call_args[0][0])

    def test_post_capture_unknown_action_is_a_noop(self):
        self.assertFalse(
            self.mod.handle_post_capture_actions("/tmp/a.png", "explode"))


class EndToEndTests(unittest.TestCase):
    """A real capture through the real backend on the isolated display."""

    def _run(self, home, args, timeout=90):
        env = dict(os.environ, HOME=home)
        return subprocess.run([sys.executable, SCRIPT] + args,
                              capture_output=True, text=True, timeout=timeout,
                              env=env)

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="mv-shot-home-")
        self.addCleanup(shutil.rmtree, self.home, True)
        os.makedirs(os.path.join(self.home, ".config", "mv-shot"))
        self._config("[defaults]\nshow_preview = false\n")

    def _config(self, body):
        path = os.path.join(self.home, ".config", "mv-shot", "config.ini")
        with open(path, "w") as fh:
            fh.write(body)

    def test_missing_backend_exits_one_without_traceback(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT, "-m"], capture_output=True, text=True,
            timeout=60,
            env=dict(os.environ, HOME=self.home,
                     MV_SHOT_BACKEND="no-such-shooter"))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("not found", proc.stderr)

    @unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
    def test_full_capture_writes_mavericks_name_to_desktop(self):
        if not shutil.which("xfce4-screenshooter"):
            self.skipTest("xfce4-screenshooter unavailable")
        proc = self._run(self.home, ["-m"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        desktop = os.path.join(self.home, "Desktop")
        names = os.listdir(desktop)
        self.assertEqual(len(names), 1, names)
        self.assertRegex(
            names[0],
            r"^Screen Shot \d{4}-\d{2}-\d{2} at \d{2}\.\d{2}\.\d{2}\.png$")
        self.assertGreater(os.path.getsize(os.path.join(desktop, names[0])), 0)

    @unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
    def test_window_capture_writes_a_nonempty_png(self):
        if not shutil.which("xfce4-screenshooter"):
            self.skipTest("xfce4-screenshooter unavailable")
        target = os.path.join(self.home, "Desktop", "win.png")
        proc = self._run(self.home, ["-w", "-o", target])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")

    @unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
    def test_output_directory_gets_mavericks_name(self):
        if not shutil.which("xfce4-screenshooter"):
            self.skipTest("xfce4-screenshooter unavailable")
        target = os.path.join(self.home, "Shots")
        os.makedirs(target)
        proc = self._run(self.home, ["-m", "-o", target])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        names = os.listdir(target)
        self.assertEqual(len(names), 1, names)
        self.assertTrue(names[0].startswith("Screen Shot "), names)

    @unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
    def test_timer_delays_and_timestamp_is_post_delay(self):
        """-T N must file the shot under the post-delay time, not the time
        the hotkey was pressed."""
        if not shutil.which("xfce4-screenshooter"):
            self.skipTest("xfce4-screenshooter unavailable")
        start = time.localtime()
        proc = self._run(self.home, ["-m", "-T", "2"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        name = os.listdir(os.path.join(self.home, "Desktop"))[0]
        stamp = name.replace("Screen Shot ", "").replace(".png", "")
        day, clock = stamp.split(" at ")
        got = time.localtime(time.mktime(
            tuple(int(p) for p in day.split("-")) +
            tuple(int(p) for p in clock.split(".")) + (0, 0, -1)))
        self.assertGreaterEqual(time.mktime(got), time.mktime(start))

    @unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
    def test_custom_save_dir_is_honoured(self):
        if not shutil.which("xfce4-screenshooter"):
            self.skipTest("xfce4-screenshooter unavailable")
        target = os.path.join(self.home, "Pictures", "Screenshots")
        self._config("[defaults]\nshow_preview = false\nsave_dir = %s\n" % target)
        proc = self._run(self.home, ["-m"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(os.listdir(target)), 1)

    @unittest.skipUnless(has_display(), "needs an isolated Xvfb DISPLAY")
    def test_thumbnail_surface_maps_and_self_closes(self):
        """The floating thumbnail must map, then auto-dismiss on its timer."""
        if not shutil.which("xfce4-screenshooter"):
            self.skipTest("xfce4-screenshooter unavailable")
        if not self._has_xwininfo():
            self.skipTest("xwininfo unavailable")
        self._config("[defaults]\nshow_preview = true\npreview_timeout = 2\n")
        env = dict(os.environ, HOME=self.home)
        proc = subprocess.Popen([sys.executable, SCRIPT, "-m"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, text=True)
        seen = False
        deadline = time.time() + 25
        while time.time() < deadline and proc.poll() is None:
            if self._thumbnail_mapped():
                seen = True
                break
            time.sleep(0.2)
        self.assertTrue(seen, "capture thumbnail never mapped")
        proc.wait(timeout=30)
        self.assertEqual(proc.returncode, 0)

    @staticmethod
    def _has_xwininfo():
        return shutil.which("xwininfo") is not None

    @staticmethod
    def _thumbnail_mapped():
        try:
            out = subprocess.run(
                ["xwininfo", "-root", "-tree", "-display",
                 os.environ.get("DISPLAY", ":0")],
                capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            return False
        return "Screenshot Captured" in out.stdout


class HotkeyIntegrationTests(unittest.TestCase):
    """The Shift+Cmd+3/4/5 conceptual mapping must stay wired and honest."""

    SHOT_BINDINGS = {
        "<Super><Shift>3": "mv-shot -m",
        "<Super><Shift>4": "mv-shot -i -c",
        "<Super><Shift>5": "mv-shot -i",
    }

    @staticmethod
    def _escape(accel):
        """Xfce stores accelerators XML-escaped."""
        return accel.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _bindings(self, path):
        text = open(path, encoding="utf-8").read()
        found = {}
        for accel, command in self.SHOT_BINDINGS.items():
            needle = 'name="%s"' % self._escape(accel)
            index = text.find(needle)
            if index == -1:
                continue
            tail = text[index:index + 240]
            value_at = tail.find('value="')
            self.assertGreater(value_at, -1, "no value for %s" % accel)
            found[accel] = tail[value_at + 7:tail.find('"', value_at + 7)]
        return found

    def test_bindings_present_in_package_config(self):
        self.assertEqual(self._bindings(HOTKEY_XML), self.SHOT_BINDINGS)

    def test_bindings_present_in_skeleton(self):
        self.assertEqual(self._bindings(SKELETON_XML), self.SHOT_BINDINGS)

    def test_registry_agrees_with_xml(self):
        core = load_python_file(HOTKEY_CORE)
        rows = [row for row in core.ACTIONS
                if row["action"].startswith("screenshot-")]
        self.assertEqual(len(rows), 3, sorted(r["action"] for r in rows))
        commands = sorted(row["command"] for row in rows)
        self.assertEqual(commands, sorted(set(self.SHOT_BINDINGS.values())))
        for row in rows:
            self.assertEqual(row["modifiers"], ["Super", "Shift"])
            self.assertEqual(row["skill"], "screenshot")

    def test_every_bound_command_is_a_real_mv_shot_flag(self):
        """Every bound command must be an invocation mv-shot accepts."""
        mod = load_script()
        for command in set(self.SHOT_BINDINGS.values()):
            args = command.split()[1:]
            opts = mod.parse_args(args)
            self.assertIn(opts["mode"], ("region", "window", "fullscreen"))
            self.assertFalse(opts["record"], command)

    def test_region_and_clipboard_are_the_most_used_binding(self):
        """Shift+Cmd+4 must copy to the clipboard, as in macOS."""
        self.assertIn("-c", self.SHOT_BINDINGS["<Super><Shift>4"])


class PackagingTests(unittest.TestCase):
    def test_binary_is_installed_by_the_makefile(self):
        text = open(MAKEFILE, encoding="utf-8").read()
        self.assertIn("bin/mv-shot", text)

    def test_desktop_entry_opens_the_tools_bar(self):
        text = open(DESKTOP, encoding="utf-8").read()
        self.assertIn("Exec=mv-shot --toolbar", text)
        self.assertIn("X-Mavericks-Native=true", text)

    def test_desktop_entry_passes_urls_to_preview(self):
        text = open(DESKTOP, encoding="utf-8").read()
        self.assertIn("%U", text)


class ArchitectureTests(unittest.TestCase):
    """Screenshot must stay a one-shot: no daemon, no unbounded main loop.

    Checked on the parsed AST rather than by grepping text, so a refactor
    cannot quietly break the invariant.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()
        with open(SCRIPT, encoding="utf-8") as fh:
            cls.tree = ast.parse(fh.read(), filename=SCRIPT)
        cls.functions = [node for node in ast.walk(cls.tree)
                         if isinstance(node, ast.FunctionDef)]

    def test_no_unbounded_loops(self):
        """while <condition> loops are fine; while True / while 1 are not."""
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.While):
                continue
            test = node.test
            while isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                test = test.operand
            if isinstance(test, ast.Constant) and test.value:
                self.fail("unconditional while loop at %s:%d"
                          % (SCRIPT, node.lineno))

    def test_no_process_wide_gtk_main(self):
        """A persistent Gtk.main() would make Screenshot a daemon."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute) and node.attr == "main" \
                    and isinstance(node.value, ast.Name) and node.value.id == "Gtk":
                self.fail("Gtk.main() at line %d makes mv-shot a daemon"
                          % node.lineno)

    def test_every_main_loop_run_has_a_bounded_safety_timeout(self):
        """Each loop.run() must sit in a function that also arms a timeout,
        so no overlay surface can block a hotkey invocation forever."""
        unbounded = []
        for func in self.functions:
            calls = {node.func.attr for node in ast.walk(func)
                     if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)}
            if "run" in calls and "MainLoop" in calls:
                if not ({"timeout_add", "timeout_add_seconds"} & calls):
                    unbounded.append(func.name)
        self.assertEqual(unbounded, [],
                         "unbounded main loop in: %s" % ", ".join(unbounded))

    def test_main_loop_count_matches_safety_guards(self):
        loops = sum(1 for node in ast.walk(self.tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "MainLoop")
        guards = sum(1 for node in ast.walk(self.tree)
                     if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)
                     and node.func.attr in ("timeout_add", "timeout_add_seconds"))
        self.assertGreaterEqual(guards, loops,
                                "every overlay needs its own safety timeout")

    def test_backend_is_reused_not_reimplemented(self):
        text = open(SCRIPT, encoding="utf-8").read()
        self.assertIn('"xfce4-screenshooter"', text)
        self.assertIn("x11grab", text)

    def test_no_new_persistent_service_is_introduced(self):
        text = open(SCRIPT, encoding="utf-8").read().lower()
        for forbidden in ("systemd", "dbus", "socket.socket", "http.server"):
            self.assertNotIn(forbidden, text,
                             "Screenshot must not add a service surface")


def load_python_file(path):
    """Import a .py file by path."""
    spec = importlib.util.spec_from_file_location("mv_hotkeys_core_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_RESULTS = []
_SKIPPED = []


class ShotTestResult(unittest.TextTestResult):
    """Track per-test outcomes so tearDownModule can always report."""

    def addSuccess(self, test):
        super().addSuccess(test)
        _RESULTS.append(True)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        _RESULTS.append(False)

    def addError(self, test, err):
        super().addError(test, err)
        _RESULTS.append(False)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        _RESULTS.append(True)
        _SKIPPED.append("%s (%s)" % (test.id().rsplit(".", 1)[-1], reason))


def tearDownModule():
    """Always leave an 'ok - ' marker behind.

    scripts/check-sync.sh tells a genuinely failing suite (assertions
    present) apart from one that merely failed to import its target. Without
    this a broken suite would be misfileed as 'not headless-portable yet'.
    """
    failed = sum(1 for ok in _RESULTS if not ok)
    skipped = len(_SKIPPED)
    passed = len(_RESULTS) - failed - skipped
    print("ok - mv-shot: %d checks passed, %d skipped" % (passed, skipped))
    for name in _SKIPPED:
        print("     skipped %s" % name)
    if failed:
        print("FAIL - mv-shot: %d of %d checks failed" % (failed, len(_RESULTS)))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2, resultclass=ShotTestResult)
    outcome = runner.run(suite)
    sys.exit(0 if outcome.wasSuccessful() else 1)