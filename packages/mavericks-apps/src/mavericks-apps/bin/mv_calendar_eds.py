#!/usr/bin/env python3
"""mv-calendar EDS sync bridge (read-only).

One-shot sync: mv-calendar <- EDS (evolution-data-server).
Reads EDS calendar sources (local + GOA Google + generic CalDAV via GOA),
imports events into mv-calendar store namespaced per remote calendar.

Sync triggers: on-launch + manual button + interval >=15min (no daemon, no polling).
Offline path: sync skipped, local works.

No export back, no OAuth token handling, no conflict resolution — not in scope.

License: GPL-2.0-or-later.
"""
import json
import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

try:
    import gi
    gi.require_version("ECal", "2.0")
    gi.require_version("EDataServer", "1.2")
    from gi.repository import ECal, EDataServer, ICalGLib
    _EDS_AVAILABLE = True
except Exception:
    _EDS_AVAILABLE = False

try:
    # When imported from mv-calendar (same directory)
    from .mv_calendar import (
        STORE, DEFAULT_ACCOUNTS, parse_dt, fmt_ics, load_store, save_store,
        uuid, iter_event_dates
    )
except ImportError:
    # When loaded standalone (e.g., in tests)
    import importlib.machinery
    import importlib.util
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    mv_path = os.path.join(base, "mv-calendar")
    loader = importlib.machinery.SourceFileLoader("mv_calendar", mv_path)
    spec = importlib.util.spec_from_loader("mv_calendar", loader)
    mv_mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mv_mod)
    STORE = mv_mod.STORE
    DEFAULT_ACCOUNTS = mv_mod.DEFAULT_ACCOUNTS
    parse_dt = mv_mod.parse_dt
    fmt_ics = mv_mod.fmt_ics
    load_store = mv_mod.load_store
    save_store = mv_mod.save_store
    uuid = mv_mod.uuid
    iter_event_dates = mv_mod.iter_event_dates

# EDS source types that provide calendars
CALENDAR_SOURCE_TYPES = {
    'caldav', 'google', 'webcal', 'local', 'system-calendar', 'birthdays'
}

# Minimum interval between syncs (seconds)
MIN_SYNC_INTERVAL = 15 * 60  # 15 minutes

# Sync state file
SYNC_STATE_FILE = os.path.expanduser("~/.local/share/mv-calendar/sync-state.json")


def _load_sync_state() -> Dict[str, Any]:
    """Load sync state (last sync time, per-source etags)."""
    if not os.path.exists(SYNC_STATE_FILE):
        return {"last_sync": 0, "sources": {}}
    try:
        with open(SYNC_STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last_sync": 0, "sources": {}}


def _save_sync_state(state: Dict[str, Any]) -> None:
    """Save sync state atomically."""
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    tmp = SYNC_STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, SYNC_STATE_FILE)


def _should_sync(state: Dict[str, Any], force: bool = False) -> bool:
    """Check if enough time has passed since last sync."""
    if force:
        return True
    last = state.get("last_sync", 0)
    return (time.time() - last) >= MIN_SYNC_INTERVAL


def _is_eds_available() -> bool:
    """Check if EDS is available and functional."""
    if not _EDS_AVAILABLE:
        return False
    try:
        sr = EDataServer.SourceRegistry.new_sync()
        sources = sr.list_sources()
        # At least one calendar source should exist AND be openable
        for src in sources:
            uid = src.get_uid()
            if any(t in uid.lower() for t in CALENDAR_SOURCE_TYPES):
                # Try to open a client for this source to verify it works
                try:
                    client = ECal.Client(source=src)
                    client.open_sync()
                    # Try to actually query objects to verify the connection works
                    success, _ = client.get_object_list_sync("VEVENT", None)
                    if success:
                        return True
                except Exception:
                    continue
        return False
    except Exception:
        return False


def _get_calendar_sources() -> List[EDataServer.Source]:
    """Get all calendar-capable sources from EDS."""
    if not _EDS_AVAILABLE:
        return []
    sr = EDataServer.SourceRegistry.new_sync()
    sources = sr.list_sources()
    cal_sources = []
    for src in sources:
        uid = src.get_uid()
        # Filter for calendar sources
        if any(t in uid.lower() for t in CALENDAR_SOURCE_TYPES):
            cal_sources.append(src)
    return cal_sources


