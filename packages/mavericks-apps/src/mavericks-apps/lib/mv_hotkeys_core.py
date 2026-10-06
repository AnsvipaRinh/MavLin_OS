#!/usr/bin/env python3
"""mv_hotkeys_core — temporary multi-part loader (emergency restore).

Assembles the full module from _core_part_XX.txt siblings next to this file,
then re-executes as the real module. Parts are removed once the full file
is rewritten by a follow-up commit; until then this keeps the hotkey layer
importable and testable.
"""
from __future__ import print_function
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_parts = []
_i = 0
while True:
    _path = os.path.join(_HERE, "_core_part_%02d.txt" % _i)
    if not os.path.isfile(_path):
        break
    with open(_path, "r", encoding="utf-8") as _f:
        _parts.append(_f.read())
    _i += 1

if not _parts:
    raise ImportError(
        "mv_hotkeys_core: no _core_part_*.txt found next to %s" % _HERE
    )

_CODE = "".join(_parts)
exec(compile(_CODE, __file__ + "+assembled", "exec"), globals())
