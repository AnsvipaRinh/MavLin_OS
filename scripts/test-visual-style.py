#!/usr/bin/env python3
"""Static visual regression contracts for the Mavericks foundation.

These checks intentionally validate design primitives rather than screenshots:
the shared theme must stay visually coherent when individual applications
change.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

def check(name, condition):
    if not condition:
        print("FAIL - " + name)
        return 1
    print("ok - " + name)
    return 0

def main():
    failures = 0
    colors = read("packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_colors.scss")
    variables = read("packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_variables.scss")
    dock = read("packages/mavericks-theme/src/mavericks-theme/plank/dock.theme")
    launchpad = read("packages/mavericks-apps/src/mavericks-apps/bin/mv_launchpad_gui.py")
    settings = read("packages/mavericks-apps/src/mavericks-apps/bin/mv-settings")
    pkgb = read("packages/mavericks-theme/PKGBUILD")

    failures += check("selection uses muted Mavericks blue",
                        "$theme_selected_bg_color: #6f8fbd;" in colors)
    failures += check("accent is not saturated iOS blue",
                        "$accent_bg_color: #5f80b2;" in colors)
    failures += check("ordinary controls stay compact",
                        "$button_min_height: 24px;" in variables)
    failures += check("menu items stay compact",
                        "$menuitem_padding: 4px 12px;" in variables)
    failures += check("Dock uses dark translucent Mavericks glass",
                        "FillStartColor=82;;82;;82;;226" in dock and
                        "FillEndColor=24;;24;;24;;226" in dock)
    failures += check("Launchpad is translucent blue-gray, not opaque black",
                        "background: rgba(28, 45, 60, 0.72);" in launchpad)
    failures += check("Launchpad item geometry is restrained",
                        "border-radius: 4px;" in launchpad)
    failures += check("System Settings uses a five-column icon grid",
                        "min_children_per_line=5" in settings and
                        "max_children_per_line=5" in settings)
    failures += check("System Settings uses 40px preference icons",
                        "image.set_pixel_size(40)" in settings)
    failures += check("System Settings tiles use a dedicated visual class",
                        "mavericks-preferences-item" in settings and
                        ".mavericks-preferences-item" in read(
                            "packages/mavericks-theme/src/mavericks-theme/gtk-3.0/gtk.scss"))
    failures += check("font target is Mavericks-era Lucida Grande",
                        "gtk-font-name=Lucida Grande 11" in pkgb)

    print("\nvisual style checks: %d failures" % failures)
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
