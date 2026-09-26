# Mavericks Linux — Keyboard Shortcut Reference

Central reference for all global keyboard bindings. Super = Windows/Command key.

## Application Launchers

| Shortcut | Action | Backend |
|---|---|---|
| Super+Space | Spotlight (search files/apps) | rofi + mv-spotlight + plocate |
| Super+L | Launchpad (app grid) | rofi + mv-launchpad |
| Super+Tab | Mission Control (window overview) | rofi + mv-mission-control |
| Super+F | Finder (Thunar) | Thunar 4.x |

## File Operations

| Shortcut | Action | Backend |
|---|---|---|
| Super+N | New Folder on Desktop | mv-newfolder |
| Super+Shift+N | New Folder in Home | mv-newfolder |
| Super+I | Get Info (Home) | mv-getinfo |
| Super+O | Open With (Home) | mv-openwith |

## System

| Shortcut | Action | Backend |
|---|---|---|
| Super+Comma | System Settings | mv-settings |
| Super+C | Control Center | mv-control |
| Super+Shift+V | Notification Center | mv-notification-center |
| Super+Shift+Space | Quick Look (Thunar selection) | mv-quicklook-thunar |
| Ctrl+Alt+Escape | Power dialog (Sleep/Restart/Shut Down/Log Out) | mv-power-ui |
| Ctrl+Alt+Logout | Log Out | mv-power-ui logout |

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

## Window Management (xfwm4)

| Shortcut | Action | Backend |
|---|---|---|
| Super+Up | Tile window up | xfwm4 |
| Super+Down | Tile window down | xfwm4 |
| Super+Left | Tile window left | xfwm4 |
| Super+Right | Tile window right | xfwm4 |
| Super+Alt+Right | Next workspace | xfwm4 |
| Super+Alt+Left | Previous workspace | xfwm4 |

## Mavericks-like Mappings (not yet implemented)

| Shortcut | Action | Status |
|---|---|---|
| Super+Q | Quit application | NOT BOUND |
| Super+M | Minimize window | NOT BOUND |
| Super+H | Hide application | NOT BOUND |
| Super+W | Close window | NOT BOUND |
| Super+E | Finder | NOT BOUND |
| Super+T | New Terminal | NOT BOUND |

## Notes (mv-notes app-level accelerators)

| Shortcut | Action |
|---|---|
| Ctrl+N | New note |
| Ctrl+Shift+N | New folder |
| Delete | Delete note (to Recently Deleted; not while typing) |
| Ctrl+F | Focus search |
| Ctrl+P | Print note |
| Ctrl+E | Export note to .txt |
| Ctrl+Shift+P | Toggle pin |
| Escape | Clear search (when search focused) |

## Reminders (mv-reminders app-level accelerators)

| Shortcut | Action |
|---|---|
| Ctrl+N | New task (opens edit dialog immediately) |
| Ctrl+Shift+N | New list |
| Delete | Delete selected task (with confirm) |
| Ctrl+F | Focus search |
| Escape | Clear search |

Right-click context menus: task row (Edit / Toggle Done / Delete), list sidebar (Rename List / Delete List; last-list deletion blocked).

## Calendar (mv-calendar app-level accelerators)

| Shortcut | Action |
|---|---|
| Ctrl+N | New event |
| Ctrl+F | Focus search |
| Ctrl+E | Export ICS |
| Ctrl+I | Import ICS |
| ← / → | Previous / next period |
| T | Today |
| 1 / 2 / 3 | Month / Week / Day view |
| Delete | Delete selected event (with confirm) |
| Escape | Clear search |

Right-click event block: Edit / Delete. Double-click event block: edit. Global binding: Ctrl+Alt+C opens Calendar.

## Xfce global bindings

- All bindings are in `xfce4-keyboard-shortcuts.xml` (channel: `commands/default` and `xfwm4/default`)
- No conflicts detected (all bindings unique)
- No orphan bindings (all scripts exist in `/usr/bin/`)
- The `mv-*` scripts are in `/usr/bin/` via the `mavericks-apps` package
- rofi themes: `/usr/share/mavericks-apps/rofi-*.rasi`
