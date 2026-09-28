#!/usr/bin/env python3
"""Headless validation for the Mavericks Firefox chrome CSS.

Checks both configs/firefox/chrome/*.css files:
- UTF-8 encoding, LF-only line endings (no CR bytes)
- balanced braces, parseable rule structure, no @-rules
- every declared property is in the allowlist (standard + -moz-*);
  GTK-only properties (-gtk-*) are rejected outright
- every CSS selector appears in element-inventory.json and every
  inventory entry is used by some CSS file (no drift either direction)
- reports !important usage count

Usage: python3 scripts/test-firefox-chrome.py
Exit 0 = all checks passed."""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_DIR = os.path.join(REPO, "configs/firefox/chrome")
CSS_FILES = [
    os.path.join(CHROME_DIR, "userChrome.css"),
    os.path.join(CHROME_DIR, "userContent.css"),
]
INVENTORY_PATH = os.path.join(CHROME_DIR, "element-inventory.json")

ALLOWED_PROPS = {
    "background", "background-color", "background-image",
    "border", "border-bottom", "border-color", "border-radius",
    "box-shadow", "color", "font-family", "font-size", "height",
    "margin", "margin-bottom", "margin-left", "min-height", "opacity",
    "padding", "transition",
}

GTK_ONLY_PROPS = {
    "-gtk-dpi", "-gtk-effect", "-gtk-icon-palette", "-gtk-icon-shadow",
    "-gtk-icon-style", "-gtk-icon-transform",
}

RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
AT_RULE_RE = re.compile(r"@[a-z-]+\s*[{};]")


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def strip_comments(text):
    return COMMENT_RE.sub("", text)


def check_encoding(path, raw):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        check("%s: valid UTF-8" % os.path.basename(path), False, str(e))
        return None
    check("%s: valid UTF-8" % os.path.basename(path), True)
    check("%s: LF-only line endings" % os.path.basename(path),
          b"\r" not in raw, "found CR byte(s)")
    return text


def check_braces(path, text):
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                check("%s: brace balance" % os.path.basename(path), False,
                      "unmatched } at offset %d" % i)
                return False
    check("%s: brace balance" % os.path.basename(path), depth == 0,
          "depth %d at EOF" % depth)
    return depth == 0


def parse_rules(text):
    rules = []
    for m in RULE_RE.finditer(text):
        sel = m.group(1).strip()
        body = m.group(2)
        if not sel or sel.startswith("@"):
            continue
        decls = []
        for d in body.split(";"):
            d = d.strip()
            if not d:
                continue
            prop, _, val = d.partition(":")
            decls.append((prop.strip().lower(), val.strip()))
        rules.append((sel, decls))
    return rules


def check_properties(rules):
    for sel, decls in rules:
        for prop, _val in decls:
            is_gtk = prop in GTK_ONLY_PROPS or prop.startswith("-gtk-")
            is_allowed = prop in ALLOWED_PROPS or prop.startswith("-moz-")
            check("prop '%s' (%s)" % (prop, sel),
                  not is_gtk and is_allowed,
                  "GTK-only property" if is_gtk
                  else "not in allowlist and not -moz-*")


def check_selectors(css_selectors, inv_selectors):
    missing = sorted(s for s in css_selectors if s not in inv_selectors)
    check("css selectors present in inventory", not missing,
          "missing: %s" % ", ".join(missing[:5]))
    stale = sorted(s for s in inv_selectors if s not in css_selectors)
    check("inventory entries used by css", not stale,
          "stale: %s" % ", ".join(stale[:5]))


def count_important(rules):
    return sum(1 for _, decls in rules for _, v in decls
               if "!important" in v)


def main():
    for path in CSS_FILES:
        check("exists %s" % os.path.basename(path), os.path.exists(path))

    text_map = {}
    for path in CSS_FILES:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        text = check_encoding(path, raw)
        if text is None:
            continue
        text = strip_comments(text)
        if check_braces(path, text):
            text_map[path] = text

    check("no @-rules in chrome css",
          not any(AT_RULE_RE.search(t) for t in text_map.values()))

    all_rules = {p: parse_rules(t) for p, t in text_map.items()}
    for rules in all_rules.values():
        check_properties(rules)

    css_selectors = set()
    for rules in all_rules.values():
        for sel, _ in rules:
            for part in sel.split(","):
                part = part.strip()
                if part:
                    css_selectors.add(part)

    inv_selectors = set()
    if os.path.exists(INVENTORY_PATH):
        with open(INVENTORY_PATH, encoding="utf-8") as f:
            inv = json.load(f)
        inv_selectors = set(inv.get("selectors", {}).keys())
        check("inventory file loads", True)
    else:
        check("inventory file loads", False, INVENTORY_PATH)
    check_selectors(css_selectors, inv_selectors)

    n_imp = sum(count_important(r) for r in all_rules.values())
    print("info: %d selectors, %d !important declarations"
          % (len(css_selectors), n_imp))

    print("\n%d checks, %d failures" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
