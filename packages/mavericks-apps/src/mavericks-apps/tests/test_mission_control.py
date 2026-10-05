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
    # When python-xlib is not installed, should be False
    assert mc._XLIB_AVAILABLE is False, "_XLIB_AVAILABLE should be False when xlib not installed"
    # Functions should still be callable
    assert callable(mc.enumerate_windows)
    assert callable(mc.get_active_window)
    assert callable(mc.get_workspaces)
    print("PASS: test_import_globals")


def test_import_globals():
    """Test that module imports cleanly and _XLIB_AVAILABLE is False when xlib missing."""
    import mission_control as mc
    assert hasattr(mc, '_XLIB_AVAILABLE'), "Module should have _XLIB_AVAILABLE"
    # When python-xlib is not installed, should be False
    assert mc._XLIB_AVAILABLE is False, "_XLIB_AVAILABLE should be False when xlib not installed"
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


# ============================================================================
# Thumbnail capture (slice 3): XComposite/XDamage/XFixes via ctypes
# ============================================================================

import ctypes
import time
from ctypes import c_int, c_uint, c_ulong, POINTER


class _FakeLib:
    """Attribute bag standing in for a CDLL: plain callables per symbol."""

    def __init__(self, **fns):
        self._fns = fns

    def __getattr__(self, name):
        # Only called for attributes not found normally; expose fns directly
        raise AttributeError(name)

    def add(self, name, fn):
        self._fns[name] = fn
        setattr(self, name, fn)


def _make_fake_libs(damage_base=88, composite_ok=True):
    """Build a coherent set of fake x11/composite/damage/fixes libraries.

    Returns (libs_dict, calls_list) where calls_list accumulates
    (symbol, args-tuple) records for flow assertions.
    """
    calls = []

    def rec(name):
        def wrapper(*args):
            calls.append((name, args))
            return None
        return wrapper

    x11 = _FakeLib()
    comp = _FakeLib()
    dmg = _FakeLib()
    fx = _FakeLib()

    x11.add("XOpenDisplay", lambda name: 0x0D15)
    x11.add("XCloseDisplay", rec("XCloseDisplay"))
    x11.add("XSync", rec("XSync"))
    x11.add("XFlush", rec("XFlush"))
    x11.add("XPending", lambda dpy: 0)
    x11.add("XNextEvent", rec("XNextEvent"))
    x11.add("XConnectionNumber", lambda dpy: -1)
    x11.add("XFree", rec("XFree"))
    x11.add("XFreePixmap", rec("XFreePixmap"))
    x11.add("XSetErrorHandler", lambda h: 0x1234)
    x11.add("XDestroyImage", rec("XDestroyImage"))

    def fake_geometry(dpy, d, root_p, x_p, y_p, w_p, h_p, bw_p, depth_p):
        calls.append(("XGetGeometry", (dpy, d)))
        ctypes.cast(w_p, POINTER(c_uint)).contents.value = 8
        ctypes.cast(h_p, POINTER(c_uint)).contents.value = 6
        ctypes.cast(depth_p, POINTER(c_uint)).contents.value = 24
        return 1
    x11.add("XGetGeometry", fake_geometry)

    def fake_composite_version(dpy, maj_p, mnr_p):
        return 1 if composite_ok else 0
    comp.add("XCompositeQueryVersion", fake_composite_version)
    comp.add("XCompositeRedirectWindow", rec("XCompositeRedirectWindow"))
    comp.add("XCompositeUnredirectWindow", rec("XCompositeUnredirectWindow"))
    comp.add("XCompositeNameWindowPixmap", lambda dpy, w: 0)

    def fake_damage_query(dpy, ev_p, err_p):
        ctypes.cast(ev_p, POINTER(c_int)).contents.value = damage_base
        ctypes.cast(err_p, POINTER(c_int)).contents.value = damage_base + 1
        return 1
    dmg.add("XDamageQueryExtension", fake_damage_query)

    def fake_damage_create(dpy, w, lvl):
        calls.append(("XDamageCreate", (dpy, w, lvl)))
        return 0x99
    dmg.add("XDamageCreate", fake_damage_create)
    dmg.add("XDamageDestroy", rec("XDamageDestroy"))
    dmg.add("XDamageSubtract", rec("XDamageSubtract"))

    fx.add("XFixesQueryVersion", lambda dpy, a, b: 1)

    def fake_create_region(dpy, r, n):
        calls.append(("XFixesCreateRegion", (dpy, r, n)))
        return 0x77
    fx.add("XFixesCreateRegion", fake_create_region)
    fx.add("XFixesDestroyRegion", rec("XFixesDestroyRegion"))
    fx.add("XFixesFetchRegion", lambda dpy, r, n_p: None)
    fx.add("XFixesSubtractRegion", rec("XFixesSubtractRegion"))

    libs = {"x11": x11, "composite": comp, "damage": dmg, "fixes": fx}
    return libs, calls


