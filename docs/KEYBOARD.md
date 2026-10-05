# MavLinOS Keyboard Reference

## Mission Control

| Action | Keys | Notes |
|--------|------|-------|
| Toggle Mission Control | `F3` (or `Super+Up`) | Shows all windows across Spaces |
| Add Desktop (Space) | `Super+Shift+A` | Creates new Space to the right |
| Remove Desktop (Space) | `Super+Shift+D` | Removes rightmost non-active Space |
| Switch to Space N | `Super+1`..`Super+9` | Direct Space navigation |
| Next Space | `Super+Right` | Move to next Space |
| Previous Space | `Super+Left` | Move to previous Space |
| Move window to next Space | `Super+Shift+Right` | Relocates focused window |
| Move window to previous Space | `Super+Shift+Left` | Relocates focused window |
| Overview UI (GUI) | `mv-mc-gui` | Full visual overlay with thumbnails |
| Overview UI (CLI) | `mv-mc-overview [--debug] [--list]` | Text-based overview |
| List windows by Space | `mv-mc-window-spaces` | JSON output for UI |
| Activate window from MC | `mv-mc-activate-window <wid>` | Focuses window by ID |
| Generate thumbnail | `mv-mc-thumbnail <wid> [width] [output]` | Window thumbnail PNG |
| Calculate grid layout | `mv-mc-grid <count> [width] [height] [margin]` | JSON grid positions |

## Window Management

| Action | Keys | Notes |
|--------|------|-------|
| Minimize window | `Super+Down` or `Super+M` | Sends to Dock/Plank |
| Close window | `Super+W` | Standard close |
| Force Quit | `Super+Shift+Q` | Force quit frontmost app |
| Hide app | `Super+H` | Hide current application |
| Show desktop | `F11` or `Super+Shift+D` | Push all windows aside |
| Cycle windows (App) | `Super+`\`` | Next window in app |
| Cycle windows (Reverse) | `Super+Shift+`\`` | Previous window in app |

## Finder-like Operations

| Action | Keys | Notes |
|--------|------|-------|
| New Folder | `Super+Shift+N` | In Thunar/Finder |
| Get Info | `Super+I` | File/folder info |
| Rename | `F2` or `Enter` | Rename selected item |
| Open with | `Super+Shift+O` | Choose application |
| Quick Look | `Space` | Preview file |
| Preview | `Super+P` | Open in Preview.app |
| Empty Trash | `Super+Shift+Delete` or `Super+Shift+E` | Clear trash (documented, unbound) |

## System

| Action | Keys | Notes |
|--------|------|-------|
| Spotlight | `Super+Space` or `Cmd+Space` | Search |
| Launchpad | `F4` or pinched thumb | App grid |
| Notification Center | `Super+Shift+N` | Notifications |
| Control Center | `F12` or `Super+C` | Quick settings |
| Brightness Up | `F2` | Increase display brightness |
| Brightness Down | `F1` | Decrease display brightness |
| Volume Up | `F12` | Increase audio |
| Volume Down | `F11` | Decrease audio |
| Mute | `F10` | Toggle mute |
| Lock screen | `Super+Shift+L` or `Super+Ctrl+Q` | Lock session |
| Terminal | `Super+T` or `Cmd+Space` → "Terminal" | Open terminal |
| Settings | `Super+,` | System preferences |

## Spaces Navigation

| Action | Keys | Notes |
|--------|------|-------|
| Space 1 | `Super+1` | First Space |
| Space 2 | `Super+2` | Second Space |
| Space 3 | `Super+3` | Third Space |
| ... | `Super+4`..`Super+9` | Up to 9 Spaces |
| Next Space | `Super+Right` | Cycle forward |
| Previous Space | `Super+Left` | Cycle backward |

## Mission Control Helpers (CLI)

| Helper | Description |
|--------|-------------|
| `mv-mc-gui` | Full GUI overlay with thumbnails (GTK3) |
| `mv-mc-overview [--debug] [--list]` | CLI overview integration |
| `mv-mc-window-spaces` | List windows grouped by workspace (JSON) |
| `mv-mc-activate-window <wid>` | Activate/focus window by ID |
| `mv-mc-thumbnail <wid> [width] [output]` | Generate window thumbnail PNG |
| `mv-mc-grid <count> [w] [h] [margin]` | Calculate grid layout for thumbnails |
| `mv-workspace-count [get|set N|add|remove]` | Manage workspace count (1-16) |

## Notes

- `Super` = Windows/Command key
- Function keys may require holding `Fn` depending on hardware
- Some shortcuts require Xfce keyboard settings to be configured
- Mission Control GUI requires GTK3 (`python3-gi`, `gir1.2-gtk-3.0`)
- Full Mission Control experience: `mv-mc-gui` for visual overlay
