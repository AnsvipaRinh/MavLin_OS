#!/usr/bin/env python3
"""Headless tests for mv-power-ui.

- mock logind on a private bus (scripts/mock-logind.py): capability query,
  dbus execution plan, policy-denied state, action error path
- logind absent: systemctl fallback plan
- pure logic: Countdown, countdown_text, format_battery_line, action_state
- CLI --status with and without logind

Read-only: no real power actions are executed. execute_plan is tested only
with injected mocks; the mock logind records calls but performs nothing.

Usage:
  python3 scripts/test-mv-power-ui.py   (auto-spawns a private dbus-daemon)

Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-power-ui")
MOCK_PATH = os.path.join(REPO, "scripts/mock-logind.py")

FAILURES = []
PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print("ok - %s" % name)


def bad(name, detail=""):
    FAILURES.append((name, detail))
    print("FAIL - %s %s" % (name, detail))


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        bad(name, detail)


def ensure_bus():
    addr = os.environ.get("DBUS_SYSTEM_BUS_ADDRESS")
    if addr:
        return addr, None
    proc = subprocess.Popen(
        ["dbus-daemon", "--session", "--print-address=1", "--fork", "--nopidfile"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    addr = proc.stdout.readline().strip()
    return addr, proc


def start_mock(addr, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.Popen([sys.executable, MOCK_PATH, addr],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, env=env)
    line = proc.stdout.readline().strip()
    if line != "READY":
        proc.kill()
        raise RuntimeError("mock failed to start: %r" % line)
    return proc


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_power_ui", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_power_ui", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run_status_cli(addr):
    env = dict(os.environ)
    if addr:
        env["DBUS_SYSTEM_BUS_ADDRESS"] = addr
    return subprocess.run(
        [sys.executable, APP_PATH, "--status"],
        capture_output=True, text=True, timeout=30, env=env)


def main():
    addr, _bus_proc = ensure_bus()
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = addr
    mv = load_app()

    # ---------- pure logic ----------
    check("actions are the four Mavericks actions",
          set(mv.ACTIONS) == {"sleep", "restart", "shutdown", "logout"},
          repr(sorted(mv.ACTIONS)))

    finished = []
    cd = mv.Countdown(3, on_finish=lambda: finished.append(True),
                       on_tick=lambda s: None)
    ticks = 0
    while cd.tick():
        ticks += 1
    check("countdown ticks exactly to zero",
          ticks == 2 and cd.left == 0 and finished == [True],
          "ticks=%d left=%d finished=%r" % (ticks, cd.left, finished))

    finished = []
    cd = mv.Countdown(2, on_finish=lambda: finished.append(True))
    cd.cancel()
    cd.tick(); cd.tick()
    check("countdown cancel prevents finish", finished == [], repr(finished))

    check("countdown_text plural",
          mv.countdown_text("shutdown", 60) == "The computer will shut down in 60 seconds.",
          mv.countdown_text("shutdown", 60))
    check("countdown_text singular",
          mv.countdown_text("sleep", 1) == "The computer will go to sleep in 1 second.",
          mv.countdown_text("sleep", 1))
    check("countdown_text restart verb",
          "restart in 59 seconds" in mv.countdown_text("restart", 59),
          mv.countdown_text("restart", 59))

    check("battery line charging",
          mv.format_battery_line({"percentage": 87.0, "state": 1}) == "Battery: 87% (Charging)",
          mv.format_battery_line({"percentage": 87.0, "state": 1}))
    check("battery line discharging",
          mv.format_battery_line({"percentage": 42.5, "state": 2}) == "Battery: 42% (Discharging)",
          mv.format_battery_line({"percentage": 42.5, "state": 2}))
    check("battery line missing",
          mv.format_battery_line(None) == "Battery status unavailable",
          mv.format_battery_line(None))
    check("battery line unknown state",
          mv.format_battery_line({"percentage": 10.0, "state": 99}) == "Battery: 10% (Unknown)",
          mv.format_battery_line({"percentage": 10.0, "state": 99}))

    check("action_state available when caps yes",
          mv.action_state("sleep", {"sleep": "yes"}) == "available")
    check("action_state unavailable when caps no",
          mv.action_state("sleep", {"sleep": "no"}) == "unavailable")
    check("action_state available when caps challenge",
          mv.action_state("restart", {"restart": "challenge"}) == "available")
    check("action_state available on systemctl fallback",
          mv.action_state("shutdown", None) == "available")
    check("action_state logout always available",
          mv.action_state("logout", {"sleep": "no"}) == "available")

    # ---------- resolve_action: logind present ----------
    caps_yes = {"sleep": "yes", "restart": "yes", "shutdown": "yes"}
    kind, payload = mv.resolve_action("sleep", caps_yes)
    check("resolve sleep via logind", kind == "dbus" and payload == "Suspend",
          "%s %s" % (kind, payload))
    kind, payload = mv.resolve_action("restart", caps_yes)
    check("resolve restart via logind", kind == "dbus" and payload == "Reboot",
          "%s %s" % (kind, payload))
    kind, payload = mv.resolve_action("shutdown", caps_yes)
    check("resolve shutdown via logind", kind == "dbus" and payload == "PowerOff",
          "%s %s" % (kind, payload))
    kind, payload = mv.resolve_action("logout", caps_yes)
    check("resolve logout via xfce4-session-logout",
          kind == "logout" and payload == ["xfce4-session-logout", "--logout"],
          "%s %s" % (kind, payload))

    caps_no = {"sleep": "no", "restart": "yes", "shutdown": "yes"}
    kind, payload = mv.resolve_action("sleep", caps_no)
    check("resolve denied action unavailable",
          kind == "unavailable" and "not permitted" in payload,
          "%s %s" % (kind, payload))

    # ---------- resolve_action: logind absent ----------
    kind, payload = mv.resolve_action("sleep", None)
    check("fallback sleep systemctl", kind == "systemctl" and payload == ["systemctl", "suspend"],
          "%s %s" % (kind, payload))
    kind, payload = mv.resolve_action("restart", None)
    check("fallback restart systemctl", kind == "systemctl" and payload == ["systemctl", "reboot"],
          "%s %s" % (kind, payload))
    kind, payload = mv.resolve_action("shutdown", None)
    check("fallback shutdown systemctl", kind == "systemctl" and payload == ["systemctl", "poweroff"],
          "%s %s" % (kind, payload))
    kind, payload = mv.resolve_action("logout", None)
    check("logout plan independent of logind",
          kind == "logout" and payload == ["xfce4-session-logout", "--logout"],
          "%s %s" % (kind, payload))

    # ---------- execute_plan with injected mocks ----------
    calls = []
    orig_call = mv._system_bus_call
    orig_popen = mv.subprocess.Popen
    try:
        mv._system_bus_call = lambda *a, **k: calls.append(a[3]) or ()
        check("execute dbus plan success",
              mv.execute_plan(("dbus", "PowerOff")) is True and calls == ["PowerOff"],
              repr(calls))

        mv._system_bus_call = lambda *a, **k: None
        errs = []
        check("execute dbus plan failure reports error",
              mv.execute_plan(("dbus", "Suspend"), on_error=errs.append) is False
              and len(errs) == 1 and "Suspend" in errs[0],
              repr(errs))

        popen_calls = []
        mv.subprocess.Popen = lambda cmd, **k: popen_calls.append(cmd) or 0
        check("execute systemctl plan spawns command",
              mv.execute_plan(("systemctl", ["systemctl", "poweroff"])) is True
              and popen_calls == [["systemctl", "poweroff"]],
              repr(popen_calls))
        check("execute logout plan spawns command",
              mv.execute_plan(("logout", ["xfce4-session-logout", "--logout"])) is True
              and popen_calls[-1] == ["xfce4-session-logout", "--logout"],
              repr(popen_calls))

        errs = []
        check("execute unavailable plan reports reason",
              mv.execute_plan(("unavailable", "Shut Down is not permitted by the system policy"),
                              on_error=errs.append) is False
              and errs == ["Shut Down is not permitted by the system policy"],
              repr(errs))
    finally:
        mv._system_bus_call = orig_call
        mv.subprocess.Popen = orig_popen

    # ---------- live bus: logind absent ----------
    caps = mv.query_capabilities()
    check("query_capabilities None without logind", caps is None, repr(caps))
    batt = mv.query_battery()
    check("query_battery None without UPower", batt is None, repr(batt))

    # ---------- live bus: mock logind ----------
    mock = start_mock(addr, {"MOCK_LOGIND_CAN_SUSPEND": "no",
                             "MOCK_LOGIND_CAN_REBOOT": "challenge",
                             "MOCK_LOGIND_CAN_POWEROFF": "yes"})
    try:
        caps = mv.query_capabilities()
        check("query_capabilities reads mock values",
              caps == {"sleep": "no", "restart": "challenge", "shutdown": "yes"},
              repr(caps))
        kind, payload = mv.resolve_action("sleep", caps)
        check("mock-denied sleep unavailable",
              kind == "unavailable", "%s %s" % (kind, payload))
        kind, payload = mv.resolve_action("restart", caps)
        check("mock-challenge restart via logind",
              kind == "dbus" and payload == "Reboot", "%s %s" % (kind, payload))
    finally:
        mock.terminate()
        mock.wait(timeout=5)

    # ---------- live bus: mock logind action execution ----------
    with tempfile.NamedTemporaryFile(delete=False) as cf:
        calls_file = cf.name
    mock = start_mock(addr, {"MOCK_LOGIND_CALLS_FILE": calls_file})
    try:
        caps = mv.query_capabilities()
        check("mock default caps all yes",
              caps == {"sleep": "yes", "restart": "yes", "shutdown": "yes"},
              repr(caps))
        check("execute PowerOff via mock logind",
              mv.execute_plan(mv.resolve_action("shutdown", caps)) is True)
        with open(calls_file) as fh:
            recorded = fh.read().split()
        check("mock logind recorded PowerOff", recorded == ["PowerOff"], repr(recorded))
    finally:
        mock.terminate()
        mock.wait(timeout=5)
        os.unlink(calls_file)

    # ---------- live bus: mock logind action failure ----------
    mock = start_mock(addr, {"MOCK_LOGIND_FAIL_ACTIONS": "1"})
    try:
        caps = mv.query_capabilities()
        errs = []
        check("execute failing action reports error",
              mv.execute_plan(mv.resolve_action("restart", caps),
                              on_error=errs.append) is False and len(errs) == 1,
              repr(errs))
    finally:
        mock.terminate()
        mock.wait(timeout=5)

    # ---------- CLI --status ----------
    r = run_status_cli(None)
    check("--status without logind exits 0", r.returncode == 0, r.stderr[-200:])
    check("--status reports logind unavailable",
          "logind: unavailable" in r.stdout, r.stdout)
    check("--status reports battery line",
          "Battery" in r.stdout, r.stdout)

    mock = start_mock(addr)
    try:
        r = run_status_cli(addr)
        check("--status with mock exits 0", r.returncode == 0, r.stderr[-200:])
        check("--status reports CanPowerOff yes",
              "CanPowerOff: yes" in r.stdout, r.stdout)
        check("--status reports CanSuspend yes",
              "CanSuspend: yes" in r.stdout, r.stdout)
    finally:
        mock.terminate()
        mock.wait(timeout=5)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
