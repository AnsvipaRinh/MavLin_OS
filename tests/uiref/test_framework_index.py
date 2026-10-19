#!/usr/bin/env python3
"""Framework-index regression tests.

Validates that the committed framework analysis (produced by
tools/uiref/framework_index.py from the extracted Mavericks framework binaries)
re-covers the structural facts the platform model depends on. A finding that
cannot be re-derived here fails instead of silently rotting in Markdown.

Run:  python3 tests/uiref/test_framework_index.py
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDX = os.environ.get("FRAMEWORK_INDEX_DIR",
                     "/home/builder/vmwork/opencode/frameworks/index")

FRAMES = ["AppKit", "Foundation", "CoreGraphics", "CoreFoundation",
          "QuartzCore", "HIToolbox", "libobjc.A.dylib"]

failures = []


def load(name):
    with open(os.path.join(IDX, "%s.x86_64.json" % name)) as f:
        return json.load(f)


def check(name, ok, detail=""):
    print(("ok - " if ok else "FAIL - ") + name +
          ((" :: " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


data = {}
for f in FRAMES:
    try:
        data[f] = load(f)
    except FileNotFoundError:
        check("index exists: %s" % f, False, "missing index file")
        data[f] = None

# 1. every framework indexed with non-trivial content
for f in FRAMES:
    d = data[f]
    if d is None:
        continue
    check("%s parses" % f, True, "%d classes, %d defined syms" %
          (len(d["objc"]["classes"]), len(d["symbols"]["defined"])))

# 2. class-count floor (frameworks must not collapse)
check("AppKit classes >= 1000",
      data["AppKit"] and len(data["AppKit"]["objc"]["classes"]) >= 1000,
      str(len(data["AppKit"]["objc"]["classes"]) if data["AppKit"] else 0))
check("Foundation classes >= 400",
      data["Foundation"] and len(data["Foundation"]["objc"]["classes"]) >= 400,
      str(len(data["Foundation"]["objc"]["classes"]) if data["Foundation"] else 0))
check("CoreGraphics has defined symbols (pure C)",
      data["CoreGraphics"] and len(data["CoreGraphics"]["symbols"]["defined"]) > 10000,
      str(len(data["CoreGraphics"]["symbols"]["defined"]) if data["CoreGraphics"] else 0))

# 3. framework coupling: AppKit sits on CoreGraphics + Foundation + libobjc
ak = data["AppKit"]
dep_names = [dep["name"] for dep in (ak["dependencies"] if ak else [])]
for dep in ("CoreGraphics.framework", "CoreFoundation.framework",
            "/usr/lib/libobjc.A.dylib", "QuartzCore.framework",
            "Carbon.framework"):
    check("AppKit depends on %s" % dep,
          any(dep in d for d in dep_names), str(dep_names))

# 4. CGS surface present in CoreGraphics (the WindowServer boundary)
cg = data["CoreGraphics"]
cgs = [s["name"] for s in (cg["symbols"]["defined"] if cg else [])
       if s["name"].startswith("_CGS")]
check("CoreGraphics defines _CGS* symbols", len(cgs) > 100,
      "%d found" % len(cgs))
for sym in ("_CGSNewWindow", "_CGSOrderWindow", "_CGSAddSurface",
            "_CGSAddTrackingRect", "_CGSSetDockRectWithReason",
            "_CGSAddWindowsToSpaces", "_CGSGetWindowLevel",
            "_CGSSetWindowLevel", "_CGSGetWorkspace"):
    check("CGS symbol %s defined" % sym,
          any(s in cgs for s in [sym]), "present")

# 5. AppKit imports CGS (boundary direction: AppKit -> CoreGraphics)
if ak:
    undef = [s["name"] for s in ak["symbols"]["undefined"]]
    for sym in ("_CGSNewWindow", "_CGSOrderWindow", "_CGSAddSurface",
                "_CGSSetWindowLevel", "_CPSSetFrontProcessWithOptions"):
        check("AppKit imports %s" % sym, sym in undef, "present")

# 6. AppKit class hierarchy (responder chain)
cl = {c["name"]: c for c in (ak["objc"]["classes"] if ak else [])}
for cn, sup in (("NSApplication", "NSResponder"),
                ("NSWindow", "NSResponder"),
                ("NSView", "NSResponder"),
                ("NSControl", "NSView"),
                ("NSButton", "NSControl"),
                ("NSPanel", "NSWindow")):
    c = cl.get(cn)
    check("class %s super == %s" % (cn, sup),
          c is not None and c.get("super") == sup,
          "super=%s" % (c.get("super") if c else "MISSING"))

# 7. key entry-point selectors present in AppKit (exact selectors + IMP)
def selectors_of(cn):
    c = cl.get(cn)
    return {m["selector"]: m for m in (c["methods"] if c else [])}

nsapp = selectors_of("NSApplication")
for sel in ("run", "sendEvent:", "nextEventMatchingMask:untilDate:inMode:dequeue:",
            "postEvent:atStart:", "currentEvent"):
    check("NSApplication implements %s" % sel,
          sel in nsapp and nsapp[sel].get("imp"),
          sel)

nswin = selectors_of("NSWindow")
for sel in ("initWithContentRect:styleMask:backing:defer:",
            "makeKeyAndOrderFront:", "makeKeyWindow", "setContentView:",
            "contentView", "setLevel:", "setOpaque:", "display",
            "orderFront:", "orderBack:", "becomeKeyWindow", "resignKeyWindow"):
    check("NSWindow implements %s" % sel, sel in nswin and nswin[sel].get("imp"),
          sel)

nsview = selectors_of("NSView")
for sel in ("setNeedsDisplay:", "setNeedsDisplayInRect:", "layoutSubtreeIfNeeded",
            "setNeedsLayout:", "hitTest:", "setFrame:"):
    check("NSView implements %s" % sel, sel in nsview and nsview[sel].get("imp"),
          sel)

# NSTextView ruler/inspector-bar API (validated against TextEdit findings)
nstv = selectors_of("NSTextView")
for sel in ("setRulerVisible:", "setUsesInspectorBar:", "setUsesRuler:", "drawRect:"):
    check("NSTextView implements %s" % sel,
          sel in nstv and nstv[sel].get("imp"), sel)

# 8. responder-chain methods on NSResponder
nsresp = selectors_of("NSResponder")
for sel in ("mouseDown:", "keyDown:", "flagsChanged:",
            "tryToPerform:with:", "interpretKeyEvents:"):
    check("NSResponder implements %s" % sel,
          sel in nsresp and nsresp[sel].get("imp"), sel)

print()
if failures:
    print("FAILURES: %d" % len(failures))
    sys.exit(1)
print("ALL FRAMEWORK-INDEX REGRESSION TESTS PASSED")
