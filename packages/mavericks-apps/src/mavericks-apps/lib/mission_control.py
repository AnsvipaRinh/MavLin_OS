#!/usr/bin/env python3
"""Mission Control — read-only window state enumeration via EWMH.

Primary backend: python-xlib (Xlib) for direct X11/EWMH queries.
Fallback: wmctrl + xwininfo subprocess parsing.
All functions are HEADLESS — no Gtk.init, no display connection beyond Xlib.
"""

import os
import sys
import subprocess
from typing import List, Dict, Any, Optional, Tuple

# --- Xlib availability detection ---
_XLIB_AVAILABLE = False
try:
    from Xlib import display as xdisplay
    from Xlib import X
    from Xlib import Xatom
    from Xlib.protocol import rq
    _XLIB_AVAILABLE = True
except ImportError:
    _XLIB_AVAILABLE = False


class WorkspaceModel:
    """Tracks per-workspace window sets, active desktop, names.

    Pure data model — no X11, no GUI, fully unit-testable.
    """

    def __init__(self, workspaces: Dict[str, Any], windows: List[Dict[str, Any]]):
        """Initialize with workspace info and window list.

        Args:
            workspaces: dict from get_workspaces() with keys 'count', 'names', 'current'
            windows: list of window dicts from enumerate_windows() with 'desktop' key
        """
        self.count = workspaces.get("count", 1)
        self.names = workspaces.get("names", [f"Desktop {i+1}" for i in range(self.count)])
        self.current = workspaces.get("current", 0)

        # Validate names count
        if len(self.names) < self.count:
            self.names.extend([f"Desktop {i+1}" for i in range(len(self.names), self.count)])

        # Per-workspace window sets: maps desktop index -> list of windows on that desktop
        self._desktops: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(self.count)}

        for w in windows:
            desktop = w.get("desktop", 0)
            # Clamp to valid range
            if desktop < 0:
                desktop = 0
            if desktop >= self.count:
                desktop = self.count - 1
            self._desktops[desktop].append(w)

    @property
    def desktops(self) -> Dict[int, List[Dict[str, Any]]]:
        """Return unmodifiable view of per-desktop window lists."""
        return dict(self._desktops)

    def windows_on_desktop(self, desktop_index: int) -> List[Dict[str, Any]]:
        """Return windows on the specified desktop index."""
        return self._desktops.get(desktop_index, [])

    def is_active(self, desktop_index: int) -> bool:
        """Check if the given desktop is the current/active one."""
        return desktop_index == self.current

    def active_desktop(self) -> int:
        """Return the index of the active desktop."""
        return self.current

    def name_for_desktop(self, desktop_index: int) -> str:
        """Return the name for the given desktop index (wraps around)."""
        return self.names[desktop_index % len(self.names)]


