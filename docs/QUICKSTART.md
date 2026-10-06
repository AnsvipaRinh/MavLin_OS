# MavLinOS Quick Start Guide

Welcome to MavLinOS! This guide will get you up and running with the Mavericks-style desktop experience in minutes.

## 1. Install Mission Control (2 minutes)

```bash
# One command to install everything
make install-mission-control
```

This will:
- Check dependencies (GTK3, ImageMagick, wmctrl, etc.)
- Install 7 Mission Control helpers to `/usr/local/bin`
- Show you what's available

If you see missing dependencies, the installer will show you the exact command to fix it:
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-ewmh python3-xlib imagemagick wmctrl xdotool
```

## 2. Try Mission Control (30 seconds)

```bash
# Launch the full GUI overlay
mv-mc-gui
```

You should see:
- Fullscreen overlay with all your windows
- Thumbnails arranged in a grid
- Workspace grouping
- Click any window to activate it
- Press ESC to close

**Or just press F3** if the keyboard shortcut is configured!

## 3. Explore Keyboard Shortcuts

MavLinOS comes with complete Mavericks-style keyboard bindings:

| Key | Action |
|-----|--------|
| `F3` | Mission Control |
| `F4` | Launchpad |
| `Super+Space` | Spotlight search |
| `Super+1`..`Super+9` | Switch to Space 1-9 |
| `Super+Shift+A` | Add new Space |
| `Super+Shift+D` | Remove Space |
| `Super+W` | Close window |
| `Super+M` | Minimize window |
| `Super+H` | Hide app |
| `Super+Shift+Q` | Force Quit |

See [`docs/KEYBOARD.md`](KEYBOARD.md) for the complete reference.

## 4. Manage Spaces

```bash
# Check current Space count
mv-workspace-count get

# Set to 4 Spaces (like macOS default)
mv-workspace-count set 4

# Add a Space
mv-workspace-count add

# Remove a Space
mv-workspace-count remove
```

## 5. Run Tests (Optional)

Want to verify everything works?

```bash
# Full test suite
make test-mission-control

# Or individual tests
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_gui.py
python3 tests/test_f3_mission_control_binding.py
```

## 6. Customize

### Change keyboard shortcuts

Edit: `configs/desktop/xfce/xfce4-panel.xml`

### Adjust workspace count

Edit: `~/.config/xfce4/xfconf/xfce4-desktop.xml`
```xml
<property name="/general/workspace_count" type="int" value="4"/>
```

### Reload panel after changes

```bash
xfce4-panel -r
```

## 7. Learn More

- [`docs/MISSION_CONTROL.md`](MISSION_CONTROL.md) — Full technical guide
- [`docs/KEYBOARD.md`](KEYBOARD.md) — All keyboard shortcuts
- [`README.md`](../README.md) — Project overview
- [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — Common issues

## Troubleshooting

### F3 doesn't work

Try manually:
```bash
mv-mc-gui
```

Or reload panel:
```bash
xfce4-panel -r
```

### No thumbnails

Install ImageMagick:
```bash
sudo apt install imagemagick
```

### GTK3 error

Install GTK3 bindings:
```bash
sudo apt install python3-gi gir1.2-gtk-3.0
```

### Command not found

Helpers are installed to `/usr/local/bin`. Check your PATH:
```bash
echo $PATH
which mv-mc-gui
```

## Next Steps

Now that you're set up:

1. ✨ **Customize the theme** — Check out `packages/mavericks-theme/`
2. 🚀 **Explore more apps** — Launchpad, Spotlight, Quick Look, Preview
3. ⌨️ **Learn all shortcuts** — Read [`docs/KEYBOARD.md`](KEYBOARD.md)
4. 🔧 **Tweak settings** — See `configs/desktop/xfce/`
5. 📖 **Deep dive** — Read [`docs/MISSION_CONTROL.md`](MISSION_CONTROL.md)

Enjoy your Mavericks-style desktop! 🎉