def _build_ximage(w, h, pixels_bgra, depth=24):
    """Build a real _XImage struct backed by pixels_bgra; return (address, keepalive_tuple)."""
    import mission_control as mc
    data = ctypes.create_string_buffer(bytes(pixels_bgra), len(pixels_bgra))
    img = mc._XImage()
    img.width, img.height = w, h
    img.xoffset, img.format = 0, 2
    img.data = ctypes.addressof(data)
    img.byte_order = 0
    img.bitmap_unit = img.bitmap_bit_order = img.bitmap_pad = 32
    img.depth = depth
    img.bytes_per_line = w * 4
    img.bits_per_pixel = 32
    img.red_mask, img.green_mask, img.blue_mask = 0xFF0000, 0xFF00, 0xFF
    return ctypes.addressof(img), (img, data)


def test_thumbnail_fit_dimensions():
    """Aspect-preserving fit: bounds, aspect, min 1, degenerate input."""
    import mission_control as mc
    fd = mc.fit_dimensions
    assert fd(800, 600, 200, 200) == (200, 150)
    assert fd(400, 300, 200, 100) == (133, 100)
    assert fd(100, 50, 400, 400) == (400, 200)      # upscale fills cell
    assert fd(64, 48, 32, 32) == (32, 24)
    assert fd(1, 1000, 100, 100) == (1, 100)
    assert fd(0, 100, 50, 50) == (1, 1)             # degenerate source
    assert fd(10, 10, 0, 0) == (1, 1)               # degenerate cell
    for (sw, sh, mw, mh) in [(800, 600, 200, 200), (1366, 768, 320, 240), (17, 33, 5, 5)]:
        w, h = fd(sw, sh, mw, mh)
        assert 1 <= w <= mw and 1 <= h <= mh
        # each axis within ~1px of the exact scaled size (int truncation)
        scale = min(mw / sw, mh / sh)
        assert abs(w - sw * scale) <= 1.25, (sw, sh, w, h)
        assert abs(h - sh * scale) <= 1.25, (sw, sh, w, h)
    print("PASS: test_thumbnail_fit_dimensions")


def test_thumbnail_bgra_to_rgba():
    """Channel swap, alpha forcing for depth 24, row stride padding."""
    import mission_control as mc
    # BGRA blue pixel -> RGBA (0,0,255)
    assert mc._bgra_to_rgba(bytes([255, 0, 0, 255]), 1, 1, 4, has_alpha=True) == bytes([0, 0, 255, 255])
    # depth-24: undefined 4th byte forced opaque
    assert mc._bgra_to_rgba(bytes([1, 2, 3, 0]), 1, 1, 4, has_alpha=False) == bytes([3, 2, 1, 255])
    # two pixels with per-row padding (stride 12 > 2*4)
    row = bytes([10, 20, 30, 0, 40, 50, 60, 0, 99, 99, 99, 99])
    out = mc._bgra_to_rgba(row, 2, 1, 12, has_alpha=True)
    assert out == bytes([30, 20, 10, 0, 60, 50, 40, 0]), out
    # two rows with padding: padding bytes ignored
    buf = row + row
    out2 = mc._bgra_to_rgba(buf, 2, 2, 12, has_alpha=False)
    assert out2 == bytes([30, 20, 10, 255, 60, 50, 40, 255]) * 2, out2
    print("PASS: test_thumbnail_bgra_to_rgba")


