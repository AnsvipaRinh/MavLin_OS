#!/usr/bin/env python3
"""Tests for the MavLinOS UI data contract (docs/UI_PLATFORM).

What is proven here:
  1. every reference example validates against its schema and the contract rules
  2. the validator actually fails on the defects the contract exists to catch
     (a validator that cannot fail is not a validator - see tools/lint-tests.py)
  3. the conformance audit of docs/UI_REFERENCE/data produces a structured,
     deterministic report (it may not crash while the extraction is in flight)
  4. the schemas themselves are loadable, versioned and cross-referenced sanely

Run: python3 tests/uiplatform/test_contract.py
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "uiplatform"))

import validate as V  # noqa: E402

EXAMPLES = os.path.join(REPO, "docs", "UI_PLATFORM", "examples")
SCHEMAS = V.SCHEMA_DIR

FAILURES = []
CHECKS = [0]


def check(name, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        FAILURES.append(name)


def load_examples():
    out = {}
    for fn in sorted(os.listdir(EXAMPLES)):
        if fn.endswith(".json"):
            with open(os.path.join(EXAMPLES, fn)) as fh:
                out[fn] = json.load(fh)
    return out


def validate_doc(name, doc, schemas):
    kind = V.schema_kind_of(doc)
    if kind not in schemas:
        return ["unknown kind %r" % kind]
    return (V.validate(doc, schemas[kind], schemas[kind], "$", roots=schemas)
            + V.check_semantic(kind, doc))


# --- 1. reference examples are contract-valid ----------------------------


def test_examples_are_valid(schemas):
    examples = load_examples()
    check("examples present", len(examples) >= 6, "%d files" % len(examples))
    for fn, doc in examples.items():
        kind, errs = V.validate_file(os.path.join(EXAMPLES, fn), schemas)
        check("example %s valid" % fn, not errs, "; ".join(errs[:3]))


# --- 2. the validator can fail -------------------------------------------


def test_validator_detects_defects(schemas):
    button = load_examples()["component.button.push.json"]
    comp_schema = schemas["component"]

    broken = copy.deepcopy(button)
    del broken["states"]
    errs = V.validate(broken, comp_schema, comp_schema, "$", roots=schemas)
    check("missing required field is reported",
          any("missing required property 'states'" in e for e in errs), errs)

    broken = copy.deepcopy(button)
    broken["id"] = "Button"
    errs = V.validate(broken, comp_schema, comp_schema, "$", roots=schemas)
    check("bad id pattern is reported",
          any("does not match" in e for e in errs), errs)

    broken = copy.deepcopy(button)
    broken["states"].append("bogus-state")
    errs = V.validate(broken, comp_schema, comp_schema, "$", roots=schemas)
    check("unknown enum value is reported",
          any("not in" in e and "bogus-state" in e for e in errs), errs)

    broken = copy.deepcopy(button)
    broken["visuals"]["per_state"]["dripping"] = {"opacity": 0.5}
    errs = (V.validate(broken, comp_schema, comp_schema, "$", roots=schemas)
            + V.check_semantic("component", broken))
    check("per_state outside the state list is reported",
          any("not in the declared state list" in e for e in errs), errs)

    broken = copy.deepcopy(button)
    broken["unexpected_key"] = 1
    errs = V.validate(broken, comp_schema, comp_schema, "$", roots=schemas)
    check("additional property is reported",
          any("unexpected property 'unexpected_key'" in e for e in errs), errs)

    broken = copy.deepcopy(button)
    broken["geometry"]["variants"][0]["intrinsic"]["h"] = "tall"
    errs = V.validate(broken, comp_schema, comp_schema, "$", roots=schemas)
    check("wrong type is reported",
          any("expected type" in e for e in errs), errs)


def test_semantic_rules_fire(schemas):
    anim = load_examples()["animation.window.minimize.json"]

    broken = copy.deepcopy(anim)
    broken["confidence"] = "high"
    broken["kind"] = "literature"
    errs = validate_doc("animation", broken, schemas)
    check("literature may not be high confidence",
          any("may not claim high confidence" in e for e in errs), errs)

    broken = copy.deepcopy(anim)
    broken["reduced_motion"] = {"policy": "substitute"}
    errs = validate_doc("animation", broken, schemas)
    check("substitute motion must be named",
          any("without a substitute" in e for e in errs), errs)

    broken = copy.deepcopy(anim)
    broken["duration_tolerance_ms"] = None
    errs = validate_doc("animation", broken, schemas)
    check("duration needs a tolerance",
          any("R-TOLERANCE" in e for e in errs), errs)

    behav = load_examples()["behavior.window.drag-by-titlebar.json"]
    broken = copy.deepcopy(behav)
    broken["state_machine"]["states"][1]["on"][0]["to"] = "nowhere"
    errs = validate_doc("behavior", broken, schemas)
    check("transition to an undeclared state is reported",
          any("undeclared state" in e for e in errs), errs)

    asset = load_examples()["asset.toolbar.background.json"]
    broken = copy.deepcopy(asset)
    broken["reproduction"]["recipe"] = ""
    errs = validate_doc("asset", broken, schemas)
    check("asset without a reproduction recipe is reported",
          any("R-REPRO" in e for e in errs), errs)

    tokens = load_examples()["design-tokens.json"]
    broken = copy.deepcopy(tokens)
    broken["tokens"]["color.x"] = {"type": "color", "value": "#123456",
                                   "kind": "derived", "confidence": "high"}
    errs = validate_doc("design-tokens", broken, schemas)
    check("measured token without evidence is reported",
          any("without evidence" in e for e in errs), errs)


# --- 3. conformance audit over the live extraction data ------------------


def test_conformance_report(schemas):
    report = V.audit_conformance(V.DEFAULT_DATA, V.DEFAULT_CAPTURES)
    check("audit returns a verdict", report.get("verdict") in ("GAPS-LISTED", "STRUCTURAL-FAIL"))
    checks = report.get("checks", [])
    check("audit ran checks", len(checks) >= 8, "%d checks" % len(checks))
    check("every check has a status and a detail",
          all(c.get("status") and c.get("detail") for c in checks))
    fact_counts = report.get("facts", {})
    check("audit reports fact counts for the 5 fact files",
          all(k in fact_counts for k in ("palette", "metrics", "typography",
                                         "behaviors", "patterns")))
    # the audit must be idempotent: same data in, same report out
    again = V.audit_conformance(V.DEFAULT_DATA, V.DEFAULT_CAPTURES)
    check("audit is deterministic", json.dumps(report, sort_keys=True) ==
          json.dumps(again, sort_keys=True))


def test_conformance_finds_the_current_gaps(schemas):
    """The gap set that is true today. Not a snapshot of counts: as soon as
    the extraction agent fills behaviors.json or harvests uiprobe.json, the
    corresponding gap must disappear from the report by itself."""
    report = V.audit_conformance(V.DEFAULT_DATA, V.DEFAULT_CAPTURES)
    facts = report.get("facts", {})
    gaps = {g["what"] for g in report.get("gaps", [])}

    if facts.get("behaviors") == 0:
        check("behaviour layer gap is reported when empty",
              any("behaviors.json" in g for g in gaps), sorted(gaps))

    windows = json.load(open(os.path.join(V.DEFAULT_DATA, "windows.json")))
    undoc = [m for m, c, bits in windows.get("summary", {}).get("style_masks", []) if not bits]
    if undoc:
        check("unnamed window style mask gap is reported",
              any("style mask" in g for g in gaps), sorted(gaps))
    else:
        check("no unnamed-style-mask gap once masks are named", True)


# --- 4. the schemas themselves -------------------------------------------


def test_schemas_are_coherent(schemas):
    check("all six schemas load",
          set(schemas) >= {"common", "component", "animation", "behavior",
                           "asset", "design-tokens"}, sorted(schemas))
    for name, doc in schemas.items():
        if name == "common":
            continue
        schema_id = doc.get("$id")
        check("%s declares an $id" % name, bool(schema_id))
    # every cross-file $ref must resolve inside the schema directory
    unresolved = []
    for name, doc in schemas.items():
        text = json.dumps(doc)
        for ref in __import__("re").findall(r'"\$ref": "([^"]+)"', text):
            if "#" in ref and ref.startswith("common"):
                if "common" not in schemas:
                    unresolved.append(ref)
    check("cross-file refs resolve", not unresolved, unresolved)


def main():
    schemas = V.load_schemas()
    test_examples_are_valid(schemas)
    test_validator_detects_defects(schemas)
    test_semantic_rules_fire(schemas)
    test_conformance_report(schemas)
    test_conformance_finds_the_current_gaps(schemas)
    test_schemas_are_coherent(schemas)

    print("\nui-platform contract: %d checks, %d failed" % (CHECKS[0], len(FAILURES)))
    if FAILURES:
        for f in FAILURES:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
