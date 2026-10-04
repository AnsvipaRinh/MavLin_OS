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

_DEFAULT_XDG_DATA_HOME = "~/.local/share"
_DEFAULT_XDG_DATA_DIRS = ("/usr/local/share", "/usr/share")

_CACHE_DIR = "~/.cache/mavericks"
_CACHE_PATH = _CACHE_DIR + "/desktop-entries.json"


def desktop_dirs():
    """Return XDG application dirs in user-to-system precedence order."""
    data_home = os.environ.get("XDG_DATA_HOME", "")
    if not data_home:
        data_home = os.path.expanduser(_DEFAULT_XDG_DATA_HOME)
    elif not os.path.isabs(os.path.expanduser(data_home)):
        data_home = os.path.expanduser(_DEFAULT_XDG_DATA_HOME)

    raw_dirs = os.environ.get("XDG_DATA_DIRS", "")
    data_dirs = [p for p in raw_dirs.split(":") if p]
    if not data_dirs:
        data_dirs = list(_DEFAULT_XDG_DATA_DIRS)

    result = [os.path.join(os.path.expanduser(data_home), "applications")]
    result.extend(
        os.path.join(os.path.expanduser(p), "applications")
        for p in data_dirs
        if os.path.isabs(os.path.expanduser(p))
    )

    unique = []
    seen = set()
    for path in result:
        path = os.path.normpath(path)
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _fingerprint():
    """Hash locale + recursive per-dir/file metadata used to build the cache."""
    h = hashlib.sha1()
    count = 0
    h.update(b"locale\\x00")
    h.update("\\x00".join(_locale_candidates()).encode("utf-8", "replace"))
    h.update(b"\\x00")
    # Desktop visibility and TryExec resolution depend on these environment
    # values, so they must participate in cache invalidation as well.
    h.update(b"desktop-env\\x00")
    h.update(os.environ.get("XDG_CURRENT_DESKTOP", "").encode("utf-8", "replace"))
    h.update(b"\\x00")
    h.update(os.environ.get("PATH", "").encode("utf-8", "replace"))
    h.update(b"\\x00")
    for d in desktop_dirs():
        if not os.path.isdir(d):
            continue
        for root, dirs, names in os.walk(d, followlinks=False):
            dirs.sort()
            names.sort()
            try:
                dst = os.stat(root)
                h.update(b"dir\\x00")
                h.update(root.encode("utf-8", "replace"))
                h.update(b"\\x00")
                h.update(str(dst.st_mtime_ns).encode())
                h.update(b"\\x00")
                h.update(str(dst.st_ctime_ns).encode())
                h.update(b"\\x00")
                h.update(str(dst.st_ino).encode())
                h.update(b"\\x00")
            except OSError:
                continue
            dir_count = 0
            for name in names:
                if not name.endswith(".desktop"):
                    continue
                path = os.path.join(root, name)
                try:
                    st = os.stat(path, follow_symlinks=False)
                except OSError:
                    continue
                h.update(b"file\\x00")
                h.update(path.encode("utf-8", "replace"))
                h.update(b"\\x00")
                h.update(str(st.st_mtime_ns).encode())
                h.update(b"\\x00")
                h.update(str(st.st_ctime_ns).encode())
                h.update(b"\\x00")
                h.update(str(st.st_ino).encode())
                h.update(b"\\x00")
                h.update(str(st.st_size).encode())
                h.update(b"\\x00")
                count += 1
                dir_count += 1
            h.update(b"count\\x00")
            h.update(root.encode("utf-8", "replace"))
            h.update(b"\\x00")
            h.update(str(dir_count).encode())
            h.update(b"\\x00")
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


def _desktop_environments():
    """Return active desktop-environment names used by OnlyShowIn/NotShowIn."""
    raw = os.environ.get("XDG_CURRENT_DESKTOP", "")
    return {item.strip() for item in raw.split(":") if item.strip()}


def _list_value(value):
    """Parse semicolon-separated desktop-entry list values."""
    return {item.strip() for item in value.split(";") if item.strip()}


def _try_exec_available(command):
    """Check TryExec without invoking the executable."""
    command = command.strip()
    if not command:
        return False
    if os.path.sep in command:
        return os.path.isfile(os.path.expanduser(command)) and os.access(
            os.path.expanduser(command), os.X_OK
        )
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            directory = os.curdir
        candidate = os.path.join(directory, command)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return True
    return False


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

    environments = _desktop_environments()
    only_show_in = _list_value(values.get("OnlyShowIn", ""))
    not_show_in = _list_value(values.get("NotShowIn", ""))
    if only_show_in and not (environments & only_show_in):
        return None
    if environments & not_show_in:
        return None

    try_exec = values.get("TryExec", "").strip()
    if try_exec and not _try_exec_available(try_exec):
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
    dbus_activatable = _parse_bool(values.get("DBusActivatable", "false"))
    if not name or (not exec_cmd and not dbus_activatable):
        return None

    # Spotlight and Launchpad launch by desktop ID through gtk-launch, so
    # Exec is retained only for ranking/metadata. DBus-activatable entries
    # are valid without Exec and are launched by the desktop activation API.
    if exec_cmd:
        exec_cmd = exec_cmd.split("%", 1)[0].strip()
        if not exec_cmd and not dbus_activatable:
            return None

    return {
        "path": path,
        "name": name,
        "exec": exec_cmd,
        "dbus_activatable": dbus_activatable,
        "icon": icon,
        "categories": categories,
    }


def _read_json_safe(path):
    """Read JSON cache; quarantine corrupt files and treat a miss safely."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        pass

    quarantine = "%s.corrupt-%d-%d" % (path, time.time_ns(), os.getpid())
    try:
        os.replace(path, quarantine)
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
            walk = os.walk(d)
        except OSError:
            continue
        for root, dirs, names in walk:
            dirs.sort()
            for name in sorted(names):
                if not name.endswith(".desktop"):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, d)
                desktop_id = rel.replace(os.sep, "-")
                if desktop_id in seen_ids:
                    continue
                seen_ids.add(desktop_id)
                e = _parse_desktop_file(path)
                if e is not None:
                    e["desktop_id"] = desktop_id
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
