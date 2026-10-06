#!/usr/bin/env python3
"""Regression tests for the optional native Mission Control path."""

import importlib.util
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless app-suite: no window today, but app code and child
# interpreters run with the ambient environment — on WSLg that is
# the user's Windows desktop.  Arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED (oid
# OS-window-leak2) instead of popping a window on the host.
sys.path.insert(0, os.path.join(ROOT, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

SCRIPT = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
    "bin", "mv-mission-control",
)
KEYS = os.path.join(
    ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
    "config", "xfce4-keyboard-shortcuts.xml",
)
PACKAGES = os.path.join(ROOT, "archiso-profile", "releng", "packages.x86_64")


def load_script():
    import shutil
    import tempfile
    tmp = tempfile.mktemp(suffix=".py", prefix="mv_mission_control_")
    shutil.copy2(SCRIPT, tmp)
    spec = importlib.util.spec_from_file_location("mv_mission_control", tmp)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MissionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def test_native_backend_launches_gtk_overview(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append((command, kwargs))
            return mock.Mock(returncode=0)

        with mock.patch.object(
            self.mod.shutil, "which", return_value="/usr/bin/mv-mc-overview"
        ), mock.patch.object(
            self.mod.os.path, "exists", return_value=True
        ), mock.patch.object(
            self.mod.subprocess, "run", side_effect=fake_run
        ):
            self.assertTrue(self.mod.run_native_expose())

        self.assertEqual(
            commands,
            [(["/usr/bin/mv-mc-overview"], {"timeout": 300})],
        )

    def test_native_backend_is_optional(self):
        with mock.patch.object(self.mod.shutil, "which", return_value=None):
            self.assertFalse(self.mod.run_native_expose())

    def test_native_failure_falls_back(self):
        with mock.patch.object(
            self.mod.shutil, "which", return_value="/usr/bin/mv-mc-overview"
        ), mock.patch.object(
            self.mod.os.path, "exists", return_value=True
        ), mock.patch.object(self.mod.subprocess, "run", side_effect=OSError):
            self.assertFalse(self.mod.run_native_expose())

    def test_keyboard_binding_selects_native_path(self):
        with open(KEYS, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(
            '<property name="&lt;Super&gt;Tab" type="string" '
            'value="mv-mission-control --native"/>',
            text,
        )
        self.assertNotIn(
            "rofi -show -modi 'mission-control:/usr/bin/mv-mission-control'",
            text,
        )


    def test_native_overview_has_mavericks_surface(self):
        overview = os.path.join(
            ROOT, "packages", "mavericks-apps", "src", "mavericks-apps",
            "bin", "mv-mc-overview",
        )
        with open(overview, encoding="utf-8") as fh:
            css = fh.read()
        self.assertIn("window.mav-mc", css)
        self.assertIn("rgba(25,27,30,0.96)", css)
        self.assertIn(".mav-card.mav-selected", css)
        self.assertIn(".mav-workspace-button", css)
        self.assertIn("linear-gradient", css)
        self.assertNotIn("background-color: #3b3c3f", css)

    def test_iso_declares_x11_runtime_tools(self):
        with open(PACKAGES, encoding="utf-8") as fh:
            package_names = set(fh.read().split())
        self.assertIn("wmctrl", package_names)
        self.assertIn("xorg-xprop", package_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
