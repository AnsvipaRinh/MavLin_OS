#!/usr/bin/env python3
"""Tests for the Spotlight preference pane analysis (F15).

Asserts that the REA decoding and native metadata extraction for the
Spotlight preference pane produced the expected results. The main
Spotlight search UI is NOT covered — it is documented as inaccessible.
"""
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
REA_FILE = REPO / "docs" / "UI_REFERENCE" / "runtime" / "raw" / "rea" / "rea_spotlight_prefpane.json"
OBJC_FILE = REPO / "docs" / "UI_REFERENCE" / "runtime" / "raw" / "native" / "spotlight_prefpane-objc-metadata.json"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


# REA NIB analysis - use coverage facet as authoritative
d = json.load(open(REA_FILE))
nr = d.get("normalized_result", {})
g = nr.get("graph", {})
coverage = g.get("coverage", [])

# Find the objects and connections facets
obj_facet = next((c for c in coverage if c.get("facet", "").startswith("objects:")), None)
conn_facet = next((c for c in coverage if c.get("facet", "").startswith("connections:")), None)
classes_facet = next((c for c in coverage if c.get("facet", "").startswith("classes:")), None)

check(obj_facet is not None, "objects facet missing from coverage")
check(conn_facet is not None, "connections facet missing from coverage")
check(classes_facet is not None, "classes facet missing from coverage")

check(obj_facet.get("examined") == 214, f"objects {obj_facet.get('examined')} != 214")
check(conn_facet.get("examined") == 19, f"connections {conn_facet.get('examined')} != 19")
check(classes_facet.get("examined") == 37, f"classes {classes_facet.get('examined')} != 37")

# Action selectors from graph edges
nodes = g.get("nodes", [])
edges = g.get("edges", [])

action_selectors = set()
for edge in edges:
    if "selector" in edge.get("id", "").lower():
        to_val = edge.get("to", "")
        if "toggleSpotlightMenuHotKey:" in to_val:
            action_selectors.add("toggleSpotlightMenuHotKey:")
        elif "toggleSpotlightWindowHotKey:" in to_val:
            action_selectors.add("toggleSpotlightWindowHotKey:")
        elif "gotoKbdPref:" in to_val:
            action_selectors.add("gotoKbdPref:")
        elif "help:" in to_val:
            action_selectors.add("help:")

expected_selectors = {"toggleSpotlightMenuHotKey:", "toggleSpotlightWindowHotKey:",
                      "gotoKbdPref:", "help:"}
check(action_selectors == expected_selectors,
      f"action selectors mismatch: got {action_selectors}, expected {expected_selectors}")

# Verify all actions target object 2 (SpotlightPref controller)
for edge in edges:
    if "action" in edge.get("id", "").lower() and "destination" in edge.get("id", "").lower():
        to_val = edge.get("to", "")
        check('object:["2"]' in to_val,
              f"action destination not object 2: {edge.get('id')}")

# Native metadata
objc = json.load(open(OBJC_FILE))
check(objc.get("class_count") == 6, f"class_count {objc.get('class_count')} != 6")
expected_classes = {"SpotlightPref", "SpotlightPrefConfigKeyEditor",
                    "SpotlightPrefItemTable", "SpotlightPrefPrivacyController",
                    "SpotlightPrefPrivateItem", "SpotlightItem"}
actual_classes = set(objc.get("classes", {}).keys())
check(actual_classes == expected_classes,
      f"classes mismatch: got {actual_classes}, expected {expected_classes}")

# SpotlightPref must have key NSPreferencePane methods
sp_methods = {m["selector"] for m in objc["classes"]["SpotlightPref"]["methods"]}
required_methods = {"mainViewDidLoad", "didSelect", "revealElementForKey:",
                    "willResignActive", "toggleSpotlightMenuHotKey:",
                    "toggleSpotlightWindowHotKey:", "gotoKbdPref:", "help:",
                    "spotlightItems", "setSpotlightItems:"}
missing = required_methods - sp_methods
check(not missing, f"SpotlightPref missing required methods: {missing}")

# SpotlightPrefConfigKeyEditor must have key editor methods
sk_methods = {m["selector"] for m in objc["classes"]["SpotlightPrefConfigKeyEditor"]["methods"]}
sk_required = {"initConfigKeyEditorWithMaster:", "becomeFirstResponder",
               "resignFirstResponder", "keyDown:", "validateMenuItem:",
               "performKeyEquivalent:", "_disableHotKeyOperationMode",
               "_restoreHotKeyOperationMode"}
sk_missing = sk_required - sk_methods
check(not sk_missing, f"SpotlightPrefConfigKeyEditor missing methods: {sk_missing}")

# SpotlightPrefPrivacyController must have privacy methods
pp_methods = {m["selector"] for m in objc["classes"]["SpotlightPrefPrivacyController"]["methods"]}
pp_required = {"init", "awakeFromNib", "_getPrivateItems", "_reloadExclusions:",
               "addItem:", "deleteItem:", "openPanelFinished:returnCode:",
               "privacyView", "setParent:"}
pp_missing = pp_required - pp_methods
check(not pp_missing, f"SpotlightPrefPrivacyController missing methods: {pp_missing}")

# Verify total method count
total_methods = sum(len(c.get("methods", [])) for c in objc.get("classes", {}).values())
check(total_methods == 114, f"total methods {total_methods} != 114")

# SpotlightItem must have enabled/icon properties
si_methods = {m["selector"] for m in objc["classes"]["SpotlightItem"]["methods"]}
si_required = {"enabled", "setEnabled:", "icon", "setIcon:"}
si_missing = si_required - si_methods
check(not si_missing, f"SpotlightItem missing methods: {si_missing}")

# SpotlightPrefPrivateItem must have path/name/icon properties
sppi_methods = {m["selector"] for m in objc["classes"]["SpotlightPrefPrivateItem"]["methods"]}
sppi_required = {"initWithPath:", "name", "setName:", "path", "setPath:", "icon", "setIcon:",
                 "initWithCoder:", "encodeWithCoder:"}
sppi_missing = sppi_required - sppi_methods
check(not sppi_missing, f"SpotlightPrefPrivateItem missing methods: {sppi_missing}")

# Evidence files exist
check(REA_FILE.exists(), "REA evidence file missing")
check(OBJC_FILE.exists(), "ObjC metadata file missing")

if failures:
    for f in failures:
        print("FAIL:", f)
    raise SystemExit(1)
print("Spotlight preference pane (F15) contract OK")
raise SystemExit(0)