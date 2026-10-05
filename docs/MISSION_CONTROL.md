# MavLinOS Mission Control Implementation

## Overview

MavLinOS implements a full Mavericks-style Mission Control with:
- Window overview across all Spaces
- Visual thumbnails with grid layout
- Click/keyboard activation
- Dynamic Space management (1-16 Spaces)
- Non-breaking integration with Xfce

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  mv-mc-gui (GTK3)                   │
│              Fullscreen overlay UI                  │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ mv-mc-window │ │ mv-mc-grid   │ │ mv-mc-thumb  │
│ -spaces      │ │              │ │ -nail        │
│ JSON windows │ │ Grid layout  │ │ PNG thumbs   │
└──────────────┘ └──────────────┘ └──────────────┘
        │
        ▼
┌──────────────┐
│ mv-mc-       │
│ activate-    │
│ window       │
│ Focus by ID  │
└──────────────┘
```

## Components

### 1. `mv-mc-window-spaces` (CLI)

Lists all windows grouped by workspace.

**Output:**
```json
{
  "workspaces": [
    {
      "id": 1,
      "name": "Space 1",
      "windows": [
        {"wid": 12345, "title": "Finder", "app": "Thunar", ...}
      ]
    }
  ]
}
```

**Dependencies:** `python3-ewmh`, `python3-xlib`

### 2. `mv-mc-thumbnail` (CLI)

Generates window thumbnails.

**Usage:**
```bash
mv-mc-thumbnail <wid> [width] [output.png]
```

**Dependencies:** `imagemagick` (import) or `scrot`

### 3. `mv-mc-grid` (CLI)

Calculates optimal grid layout for thumbnails.

**Output:**
```json
{
  "rows": 2,
  "cols": 3,
  "cell_width": 400,
  "cell_height": 300,
  "windows": [{"index": 0, "x": 50, "y": 50, ...}]
}
```

### 4. `mv-mc-activate-window` (CLI)

Activates/focuses a window by ID.

**Usage:**
```bash
mv-mc-activate-window <wid>
```

**Dependencies:** `wmctrl` or `xdotool`

### 5. `mv-mc-overview` (CLI integration)

Integrates all helpers for CLI-based overview.

**Modes:**
- `--list`: Text list of windows
- `--debug`: JSON debug output

### 6. `mv-mc-gui` (GTK3 overlay)

**Full visual Mission Control experience.**

**Features:**
- Fullscreen overlay
- Thumbnail grid
- Click/Enter to activate
- ESC to close
- Workspace grouping

**Dependencies:** `python3-gi`, `gir1.2-gtk-3.0`

**Usage:**
```bash
mv-mc-gui [--debug]
```

### 7. `mv-workspace-count` (CLI)

Manages Space count (1-16).

**Usage:**
```bash
mv-workspace-count get           # Show current count
mv-workspace-count set 4         # Set to 4 Spaces
mv-workspace-count add           # Add one Space
mv-workspace-count remove        # Remove one Space
```

## Keyboard Bindings

| Key | Action |
|-----|--------|
| `F3` | Toggle Mission Control GUI |
| `Super+Up` | Alternative MC toggle |
| `Super+1`..`Super+9` | Switch to Space N |
| `Super+Right/Left` | Next/Previous Space |
| `Super+Shift+A` | Add Space |
| `Super+Shift+D` | Remove Space |

## Testing

### Unit Tests

```bash
# Window spaces
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_windows.py

# Thumbnail helper
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_thumbnail_helper.py

# Grid helper
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_grid.py

# Activate helper
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_activate.py

# Overview integration
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_overview.py

# GUI overlay
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_mission_control_gui.py

# Workspace count
python3 packages/mavericks-apps/src/mavericks-apps/tests/test_workspace_count_helper.py

# F3 binding
python3 tests/test_f3_mission_control_binding.py
```

### CI Gates

```bash
ci/test-f3-binding.sh
```

## Configuration

### Xfce Panel Shortcuts

File: `configs/desktop/xfce/xfce4-panel.xml`

```xml
<property name="shortcuts" type="empty">
  <property name="&lt;Super&gt;F3" type="string" value="mv-mc-gui"/>
</property>
```

### Workspace Count

File: `~/.config/xfce4/xfconf/xfce4-desktop.xml`

```xml
<property name="/general/workspace_count" type="int" value="4"/>
```

## Mavericks Fidelity

| Feature | Status | Notes |
|---------|--------|-------|
| Window thumbnails | ✅ | Generated on-demand |
| Grid layout | ✅ | Dynamic, screen-aware |
| Space grouping | ✅ | Windows grouped by Space |
| Click activation | ✅ | GTK3 overlay |
| Keyboard navigation | ✅ | Arrow keys + Enter |
| ESC to close | ✅ | Implemented |
| Add Space (+) | ✅ | Via helper |
| Remove Space (X) | ✅ | Non-active only |
| 1-16 Spaces | ✅ | Mavericks limits enforced |
| F3 binding | ✅ | Non-breaking |

## Troubleshooting

### No thumbnails generated

Check dependencies:
```bash
sudo apt install imagemagick scrot
```

### GTK3 not available

Install:
```bash
sudo apt install python3-gi gir1.2-gtk-3.0
```

### F3 not working

Reload panel:
```bash
xfce4-panel -r
```

Or manually run:
```bash
mv-mc-gui
```

## Future Enhancements

- [ ] Smooth animations (zoom in/out)
- [ ] Window clustering by app
- [ ] Search/filter in MC
- [ ] Touchpad gesture support
- [ ] Multi-monitor awareness
- [ ] Performance optimization (cached thumbnails)

## References

- Issue #1: Architecture execution plan
- Issue #2: Poppy OS X Revieve audit
- `docs/KEYBOARD.md`: Full keyboard reference
