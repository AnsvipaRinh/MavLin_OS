#!/usr/bin/env python3
"""Headless tests for mv-settings (Mavericks System Settings shell).

Since the 2026-10-06 System Settings P0 rework the app is a real
preference shell (icon grid + embedded native panes + honest unavailable
states), so this suite pins:

  * the pure layer imports with `gi` blocked (headless contract);
  * PAGES as 4-tuples (label, icon, argv|None, pane|None), unique labels;
  * §6/§13.6 pane coverage: every Mavericks settings surface must have a
    pane entry (native or explicit external), including the panes added
    in the rework (Dock, Mission Control, Trackpad, Security & Privacy,
    Sharing, Desktop & Screen Saver);
  * routing policy page_action (pane > launch > honest unavailable);
  * the pane-helper parsers/clamps (workspaces, battery, timedate,
    locale.conf, touchpad detection, service_enabled);
  * the Dock control table against the plank GSettings schema vocabulary;
  * icon-name existence against the Mavericks theme source.

Usage: python3 scripts/test-mv-settings.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
from types import SimpleNamespace

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless app-suite: arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED instead of popping a
# window on the host (WSLg) desktop.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

BIN = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin")


def ok(name):
    ok.count += 1
    print("ok - %s" % name)
ok.count = 0


def bad(name, detail=""):
    bad.failures.append((name, detail))
    print("FAIL - %s %s" % (name, detail))
bad.failures = []


def check(name, cond, detail=""):
    ok(name) if cond else bad(name, detail)


class _BlockGi:
    def find_spec(self, name, path=None, target=None):
        if name == "gi" or name.startswith("gi."):
            raise ImportError("blocked by test: %s" % name)
        return None


def load(mod_name, filename, block_gi=True):
    if block_gi:
        sys.meta_path.insert(0, _BlockGi())
    try:
        path = os.path.join(BIN, filename)
        loader = importlib.machinery.SourceFileLoader(mod_name, path)
        spec = importlib.util.spec_from_loader(mod_name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        if block_gi:
            sys.meta_path.remove(sys.meta_path[0])


# Frozen vocabulary of the plank 0.11 dock schema (validated against the
# installed schema by scripts/test-dock-plank.py; frozen here so this
# suite stays headless and offline).
PLANK_DOCK_SCHEMA_KEYS = {
    "alignment", "auto-pinning", "current-workspace-only", "dock-items",
    "hide-delay", "hide-mode", "icon-size", "items-alignment", "lock-items",
    "monitor", "offset", "pinned-only", "position", "pressure-reveal",
    "show-dock-item", "theme", "tooltips-enabled", "unhide-delay",
    "zoom-enabled", "zoom-percent",
}
PLANK_HIDE_MODE_NICKS = {"intelligent", "auto", "none", "dodge-maximized",
                         "windows", "dodge-active", "dodge-all"}
PLANK_POSITION_NICKS = {"left", "right", "top", "bottom"}
PLANK_ALIGNMENT_NICKS = {"start", "center", "end", "panel"}

# §6/§13.6: the settings surfaces the Mavericks desktop must expose.
REQUIRED_LABELS = {
    "General", "Appearance", "Desktop & Screen Saver", "Dock",
    "Mission Control", "Language & Region", "Date & Time",
    "Security & Privacy", "Notifications", "Displays", "Energy Saver",
    "Keyboard", "Keyboard Shortcuts", "Mouse", "Trackpad", "Sound",
    "Network", "Bluetooth", "Sharing", "Users", "About",
}


def main():
    try:
        m = load("mv_settings", "mv-settings")
        ok("mv-settings imports headless (gi blocked)")
    except Exception as e:
        bad("mv-settings imports headless (gi blocked)", repr(e))
        print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
        return 1

    # --- PAGES table contract ---
    rows_ok = all(len(r) == 4 and isinstance(r[0], str) and isinstance(r[1], str)
                  and (r[2] is None or (isinstance(r[2], list) and r[2]
                      and all(isinstance(x, str) for x in r[2])))
                  and (r[3] is None or isinstance(r[3], str))
                  for r in m.PAGES)
    check("PAGES: (label, icon, argv|None, pane|None) shape", rows_ok,
          str([r for r in m.PAGES if len(r) != 4][:2]))
    labels = [r[0] for r in m.PAGES]
    check("PAGES: labels unique", len(labels) == len(set(labels)),
          "dupes=%s" % [l for l in set(labels) if labels.count(l) > 1])
    check("PAGES: non-trivial table", len(m.PAGES) >= 20, str(len(m.PAGES)))

    missing_surfaces = REQUIRED_LABELS - set(labels)
    check("PAGES: all §6 settings surfaces present", not missing_surfaces,
          "missing=%s" % sorted(missing_surfaces))

    # The About page must chain to mv-about (the app we tested separately).
    about = [r for r in m.PAGES if r[0] == "About"]
    check("PAGES: About -> mv-about", bool(about) and about[0][2] == ["mv-about"],
          str(about))

    # Keyboard Shortcuts must keep chaining to mv-hotkeys-gui (integration
    # promised elsewhere; do not break it).
    ks = [r for r in m.PAGES if r[0] == "Keyboard Shortcuts"]
    check("PAGES: Keyboard Shortcuts -> mv-hotkeys-gui",
          bool(ks) and ks[0][2] == ["mv-hotkeys-gui"], str(ks))

    pane_keys = {r[3] for r in m.PAGES if r[3]}
    check("PAGES: every pane key is a known native pane",
          pane_keys <= set(m.NATIVE_PANES),
          "unknown=%s" % sorted(pane_keys - set(m.NATIVE_PANES)))
    check("PAGES: every native pane (except 'unavailable') is reachable",
          set(m.NATIVE_PANES) - {"unavailable"} == pane_keys,
          "unreachable=%s" % sorted(set(m.NATIVE_PANES) - {"unavailable"} - pane_keys))
    check("PAGES: native panes are the majority surface",
          len(pane_keys) >= 10, str(len(pane_keys)))

    # --- pure helpers: RandR display parsing ---
    sample_xrandr = """Screen 0: minimum 320 x 200, current 3200 x 1080, maximum 8192 x 8192
