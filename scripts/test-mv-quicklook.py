#!/usr/bin/env python3
"""Headless contract tests for mv-quicklook runtime behavior."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-quicklook")
text = open(PATH, encoding="utf-8").read()

checks = [
    # Original contract checks
    ("video FPS uses non-integer-safe division", 'float(fps[0]) / float(fps[1])' in text),
    ("PDF paths use GLib filename-to-URI conversion",
     "GLib.filename_to_uri(path, None)" in text),
    ("Escape destroys the preview window",
     'if key in ("Escape", "q", "Q"):' in text and "            self.destroy()" in text),
    ("direct CLI enters GTK main loop",
     "    w = PreviewWindow(files" in text and "    Gtk.main()" in text),

    # New feature checks - Preview selection grid
    ("PreviewSelectionGrid class exists", "class PreviewSelectionGrid" in text),
    ("Grid shows file thumbnails", "create_grid_item" in text),
    ("Grid handles Enter/Space to preview", "Return" in text and "KP_Enter" in text and "space" in text),

    # New feature checks - Enhanced keyboard navigation
    ("Home/End keys navigate to first/last", '"Home"' in text and '"End"' in text),
    ("Page Up/Down jumps by 10", '"Page_Up"' in text and '"Page_Down"' in text),
    ("G key shows grid view", '"g", "G"' in text),
    ("Focus-out auto-close logic", "_maybe_close_on_focus_loss" in text),

    # New feature checks - Format support
    ("Extended image formats (HEIC, AVIF, TIFF)", ".heic" in text and ".avif" in text and ".tiff" in text),
    ("Extended media formats", ".opus" in text and ".m4v" in text and ".ts" in text),
    ("Office document support (DOC, DOCX, ODT, RTF)", ".docx" in text and ".odt" in text and ".rtf" in text),
    ("Office preview build_office_preview method", "build_office_preview" in text),

    # New feature checks - Improved media metadata
    ("Media metadata grid with selectable values", "set_selectable(True)" in text),
    ("Video/audio icon detection", "video-x-generic" in text and "audio-x-generic" in text),

    # New feature checks - Window lifecycle
    ("Fullscreen toggle with size restore", "prev_size" in text and "unfullscreen" in text),
    ("Open button with suggested-action class", "suggested-action" in text),

    # Multi-file navigation
    ("Multi-file navigation buttons", "go-previous" in text and "go-next" in text),
    ("Navigation wraps around", "self.index = (self.index + delta) % len(self.paths)" in text),

    # HeaderBar enhancements
    ("Grid button in headerbar", "view-grid" in text),
    ("File counter in title", "%d of %d" in text),

    # Thunar integration script checks
]

# Check Thunar integration script
THUNAR_PATH = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-quicklook-thunar")
thunar_text = open(THUNAR_PATH, encoding="utf-8").read()

thunar_checks = [
    ("Thunar script: get_thunar_selection function", "def get_thunar_selection" in thunar_text),
    ("Thunar script: xdotool for active window", "getactivewindow" in thunar_text),
    ("Thunar script: Ctrl+C copy", "ctrl+c" in thunar_text),
    ("Thunar script: clipboard polling with timeout", "wait_for_text" in thunar_text),
    ("Thunar script: file:// URI parsing", "file://" in thunar_text),
    ("Thunar script: multi-select support", "splitlines" in thunar_text),
    ("Thunar script: execvp mv-quicklook", "execvp" in thunar_text),
    ("Thunar script: notify-send fallback", "notify-send" in thunar_text),
]

checks.extend(thunar_checks)

failed = 0
for name, ok in checks:
    print(("ok - " if ok else "FAIL - ") + name)
    failed += not ok

sys.exit(1 if failed else 0    # --- native Mavericks window chrome ---
    check("Quick Look uses real XFWM4 window decoration", "self.set_decorated(True)" in text)
    check("Quick Look no longer uses Gtk.HeaderBar CSD", "Gtk.HeaderBar" not in text and "self.set_titlebar(" not in text)
    check("Quick Look keeps controls in an in-window toolbar", "mavericks-quicklook-toolbar" in text and "hb.pack_end(open_b, False, False, 0)" in text)

)