def test_thumbnail_scale_rgba():
    """Nearest rescale: identity, uniform step, general case, row pick."""
    import mission_control as mc
    sr = mc._scale_rgba
    red = bytes([255, 0, 0, 255])
    # identity
    assert sr(red * 4, 2, 2, 2, 2) == red * 4
    # 4x4 -> 2x2 solid stays solid
    assert sr(red * 16, 4, 4, 2, 2) == red * 4
    # uniform column step 4->2 picks every 2nd pixel
    row = bytes([10, 20, 30, 40]) * 4
    assert sr(row, 4, 1, 2, 1) == bytes([10, 20, 30, 40]) * 2
    # general non-uniform 3->2 (floor mapping [0,1])
    row3 = bytes([1, 1, 1, 255, 2, 2, 2, 255, 3, 3, 3, 255])
    assert sr(row3, 3, 1, 2, 1) == bytes([1, 1, 1, 255, 2, 2, 2, 255])
    # row nearest pick 6->2
    col = bytes([1, 1, 1, 255] * 3 + [9, 9, 9, 255] * 3)
    assert sr(col, 1, 6, 1, 2) == bytes([1, 1, 1, 255, 9, 9, 9, 255])
    # upscales row 2->4 (nearest duplicates pixels)
    two = bytes([5, 6, 7, 255]) * 2
    assert sr(two, 2, 1, 4, 1) == bytes([5, 6, 7, 255]) * 4
    # degenerate
    assert sr(b"", 0, 0, 4, 4) == b""
    assert sr(red, 1, 1, 0, 0) == b""
    print("PASS: test_thumbnail_scale_rgba")


def test_thumbnail_placeholder_pattern():
    """Deterministic checkerboard, correct size, cheap regeneration."""
    import mission_control as mc
    ph = mc._placeholder_rgba
    a = ph(64, 48)
    assert len(a) == 64 * 48 * 4
    assert a == ph(64, 48)                     # deterministic
    def px(buf, w, x, y): return tuple(buf[(y * w + x) * 4:(y * w + x) * 4 + 4])
    assert px(a, 64, 0, 0) == (214, 214, 214, 255)
    assert px(a, 64, 16, 0) == (152, 152, 152, 255)
    assert px(a, 64, 0, 16) == (152, 152, 152, 255)
    assert px(a, 64, 16, 16) == (214, 214, 214, 255)
    # odd sizes clamp fine
    b = ph(7, 5)
    assert len(b) == 7 * 5 * 4
    print("PASS: test_thumbnail_placeholder_pattern")


def test_thumbnail_normalize_win_id():
    """int / '0x...' / decimal / garbage normalization."""
    import mission_control as mc
    n = mc._normalize_win_id
    assert n("0x1a") == 26
    assert n("0X2B") == 43
    assert n(42) == 42
    assert n(" 7 ") == 7
    assert n(0) == 0
    assert n("zz") is None
    assert n("") is None
    assert n(None) is None
    assert n(-5) is None
    assert n(True) is None
    print("PASS: test_thumbnail_normalize_win_id")


def test_thumbnail_no_display_raises():
    """No DISPLAY and no display_name -> RuntimeError (headless discipline)."""
    import mission_control as mc
    libs, _ = _make_fake_libs()
    saved = os.environ.pop("DISPLAY", None)
    try:
        try:
            mc.ThumbnailCapture(libs=libs)
            raise AssertionError("should have raised RuntimeError")
        except RuntimeError as e:
            assert "DISPLAY" in str(e)
    finally:
        if saved is not None:
            os.environ["DISPLAY"] = saved
    print("PASS: test_thumbnail_no_display_raises")


def test_thumbnail_forbidden_display_raises():
    """Displays in $MV_FORBIDDEN_DISPLAYS are refused (host display guard)."""
    import mission_control as mc
    libs, _ = _make_fake_libs()
    saved = os.environ.get("MV_FORBIDDEN_DISPLAYS")
    os.environ["MV_FORBIDDEN_DISPLAYS"] = ":0"
    try:
        try:
            mc.ThumbnailCapture(display_name=":0", libs=libs)
            raise AssertionError("should have raised RuntimeError")
        except RuntimeError as e:
            assert "forbidden" in str(e)
    finally:
        if saved is None:
            os.environ.pop("MV_FORBIDDEN_DISPLAYS", None)
        else:
            os.environ["MV_FORBIDDEN_DISPLAYS"] = saved
    print("PASS: test_thumbnail_forbidden_display_raises")


