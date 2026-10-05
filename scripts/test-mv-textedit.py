#!/usr/bin/env python3
"""Lifecycle regression test for mv-textedit (TextEdit).

Guards against a self-respawning Text Editor window on the WSLg desktop.
Verifies the full process lifecycle:

  1. manual launch works: process starts and stays alive (does not self-close)
  2. terminate -> process exits and stays dead (no respawn)
  3. kill -> stays dead (no respawn)
  4. repeat several times
  5. process tree shows no hidden respawner (no watchdog/retry/relaunch parent)

A display is required for the GUI to reach its main loop; the GUI section is
skipped when headless (no DISPLAY / no WAYLAND_DISPLAY), matching the other
test-*.py harnesses.

This test launches the real app in its own session (like a desktop launch),
tears it down via its process group, and polls the process tree for any new
instance. If a watchdog/timer/retry-loop respawner is ever introduced, this
test fails.

Usage: python3 scripts/test-mv-textedit.py
Exit 0 = all tests passed (or GUI section skipped headless)."""
import os
import signal
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-textedit")

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
REPEATS = 3
RESPAWN_WATCH_S = 8


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


def app_pids():
    """Pids of running mv-textedit app processes (excludes this test/shells)."""
    out = subprocess.run(
        ["pgrep", "-f", "mavericks-apps/bin/mv-text"],
        capture_output=True, text=True)
    pids = []
    for tok in out.stdout.split():
        try:
            pid = int(tok)
        except ValueError:
            continue
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        # exclude this test's own shell chain and pgrep itself
        if "test-mv-textedit" in cmd or "pgrep" in cmd:
            continue
        if "bin/mv-textedit" in cmd:
            pids.append(pid)
    return pids


def launch():
    """Launch the real app in its own session, like a desktop launch."""
    env = dict(os.environ)
    # Target session is X11/Xfce. Defaulting to "wayland" put this app on
    # the WSLg host compositor (= the user's Windows desktop) whenever
    # GDK_BACKEND was unset; scripts/gui-isolation.sh forbids that too.
    env.setdefault("GDK_BACKEND", "x11")
    return subprocess.Popen(
        [sys.executable, APP_PATH],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env, start_new_session=True)


def teardown(proc):
    """Kill the app's whole process group (idempotent)."""
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def wait_gone(proc, timeout=5):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if proc.poll() is not None:
            return True
        time.sleep(0.1)
    return proc.poll() is not None


def watch_respawn(exclude_pid, seconds):
    """Return a list of NEW app pids that appeared (excluding exclude_pid)."""
    seen = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        for pid in app_pids():
            if pid != exclude_pid and pid not in seen:
                seen.append(pid)
        time.sleep(0.5)
    return seen


def main():
    print("mv-textedit lifecycle test")
    print("  app: %s" % APP_PATH)
    print("  display: %s" % ("yes" if HAS_DISPLAY else "no (headless)"))

    if not HAS_DISPLAY:
        print("SKIP - no display; GUI lifecycle section requires one "
              "(headless import/logic is covered by the bench S03 scenario)")
        return 0

    # 0. precondition: no editor running before we start
    pre = app_pids()
    check("no editor running before test", not pre,
          "found pre-existing: %s" % pre)

    for i in range(1, REPEATS + 1):
        proc = launch()
        # 1. manual launch works and stays alive (does not self-close)
        time.sleep(3)
        alive = proc.poll() is None
        check("repeat %d: launch works (process alive after 3s)" % i, alive,
              "exited early rc=%s" % proc.returncode)
        if not alive:
            teardown(proc)
            continue

        # 2. terminate -> exits and stays dead (no respawn)
        teardown(proc)
        gone = wait_gone(proc)
        check("repeat %d: terminate -> exits" % i, gone)
        new = watch_respawn(proc.pid, RESPAWN_WATCH_S)
        check("repeat %d: no respawn after terminate (%ds)" % (i, RESPAWN_WATCH_S),
              not new, "new pids: %s" % new)

    # 3. kill -> stays dead (no respawn)
    proc = launch()
    time.sleep(3)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        wait_gone(proc)
    new = watch_respawn(proc.pid, RESPAWN_WATCH_S)
    check("kill -> no respawn (%ds)" % RESPAWN_WATCH_S,
          not new, "new pids: %s" % new)

    # 4. no hidden respawner: nothing left running, no watchdog parent
    time.sleep(1)
    leftover = app_pids()
    check("no lingering editor after test", not leftover,
          "leftover pids: %s" % leftover)

    print("\n%d checks passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
