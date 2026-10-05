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