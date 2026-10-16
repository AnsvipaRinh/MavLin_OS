#!/usr/bin/env python3
"""REA evidence contract tests.

Every committed REA finding must carry its provenance (binary SHA256, REA
version, provider, evidence id) and must cross-check against the runtime observations it claims to support. Static findings are never
promoted to runtime facts by these tests — the mapping assertions check
that BOTH sides exist and agree on names, nothing more.

Run:  python3 tests/uiref/test_rea_evidence.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(REPO, "docs", "UI_REFERENCE", "runtime", "raw")
REA = os.path.join(RAW, "rea")
failures = []


def check(name, ok, detail=""):
    print(("ok - " if ok else "FAIL - ") + name +
          ((" :: " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def load_summary(app):
    with open(os.path.join(REA, f"rea_{app}_summary.json")) as f:
        return json.load(f)


def load_runtime(name):
    with open(os.path.join(RAW, "textedit-doc", name)) as f:
        return json.load(f)


# 1. provenance present on both summaries
for app in ("te", "calc"):
    s = load_summary(app)
    check(f"{app}: rea version pinned", s.get("rea_version") == "6.4.0", str(s.get("rea_version")))
    check(f"{app}: provider is disassembler-free", "no disassembler" in s.get("provider", ""), s.get("provider"))
    check(f"{app}: binary sha256 present", bool(s.get("subject_sha256")) and len(s["subject_sha256"]) == 64)
    check(f"{app}: evidence id present", bool(s.get("evidence_id")))
    check(f"{app}: documents non-empty", len(s.get("documents", [])) > 0)
    check(f"{app}: selector inventory non-empty", len(s.get("selector_inventory", [])) > 0)

# 2. known binary identities (extracted 2026-10-16, cross-checked vs REA target_sha256)
te = load_summary("te")
check("textedit binary sha256", te["subject_sha256"] == "47ce7ec7e8151f4b64f4470314e61ee5f553f848234f2bf1978172d34cacf1a0")
calc = load_summary("calc")
check("calculator binary sha256", calc["subject_sha256"] == "c2ff9f04f3188f802bd2b03bfc809b4a7175f0d240d8f13bf3cc262c0ea18445")

# 3. NIB side of the claimed mappings exists
check("toggleRuler: in TextEdit NIB selectors", "toggleRuler:" in te["selector_inventory"])
check("toggleRich: in TextEdit NIB selectors", "toggleRich:" in te["selector_inventory"])
check("digit: in Calculator NIB selectors", "digit:" in calc["selector_inventory"])
check("enter: in Calculator NIB selectors", "enter:" in calc["selector_inventory"])

# 4. runtime side of the claimed mappings exists (names agree, nothing promoted)
rt = load_runtime("textedit-doc-blank.json")


def menu_titles(m, out):
    for it in m.get("items", []):
        if it.get("title"):
            out.append(it["title"])
        menu_titles(it, out)
    return out


titles = menu_titles(rt["main_menu"], [])
check("runtime menu has Show Ruler", "Show Ruler" in titles)
check("runtime menu has Make Rich Text", "Make Rich Text" in titles)

# 5. code-constructed UI is ABSENT from NIBs (the F1 finding, machine-checked)
te_blob = json.dumps(te)
for absent in ("NSInspectorBarView", "NSInspectorBarItemController", "NSRulerView", "ScalingScrollView"):
    check(f"{absent} absent from TextEdit NIB evidence", absent not in te_blob)

print(f"\n{len(failures)} failures")
raise SystemExit(1 if failures else 0)
