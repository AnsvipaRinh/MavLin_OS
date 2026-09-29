#!/usr/bin/env python3
"""Shared .desktop parse cache for mv-launchpad / mv-spotlight.

Every open of Launchpad/Spotlight re-parsed all XDG .desktop files in
Python (~12-15 ms for ~108 files). This module caches the raw parsed
entries in ~/.cache/mavericks/desktop-entries.json.

Invalidation is airtight: the cache key covers every desktop dir's
(mtime_ns, file count) plus every .desktop file's (mtime_ns, size).
Add/remove/rename changes dir mtime+count; in-place edits change file
mtime_ns (ns granularity on ext4/btrfs). The only uncaught case is a
content swap that preserves both size and mtime_ns — not producible by
pacman, sed -i, or editors without deliberate mtime forgery.

Corrupt-cache safety follows the mv-music family pattern: a corrupt
cache file is quarantined (renamed .corrupt-<ts>) and treated as a miss.

Raw entries (Hidden/NoDisplay filtered) are returned; each app applies
its own post-processing (dedup/sort/icon validation).
"""
import hashlib
import json
import os
import time

_DESKTOP_DIR_PATHS = (
    "/usr/share/applications",
    "/usr/local/share/applications",
    "~/.local/share/applications",
)

_CACHE_DIR = "~/.cache/mavericks"
_CACHE_PATH = _CACHE_DIR + "/desktop-entries.json"


def desktop_dirs():
    """XDG desktop dirs, computed at call time (tests patch HOME)."""
    return [
        os.path.expanduser(p) for p in _DESKTOP_DIR_PATHS
    ]


def _fingerprint():
    """Hash of per-dir (mtime_ns, count) + per-file (mtime_ns, size).

    Add/remove/rename changes dir mtime_ns + count; in-place edits change
    file mtime_ns. Same guarantee class as the mv-music scan cache.
    """
    h = hashlib.sha1()
    count = 0
    for d in desktop_dirs():
        if not os.path.isdir(d):
            continue
        try:
            dst = os.stat(d)
            h.update(b"dir\x00")
            h.update(d.encode("utf-8", "replace"))
            h.update(b"\x00")
            h.update(str(dst.st_mtime_ns).encode())
            h.update(b"\x00")
        except OSError:
            continue
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        dir_count = 0
        for name in names:
            if not name.endswith(".desktop"):
                continue
            path = os.path.join(d, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            h.update(b"file\x00")
            h.update(path.encode("utf-8", "replace"))
            h.update(b"\x00")
            h.update(str(st.st_mtime_ns).encode())
            h.update(b"\x00")
            h.update(str(st.st_size).encode())
            h.update(b"\x00")
            count += 1
            dir_count += 1
        h.update(b"count\x00")
        h.update(d.encode("utf-8", "replace"))
        h.update(b"\x00")
        h.update(str(dir_count).encode())
        h.update(b"\x00")
    return h.hexdigest(), count


def _parse_desktop_file(path):
    """Parse one .desktop file into a raw entry, or None if hidden/invalid.

    Parsing matches mv-launchpad/mv-spotlight exactly: Hidden/NoDisplay
    files skipped; Name/Exec/Icon/Categories line prefixes; Exec stripped
    at '%'; entries without both Name and Exec dropped.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            content = fp.read()
    except OSError:
        return None
    if "NoDisplay=true" in content or "Hidden=true" in content:
        return None
    name = ""
    exec_cmd = ""
    icon = ""
    categories = ""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Name="):
            name = line[5:].strip()
        elif line.startswith("Exec="):
            exec_cmd = line[5:].strip().split("%")[0]
        elif line.startswith("Icon="):
            icon = line[5:].strip()
        elif line.startswith("Categories="):
            categories = line[11:].strip()
    if not name or not exec_cmd:
        return None
    return {
        "path": path,
        "name": name,
        "exec": exec_cmd,
        "icon": icon,
        "categories": categories,
    }


def _read_json_safe(path):
    """Read JSON cache; on any error quarantine the corrupt file (family
    pattern: never silently lost) and return None (cache miss)."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        pass
    try:
        os.replace(path, "%s.corrupt-%d" % (path, int(time.time())))
    except OSError:
        pass
    return None


def load_desktop_entries():
    """Return raw .desktop entries for all XDG desktop dirs.

    Cache hit (fingerprint match) skips all file reads/parsing.
    Miss/corrupt/stale -> full re-parse + atomic cache write.
    """
    fp, count = _fingerprint()
    path = os.path.expanduser(_CACHE_PATH)
    data = _read_json_safe(path)
    if isinstance(data, dict):
        entry = data.get("desktop")
        if isinstance(entry, dict) and entry.get("fp") == fp \
                and entry.get("count") == count:
            entries = entry.get("entries")
            if isinstance(entries, list):
                return entries
    entries = []
    for d in desktop_dirs():
        if not os.path.isdir(d):
            continue
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop"):
                continue
            e = _parse_desktop_file(os.path.join(d, name))
            if e is not None:
                entries.append(e)
    _save_desktop_entries(entries, fp, count)
    return entries


def _save_desktop_entries(entries, fp, count):
    try:
        cdir = os.path.expanduser(_CACHE_DIR)
        os.makedirs(cdir, exist_ok=True)
        path = os.path.expanduser(_CACHE_PATH)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"desktop": {"fp": fp, "count": count,
                                   "entries": entries}}, f)
        os.replace(tmp, path)
    except OSError:
        pass
