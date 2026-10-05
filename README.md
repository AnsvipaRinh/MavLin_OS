# MavLinOS

MavLinOS — macOS Mavericks-style desktop experience on Arch Linux (Xfce/X11), built with mkarchiso.

## Quick Start

```bash
# Build / validate the Arch-based project from the repository.
# Runtime installation is currently a manual Arch installation step.

# Try Mission Control after the project packages are installed:
mv-mc-gui
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

- [`docs/KEYBOARD.md`](docs/KEYBOARD.md) — Complete keyboard reference
- [`docs/MISSION_CONTROL.md`](docs/MISSION_CONTROL.md) — Mission Control implementation guide
- [`docs/INSTALLATION_CONTRACT.md`](docs/INSTALLATION_CONTRACT.md) — Current installation/firstboot contract
- [`docs/HARDWARE.md`](docs/HARDWARE.md) — Hardware profiles and validation scope

## Testing

```bash
# Run all tests
ci/test-mission-control.sh

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

- Arch Linux / mkarchiso
- Xfce 4.16+
- Python 3.8+
- GTK3
- ImageMagick or scrot
- wmctrl, xdotool

## License

GPL-3.0-or-later

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `ci/test-mission-control.sh`
5. Submit a pull request

## Acknowledgments

- Poppy OS X Revieve by kayover — Visual reference and inspiration
- Xfce team — Lightweight desktop foundation
- Ubuntu team — Base distribution

## Status

- Mission Control: native GTK overview implemented; keyboard navigation and window/workspace interaction are implemented; hardware visual/thumbnail validation remains.
- Spaces management: 1–16 workspaces with add/remove/switch support.
- Mavericks theme: implemented in the current Xfce/GTK3 stack.
- Keyboard shortcuts: implemented and contract-tested.
- Automated tests and CI gates: present; hardware-dependent behavior remains explicitly marked.


## Installation status

The repository currently provides the Arch live ISO and project-specific firstboot/profile scripts, but not a repository-controlled graphical installer or automatic target-user provisioning flow. Until that installer contract is implemented, firstboot must be invoked explicitly during the manual installation procedure. Do not assume Calamares, archinstall hooks, or automatic target-user discovery.
