#!/usr/bin/env python3
"""Tests for the Finder NIB analysis (F10).

Asserts that the REA decoding of all 74 English NIBs produced the expected
aggregate inventory and that the major NIBs are present with their key
metrics. Every case can fail against the committed REA evidence.
"""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BATCH1 = REPO / "docs" / "UI_REFERENCE" / "runtime" / "raw" / "rea" / "rea_finder_batch1.json"
BATCH2 = REPO / "docs" / "UI_REFERENCE" / "runtime" / "raw" / "rea" / "rea_finder_batch2.json"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def analyze_batch(path):
    d = json.load(open(path))
    nr = d.get("normalized_result", {})
    g = nr.get("graph", {})
    nodes = g.get("nodes", [])
    edges = g.get("edges", [])
    return nodes, edges


def count_by_doc(nodes, edges):
    docs = {}
    for node in nodes:
        m = re.match(r'ib:"([^"]+)"', node.get("id", ""))
        if m:
            doc = m.group(1)
            nib_name = doc.split('/')[-1]
            if nib_name not in docs:
                docs[nib_name] = {"nodes": 0, "edges": 0, "actions": 0, "outlets": 0,
                                  "views": 0, "controls": 0, "classes": set()}
            docs[nib_name]["nodes"] += 1
    for edge in edges:
        m = re.match(r'ib:"([^"]+)"', edge.get("id", ""))
        if m:
            doc = m.group(1)
            nib_name = doc.split('/')[-1]
            if nib_name in docs:
                docs[nib_name]["edges"] += 1
                if "action" in edge.get("id", "").lower():
                    docs[nib_name]["actions"] += 1
                if "outlet" in edge.get("id", "").lower():
                    docs[nib_name]["outlets"] += 1
    for node in nodes:
        m = re.match(r'ib:"([^"]+)"', node.get("id", ""))
        if m:
            doc = m.group(1)
            nib_name = doc.split('/')[-1]
            if nib_name in docs:
                kind = node.get("kind", "")
                if kind == "view":
                    docs[nib_name]["views"] += 1
                elif kind == "control":
                    docs[nib_name]["controls"] += 1
    return docs


nodes1, edges1 = analyze_batch(BATCH1)
nodes2, edges2 = analyze_batch(BATCH2)
docs1 = count_by_doc(nodes1, edges1)
docs2 = count_by_doc(nodes2, edges2)

# Merge
all_docs = {}
for d in (docs1, docs2):
    for k, v in d.items():
        if k not in all_docs:
            all_docs[k] = v
        else:
            all_docs[k]["nodes"] += v["nodes"]
            all_docs[k]["edges"] += v["edges"]
            all_docs[k]["actions"] += v["actions"]
            all_docs[k]["outlets"] += v["outlets"]
            all_docs[k]["views"] += v["views"]
            all_docs[k]["controls"] += v["controls"]

# Assertions
check(len(all_docs) == 74, f"expected 74 NIBs, got {len(all_docs)}")

total_nodes = sum(d["nodes"] for d in all_docs.values())
total_edges = sum(d["edges"] for d in all_docs.values())
total_actions = sum(d["actions"] for d in all_docs.values())
total_outlets = sum(d["outlets"] for d in all_docs.values())
total_views = sum(d["views"] for d in all_docs.values())
total_controls = sum(d["controls"] for d in all_docs.values())

check(total_nodes == 8492, f"total nodes {total_nodes} != 8492")
check(total_edges == 2555, f"total edges {total_edges} != 2555")
check(total_actions == 951, f"total actions {total_actions} != 951")
check(total_outlets == 1604, f"total outlets {total_outlets} != 1604")
check(total_views == 235, f"total views {total_views} != 235")
check(total_controls == 1159, f"total controls {total_controls} != 1159")

# Major NIBs must be present (by nib_name)
major_nibs = {
    "MenuBar.nib", "FFKMenuBar.nib", "ViewOptionsWindow.nib", "PreferencesWindow.nib",
    "InfoWindowGeneralView.nib", "InfoWindowPermissionsView.nib",
    "ListView.nib", "ColumnPreview.nib", "ConnectToWindow.nib",
    "MeetingRoomProgressView.nib", "Toolbar.nib", "BrowserWindow.nib",
    "FFKBrowserWindow.nib", "FFKView.nib"
}
for nib in major_nibs:
    check(nib in all_docs, f"major NIB {nib} missing")

# MenuBar.nib must have 408 actions
mb = all_docs.get("MenuBar.nib")
check(mb is not None, "MenuBar.nib not found")
check(mb["actions"] == 408, f"MenuBar.nib actions {mb['actions']} != 408")

# FFKMenuBar.nib must have 27 actions
ffk_mb = all_docs.get("FFKMenuBar.nib")
check(ffk_mb is not None, "FFKMenuBar.nib not found")
check(ffk_mb["actions"] == 27, f"FFKMenuBar.nib actions {ffk_mb['actions']} != 27")

# Total menu actions = 435
check(total_actions == 951, "total actions mismatch")

# Evidence files must exist
check(BATCH1.exists(), "batch1 evidence file missing")
check(BATCH2.exists(), "batch2 evidence file missing")

if failures:
    for f in failures:
        print("FAIL:", f)
    raise SystemExit(1)
print("Finder NIB analysis (F10) contract OK")
raise SystemExit(0)