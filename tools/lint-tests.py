#!/usr/bin/env python3
"""Lint test files for tests that cannot fail.

Born from three real defects found on 2026-10-06/07 (see docs/COORDINATION.md):
  * #186  scripts/test-mv-keychain.py lost its `if __name__ == "__main__"`
          block: the script ran nothing and exited 0.
  * #182  scripts/test-mv-about.py passed a quoted string as the condition
          of check(); a non-empty string is always true.
  * Perplexity tests (tests/test_mv_*.py) with no assertions that also
          launch real GUI apps through subprocess.

Rules (stdlib only, static, never executes the tests):
  ERROR no-entrypoint     scripts/test-*.py defines main() but has no
                          `if __name__ == "__main__"` block.
  ERROR string-condition  check("name", "literal") - both args are string
                          literals, so the condition is always true.
  ERROR const-assert      `assert "literal"` or `assert (cond, "msg")`.
  WARN  no-assertions     no assert/check/raise/exit anywhere in the file.
  WARN  gui-launch        runs bin/mv-* via subprocess without
                          mv_gui_iso / gui_display isolation.

Usage:
  python3 tools/lint-tests.py             # advisory: always exits 0
  python3 tools/lint-tests.py --strict    # exit 1 if any ERROR
  python3 tools/lint-tests.py --root=PATH # lint another checkout

NOTE: written without the ability to execute it. First real run may need
small fixes; treat the first output as a draft."""
import ast
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".worktrees", ".venv"}
ASSERT_CALLS = {"check", "fail", "bad", "expect", "raises", "exit"}
STRING_COND_CALLS = {"check", "expect", "ok_if", "assert_true"}


def find_files(root):
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".py"):
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            is_script_test = rel.startswith("scripts/") and name.startswith("test-")
            is_pkg_test = "/tests/" in ("/" + rel) and name.startswith("test_")
            if is_script_test or is_pkg_test:
                found.append(rel)
    return sorted(found)


def call_name(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def is_str_const(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def has_main_guard(tree):
    for node in tree.body:
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
            continue
        sides = [node.test.left] + list(node.test.comparators)
        names = [s.id for s in sides if isinstance(s, ast.Name)]
        consts = [s.value for s in sides if isinstance(s, ast.Constant)]
        if "__name__" in names and "__main__" in consts:
            return True
    return False


def defines_main(tree):
    return any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body)


def lint_file(root, rel):
    """Return a list of (level, line, rule, message)."""
    findings = []
    path = os.path.join(root, rel)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=rel)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return [("ERROR", 1, "unreadable", "cannot parse: %r" % (exc,))]

    is_script = rel.startswith("scripts/")
    if is_script and defines_main(tree) and not has_main_guard(tree):
        findings.append((
            "ERROR", 1, "no-entrypoint",
            "defines main() but has no `if __name__ == \"__main__\"` block: "
            "running the script executes nothing and exits 0"))

    assertions = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            assertions += 1
            test = node.test
            if is_str_const(test) and test.value:
                findings.append(("ERROR", node.lineno, "const-assert",
                                 "assert of a non-empty string literal is always true"))
            elif isinstance(test, ast.Tuple) and test.elts:
                findings.append(("ERROR", node.lineno, "const-assert",
                                 "assert of a non-empty tuple is always true "
                                 "(drop the parentheses around cond, msg)"))
        elif isinstance(node, ast.Raise):
            assertions += 1
        elif isinstance(node, ast.Call):
            name = call_name(node)
            if name.startswith("assert") or name in ASSERT_CALLS:
                assertions += 1
            if (name in STRING_COND_CALLS and len(node.args) >= 2
                    and is_str_const(node.args[0]) and is_str_const(node.args[1])
                    and node.args[1].value):
                findings.append((
                    "ERROR", node.lineno, "string-condition",
                    "%s(\"name\", \"literal\"): the condition is a string literal, "
                    "always true (remove the quotes around the expression)" % name))

    if assertions == 0:
        findings.append(("WARN", 1, "no-assertions",
                         "no assert/check/raise/exit anywhere: this file cannot fail"))

    if ("subprocess" in source and re.search(r"bin/mv-[a-z]", source)
            and "mv_gui_iso" not in source and "gui_display" not in source):
        findings.append(("WARN", 1, "gui-launch",
                         "runs a bin/mv-* app via subprocess without "
                         "mv_gui_iso/gui_display isolation"))
    return findings


def main(argv):
    strict = "--strict" in argv
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for arg in argv:
        if arg.startswith("--root="):
            root = os.path.abspath(arg.split("=", 1)[1])

    files = find_files(root)
    errors = 0
    warns = 0
    for rel in files:
        for level, line, rule, msg in sorted(lint_file(root, rel), key=lambda f: f[1]):
            print("%s %s:%d: [%s] %s" % (level, rel, line, rule, msg))
            if level == "ERROR":
                errors += 1
            else:
                warns += 1

    print("\nlint-tests: %d files, %d errors, %d warnings" % (len(files), errors, warns))
    if errors and not strict:
        print("(advisory mode: pass --strict to fail on errors)")
    return 1 if (strict and errors) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
