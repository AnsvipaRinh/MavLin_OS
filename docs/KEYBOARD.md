# MavLinOS — Keyboard Shortcut Reference

Central reference for all global keyboard bindings. Super = Windows/Command key.

## Application Launchers

| Shortcut | Action | Backend |
|---|---|---|
| Super+Space | Spotlight (search files/apps) | rofi + mv-spotlight + plocate |
| Super+L | Launchpad (app grid) | rofi + mv-launchpad |
| Super+Shift+L | Launchpad edit mode | mv-launchpad-edit |
| Super+Tab | Mission Control (window overview) | rofi + mv-mission-control |
| Super+Shift+F | Finder (column UI) | mv-finder-columns |
| Super+E | Finder (column UI) | mv-finder-columns |

## File Operations

| Shortcut | Action | Backend |
|---|---|---|
| Ctrl+Alt+N | New Folder on Desktop | mv-newfolder |
| Super+Shift+N | New Folder in Home | mv-newfolder |
| Super+I | Get Info (Home) | mv-getinfo |
| Super+O | Open With (Home) | mv-openwith |
| Super+Shift+I | Get Info (Current) | mv-getinfo |
| Super+Shift+O | Open With (Current) | mv-openwith |
| Super+F4 | Eject (Selected) | mv-eject |
| Super+Delete | Move to Trash | trash-cli |
| Super+Shift+Delete | Empty Trash | trash-empty |

## System

| Shortcut | Action | Backend |
|---|---|---|
| Super+Comma | System Settings | mv-settings |
| Super+Shift+C | Control Center | mv-control |
| Super+Shift+V | Notification Center | mv-notification-center |
| Super+Shift+Space | Quick Look (Thunar selection) | mv-quicklook-thunar |
| Ctrl+Alt+Escape | Power dialog (Sleep/Restart/Shut Down/Log Out) | mv-power-ui |
| Ctrl+Alt+Delete | Log Out | mv-power-ui logout |
| Super+Shift+E | Empty Trash | trash-empty |

## Window management (global)

| Shortcut | Action | Backend |
|---|---|---|
| Super+Q | Quit focused application | mv-quit-app (xdotool) |
| Super+M | Minimize focused window | mv-minimize-window |
| Super+H | Hide focused application | mv-hide-app |
| Super+W | Close focused window | mv-close-window |

## Screenshots

| Shortcut | Action | Backend |
|---|---|---|
| Super+Shift+3 | Full screen to file | mv-shot |
| Super+Shift+4 | Selection to file | mv-shot -i |
| Super+Shift+5 | Interactive window to file | mv-shot -i -c |

## Volume

| Shortcut | Action | Backend |
|---|---|---|
| XF86AudioRaiseVolume | Volume +5% | pactl |
| XF86AudioLowerVolume | Volume -5% | pactl |
| XF86AudioMute | Mute toggle | pactl |

## Display brightness

| Shortcut | Action | Backend |
|---|---|---|
| XF86MonBrightnessUp | Brightness +5% | mv-brightness (sysfs + udev uaccess) |
| XF86MonBrightnessDown | Brightness -5% | mv-brightness (sysfs + udev uaccess) |

## Window tiling (xfwm4)

| Shortcut | Action | Backend |
|---|---|---|
| Super+Up | Tile window up | xfwm4 |
| Super+Down | Tile window down | xfwm4 |
| Super+Left | Tile window left | xfwm4 |
| Super+Right | Tile window right | xfwm4 |
| Super+Alt+Right | Next workspace | xfwm4 |
| Super+Alt+Left | Previous workspace | xfwm4 |

## Mavericks-like mappings still app-level

These are **not** globally bound (to avoid stealing browser/editor shortcuts):

| Shortcut | Action | App-level equivalent |
|---|---|---|
| Super+T | New tab | Ctrl+T in Firefox |
| Super+N | New window | Ctrl+N in Firefox |
| Super+C | Copy | Ctrl+C |
| Super+F | Find | Ctrl+F |

## Finder / Thunar (app-level accelerators)

| Shortcut | Action |
|---|---|
| Ctrl+1 | Icon view |
| Ctrl+2 | List view |
| Ctrl+3 | Compact view |
| Ctrl+= | Zoom in |
| Ctrl+- | Zoom out |
| Ctrl+0 | Normal size |

## Xfce global bindings

- Source of truth: `packages/mavericks-apps/.../xfce4-keyboard-shortcuts.xml` (mirrored into airootfs skel)
- `mv-*` scripts ship via the `mavericks-apps` package
- Regression gates: `scripts/test-finder-launcher.py`, `scripts/test-window-keys.py`, `scripts/test-brightness-keys.py`, `scripts/test-backlight-udev.py`