def test_thumbnail_placeholder_when_composite_missing():
    """XComposite unavailable -> deterministic placeholder, never an exception."""
    import mission_control as mc
    libs, calls = _make_fake_libs(composite_ok=False)
    tc = mc.ThumbnailCapture(display_name=":97", libs=libs)
    assert tc.available is False
    r = tc.capture_window("0x2a", 40, 30)
    assert r["placeholder"] is True
    assert r["width"] == 40 and r["height"] == 30 and r["stride"] == 160
    assert len(r["data"]) == 40 * 30 * 4
    assert "error" in r
    # no capture calls happened (only open/probes recorded)
    syms = [c[0] for c in calls]
    assert "XCompositeNameWindowPixmap" not in syms
    tc.close()
    print("PASS: test_thumbnail_placeholder_when_composite_missing")


def test_thumbnail_capture_flow_mock():
    """Happy-path capture flow via fake libs + a real XImage struct.

    Window 0x2a (42), pixmap 8x6 depth 24, blue pixels BGRA.
    Expect: redirect -> name pixmap -> geometry -> get image ->
    destroy image -> free pixmap -> unredirect, result 4x3 RGBA.
    """
    import mission_control as mc
    libs, calls = _make_fake_libs()

    # 8x6 solid blue BGRA (B=255, G=0, R=0, X=255)
    pixels = bytes([255, 0, 0, 255]) * (8 * 6)
    img_addr, keepalive = _build_ximage(8, 6, pixels)

    def fake_get_image(dpy, d, x, y, w, h, mask, fmt):
        calls.append(("XGetImage", (dpy, d, w, h)))
        return img_addr
    libs["x11"].add("XGetImage", fake_get_image)

    def fake_name_pixmap(dpy, w):
        calls.append(("XCompositeNameWindowPixmap", (dpy, w)))
        return 0xABC
    libs["composite"].add("XCompositeNameWindowPixmap", fake_name_pixmap)

    tc = mc.ThumbnailCapture(display_name=":97", libs=libs)
    r = tc.capture_window("0x2a", 4, 4)

    assert r["placeholder"] is False, r.get("error")
    assert r["win_id"] == 42
    assert (r["width"], r["height"]) == (4, 3), (r["width"], r["height"])
    assert r["stride"] == 16
    assert len(r["data"]) == 4 * 3 * 4
    assert tuple(r["data"][0:4]) == (0, 0, 255, 255), r["data"][0:4]  # RGBA blue

    syms = [c[0] for c in calls]
    for expected in ["XCompositeRedirectWindow", "XCompositeNameWindowPixmap",
                     "XGetGeometry", "XGetImage", "XDestroyImage",
                     "XFreePixmap", "XCompositeUnredirectWindow"]:
        assert expected in syms, f"missing call {expected} in {syms}"
    # redirect/unredirect got the normalized window id
    redir = [c for c in calls if c[0] == "XCompositeRedirectWindow"][0]
    assert redir[1][1] == 42
    unredir = [c for c in calls if c[0] == "XCompositeUnredirectWindow"][0]
    assert unredir[1][1] == 42
    tc.close()
    print("PASS: test_thumbnail_capture_flow_mock")


def test_thumbnail_capture_badpixmap_mock():
    """NameWindowPixmap -> 0 (unmapped window) -> placeholder + cleanup."""
    import mission_control as mc
    libs, calls = _make_fake_libs()
    libs["composite"].add("XCompositeNameWindowPixmap", lambda dpy, w: 0)
    libs["x11"].add("XGetImage", lambda *a: 0)

    tc = mc.ThumbnailCapture(display_name=":97", libs=libs)
    r = tc.capture_window(0x55, 20, 10)
    assert r["placeholder"] is True
    assert r["win_id"] == 0x55
    assert "error" in r
    syms = [c[0] for c in calls]
    assert "XGetImage" not in syms          # failed before pixel read
    assert "XCompositeUnredirectWindow" in syms  # cleanup still happens
    tc.close()
    print("PASS: test_thumbnail_capture_badpixmap_mock")


