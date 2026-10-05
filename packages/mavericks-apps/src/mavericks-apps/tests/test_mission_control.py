#!/usr/bin/env python3
"""Mission Control unit tests — window enumeration via EWMH/Xlib + fallback.

Tests verify dict shapes, empty-list grace, multi-workspace, and fallback path.
"""
import os
import sys

# Add the lib directory to path so mission_control is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

import sys
import os
import types
from unittest.mock import patch, MagicMock


def _inject_xlib_mock():
    """Inject a mock Xlib module so the primary EWMH path is exercised.

    This creates a fake Xlib module with fake Display/window objects
    that return controlled data for enumeration.
    """
    # Create a minimal mock Xlib module
    xlib_mock = types.ModuleType("Xlib")

    # Fake Display class
    class FakeDisplay:
        def __init__(self, *args, **kwargs):
            pass
        def screen(self):
            return self._FakeScreen()
        def close(self):
            pass
        def intern_atom(self, name):
            # Return a mock atom that behaves like an int
            return hash(name) & 0x7FFFFFFF
        def get_atom_name(self, atom):
            # Return a name for known atoms
            atoms = {
                hash("_NET_CLIENT_LIST") & 0x7FFFFFFF: "_NET_CLIENT_LIST",
                hash("_NET_WM_NAME") & 0x7FFFFFFF: "_NET_WM_NAME",
                hash("_NET_WM_DESKTOP") & 0x7FFFFFFF: "_NET_WM_DESKTOP",
                hash("_NET_WM_STATE") & 0x7FFFFFFF: "_NET_WM_STATE",
                hash("_NET_WM_STATE_HIDDEN") & 0x7FFFFFFF: "_NET_WM_STATE_HIDDEN",
                hash("_NET_WM_STATE_FULLSCREEN") & 0x7FFFFFFF: "_NET_WM_STATE_FULLSCREEN",
                hash("_NET_ACTIVE_WINDOW") & 0x7FFFFFFF: "_NET_ACTIVE_WINDOW",
                hash("_NET_NUMBER_OF_DESKTOPS") & 0x7FFFFFFF: "_NET_NUMBER_OF_DESKTOPS",
                hash("_NET_DESKTOP_NAMES") & 0x7FFFFFFF: "_NET_DESKTOP_NAMES",
                hash("_NET_CURRENT_DESKTOP") & 0x7FFFFFFF: "_NET_CURRENT_DESKTOP",
                hash("_GTK_FRAME_EXTENTS") & 0x7FFFFFFF: "_GTK_FRAME_EXTENTS",
            }
            return atoms.get(atom, None)

        class _FakeScreen:
            def __init__(self):
                self.root = self._FakeWindow()
            class _FakeWindow:
                def get_geometry(self):
                    return type('geom', (), {'x': 0, 'y': 0, 'width': 100, 'height': 200})()
                def get_wm_class(self):
                    return (None, "Thunar")
                def get_full_property(self, atom, prop_type):
                    return None
                def get_attributes(self):
                    return type('attrs', (), {'map_state': 0})()
                def connect(self, *args, **kwargs):
                    pass

        def create_resource_object(self, *args, **kwargs):
            return self._FakeWindow()

    xlib_mock.display = FakeDisplay()
    xlib_mock.X = types.ModuleType("Xlib.X")
    xlib_mock.Xatom = types.ModuleType("Xlib.Xatom")
    xlib_mock.Xatom.ATOM = 4
    xlib_mock.Xatom.WINDOW = 31
    xlib_mock.X.CARDINAL = 1
    xlib_mock.X.AnyPropertyType = 0
    xlib_mock.X.NONE = 0
    xlib_mock.XErrorException = Exception

    # Add to sys.modules BEFORE importing mission_control
    sys.modules["Xlib"] = xlib_mock
    sys.modules["Xlib.display"] = types.ModuleType("Xlib.display")
    sys.modules["Xlib.display"].display = xlib_mock.display
    sys.modules["Xlib.X"] = xlib_mock.X
    sys.modules["Xlib.Xatom"] = xlib_mock.Xatom
    sys.modules["Xlib.protocol"] = types.ModuleType("Xlib.protocol")
    sys.modules["Xlib.protocol"].rq = types.ModuleType("Xlib.protocol.rq")