DP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 344mm x 193mm
   1920x1080 60.00*+ 59.94
   1280x720 60.00
HDMI-1 connected 1280x1024+1920+0 (normal left inverted right x axis y axis) 376mm x 301mm
   1280x1024 60.02*+
"""
    displays_parsed = m.parse_xrandr(sample_xrandr)
    check("randr: connected outputs parsed", len(displays_parsed) == 2)
    check("randr: primary flag parsed", displays_parsed[0]["primary"] is True)
    check("randr: current mode parsed", displays_parsed[0]["current"] == "1920x1080")
    check("randr: position parsed", displays_parsed[1]["position"] == (1920, 0))
    check("randr: advertised modes parsed", [x["mode"] for x in displays_parsed[0]["modes"]] == ["1920x1080", "1280x720"])
    check("randr: current rate marker parsed", displays_parsed[0]["modes"][0]["current"] is True)

    # --- page_is_available ---
    check("available: None cmd -> False", m.page_is_available(None) is False)
    check("available: real tool -> True", m.page_is_available(["sh"]) is True)
    check("available: fake tool -> False",
          m.page_is_available(["definitely-not-a-real-binary-42"]) is False)
    check("available: empty list -> False", m.page_is_available([]) is False)

    # --- page_action routing policy ---
    general = [r for r in m.PAGES if r[0] == "General"][0]
    check("route: native pane wins over everything",
          m.page_action(general) == ("pane", "general"))
    displays = [r for r in m.PAGES if r[0] == "Displays"][0]
    check("route: Displays uses native pane",
          displays[2] is None and displays[3] == "displays", str(displays))
    check("native pane registry: Displays is declared",
          "displays" in m.NATIVE_PANES)
    network = [r for r in m.PAGES if r[0] == "Network"][0]\n    sound = [r for r in m.PAGES if r[0] == "Sound"][0]
    check("route: Sound uses native pane",
          sound[2] is None and sound[3] == "sound", str(sound))
    check("native pane registry: Sound is declared",
          "sound" in m.NATIVE_PANES)

    check("route: Network uses native pane",
          network[2] is None and network[3] == "network", str(network))
    check("native pane registry: Network is declared",
          "network" in m.NATIVE_PANES)

    bt = [r for r in m.PAGES if r[0] == "Bluetooth"][0]
    fake = m.page_action(bt, tool_available=lambda cmd: False)
    check("route: missing tool -> honest unavailable",
          fake == ("unavailable", "blueman-manager"), str(fake))
    check("route: pane row with argv still routes to the pane",
          m.page_action([r for r in m.PAGES if r[0] == "Energy Saver"][0])[0]
          == "pane")

    # --- filter_pages search semantics ---
    check("filter: empty query -> all pages", len(m.filter_pages("")) == len(m.PAGES))
    res = m.filter_pages("network")
    check("filter: 'network' matches Network exactly",
          [r[0] for r in res] == ["Network"], str(res))
    res = m.filter_pages("dis")
    check("filter: case-insensitive substring ('dis' -> Displays)",
          set(r[0] for r in res) >= {"Displays"}, str(res))
    check("filter: nonsense -> empty", m.filter_pages("zzq-no-such-page") == [])

    # --- GUI factory stays lazy ---
    sys.meta_path.insert(0, _BlockGi())
    try:
        m.build_settings_class()
        bad("build_settings_class requires gi (lazy)", "worked without gi?!")
    except ImportError:
        ok("build_settings_class requires gi (lazy)")
    finally:
        sys.meta_path.remove(sys.meta_path[0])

    # --- pure pane helpers: Mission Control ---
    check("workspaces: clamp high", m.clamp_workspaces(99) == m.WORKSPACE_MAX)
    check("workspaces: clamp low", m.clamp_workspaces(0) == m.WORKSPACE_MIN)
    check("workspaces: clamp passthrough", m.clamp_workspaces(7) == 7)
    check("workspaces: clamp garbage -> min",
          m.clamp_workspaces("banana") == m.WORKSPACE_MIN)
    check("workspaces: range is the Mavericks 1..16",
          (m.WORKSPACE_MIN, m.WORKSPACE_MAX) == (1, 16))

    # --- pure pane helpers: Dock control table ---
    check("dock: keys unique",
          len(m.DOCK_USER_KEYS) == len(m.DOCK_CONTROLS))
    check("dock: every control key exists in the plank schema",
          m.DOCK_USER_KEYS <= PLANK_DOCK_SCHEMA_KEYS,
          "unknown=%s" % sorted(m.DOCK_USER_KEYS - PLANK_DOCK_SCHEMA_KEYS))
    kinds_ok = all(c[2] in ("range", "bool", "enum") for c in m.DOCK_CONTROLS)
    check("dock: control kinds valid", kinds_ok)
    enums = {c[0]: c[3] for c in m.DOCK_CONTROLS if c[2] == "enum"}
    check("dock: hide-mode nicks are plank nicks",
          {n for n, _l in enums["hide-mode"]} <= PLANK_HIDE_MODE_NICKS)
    check("dock: position nicks are plank nicks",
          {n for n, _l in enums["position"]} <= PLANK_POSITION_NICKS)
    check("dock: alignment nicks are plank nicks",
          {n for n, _l in enums["alignment"]} <= PLANK_ALIGNMENT_NICKS)
    ranges_ok = all(c[3][0] < c[3][1]
                    for c in m.DOCK_CONTROLS if c[2] == "range")
    check("dock: range controls have min < max", ranges_ok)
    # the Mavericks look keys stay owned by mv-dock-config, not user-editable
    check("dock: theme/behaviour keys not exposed",
          not (m.DOCK_USER_KEYS & {"theme", "auto-pinning", "pinned-only",
                                   "show-dock-item", "hide-delay",
                                   "unhide-delay", "lock-items"}))

    # --- pure pane helpers: Energy ---
    check("energy: blank keys sane",
          all(lo < hi and lo >= 0
              for _k, _t, lo, hi in m.ENERGY_BLANK_KEYS))
    check("energy: four display-sleep rows",
          len(m.ENERGY_BLANK_KEYS) == 4)

    # --- pure pane helpers: battery ---
    check("battery: absent -> honest 'No battery present'",
          m.format_battery({}) == "No battery present")
    check("battery: not present -> honest",
          m.format_battery({"IsPresent": False}) == "No battery present")
    check("battery: percentage rounds",
          m.format_battery({"IsPresent": True, "Percentage": 87.4})
          == "Battery: 87%")
    check("battery: charging suffix",
          m.format_battery({"IsPresent": True, "Percentage": 42.0,
                            "State": 2}) == "Battery: 42% (charging)")
    check("battery: discharging suffix",
          m.format_battery({"IsPresent": True, "Percentage": 10.0,
                            "State": 1}) == "Battery: 10% (discharging)")
    check("battery: unknown level stays honest",
          m.format_battery({"IsPresent": True})
          == "Battery present (charge level unknown)")

    # --- pure pane helpers: Date & Time ---
    tz, ntp, synced, clock = m.parse_timedate(
        {"Timezone": "Europe/Warsaw", "NTP": False, "NTPSynchronized": True,
         "TimeUSec": 1760000000000000})
    check("timedate: timezone passthrough", tz == "Europe/Warsaw")
    check("timedate: ntp flags decoded", (ntp, synced) == (False, True))
    check("timedate: clock rendered", clock != "clock unavailable")
    tz2, ntp2, _s2, clock2 = m.parse_timedate({})
    check("timedate: empty props stay honest",
          (tz2, ntp2, clock2) == ("unknown", False, "clock unavailable"))

    # --- pure pane helpers: Language & Region ---
    parsed = m.parse_locale_conf(
        '# comment\nLANG="en_US.UTF-8"\nLC_TIME=pl_PL.UTF-8\nGARBAGE\n')
    check("locale: assignments parsed with quotes stripped",
          parsed == {"LANG": "en_US.UTF-8", "LC_TIME": "pl_PL.UTF-8"},
          str(parsed))
    check("locale: empty text -> empty dict", m.parse_locale_conf("") == {})

    # --- pure pane helpers: Trackpad detection ---
    check("touchpad: detected by Name",
          m.detect_touchpad(
              'I: Bus=0011\nN: Name="Apple SPI Touchpad"\nP: Phys=x\n')
          is True)
    check("touchpad: detected by Phys",
          m.detect_touchpad(
              'I: Bus=0011\nN: Name="Lid Switch"\nP: Phys=i8042/serio1/input1 touchpad\n')
          is True)
    check("touchpad: mouse-only -> negative",
          m.detect_touchpad(
              'I: Bus=0003\nN: Name="Logitech USB Mouse"\nP: Phys=usb\n')
          is False)
    check("touchpad: empty -> negative", m.detect_touchpad("") is False)

    # --- pure pane helpers: service_enabled ---
    check("service: rc=0 -> enabled",
          m.service_enabled("sshd.service",
                            runner=lambda a: SimpleNamespace(returncode=0))
          is True)
    check("service: rc=1 -> disabled",
          m.service_enabled("sshd.service",
                            runner=lambda a: SimpleNamespace(returncode=1))
          is False)
    def _boom(a, **kw):
        raise FileNotFoundError("no systemctl")
    check("service: no systemctl -> unknown",
          m.service_enabled("sshd.service", runner=_boom) is None)

    # --- pure pane helpers: Users info ---
    user, home = m.current_user_home()
    check("users: returns non-empty user+home",
          bool(user) and bool(home) and home.startswith("/"))

    # --- icon-name audit vs our Mavericks theme source (hard assertion) ---
    icons_root = os.path.join(REPO, "packages/mavericks-theme/src/mavericks-theme/icons")
    if os.path.isdir(icons_root):
        theme_icons = set()
        for _dirpath, _dirs, files in os.walk(icons_root):
            for f in files:
                if f.endswith(".svg"):
                    theme_icons.add(f[:-4])
        missing = sorted({r[1] for r in m.PAGES} - theme_icons)
        check("PAGES: every icon exists in Mavericks theme", not missing,
              "missing=%s" % missing)
    else:
        print("skip - icon-name audit (theme source not found at %s)" % icons_root)

    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
