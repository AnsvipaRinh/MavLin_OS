#!/usr/bin/env python3
"""Portable regression tests for the native Mission Control path."""

import importlib.util
import os
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

    def test_native_backend_uses_daemon_free_all_desktops_expose(self):
        with mock.patch.object(self.mod.shutil, "which", return_value="/usr/bin/skippy-xd"), \
             mock.patch.object(self.mod.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            self.assertTrue(self.mod.run_native_expose())
        run.assert_called_once_with(
            ["/usr/bin/skippy-xd", "--desktop", "-1"],
            timeout=30,
        )

    def test_native_backend_is_optional(self):
        with mock.patch.object(self.mod.shutil, "which", return_value=None):
            self.assertFalse(self.mod.run_native_expose())

    def test_native_failure_falls_back(self):
        with mock.patch.object(self.mod.shutil, "which", return_value="/usr/bin/skippy-xd"), \
             mock.patch.object(self.mod.subprocess, "run", side_effect=OSError):
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