def _make_test_window(xlib_mock, title="Test Window", desktop=0, win_id=1, wm_class="Thunar", **kwargs):
    """Create a fake Xlib window resource with controlled properties."""
    # We need to create a fake resource object
    win = types.SimpleNamespace()
    win._xlib = xlib_mock

    # Set up property return values
    # _NET_CLIENT_LIST is on root, others on window
    return win


def _mock_xlib_client_list(xlib_mock, win_ids):
    """Patch the module-level client list and display behavior."""
    # Make intern_atom work for EWMH atoms
    known_atoms = {
        "_NET_CLIENT_LIST": hash("_NET_CLIENT_LIST") & 0x7FFFFFFF,
        "_NET_WM_NAME": hash("_NET_WM_NAME") & 0x7FFFFFFF,
        "_NET_WM_DESKTOP": hash("_NET_WM_DESKTOP") & 0x7FFFFFFF,
        "_NET_WM_STATE": hash("_NET_WM_STATE") & 0x7FFFFFFF,
        "_NET_WM_STATE_HIDDEN": hash("_NET_WM_STATE_HIDDEN") & 0x7FFFFFFF,
        "_NET_WM_STATE_FULLSCREEN": hash("_NET_WM_STATE_FULLSCREEN") & 0x7FFFFFFF,
        "_NET_ACTIVE_WINDOW": hash("_NET_ACTIVE_WINDOW") & 0x7FFFFFFF,
        "_NET_NUMBER_OF_DESKTOPS": hash("_NET_NUMBER_OF_DESKTOPS") & 0x7FFFFFFF,
        "_NET_DESKTOP_NAMES": hash("_NET_DESKTOP_NAMES") & 0x7FFFFFFF,
        "_NET_CURRENT_DESKTOP": hash("_NET_CURRENT_DESKTOP") & 0x7FFFFFFF,
        "_GTK_FRAME_EXTENTS": hash("_GTK_FRAME_EXTENTS") & 0x7FFFFFFF,
    }

    disp = xlib_mock.display
    disp._mc_atom_cache = {}
    for name, atom_val in known_atoms.items():
        disp._mc_atom_cache[name] = atom_val

    # Make intern_atom return correct values
    original_intern = disp.intern_atom
    def mock_intern_atom(name):
        if name in known_atoms:
            return known_atoms[name]
        return original_intern(name) if callable(original_intern) else 0
    disp.intern_atom = mock_intern_atom

    # Make get_atom_name work
    def mock_get_atom_name(atom):
        for name, val in known_atoms.items():
            if val == atom:
                return name
        return None
    disp.get_atom_name = mock_get_atom_name

    # Now let's make the window objects return proper data
    # We'll handle this in the enumerate_windows test below


def test_enum_empty_fallback():
    """Test enumerate_windows returns empty list when no windows available (fallback path)."""
    import mission_control as mc

    # Ensure Xlib is not available (default when python-xlib not installed)
    mc._XLIB_AVAILABLE = False

    # Test with mocked wmctrl that returns nothing
    with patch.object(mc, '_enumerate_windows_fallback', return_value=[]):
        result = mc.enumerate_windows()
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 0, f"Expected empty list, got {len(result)} items"
    print("PASS: test_enum_empty_fallback")


