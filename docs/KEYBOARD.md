# MavLinOS — Keyboard Shortcut Reference

Source of truth: `packages/mavericks-apps/.../config/xfce4-keyboard-shortcuts.xml`
(mirrored into airootfs skel). Super = Windows / Command key.

## Application launchers

| Shortcut | Action | Backend |
|---|---|---|
| Super+Space | Spotlight | rofi + mv-spotlight |
| Super+L | Launchpad | rofi + mv-launchpad |
| Super+Shift+L | Launchpad edit mode | mv-launchpad-edit |
| Super+Tab | Mission Control | mv-mission-control --native |
| Super+Shift+F | Finder (column UI) | mv-finder-columns |
| Super+E | Finder (column UI) | mv-finder-columns |
| Ctrl+Alt+T | Terminal | xfce4-terminal |
| Super+Comma | System Settings | mv-settings |
| Super+Shift+C | Control Center | mv-control |
| Super+Shift+V | Notification Center | mv-notification-center |
| Ctrl+Alt+C | Calendar | mv-calendar |

## File operations

| Shortcut | Action | Backend |
|---|---|---|
| Ctrl+Alt+N | New Folder on Desktop | mv-newfolder |
| Super+Shift+N | New Folder in Home | mv-newfolder |
| Super+I | Get Info | mv-getinfo |
| Super+O | Open With | mv-openwith |
| Super+Delete | Move to Trash | mv-trash (trash-put / Delete key) |
| Super+Shift+Delete | Empty Trash | trash-empty |
| Super+Shift+E | Empty Trash | trash-empty |
| Super+F4 | Eject | mv-eject |
| Super+Shift+Space | Quick Look (Thunar) | mv-quicklook-thunar |

## Window management

| Shortcut | Action | Backend |
|---|---|---|
| Super+Q | Quit focused application | mv-quit-app |
| Super+Shift+Q | Force Quit dialog | mv-force-quit |
| Super+M | Minimize focused window | mv-minimize-window |
| Super+H | Hide focused application | mv-hide-app |
| Super+W | Close focused window | mv-close-window |
| Super+Up / Down / Left / Right | Tile window | xfwm4 |
| Alt+Tab | Cycle windows | xfwm4 |
| Alt+Shift+Tab | Cycle windows reverse | xfwm4 |

## Spaces

| Shortcut | Action | Backend |
|---|---|---|
| Super+1 … Super+4 | Switch to Space N | xfwm4 |
| Super+Alt+Left / Right | Previous / next Space | xfwm4 |

## Screenshots

| Shortcut | Action | Backend |
|---|---|---|
| Super+Shift+3 | Full screen | mv-shot -m |
| Super+Shift+4 | Selection | mv-shot -i -c |
| Super+Shift+5 | Interactive | mv-shot -i |

## System

| Shortcut | Action | Backend |
|---|---|---|
| Ctrl+Alt+L | Lock Screen | xfce4-screensaver-command --lock |
| Ctrl+Alt+Escape | Power dialog | mv-power-ui |
| Ctrl+Alt+Delete | Log Out | mv-power-ui logout |
| XF86MonBrightnessUp / Down | Brightness | mv-brightness |
| XF86AudioRaise / Lower / Mute | Volume | pactl |
| XF86AudioPlay / Next / Prev / Stop | Media | mv-music |

## Notes

- Function / media keys depend on firmware and `Fn` behavior.
- App-level accelerators (Ctrl+C/V/T/F, Thunar Ctrl+1/2/3 zoom) stay in the application.
- Regression gates: `scripts/test-*-keys.py`, `scripts/test-workspaces.py`, `scripts/test-alt-tab.py`, `scripts/test-lock-screen.py`, `scripts/test-empty-trash-keys.py`, `scripts/test-trash-eject-keys.py`, `scripts/test-force-quit-key.py`.
