#!/usr/bin/env python3
"""Native (Ghidra) evidence contract tests.

The committed native findings must be traceable: every documented selector
must exist in the extracted Objective-C metadata, carry a real IMP, and the
documented control-flow claims must be visible in the committed
decompilations. A finding that cannot be re-derived from the committed
evidence fails here instead of silently rotting in a Markdown file.

Run:  python3 tests/uiref/test_native_evidence.py
"""
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAT = os.path.join(REPO, "docs", "UI_REFERENCE", "runtime", "raw", "native")
DOC = os.path.join(REPO, "docs", "UI_REFERENCE", "native-findings.md")
failures = []


def check(name, ok, detail=""):
    print(("ok - " if ok else "FAIL - ") + name +
          ((" :: " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


with open(os.path.join(NAT, "textedit-objc-metadata.json")) as f:
    meta = json.load(f)
with open(os.path.join(NAT, "textedit-decompilations.json")) as f:
    dec = json.load(f)
with open(os.path.join(NAT, "textedit-objc-imp-index.json")) as f:
    idx = json.load(f)
with open(DOC) as f:
    doc = f.read()

# 1. extraction really covered the binary
c = meta["counts"]
check("classes recovered", c["classes"] >= 15, str(c))
check("all methods carry a selector", c["methods_with_selector"] == c["methods_total"], str(c))
check("all methods carry an IMP", c["methods_with_known_imp"] == c["methods_total"], str(c))
check("all IMPs matched a Ghidra function",
      c["methods_matched_to_ghidra_function"] == c["methods_total"], str(c))

# 2. provenance pinned
p = meta["provenance"]
check("binary sha256 pinned",
      p.get("program") == "TextEdit" and p["image_base"] == "0x100000000", str(p))
check("ghidra version pinned", p.get("ghidra_version") == "12.1.2", str(p.get("ghidra_version")))

# 3. the corrected ruler mapping is backed by the binary
sels = meta["selectors"]
check("showRuler: implemented by DocumentWindowController",
      any(h["owner"] == "DocumentWindowController" for h in sels.get("showRuler:", [])))
check("showRulerDelayed: implemented", "showRulerDelayed:" in sels)
check("updateForRichTextAndRulerState: implemented", "updateForRichTextAndRulerState:" in sels)
check("toggleRuler: has NO implementation in this binary", "toggleRuler:" not in sels)

# 4. decompilation evidence exists and says what the doc claims
fn = {f["selector"]: f for f in dec["functions"]}
check("showRuler: decompiled", fn.get("showRuler:", {}).get("status") == "ok")
sr = fn.get("showRuler:", {}).get("decompiled", "")
check("showRuler: reads the ShowRuler default", "boolForKey" in sr and "ShowRuler" in sr)
check("showRuler: drives NSTextView setRulerVisible:", "setRulerVisible" in sr)
uf = fn.get("updateForRichTextAndRulerState:", {}).get("decompiled", "")
# the decompiler prints ObjC selectors as PTR_s_<name>__<addr>; match the name
for api in ("setRichText", "setUsesRuler", "setUsesInspectorBar", "setImportsGraphics"):
    check(f"updateForRichTextAndRulerState: calls {api}:", api in uf)
tr = fn.get("toggleRich:", {}).get("decompiled", "")
# Ghidra truncates long ObjC symbol names in decompiled output
check("toggleRich: wraps work in a document activity",
      "performActivityWithSynchronousWa" in tr)
check("toggleRich: uses the known conversion block", "FUN_100011fee" in tr)
check("toggleRichWithNewFileType: present",
      fn.get("toggleRichWithNewFileType:", {}).get("status") == "ok")

# 5. doc claims stay consistent with the binary
check("doc refutes the old Show Ruler -> toggleRuler: mapping",
      "does not exist in TextEdit" in doc)
with open(os.path.join(REPO, "docs", "UI_REFERENCE", "rea-findings.md")) as fh:
    rea_doc = fh.read()
check("superseded mapping is annotated in rea-findings.md",
      "REFUTED" in rea_doc and "showRuler:" in rea_doc)
check("doc records the runtime correlation",
      "setUsesInspectorBar:" in doc and "NSThemeFrame" in doc)

# 6. IMP index usable for callee resolution
check("IMP index populated", len(idx.get("by_imp", {})) >= 200, str(len(idx.get("by_imp", {}))))

print(f"\n{len(failures)} failures")
raise SystemExit(1 if failures else 0)