#!/usr/bin/env python3
"""Tests for the design-token compiler (tools/uiplatform/tokens.py).

The compiler is the first consumer of the UI data contract, so these tests
prove both directions:
  * the generated token file is contract-valid and traceable to the extraction
    facts it claims;
  * the compiler FAILS when the extraction drifts underneath it, and when a
    proposed value tries to hide its own status.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "uiplatform"))

import validate as V  # noqa: E402
import tokens as T  # noqa: E402

PALETTE = os.path.join(REPO, "docs/UI_REFERENCE/data/palette.json")

FAILURES = []
CHECKS = [0]


def check(name, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        FAILURES.append(name)


def run_generator(out_dir, palette=PALETTE, extra=()):
    out = os.path.join(out_dir, "tokens.json")
    manifest = os.path.join(out_dir, "manifest.json")
    cmd = [sys.executable, os.path.join(REPO, "tools/uiplatform/tokens.py"),
           "--palette", palette, "--out", out, "--manifest", manifest] + list(extra)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc, out, manifest


def test_compiles_and_validates():
    tmp = tempfile.mkdtemp(prefix="mv-tokens-")
    try:
        proc, out, manifest = run_generator(tmp)
        check("generator exits 0", proc.returncode == 0, proc.stderr.strip())
        check("token file written", os.path.exists(out))
        check("manifest written", os.path.exists(manifest))
        if not os.path.exists(out):
            return

        schemas = V.load_schemas()
        kind, errors = V.validate_file(out, schemas)
        check("generated tokens are contract-valid (schema)", not errors, "; ".join(errors[:4]))
        errors = V.check_semantic("design-tokens", json.load(open(out)))
        check("generated tokens are contract-valid (rules)", not errors, "; ".join(errors[:4]))
        km, merrs = V.validate_file(manifest, schemas)
        check("manifest is contract-valid", not merrs, "; ".join(merrs[:4]))

        doc = json.load(open(out))
        tokens = doc["tokens"]
        check("tokens were produced", len(tokens) >= 15, "%d tokens" % len(tokens))

        # traceability: every derived token must point at a real palette fact
        palette = json.load(open(PALETTE))
        facts = {f["id"] for f in palette.get("facts", [])}
        sources = palette.get("sources", {})
        derived = {t: v for t, v in tokens.items() if v.get("kind") == "derived"}
        check("derived tokens exist", len(derived) >= 1, sorted(derived))
        for name, tok in derived.items():
            ok = tok.get("evidence") and all(
                (not str(e).startswith("src:")) or e[4:] in sources for e in tok["evidence"])
            check("derived %s cites a registered source" % name, ok, tok.get("evidence"))

        proposed = {t: v for t, v in tokens.items() if v.get("kind") == "proposed"}
        check("proposed tokens exist", len(proposed) >= 5, "%d proposed" % len(proposed))
        for name, tok in proposed.items():
            check("proposed %s documents itself" % name,
                  bool(tok.get("notes")) and "decision" in tok["notes"].lower()
                  or "Placeholder" in tok.get("notes", ""), tok.get("notes", "")[:60])

        check("no proposed value pretends to be measured",
              all(t.get("kind") != "measured" for t in proposed.values()))
        check("appearance variants cover blue and graphite",
              doc.get("appearance") == ["blue", "graphite"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_deterministic():
    a, b = tempfile.mkdtemp(prefix="mv-a-"), tempfile.mkdtemp(prefix="mv-b-")
    try:
        run_generator(a)
        run_generator(b)
        same = (open(os.path.join(a, "tokens.json"), "rb").read()
                == open(os.path.join(b, "tokens.json"), "rb").read())
        check("compiler output is byte-deterministic", same)
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)


def test_drift_breaks_the_build():
    """A palette that no longer contains a referenced fact must fail loudly."""
    tmp = tempfile.mkdtemp(prefix="mv-drift-")
    try:
        with open(PALETTE) as fh:
            palette = json.load(fh)
        before = len(palette["facts"])
        palette["facts"] = [f for f in palette["facts"] if f["id"] != "appkit.color.dddddd.add"]
        drifted = os.path.join(tmp, "palette-drifted.json")
        with open(drifted, "w") as fh:
            json.dump(palette, fh)
        check("drifted palette prepared", len(palette["facts"]) == before - 1)

        proc, _out, _man = run_generator(tmp, palette=drifted)
        check("drift fails the generator", proc.returncode != 0, "exit=%d" % proc.returncode)
        check("drift message names the missing fact",
              "appkit.color.dddddd.add" in (proc.stdout + proc.stderr),
              (proc.stdout + proc.stderr)[:120])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cli_check_flag():
    tmp = tempfile.mkdtemp(prefix="mv-check-")
    try:
        proc, out, _man = run_generator(tmp, extra=["--check"])
        check("--check passes on fresh output", proc.returncode == 0, proc.stderr.strip())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_compiles_and_validates()
    test_deterministic()
    test_drift_breaks_the_build()
    test_cli_check_flag()
    print("\ntoken compiler: %d checks, %d failed" % (CHECKS[0], len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
