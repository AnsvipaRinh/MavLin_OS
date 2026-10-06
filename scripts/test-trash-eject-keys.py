#!/usr/bin/env python3
"""Validate Super+Delete (mv-trash) and Super+F4 (mv-eject) bindings + packaging."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = [
    os.path.join(
        REPO,
        "packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml",
    ),
    os.path.join(
        REPO,
        "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
        "xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml",
    ),
]
TRASH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-trash"
)
EJECT = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-eject"
)
MAKE = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/Makefile"
)
PKGS = os.path.join(REPO, "archiso-profile/releng/packages.x86_64")
DOC = os.path.join(REPO, "docs/KEYBOARD.md")

def executable_source(path):
    """Only the strings/attributes that actually run, docstrings excluded.

    mv-eject's module docstring quotes the dead GIO APIs on purpose (it is
    the record of what was broken), so a plain text search finds them and
    reports live code that is not there. Same approach as
    scripts/test-mv-eject.py.
    """
    import ast
    tree = ast.parse(open(path, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    parts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                parts.append(node.value)
        elif isinstance(node, ast.Attribute):
            parts.append(node.attr)
    return "\n".join(parts)


errors = []
for path in KB:
    if not os.path.isfile(path):
        errors.append("missing %s" % path)
        continue
    text = open(path, encoding="utf-8").read()
    if 'name="&lt;Super&gt;Delete" type="string" value="mv-trash"' not in text:
        errors.append("%s missing Super+Delete → mv-trash" % path)
    if 'name="&lt;Super&gt;F4" type="string" value="mv-eject"' not in text:
        errors.append("%s missing Super+F4 → mv-eject" % path)

if not os.path.isfile(TRASH):
    errors.append("mv-trash script missing")
else:
    body = open(TRASH, encoding="utf-8").read()
    if "trash-put" not in body:
        errors.append("mv-trash must call trash-put")

if not os.path.isfile(EJECT):
    errors.append("mv-eject missing")
else:
    # Look at executable code only. mv-eject's docstring quotes the dead
    # APIs on purpose — it is the record of what was broken — so a plain
    # text search reports them as live. Reuse the AST walk from the
    # dedicated suite so both gates see the same thing.
    eject_body = open(EJECT, encoding="utf-8").read()
    code_only = executable_source(EJECT)
    # mv-eject used to call Gio.UnixMountMonitor.get().get_mounts(), which no
    # longer exists in PyGObject, so every run died with an AttributeError
    # and the Super+F4 binding was a dead key. The resolution layer is now
    # /proc/self/mountinfo, which cannot rot with GObject introspection.
    if "UnixMountMonitor" in code_only:
        errors.append("mv-eject still calls the removed "
                      "Gio.UnixMountMonitor.get_mounts() API")
    if "unmount_with_operation" in code_only:
        errors.append("mv-eject still uses the async unmount with no "
                      "main loop (it silently did nothing)")
    if "/proc/self/mountinfo" not in code_only:
        errors.append("mv-eject must resolve mounts from "
                      "/proc/self/mountinfo")
    if "os.system" in code_only:
        errors.append("mv-eject must not shell out via os.system "
                      "(Python repr pasted into /bin/sh)")

mf = open(MAKE, encoding="utf-8").read()
if "bin/mv-trash" not in mf:
    errors.append("Makefile does not install mv-trash")

pkgs = open(PKGS, encoding="utf-8").read()
if "trash-cli" not in pkgs:
    errors.append("trash-cli missing from packages.x86_64")
if "xdotool" not in pkgs:
    errors.append("xdotool missing from packages.x86_64 (mv-trash fallback)")

doc = open(DOC, encoding="utf-8").read()
if "Super+Delete" not in doc or "Super+F4" not in doc:
    errors.append("KEYBOARD.md missing Super+Delete or Super+F4")

if errors:
    for e in errors:
        print("FAIL - %s" % e)
    sys.exit(1)

print("ok - Super+Delete → mv-trash")
print("ok - Super+F4 → mv-eject")
print("ok - mv-trash packaged in Makefile")
print("ok - trash-cli + xdotool in ISO")
