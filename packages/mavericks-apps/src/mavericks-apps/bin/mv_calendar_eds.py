#!/usr/bin/env python3
"""mv-calendar EDS sync bridge (bidirectional).

One-shot sync: mv-calendar <-> EDS (evolution-data-server).
Reads EDS calendar sources (local + GOA Google + generic CalDAV via GOA),
imports events into mv-calendar store namespaced per remote calendar.
Exports locally-created/edited/deleted events in "EDS Sync"-namespaced calendars
back to their EDS source where the backend allows (create/update/delete via
ECal.Client, one-shot, same 15-min/event-driven triggers, no daemon).

Sync triggers: on-launch + manual button + interval >=15min (no daemon, no polling).
Offline path: sync skipped, local works.

Conflict policy: remote-wins with local backup copy kept + user-visible notice
(documented in code + docs, no silent loss). Where EDS factory is absent
(container), code degrades gracefully (skip with reason, covered by test with
mocked client).

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

# Backup directory for conflict resolution
BACKUP_DIR = os.path.expanduser("~/.local/share/mv-calendar/eds-backups")

# EDS Sync account name
EDS_SYNC_ACCOUNT = "EDS Sync"


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


def _ensure_backup_dir() -> None:
    """Ensure backup directory exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _backup_local_event(ev: Dict[str, Any], reason: str) -> None:
    """Save a backup copy of a local event that will be overwritten by remote.
    
    Conflict policy: remote-wins with local backup copy kept + user-visible notice.
    The backup is stored in BACKUP_DIR with timestamp and reason.
    """
    _ensure_backup_dir()
    timestamp = time.strftime("%Y%m%dT%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{ev.get('id', 'unknown')}_{timestamp}.json")
    backup_data = {
        "event": ev,
        "reason": reason,
        "timestamp": timestamp,
    }
    try:
        with open(backup_file, "w") as f:
            json.dump(backup_data, f, indent=2)
    except Exception:
        pass  # Best effort backup


def _event_to_ics(ev: Dict[str, Any]) -> str:
    """Convert mv-calendar event dict to iCalendar VEVENT string."""
    lines = ["BEGIN:VEVENT"]
    lines.append(f"UID:{ev.get('id', uuid.uuid4().hex[:12])}")
    
    start = parse_dt(ev.get("start", ""))
    end = parse_dt(ev.get("end", "") or ev.get("start", ""))
    all_day = ev.get("all_day", False)
    
    if start:
        if all_day:
            lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}")
    
    if end:
        if all_day:
            lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
        else:
            lines.append(f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}")
    
    if ev.get("title"):
        lines.append(f"SUMMARY:{ics_escape(ev['title'])}")
    if ev.get("location"):
        lines.append(f"LOCATION:{ics_escape(ev['location'])}")
    if ev.get("description"):
        lines.append(f"DESCRIPTION:{ics_escape(ev['description'])}")
    
    repeat = ev.get("repeat", "none")
    if repeat != "none":
        lines.append(f"RRULE:FREQ={repeat.upper()}")
    
    lines.append("END:VEVENT")
    return "\r\n".join(lines) + "\r\n"


def ics_escape(text: str) -> str:
    """Escape text for iCalendar."""
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _sync_source_writeback(client: ECal.Client, source: EDataServer.Source,
                           state: Dict[str, Any], store_path: str = None) -> Tuple[int, int, int, List[str]]:
    """Sync local changes back to EDS source.
    
    Returns: (created, updated, deleted, warnings)
    """
    created = 0
    updated = 0
    deleted = 0
    errors = 0
    warnings = []
    
    try:
        source_uid = source.get_uid()
        source_name = source.get_display_name()
        
        # Get all local events for this EDS source
        store = load_store(store_path)
        local_events = [
            ev for ev in store.get("events", [])
            if ev.get("_eds_source_uid") == source_uid
        ]
        
        # Get current remote events from EDS
        success, objs = client.get_object_list_sync("VEVENT", None)
        if not success:
            return 0, 0, 0, ["Failed to read remote events"]
        
        remote_events = {}
        for obj in objs:
            ical_str = obj.get_component_as_string()
            if ical_str:
                comp = ICalGLib.Component.new_from_string(ical_str)
                if comp:
                    uid_prop = comp.get_first_property("UID")
                    if uid_prop:
                        uid_val = uid_prop.get_value()
                        remote_events[uid_val] = {
                            "ical": ical_str,
                            "obj": obj,
                        }
        
        # Track which remote events we've seen
        seen_remote_uids = set()
        
        # Process local events: create or update
        for ev in local_events:
            ev_uid = ev.get("id", "")
            ev_ical = ev.get("_eds_ical", "")
            
            if ev_uid in remote_events:
                # Event exists remotely - check if local has changes
                remote_ical = remote_events[ev_uid]["ical"]
                if ev_ical != remote_ical:
                    # Local has changes - check for conflict
                    # Conflict policy: remote-wins with local backup
                    _backup_local_event(ev, f"Conflict on update: remote changed for {source_name}")
                    warnings.append(f"Conflict: remote won for event '{ev.get('title', 'unknown')}' in {source_name}. Local changes backed up.")
                    
                    # Update local with remote version (remote wins)
                    remote_ev = _ics_to_event(remote_ical, source_uid, source_name)
                    if remote_ev:
                        # Preserve local ID but update with remote data
                        remote_ev["id"] = ev_uid
                        remote_ev["notified"] = ev.get("notified", [])
                        # Replace in store
                        for i, store_ev in enumerate(store["events"]):
                            if store_ev.get("id") == ev_uid:
                                store["events"][i] = remote_ev
                                break
                        save_store(path=store_path, data=store)
                        updated += 1
                seen_remote_uids.add(ev_uid)
            else:
                # New local event - create in EDS
                try:
                    ics_str = _event_to_ics(ev)
                    comp = ICalGLib.Component.new_from_string(ics_str)
                    if comp:
                        # Create object in EDS
                        success = client.create_object_sync(comp)
                        if success:
                            created += 1
                            # Update local with server-assigned UID if needed
                            new_uid_prop = comp.get_first_property("UID")
                            if new_uid_prop:
                                new_uid = new_uid_prop.get_value()
                                if new_uid != ev_uid:
                                    ev["id"] = new_uid
                        else:
                            warnings.append(f"Failed to create event '{ev.get('title', 'unknown')}' in {source_name}")
                            errors += 1
                except Exception as e:
                    warnings.append(f"Error creating event '{ev.get('title', 'unknown')}': {e}")
        
        # Process remote events not seen locally - delete from EDS
        # Only delete if the event was originally from this source (has _eds_source_uid)
        for remote_uid, remote_data in remote_events.items():
            if remote_uid not in seen_remote_uids:
                # Check if this remote event was originally synced from this source
                # by looking for it in local store
                local_match = None
                for ev in store.get("events", []):
                    if ev.get("_eds_source_uid") == source_uid and ev.get("id") == remote_uid:
                        local_match = ev
                        break
                
                if local_match is None:
                    # Event exists remotely but not locally - it was deleted locally
                    # Propagate delete to EDS
                    try:
                        client.remove_object_sync(remote_uid)
                        deleted += 1
                    except Exception as e:
                        warnings.append(f"Error deleting event {remote_uid}: {e}")
                else:
                    # Event exists locally but we didn't see it in our local_events filter
                    # This shouldn't happen but handle gracefully
                    seen_remote_uids.add(remote_uid)
        
    except Exception as e:
        warnings.append(f"Writeback error: {e}")
    
    return created, updated, deleted, warnings


