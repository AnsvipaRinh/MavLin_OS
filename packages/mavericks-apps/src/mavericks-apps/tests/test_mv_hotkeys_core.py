"""Regression tests for the Mavericks hotkey core registry.

The hotkey core was recently restored after an accidental placeholder overwrite.
These tests protect its importability and the essential action registry.
"""
import importlib.util
import os
import sys


CORE_PATH = "packages/mavericks-apps/src/mavericks-apps/lib/mv_hotkeys_core.py"


def load_core():
    """Load hotkeys core directly from source without installation."""
    if not os.path.exists(CORE_PATH):
        raise FileNotFoundError(f"Missing hotkey core: {CORE_PATH}")
    spec = importlib.util.spec_from_file_location("mv_hotkeys_core", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hotkeys_core_imports():
    """Core must import as one complete Python source file."""
    core = load_core()
    assert core is not None, "Hotkey core failed to load"
    print("PASS: mv_hotkeys_core imports successfully")


def test_hotkeys_core_is_not_placeholder():
    """Core must not regress to the destructive PLACEHOLDER state."""
    with open(CORE_PATH, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    assert source.strip() != "PLACEHOLDER", "Hotkey core regressed to PLACEHOLDER"
    assert len(source) > 5000, "Hotkey core unexpectedly small/incomplete"
    print("PASS: mv_hotkeys_core is complete source, not placeholder")


def test_action_registry_exists():
    """Core must expose an action registry used to render Xfce shortcuts."""
    core = load_core()
    assert hasattr(core, "ACTIONS"), "Missing ACTIONS registry"
    actions = core.ACTIONS
    assert isinstance(actions, (list, tuple, dict)), "ACTIONS has invalid type"
    assert len(actions) >= 50, f"Expected at least 50 actions, found {len(actions)}"
    print(f"PASS: hotkey action registry contains {len(actions)} actions")


def test_essential_mavericks_actions_present():
    """Essential Mavericks keyboard actions must stay represented."""
    core = load_core()
    actions = core.ACTIONS
    action_text = repr(actions)

    required_tokens = [
        "spotlight",
        "launchpad",
        "mission",
        "quicklook",
        "force",
        "empty-trash",
        "airdrop",
    ]
    for token in required_tokens:
        assert token in action_text.lower(), f"Missing essential hotkey action: {token}"
    print("PASS: essential Mavericks actions remain in registry")


def test_xml_rendering_api_exists():
    """Core must retain XML rendering support for generated Xfce bindings."""
    core = load_core()
    candidates = ("render_xml", "export", "apply_all", "verify")
    assert any(hasattr(core, name) for name in candidates), "No hotkey rendering/application API exposed"
    print("PASS: hotkey XML rendering/application API is present")


if __name__ == "__main__":
    test_hotkeys_core_imports()
    test_hotkeys_core_is_not_placeholder()
    test_action_registry_exists()
    test_essential_mavericks_actions_present()
    test_xml_rendering_api_exists()