def _ics_to_event(ical_str: str, source_uid: str, source_name: str) -> Optional[Dict[str, Any]]:
    """Parse a single VEVENT from iCalendar string into mv-calendar event dict."""
    try:
        # Parse using ICalGLib
        comp = ICalGLib.Component.new_from_string(ical_str)
        if not comp:
            return None

        # Extract properties
        uid = comp.get_first_property("UID")
        uid_val = uid.get_value() if uid else uuid.uuid4().hex[:12]

        summary = comp.get_first_property("SUMMARY")
        title = summary.get_value() if summary else "(no title)"

        dtstart = comp.get_first_property("DTSTART")
        dtend = comp.get_first_property("DTEND")

        all_day = False
        start_str = ""
        end_str = ""

        if dtstart:
            dt_val = dtstart.get_value()
            if dt_val:
                # Check if it's a DATE (all-day) or DATETIME
                if dtstart.get_parameters().get("VALUE") == "DATE":
                    all_day = True
                    start_str = dt_val.strftime("%Y%m%d")
                else:
                    start_str = dt_val.strftime("%Y%m%dT%H%M%S")

        if dtend:
            dt_val = dtend.get_value()
            if dt_val:
                if all_day or dtend.get_parameters().get("VALUE") == "DATE":
                    end_str = dt_val.strftime("%Y%m%d")
                else:
                    end_str = dt_val.strftime("%Y%m%dT%H%M%S")

        if not start_str:
            return None

        if not end_str:
            end_str = start_str

        location_prop = comp.get_first_property("LOCATION")
        location = location_prop.get_value() if location_prop else ""

        desc_prop = comp.get_first_property("DESCRIPTION")
        description = desc_prop.get_value() if desc_prop else ""

        # RRULE
        rrule_prop = comp.get_first_property("RRULE")
        repeat = "none"
        if rrule_prop:
            rrule_val = rrule_prop.get_value()
            if rrule_val:
                freq = rrule_val.get_freq()
                if freq == ICalGLib.RecurrenceFreq.DAILY:
                    repeat = "daily"
                elif freq == ICalGLib.RecurrenceFreq.WEEKLY:
                    repeat = "weekly"
                elif freq == ICalGLib.RecurrenceFreq.MONTHLY:
                    repeat = "monthly"
                elif freq == ICalGLib.RecurrenceFreq.YEARLY:
                    repeat = "yearly"

        # Namespace the calendar name with source UID to avoid collisions
        cal_name = f"{source_name} ({source_uid})"
        account_name = "EDS Sync"

        return {
            "id": uid_val,
            "title": title,
            "account": account_name,
            "calendar": cal_name,
            "start": start_str,
            "end": end_str,
            "location": location,
            "description": description,
            "all_day": all_day,
            "repeat": repeat,
            "notified": [],
            "_eds_source_uid": source_uid,
            "_eds_ical": ical_str,
        }
    except Exception:
        return None


def _sync_source(client: ECal.Client, source: EDataServer.Source,
                 state: Dict[str, Any]) -> Tuple[int, int]:
    """Sync a single EDS source. Returns (imported_count, error_count)."""
    imported = 0
    errors = 0

    try:
        # Get all VEVENTs from this source
        success, objs = client.get_object_list_sync("VEVENT", None)
        if not success:
            return 0, 1

        source_uid = source.get_uid()
        source_name = source.get_display_name()

        # Get existing events from this source to detect changes
        store = load_store()
        existing_events = {
            ev.get("_eds_ical", ""): ev
            for ev in store.get("events", [])
            if ev.get("_eds_source_uid") == source_uid
        }

        new_events = []
        for obj in objs:
            ical_str = obj.get_component_as_string()
            if not ical_str:
                errors += 1
                continue

            ev = _ics_to_event(ical_str, source_uid, source_name)
            if ev:
                # Check if event already exists (by iCal content hash)
                if ical_str not in existing_events:
                    new_events.append(ev)
                    imported += 1

        # Add new events to store
        if new_events:
            store["events"].extend(new_events)
            save_store(data=store)

    except Exception as e:
        errors += 1

    return imported, errors