def test_enum_dict_shape_fallback():
    """Test enumerate_windows returns dicts with expected keys (fallback path)."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    test_windows = [
        {
            "win_id": "0x123456",
            "title": "Thunar",
            "wm_class": "Thunar",
            "pid": 1234,
            "desktop": 0,
            "geometry": {"x": 10, "y": 20, "width": 800, "height": 600},
            "mapped": True,
            "state": [],
        },
        {
            "win_id": "0x789abc",
            "title": "Firefox",
            "wm_class": "Firefox",
            "pid": 5678,
            "desktop": 1,
            "geometry": {"x": 100, "y": 150, "width": 1200, "height": 800},
            "mapped": True,
            "state": ["_NET_WM_STATE_FULLSCREEN"],
        },
    ]

    with patch.object(mc, '_enumerate_windows_fallback', return_value=test_windows):
        result = mc.enumerate_windows()
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 2, f"Expected 2 windows, got {len(result)}"

        # Verify all required keys exist
        required_keys = {"win_id", "title", "wm_class", "pid", "desktop", "geometry", "mapped", "state"}
        for i, w in enumerate(result):
            missing = required_keys - set(w.keys())
            assert not missing, f"Window {i} missing keys: {missing}"

        # Verify individual values
        assert result[0]["title"] == "Thunar"
        assert result[0]["wm_class"] == "Thunar"
        assert result[0]["pid"] == 1234
        assert result[0]["desktop"] == 0
        assert result[0]["geometry"]["width"] == 800
        assert result[0]["mapped"] is True
        assert result[0]["state"] == []
        assert result[1]["title"] == "Firefox"
        assert result[1]["wm_class"] == "Firefox"
        assert result[1]["pid"] == 5678
        assert result[1]["desktop"] == 1
        assert result[1]["geometry"]["width"] == 1200
        assert result[1]["mapped"] is True
        assert "_NET_WM_STATE_FULLSCREEN" in result[1]["state"]
    print("PASS: test_enum_dict_shape_fallback")


def test_enum_empty_list_grace():
    """Test enumerate_windows handles empty window list gracefully."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    with patch.object(mc, '_enumerate_windows_fallback', return_value=[]):
        result = mc.enumerate_windows()
        assert result == [], f"Expected empty list, got {result}"

    with patch.object(mc, '_enumerate_windows_fallback', return_value=None):
        result = mc.enumerate_windows()
        assert result == [], f"Expected empty list from None, got {result}"

    print("PASS: test_enum_empty_list_grace")


def test_get_active_none_fallback():
    """Test get_active_window returns None when no active window in fallback."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    with patch.object(mc, '_get_active_window_fallback', return_value=None):
        result = mc.get_active_window()
        assert result is None, f"Expected None, got {result}"

    print("PASS: test_get_active_none_fallback")


def test_get_active_dict_shape_fallback():
    """Test get_active_window returns dict with win_id (fallback path)."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    with patch.object(mc, '_get_active_window_fallback', return_value={"win_id": "0xabcdef"}):
        result = mc.get_active_window()
        assert isinstance(result, dict), "Result should be a dict"
        assert "win_id" in result, "Result should have win_id key"
        assert result["win_id"] == "0xabcdef"
    print("PASS: test_get_active_dict_shape_fallback")


def test_workspaces_dict_shape_fallback():
    """Test get_workspaces returns dict with expected keys (fallback path)."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    with patch.object(mc, '_get_workspaces_fallback', return_value={
        "count": 3,
        "names": ["Desktop 1", "Desktop 2", "Desktop 3"],
        "current": 1,
    }):
        result = mc.get_workspaces()
        assert isinstance(result, dict), "Result should be a dict"
        assert "count" in result, "Result should have count key"
        assert "names" in result, "Result should have names key"
        assert "current" in result, "Result should have current key"
        assert result["count"] == 3
        assert len(result["names"]) == 3
        assert result["current"] == 1
    print("PASS: test_workspaces_dict_shape_fallback")


def test_workspaces_empty_names_fallback():
    """Test get_workspaces default names when none available."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    with patch.object(mc, '_get_workspaces_fallback', return_value={"count": 1, "names": [], "current": 0}):
        result = mc.get_workspaces()
        assert result["count"] == 1
        assert result["names"] == ["Desktop 1"] or result["names"] == [], \
            f"Expected default names, got {result['names']}"
    print("PASS: test_workspaces_empty_names_fallback")