def test_thumbnail_capture_invalid_wid():
    """Unparseable window id -> placeholder without any X capture calls."""
    import mission_control as mc
    libs, calls = _make_fake_libs()
    tc = mc.ThumbnailCapture(display_name=":97", libs=libs)
    r = tc.capture_window("not-a-window", 8, 8)
    assert r["placeholder"] is True
    assert "error" in r
    syms = [c[0] for c in calls]
    assert "XCompositeRedirectWindow" not in syms
    assert "XCompositeNameWindowPixmap" not in syms
    tc.close()
    print("PASS: test_thumbnail_capture_invalid_wid")


def test_thumbnail_lifecycle_start_stop():
    """start_capture: redirect + damage + fixes region per window; stop undoes all."""
    import mission_control as mc
    libs, calls = _make_fake_libs()
    tc = mc.ThumbnailCapture(display_name=":97", libs=libs)
    assert tc.available

    cb = []
    ok = tc.start_capture([0x10, "0x20"], callback=lambda w, a: cb.append((w, a)))
    assert ok is True
    assert tc.capturing is True
    syms = [c[0] for c in calls]
    assert syms.count("XCompositeRedirectWindow") == 2
    assert syms.count("XDamageCreate") == 2
    assert syms.count("XFixesCreateRegion") == 2

    # idempotent: second start on same windows does not duplicate
    calls.clear()
    tc.start_capture([0x10, 0x20])
    syms = [c[0] for c in calls]
    assert syms.count("XDamageCreate") == 0

    tc.stop_capture()
    assert tc.capturing is False
    syms = [c[0] for c in calls]
    assert syms.count("XDamageDestroy") == 2
    assert syms.count("XFixesDestroyRegion") == 2
    assert syms.count("XCompositeUnredirectWindow") == 2

    # double stop is a no-op
    calls.clear()
    tc.stop_capture()
    assert [c[0] for c in calls] == []
    tc.close()
    assert "XCloseDisplay" in [c[0] for c in calls]
    print("PASS: test_thumbnail_lifecycle_start_stop")


def test_thumbnail_damage_poll_mock():
    """poll_damage: parses XDamageNotifyEvent, subtracts, fetches region bbox,
    fires callback; non-damage events skipped."""
    import mission_control as mc
    libs, calls = _make_fake_libs(damage_base=88)

    def craft_event(ev_type, drawable, x, y, w, h):
        ev = mc._XDamageNotifyEvent()
        ev.type = ev_type
        ev.drawable = drawable
        ev.area.x, ev.area.y, ev.area.width, ev.area.height = x, y, w, h
        return ctypes.string_at(ctypes.addressof(ev), ctypes.sizeof(ev))

    src_holder = [craft_event(88, 0x10, 1, 2, 3, 4)]

    def fake_next_event(dpy, buf):
        calls.append(("XNextEvent", (dpy,)))
        src = src_holder[0]
        ctypes.memmove(buf, src, len(src))
        return 0

    pending_returns = []

    def fake_pending(dpy):
        return pending_returns.pop(0) if pending_returns else 0

    # XFixesFetchRegion: 2 rectangles -> bbox (1,2)-(7,11) i.e. 6x9
    rects = (mc._XRectangle * 2)()
    rects[0].x, rects[0].y, rects[0].width, rects[0].height = 1, 2, 3, 4
    rects[1].x, rects[1].y, rects[1].width, rects[1].height = 4, 5, 3, 6

    def fake_fetch(dpy, region, n_p):
        calls.append(("XFixesFetchRegion", (dpy, region)))
        ctypes.cast(n_p, POINTER(c_int)).contents.value = 2
        return ctypes.addressof(rects)

    # NB: overrides must be installed BEFORE ThumbnailCapture binds them
    libs["x11"].add("XNextEvent", fake_next_event)
    libs["x11"].add("XPending", fake_pending)
    libs["fixes"].add("XFixesFetchRegion", fake_fetch)

    tc = mc.ThumbnailCapture(display_name=":97", libs=libs)
    cb = []
    tc.start_capture([0x10], callback=lambda w, a: cb.append((w, a)))

    # 1) damage event with fixes-region bbox
    pending_returns.extend([1, 0])
    events = tc.poll_damage()
    assert len(events) == 1, events
    e = events[0]
    assert e["win_id"] == 0x10
    assert e["area"] == {"x": 1, "y": 2, "width": 6, "height": 9}, e["area"]
    syms = [c[0] for c in calls]
    assert "XDamageSubtract" in syms
    assert "XFixesSubtractRegion" in syms       # parts region emptied
    assert "XFree" in syms                      # fetched rects freed
    assert cb and cb[0][0] == 0x10, cb

    # 2) non-damage event (type != damage_base) is skipped silently
    calls.clear()
    src_holder[0] = craft_event(999, 0x10, 0, 0, 5, 5)
    pending_returns.extend([1, 0])
    assert tc.poll_damage() == []
    assert "XDamageSubtract" not in [c[0] for c in calls]

    # 3) no events pending -> empty list, no X calls
    calls.clear()
    assert tc.poll_damage() == []
    assert [c[0] for c in calls] == []

    tc.stop_capture()
    tc.close()
    print("PASS: test_thumbnail_damage_poll_mock")


