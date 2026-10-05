# MavLinOS — Keyboard Shortcut Reference

Source of truth for **global** bindings:
`packages/mavericks-apps/.../config/xfce4-keyboard-shortcuts.xml`
(mirrored into airootfs skel). Super = Windows / Command key.

Only shortcuts listed under “Bound globally” are wired in that XML.
CLI helpers and app-level accelerators are separate.

## Bound globally — application launchers

| Shortcut | Action | Backend |
|---|---|---|
| Super+Space | Spotlight | rofi + mv-spotlight |
| Super+L | Launchpad | rofi + mv-launchpad |
| Super+Shift+L | Launchpad edit mode | mv-launchpad-edit |
| Super+Tab | Mission Control | mv-mission-control --native |
| Super+F3 | Mission Control GUI overlay | mv-mc-gui |
| Super+Shift+F | Finder (column UI) | mv-finder-columns |
| Super+E | Finder (column UI) | mv-finder-columns |
| Ctrl+Alt+T | Terminal | xfce4-terminal |
| Super+Comma | System Settings | mv-settings |
| Super+Shift+C | Control Center | mv-control |
| Super+Shift+V | Notification Center | mv-notification-center |
| Ctrl+Alt+C | Calendar | mv-calendar |

## Bound globally — file operations

| Shortcut | Action | Backend |
|---|---|---|
| Ctrl+Alt+N | New Folder on Desktop | mv-newfolder |
| Super+Shift+N | New Folder in Home | mv-newfolder |
| Super+I | Get Info | mv-getinfo |
| Super+O | Open With | mv-openwith |
| Super+Delete | Move to Trash | mv-trash |
| Super+Shift+Delete | Empty Trash | trash-empty |
| Super+Shift+E | Empty Trash | trash-empty |
| Super+F4 | Eject | mv-eject |
| Super+Shift+Space | Quick Look (Thunar) | mv-quicklook-thunar |

## Bound globally — window management

| Shortcut | Action | Backend |
|---|---|---|
| Super+Q | Quit focused application | mv-quit-app |
| Super+Shift+Q | Force Quit dialog | mv-force-quit |
| Super+Alt+Escape | Force Quit dialog (Cmd+Option+Esc) | mv-force-quit |
| Super+M | Minimize focused window | mv-minimize-window |
| Super+H | Hide focused application | mv-hide-app |
| Super+W | Close focused window | mv-close-window |
| Super+Up / Down / Left / Right | Tile window | xfwm4 |
| Alt+Tab | Cycle windows | xfwm4 |
| Alt+Shift+Tab | Cycle windows reverse | xfwm4 |

## Bound globally — Spaces

| Shortcut | Action | Backend |
|---|---|---|
| Super+1 … Super+4 | Switch to Space N | xfwm4 |
| Super+Alt+Left / Right | Previous / next Space | xfwm4 |

Note: Super+Left/Right tile the window; workspace switch uses Super+Alt+Arrow.

## Bound globally — screenshots

| Shortcut | Action | Backend |
|---|---|---|
| Super+Shift+3 | Full screen | mv-shot -m |
| Super+Shift+4 | Selection | mv-shot -i -c |
| Super+Shift+5 | Interactive | mv-shot -i |

## Bound globally — system / media

| Shortcut | Action | Backend |
|---|---|---|
| Ctrl+Alt+L | Lock Screen | xfce4-screensaver-command --lock |
| Ctrl+Alt+Escape | Power dialog | mv-power-ui |
| Ctrl+Alt+Delete | Log Out | mv-power-ui logout |
| XF86MonBrightnessUp / Down | Brightness | mv-brightness |
| XF86AudioRaise / Lower / Mute | Volume | pactl |
| XF86AudioPlay / Next / Prev / Stop | Media | mv-music |

## Mission Control CLI helpers (not global keybindings)

| Helper | Description |
|--------|-------------|
| `mv-mc-gui` | GUI overlay with thumbnails (GTK3) |
| `mv-mc-overview [--debug] [--list]` | CLI overview |
| `mv-mc-window-spaces` | Windows grouped by workspace (JSON) |
| `mv-mc-activate-window <wid>` | Focus window by ID |
| `mv-mc-thumbnail <wid> [width] [output]` | Window thumbnail PNG |
| `mv-mc-grid <count> [w] [h] [margin]` | Grid layout for thumbnails |
| `mv-workspace-count [get\|set N\|add\|remove]` | Workspace count (1–16) |

## Notes

- Function / media keys depend on firmware and `Fn`.
- App-level accelerators (Ctrl+C/V/T/F, Thunar Ctrl+1/2/3, in-app Space for Quick Look) stay in the application.
- Regression gates: `scripts/test-*-keys.py`, `test-workspaces.py`, `test-alt-tab.py`, `test-lock-screen.py`, `test-empty-trash-keys.py`, `test-trash-eject-keys.py`, `test-force-quit-key.py`.