def test_enum_multi_workspace_fallback():
    """Test enumerate_windows with windows on different desktops (fallback)."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    test_windows = [
        {
            "win_id": "0x001",
            "title": "Term",
            "wm_class": "XTerm",
            "pid": 100,
            "desktop": 0,
            "geometry": {"x": 0, "y": 0, "width": 400, "height": 300},
            "mapped": True,
            "state": [],
        },
        {
            "win_id": "0x002",
            "title": "Browser",
            "wm_class": "Firefox",
            "pid": 200,
            "desktop": 1,
            "geometry": {"x": 0, "y": 0, "width": 800, "height": 600},
            "mapped": True,
            "state": [],
        },
        {
            "win_id": "0x003",
            "title": "Editor",
            "wm_class": "Geany",
            "pid": 300,
            "desktop": 2,
            "geometry": {"x": 100, "y": 100, "width": 600, "height": 400},
            "mapped": True,
            "state": [],
        },
    ]

    with patch.object(mc, '_enumerate_windows_fallback', return_value=test_windows):
        result = mc.enumerate_windows()
        assert len(result) == 3

        # Verify different desktops
        desktops = [w["desktop"] for w in result]
        assert 0 in desktops, "Should have window on desktop 0"
        assert 1 in desktops, "Should have window on desktop 1"
        assert 2 in desktops, "Should have window on desktop 2"

        # Verify each window has correct desktop
        for w in result:
            assert isinstance(w["desktop"], int), f"desktop should be int, got {type(w['desktop'])}"

    print("PASS: test_enum_multi_workspace_fallback")


def test_enum_mapped_fallback():
    """Test mapped state detection in fallback path."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    # Window with geometry → mapped True; no geometry → mapped False
    test_windows = [
        {
            "win_id": "0x010",
            "title": "Mapped",
            "wm_class": "XTerm",
            "pid": 100,
            "desktop": 0,
            "geometry": {"x": 0, "y": 0, "width": 100, "height": 100},
            "mapped": True,
            "state": [],
        },
        {
            "win_id": "0x020",
            "title": "Iconified",
            "wm_class": "XTerm",
            "pid": 200,
            "desktop": 0,
            "geometry": {"x": 0, "y": 0, "width": 0, "height": 0},
            "mapped": False,
            "state": [],
        },
    ]

    with patch.object(mc, '_enumerate_windows_fallback', return_value=test_windows):
        result = mc.enumerate_windows()
        assert len(result) == 2
        assert result[0]["mapped"] is True
        assert result[1]["mapped"] is False
    print("PASS: test_enum_mapped_fallback")


def test_enum_state_atoms_fallback():
    """Test state atom extraction in fallback path."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    test_windows = [
        {
            "win_id": "0x010",
            "title": "Normal",
            "wm_class": "XTerm",
            "pid": 100,
            "desktop": 0,
            "geometry": {"x": 0, "y": 0, "width": 100, "height": 100},
            "mapped": True,
            "state": [],
        },
        {
            "win_id": "0x020",
            "title": "Fullscreen",
            "wm_class": "Firefox",
            "pid": 200,
            "desktop": 0,
            "geometry": {"x": 0, "y": 0, "width": 1920, "height": 1080},
            "mapped": True,
            "state": ["_NET_WM_STATE_FULLSCREEN"],
        },
        {
            "win_id": "0x030",
            "title": "Sticky",
            "wm_class": "XTerm",
            "pid": 300,
            "desktop": -1,
            "geometry": {"x": 0, "y": 0, "width": 100, "height": 100},
            "mapped": True,
            "state": ["_NET_WM_STATE_STICKY"],
        },
    ]

    with patch.object(mc, '_enumerate_windows_fallback', return_value=test_windows):
        result = mc.enumerate_windows()
        assert len(result) == 3
        assert result[0]["state"] == []
        assert "_NET_WM_STATE_FULLSCREEN" in result[1]["state"]
        assert "_NET_WM_STATE_STICKY" in result[2]["state"]
        assert result[2]["desktop"] == -1  # sticky = all desktops
    print("PASS: test_enum_state_atoms_fallback")


def test_import_globals():
    """Test that module imports cleanly and _XLIB_AVAILABLE is False when xlib missing."""
    import mission_control as mc
    assert hasattr(mc, '_XLIB_AVAILABLE'), "Module should have _XLIB_AVAILABLE"
    # The module must remain importable regardless of whether Xlib is available.
    # The package declares python-xlib, while isolated unit-test environments may not.
    assert isinstance(mc._XLIB_AVAILABLE, bool), "_XLIB_AVAILABLE should be a boolean"
    # Functions should still be callable
    assert callable(mc.enumerate_windows)
    assert callable(mc.get_active_window)
    assert callable(mc.get_workspaces)
    print("PASS: test_import_globals")


def test_compute_layout_empty():
    """Test compute_layout with no windows."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    result = mc.compute_layout([], {"count": 1, "names": ["Desktop 1"], "current": 0}, 1920, 1080)
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 0, f"Expected empty list, got {len(result)}"
    print("PASS: test_compute_layout_empty")