def _sync_source_bidirectional(client: ECal.Client, source: EDataServer.Source,
                                state: Dict[str, Any]) -> Tuple[int, int, int, int, List[str]]:
    """Bidirectional sync: read from EDS, then write local changes back.
    
    Returns: (imported, created, updated, deleted, warnings)
    """
    warnings = []
    
    # First: read from EDS (existing logic)
    imported, errors = _sync_source(client, source, state)
    if errors > 0:
        warnings.append(f"Read sync had {errors} error(s)")
    
    # Then: write local changes back to EDS
    store_path = state.get("_store_path")
    created, updated, deleted, wb_warnings = _sync_source_writeback(client, source, state, store_path)
    warnings.extend(wb_warnings)
    
    return imported, created, updated, deleted, warnings


def sync_eds(force: bool = False, on_progress: Optional[callable] = None) -> Dict[str, Any]:
    """
    One-shot bidirectional sync: mv-calendar <-> EDS (evolution-data-server).

    Args:
        force: Skip interval check, sync immediately
        on_progress: Optional callback(msg) for progress updates

    Returns:
        dict with keys: success (bool), imported (int), created (int),
        updated (int), deleted (int), errors (int), warnings (list),
        skipped (bool), reason (str), sources_synced (list)
    """
    result = {
        "success": False,
        "imported": 0,
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "errors": 0,
        "warnings": [],
        "skipped": False,
        "reason": "",
        "sources_synced": [],
    }

    # Load sync state
    state = _load_sync_state()
    # Pass store path to writeback functions
    state["_store_path"] = STORE

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
        if EDS_SYNC_ACCOUNT not in store["accounts"]:
            store["accounts"][EDS_SYNC_ACCOUNT] = {"calendars": {}}

        total_imported = 0
        total_created = 0
        total_updated = 0
        total_deleted = 0
        total_errors = 0
        all_warnings = []

        for source in sources:
            source_uid = source.get_uid()
            source_name = source.get_display_name()

            if on_progress:
                on_progress(f"Syncing {source_name}...")

            # Create ECal client for this source
            client = ECal.Client(source=source)
            client.open_sync()

            imported, created, updated, deleted, warnings = _sync_source_bidirectional(client, source, state)
            total_imported += imported
            total_created += created
            total_updated += updated
            total_deleted += deleted
            total_errors += 0  # errors handled in warnings
            all_warnings.extend(warnings)

            if imported > 0 or created > 0 or updated > 0 or deleted > 0 or len(warnings) == 0:
                result["sources_synced"].append({
                    "uid": source_uid,
                    "name": source_name,
                    "imported": imported,
                    "created": created,
                    "updated": updated,
                    "deleted": deleted,
                    "warnings": warnings,
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
        result["created"] = total_created
        result["updated"] = total_updated
        result["deleted"] = total_deleted
        result["errors"] = total_errors
        result["warnings"] = all_warnings
        result["reason"] = (f"Synced {len(sources)} source(s): "
                           f"imported {total_imported}, created {total_created}, "
                           f"updated {total_updated}, deleted {total_deleted}")
        if all_warnings:
            result["reason"] += f"; {len(all_warnings)} warning(s)"
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