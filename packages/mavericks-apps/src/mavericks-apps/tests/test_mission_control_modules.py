"""Regression tests for Mission Control live and animation modules."""
import importlib.util
import os


LIB_DIR = "packages/mavericks-apps/src/mavericks-apps/lib"


def load_module(name):
    """Load one Mission Control library module directly from source."""
    path = os.path.join(LIB_DIR, f"{name}.py")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing Mission Control module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def test_live_module_imports():
    """Live overview module must remain importable."""
    module, _ = load_module("mission_control_live")
    assert module is not None
    print("PASS: mission_control_live imports successfully")


def test_live_module_is_substantial():
    """Live overview source must not become an empty stub."""
    _, path = load_module("mission_control_live")
    with open(path, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert len(source) > 1000, "mission_control_live source unexpectedly small"
    assert "window" in source.lower(), "mission_control_live lacks window handling"
    print("PASS: mission_control_live source is substantial")


def test_animation_module_imports():
    """Animation module must remain importable."""
    module, _ = load_module("mission_control_anim")
    assert module is not None
    print("PASS: mission_control_anim imports successfully")


def test_animation_module_is_substantial():
    """Animation source must not become an empty stub."""
    _, path = load_module("mission_control_anim")
    with open(path, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert len(source) > 500, "mission_control_anim source unexpectedly small"
    assert any(token in source.lower() for token in ("anim", "transition", "frame")), (
        "mission_control_anim lacks animation logic"
    )
    print("PASS: mission_control_anim source is substantial")


def test_modules_expose_public_api():
    """Both modules must provide at least one non-private callable/class API."""
    for name in ("mission_control_live", "mission_control_anim"):
        module, _ = load_module(name)
        public_api = [
            attr for attr in dir(module)
            if not attr.startswith("_") and callable(getattr(module, attr))
        ]
        assert public_api, f"{name} exposes no public callable API"
        print(f"PASS: {name} exposes public API: {', '.join(public_api[:5])}")


if __name__ == "__main__":
    test_live_module_imports()
    test_live_module_is_substantial()
    test_animation_module_imports()
    test_animation_module_is_substantial()
    test_modules_expose_public_api()