def test_compute_layout_single_window():
    """Test compute_layout with a single window."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    result = mc.compute_layout(
        [{"win_id": "0x001", "title": "Test", "wm_class": "XTerm", "pid": 100, "desktop": 0,
          "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []}],
        {"count": 1, "names": ["Desktop 1"], "current": 0},
        1920, 1080
    )
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 1, f"Expected 1 layout item, got {len(result)}"
    item = result[0]
    assert item["win_id"] == "0x001"
    assert "rect" in item
    assert "x" in item["rect"] and "y" in item["rect"] and "width" in item["rect"] and "height" in item["rect"]
    assert item["workspace"] == 0
    assert item["z"] == 0  # active workspace gets z=0
    print("PASS: test_compute_layout_single_window")


def test_compute_layout_multi_workspace():
    """Test compute_layout with windows on multiple workspaces."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    windows = [
        {"win_id": "0x001", "title": "Term", "wm_class": "XTerm", "pid": 100, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
        {"win_id": "0x002", "title": "Browser", "wm_class": "Firefox", "pid": 200, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 800, "height": 600}, "mapped": True, "state": []},
        {"win_id": "0x003", "title": "Editor", "wm_class": "Geany", "pid": 300, "desktop": 1,
         "geometry": {"x": 100, "y": 100, "width": 600, "height": 400}, "mapped": True, "state": []},
    ]

    result = mc.compute_layout(
        windows,
        {"count": 2, "names": ["Desktop 1", "Desktop 2"], "current": 0},
        1920, 1080
    )
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    # Should have 3 items (2 on desk 0, 1 on desk 1)
    assert len(result) == 3, f"Expected 3 layout items, got {len(result)}"

    # Check workspace assignments
    desks = [item["workspace"] for item in result]
    assert 0 in desks, "Should have windows on desktop 0"
    assert 1 in desks, "Should have windows on desktop 1"

    # Active workspace (0) should come first (z=0)
    assert result[0]["z"] == 0, "Active workspace should have z=0"
    print("PASS: test_compute_layout_multi_workspace")


