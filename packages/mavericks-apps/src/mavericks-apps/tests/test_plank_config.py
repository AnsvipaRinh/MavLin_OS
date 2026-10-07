"""Regression tests for Mavericks Plank dock configuration."""
import importlib.util
import os


PLANK_CONFIG_PATH = "packages/mavericks-apps/src/mavericks-apps/lib/plank_config.py"


def load_plank_config():
    """Load Plank configuration module directly from source."""
    if not os.path.exists(PLANK_CONFIG_PATH):
        raise FileNotFoundError(f"Missing Plank config module: {PLANK_CONFIG_PATH}")
    spec = importlib.util.spec_from_file_location("plank_config", PLANK_CONFIG_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plank_config_imports():
    """Dock configuration module must import successfully."""
    module = load_plank_config()
    assert module is not None
    print("PASS: plank_config imports successfully")


def test_plank_config_source_is_substantial():
    """Guard against accidental empty/stub replacement of Dock logic."""
    with open(PLANK_CONFIG_PATH, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert len(source) > 500, "Plank config source unexpectedly small"
    assert "plank" in source.lower(), "Plank config source lacks dock references"
    print("PASS: plank_config source is present and substantial")


def test_plank_config_exports_api():
    """Module must expose configuration or application entry API."""
    module = load_plank_config()
    public_names = [name for name in dir(module) if not name.startswith("_")]
    candidates = ("configure", "apply", "main", "PlankConfig", "DockConfig")
    assert any(name in public_names for name in candidates), (
        f"Missing expected Plank configuration API; exports: {public_names}"
    )
    print("PASS: plank_config exposes Dock configuration API")


if __name__ == "__main__":
    test_plank_config_imports()
    test_plank_config_source_is_substantial()
    test_plank_config_exports_api()
