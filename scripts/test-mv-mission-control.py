#!/usr/bin/env python3
"""Portable regression tests for the native Mission Control path."""

import importlib.util
import os
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "packages", "mavericks-apps", "src", "mavericks-apps", "bin", "mv-mission-control")
KEYS = os.path.join(ROOT, "packages", "mavericks-apps", "src", "mavericks-apps", "config", "xfce4-keyboard-shortcuts.xml")


def load_script():
    spec = importlib.util.spec_from_file_location("mv_mission_control", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MissionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def test_native_backend_primes_workspaces_then_exposes(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append((command, kwargs))
            result = mock.Mock(returncode=0)
            result.stdout = "0  * DG: 0 0 0 0\n"
            return result

        with mock.patch.object(self.mod.shutil, "which", return_value="/usr/bin/skippy-xd"), \
             mock.patch.object(self.mod.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(time, "sleep"):
            self.assertTrue(self.mod.run_native_expose())

        self.assertIn(
            (["/usr/bin/skippy-xd", "--start-daemon"], {"timeout": 5}),
            commands,
        )
        self.assertIn(
            (["/usr/bin/skippy-xd", "--expose", "--desktop", "-1"], {"timeout": 300}),
            commands,
        )
        self.assertIn(
            (["/usr/bin/skippy-xd", "--stop-daemon"], {"timeout": 5, "check": False}),
            commands,
        )
        self.assertTrue(any(cmd[:2] == ["/usr/bin/wmctrl", "-s"] for cmd, _ in commands))
        self.assertEqual(
            commands[-1][0],
            ["/usr/bin/skippy-xd", "--stop-daemon"],
        )

    def test_native_backend_is_optional(self):
        with mock.patch.object(self.mod.shutil, "which", return_value=None):
            self.assertFalse(self.mod.run_native_expose())

    def test_native_failure_falls_back(self):
        with mock.patch.object(self.mod.shutil, "which", return_value="/usr/bin/skippy-xd"),              mock.patch.object(self.mod.subprocess, "run", side_effect=OSError):
            self.assertFalse(self.mod.run_native_expose())

    def test_keyboard_binding_selects_native_path(self):
        with open(KEYS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(
            '<property name="&lt;Super&gt;Tab" type="string" value="mv-mission-control --native"/>',
            text,
        )
        self.assertNotIn("rofi -show -modi 'mission-control:/usr/bin/mv-mission-control'", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