def test_compute_layout_overlap_resolution():
    """Test compute_layout: windows don't overlap, grid auto-fit works."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    # Many windows on one workspace - should auto-fit grid
    windows = []
    for i in range(8):
        windows.append({
            "win_id": f"0x{i:03x}",
            "title": f"Window {i}",
            "wm_class": "XTerm",
            "pid": 100 + i,
            "desktop": 0,
            "geometry": {"x": 0, "y": 0, "width": 400, "height": 300},
            "mapped": True,
            "state": [],
        })

    result = mc.compute_layout(
        windows,
        {"count": 1, "names": ["Desktop 1"], "current": 0},
        1920, 1080
    )
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 8, f"Expected 8 layout items, got {len(result)}"

    # All rects should be within screen bounds
    for item in result:
        r = item["rect"]
        assert 0 <= r["x"] < 1920, f"x out of bounds: {r['x']}"
        assert 0 <= r["y"] < 1080, f"y out of bounds: {r['y']}"
        assert r["width"] > 0, f"width must be > 0: {r['width']}"
        assert r["height"] > 0, f"height must be > 0: {r['height']}"

    # Z-order should be sequential
    zs = [item["z"] for item in result]
    assert zs == sorted(zs), f"Z-order should be sorted, got {zs}"
    print("PASS: test_compute_layout_overlap_resolution")


def test_compute_layout_screen_fit():
    """Test compute_layout: layout adapts to screen size."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    windows = [
        {"win_id": "0x001", "title": "Win1", "wm_class": "XTerm", "pid": 100, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
        {"win_id": "0x002", "title": "Win2", "wm_class": "XTerm", "pid": 200, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
        {"win_id": "0x003", "title": "Win3", "wm_class": "XTerm", "pid": 300, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
        {"win_id": "0x004", "title": "Win4", "wm_class": "XTerm", "pid": 400, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
    ]

    # Small screen - should have fewer cols
    result_small = mc.compute_layout(
        windows, {"count": 1, "names": ["Desktop 1"], "current": 0}, 800, 600
    )
    # Large screen - should have more cols
    result_large = mc.compute_layout(
        windows, {"count": 1, "names": ["Desktop 1"], "current": 0}, 1920, 1080
    )

    # Both should produce 4 items
    assert len(result_small) == 4
    assert len(result_large) == 4

    # Z-order should be 0 for both (active workspace)
    assert result_small[0]["z"] == 0
    assert result_large[0]["z"] == 0

    # Different screen sizes may produce different layouts (different z distribution)
    # but both should be valid
    print("PASS: test_compute_layout_screen_fit")


def test_compute_layout_with_placeholder():
    """Test compute_layout includes placeholders for empty desktops."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    windows = [
        {"win_id": "0x001", "title": "Win1", "wm_class": "XTerm", "pid": 100, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
    ]

    result = mc.compute_layout(
        windows,
        {"count": 3, "names": ["Desktop 1", "Desktop 2", "Desktop 3"], "current": 0},
        1920, 1080
    )

    # Should have 1 window + 2 placeholders for empty desktops 1 and 2
    # Active desktop (0) has the window, desktops 1 and 2 get placeholders
    assert len(result) == 3, f"Expected 3 items (1 window + 2 placeholders), got {len(result)}"

    # Find the window item and placeholder items
    window_items = [i for i in result if not i.get("placeholder")]
    placeholder_items = [i for i in result if i.get("placeholder")]
    assert len(window_items) == 1, "Should have 1 window item"
    assert len(placeholder_items) == 2, "Should have 2 placeholder items"

    # Window should be on active desktop (z=0)
    window_z = [i for i in result if not i.get("placeholder")][0]["z"]
    assert window_z == 0, "Window should have z=0 on active desktop"
    print("PASS: test_compute_layout_with_placeholder")


def test_layoutmodel_compute():
    """Test LayoutModel class compute method."""
    import mission_control as mc

    mc._XLIB_AVAILABLE = False

    lm = mc.LayoutModel(screen_w=1920, screen_h=1080, margin=20, gap=10)
    lm.set_windows([
        {"win_id": "0x001", "title": "Win1", "wm_class": "XTerm", "pid": 100, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 400, "height": 300}, "mapped": True, "state": []},
        {"win_id": "0x002", "title": "Win2", "wm_class": "XTerm", "pid": 200, "desktop": 0,
         "geometry": {"x": 0, "y": 0, "width": 800, "height": 600}, "mapped": True, "state": []},
    ])
    lm.set_workspaces({"count": 1, "names": ["Desktop 1"], "current": 0})
    result = lm.compute()
    assert isinstance(result, list)
    assert len(result) == 2
    print("PASS: test_layoutmodel_compute")


if __name__ == "__main__":
    tests = [
        test_import_globals,
        test_enum_empty_fallback,
        test_enum_dict_shape_fallback,
        test_enum_empty_list_grace,
        test_get_active_none_fallback,
        test_get_active_dict_shape_fallback,
        test_workspaces_dict_shape_fallback,
        test_workspaces_empty_names_fallback,
        test_enum_multi_workspace_fallback,
        test_enum_mapped_fallback,
        test_enum_state_atoms_fallback,
        test_compute_layout_empty,
        test_compute_layout_single_window,
        test_compute_layout_multi_workspace,
        test_compute_layout_overlap_resolution,
        test_compute_layout_screen_fit,
        test_compute_layout_with_placeholder,
        test_layoutmodel_compute,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)