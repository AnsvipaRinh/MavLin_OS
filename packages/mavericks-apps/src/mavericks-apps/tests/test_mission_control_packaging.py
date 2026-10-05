#!/usr/bin/env python3
"""Packaging regression tests for Mission Control helpers (issue #80).

Guards the mavericks-apps install manifest:
1. every mv-mc-* / mv-workspace-count / mv-mission-control executable that
   exists in bin/ must appear in the Makefile install list;
2. every helper referenced by Mission Control scripts (run_helper() calls,
   shutil.which() probes) must be installed;
3. lib/mission_control.py + lib/mission_control_thumbnail.py must be
   installed to share/mavericks-apps (mv-mc-overview imports them from
   there on an installed system);
4. when make + cc are available, a real DESTDIR install must place every
   helper at /usr/bin and every lib at /usr/share/mavericks-apps.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..")
BIN = os.path.join(SRC, "bin")
MAKEFILE = os.path.join(SRC, "Makefile")

# Mission Control family: everything the overview stack can invoke.
MC_EXECUTABLES = [
    "mv-mission-control",
    "mv-mc-overview",
    "mv-mc-gui",
    "mv-mc-grid",
    "mv-mc-thumbnail",
    "mv-mc-window-spaces",
    "mv-mc-activate-window",
    "mv-workspace-count",
]
MC_LIBS = ["mission_control.py", "mission_control_thumbnail.py"]


def _makefile_text():
    with open(MAKEFILE, "r", encoding="utf-8") as fh:
        return fh.read()


def _installed_bin_names(makefile_text):
    """Names the `for f in bin/...` list installs (basename per entry)."""
    m = re.search(r"for f in (bin/[^:]+?); do", makefile_text, re.S)
    if not m:
        return set()
    names = set()
    for entry in m.group(1).split():
        entry = entry.replace("\\\n", "").strip()
        if entry.startswith("bin/"):
            names.add(os.path.basename(entry))
    return names


def _referenced_helpers():
    """mv-mc-* / mv-workspace-count names referenced from MC scripts."""
    referenced = set()
    scripts = [os.path.join(BIN, name) for name in MC_EXECUTABLES]
    scripts = [p for p in scripts if os.path.exists(p)]
    for path in scripts:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for match in re.findall(r'run_helper\(\s*"([^"]+)"', text):
            referenced.add(match)
        for match in re.findall(r'shutil\.which\(\s*"([^"]+)"', text):
            referenced.add(match)
        for match in re.findall(r'"(/usr/bin/)(mv-[a-z0-9-]+)"', text):
            referenced.add(match[1])
    return referenced


def test_mc_executables_in_install_list():
    text = _makefile_text()
    installed = _installed_bin_names(text)
    missing = [name for name in MC_EXECUTABLES if name not in installed]
    assert not missing, f"Makefile install list misses MC helpers: {missing}"
    print("PASS: all MC executables are in the Makefile install list")


def test_referenced_helpers_in_install_list():
    text = _makefile_text()
    installed = _installed_bin_names(text)
    referenced = _referenced_helpers()
    assert referenced, "no helper references found — scanner is broken"
    missing = sorted(name for name in referenced if name not in installed)
    assert not missing, f"referenced helpers not installed: {missing}"
    print(f"PASS: all {len(referenced)} referenced helpers are installed")


def test_mc_libs_installed_to_share():
    text = _makefile_text()
    for lib in MC_LIBS:
        pattern = r"lib/" + re.escape(lib) + r'.*?\$\(PREFIX\)/share/mavericks-apps/' + re.escape(lib)
        assert re.search(pattern, text), f"{lib} not installed to share/mavericks-apps"
    print("PASS: mission_control libs are installed to share/mavericks-apps")


def test_bin_files_not_forgotten():
    """Any executable mv-* file in bin/ must be installed somewhere.

    Catches the issue #80 class of regression: a new helper is added to
    bin/ but never added to the install manifest.
    """
    text = _makefile_text()
    installed = _installed_bin_names(text)
    # Also count installs done via explicit `install -Dm755 bin/...` lines.
    for m in re.finditer(r"install -Dm755 bin/([\w.-]+)", text):
        installed.add(m.group(1))
    known_py = {"mv_launchpad_edit.py", "mv_desktop_cache.py", "mv_dialogs.py",
                "mv_calendar_eds.py", "mv_calendar.py"}  # loaded via fallback loaders
    missing = []
    for name in os.listdir(BIN):
        if not name.startswith("mv-") or name.endswith(".c"):
            continue
        if name in known_py:
            continue
        if not os.path.isfile(os.path.join(BIN, name)):
            continue
        if name not in installed:
            missing.append(name)
    missing = sorted(missing)
    assert not missing, f"mv-* helpers in bin/ missing from install: {missing}"
    print("PASS: every mv-* helper in bin/ is installed")


def test_destdir_install_manifest():
    """Real `make DESTDIR install` places every MC helper correctly."""
    if not (shutil.which("make") and shutil.which("cc")):
        print("SKIP: test_destdir_install_manifest (make/cc unavailable)")
        return
    destdir = tempfile.mkdtemp(prefix="mc-pkg-", dir=os.environ.get("TMPDIR", "/tmp"))
    try:
        proc = subprocess.run(
            ["make", "DESTDIR=" + destdir, "clean", "install"],
            cwd=SRC, capture_output=True, text=True, timeout=300,
        )
        assert proc.returncode == 0, f"make install failed: {proc.stderr[-500:]}"
        for name in MC_EXECUTABLES:
            path = os.path.join(destdir, "usr", "bin", name)
            assert os.path.isfile(path), f"not installed: /usr/bin/{name}"
            assert os.access(path, os.X_OK), f"not executable: /usr/bin/{name}"
        for lib in MC_LIBS:
            path = os.path.join(destdir, "usr", "share", "mavericks-apps", lib)
            assert os.path.isfile(path), f"not installed: {path}"
        # The installed file set must be import-sufficient for mv-mc-overview:
        # running the DESTDIR copy with its share dir on sys.path must pass
        # the import of both libs (mirrors LIBDIR on an installed system).
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(destdir, "usr", "share", "mavericks-apps")
        probe = subprocess.run(
            [sys.executable, "-c",
             "import mission_control, mission_control_thumbnail; print('ok')"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        assert probe.returncode == 0 and "ok" in probe.stdout, \
            f"installed libs not importable: {probe.stderr[-500:]}"
        print("PASS: DESTDIR install places every MC helper + libs correctly")
    finally:
        shutil.rmtree(destdir, ignore_errors=True)


TESTS = [
    test_mc_executables_in_install_list,
    test_referenced_helpers_in_install_list,
    test_mc_libs_installed_to_share,
    test_bin_files_not_forgotten,
    test_destdir_install_manifest,
]

if __name__ == "__main__":
    passed = failed = 0
    for test in TESTS:
        try:
            test()
            passed += 1
        except AssertionError as exc:
            print(f"FAIL: {test.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"ERROR: {test.__name__}: {type(exc).__name__}: {exc}")
            failed += 1
    print(f"Results: {passed} passed, {failed} failed out of {len(TESTS)}")
    raise SystemExit(1 if failed else 0)