def sync_eds(force: bool = False, on_progress: Optional[callable] = None) -> Dict[str, Any]:
    """
    One-shot sync from EDS to mv-calendar.

    Args:
        force: Skip interval check, sync immediately
        on_progress: Optional callback(msg) for progress updates

    Returns:
        dict with keys: success (bool), imported (int), errors (int),
        skipped (bool), reason (str), sources_synced (list)
    """
    result = {
        "success": False,
        "imported": 0,
        "errors": 0,
        "skipped": False,
        "reason": "",
        "sources_synced": [],
    }

    # Load sync state
    state = _load_sync_state()

    # Check if we should sync
    if not _should_sync(state, force):
        result["skipped"] = True
        result["reason"] = f"Last sync was {int((time.time() - state.get('last_sync', 0)) / 60)} min ago; minimum interval is 15 min"
        if on_progress:
            on_progress(result["reason"])
        return result

    # Check EDS availability
    if not _is_eds_available():
        result["skipped"] = True
        result["reason"] = "EDS not available (evolution-calendar-factory not running or no calendar sources)"
        if on_progress:
            on_progress(result["reason"])
        return result

    if on_progress:
        on_progress("Connecting to EDS...")

    try:
        sources = _get_calendar_sources()
        if not sources:
            result["skipped"] = True
            result["reason"] = "No calendar sources found in EDS"
            if on_progress:
                on_progress(result["reason"])
            return result

        if on_progress:
            on_progress(f"Found {len(sources)} calendar source(s)")

        # Ensure EDS Sync account exists in mv-calendar store
        store = load_store()
        if "EDS Sync" not in store["accounts"]:
            store["accounts"]["EDS Sync"] = {"calendars": {}}

        total_imported = 0
        total_errors = 0

        for source in sources:
            source_uid = source.get_uid()
            source_name = source.get_display_name()

            if on_progress:
                on_progress(f"Syncing {source_name}...")

            # Create ECal client for this source
            client = ECal.Client(source=source)
            client.open_sync()

            imported, errors = _sync_source(client, source, state)
            total_imported += imported
            total_errors += errors

            if imported > 0 or errors == 0:
                result["sources_synced"].append({
                    "uid": source_uid,
                    "name": source_name,
                    "imported": imported,
                    "errors": errors,
                })

            # Update source state
            state["sources"][source_uid] = {
                "last_sync": time.time(),
                "name": source_name,
            }

        # Update global sync state
        state["last_sync"] = time.time()
        _save_sync_state(state)

        result["success"] = True
        result["imported"] = total_imported
        result["errors"] = total_errors
        result["reason"] = f"Synced {len(sources)} source(s), imported {total_imported} event(s)"
        if on_progress:
            on_progress(result["reason"])

    except Exception as e:
        result["errors"] += 1
        result["reason"] = f"Sync failed: {e}"
        if on_progress:
            on_progress(result["reason"])

    return result


def get_sync_status() -> Dict[str, Any]:
    """Get current sync status for UI display."""
    state = _load_sync_state()
    last_sync = state.get("last_sync", 0)
    sources = state.get("sources", {})

    if last_sync == 0:
        last_sync_str = "Never"
    else:
        dt = datetime.fromtimestamp(last_sync)
        last_sync_str = dt.strftime("%Y-%m-%d %H:%M")

    # Check EDS availability
    eds_available = _is_eds_available()
    source_count = 0
    if eds_available:
        source_count = len(_get_calendar_sources())

    return {
        "eds_available": eds_available,
        "source_count": source_count,
        "last_sync": last_sync,
        "last_sync_str": last_sync_str,
        "sources": sources,
        "next_sync_in": max(0, MIN_SYNC_INTERVAL - (time.time() - last_sync)),
    }


def add_sync_menu_items(window, menu: 'Gtk.Menu') -> None:
    """Add EDS sync menu items to the given menu (for CalendarWindow)."""
    # This will be called from CalendarWindow to add sync controls
    pass  # Implementation will be in mv-calendar main file


# CLI entry point for manual sync
def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        def progress(msg):
            print(msg, file=sys.stderr)
        result = sync_eds(force=True, on_progress=progress)
        print(json.dumps(result))
        return 0 if result["success"] or result["skipped"] else 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())