# MavLinOS

MavLinOS — macOS Mavericks-style desktop experience on Linux (Xfce/Ubuntu).

## Quick Start

**First time? Start here:** [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

```bash
# Install all dependencies and Mission Control
make install-mission-control

# Try Mission Control
mv-mc-gui

# Or use keyboard shortcut
# Press F3
```

## Features

- 🎯 **Mission Control** — Full window overview with thumbnails across Spaces
- 🖥️ **Spaces** — Dynamic workspace management (1-16 Spaces)
- 🎨 **Mavericks Theme** — Authentic GTK theme matching OS X 10.9
- ⌨️ **Keyboard Shortcuts** — Complete Mavericks-style key bindings
- 🚀 **Launchpad** — App grid launcher
- 🔍 **Spotlight** — Fast app/file search
- 📱 **Handoff-like** — Cross-device continuity features

## Documentation

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) — **First-time user guide** ⭐
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — **Developer guide** 🛠️
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — **Community guidelines** 🤝
- [`SECURITY.md`](SECURITY.md) — **Security policy** 🔒
- [`CHANGELOG.md`](CHANGELOG.md) — **Project history** 📜
- [`docs/KEYBOARD.md`](docs/KEYBOARD.md) — Complete keyboard reference
- [`docs/MISSION_CONTROL.md`](docs/MISSION_CONTROL.md) — Mission Control implementation guide
- [`docs/INSTALL.md`](docs/INSTALL.md) — Installation instructions
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — Common issues and fixes

## Testing

```bash
# Run all Mission Control tests
make test-mission-control

# Or individual components
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_gui.py
python3 tests/test_f3_mission_control_binding.py
```

## Architecture

```
MavLinOS/
├── packages/
│   ├── mavericks-theme/     # GTK theme, icons, cursors
│   └── mavericks-apps/      # Mission Control, Launchpad, etc.
├── configs/
│   └── desktop/xfce/        # Xfce configuration
├── docs/                    # Documentation
├── tests/                   # Integration tests
└── ci/                      # CI gates
```

## Mission Control Stack

```
mv-mc-gui (GTK3 overlay)
    ↓
mv-mc-window-spaces (JSON window list)
mv-mc-thumbnail (PNG thumbnails)
mv-mc-grid (layout calculation)
mv-mc-activate-window (focus by ID)
mv-workspace-count (Space management)
```

## Requirements

- Ubuntu 22.04+ or Xubuntu 22.04+
- Xfce 4.16+
- Python 3.8+
- GTK3
- ImageMagick or scrot
- wmctrl, xdotool

## License

GPL-3.0-or-later

## Contributing

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for the developer guide.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make test-mission-control`
5. Submit a pull request

## Security

See [`SECURITY.md`](SECURITY.md) for reporting security vulnerabilities.

## Acknowledgments

- Poppy OS X Revieve by kayover — Visual reference and inspiration
- Xfce team — Lightweight desktop foundation
- Ubuntu team — Base distribution

## Status

✅ Mission Control (full implementation)
✅ Spaces management (1-16)
✅ Mavericks theme
✅ Keyboard shortcuts
✅ Documentation (QUICKSTART, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, KEYBOARD, MISSION_CONTROL)
✅ Test coverage
✅ CI gates
✅ Easy installation (`make install-mission-control`)
✅ Security policy

🚧 In progress: Animations, multi-monitor, touchpad gestures
