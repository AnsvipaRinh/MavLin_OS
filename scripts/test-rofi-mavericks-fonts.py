#!/usr/bin/env python3
"""Regression checks for legacy Rofi fallback typography."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIGS = [
    os.path.join(ROOT, "packages", "mavericks-apps", "src", "mavericks-apps", "config", name)
    for name in ("rofi-mavericks.rasi", "rofi-launchpad.rasi", "rofi-mission-control.rasi")
]

class RofiMavericksFontTests(unittest.TestCase):
    def test_fallback_configs_use_lucida_grande(self):
        for path in CONFIGS:
            with self.subTest(path=path):
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                self.assertIn("Lucida Grande", text)
                self.assertNotIn("San Francisco", text)
                self.assertNotIn("Helvetica Neue", text)

if __name__ == "__main__":
    unittest.main(verbosity=2)