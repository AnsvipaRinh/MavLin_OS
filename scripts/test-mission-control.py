#!/usr/bin/env python3
"""Validate the Mission Control runtime contract.

Mission Control's current implementation is intentionally one-shot and uses
wmctrl/xprop for X11 window/workspace discovery and activation. Keep its
runtime dependencies explicit so the ISO cannot ship a broken shortcut.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "packages/mavericks-apps/src/mavericks-apps/bin/mv-mission-control"
PACKAGES = ROOT / "archiso-profile/releng/packages.x86_64"
KEYS = ROOT / "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml"


def main():
    app = APP.read_text(encoding="utf-8")
    packages = set(PACKAGES.read_text(encoding="utf-8").split())
    keys = KEYS.read_text(encoding="utf-8")

    assert "wmctrl" in packages, "Mission Control requires wmctrl in the ISO"
    assert "xprop" in app, "Mission Control must use xprop for active-window state"
    assert '[\"wmctrl\", \"-l\", \"-x\"]' in app
    assert '[\"wmctrl\", \"-d\"]' in app
    assert '[\"wmctrl\", \"-i\", \"-a\", win_id]' in app
    assert "mission-control:/usr/bin/mv-mission-control" in keys
    assert "wmctrl" not in app or "FileNotFoundError" in app
    print("OK: Mission Control runtime contract")


if __name__ == "__main__":
    main()
