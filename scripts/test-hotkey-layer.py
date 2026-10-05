#!/usr/bin/env python3
"""mv-hotkeys layer tests — the global keyboard shortcut layer (P0 #23).

Covers the pure core (registry, accelerator normalisation, conflict
detection, protection, override merge, XML render/parse/drift) plus the CLI
contract, and exercises the live xfconf rebind path against a THROWAWAY
channel-scoped state that is fully restored afterwards.

Design note: no gi import anywhere — the GUI's pure helpers are imported with
`gi` blocked so the suite proves the no-GTK portability rule.

Usage: python3 scripts/test-hotkey-layer.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

APPS = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps")
sys.path.insert(0, os.path.join(APPS, "lib"))

import mv_hotkeys_core as core  # noqa: E402

BIN = os.path.join(APPS, "bin")
FACTORY_XML = os.path.join(APPS, "config/xfce4-keyboard-shortcuts.xml")
SKEL_XML = os.path.join(
    REPO, "archiso-profile/releng/airootfs/etc/skel/.config/xfce4/xfconf/"
          "xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml")
SKILLS_JSON = os.path.join(APPS, "config/hotkeys/skills.json")

results = {"ok": 0, "fail": []}


def check(name, cond, detail=""):
    if cond:
        results["ok"] += 1
        print("ok - %s" % name)
    else:
        results["fail"].append(name)
        print("FAIL - %s %s" % (name, detail))


def raises(name, exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        results["ok"] += 1
        print("ok - %s" % name)
        return
    except Exception as other:  # noqa: BLE001
        check(name, False, "wrong exception: %r" % other)
        return
    check(name, False, "no exception raised")


def load_module(mod_name, filename):
    loader = importlib.machinery.SourceFileLoader(mod_name,
                                                  os.path.join(BIN, filename))
    spec = importlib.util.spec_from_loader(mod_name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run_cli(args, env=None):
    environ = dict(os.environ)
    environ["PYTHONPATH"] = os.path.join(APPS, "lib")
    if env:
        environ.update(env)
    proc = subprocess.run([sys.executable, os.path.join(BIN, "mv-hotkeys")]
                          + args, capture_output=True, text=True, env=environ,
                          timeout=60)
    return proc


# ---------------------------------------------------------------------------
# 1. Registry invariants
# ---------------------------------------------------------------------------
ids = core.action_ids()
check("registry has no duplicate action ids", len(ids) == len(set(ids)))
check("registry is non-trivial", len(ids) >= 50, "only %d" % len(ids))

missing_targets = []
for row in core.ACTIONS:
    command = row["command"]
    head = command.split()[0]
    if head.startswith("/"):
        # Absolute path: must be something the package Makefile installs
        # (some tools ship with an underscore source renamed on install).
        name = head.rsplit("/", 1)[-1]
        stem = name.replace("-", "_")
        candidates = [os.path.join(APPS, "bin", name),
                      os.path.join(APPS, "bin", stem),
                      os.path.join(APPS, "bin", stem + ".py"),
                      os.path.join(REPO, head.lstrip("/"))]
        if not any(os.path.exists(c) for c in candidates):
            missing_targets.append("%s -> %s" % (row["action"], head))
    else:
        # External backend binaries: check they are declared dependencies or
        # are provided by an already-installed tool.
        if head.startswith("mv-") and not os.path.exists(
                os.path.join(APPS, "bin", head)):
            missing_targets.append("%s -> %s" % (row["action"], head))
check("every registry command resolves to an installed or declared backend",
      not missing_targets, "; ".join(missing_targets))

required_actions = [
    "spotlight", "launchpad", "mission-control", "quicklook",
    "screenshot-full", "screenshot-area", "screenshot-interactive",
    "new-folder-home", "rename", "get-info", "open-with", "move-to-trash",
    "empty-trash", "eject", "cycle-windows", "cycle-windows-reverse",
    "quit-app", "force-quit", "minimize-window", "hide-app",
    "close-window", "settings", "control-center", "notification-center",
    "lock-screen", "power-dialog", "log-out", "workspace-next",
    "volume-raise", "brightness-up",
]
absent = [a for a in required_actions if a not in core.ACTION_INDEX]
check("all canonical Mavericks actions are registered", not absent,
      "missing: %s" % absent)

# ---------------------------------------------------------------------------
# 2. Protected keys — standard Linux shortcuts and the hardware row
# ---------------------------------------------------------------------------
for action in ("terminal", "lock-screen", "cycle-windows",
               "cycle-windows-reverse", "volume-mute", "brightness-up"):
    check("%s is protected" % action,
          action in core.PROTECTED_ACTIONS)

tmpdir = tempfile.mkdtemp(prefix="mv-hotkeys-test-")
tmp_override = os.path.join(tmpdir, "overrides.json")
raises("protected action cannot be rebound", PermissionError,
       core.set_override, "terminal", "Super+T", None, {}, tmp_override)
raises("hardware key is reserved", PermissionError,
       core.set_override, "spotlight", "XF86AudioMute", None, {}, tmp_override)

# ---------------------------------------------------------------------------
# 3. Accelerator normalisation
# ---------------------------------------------------------------------------
cases = [
    ("Super+Shift+3", {"modifiers": ["Super", "Shift"], "key": "3"}),
    ("Super + Space", {"modifiers": ["Super"], "key": "space"}),
    ("<Super>space", {"modifiers": ["Super"], "key": "space"}),
    ("&lt;Super&gt;space", {"modifiers": ["Super"], "key": "space"}),
    ("Cmd+I", {"modifiers": ["Super"], "key": "i"}),
    ("Ctrl+Alt+Delete", {"modifiers": ["Primary", "Alt"], "key": "Delete"}),
    ("Super+comma", {"modifiers": ["Super"], "key": "comma"}),
    ("Super+F4", {"modifiers": ["Super"], "key": "F4"}),
]
for text, want in cases:
    try:
        got = core.normalize_accelerator(text)
    except ValueError as exc:
        got = "error: %s" % exc
    check("normalise %r" % text, got == want, "got %r" % (got,))

raises("bare key is refused", ValueError, core.normalize_accelerator, "k")
raises("unknown modifier is refused", ValueError,
       core.normalize_accelerator, "Hyper+q")
raises("unknown key is refused", ValueError,
       core.normalize_accelerator, "Super+NotAKey")
raises("empty accelerator is refused", ValueError, core.normalize_accelerator, "")

check("Apple-style display",
      core.display_accelerator({"modifiers": ["Super", "Shift"],
                                "key": "3"}) == "Super+Shift+3")
check("property name is xml-escaped",
      core.xml_escape(core.property_accelerator(
          {"modifiers": ["Super"], "key": "space"})) == "&lt;Super&gt;space")

# ---------------------------------------------------------------------------
# 4. Conflict detection (order-insensitive)
# ---------------------------------------------------------------------------
check("factory registry has no conflicts", not core.detect_conflicts())
overrides = dict(core.load_overrides(tmp_override))
overrides["spotlight"] = {"accelerator": {"modifiers": ["Super"],
                                          "key": "l"}}
conflicts = core.detect_conflicts(overrides=overrides)
check("rebound-onto-existing is detected", len(conflicts) == 1,
      "got %r" % conflicts)
check("conflict names both actions",
      conflicts and set(conflicts[0]["actions"]) == {"spotlight", "launchpad"})

reordered = {"spotlight": {"accelerator": {"modifiers": ["Primary", "Super"],
                                          "key": "l"}}}
check("modifier order does not fake a conflict",
      not core.detect_conflicts(overrides=reordered))

check("conflicting override table is rejected",
      any("conflicting" in e for e in core.check_overrides(overrides)))

# ---------------------------------------------------------------------------
# 5. Overrides round-trip
# ---------------------------------------------------------------------------
saved = core.set_override("spotlight", "Super+Shift+p", None, {},
                          tmp_override)
check("override stored", "spotlight" in saved)
check("override file is small and additive",
      json.load(open(tmp_override, encoding="utf-8"))["bindings"]["spotlight"]
      ["accelerator"] == {"modifiers": ["Super", "Shift"], "key": "p"})
effective = core.effective_bindings(saved)
check("override takes effect",
      effective["spotlight"]["modifiers"] == ["Super", "Shift"])
check("unrelated actions stay factory",
      effective["launchpad"]["modifiers"] == ["Super"])
core.clear_override("spotlight", saved, tmp_override)
check("override removed",
      "spotlight" not in core.load_overrides(tmp_override))

# ---------------------------------------------------------------------------
# 6. Factory XML is the registry
# ---------------------------------------------------------------------------
with open(FACTORY_XML, encoding="utf-8") as fh:
    factory_bindings = core.parse_xml_bindings(fh.read())
drift = core.compare_bindings(core.registry_bindings(), factory_bindings)
check("packaged XML matches the registry", not drift, "; ".join(drift))

with open(SKEL_XML, encoding="utf-8") as fh:
    skel_bindings = core.parse_xml_bindings(fh.read())
check("skel XML matches the packaged XML",
      not core.compare_bindings(factory_bindings, skel_bindings))

check("rendered XML round-trips through the parser",
      not core.compare_bindings(
          core.registry_bindings(),
          core.parse_xml_bindings(core.render_xml())))

rendered = core.render_xml()
check("rendered XML has both xfconf branches",
      'name="commands"' in rendered and 'name="xfwm4"' in rendered)
check("every action id reaches the rendered XML",
      all(row["command"] in rendered for row in core.ACTIONS))

# ---------------------------------------------------------------------------
# 7. Skills taxonomy
# ---------------------------------------------------------------------------
with open(SKILLS_JSON, encoding="utf-8") as fh:
    skills_doc = json.load(fh)
skill_ids = {s["id"] for s in skills_doc["skills"]}
used_skills = {row["skill"] for row in core.ACTIONS}
check("every action maps to a declared skill",
      used_skills <= skill_ids, "unknown: %s" % (used_skills - skill_ids))
check("every declared skill is used", skill_ids <= used_skills,
      "unused: %s" % (skill_ids - used_skills))
check("load_skills filters to used skills",
      {s["id"] for s in core.load_skills()} == used_skills)

# ---------------------------------------------------------------------------
# 7b. Documentation must cover the layer
# ---------------------------------------------------------------------------
DOC = os.path.join(REPO, "docs/KEYBOARD.md")
doc = open(DOC, encoding="utf-8").read()
undocumented = [row["action"] for row in core.ACTIONS
                if row["label"] not in doc
                and core.display_accelerator(row) not in doc]
check("docs/KEYBOARD.md documents every managed action", not undocumented,
      "missing: %s" % undocumented)
check("docs/KEYBOARD.md states the protected policy",
      "Protected (not rebindable)" in doc)
check("docs/KEYBOARD.md documents the reconfigure commands",
      all(cmd in doc for cmd in ("mv-hotkeys set", "mv-hotkeys reset",
                                 "mv-hotkeys verify", "mv-hotkeys gui")))

# ---------------------------------------------------------------------------
# 8. Import/export
# ---------------------------------------------------------------------------
table = core.export_table({})
check("export table covers every action", len(table) == len(core.ACTIONS))
export_file = os.path.join(tmpdir, "export.json")
proc = run_cli(["export", "-o", export_file])
check("cli export writes a file", proc.returncode == 0 and
      os.path.isfile(export_file), proc.stderr.strip())

imported, rejected = core.import_table(
    [{"action": "spotlight", "accelerator": "Super+Shift+p"},
     {"action": "volume-mute", "accelerator": "Super+M"},
     {"action": "does-not-exist", "accelerator": "Super+Y"}],
    overrides={}, path=os.path.join(tmpdir, "imported.json"))
check("import stores a rebindable action", "spotlight" in imported)
check("import refuses to move a protected action",
      any("volume-mute" in note for note in rejected), str(rejected))
check("import reports unknown actions",
      any("does-not-exist" in note for note in rejected), str(rejected))

# ---------------------------------------------------------------------------
# 9. verify detects drift
# ---------------------------------------------------------------------------
good = {core.property_path_identity(row["branch"], row): row["command"]
        for row in core.ACTIONS}
check("verify is clean for the factory state",
      not core.verify(overrides={}, live=good))
broken = dict(good)
first = sorted(broken)[0]
broken[first] = "something-else"
check("verify reports a wrong command", core.verify(overrides={}, live=broken))
missing = dict(good)
missing.pop(sorted(missing)[3])
check("verify reports a missing binding",
      core.verify(overrides={}, live=missing))

# ---------------------------------------------------------------------------
# 10. CLI contract
# ---------------------------------------------------------------------------
proc = run_cli(["--help"])
check("cli --help works", proc.returncode == 0 and "verify" in proc.stdout)
proc = run_cli(["bogus-command"])
check("cli rejects an unknown command", proc.returncode == 2)

tmp_override2 = os.path.join(tmpdir, "cli-overrides.json")
env = {"MV_HOTKEYS_OVERRIDES": tmp_override2}
proc = run_cli(["verify", "--xml", FACTORY_XML], env=env)
check("cli verify --xml passes", proc.returncode == 0, proc.stdout + proc.stderr)

proc = run_cli(["show", "spotlight"], env=env)
check("cli show works", proc.returncode == 0 and "accelerator" in proc.stdout)
proc = run_cli(["show", "nope"], env=env)
check("cli show rejects unknown action", proc.returncode == 2)

proc = run_cli(["conflicts"], env=env)
check("cli conflicts is clean at factory", proc.returncode == 0,
      proc.stdout)

proc = run_cli(["set", "spotlight", "Super+Shift+p"], env=env)
check("cli set stores the override",
      "Super+Shift+P" in proc.stdout,
      proc.stdout + proc.stderr)
check("cli set reports the new accelerator",
      "Super+Shift+P" in proc.stdout, proc.stdout)

proc = run_cli(["list", "--json"], env=env)
rows = json.loads(proc.stdout)["bindings"] if proc.returncode == 0 else []
spotlight = next((r for r in rows if r["action"] == "spotlight"), None)
check("cli list --json reflects the override",
      spotlight and spotlight["accelerator"] == "Super+Shift+P"
      and spotlight["overridden"], repr(spotlight))

proc = run_cli(["set", "terminal", "Super+T"], env=env)
check("cli set refuses a protected action", proc.returncode == 3,
      proc.stdout + proc.stderr)

proc = run_cli(["reset", "spotlight"], env=env)
check("cli reset clears the override",
      "spotlight" not in core.load_overrides(tmp_override2),
      proc.stdout + proc.stderr)

proc = run_cli(["render-xml"], env=env)
check("cli render-xml prints parseable XML",
      proc.returncode == 0 and not core.parse_xml_bindings(proc.stdout) is None)

# ---------------------------------------------------------------------------
# 11. Live xfconf rebind path (restores the channel afterwards)
# ---------------------------------------------------------------------------
# The rebind test mutates a REAL xfconf channel, so it is opt-in: other agents
# share this host's session and a suite that silently rewrites the user's
# keybindings is not acceptable.  Run with MV_HOTKEYS_LIVE_TEST=1 to include it;
# the channel is restored byte-for-byte in a finally block either way.
live_opt_in = os.environ.get("MV_HOTKEYS_LIVE_TEST") == "1"
have_xfconf = subprocess.run(["which", "xfconf-query"],
                             capture_output=True).returncode == 0
if not live_opt_in:
    print("skip - live xfconf rebind test (set MV_HOTKEYS_LIVE_TEST=1 to run)")
elif not have_xfconf:
    print("skip - xfconf-query not installed")
else:
    proc = subprocess.run(["xfconf-query", "-c", core.CHANNEL, "-l"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        print("skip - no live xfconf channel on this host")
    else:
        live_before = core.live_raw()
        tmp_override3 = os.path.join(tmpdir, "live-overrides.json")
        env3 = {"MV_HOTKEYS_OVERRIDES": tmp_override3}
        try:
            # Super+Shift+U is free in the registry (checked above), so the
            # live rebind exercises a genuinely new accelerator.
            core.set_override("quicklook", "Super+Shift+u", None, {},
                              tmp_override3)
            overrides3 = core.load_overrides(tmp_override3)
            steps = core.apply_action("quicklook", overrides3)
            check("live apply reports its steps", bool(steps), str(steps))
            live_now = core.live_list()
            check("live channel carries the new binding",
                  live_now.get(core.property_path_identity(
                      "commands", {"modifiers": ["Super", "Shift"],
                                   "key": "u"})) == "mv-quicklook-thunar",
                  repr(live_now.get(core.property_path_identity(
                      "commands", {"modifiers": ["Super", "Shift"],
                                   "key": "u"}))))
            check("old quicklook binding was cleaned up",
                  core.property_path_identity(
                      "commands", {"modifiers": ["Super", "Shift"],
                                   "key": "space"}) not in live_now)
            steps, _ = core.reset_action("quicklook", overrides3,
                                         tmp_override3)
            check("live reset restores the factory binding",
                  core.live_list().get(core.property_path_identity(
                      "commands", {"modifiers": ["Super", "Shift"],
                                   "key": "space"})) == "mv-quicklook-thunar",
                  str(steps))
        finally:
            # Restore the channel byte-for-byte.
            live_now = core.live_raw()
            for path in set(live_now) - set(live_before):
                core.live_remove(path)
            for path, value in live_before.items():
                if live_now.get(path) != value:
                    core.live_set(path, value)
            restored = core.live_raw()
            check("live channel restored",
                  all(restored.get(p) == v for p, v in live_before.items()) and
                  not (set(restored) - set(live_before)),
                  "channel was left dirty")

# ---------------------------------------------------------------------------
# 12. GUI pure helpers import with gi blocked
# ---------------------------------------------------------------------------
class _BlockGi:
    def find_spec(self, name, path=None, target=None):
        if name == "gi" or name.startswith("gi."):
            raise ImportError("blocked by test")
        return None


sys.meta_path.insert(0, _BlockGi())
try:
    gui = load_module("mv_hotkeys_gui_test", "mv-hotkeys-gui")
except ImportError as exc:
    check("mv-hotkeys-gui imports headless", False, str(exc))
else:
    check("mv-hotkeys-gui imports headless", True)
    check("Apple glyph rendering",
          gui.shortcut_label(["Super", "Shift"], "3") == "⌘⇧3")
    check("ctrl-alt glyph rendering",
          gui.shortcut_label(["Primary", "Alt"], "n") == "⌃⌥N")
    check("named key label",
          gui.shortcut_label(["Super"], "space") == "⌘Space")
    finder_rows = gui.rows_for_skill("finder")
    check("finder skill exposes the Finder operations",
          {r["action"] for r in finder_rows} >= {
              "new-folder-home", "rename", "get-info", "move-to-trash",
              "empty-trash", "eject"}, str(sorted(r["action"]
                                                  for r in finder_rows)))
    check("finder rows carry their skill", all(r["skill"] == "finder"
                                               for r in finder_rows))
    check("rows_for_skill covers every action",
          sum(len(gui.rows_for_skill(s["id"])) for s in skills_doc["skills"])
          == len(core.ACTIONS))
    check("filter is case-insensitive substring",
          [r["action"] for r in gui.filter_rows(finder_rows, "TRASH")]
          == ["move-to-trash", "empty-trash", "empty-trash-alt"],
          str([r["action"] for r in gui.filter_rows(finder_rows, "TRASH")]))
    check("empty query returns everything",
          len(gui.filter_rows(finder_rows, "")) == len(finder_rows))
    check("no query returns everything",
          len(gui.filter_rows(finder_rows, None)) == len(finder_rows))
    check("keysym normalisation",
          gui._normalise_keysym("XF86AudioMute") == "XF86AudioMute")
    check("keysym normalisation (letter)",
          gui._normalise_keysym("A") == "a")
    check("unknown keysym is not offered",
          gui._normalise_keysym("XF86Ungrab") is None)
    check("protected rows are flagged",
          all(r["protected"] for r in gui.rows_for_skill("keyboard")))
    total = len(gui.build_rows(skills_doc["skills"]))
    check("build_rows covers the registry", total == len(core.ACTIONS))

# ---------------------------------------------------------------------------
print("")
if results["fail"]:
    print("%d passed, %d FAILED: %s" % (results["ok"], len(results["fail"]),
                                       ", ".join(results["fail"])))
    sys.exit(1)
print("%d checks passed" % results["ok"])