#!/usr/bin/env python3
"""Packaging regression test for the Calendar EDS helper."""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..")
MAKEFILE = os.path.join(SRC, "Makefile")


def test_calendar_eds_helper_is_installed():
    with open(MAKEFILE, "r", encoding="utf-8") as fh:
        text = fh.read()

    assert re.search(
        r"install -Dm755 bin/mv_calendar_eds\.py "
        r'"\$\(DESTDIR\)\$\(PREFIX\)/bin/mv_calendar_eds\.py"',
        text,
    ), "Makefile does not install mv_calendar_eds.py next to mv-calendar"


if __name__ == "__main__":
    test_calendar_eds_helper_is_installed()
    print("PASS: Calendar EDS helper is installed")
