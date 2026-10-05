"""Regression tests for the GTK Launchpad editor drag-reorder contract."""
import ast
from pathlib import Path

EDITOR = Path(__file__).parents[1] / "bin" / "mv_launchpad_edit.py"


def _load_reorder_function():
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "reorder_apps":
            namespace = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(EDITOR), "exec"), namespace)
            return namespace["reorder_apps"]
    raise AssertionError("reorder_apps helper is missing")


def test_drag_reorder_moves_item_before_destination():
    reorder_apps = _load_reorder_function()
    apps = ["A", "B", "C", "D"]
    assert reorder_apps(apps, 0, 2) == ["B", "A", "C", "D"]
    assert reorder_apps(apps, 3, 1) == ["A", "D", "B", "C"]


def test_drag_reorder_noop_and_invalid_indices_are_safe():
    reorder_apps = _load_reorder_function()
    apps = ["A", "B", "C"]
    assert reorder_apps(apps, 1, 1) == apps
    assert reorder_apps(apps, -1, 1) == apps
    assert reorder_apps(apps, 0, 99) == apps


def test_drag_handler_updates_authoritative_app_list():
    source = EDITOR.read_text(encoding="utf-8")
    assert "self.app_list = self.reorder_apps(" in source
    assert "self.populate_list()" in source
    assert "self.list_store.remove(source_iter)" not in source


if __name__ == "__main__":
    test_drag_reorder_moves_item_before_destination()
    test_drag_reorder_noop_and_invalid_indices_are_safe()
    test_drag_handler_updates_authoritative_app_list()
    print("PASS: Launchpad editor drag reorder contract")
