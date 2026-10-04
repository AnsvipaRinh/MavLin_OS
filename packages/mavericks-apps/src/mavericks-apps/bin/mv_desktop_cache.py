#!/usr/bin/env python3
"""Shared .desktop parse cache for mv-launchpad / mv-spotlight.

Every open of Launchpad/Spotlight re-parsed all XDG .desktop files in
Python (~12-15 ms for ~108 files). This module caches the raw parsed
entries in ~/.cache/mavericks/desktop-entries.json.

The parser is intentionally small, but follows the Desktop Entry model
closely enough for application discovery: only the [Desktop Entry] group
is read, Hidden/NoDisplay are parsed as booleans, Type=Application is
honored when present, localized Name keys are selected from the active
locale, and duplicate desktop IDs use user-local/system precedence.

Invalidation covers every desktop dir's (mtime_ns, file count) plus every
.desktop file's (mtime_ns, size). Corrupt cache files are quarantined.
"""
import hashlib
import json
import os
import tempfile
import time

_DESKTOP_DIR_PATHS = (
    "~/.local/share/applications",
    "/usr/local/share/applications",
    "/usr/share/applications",
)

_CACHE_DIR = "~/.cache/mavericks"
_CACHE_PATH = _CACHE_DIR + "/desktop-entries.json"


def desktop_dirs():
    """XDG desktop dirs, computed at call time (tests patch HOME)."""
    return [os.path.expanduser(p) for p in _DESKTOP_DIR_PATHS]


def _fingerprint():
    """Hash of locale + per-dir/file metadata used to build the cache."""
    h = hashlib.sha1()
    count = 0
    h.update(b"locale\\x00")
    h.update("\\x00".join(_locale_candidates()).encode("utf-8", "replace"))
    h.update(b"\\x00")
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
            h.update(str(st.st_ctime_ns).encode())
            h.update(b"\x00")
            h.update(str(st.st_ino).encode())
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


def _locale_candidates():
    """Return desktop-entry locale keys from most to least specific."""
    values = []
    for variable in ("LANGUAGE", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(variable, "")
        if not raw:
            continue
        for value in raw.split(":"):
            value = value.split(".", 1)[0]
            if value and value not in values:
                values.append(value)
    candidates = []
    for value in values:
        variants = [value]
        base = value.split("@", 1)[0]
        if base not in variants:
            variants.append(base)
        language = base.split("_", 1)[0]
        if language not in variants:
            variants.append(language)
        for candidate in variants:
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _parse_bool(value):
    return value.strip().lower() == "true"


def _parse_desktop_file(path):
    """Parse one application .desktop file into a raw entry."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            content = fp.read()
    except OSError:
        return None

    section = None
    values = {}
    localized_names = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section != "Desktop Entry" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key.startswith("Name[") and key.endswith("]"):
            localized_names[key[5:-1]] = value
        elif key not in values:
            values[key] = value

    if _parse_bool(values.get("Hidden", "false")):
        return None
    if _parse_bool(values.get("NoDisplay", "false")):
        return None
    entry_type = values.get("Type", "Application").strip()
    if entry_type != "Application":
        return None

    name = ""
    for locale_key in _locale_candidates():
        if locale_key in localized_names:
            name = localized_names[locale_key]
            break
    if not name:
        name = values.get("Name", "").strip()

    exec_cmd = values.get("Exec", "").strip()
    icon = values.get("Icon", "").strip()
    categories = values.get("Categories", "").strip()
    if not name or not exec_cmd:
        return None

    # Spotlight now launches by desktop ID, so Exec is retained only for
    # ranking/metadata. Keep the legacy field-code stripping behavior here.
    exec_cmd = exec_cmd.split("%", 1)[0].strip()
    if not exec_cmd:
        return None

    return {
        "path": path,
        "name": name,
        "exec": exec_cmd,
        "icon": icon,
        "categories": categories,
    }


def _read_json_safe(path):
    """Read JSON cache; quarantine corrupt files and treat as a miss."""
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
    """Return raw .desktop entries with desktop-ID precedence applied.

    The first occurrence of a desktop filename wins because desktop_dirs()
    is ordered user-local > /usr/local > /usr/share.
    """
    fp, count = _fingerprint()
    path = os.path.expanduser(_CACHE_PATH)
    data = _read_json_safe(path)
    if isinstance(data, dict):
        entry = data.get("desktop")
        if isinstance(entry, dict) and entry.get("fp") == fp and entry.get("count") == count:
            entries = entry.get("entries")
            if isinstance(entries, list):
                return entries

    entries = []
    seen_ids = set()
    for d in desktop_dirs():
        if not os.path.isdir(d):
            continue
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop") or name in seen_ids:
                continue
            seen_ids.add(name)
            e = _parse_desktop_file(os.path.join(d, name))
            if e is not None:
                entries.append(e)
    _save_desktop_entries(entries, fp, count)
    return entries


def _save_desktop_entries(entries, fp, count):
    """Persist the desktop cache with a unique, same-directory atomic write."""
    cdir = os.path.expanduser(_CACHE_DIR)
    path = os.path.expanduser(_CACHE_PATH)
    tmp_path = None
    try:
        os.makedirs(cdir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".desktop-entries.", dir=cdir)
        with os.fdopen(fd, "w") as cache_file:
            json.dump({"desktop": {"fp": fp, "count": count, "entries": entries}}, cache_file)
            cache_file.write("\n")
            cache_file.flush()
            os.fsync(cache_file.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
        try:
            dir_fd = os.open(cdir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except OSError:
        pass
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
