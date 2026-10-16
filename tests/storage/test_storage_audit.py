#!/usr/bin/env python3
"""Tests for scripts/storage-audit.py.

Storage mistakes are expensive and slow to notice, so these tests pin the
behaviour that matters:

  * sparse files are counted by allocated size, not apparent size;
  * nested paths are measured once, never double counted;
  * WSL and Windows-volume detection work in both directions;
  * a missing or unreadable path degrades instead of crashing;
  * threshold transitions land on the documented severities;
  * protected paths are refused by the cleanup guard.

Every case below can fail: each asserts a specific expected value rather than
just running the code.

Run:  python3 tests/storage/test_storage_audit.py
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "storage_audit", REPO / "scripts" / "storage-audit.py")
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)

failures = []
GB = 1024 ** 3


def check(cond, msg):
    if not cond:
        failures.append(msg)


POLICY = json.loads((REPO / "config" / "storage-policy.json").read_text())


def fsrec(size_gb, avail_gb, fstype="ext4", mount="/mnt/test"):
    return {
        "mount": mount, "fstype": fstype, "size": int(size_gb * GB),
        "used": int((size_gb - avail_gb) * GB), "avail": int(avail_gb * GB),
        "use_pct": int((1 - avail_gb / size_gb) * 100),
    }


# --- sparse file accounting -------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    root = pathlib.Path(td)
    (root / "dense.txt").write_bytes(b"x" * 4096)
    sparse = root / "sparse.raw"
    with open(sparse, "wb") as fh:
        fh.truncate(512 * GB)          # 512 GiB apparent, a few blocks allocated
    m = sa.measure_tree(str(root))
    check(m["exists"] is True, "measure_tree: temp tree should exist")
    check(m["apparent"] >= 512 * GB,
          f"measure_tree: apparent size must count the sparse hole, got {m['apparent']}")
    check(m["allocated"] < 16 * 1024 * 1024,
          f"measure_tree: allocated size must ignore the sparse hole, got {m['allocated']}")
    check(m["sparse_files"] >= 1, "measure_tree: sparse file was not detected")
    check(m["allocated"] < m["apparent"],
          "measure_tree: allocated must be below apparent for sparse data")

# --- nested paths must not be double counted -------------------------------
with tempfile.TemporaryDirectory() as td:
    root = pathlib.Path(td)
    (root / "inner").mkdir()
    (root / "inner" / "payload.bin").write_bytes(b"y" * (8 * 1024 * 1024))
    res = sa.measure_many([str(root), str(root / "inner"), str(root / "inner")])
    check(len(res["subsystems"]) == 1,
          f"measure_many: nested roots must collapse, got {list(res['subsystems'])}")
    check(res["skipped_nested"], "measure_many: nested roots must be reported as skipped")
    total = res["totals"]["allocated"]
    check(total < 16 * 1024 * 1024,
          f"measure_many: payload counted more than once ({total} bytes)")

# --- missing and unreadable paths -----------------------------------------
missing = sa.measure_tree("/nonexistent/storage-audit-test")
check(missing["exists"] is False, "measure_tree: missing path must report exists=False")
check(missing["allocated"] == 0, "measure_tree: missing path must report zero size")

res_missing = sa.measure_many(["/nonexistent/a", "/nonexistent/b"])
check(res_missing["totals"]["allocated"] == 0,
      "measure_many: all-missing roots must total zero")

# --- WSL detection, both directions ---------------------------------------
with tempfile.TemporaryDirectory() as td:
    wsl_release = pathlib.Path(td) / "osrelease"
    wsl_release.write_text("6.18.54.1-microsoft-standard-WSL2\n")
    linux_release = pathlib.Path(td) / "osrelease2"
    linux_release.write_text("6.9.0-arch\n")
    check(sa.is_wsl([str(wsl_release)]) is True, "is_wsl: WSL kernel not detected")
    check(sa.is_wsl([str(linux_release)]) is False, "is_wsl: plain Linux falsely detected")
    check(sa.is_wsl([str(pathlib.Path(td) / "absent")]) is False,
          "is_wsl: missing probe must not raise")
    check(sa.is_wsl() is True,
          "is_wsl: this test host is WSL, detection must agree")

# --- Windows volume detection ---------------------------------------------
orig_records = sa._df_records
sa._df_records = lambda: [
    fsrec(475.9, 14.8, fstype="9p", mount="/mnt/c"),
    fsrec(1006.9, 562.9, fstype="ext4", mount="/"),
]
try:
    discovered = sa.discover_filesystems([REPO])
    windows = [f for f in discovered if f.get("is_windows_volume")]
    check(windows, "discover_filesystems: 9p Windows volume not detected")
    if windows:
        check(windows[0]["mount"] == "/mnt/c",
              f"discover_filesystems: wrong Windows mount {windows[0]['mount']}")
    check(any(f["mount"] == "/" for f in discovered),
          "discover_filesystems: WSL root filesystem holding the repo not detected")
finally:
    sa._df_records = orig_records

# --- threshold transitions -------------------------------------------------
check(sa.severity(fsrec(500, 300), POLICY) == "NORMAL",
      "severity: 300 GiB free must be NORMAL")
check(sa.severity(fsrec(1000, 100), POLICY) == "WARNING",
      "severity: 100/1000 GiB is 10% free, must be WARNING not CRITICAL")
check(sa.severity(fsrec(100, 8), POLICY) == "CRITICAL",
      "severity: 8 GiB free on a small disk must be CRITICAL")
check(sa.severity(fsrec(475.9, 14.8), POLICY) == "EMERGENCY",
      "severity: 14.8 GiB free of 475.9 is 3% free, must be EMERGENCY")
# 25% free but only 25 GiB: the absolute WARNING rule must fire even though the
# percentage alone would look acceptable.
check(sa.severity(fsrec(100, 25), POLICY) == "WARNING",
      "severity: absolute free-space rule must fire below 30 GiB")
check(sa.severity({"mount": "/x", "size": None}, POLICY) == "UNKNOWN",
      "severity: missing size must report UNKNOWN, not crash")

# --- policy drives thresholds, not hardcoded numbers ------------------------
custom = {"thresholds": {"default": {
    "WARNING": {"free_gb_below": 1000}, "CRITICAL": {"free_gb_below": 2000},
    "EMERGENCY": {"free_gb_below": 3000}}}}
check(sa.severity(fsrec(100, 300), custom) == "EMERGENCY",
      "severity: custom policy thresholds were ignored")
check(sa.severity(fsrec(5000, 4000), custom) == "NORMAL",
      "severity: custom policy must allow a wider disk")

# --- protected paths --------------------------------------------------------
check(sa.is_protected("/home/builder/vmwork/mavericks-hdd.raw", POLICY) is True,
      "is_protected: guest disk must be protected")
check(sa.is_protected("/home/builder/vmwork/mavericks-hdd.raw.backup-2026-10-15/x",
                      POLICY) is True,
      "is_protected: backup path under a protected prefix must be protected")
check(sa.is_protected("/mnt/c", POLICY) is True, "is_protected: Windows volume must be protected")
check(sa.is_protected("/home/builder/vmwork/opencode", POLICY) is False,
      "is_protected: research data must not be protected")

ok, why = sa.cleanup_guard("/home/builder/vmwork/mavericks-hdd.raw", POLICY)
check(ok is False and "protected" in why,
      f"cleanup_guard: must refuse the guest disk, got {ok} {why!r}")
ok, why = sa.cleanup_guard("/definitely/not/here", POLICY)
check(ok is False, "cleanup_guard: missing path must be refused")
with tempfile.TemporaryDirectory() as td:
    ok, why = sa.cleanup_guard(td, POLICY)
    check(ok is True, f"cleanup_guard: ordinary temp dir must pass the guard, got {why!r}")

# --- human() formatting ------------------------------------------------------
check(sa.human(0) == "0.0 B", f"human: zero formats as {sa.human(0)!r}")
check(sa.human(GB).startswith("1.0 GiB"), f"human: 1 GiB formats as {sa.human(GB)!r}")
check(sa.human(1) == "1.0 B", f"human: one byte formats as {sa.human(1)!r}")

# --- end-to-end CLI ---------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    out = pathlib.Path(td) / "inv.json"
    rc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "storage-audit.py"),
         "--path", str(REPO), "inventory", "--json", str(out)],
        capture_output=True, text=True, timeout=600)
    check(rc.returncode == 0, f"CLI: inventory exited {rc.returncode}: {rc.stderr[:200]}")
    check(out.exists(), "CLI: --json did not write the inventory")
    if out.exists():
        inv = json.loads(out.read_text())
        check("filesystems" in inv and inv["filesystems"],
              "CLI: inventory has no filesystems")
        check(inv["wsl"] is True, "CLI: inventory did not record the WSL environment")
        check("subsystems" in inv, "CLI: inventory has no subsystem breakdown")
        rc2 = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "storage-audit.py"),
             "preflight", "--need", "99999"],
            capture_output=True, text=True, timeout=600)
        check(rc2.returncode >= 2,
              f"CLI: impossible preflight must not return NORMAL (rc={rc2.returncode})")
        check("INSUFFICIENT" in rc2.stdout,
              "CLI: impossible preflight must say INSUFFICIENT")

if failures:
    for f in failures:
        print("FAIL:", f)
    raise SystemExit(1)
print("storage audit contract OK")
raise SystemExit(0)