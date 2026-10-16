#!/usr/bin/env python3
"""Storage inventory and capacity preflight for MavlinOS agents.

MavlinOS is developed inside Arch Linux under WSL2.  That makes two very
different numbers matter, and confusing them is how a machine that looks empty
inside Linux runs out of room on Windows:

  * free space *inside* the WSL virtual disk (ext4, normally 1 TiB max), and
  * free space on the *Windows volume* that stores that virtual disk.

The virtual disk grows by writing into the Windows volume, so the Windows
figure is the real ceiling.  This script reports both, never only one.

No daemon and no polling: it measures on demand and prints a report.

Usage:
  storage-audit.py inventory [--save] [--json PATH]
  storage-audit.py preflight --need 20          # gate a large operation
  storage-audit.py diff [--against PATH]

Exit codes for `preflight`:
  0 NORMAL, 1 WARNING, 2 CRITICAL, 3 EMERGENCY, 4 usage/measurement error.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "config" / "storage-policy.json"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "UI_REFERENCE" / "storage-baseline.json"

SEVERITY_ORDER = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2, "EMERGENCY": 3}
BLOCKING = {"CRITICAL", "EMERGENCY"}

# Paths outside the repository that belong to MavlinOS research.
EXTERNAL_ROOTS = ["/home/builder/vmwork", "/home/builder/ghidra_proj"]

# Windows capacity is reported from a 9p mount when present.
WINDOWS_FSTYPES = {"9p", "drvfs", "drvfs.exe"}


def load_policy(path: str | os.PathLike | None = None) -> dict:
    p = pathlib.Path(path) if path else DEFAULT_POLICY
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return {"thresholds": {}, "subsystems": {}, "protected": []}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"storage-audit: invalid policy {p}: {exc}")


# --------------------------------------------------------------------------
# filesystem discovery
# --------------------------------------------------------------------------

def is_wsl(probes: list[str] | None = None) -> bool:
    """True when running inside WSL (any distribution).

    The environment variables are consulted only for the default probe list, so
    a caller (or a test) passing explicit probes gets a deterministic answer.
    """
    use_env = probes is None
    for probe in (probes if probes is not None
                  else ["/proc/sys/kernel/osrelease", "/proc/version"]):
        try:
            text = pathlib.Path(probe).read_text().lower()
        except OSError:
            continue
        if "microsoft" in text or "wsl" in text:
            return True
    if use_env:
        return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
    return False


def _df_records() -> list[dict]:
    """df for real block-backed and 9p mounts, keyed by mount point."""
    # `df -P` keeps one filesystem per line, which matters because WSL mount
    # points can contain spaces.  `-P` cannot be combined with `--output`, so the
    # filesystem type is resolved separately through findmnt.
    try:
        out = subprocess.run(
            ["df", "-P", "-B1"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        src, size, used, avail, pcent, target = parts
        try:
            rows.append({
                "source": src,
                "fstype": _fstype_of(target),
                "size": int(size),
                "used": int(used),
                "avail": int(avail),
                "use_pct": int(pcent.rstrip("%")),
                "mount": target,
            })
        except ValueError:
            continue
    return rows


def _fstype_of(mount: str) -> str:
    try:
        out = subprocess.run(
            ["findmnt", "-no", "FSTYPE", "--target", mount],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.strip()
        return out
    except (OSError, subprocess.SubprocessError):
        return ""


def discover_filesystems(extra_paths: list[str] | None = None) -> list[dict]:
    """Return the filesystems that matter: the ones holding project data.

    Always includes the filesystem holding the repository, plus any Windows
    volume mounted into WSL.  De-duplicated by mount point.
    """
    rows = _df_records()
    by_mount = {r["mount"]: r for r in rows}
    wanted: list[str] = []

    for path in [str(REPO_ROOT), *(extra_paths or [])]:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            continue
        best = None
        for mount in by_mount:
            if path == mount or path.startswith(mount.rstrip("/") + "/"):
                if best is None or len(mount) > len(best):
                    best = mount
        if best:
            wanted.append(best)

    for r in rows:
        if r["fstype"] in WINDOWS_FSTYPES:
            wanted.append(r["mount"])

    seen, out = set(), []
    for mount in wanted:
        if mount in seen:
            continue
        seen.add(mount)
        rec = dict(by_mount.get(mount, {}))
        rec.setdefault("mount", mount)
        rec["fstype"] = _fstype_of(mount) or rec.get("fstype", "")
        rec["is_windows_volume"] = rec.get("fstype", "") in WINDOWS_FSTYPES
        out.append(rec)
    return out


def severity(fs: dict, policy: dict) -> str:
    """Classify one filesystem against the configured thresholds."""
    th = policy.get("thresholds", {}).get("default", {})
    avail = fs.get("avail")
    if avail is None:
        return "UNKNOWN"
    pct = 100.0 - (fs.get("used", 0) * 100.0 / fs["size"]) if fs.get("size") else 0.0

    def hit(level):
        rule = th.get(level, {})
        by_pct = rule.get("free_pct_below")
        by_abs = rule.get("free_gb_below")
        pct_hit = by_pct is not None and pct < by_pct
        abs_hit = by_abs is not None and avail < by_abs * (1024 ** 3)
        return pct_hit or abs_hit

    for level in ("EMERGENCY", "CRITICAL", "WARNING"):
        if hit(level):
            return level
    return "NORMAL"


# --------------------------------------------------------------------------
# size accounting
# --------------------------------------------------------------------------

def measure_tree(root: str, follow_symlinks: bool = False) -> dict:
    """Measure one tree without following symlinks or crossing devices.

    Reports apparent size (sum of st_size), allocated size (sum of st_blocks*512)
    so sparse files and hard links are accounted honestly.
    """
    result = {
        "path": str(root), "exists": False, "files": 0, "dirs": 0,
        "apparent": 0, "allocated": 0, "errors": [], "sparse_files": 0,
        "newest_mtime": None,
    }
    if not os.path.exists(root):
        return result
    result["exists"] = True
    seen: set[tuple[int, int]] = set()
    newest = 0.0
    stack = [str(root)]
    root_dev = os.stat(str(root)).st_dev if os.path.exists(str(root)) else None

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except (PermissionError, OSError) as exc:
            if len(result["errors"]) < 10:
                result["errors"].append(f"{current}: {exc.__class__.__name__}")
            continue
        for entry in entries:
            try:
                if entry.is_symlink() and not follow_symlinks:
                    continue
                st = entry.stat(follow_symlinks=follow_symlinks)
            except OSError:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            if st.st_dev != root_dev and entry.is_dir(follow_symlinks=False):
                continue  # do not cross into other filesystems
            newest = max(newest, st.st_mtime)
            if entry.is_dir(follow_symlinks=False):
                result["dirs"] += 1
                stack.append(entry.path)
            else:
                result["files"] += 1
                result["apparent"] += st.st_size
                alloc = st.st_blocks * 512
                result["allocated"] += alloc
                if alloc < st.st_size:
                    result["sparse_files"] += 1
    result["newest_mtime"] = newest or None
    return result


def measure_many(roots: list[str]) -> dict:
    """Measure several roots, skipping anything nested inside an earlier root.

    Prevents double counting, e.g. /home/builder/vmwork and a subdirectory of it.
    """
    existing = sorted(
        [os.path.abspath(r) for r in roots if os.path.exists(r)],
        key=len,
    )
    top, skipped = [], []
    for path in existing:
        if any(path.startswith(t.rstrip("/") + "/") for t in top):
            skipped.append(path)
            continue
        top.append(path)

    subsystems, totals = {}, {"apparent": 0, "allocated": 0, "files": 0}
    for path in top:
        m = measure_tree(path)
        name = pathlib.Path(path).name or path
        subsystems[name] = m
        totals["apparent"] += m["apparent"]
        totals["allocated"] += m["allocated"]
        totals["files"] += m["files"]
    return {"subsystems": subsystems, "totals": totals, "skipped_nested": skipped}


def human(n: int) -> str:
    step = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(step) < 1024 or unit == "TiB":
            return f"{step:.1f} {unit}"
        step /= 1024
    return f"{step:.1f} TiB"


# --------------------------------------------------------------------------
# inventory assembly
# --------------------------------------------------------------------------

def build_inventory(policy: dict, extra_paths: list[str] | None = None) -> dict:
    fss = discover_filesystems(extra_paths)
    for fs in fss:
        fs["severity"] = severity(fs, policy)

    research_roots = [r for r in EXTERNAL_ROOTS if os.path.exists(r)]
    tree = measure_many(research_roots + [str(REPO_ROOT)])

    subsystem_meta = []
    for name, meta in tree["subsystems"].items():
        path = meta["path"]
        cat = "unclassified"
        for entry in policy.get("subsystems", []):
            if path.startswith(entry.get("path", "\0")):
                cat = entry.get("category", "unclassified")
                break
        subsystem_meta.append({
            "name": name, "path": path, "category": cat,
            "apparent": meta["apparent"], "allocated": meta["allocated"],
            "files": meta["files"], "sparse_files": meta["sparse_files"],
        })
    subsystem_meta.sort(key=lambda r: r["allocated"], reverse=True)

    return {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wsl": is_wsl(),
        "filesystems": fss,
        "worst_severity": max(
            (fs["severity"] for fs in fss),
            key=lambda s: SEVERITY_ORDER.get(s, 0), default="NORMAL"),
        "research_roots": research_roots,
        "totals": tree["totals"],
        "subsystems": subsystem_meta,
        "skipped_nested": tree["skipped_nested"],
        "protected": policy.get("protected", []),
    }


def render_report(inv: dict) -> str:
    out = []
    out.append(f"MavlinOS storage inventory  {inv['generated']}")
    out.append(f"environment: {'WSL' if inv['wsl'] else 'native Linux'}")
    out.append("")
    out.append("Filesystems holding project data:")
    for fs in inv["filesystems"]:
        tag = "windows volume" if fs.get("is_windows_volume") else "wsl filesystem"
        out.append(
            f"  {fs['mount']:<28} {fs.get('fstype',''):<8} "
            f"{human(fs.get('size', 0)):>10} total  {human(fs.get('avail', 0)):>10} free  "
            f"{fs.get('use_pct', 0):>3}%  [{fs.get('severity')}]  {tag}"
        )
    out.append(f"  worst severity: {inv['worst_severity']}")
    out.append("")
    out.append("Research footprint (allocated on disk):")
    for s in inv["subsystems"]:
        out.append(
            f"  {s['name']:<26} {human(s['allocated']):>10} allocated  "
            f"{human(s['apparent']):>10} apparent  {s['files']:>7} files  [{s['category']}]"
        )
    out.append(f"  {'TOTAL':<26} {human(inv['totals']['allocated']):>10} allocated")
    if inv.get("skipped_nested"):
        out.append(f"  (skipped nested to avoid double counting: {', '.join(inv['skipped_nested'])})")
    out.append("")
    out.append("Windows volume is the real ceiling: the WSL virtual disk grows into it.")
    return "\n".join(out)


def preflight(need_gb: float, policy: dict, extra_paths: list[str] | None = None) -> int:
    inv = build_inventory(policy, extra_paths)
    print(render_report(inv))
    print("")
    windows = [fs for fs in inv["filesystems"] if fs.get("is_windows_volume")]
    targets = windows or inv["filesystems"]
    need = int(need_gb * (1024 ** 3))
    worst, blocking = "NORMAL", None
    for fs in targets:
        sev = fs.get("severity", "NORMAL")
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(worst, 0):
            worst, blocking = sev, fs
        if fs.get("avail", 0) < need:
            print(f"  INSUFFICIENT on {fs['mount']}: needs {human(need)}, "
                  f"only {human(fs.get('avail', 0))} free")
            worst = max([worst, "CRITICAL"], key=lambda s: SEVERITY_ORDER[s])
    print(f"PREFLIGHT: need {human(need)} -> {worst}"
          + (f" (blocking filesystem: {blocking['mount']})" if worst in BLOCKING else ""))
    return SEVERITY_ORDER.get(worst, 0)


def diff_inventory(current: dict, previous: dict) -> str:
    lines = ["Growth since baseline:"]
    prev = {s["path"]: s for s in previous.get("subsystems", [])}
    cur = {s["path"]: s for s in current.get("subsystems", [])}
    grew = False
    for path, s in sorted(cur.items()):
        old = prev.get(path, {}).get("allocated", 0)
        delta = s["allocated"] - old
        if delta > 100 * 1024 * 1024:
            grew = True
            lines.append(f"  +{human(delta):>10}  {path}")
        elif delta < -(100 * 1024 * 1024):
            grew = True
            lines.append(f"  {human(delta):>10}  {path}")
    for path in prev:
        if path not in cur:
            grew = True
            lines.append(f"  REMOVED    {path}")
    if not grew:
        lines.append("  no change above 100 MiB")
    pf = {f["mount"]: f for f in previous.get("filesystems", [])}
    for fs in current.get("filesystems", []):
        old = pf.get(fs["mount"], {}).get("avail")
        if old is not None:
            delta = fs.get("avail", 0) - old
            if abs(delta) > 100 * 1024 * 1024:
                lines.append(f"  {human(delta):>10}  free space on {fs['mount']}"
                             f" (now {fs.get('severity')})")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# protected paths
# --------------------------------------------------------------------------

def is_protected(path: str, policy: dict) -> bool:
    """True when cleanup must refuse to touch this path."""
    ap = os.path.abspath(path)
    for raw in policy.get("protected", []):
        p = os.path.abspath(raw)
        if ap == p or ap.startswith(p.rstrip("/") + "/"):
            return True
    return False


def cleanup_guard(path: str, policy: dict) -> tuple[bool, str]:
    ok, why = True, ""
    if not os.path.exists(path):
        return False, f"path does not exist: {path}"
    if is_protected(path, policy):
        ok, why = False, f"protected path, refusing automatic cleanup: {path}"
    return ok, why


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MavlinOS storage inventory")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--path", action="append", default=[],
                    help="extra path to account for (repeatable)")
    sub = ap.add_subparsers(dest="cmd")

    p_inv = sub.add_parser("inventory")
    p_inv.add_argument("--save", action="store_true", help="write the baseline file")
    p_inv.add_argument("--json", dest="json_out", default=None)

    p_pre = sub.add_parser("preflight")
    p_pre.add_argument("--need", type=float, required=True, help="GiB required")

    p_diff = sub.add_parser("diff")
    p_diff.add_argument("--against", default=str(DEFAULT_BASELINE))

    args = ap.parse_args(argv)
    policy = load_policy(args.policy)
    cmd = args.cmd or "inventory"

    if cmd == "preflight":
        return preflight(args.need, policy, args.path)

    inv = build_inventory(policy, args.path)
    print(render_report(inv))

    if cmd == "diff":
        try:
            prev = json.loads(pathlib.Path(args.against).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  no usable baseline ({exc})")
        else:
            print("")
            print(diff_inventory(inv, prev))

    if cmd == "inventory":
        out = args.json_out
        if args.save and not out:
            out = str(DEFAULT_BASELINE)
        if out:
            pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(out).write_text(json.dumps(inv, indent=1) + "\n")
            print(f"\nbaseline written: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())