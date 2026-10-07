"""Regression tests for Mission Control preview rendering module."""
import importlib.util
import os


PREVIEWS_PATH = "packages/mavericks-apps/src/mavericks-apps/lib/mission_control_previews.py"


def load_previews():
    """Load preview renderer module directly from source."""
    if not os.path.exists(PREVIEWS_PATH):
        raise FileNotFoundError(f"Missing preview renderer: {PREVIEWS_PATH}")
    spec = importlib.util.spec_from_file_location("mission_control_previews", PREVIEWS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_previews_module_imports():
    """Preview renderer must import successfully."""
    module = load_previews()
    assert module is not None
    print("PASS: mission_control_previews imports successfully")


def test_previews_module_is_substantial():
    """Preview renderer must not regress to a stub."""
    with open(PREVIEWS_PATH, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert len(source) > 1000, "mission_control_previews source unexpectedly small"
    lowered = source.lower()
    assert "preview" in lowered or "thumbnail" in lowered, (
        "mission_control_previews lacks preview/thumbnail logic"
    )
    print("PASS: mission_control_previews source is substantial")


def test_previews_module_exposes_api():
    """Preview renderer should expose a callable rendering-related API."""
    module = load_previews()
    public_callables = [
        name for name in dir(module)
        if not name.startswith("_") and callable(getattr(module, name))
    ]
    assert public_callables, "mission_control_previews exposes no public callable API"
    expected_tokens = ("preview", "thumbnail", "render", "capture")
    assert any(any(token in name.lower() for token in expected_tokens) for name in public_callables), (
        f"No preview renderer callable found; exports: {public_callables}"
    )
    print(f"PASS: mission_control_previews API available: {', '.join(public_callables[:5])}")


if __name__ == "__main__":
    test_previews_module_imports()
    test_previews_module_is_substantial()
    test_previews_module_exposes_api()
