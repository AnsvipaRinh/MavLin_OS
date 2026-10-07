"""Regression tests for the primary Mission Control core module."""
import importlib.util
import os


CORE_PATH = "packages/mavericks-apps/src/mavericks-apps/lib/mission_control.py"


def load_core():
    """Load Mission Control core directly from source."""
    if not os.path.exists(CORE_PATH):
        raise FileNotFoundError(f"Missing Mission Control core: {CORE_PATH}")
    spec = importlib.util.spec_from_file_location("mission_control", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_imports():
    """Mission Control core must import successfully."""
    module = load_core()
    assert module is not None
    print("PASS: mission_control core imports successfully")


def test_core_source_is_substantial():
    """Core must not regress to an empty implementation or placeholder."""
    with open(CORE_PATH, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert len(source) > 2000, "Mission Control core source unexpectedly small"
    lowered = source.lower()
    assert "window" in lowered, "Mission Control core lacks window model logic"
    assert "workspace" in lowered or "space" in lowered, (
        "Mission Control core lacks workspace/Space logic"
    )
    print("PASS: mission_control core source is substantial")


def test_core_exposes_model_api():
    """Core must expose public callable/class APIs for the overview model."""
    module = load_core()
    public_api = [
        name for name in dir(module)
        if not name.startswith("_") and callable(getattr(module, name))
    ]
    assert public_api, "Mission Control core exposes no public callable API"

    expected_tokens = ("window", "space", "workspace", "layout", "mission", "overview")
    assert any(any(token in name.lower() for token in expected_tokens) for name in public_api), (
        f"No expected Mission Control API found; exports: {public_api}"
    )
    print(f"PASS: mission_control core API available: {', '.join(public_api[:8])}")


if __name__ == "__main__":
    test_core_imports()
    test_core_source_is_substantial()
    test_core_exposes_model_api()
