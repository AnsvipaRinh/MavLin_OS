# MavLinOS — Keyboard Shortcut Reference

Central reference for all global keyboard bindings. Super = Windows/Command key.

## Application Launchers

| Shortcut | Action | Backend |
|---|---|---|
| Super+Space | Spotlight (search files/apps) | rofi + mv-spotlight + plocate |
| Super+L | Launchpad (app grid) | rofi + mv-launchpad |
| Super+Tab | Mission Control (window overview) | rofi + mv-mission-control |
| Super+Shift+F | Finder (Thunar) | Thunar 4.x |

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
| Ctrl+Alt+Logout | Log Out | mv-power-ui logout |
| Super+E | Finder / Thunar | Thunar |
| Super+Shift+E | Empty Trash | trash-empty |

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

## Mavericks-like Mappings (app-level, handled by apps internally)

These shortcuts are NOT globally bound. They are handled by individual applications
using their Ctrl-key equivalents (Firefox, Thunar, terminal, etc.) to avoid
global conflicts. This is the correct Mavericks-like separation: app shortcuts
don't steal global shortcuts.

| Shortcut | Action | App-Level Equivalent | Status |
|---|---|---|---|
| Super+Q | Quit application | Ctrl+Q in Firefox | App-level |
| Super+M | Minimize window | xfwm4 Super+Down | App-level |
| Super+H | Hide application | — | App-level |
| Super+W | Close window/tab | Ctrl+W in Firefox | App-level |
| Super+E | Finder / Thunar | Super+Shift+F | App-level |
| Super+T | New tab | Ctrl+T in Firefox | App-level |
| Super+N | New window | Ctrl+N in Firefox | App-level |
| Super+C | Copy | Ctrl+C in Firefox/terminal | App-level |
| Super+F | Find | Ctrl+F in Firefox | App-level |

## Finder / Thunar (app-level accelerators)

Handled inside Thunar natively (binary-verified, Thunar 4.20) — same
app-level Ctrl split as macOS Cmd:

| Shortcut | Action |
|---|---|
| Ctrl+1 | Icon view (Finder default view) |
| Ctrl+2 | List view |
| Ctrl+3 | Compact view |
| Ctrl+= | Zoom in (icon/row size up) |
| Ctrl+- | Zoom out |
| Ctrl+0 | Normal size |

mv-finder-search and mv-finder-columns follow the same zoom convention
(Ctrl+= / Ctrl+- / Ctrl+0 over a 16/22/32/48 px icon ladder).

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
