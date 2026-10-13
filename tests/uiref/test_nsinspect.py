#!/usr/bin/env python3
"""nsinspect contract tests (pre-runtime).

The inspector must be able to prove that it inspects *runtime objects*, not
screenshots: these checks build it, validate the document structure against the
contract, and assert that the source actually asks AppKit for windows, views,
control cells, control sizes, bezel styles and target/action pairs.

Run:  python3 tests/uiref/test_nsinspect.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "tools", "uiref", "nsinspect.c")
failures = []


def check(name, ok, detail=""):
    print(("ok - " if ok else "FAIL - ") + name +
          ((" :: " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    if not os.path.exists(SRC):
        print("FAIL - inspector source missing: %s" % SRC)
        return 1
    tmp = tempfile.mkdtemp(prefix="nsinspect-test-")
    try:
        binary = os.path.join(tmp, "selftest")
        build = run(["clang", "-DNSINSPECT_SELFTEST", "-o", binary, SRC])
        check("self test compiles on Linux", build.returncode == 0,
              (build.stderr or "")[-400:])
        if build.returncode != 0:
            return 1

        out = os.path.join(tmp, "nsinspect.json")
        proc = run([binary, out])
        check("self test runs and exits non-zero when AppKit is absent",
              proc.returncode == 2, "exit=%d" % proc.returncode)
        check("no temporary file is left behind",
              not os.path.exists(out + ".tmp"), os.listdir(tmp))

        try:
            with open(out) as fh:
                doc = json.load(fh)
            check("output is valid JSON", True)
        except Exception as exc:                      # noqa: BLE001
            check("output is valid JSON", False, str(exc))
            return 1

        check("schema is the contract id", doc.get("schema") == "mavlinos.nsinspect/1",
              str(doc.get("schema")))
        for key in ("kind", "extractor", "aqua_session", "windows",
                    "controls_found", "status"):
            check("document carries %r" % key, key in doc)
        check("kind is runtime-observed, not OCR or screenshot derived",
              doc.get("kind") == "runtime-observed", str(doc.get("kind")))
        check("status is reported, not hidden",
              doc.get("status") in ("ok", "failed - no AppKit in this process"),
              str(doc.get("status")))

        # The whole point of the tool: it must query live objects.
        source = open(SRC, encoding="utf-8").read()
        for sel in ("sharedApplication", "windows", "contentView", "subviews",
                    "objectAtIndex:", "count", "frame", "styleMask",
                    "isKeyWindow", "isMainWindow", "isVisible", "level"):
            check("inspects %s" % sel, '"%s"' % sel in source)
        for sel in ("cell", "controlSize", "bezelStyle", "doubleValue", "minValue",
                    "maxValue", "target", "action", "tag", "isEnabled", "alphaValue"):
            check("reads control property %s" % sel, '"%s"' % sel in source)
        check("walks superclasses to classify controls", "class_getSuperclass" in source)
        check("resolves selectors to names, never guessing", "sel_getName" in source)
        check("uses the objective-C runtime, not screenshot analysis",
              "objc_msgSend" in source and "screendump" not in source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if not shutil.which("clang"):
        print("skip - Mach-O cross build (clang missing)")
    else:
        mach_dir = tempfile.mkdtemp(prefix="nsinspect-macho-")
        try:
            build = run(["bash", os.path.join(REPO, "tools", "uiref", "build-nsinspect.sh"),
                         mach_dir])
            check("build-nsinspect.sh succeeds", build.returncode == 0,
                  (build.stderr or "")[-400:])
            for name in ("nsinspect.dylib", "nsinspect-tool"):
                path = os.path.join(mach_dir, name)
                if not os.path.exists(path):
                    check("%s is produced" % name, False)
                    continue
                head = open(path, "rb").read(4)
                check("%s is a Mach-O binary" % name, head in (b"\xfe\xed\xfa\xce", b"\xcf\xfa\xed\xfe"),
                      head.hex())
        finally:
            shutil.rmtree(mach_dir, ignore_errors=True)

    print()
    if failures:
        print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("nsinspect contract OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
