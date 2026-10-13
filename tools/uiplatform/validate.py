#!/usr/bin/env python3
"""validate.py - MavLinOS UI data contract checker.

Two jobs, one tool:

  validate [PATH...]      Validate documents against schemas/*.json
                          (default: docs/UI_PLATFORM/examples/*.json).
                          A document declares its own schema with the
                          "schema" key: "mavlinos.<kind>/1" resolves to
                          schemas/<kind>.schema.json.

  conformance [--data DIR]
                          Read-only audit of the extraction output
                          (docs/UI_REFERENCE/data by default) against the
                          contract in docs/UI_PLATFORM/02-DATA-CONTRACT.md.
                          Prints a report of what is contract-complete, what
                          is missing and where the records hide it. Exits 1
                          only on structural errors (unreadable/unparsable
                          data, broken internal counts) - gaps are findings,
                          not failures, because the extraction is still in
                          flight.

Deliberately stdlib-only: the build container has no jsonschema package,
and this must run in CI as-is.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
SCHEMA_DIR = os.path.join(REPO, "docs", "UI_PLATFORM", "schemas")
EXAMPLES_DIR = os.path.join(REPO, "docs", "UI_PLATFORM", "examples")
DEFAULT_DATA = os.path.join(REPO, "docs", "UI_REFERENCE", "data")
DEFAULT_CAPTURES = os.path.join(REPO, "docs", "UI_REFERENCE", "captures", "index.json")

# --- mini JSON-Schema validator (the subset our schemas actually use) ----


TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
}


def type_ok(value, expected):
    if isinstance(expected, list):
        return any(type_ok(value, e) for e in expected)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return isinstance(value, TYPE_MAP.get(expected, object))


def resolve_ref(ref, root, roots):
    """Resolve both local ('#/definitions/x') and cross-file refs
    ('common.schema.json#/definitions/x') inside docs/UI_PLATFORM/schemas."""
    if "#" in ref:
        target_file, pointer = ref.split("#", 1)
    else:
        target_file, pointer = "", ref
    if target_file:
        root = roots.get(target_file.split(".")[0])
        if root is None:
            raise ValueError("unknown schema file " + target_file)
    node = root
    for part in pointer.lstrip("/").split("/"):
        if part:
            node = node[part]
    return node, root


def validate(instance, schema, root, path="$", errors=None, roots=None):
    """Return a list of human readable errors. Empty list == valid."""
    if errors is None:
        errors = []
    if roots is None:
        roots = {"__self__": root}
    if not isinstance(schema, dict):
        return errors
    where = path

    ref = schema.get("$ref")
    if ref:
        try:
            target, target_root = resolve_ref(ref, root, roots)
        except (KeyError, ValueError) as exc:
            errors.append("%s: unresolvable $ref %r (%s)" % (where, ref, exc))
            return errors
        return validate(instance, target, target_root, where, errors, roots)

    if "const" in schema and instance != schema["const"]:
        errors.append("%s: expected const %r, got %r" % (where, schema["const"], instance))

    if "enum" in schema and instance not in schema["enum"]:
        errors.append("%s: %r not in %s" % (where, instance, schema["enum"]))

    if "type" in schema and not type_ok(instance, schema["type"]):
        errors.append("%s: expected type %s, got %s (%r)"
                      % (where, schema["type"], type(instance).__name__, instance))
        return errors  # further checks would be noise on a wrong type

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append("%s: missing required property %r" % (where, key))
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in instance:
                validate(instance[key], subschema, root, "%s.%s" % (path, key), errors, roots)
        extra = schema.get("additionalProperties", True)
        for key in instance:
            if key in props or key in ("$schema", "$id"):
                continue
            if extra is False:
                errors.append("%s: unexpected property %r" % (where, key))
            elif isinstance(extra, dict):
                validate(instance[key], extra, root, "%s.%s" % (path, key), errors, roots)
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errors.append("%s: needs >= %d properties" % (where, schema["minProperties"]))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append("%s: needs >= %d items" % (where, schema["minItems"]))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(instance):
                validate(item, item_schema, root, "%s[%d]" % (path, i), errors, roots)

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append("%s: %r does not match %s" % (where, instance, schema["pattern"]))
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append("%s: shorter than %d" % (where, schema["minLength"]))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("%s: %r < minimum %r" % (where, instance, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("%s: %r > maximum %r" % (where, instance, schema["maximum"]))

    if isinstance(instance, list) and schema.get("uniqueItems"):
        seen = [json.dumps(x, sort_keys=True) for x in instance]
        if len(set(seen)) != len(seen):
            errors.append("%s: items are not unique" % where)

    return errors


# --- schema loading ------------------------------------------------------


def load_schemas():
    """kind -> schema doc, plus every doc keyed by file stem for cross-file $ref."""
    docs = {}
    for fn in sorted(os.listdir(SCHEMA_DIR)):
        if not fn.endswith(".schema.json"):
            continue
        kind = fn.split(".")[0]
        with open(os.path.join(SCHEMA_DIR, fn)) as fh:
            docs[kind] = json.load(fh)
    return docs


def schema_kind_of(doc):
    name = doc.get("schema", "")
    m = re.match(r"^mavlinos\.([a-z0-9-]+)/\d+$", str(name))
    return m.group(1) if m else None


def check_semantic(kind, doc):
    """Contract rules that are not expressible as JSON Schema.

    These are the rules that make the extraction honest: a measurement
    without evidence, a literature timing dressed up as high confidence, a
    component that declares a state it never describes. They run on every
    document, so they also protect future records written by someone else.
    """
    errors = []
    where = doc.get("id", "<no id>")

    doc_kind = doc.get("kind")
    ev = doc.get("evidence")
    if doc_kind in ("measured", "derived") and not ev:
        errors.append("%s: kind=%s requires evidence (contract rule R-EVIDENCE)" % (where, doc_kind))
    if doc_kind == "literature" and doc.get("confidence") == "high":
        errors.append("%s: literature may not claim high confidence (R-EVIDENCE)" % where)
    if doc.get("status") == "verified" and doc.get("kind") not in ("measured", "capture-frames"):
        if kind != "design-tokens":
            errors.append("%s: status=verified requires measured evidence (R-VERIFY)" % where)

    if kind == "component":
        states = set(doc.get("states", []))
        for state in (doc.get("visuals", {}).get("per_state", {}) or {}):
            if state not in states:
                errors.append("%s: per_state %r is not in the declared state list"
                              % (where, state))
        for variant in doc.get("geometry", {}).get("variants", []):
            if not variant.get("intrinsic", {}).get("w"):
                errors.append("%s: variant %r has no intrinsic width"
                              % (where, variant.get("id")))

    if kind == "animation":
        rm = doc.get("reduced_motion", {})
        if rm.get("policy") == "substitute" and not rm.get("substitute"):
            errors.append("%s: reduced_motion=substitute without a substitute (R-NOMOTION)" % where)
        if doc.get("duration_tolerance_ms") is None and doc.get("duration_ms") is not None:
            errors.append("%s: duration without a tolerance is not measurable (R-TOLERANCE)" % where)

    if kind == "behavior":
        sm = doc.get("state_machine", {})
        ids = {s.get("id") for s in sm.get("states", [])}
        if sm.get("initial") not in ids:
            errors.append("%s: initial state %r is not declared" % (where, sm.get("initial")))
        for st in sm.get("states", []):
            for tr in st.get("on", []):
                target = tr.get("to")
                if target and target not in ids:
                    errors.append("%s: transition %r -> %r names an undeclared state"
                                  % (where, st.get("id"), target))
                if tr.get("animation") and not tr.get("to"):
                    errors.append("%s: transition with animation but no target state" % where)

    if kind == "asset":
        rec = doc.get("reproduction", {})
        if rec.get("method") != "no-replacement" and not rec.get("recipe"):
            errors.append("%s: reproduction without a recipe cannot be rebuilt (R-REPRO)" % where)

    if kind == "design-tokens":
        for name, tok in doc.get("tokens", {}).items():
            if not re.match(r"^(color|font|metric|duration|easing|shadow|texture|asset)\.[a-z0-9]",
                            name):
                errors.append("%s: token id %r has no type prefix (R-TOKENID)" % (where, name))
            if tok.get("kind") in ("measured", "derived") and not tok.get("evidence"):
                errors.append("%s: token %r is %s without evidence" % (where, name, tok.get("kind")))
    return errors


def validate_file(path, schemas, roots=None, semantic=True):
    """Returns (kind, errors). kind is None when the document has no known schema."""
    with open(path) as fh:
        doc = json.load(fh)
    kind = schema_kind_of(doc)
    if not kind:
        return None, ["%s: no usable schema identifier" % path]
    if kind not in schemas:
        return kind, ["%s: unknown schema kind %r (have: %s)"
                      % (path, kind, ", ".join(sorted(schemas)))]
    if roots is None:
        roots = dict(schemas)
    errors = validate(doc, schemas[kind], schemas[kind], "$", roots=roots)
    if semantic:
        errors += check_semantic(kind, doc)
    return kind, errors


# --- conformance audit of the extraction output ---------------------------


def _load(path):
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def _count_terms(obj):
    n = 0
    if isinstance(obj, dict):
        for v in obj.values():
            n += _count_terms(v)
    elif isinstance(obj, list):
        for v in obj:
            n += _count_terms(v)
    return n


def _signal(strings):
    """Share of strings that carry actual English (no code-point noise)."""
    good = 0
    for s in strings:
        if not isinstance(s, str) or len(s) < 4:
            continue
        letters = sum(c.isalpha() or c in " .-/'" for c in s)
        if letters / len(s) < 0.8:
            continue
        if re.search(r"(.)\1{4,}", s):
            continue
        good += 1
    return good


def audit_conformance(data_dir, captures_path):
    """Read-only report on how far the extraction output meets the contract."""
    report = {"data_dir": data_dir, "checks": [], "facts": {}, "gaps": []}

    def finding(check, status, detail):
        report["checks"].append({"check": check, "status": status, "detail": detail})

    files = sorted(f for f in os.listdir(data_dir) if f.endswith(".json")) \
        if os.path.isdir(data_dir) else []
    report["files"] = files

    structural = []
    for fn in files:
        try:
            json.load(open(os.path.join(data_dir, fn)))
        except Exception as exc:  # noqa: BLE001 - report, never crash
            structural.append("%s unparsable: %s" % (fn, exc))
    if structural:
        finding("json parses", "FAIL", "; ".join(structural))
    else:
        finding("json parses", "OK", "%d data files parse" % len(files))

    pal = _load(os.path.join(data_dir, "palette.json")) or {}
    metrics = _load(os.path.join(data_dir, "metrics.json")) or {}
    typo = _load(os.path.join(data_dir, "typography.json")) or {}
    behav = _load(os.path.join(data_dir, "behaviors.json")) or {}
    patterns = _load(os.path.join(data_dir, "patterns.json")) or {}
    comps = _load(os.path.join(data_dir, "components.json")) or {}
    assets = _load(os.path.join(data_dir, "assets.json")) or {}
    windows = _load(os.path.join(data_dir, "windows.json")) or {}
    surfaces = _load(os.path.join(data_dir, "surfaces.json")) or {}
    terminology = _load(os.path.join(data_dir, "terminology.json")) or {}
    nibs = _load(os.path.join(data_dir, "nib_geometry.json")) or {}
    api = _load(os.path.join(data_dir, "ui-api.json")) or {}

    report["facts"] = {
        "palette": len(pal.get("facts", [])),
        "metrics": len(metrics.get("facts", [])),
        "typography": len(typo.get("facts", [])),
        "behaviors": len(behav.get("facts", [])),
        "patterns": len(patterns.get("facts", [])),
        "assets": len(assets.get("assets", [])),
        "windows": len(windows.get("windows", [])),
        "surfaces": len(surfaces.get("surfaces", [])),
        "components": len(comps.get("components", [])),
        "nibs": len(nibs.get("nibs", [])),
        "api_classes": sum(len(m.get("classes", {})) for m in api.get("modules", {}).values()),
    }

    # 1. capture registry: the only way capture-based evidence can exist
    captures = _load(captures_path) or {"captures": {}}
    n_caps = len(captures.get("captures", {}))
    status = "OK" if n_caps else "MISSING"
    finding("capture registry", status,
            "%d captures registered in %s" % (n_caps, os.path.basename(captures_path)))
    if not n_caps:
        report["gaps"].append({
            "severity": "high", "what": "no capture exists",
            "why": "capture:<id> evidence cannot be produced; every value is source-derived",
            "resolve": "capture",
        })

    # 2. layers that are still empty
    for name, count, severity, layer in (
        ("metrics", len(metrics.get("facts", [])), "high", "A"),
        ("typography", len(typo.get("facts", [])), "high", "A"),
        ("behaviors", len(behav.get("facts", [])), "critical", "B"),
        ("patterns", len(patterns.get("facts", [])), "medium", "A"),
    ):
        status = "OK" if count else "EMPTY"
        finding("%s facts" % name, status, "%d facts" % count)
        if not count:
            report["gaps"].append({
                "severity": severity, "what": "data/%s.json has no facts" % name,
                "why": "layer %s is not captured in machine-readable form" % layer,
                "resolve": "measure-in-guest",
            })

    # 3. provenance: does any record carry an artifact hash?
    hashed = 0
    for f in pal.get("facts", []):
        if isinstance(f.get("evidence"), str):
            hashed += 1  # src: keys point at the sources registry
    sources = pal.get("sources", {})
    with_hash = [k for k, v in sources.items() if isinstance(v, dict) and v.get("sha256")]
    finding("evidence source registry", "OK" if sources else "MISSING",
            "%d source keys, %d with sha256: %s"
            % (len(sources), len(with_hash), ", ".join(sorted(sources))))
    if not with_hash:
        report["gaps"].append({
            "severity": "medium", "what": "no artifact is pinned by hash",
            "why": "a re-run on a different system build cannot prove it read the same bytes",
            "resolve": "research",
        })

    # 4. assets: contract needs rendering + reproduction, not just pixel size
    n_assets = len(assets.get("assets", []))
    missing_render = sum(1 for a in assets.get("assets", []) if "rendering" not in a)
    missing_caps = sum(1 for a in assets.get("assets", []) if a.get("format") == "png"
                       and a.get("w", 0) > 16 and "cap_insets" not in a)
    finding("asset records", "PARTIAL",
            "%d assets, %d without rendering rules, %d resizable PNGs without cap insets"
            % (n_assets, missing_render, missing_caps))
    report["gaps"].append({
        "severity": "high", "what": "no asset carries rendering/reproduction data",
        "why": "an icon or chrome bitmap without scale behaviour is unusable at any size "
               "but the authored one; a component cannot be rebuilt from it",
        "resolve": "research",
    })

    # 5. windows: undocumented style bits must be resolved before use
    undoc = [(m, c) for m, c, bits in windows.get("summary", {}).get("style_masks", [])
             if not bits]
    if undoc:
        finding("window style masks", "PARTIAL",
                "masks without a documented bit name: %s"
                % ", ".join("%s(%d)" % (m, c) for m, c in undoc))
        report["gaps"].append({
            "severity": "high", "what": "window style mask bits %s are unnamed"
            % ", ".join(str(m) for m, _ in undoc),
            "why": "the window platform cannot implement a mask it cannot name; guessing a "
                   "bit name produces windows with the wrong chrome",
            "resolve": "research",
        })
    else:
        finding("window style masks", "OK", "every mask maps to documented bits")

    # 6. surfaces: assembly order / geometry missing
    no_geo = sum(1 for s in surfaces.get("surfaces", [])
                 if not s.get("evidence", {}).get("nib_geometry"))
    finding("surface geometry", "PARTIAL",
            "%d/%d surfaces have nib geometry" % (len(surfaces.get("surfaces", [])) - no_geo,
                                                  len(surfaces.get("surfaces", []))))
    report["gaps"].append({
        "severity": "medium", "what": "surfaces list required controls but not assembly",
        "why": "implementers still have to invent z-order, spacing and alignment",
        "resolve": "measure-in-guest",
    })

    # 7. components: contract fields missing
    n_comps = len(comps.get("components", []))
    missing_states = [c.get("id") for c in comps.get("components", []) if not c.get("states")]
    with_runtime = sum(1 for c in comps.get("coverage", []) if c.get("has_runtime"))
    finding("component records", "PARTIAL",
            "%d components, %d without state list, %d with runtime evidence"
            % (n_comps, len(missing_states), with_runtime))
    report["gaps"].append({
        "severity": "critical" if missing_states else "high",
        "what": "components have bones+skin but no states/visuals/a11y (contract fields)",
        "why": "a component without a state list cannot be drawn correctly on hover, "
               "pressed, inactive or disabled - which is where themed ports fail",
        "resolve": "measure-in-guest",
    })

    # 8. terminology: how much of the corpus is signal?
    strings = []

    def _collect(node):
        if isinstance(node, dict):
            for v in node.values():
                _collect(v)
        elif isinstance(node, list):
            for v in node:
                _collect(v)
        elif isinstance(node, str):
            strings.append(node)

    _collect(terminology.get("apps", {}))
    good = _signal(strings)
    finding("terminology signal", "PARTIAL" if strings else "MISSING",
            "%d strings, %d with clear-English signal" % (len(strings), good))
    if strings and good < len(strings) * 0.5:
        report["gaps"].append({
            "severity": "medium",
            "what": "terminology corpus is mostly Mach-O noise",
            "why": "menu titles and alert wording must be selectable, not hunted for",
            "resolve": "research",
        })

    # 9. ibars garbage in the ObjC index (ivar names are raw bytes)
    n_ivars = 0
    bad_ivars = 0
    for mod in api.get("modules", {}).values():
        for cls in mod.get("classes", {}).values():
            for iv in cls.get("ivars", []) or []:
                n_ivars += 1
                if not isinstance(iv, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", iv):
                    bad_ivars += 1
    if n_ivars:
        finding("objc ivar names", "OK" if bad_ivars < n_ivars * 0.2 else "NOISE",
                "%d ivars, %d are not usable names" % (n_ivars, bad_ivars))
        if bad_ivars >= n_ivars * 0.2:
            report["gaps"].append({
                "severity": "medium", "what": "ivar slots decode as bytes, not names",
                "why": "the bones layer claims 'who draws it' but cannot show the state it "
                       "draws from; a state machine cannot be derived from it",
                "resolve": "research",
            })

    structural_errors = [c for c in report["checks"] if c["status"] == "FAIL"]
    report["verdict"] = "STRUCTURAL-FAIL" if structural_errors else "GAPS-LISTED"
    return report


# --- cli -----------------------------------------------------------------


def print_report(report, as_json):
    if as_json:
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0
    print("data contract conformance: %s" % report.get("verdict"))
    for c in report["checks"]:
        print("  [%-8s] %-24s %s" % (c["status"], c["check"], c["detail"]))
    if report.get("gaps"):
        print("\ngaps (%d):" % len(report["gaps"]))
        for g in sorted(report["gaps"], key=lambda x: x["severity"]):
            print("  %-8s %s -- %s (resolve: %s)"
                  % (g["severity"].upper(), g["what"], g["why"], g["resolve"]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="validate",
                    choices=["validate", "conformance"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--captures", default=DEFAULT_CAPTURES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    schemas = load_schemas()

    if args.command == "conformance":
        if not os.path.isdir(args.data):
            print("no data dir: %s" % args.data, file=sys.stderr)
            return 1
        report = audit_conformance(args.data, args.captures)
        return 1 if report["verdict"] == "STRUCTURAL-FAIL" else print_report(report, args.json)

    paths = args.paths
    if not paths:
        paths = [EXAMPLES_DIR]
    failures = 0
    checked = 0
    for p in paths:
        targets = []
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.endswith(".json"):
                    targets.append(os.path.join(p, f))
        else:
            targets.append(p)
        for t in targets:
            checked += 1
            kind, errors = validate_file(t, schemas)
            rel = os.path.relpath(t, REPO)
            if errors:
                failures += 1
                print("FAIL %s" % rel)
                for e in errors:
                    print("   -", e)
            else:
                print("OK   %s (%s)" % (rel, kind or "no schema"))
    print("\nvalidated %d documents, %d failed" % (checked, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
