"""Regression tests for the Mavericks-style application menu module."""
import importlib.util
import os


APP_MENU_PATH = "packages/mavericks-apps/src/mavericks-apps/lib/mavericks_appmenu.py"


def load_appmenu():
    """Load application menu module directly from source."""
    if not os.path.exists(APP_MENU_PATH):
        raise FileNotFoundError(f"Missing app menu module: {APP_MENU_PATH}")
    spec = importlib.util.spec_from_file_location("mavericks_appmenu", APP_MENU_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_appmenu_imports():
    """Global menu module must import without packaging/runtime failure."""
    module = load_appmenu()
    assert module is not None
    print("PASS: mavericks_appmenu imports successfully")


def test_appmenu_source_is_substantial():
    """Guard against accidental replacement by an empty stub."""
    with open(APP_MENU_PATH, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert len(source) > 1000, "Application menu source unexpectedly small"
    assert "menu" in source.lower(), "Application menu source lacks menu implementation"
    print("PASS: mavericks_appmenu source is present and substantial")


def test_appmenu_exports_api():
    """Module should expose at least one public menu/application integration API."""
    module = load_appmenu()
    public_names = [name for name in dir(module) if not name.startswith("_")]
    candidates = ("AppMenu", "Menu", "ApplicationMenu", "build_menu", "main")
    assert any(name in public_names for name in candidates), (
        f"Missing expected app menu API; exports: {public_names}"
    )
    print("PASS: mavericks_appmenu exposes menu integration API")


if __name__ == "__main__":
    test_appmenu_imports()
    test_appmenu_source_is_substantial()
    test_appmenu_exports_api()
