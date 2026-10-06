#!/usr/bin/env python3
"""Regression contracts for the native Finder shell."""

from pathlib import Path


def test_finder_native_mavericks_shell_contract():
    source = Path(__file__).parents[1] / "bin" / "mv-finder-columns"
    text = source.read_text(encoding="utf-8")
    for token in (
        "_build_sidebar",
        "Search",
        "on_back",
        "on_forward",
        "on_up",
        "mavericks-finder-sidebar",
        "mavericks-finder-column",
    ):
        assert token in text
    assert 'hb.set_subtitle("Finder")' in text
    assert 'hb.set_subtitle("Column View")' not in text