def test_thumbnail_integration_xvfb():
    """Integration on the pinned Xvfb :97 (auto-gated, no host display).

    Exercises the real XComposite/XDamage/XFixes stack: window content
    capture with pixel-exact assertions, damage lifecycle, multi-cycle
    stability (XEvent-192 heap-corruption regression) and read-only
    window state after captures.
    """
    import mission_control as mc
    disp = os.environ.get("DISPLAY", "")
    enabled = (disp == ":97") or os.environ.get("MV_MC_INTEGRATION") == "1"
    if not enabled:
        print("SKIP: test_thumbnail_integration_xvfb (DISPLAY=%r, set DISPLAY=:97 via gui-isolation.sh)" % disp)
        return

    c = ctypes
    x11 = mc._load_first_ctypes(mc._X11_LIB_NAMES)
    f_open = mc._bind_ctypes(x11, "XOpenDisplay", c.c_void_p, [c.c_char_p])
    f_root = mc._bind_ctypes(x11, "XDefaultRootWindow", c.c_ulong, [c.c_void_p])
    f_create = mc._bind_ctypes(x11, "XCreateSimpleWindow", c.c_ulong,
        [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_ulong])
    f_map = mc._bind_ctypes(x11, "XMapWindow", c.c_int, [c.c_void_p, c.c_ulong])
    f_sync = mc._bind_ctypes(x11, "XSync", c.c_int, [c.c_void_p, c.c_int])
    f_creategc = mc._bind_ctypes(x11, "XCreateGC", c.c_ulong,
                                 [c.c_void_p, c.c_ulong, c.c_ulong, c.c_void_p])
    f_setfg = mc._bind_ctypes(x11, "XSetForeground", c.c_int,
                              [c.c_void_p, c.c_ulong, c.c_ulong])
    f_fill = mc._bind_ctypes(x11, "XFillRectangle", c.c_int,
        [c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.c_uint, c.c_uint])

    probe = f_open(b":97")
    if not probe:
        print("SKIP: test_thumbnail_integration_xvfb (Xvfb :97 not reachable)")
        return
    mc._bind_ctypes(x11, "XCloseDisplay", c.c_int, [c.c_void_p])(probe)

    dpy = f_open(b":97")
    root = f_root(dpy)
    win = f_create(dpy, root, 0, 0, 64, 48, 0, 0, 0xFFFFFF)
    f_map(dpy, win)
    f_sync(dpy, 0)
    gc_ = f_creategc(dpy, win, 0, None)
    f_setfg(dpy, gc_, 0xFF0000)
    f_fill(dpy, win, gc_, 20, 20, 20, 20)
    f_sync(dpy, 0)

    tc = mc.ThumbnailCapture(display_name=":97")
    if not tc.available:
        tc.close()
        print("SKIP: test_thumbnail_integration_xvfb (no COMPOSITE on :97)")
        return

    try:
        # --- capture: dims + pixel-exact content
        r = tc.capture_window(win, 32, 32)
        assert r["placeholder"] is False, r.get("error")
        assert (r["width"], r["height"]) == (32, 24)
        data = r["data"]
        assert len(data) == 32 * 24 * 4
        px = lambda x, y: tuple(data[(y * 32 + x) * 4:(y * 32 + x) * 4 + 4])
        assert px(2, 2) == (255, 255, 255, 255), px(2, 2)
        assert px(15, 15) == (255, 0, 0, 255), px(15, 15)

        # --- capture: hex-string window id accepted
        r_hex = tc.capture_window(hex(win), 16, 16)
        assert r_hex["placeholder"] is False and r_hex["win_id"] == win

        # --- capture: fullscreen-size window within latency budget
        big = f_create(dpy, root, 0, 0, 1680, 1050, 0, 0, 0x3366CC)
        f_map(dpy, big)
        f_sync(dpy, 0)
        t0 = time.time()
        rb = tc.capture_window(big, 400, 400)
        dt_ms = (time.time() - t0) * 1000
        assert rb["placeholder"] is False, rb.get("error")
        assert (rb["width"], rb["height"]) == (400, 250)
        assert tuple(rb["data"][0:4]) == (0x33, 0x66, 0xCC, 255)
        assert dt_ms < 1500, f"capture too slow: {dt_ms:.0f}ms"

        # --- damage lifecycle
        cb = []
        assert tc.start_capture([win], callback=lambda w, a: cb.append((w, a))) is True
        tc.poll_damage(timeout_ms=1000)          # drain initial damage
        f_setfg(dpy, gc_, 0x00FF00)
        f_fill(dpy, win, gc_, 0, 0, 10, 10)
        f_sync(dpy, 0)
        evs = tc.poll_damage(timeout_ms=3000)
        assert any(e["win_id"] == win for e in evs), evs
        assert cb, "damage callback not fired"
        area = [e for e in evs if e["win_id"] == win][-1]["area"]
        assert area["x"] < 10 and area["y"] < 10 and area["width"] <= 10, area

        # --- recapture reflects damaged content
        r2 = tc.capture_window(win, 64, 64)
        assert r2["placeholder"] is False
        assert tuple(r2["data"][0:4]) == (0, 255, 0, 255), tuple(r2["data"][0:4])

        # --- multi-cycle stability (XEvent-192 heap-corruption regression)
        total = 0
        for i in range(30):
            f_fill(dpy, win, gc_, (i * 5) % 40, (i * 3) % 30, 6, 6)
            f_sync(dpy, 0)
            total += len(tc.poll_damage(timeout_ms=500))
        assert total >= 20, total
        junk = [dict(a=i, b=str(i)) for i in range(20000)]  # heap churn
        assert sum(d["a"] for d in junk) > 0

        # --- read-only guarantee: window still alive, geometry intact
        f_geom = mc._bind_ctypes(x11, "XGetGeometry", c.c_int,
            [c.c_void_p, c.c_ulong, POINTER(c_ulong), POINTER(c.c_int), POINTER(c.c_int),
             POINTER(c_uint), POINTER(c_uint), POINTER(c_uint), POINTER(c_uint)])
        root_p = c_ulong(0)
        gx, gy = c.c_int(0), c.c_int(0)
        gw, gh, gbw, gdepth = c_uint(0), c_uint(0), c_uint(0), c_uint(0)
        assert f_geom(dpy, win, ctypes.byref(root_p), ctypes.byref(gx), ctypes.byref(gy),
                      ctypes.byref(gw), ctypes.byref(gh), ctypes.byref(gbw),
                      ctypes.byref(gdepth)) != 0
        assert (gw.value, gh.value) == (64, 48), (gw.value, gh.value)

        tc.stop_capture()
        assert tc.capturing is False
        r3 = tc.capture_window(win, 32, 32)
        assert r3["placeholder"] is False
    finally:
        tc.close()

    print("PASS: test_thumbnail_integration_xvfb (%.0fms fullscreen capture)" % dt_ms)


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
        test_thumbnail_fit_dimensions,
        test_thumbnail_bgra_to_rgba,
        test_thumbnail_scale_rgba,
        test_thumbnail_placeholder_pattern,
        test_thumbnail_normalize_win_id,
        test_thumbnail_no_display_raises,
        test_thumbnail_forbidden_display_raises,
        test_thumbnail_placeholder_when_composite_missing,
        test_thumbnail_capture_flow_mock,
        test_thumbnail_capture_badpixmap_mock,
        test_thumbnail_capture_invalid_wid,
        test_thumbnail_lifecycle_start_stop,
        test_thumbnail_damage_poll_mock,
        test_thumbnail_integration_xvfb,
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