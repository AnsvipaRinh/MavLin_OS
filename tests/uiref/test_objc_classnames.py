#!/usr/bin/env python3
"""Contract tests for Objective-C class-name resolution across supported ABIs.

Two classes of regression matter here:

1. Binaries whose class names *are* present in __objc_classname (TextEdit,
   Calculator and both calculator plug-ins) must keep resolving every class,
   otherwise a change made to satisfy Finder silently degrades proven results.

2. Binaries whose class names are absent from the binary (Finder) must report
   every class as explicitly unresolved.  A test that can fail here is the guard
   against the previous behaviour, where a rejected pointer was decoded anyway
   and produced several hundred plausible-looking but fictional class names.

Run:  python3 tests/uiref/test_objc_classnames.py
"""
import json
import pathlib
import sys

RAW = pathlib.Path(__file__).resolve().parents[2] / "docs/UI_REFERENCE/runtime/raw/native"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def load(name):
    return json.loads((RAW / name).read_text())


def classes_of(doc):
    return [c for c in doc.get("classes", []) if "name" in c]


def is_identifier(s):
    return bool(s) and all(ch.isalnum() or ch in "_$" for ch in s)


# 1. Binaries with real class names must resolve every class.
RESOLVING = {
    "regression-textedit.json": (15, 253),
    "regression-calc.json": (11, 217),
    "regression-basic.json": (8, 153),
    "regression-hex.json": (2, 77),
}
for fname, (n_classes, n_methods) in RESOLVING.items():
    doc = load(fname)
    cls = classes_of(doc)
    check(
        len(cls) == n_classes,
        f"{fname}: expected {n_classes} classes, got {len(cls)}",
    )
    unnamed = [c for c in cls if not c.get("name")]
    check(
        not unnamed,
        f"{fname}: {len(unnamed)} class(es) lost their name, e.g. {unnamed[:2]}",
    )
    malformed = [c["name"] for c in cls if not is_identifier(c["name"])]
    check(
        not malformed,
        f"{fname}: {len(malformed)} malformed class name(s), e.g. {malformed[:2]}",
    )
    total = doc.get("counts", {}).get("methods_total", n_methods)
    check(
        total == n_methods,
        f"{fname}: expected {n_methods} methods, got {total}",
    )

# 2. Finder must be explicit about unresolved names, never invent them.
finder = load("finder-objc-metadata.json")
fcls = classes_of(finder)
check(len(fcls) == 663, f"finder: expected 663 class entries, got {len(fcls)}")

named = [c for c in fcls if c.get("name")]
check(
    not named,
    f"finder: {len(named)} class name(s) must be unresolved, "
    f"binary stores no class names; got e.g. {[c['name'] for c in named[:3]]}",
)
unresolved = [c for c in fcls if c.get("name_source") == "unresolved"]
check(
    len(unresolved) == len(fcls),
    f"finder: every class needs name_source=unresolved, "
    f"got {len(unresolved)}/{len(fcls)}",
)
check(
    all(c.get("class_ptr", "").startswith("0x") for c in fcls),
    "finder: every class must still carry its class pointer",
)

counts = finder.get("counts", {})
check(
    counts.get("methods_total") == 9337,
    f"finder: expected 9337 methods, got {counts.get('methods_total')}",
)
check(
    counts.get("methods_with_known_imp") == 9286,
    f"finder: expected 9286 methods with IMP, got {counts.get('methods_with_known_imp')}",
)

# 3. The ABI evidence backing the Finder verdict must stay in the repository.
abi = load("finder-abi-layout.json")
check("sections" in abi, "finder-abi-layout.json: section table missing")
check(
    any("__objc_classname" in k for k in abi.get("sections", {})),
    "finder-abi-layout.json: __objc_classname bounds missing",
)

if failures:
    for f in failures:
        print("FAIL:", f)
    raise SystemExit(1)
print("objc class-name resolution contract OK")
raise SystemExit(0)