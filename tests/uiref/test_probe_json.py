#!/usr/bin/env python3
"""mvprobe contract tests (pre-runtime).

These run on Linux and can fail: the probe's JSON writer is compiled against a
fake Objective-C runtime and the result must be valid, complete JSON that
reports gaps instead of invented values, and the Mach-O cross build must
produce real x86_64 binaries.

Run:  python3 tests/uiref/test_probe_json.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "tools", "uiref", "mvprobe.c")
SECTIONS = ("colors", "window", "controls", "text")
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
        print("FAIL - probe source missing: %s" % SRC)
        return 1
    tmp = tempfile.mkdtemp(prefix="mvprobe-test-")
    try:
        binary = os.path.join(tmp, "selftest")
        build = run(["clang", "-DMVPROBE_SELFTEST", "-o", binary, SRC])
        check("self test compiles on Linux", build.returncode == 0,
              (build.stderr or "")[-400:])
        if build.returncode != 0:
            return 1

        out = os.path.join(tmp, "probe.json")
        proc = run([binary, out])
        check("self test exits non-zero when sections fail (2)", proc.returncode == 2,
              "exit=%d" % proc.returncode)
        check("no temporary file is left behind",
              not os.path.exists(out + ".tmp"), os.listdir(tmp))

        try:
            with open(out) as fh:
                doc = json.load(fh)
            check("output is valid JSON", True)
        except Exception as exc:                      # noqa: BLE001
            check("output is valid JSON", False, str(exc))
            return 1

        check("schema is the contract id", doc.get("schema") == "mavlinos.uiprobe/2",
              str(doc.get("schema")))
        for key in ("errors", "gaps", "summary", "status", "environment"):
            check("document carries %r" % key, key in doc)
        for section in SECTIONS:
            check("section %s present with a status" % section,
                  isinstance(doc.get(section), dict) and "status" in doc.get(section, {}))
        summary = doc.get("summary", {})
        for key in ("items", "errors", "gaps", "status"):
            check("summary carries %r" % key, key in summary)
        check("failed sections are reported, not hidden",
              doc.get("status") == "partial" and summary.get("status") == "partial")
        check("gaps carry a resolution",
              all(g.get("resolution") for g in (doc.get("gaps") or [])),
              "gap without resolution")
        check("every gap names what is missing",
              all(g.get("missing") for g in (doc.get("gaps") or [])))
        check("errors name their section",
              all(e.get("section") for e in (doc.get("errors") or [])))
        check("no colour is invented when AppKit answers nothing",
              all(c.get("hex") is None for c in (doc.get("colors", {}).get("items") or [])))
        check("environment records units",
              doc.get("environment", {}).get("units", {}).get("geometry") == "pt")

        # The findings of the source audit must not come back:
        # the standard window button is an instance method with an enum
        # argument, control sizes must be the real NSControlSize values, and the
        # widget type must be probed as an instance method.
        source = open(SRC, encoding="utf-8").read()
        check("control sizes are Regular=0, Small=1, Mini=2",
              "CONTROL_SIZES[3] = {0, 1, 2}" in source)
        check("no invented 'large' control size", '"large"' not in source)
        check("standard window buttons use the enum, not a selector",
              'send_id_arg(win, "standardWindowButton:", BUTTON_KINDS[i])' in source)
        check("a real NSWindow instance is created",
              "initWithContentRect:styleMask:backing:defer:" in source)
        check("widget type uses an instance method",
              'has_instance_method(cls, "ns_widgetType")' in source
              and "class_getClassMethod" not in source)
        check("colours store hex and alpha separately",
              '\\"hex\\": %s%s%s, \\"alpha\\": %s' in source
              or '"hex": %s%s%s, "alpha": %s' in source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if not shutil.which("clang"):
        print("skip - Mach-O cross build (clang missing)")
    else:
        mach_dir = tempfile.mkdtemp(prefix="mvprobe-macho-")
        try:
            build = run(["bash", os.path.join(REPO, "tools", "uiref", "build-probe.sh"),
                         mach_dir])
            check("build-probe.sh succeeds", build.returncode == 0,
                  (build.stderr or "")[-400:])
            for name in ("mvprobe.dylib", "mvprobe-tool"):
                path = os.path.join(mach_dir, name)
                if not os.path.exists(path):
                    check("%s is produced" % name, False)
                    continue
                head = open(path, "rb").read(4)
                magic = head in (b"\xfe\xed\xfa\xce", b"\xcf\xfa\xed\xfe")
                check("%s is a Mach-O binary" % name, magic, head.hex())
        finally:
            shutil.rmtree(mach_dir, ignore_errors=True)

    print()
    if failures:
        print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("mvprobe contract OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