def compute_layout(
    windows: List[Dict[str, Any]],
    workspaces: Dict[str, Any],
    screen_w: int,
    screen_h: int,
    margin: int = 20,
    gap: int = 10,
) -> List[Dict[str, Any]]:
    """Pure function: compute non-overlapping grid layout for mission control overview.

    Given a list of windows + workspace model + screen dimensions, computes per-window
    rectangle (x, y, w, h), workspace assignment, and z-order.

    Layout strategy:
    - Windows grouped by workspace
    - Active workspace rendered first (topmost, z=0)
    - Each workspace's windows laid out in a grid with auto-fit rows/cols
    - Aspect-ratio preservation per window
    - Margin + gap around/between windows
    - Empty workspaces get placeholder rectangles

    Returns list of dicts with keys:
        win_id: str
        rect: dict {x, y, w, h}
        workspace: int (desktop index)
        z: int (lower = higher priority; active workspace z=0)
    """
    model = WorkspaceModel(workspaces, windows)

    # Count total windows across all desktops
    total_windows = sum(len(model.windows_on_desktop(d)) for d in range(model.count))

    # If no windows at all, return empty layout (no point laying out an empty grid)
    if total_windows == 0:
        return []

    # Always include all desktops in the layout
    # Sort desktops: active first, then others in order
    active_desktop = model.active_desktop()
    all_desktops = list(range(model.count))
    if active_desktop in all_desktops:
        all_desktops.remove(active_desktop)
        all_desktops.insert(0, active_desktop)

    layout = []
    z = 0  # z-order: active workspace gets z=0,1,2... then others

    available_w = screen_w - 2 * margin
    available_h = screen_h - 2 * margin

    for desktop_idx in all_desktops:
        windows_on_desk = model.windows_on_desktop(desktop_idx)

        if windows_on_desk:
            # Compute grid columns based on aspect-ratio-preserving auto-fit
            best_cols = 1
            best_score = float("inf")
            for cols in range(1, len(windows_on_desk) + 1):
                rows = -(-len(windows_on_desk) // cols)  # ceiling division
                # Cell size:
                cell_w = available_w / cols
                cell_h = (available_h - (rows - 1) * gap) / rows if rows > 0 else available_h
                # Score: how well does this fill the screen?
                if cell_w > 0 and cell_h > 0:
                    # Target cell size that's not too small (> 80px wide or tall)
                    score = abs(cell_w - 150) + abs(cell_h - 150)
                    if score < best_score:
                        best_score = score
                        best_cols = cols
            cols = best_cols
            rows = -(-len(windows_on_desk) // cols)  # ceiling division

            # Compute cell geometry
            cell_w = available_w / cols
            cell_h = available_h / rows

            # Position windows in this grid
            for win_idx, win in enumerate(windows_on_desk):
                col = win_idx % cols
                row = win_idx // cols

                rect_x = margin + col * cell_w + col * gap
                rect_y = margin + row * cell_h + row * gap
                rect_w = cell_w - gap  # subtract gap to avoid overlap between adjacent cells
                rect_h = cell_h - gap

                # Ensure minimum size
                if rect_w < 40:
                    rect_w = 40
                if rect_h < 40:
                    rect_h = 40

                # Clamp to screen
                if rect_x + rect_w > screen_w:
                    rect_x = screen_w - rect_w - margin
                if rect_y + rect_h > screen_h:
                    rect_y = screen_h - rect_h - margin
                if rect_x < margin:
                    rect_x = margin
                if rect_y < margin:
                    rect_y = margin

                layout.append({
                    "win_id": win["win_id"],
                    "rect": {
                        "x": rect_x,
                        "y": rect_y,
                        "width": rect_w,
                        "height": rect_h,
                    },
                    "workspace": desktop_idx,
                    "z": z,
                })

            z += 1  # next workspace gets higher z

        # Always add a placeholder for desktops with no windows
        if not windows_on_desk:
            cell_w = available_w / 1
            cell_h = available_h / 1
            layout.append({
                "win_id": "",
                "rect": {
                    "x": margin,
                    "y": margin,
                    "width": cell_w,
                    "height": cell_h,
                },
                "workspace": desktop_idx,
                "z": z,
                "placeholder": True,
            })
            z += 1

    # Sort by z-order (already in order, but ensure)
    layout.sort(key=lambda item: item.get("z", 999))

    return layout


class LayoutModel:
    """High-level layout model: computes grid positions for mission control overview.

    Takes enumerate_windows() output + get_workspaces() → computes grid positions
    for overview (rows/cols auto-fit), per-window rect (x,y,w,h), z-order, workspace assignment.

    Pure functions, zero display, zero Gtk, unit-testable.
    """

    def __init__(self, screen_w: int, screen_h: int, margin: int = 20, gap: int = 10):
        """Initialize layout model with screen dimensions.

        Args:
            screen_w: total screen width in pixels
            screen_h: total screen height in pixels
            margin: outer margin around the overview window
            gap: gap between grid cells
        """
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.margin = margin
        self.gap = gap
        self.windows: List[Dict[str, Any]] = []
        self.workspaces: Dict[str, Any] = {"count": 1, "names": ["Desktop 1"], "current": 0}

    def set_windows(self, windows: List[Dict[str, Any]]) -> None:
        """Set the window list (output of enumerate_windows())."""
        self.windows = windows

    def set_workspaces(self, workspaces: Dict[str, Any]) -> None:
        """Set the workspace model (output of get_workspaces())."""
        self.workspaces = workspaces

    def compute(self) -> List[Dict[str, Any]]:
        """Compute the full layout: returns list of {win_id, rect, workspace, z}.

        Returns:
            List of layout dicts sorted by z-order (active workspace first).
        """
        return compute_layout(
            self.windows,
            self.workspaces,
            self.screen_w,
            self.screen_h,
            self.margin,
            self.gap,
        )


# --- Internal helpers ---

def _get_display():
    """Get Xlib display connection or None if unavailable."""
    if not _XLIB_AVAILABLE:
        return None
    try:
        return xdisplay.Display()
    except Exception:
        return None


def _get_atom(disp, name: str):
    """Get atom by name, caching on display."""
    if not hasattr(disp, '_mc_atom_cache'):
        disp._mc_atom_cache = {}
    if name not in disp._mc_atom_cache:
        disp._mc_atom_cache[name] = disp.intern_atom(name)
    return disp._mc_atom_cache[name]


def _get_window_property(disp, win, atom_name: str, prop_type=0, length=1024):
    """Fetch a window property safely."""
    atom = _get_atom(disp, atom_name)
    try:
        prop = win.get_full_property(atom, prop_type)
        if prop and prop.value:
            return prop.value
    except Exception:
        pass
    return None


def _get_window_property_string(disp, win, atom_name: str) -> str:
    """Fetch a string property (UTF-8 or STRING)."""
    atom = _get_atom(disp, atom_name)
    try:
        # Try UTF8_STRING first
        prop = win.get_full_property(atom, _get_atom(disp, "UTF8_STRING"))
        if prop and prop.value:
            if isinstance(prop.value, bytes):
                return prop.value.decode("utf-8", errors="replace")
            return str(prop.value)
    except Exception:
        pass
    try:
        # Fallback to STRING
        prop = win.get_full_property(atom, Xatom.STRING)
        if prop and prop.value:
            if isinstance(prop.value, bytes):
                return prop.value.decode("utf-8", errors="replace")
            return str(prop.value)
    except Exception:
        pass
    return ""


def _get_window_geometry_xlib(disp, win) -> Dict[str, int]:
    """Get window geometry via Xlib (includes frame extents if available)."""
    geo = {"x": 0, "y": 0, "width": 0, "height": 0}
    try:
        g = win.get_geometry()
        geo["x"] = g.x
        geo["y"] = g.y
        geo["width"] = g.width
        geo["height"] = g.height
    except Exception:
        pass

    # Try to get _GTK_FRAME_EXTENTS for frame correction
    extents = _get_window_property(disp, win, "_GTK_FRAME_EXTENTS", Xatom.CARDINAL, 4)
    if extents and len(extents) == 4:
        left, right, top, bottom = extents
        geo["x"] -= left
        geo["y"] -= top
        geo["width"] += left + right
        geo["height"] += top + bottom
    return geo


def _get_window_state_xlib(disp, win) -> List[str]:
    """Get window state atoms from _NET_WM_STATE."""
    states = []
    prop = _get_window_property(disp, win, "_NET_WM_STATE", Xatom.ATOM)
    if prop:
        for atom_val in prop:
            try:
                name = disp.get_atom_name(atom_val)
                if name:
                    states.append(name)
            except Exception:
                pass
    return states


def _is_window_mapped(disp, win) -> bool:
    """Check if window is mapped (not iconified/hidden)."""
    try:
        attrs = win.get_attributes()
        return attrs.map_state == X.MapState.Viewable
    except Exception:
        pass
    return False


# --- Xlib implementation ---

def _enumerate_windows_xlib() -> List[Dict[str, Any]]:
    """Enumerate windows using Xlib/EWMH."""
    disp = _get_display()
    if not disp:
        return []

    windows = []
    root = disp.screen().root

    # Get _NET_CLIENT_LIST
    client_list = _get_window_property(disp, root, "_NET_CLIENT_LIST", Xatom.WINDOW)
    if not client_list:
        disp.close()
        return []

    # Get current desktop
    current_desktop = 0
    curr_desk_prop = _get_window_property(disp, root, "_NET_CURRENT_DESKTOP", Xatom.CARDINAL)
    if curr_desk_prop:
        current_desktop = int(curr_desk_prop[0])

    for win_id in client_list:
        try:
            win = disp.create_resource_object('window', win_id)
        except Exception:
            continue

        # Title
        title = _get_window_property_string(disp, win, "_NET_WM_NAME")
        if not title:
            title = _get_window_property_string(disp, win, "WM_NAME")
        if not title:
            title = "(no title)"

        # WM_CLASS
        wm_class = ""
        try:
            cls = win.get_wm_class()
            if cls:
                wm_class = cls[1] if cls[1] else cls[0]  # res_class preferred
        except Exception:
            pass

        # PID
        pid = 0
        pid_prop = _get_window_property(disp, win, "_NET_WM_PID", Xatom.CARDINAL)
        if pid_prop:
            pid = int(pid_prop[0])

        # Desktop
        desktop = 0
        desk_prop = _get_window_property(disp, win, "_NET_WM_DESKTOP", Xatom.CARDINAL)
        if desk_prop:
            desktop = int(desk_prop[0])
            # 0xFFFFFFFF means sticky (all desktops)
            if desktop == 0xFFFFFFFF:
                desktop = -1

        # Geometry
        geometry = _get_window_geometry_xlib(disp, win)

        # Mapped state
        mapped = _is_window_mapped(disp, win)

        # State atoms
        state_atoms = _get_window_state_xlib(disp, win)

        windows.append({
            "win_id": hex(win_id),
            "title": title,
            "wm_class": wm_class,
            "pid": pid,
            "desktop": desktop,
            "geometry": geometry,
            "mapped": mapped,
            "state": state_atoms,
        })

    disp.close()
    return windows


def _get_active_window_xlib() -> Optional[Dict[str, Any]]:
    """Get active window using Xlib/EWMH."""
    disp = _get_display()
    if not disp:
        return None

    root = disp.screen().root
    active_prop = _get_window_property(disp, root, "_NET_ACTIVE_WINDOW", Xatom.WINDOW)
    if not active_prop:
        disp.close()
        return None

    win_id = int(active_prop[0])
    disp.close()
    return {"win_id": hex(win_id)}


def _get_workspaces_xlib() -> Dict[str, Any]:
    """Get workspace info using Xlib/EWMH."""
    disp = _get_display()
    if not disp:
        return {"count": 1, "names": ["Desktop 1"], "current": 0}

    root = disp.screen().root
    result = {"count": 1, "names": ["Desktop 1"], "current": 0}

    # Number of desktops
    num_prop = _get_window_property(disp, root, "_NET_NUMBER_OF_DESKTOPS", Xatom.CARDINAL)
    if num_prop:
        result["count"] = int(num_prop[0])

    # Desktop names
    names_prop = _get_window_property(disp, root, "_NET_DESKTOP_NAMES", Xatom.STRING)
    if names_prop:
        # Property value is a list of null-terminated strings
        if isinstance(names_prop, bytes):
            names_str = names_prop.decode("utf-8", errors="replace")
        else:
            names_str = str(names_prop)
        names = [n for n in names_str.split('\x00') if n]
        if names:
            result["names"] = names

    # Current desktop
    curr_prop = _get_window_property(disp, root, "_NET_CURRENT_DESKTOP", Xatom.CARDINAL)
    if curr_prop:
        result["current"] = int(curr_prop[0])

    disp.close()
    return result


# --- Fallback implementation (wmctrl + xwininfo) ---

def _enumerate_windows_fallback() -> List[Dict[str, Any]]:
    """Enumerate windows using wmctrl + xwininfo."""
    windows = []

    # Get window list from wmctrl
    try:
        result = subprocess.run(
            ["wmctrl", "-l", "-x"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    except Exception:
        return []

    # Get current workspace
    current_workspace = 0
    try:
        result = subprocess.run(
            ["wmctrl", "-d"],
            capture_output=True,
            text=True,
            timeout=2
        )
        for line in result.stdout.strip().split("\n"):
            if "*" in line:
                parts = line.split()
                if parts:
                    current_workspace = int(parts[0])
                break
    except Exception:
        pass

    for line in lines:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        win_id = parts[0]
        desktop_str = parts[1]
        win_class = parts[2]
        title = parts[4]

        # Skip panel/dock windows
        if title.startswith("xfce4-panel") or title.startswith("Plank") or win_class == "xfce4-panel":
            continue

        try:
            desktop = int(desktop_str)
        except ValueError:
            desktop = -1  # sticky

        # Get geometry via xwininfo
        geometry = {"x": 0, "y": 0, "width": 0, "height": 0}
        try:
            result = subprocess.run(
                ["xwininfo", "-id", win_id],
                capture_output=True,
                text=True,
                timeout=2
            )
            for gline in result.stdout.split("\n"):
                gline = gline.strip()
                if gline.startswith("Absolute upper-left X:"):
                    geometry["x"] = int(gline.split(":")[1].strip())
                elif gline.startswith("Absolute upper-left Y:"):
                    geometry["y"] = int(gline.split(":")[1].strip())
                elif gline.startswith("Width:"):
                    geometry["width"] = int(gline.split(":")[1].strip())
                elif gline.startswith("Height:"):
                    geometry["height"] = int(gline.split(":")[1].strip())
        except Exception:
            pass

        # State info (limited in fallback)
        state = []
        if desktop == -1:
            state.append("_NET_WM_STATE_STICKY")

        windows.append({
            "win_id": win_id,
            "title": title,
            "wm_class": win_class,
            "pid": 0,  # Not available via wmctrl
            "desktop": desktop,
            "geometry": geometry,
            "mapped": geometry["width"] > 0 and geometry["height"] > 0,
            "state": state,
        })

    return windows


def _get_active_window_fallback() -> Optional[Dict[str, Any]]:
    """Get active window using xprop."""
    try:
        result = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True,
            text=True,
            timeout=2
        )
        for line in result.stdout.split("\n"):
            if "_NET_ACTIVE_WINDOW" in line and "0x" in line:
                # Format: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x123456
                parts = line.split()
                for p in parts:
                    if p.startswith("0x"):
                        return {"win_id": p.strip(",")}
    except Exception:
        pass
    return None


def _get_workspaces_fallback() -> Dict[str, Any]:
    """Get workspace info using wmctrl -d."""
    result = {"count": 1, "names": ["Desktop 1"], "current": 0}
    try:
        proc = subprocess.run(
            ["wmctrl", "-d"],
            capture_output=True,
            text=True,
            timeout=2
        )
        lines = proc.stdout.strip().split("\n")
        if lines and lines[0]:
            result["count"] = len(lines)
            names = []
            current = 0
            for i, line in enumerate(lines):
                parts = line.split(None, 8)
                if len(parts) >= 9:
                    names.append(parts[8] if parts[8] else f"Desktop {i+1}")
                    if "*" in line:
                        current = i
            if names:
                result["names"] = names
            result["current"] = current
    except Exception:
        pass
    return result


# --- Public API ---

def enumerate_windows() -> List[Dict[str, Any]]:
    """Return list of all windows with metadata.

    Each dict contains:
        win_id: str (hex window ID)
        title: str (window title)
        wm_class: str (WM_CLASS res_class)
        pid: int (process ID)
        desktop: int (workspace number, -1 for sticky/all)
        geometry: dict {x, y, width, height}
        mapped: bool (window is viewable)
        state: list of str (EWMH state atoms like _NET_WM_STATE_HIDDEN)
    """
    if _XLIB_AVAILABLE:
        result = _enumerate_windows_xlib()
        if result is not None:
            return result
    result = _enumerate_windows_fallback()
    if result is None:
        return []
    return result


def get_active_window() -> Optional[Dict[str, Any]]:
    """Return currently active window info or None.

    Returns dict with win_id (hex), or None if unavailable.
    """
    if _XLIB_AVAILABLE:
        result = _get_active_window_xlib()
        if result is not None:
            return result
    return _get_active_window_fallback()


def get_workspaces() -> Dict[str, Any]:
    """Return workspace information.

    Returns dict with:
        count: int (number of desktops)
        names: list of str (desktop names)
        current: int (current desktop index)
    """
    if _XLIB_AVAILABLE:
        result = _get_workspaces_xlib()
        if result is not None:
            return result
    return _get_workspaces_fallback()



# --- EWMH activation helpers ---

def _parse_window_id(win_id: Any) -> Optional[int]:
    """Convert a hex/int X11 window id to an integer resource id."""
    try:
        if isinstance(win_id, str):
            return int(win_id.strip(), 0)
        return int(win_id)
    except (TypeError, ValueError):
        return None


def _send_root_client_message(disp, message_atom_name: str, data: List[int]) -> bool:
    """Send an EWMH ClientMessage to the root window."""
    if not disp or not _XLIB_AVAILABLE:
        return False
    try:
        from Xlib.protocol import event
        root = disp.screen().root
        message_atom = _get_atom(disp, message_atom_name)
        message = event.ClientMessage(window=root, client_type=message_atom, data=(32, data))
        root.send_event(
            message,
            event_mask=(X.SubstructureRedirectMask | X.SubstructureNotifyMask),
        )
        disp.flush()
        return True
    except Exception:
        return False


def _switch_workspace_xlib(disp, desktop: int) -> bool:
    """Switch to an EWMH desktop using _NET_CURRENT_DESKTOP."""
    if desktop < 0:
        return False
    return _send_root_client_message(
        disp, "_NET_CURRENT_DESKTOP", [int(desktop), 0, 2, 0, 0]
    )


def _unminimize_window_xlib(disp, win) -> bool:
    """Remove _NET_WM_STATE_HIDDEN and request the window to be mapped."""
    changed = False
    try:
        from Xlib.protocol import event
        root = disp.screen().root
        state_atom = _get_atom(disp, "_NET_WM_STATE")
        hidden_atom = _get_atom(disp, "_NET_WM_STATE_HIDDEN")
        message = event.ClientMessage(
            window=win,
            client_type=state_atom,
            data=(32, [0, hidden_atom, 0, 2, 0]),
        )
        root.send_event(
            message,
            event_mask=(X.SubstructureRedirectMask | X.SubstructureNotifyMask),
        )
        changed = True
    except Exception:
        pass
    try:
        win.map()
        changed = True
    except Exception:
        pass
    return changed


def _activate_window_xlib(win_id: Any) -> bool:
    """Activate a window with EWMH, switching workspace and restoring hidden state."""
    parsed_id = _parse_window_id(win_id)
    if parsed_id is None:
        return False

    disp = _get_display()
    if not disp:
        return False

    try:
        root = disp.screen().root
        target = disp.create_resource_object("window", parsed_id)

        desktop = _get_window_property(disp, target, "_NET_WM_DESKTOP", Xatom.CARDINAL)
        target_desktop = int(desktop[0]) if desktop else -1
        if target_desktop == 0xFFFFFFFF:
            target_desktop = -1

        current = _get_window_property(disp, root, "_NET_CURRENT_DESKTOP", Xatom.CARDINAL)
        current_desktop = int(current[0]) if current else 0

        if target_desktop >= 0 and target_desktop != current_desktop:
            if not _switch_workspace_xlib(disp, target_desktop):
                return False

        states = _get_window_state_xlib(disp, target)
        if "_NET_WM_STATE_HIDDEN" in states:
            _unminimize_window_xlib(disp, target)

        from Xlib.protocol import event
        active_atom = _get_atom(disp, "_NET_ACTIVE_WINDOW")
        message = event.ClientMessage(
            window=target,
            client_type=active_atom,
            data=(32, [2, 0, parsed_id, 0, 0]),
        )
        root.send_event(
            message,
            event_mask=(X.SubstructureRedirectMask | X.SubstructureNotifyMask),
        )
        try:
            target.raise_window()
        except Exception:
            pass
        disp.flush()
        return True
    except Exception:
        return False
    finally:
        try:
            disp.close()
        except Exception:
            pass


def set_workspace_count(count: int) -> bool:
    """Set the number of X11 workspaces, matching Mavericks' Spaces limit."""
    try:
        count = int(count)
    except (TypeError, ValueError):
        return False
    if not 1 <= count <= 16:
        return False

    # wmctrl delegates the workspace-count change to the window manager.
    # xfwm4 accepts this EWMH operation without taking ownership of windows.
    try:
        result = subprocess.run(
            ["wmctrl", "-n", str(count)],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass

    return False


def remove_workspace(desktop: int) -> bool:
    """Remove a non-active X11 workspace while preserving desktop order.

    xfwm4 exposes the workspace count but not a native "remove this middle
    workspace" EWMH operation. Shift windows from subsequent workspaces down
    one slot, then remove the final slot. This reproduces Mavericks' logical
    result without requiring a compositor-specific extension.
    """
    try:
        desktop = int(desktop)
    except (TypeError, ValueError):
        return False
    workspaces = get_workspaces()
    count = max(1, int(workspaces.get("count", 1)))
    current = int(workspaces.get("current", 0))
    if count <= 1 or desktop <= 0 or desktop >= count or desktop == current:
        return False

    windows = enumerate_windows()
    # Shift windows from the following Spaces into the removed Space's slot.
    for source in range(desktop + 1, count):
        target = source - 1
        for win in windows:
            try:
                win_desktop = int(win.get("desktop", -1))
            except (TypeError, ValueError):
                continue
            if win_desktop == source:
                if not move_window_to_workspace(win.get("win_id"), target):
                    return False

    return set_workspace_count(count - 1)


def switch_workspace(desktop: int) -> bool:
    """Switch to a workspace by zero-based EWMH desktop index."""
    try:
        desktop = int(desktop)
    except (TypeError, ValueError):
        return False
    if desktop < 0:
        return False

    if _XLIB_AVAILABLE:
        disp = _get_display()
        if disp:
            try:
                return _switch_workspace_xlib(disp, desktop)
            finally:
                try:
                    disp.close()
                except Exception:
                    pass

    try:
        result = subprocess.run(
            ["wmctrl", "-s", str(desktop)],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _move_window_to_workspace_xlib(disp, win_id: Any, desktop: int) -> bool:
    """Move a window to an EWMH desktop using _NET_WM_DESKTOP."""
    parsed_id = _parse_window_id(win_id)
    try:
        desktop = int(desktop)
    except (TypeError, ValueError):
        return False
    if parsed_id is None or desktop < 0 or not disp:
        return False
    try:
        target = disp.create_resource_object("window", parsed_id)
        root = disp.screen().root
        atom = _get_atom(disp, "_NET_WM_DESKTOP")
        from Xlib.protocol import event
        message = event.ClientMessage(
            window=target,
            client_type=atom,
            data=(32, [desktop, 2, 0, 0, 0]),
        )
        root.send_event(
            message,
            event_mask=(X.SubstructureRedirectMask | X.SubstructureNotifyMask),
        )
        disp.flush()
        return True
    except Exception:
        return False


def move_window_to_workspace(win_id: Any, desktop: int) -> bool:
    """Move an X11 window to a zero-based EWMH workspace."""
    try:
        desktop = int(desktop)
    except (TypeError, ValueError):
        return False
    if desktop < 0:
        return False

    if _XLIB_AVAILABLE:
        disp = _get_display()
        if disp:
            try:
                if _move_window_to_workspace_xlib(disp, win_id, desktop):
                    return True
            finally:
                try:
                    disp.close()
                except Exception:
                    pass

    parsed_id = _parse_window_id(win_id)
    if parsed_id is None:
        return False
    try:
        result = subprocess.run(
            ["wmctrl", "-i", "-r", hex(parsed_id), "-t", str(desktop)],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def activate_window(win_id: Any) -> bool:
    """Activate an X11 window, switching workspace and restoring minimized state."""
    if _XLIB_AVAILABLE and _activate_window_xlib(win_id):
        return True

    parsed_id = _parse_window_id(win_id)
    if parsed_id is None:
        return False

    try:
        result = subprocess.run(
            ["wmctrl", "-i", "-a", hex(parsed_id)],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

# --- Module self-test ---
if __name__ == "__main__":
    print("=== enumerate_windows ===")
    for w in enumerate_windows():
        print(f"  {w['win_id']} desk={w['desktop']} class={w['wm_class']} title={w['title'][:50]} geom={w['geometry']} mapped={w['mapped']} state={w['state']}")

    print("\n=== get_active_window ===")
    active = get_active_window()
    print(f"  {active}")

    print("\n=== get_workspaces ===")
    ws = get_workspaces()
    print(f"  count={ws['count']} current={ws['current']} names={ws['names']}")