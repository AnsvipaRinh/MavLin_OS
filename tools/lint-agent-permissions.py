#!/usr/bin/env python3
"""Check that every shell command an agent prompt tells the agent to run is
allowed by that agent's own `permission: bash:` list (OpenCode semantics:
last matching rule wins, `*` matches any text, no match = not allowed).

Why: orchestrator.md once told the agent to run `bash -c 'scripts/...'` and
`scripts/contrib/backlog.sh --refine` while its allow-list only contained the
bare `scripts/session-reuse.py ...` forms. Every such command was silently
denied, so the failure-recovery steps could not run.

Usage:
  python3 tools/lint-agent-permissions.py [agent.md ...]   (default: .opencode/agents/*.md)
  exit 0 = every referenced command is allowed; exit 1 = at least one is denied
"""
import glob
import os
import re
import sys

CMD_START = ("scripts/", "python3 scripts/", "git ", "sleep ", "bash ", "python3 ", "tools/")


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return "", text
    return m.group(1), m.group(2)


def parse_bash_rules(front):
    """Return ordered [(pattern, action)] from the `bash:` block."""
    rules, in_bash = [], False
    for line in front.split("\n"):
        if re.match(r"^\s{2}bash:\s*$", line):
            in_bash = True
            continue
        if in_bash:
            m = re.match(r'^\s{4}"(.+)":\s*(allow|deny|ask)\s*$', line)
            if m:
                rules.append((m.group(1), m.group(2)))
                continue
            if line.strip() == "" or re.match(r"^\s{4}\S", line):
                continue
            in_bash = False
    return rules


def glob_to_regex(pat):
    return re.compile("^" + ".*".join(re.escape(p) for p in pat.split("*")) + "$", re.S)


def decide(cmd, rules):
    verdict, rule = "ask", None
    for pat, action in rules:
        if glob_to_regex(pat).match(cmd):
            verdict, rule = action, pat
    return verdict, rule


def extract_commands(body):
    cmds = []
    for m in re.finditer(r"`([^`\n]+)`", body):
        span = m.group(1).strip()
        if span.startswith(CMD_START):
            cmds.append(span)
    in_fence = False
    for line in body.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.strip().startswith(CMD_START):
            cmds.append(line.strip())
    seen, out = set(), []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def lint(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    front, body = parse_frontmatter(text)
    rules = parse_bash_rules(front)
    if not rules:
        return [], 0
    bad = []
    cmds = extract_commands(body)
    for c in cmds:
        verdict, rule = decide(c, rules)
        if verdict != "allow":
            bad.append((c, verdict, rule))
    return bad, len(cmds)


def main(argv):
    paths = argv or sorted(glob.glob(".opencode/agents/*.md"))
    failed = 0
    for p in paths:
        bad, n = lint(p)
        for c, verdict, rule in bad:
            failed += 1
            print("DENIED %s: `%s` -> %s%s" % (
                p, c, verdict, " (rule %r)" % rule if rule else " (no matching rule)"))
        if not bad:
            print("ok %s: %d referenced commands, all allowed" % (p, n))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
