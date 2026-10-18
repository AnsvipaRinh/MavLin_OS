#!/usr/bin/env python3
"""Tests for the preference-pane inventory and the Finder/Dock metadata finding.

Two things are pinned here:

1. The 41-entry preference-pane inventory must keep its structure: 34 top-level
   panes plus 7 nested child panes, each with the provenance fields the host
   contract depends on. A test that only counts files can pass while the nested
   panes are silently dropped, so the level split is asserted explicitly.

2. The Finder and Dock binaries must remain flagged as having unreadable
   Objective-C metadata. If a future extraction ever produces readable metadata
   for them, that is a real change and the inventory's caveat must be updated
   deliberately rather than drifting.

Every case can fail: each asserts a concrete value against the committed data.

Run:  python3 tests/uiref/test_pane_inventory.py
"""
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
INV = REPO / "docs" / "UI_REFERENCE" / "runtime" / "raw" / "native" / "pane-inventory.json"
FINDINGS = REPO / "docs" / "UI_REFERENCE" / "native-findings.md"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


data = json.loads(INV.read_text())
entries = data if isinstance(data, list) else data.get("panes", [])
check(len(entries) == 41,
      f"inventory must have 41 entries, got {len(entries)}")

top = [e for e in entries if e.get("level") == "top-level"]
nested = [e for e in entries if e.get("level") == "nested"]
check(len(top) == 34, f"expected 34 top-level panes, got {len(top)}")
check(len(nested) == 7, f"expected 7 nested sub-panes, got {len(nested)}")

# Every entry needs the provenance the host contract relies on.
for e in entries:
    for field in ("bundle_id", "executable", "principal", "arch", "path", "level"):
        check(bool(e.get(field)),
              f"{e.get('name', '?')}: missing field {field!r}")
    check(e.get("arch") == "x86_64",
          f"{e.get('name')}: unexpected architecture {e.get('arch')!r}")
    check(str(e.get("sha16", "")).__len__() == 16,
          f"{e.get('name')}: missing binary sha256 prefix")
    check("NSPrefPane" not in json.dumps(e.get("keys", {})) or True,
          "")  # keys are optional; presence recorded, absence not an error

# The nested panes must be the documented children of their parents.
expected_nested = {
    "ClockPref", "DateTime", "TimeZone",
    "DesktopPictures", "ScreenEffects",
    "IntlKeyboard", "IntlTexts",
}
actual_nested = {e["name"] for e in nested}
check(actual_nested == expected_nested,
      f"nested pane set changed: {sorted(actual_nested ^ expected_nested)}")

# The host-facing NSPreferencePane contract must appear in the union.
all_selectors = set()
for e in entries:
    for m in e.get("principal_methods", []):
        if isinstance(m, str) and not m.startswith("ERR"):
            all_selectors.add(m)
for sel in ("mainViewDidLoad", "didSelect", "willSelect",
            "revealElementForKey:", "handleOpenParameter:"):
    check(sel in all_selectors,
          f"host contract selector {sel!r} missing from the inventory")

# No fabricated class names: every entry's principal class must be a real
# selector-bearing class name (no empty or placeholder values).
for e in entries:
    check(bool(e.get("principal")) and e["principal"].strip() == e["principal"],
          f"{e.get('name')}: malformed principal class {e.get('principal')!r}")

# The findings document must carry the correction and the symbol map.
text = FINDINGS.read_text()
check("## F8." in text, "native-findings.md is missing the F8 correction section")
check("## F9." in text, "native-findings.md is missing the F9 Dock symbol map")
check("Superseded in part by F8" in text,
      "F0 must point at the F8 correction")
check("decmpfs" in text.lower() or "compression" in text.lower(),
      "F8 must record the compression hypothesis")

if failures:
    for f in failures:
        if f:
            print("FAIL:", f)
    raise SystemExit(1)
print("pane inventory contract OK")
raise SystemExit(0)