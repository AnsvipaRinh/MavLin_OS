#!/usr/bin/env python3
"""Headless tests for mv-calendar.

Covers the pure store/logic layer (no GTK widgets are instantiated):
- store round-trip, backup-on-save, corrupt-store quarantine + restore
- normalization of legacy/corrupt stores
- strict ICS datetime parsing (no silent now() fallback)
- events_for_day: timed, all-day, multi-day, invisible calendar, bad data
- repeat expansion (daily/weekly/monthly/yearly, month-end clamp, horizon)
- search matching (title + location)
- event validation (title required, end >= start)
- ICS export/import round-trip incl. escaping, folding, RRULE
- read_ics skips malformed VEVENTs
- upcoming-event notification selection + notified dedup
- geometry round-trip

Usage: python3 scripts/test-mv-calendar.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-calendar")

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


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_calendar", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_calendar", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def main():
    mv = load_app()
    check("module imports headless", True)

    with tempfile.TemporaryDirectory() as td:
        store = os.path.join(td, "calendars.json")

        data = mv.load_store(store)
        check("missing store -> default accounts",
              set(data["accounts"]) == {"Personal", "Work"}
              and data["events"] == [])

        # Test account-based structure with nested calendars
        ev1 = {"id": "e1", "title": "standup", "account": "Work", "calendar": "Work",
               "start": "20260926T093000", "end": "20260926T100000",
               "location": "Room 1", "description": "daily",
               "all_day": False, "repeat": "none", "notified": []}
        ev2 = {"id": "e2", "title": "Holiday", "account": "Personal", "calendar": "Personal",
               "start": "20261005", "end": "20261007", "location": "",
               "description": "", "all_day": True, "repeat": "none",
               "notified": []}
        data["events"] = [ev1, ev2]
        mv.save_store(store, data)
        check("store round-trip",
              mv.load_store(store)["events"] == [ev1, ev2])
        mv.save_store(store, data)
        check("backup created on save", os.path.exists(store + ".bak"))

        # corrupt store, no backup -> quarantine + fresh store + warn
        if os.path.exists(store + ".bak"):
            os.remove(store + ".bak")
        with open(store, "w") as f:
            f.write("{not json")
        warns = []
        data2 = mv.load_store(store, warns.append)
        check("corrupt store -> fresh default",
              data2["events"] == []
              and set(data2["accounts"]) == {"Personal", "Work"})
        check("corrupt store warns",
              len(warns) == 1 and "quarantined" in warns[0], str(warns))
        check("corrupt store quarantined",
              any(f.startswith("calendars.json.corrupt-")
                  for f in os.listdir(td)), str(os.listdir(td)))

        # corrupt store WITH valid backup -> restore from backup
        mv.save_store(store, {"accounts": data["accounts"],
                               "events": [ev1, ev2]})
        mv.save_store(store, {"accounts": data["accounts"],
                               "events": [ev1, ev2]})
        check("backup regenerated", os.path.exists(store + ".bak"))
        with open(store, "w") as f:
            f.write("also not json")
        warns2 = []
        data3 = mv.load_store(store, warns2.append)
        check("corrupt store restores from backup",
              data3["events"] == [ev1, ev2])
        check("restore-from-backup warns",
              len(warns2) == 1 and "restored from backup" in warns2[0],
              str(warns2))

        # normalization
        norm = mv._normalize("garbage")
        check("normalize non-dict",
              set(norm["accounts"]) == {"Personal", "Work"}
              and norm["events"] == [] and norm["geometry"] == {})
        # Account-based normalization test
        norm = mv._normalize({"accounts": {"Personal": {"calendars": {"X": "bad", "Y": {"color": "#fff"}}}},
                              "events": [{"title": "x"}, 5], "extra": 1})
        check("normalize fixes bad calendar",
              norm["accounts"]["Personal"]["calendars"]["X"] == {"color": "#888888", "visible": True}
              and norm["accounts"]["Personal"]["calendars"]["Y"]["visible"] is True)
        check("normalize drops non-dict events",
              len(norm["events"]) == 1 and norm["events"][0]["id"]
              and norm["events"][0]["all_day"] is False
              and norm["events"][0]["repeat"] == "none"
              and norm["events"][0]["notified"] == [])
        check("normalize keeps extra keys", norm.get("extra") == 1)

        # geometry round-trip
        data4 = mv.load_store(store)
        data4["geometry"] = {"x": 10, "y": 20, "w": 1050, "h": 700}
        mv.save_store(store, data4)
        check("geometry round-trip",
              mv.load_store(store)["geometry"] == data4["geometry"])

    # date parsing
    check("parse_dt datetime", mv.parse_dt("20260926T143000")
          == datetime(2026, 9, 26, 14, 30))
    check("parse_dt date", mv.parse_dt("20261005") == datetime(2026, 10, 5))
    check("parse_dt rejects garbage", mv.parse_dt("not-a-date") is None)
    check("parse_dt rejects short", mv.parse_dt("2026") is None)
    check("parse_dt rejects None", mv.parse_dt(None) is None)
    check("fmt_time", mv.fmt_time(datetime(2026, 9, 26, 9, 5)) == "09:05")

    # events_for_day - uses account-based structure
    cals = {"Personal": {"calendars": {"Personal": {"color": "#007aff", "visible": True},
                         "Hidden": {"color": "#0f0", "visible": False}}},
            "Work": {"calendars": {"Work": {"color": "#ff3b30", "visible": True}}}}
    timed = {"id": "t1", "title": "meeting", "account": "Work", "calendar": "Work",
             "start": "20260926T140000", "end": "20260926T150000"}
    allday = {"id": "t2", "title": "trip", "account": "Personal", "calendar": "Personal",
              "start": "20260926", "end": "20260928", "all_day": True}
    hidden = {"id": "t3", "title": "secret", "account": "Personal", "calendar": "Hidden",
              "start": "20260926T100000", "end": "20260926T110000"}
    bad = {"id": "t4", "title": "broken", "account": "Work", "calendar": "Work",
           "start": "garbage", "end": "garbage"}
    span = [timed, allday, hidden, bad]
    d = datetime(2026, 9, 26)
    check("events_for_day timed",
          [e["id"] for e in mv.events_for_day(span, cals, d)] == ["t1", "t2"])
    check("events_for_day skips invisible calendar",
          all(e["id"] != "t3" for e in mv.events_for_day(span, cals, d)))
    check("events_for_day skips unparseable start",
          all(e["id"] != "t4" for e in mv.events_for_day(span, cals, d)))
    check("events_for_day multi-day span",
          [e["id"] for e in mv.events_for_day(span, cals,
                                               datetime(2026, 9, 27))] == ["t2"])
    check("events_for_day query filter",
          [e["id"] for e in mv.events_for_day(span, cals, d, "meeting")]
          == ["t1"])
    check("events_for_day query no match",
          mv.events_for_day(span, cals, d, "zzz") == [])

    # repeat expansion
    daily = {"start": "20260926T090000", "end": "20260928T090000",
             "repeat": "daily"}
    check("repeat daily",
          [s.day for s in mv.iter_event_dates(daily)] == [26, 27, 28])
    weekly = {"start": "20260923T090000", "end": "20261007T090000",
              "repeat": "weekly"}
    check("repeat weekly",
          [s.day for s in mv.iter_event_dates(weekly)] == [23, 30, 7])
    monthly = {"start": "20260131T090000", "end": "20260531T090000",
               "repeat": "monthly"}
    check("repeat monthly month-end clamp",
          [(s.month, s.day) for s in mv.iter_event_dates(monthly)]
          == [(1, 31), (2, 28), (3, 31), (4, 30), (5, 31)])
    yearly = {"start": "20240229T090000", "end": "20280229T090000",
              "repeat": "yearly"}
    check("repeat yearly leap clamp",
          [(s.year, s.month, s.day) for s in mv.iter_event_dates(yearly)]
          == [(2024, 2, 29), (2025, 2, 28), (2026, 2, 28),
              (2027, 2, 28), (2028, 2, 29)])
    none = {"start": "20260926T090000", "end": "20260926T100000",
            "repeat": "none"}
    check("repeat none single",
          len(list(mv.iter_event_dates(none))) == 1)
    check("repeat bad freq treated as none",
          len(list(mv.iter_event_dates({"start": "20260926T090000",
                                        "end": "20260927T090000",
                                        "repeat": "hourly"}))) == 1)
    check("repeat no start yields nothing",
          list(mv.iter_event_dates({"start": "bad", "end": "bad",
                                    "repeat": "daily"})) == [])
    check("repeat infinite bounded by horizon",
          len(list(mv.iter_event_dates({"start": "20200101T090000",
                                        "end": "29990101T090000",
                                        "repeat": "daily"}))) <= 1096)

    # search
    ev = {"title": "Dentist", "location": "Main Street"}
    check("matches title case-insensitive", mv.matches_event(ev, "dentist"))
    check("matches location", mv.matches_event(ev, "main"))
    check("matches empty query", mv.matches_event(ev, ""))
    check("non-match", not mv.matches_event(ev, "doctor"))

    # validation
    check("validate empty title",
          mv.validate_event("", datetime(2026, 9, 26, 10),
                            datetime(2026, 9, 26, 11), False)
          == "Title is required.")
    check("validate end before start",
          mv.validate_event("x", datetime(2026, 9, 26, 11),
                            datetime(2026, 9, 26, 10), False)
          == "End time must be after start time.")
    check("validate ok",
          mv.validate_event("x", datetime(2026, 9, 26, 10),
                            datetime(2026, 9, 26, 11), False) is None)
    check("validate all-day ignores times",
          mv.validate_event("x", datetime(2026, 9, 26, 11),
                            datetime(2026, 9, 26, 10), True) is None)

    # ICS export/import round-trip
    with tempfile.TemporaryDirectory() as td:
        ics_path = os.path.join(td, "cal.ics")
        events = [
            {"id": "abc123", "title": "Team, standup; daily",
             "account": "Work", "calendar": "Work", "start": "20260926T093000",
             "end": "20260926T100000", "location": "Room 1, Bldg; 2",
             "description": "Line one\nLine two", "all_day": False,
             "repeat": "weekly", "notified": []},
            {"id": "def456", "title": "Holiday", "account": "Personal", "calendar": "Personal",
             "start": "20261005", "end": "20261007", "location": "",
             "description": "", "all_day": True, "repeat": "none",
             "notified": []},
        ]
        mv.write_ics(ics_path, events)
        with open(ics_path, newline="") as f:
            raw = f.read()
        check("ics uses CRLF", "\r\n" in raw)
        check("ics escapes semicolon", r"standup\; daily" in raw)
        check("ics escapes comma", r"Team\, standup" in raw)
        check("ics escapes newline", "Line one\\nLine two" in raw)
        check("ics all-day VALUE=DATE", "DTSTART;VALUE=DATE:20261005" in raw)
        check("ics RRULE", "RRULE:FREQ=WEEKLY" in raw)
        check("ics folds long lines",
              all(len(line) <= 76 for line in raw.split("\r\n")),
              str([len(l) for l in raw.split("\r\n") if len(l) > 76]))

        imported, errors = mv.read_ics(ics_path)
        check("ics import count", len(imported) == 2 and errors == 0,
              "%d events, %d errors" % (len(imported), errors))
        e1 = next(e for e in imported if e["id"] == "abc123")
        check("ics import summary unescaped", e1["title"] == "Team, standup; daily")
        check("ics import location unescaped",
              e1["location"] == "Room 1, Bldg; 2")
        check("ics import description unescaped",
              e1["description"] == "Line one\nLine two")
        check("ics import repeat", e1["repeat"] == "weekly")
        check("ics import all-day", imported[1]["all_day"] is True)
        check("ics import all-day start",
              imported[1]["start"] == "20261005")

        # malformed ICS: one good VEVENT, one broken
        bad_ics = os.path.join(td, "bad.ics")
        with open(bad_ics, "w") as f:
            f.write("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
                    "SUMMARY:no dates\r\nEND:VEVENT\r\n"
                    "BEGIN:VEVENT\r\nSUMMARY:good\r\n"
                    "DTSTART:20260926T100000\r\nEND:VEVENT\r\n"
                    "END:VCALENDAR\r\n")
        imported2, errors2 = mv.read_ics(bad_ics)
        check("ics skips malformed vevent",
              len(imported2) == 1 and errors2 == 1
              and imported2[0]["title"] == "good",
              "%d events, %d errors" % (len(imported2), errors2))

    # upcoming notifications
    base = datetime(2026, 9, 26, 12, 0, 0)
    soon = {"id": "u1", "title": "in 10 min", "start": "20260926T121000",
            "end": "20260926T130000", "all_day": False, "notified": []}
    later = {"id": "u2", "title": "in 2 hours", "start": "20260926T140000",
             "end": "20260926T150000", "all_day": False, "notified": []}
    past = {"id": "u3", "title": "already started", "start": "20260926T110000",
            "end": "20260926T120000", "all_day": False, "notified": []}
    done = {"id": "u4", "title": "notified already", "start": "20260926T121000",
            "end": "20260926T130000", "all_day": False,
            "notified": ["2026-09-26T12:10"]}
    allday_ev = {"id": "u5", "title": "all-day today", "start": "20260926",
                 "end": "20260926", "all_day": True, "notified": []}
    bad_ev = {"id": "u6", "title": "broken", "start": "junk", "end": "junk",
              "all_day": False, "notified": []}
    out = mv.check_upcoming([soon, later, past, done, allday_ev, bad_ev],
                            within_min=15, now_dt=base)
    check("check_upcoming picks only due-soon unnotified",
          [e["id"] for e in out] == ["u1"], str([e["id"] for e in out]))

    # CLI entry point with mocked notify-send (dates relative to real now)
    with tempfile.TemporaryDirectory() as td:
        store = os.path.join(td, "calendars.json")
        in10 = (datetime.now() + timedelta(minutes=10)).strftime(
            "%Y%m%dT%H%M%S")
        soon_rel = {"id": "u1", "title": "in 10 min", "start": in10,
                    "end": "20990101T000000", "all_day": False,
                    "notified": []}
        mv.save_store(store, {"accounts": mv.DEFAULT_ACCOUNTS,
                               "events": [soon_rel]})
        calls = []
        orig_sub = mv.subprocess
        mv.subprocess = SimpleNamespace(
            run=lambda args: calls.append(args) or SimpleNamespace(returncode=0))
        try:
            mv.STORE = store
            rc = mv.check_upcoming_cli()
        finally:
            mv.subprocess = orig_sub
            mv.STORE = os.path.expanduser(
                "~/.local/share/mv-calendar/calendars.json")
        check("cli exits 0", rc == 0)
        check("cli notifies once", len(calls) == 1
              and calls[0][2].endswith("in 10 min"), str(calls))
        expected_key = datetime.strptime(in10, "%Y%m%dT%H%M%S").strftime(
            "%Y-%m-%dT%H:%M")
        check("cli marks notified",
              mv.load_store(store)["events"][0]["notified"] == [expected_key])
        calls.clear()
        orig_sub = mv.subprocess
        mv.subprocess = SimpleNamespace(
            run=lambda args: calls.append(args) or SimpleNamespace(returncode=0))
        try:
            mv.check_upcoming_cli()
        finally:
            mv.subprocess = orig_sub
        check("cli second run is quiet", calls == [], str(calls))

    # P1-C2: timer one-shot must not import Gtk (lazy-import fix)
    code = (
        "import sys; sys.argv=['mv-calendar','--check-upcoming'];"
        "import importlib.machinery as im, importlib.util as iu;"
        "ld=im.SourceFileLoader('app',%r); sp=iu.spec_from_loader('app',ld);"
        "m=iu.module_from_spec(sp); ld.exec_module(m);"
        "print('GTK' if any(k.startswith('gi.repository.Gtk') "
        "for k in sys.modules) else 'NOGTK')" % APP_PATH)
    p = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=60)
    check("timer path skips Gtk import", p.stdout.strip() == "NOGTK",
          (p.stdout + p.stderr).strip()[:200])

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())