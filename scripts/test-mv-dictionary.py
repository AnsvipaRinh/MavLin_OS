#!/usr/bin/env python3
"""Headless tests for mv-dictionary.

Pure-logic section (no GTK widgets, no user store touched):
- offline source resolution: built-in glossary, dictd, system word list
- word-of-the-day determinism
- history/bookmarks store round-trip, limits, corrupt/junk safety
- HTML escaping in generated pages
- speak() backend detection

GUI smoke (real GTK on $DISPLAY, skipped headless):
- construction, web mode vs local mode (WebKit2 absent)
- search, search-as-you-type debounce, tab switching, keyboard shortcuts
- bookmark toggle + persistence, history sidebar + empty state
- word-of-the-day banner, argv word prefill
- load-failed handler signature (offline error page)

Usage: python3 scripts/test-mv-dictionary.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-dictionary")

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


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


def load_app():
    loader = importlib.machinery.SourceFileLoader("mv_dictionary", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_dictionary", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def key_event(keyval, ctrl=False):
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.keyval = keyval
    if ctrl:
        ev.state = Gdk.ModifierType.CONTROL_MASK
    return ev


def test_pure(m):
    src, text = m.local_definition("apple")
    check("glossary hit", src == "built-in glossary" and "fruit" in text,
          "%s %s" % (src, text))
    check("glossary case-insensitive",
          m.local_definition("APPLE")[0] == "built-in glossary")
    check("glossary miss no dictd", m.local_definition("xyzzyplugh") is None,
          str(m.local_definition("xyzzyplugh")))

    wod_word, wod_def = m.word_of_the_day()
    check("wod word in glossary", wod_word in m.GLOSSARY, wod_word)
    check("wod def matches", wod_def == m.GLOSSARY[wod_word])
    import datetime
    day = datetime.date.today().timetuple().tm_yday
    expected = sorted(m.GLOSSARY)[day % len(m.GLOSSARY)]
    check("wod deterministic by day-of-year", wod_word == expected,
          "%s != %s" % (wod_word, expected))

    with tempfile.TemporaryDirectory() as tmp:
        hpath = os.path.join(tmp, "history.json")
        with mock.patch.object(m, "HISTORY_FILE", hpath):
            check("history missing file", m.load_history() == [])
            m.save_history(["a", "b", "c"])
            check("history round-trip", m.load_history() == ["a", "b", "c"])
            m.save_history(["x"] * 60)
            check("history limit 50", len(m.load_history()) == 50,
                  str(len(m.load_history())))
            with open(hpath, "w") as f:
                f.write("{not json")
            check("history corrupt empty", m.load_history() == [])
            with open(hpath, "w") as f:
                f.write('{"not": "a list"}')
            check("history non-list empty", m.load_history() == [])
            with open(hpath, "w") as f:
                f.write('["ok", 42, null, "fine"]')
            check("history junk filtered",
                  m.load_history() == ["ok", "fine"], str(m.load_history()))

        bpath = os.path.join(tmp, "bookmarks.json")
        with mock.patch.object(m, "BOOKMARKS_FILE", bpath):
            check("bookmarks missing file", m.load_bookmarks() == [])
            m.save_bookmarks(["finder", "dock"])
            check("bookmarks round-trip",
                  m.load_bookmarks() == ["finder", "dock"])
            with open(bpath, "w") as f:
                f.write("corrupt{")
            check("bookmarks corrupt empty", m.load_bookmarks() == [])

    with mock.patch.object(m.shutil, "which", return_value=None):
        check("dictd absent returns None", m.query_dictd("apple") is None)
    check("wordlist non-alpha false", m.word_in_wordlist("foo123") is False)
    check("wordlist empty false", m.word_in_wordlist("") is False)

    with mock.patch.object(m.shutil, "which", return_value=None):
        check("speak no backend false", m.speak("apple") is False)
    with mock.patch.object(m.shutil, "which",
                           side_effect=lambda b: "/usr/sbin/espeak-ng"
                           if b == "espeak-ng" else None):
        with mock.patch.object(m.subprocess, "Popen") as P:
            check("speak spawns espeak-ng", m.speak("apple") is True)
            args = P.call_args[0][0]
            check("speak passes word", args[-1] == "apple", str(args))

    page = m.apple_definition("<script>alert(1)</script>")
    check("apple html escaped", "<script>alert(1)</script>" not in page
          and "&lt;script&gt;" in page, page[:200])
    page2 = m.definition_html("a<b", "x&y", "src")
    check("definition html escaped", "a<b" not in page2 and "x&amp;y" in page2)

    check("offline html mentions offline", "Offline" in m.OFFLINE_HTML)
    check("welcome html has wod", "Word of the Day" in m.welcome_html())
    welcome = m.welcome_html()
    check("welcome html embeds mavericks css",
          "font-family: Georgia" in welcome and "#f7f4ec" in welcome)
    check("apple page has leather band",
          "apple-band" in m.apple_definition("finder"))
    check("apple page not-found styled",
          "not-found" in m.apple_definition("xyzzy"))


def test_gui(m):
    if not HAS_DISPLAY:
        print("SKIP - GUI smoke (no display)")
        return
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk

    with tempfile.TemporaryDirectory() as tmp:
        hpath = os.path.join(tmp, "history.json")
        bpath = os.path.join(tmp, "bookmarks.json")
        cdir = os.path.join(tmp, "cache")
        with mock.patch.object(m, "HISTORY_FILE", hpath), \
             mock.patch.object(m, "BOOKMARKS_FILE", bpath), \
             mock.patch.object(m, "CACHE_DIR", cdir):
            app = m.DictionaryWindow()
            Gtk.main_iteration_do(False)
            check("window constructs", app is not None)
            check("web mode detected", app.web_mode if hasattr(app, "web_mode")
                  else m.WebKit2 is not None)
            check("four tabs",
                  len(app.source_stack.get_children()) == 4,
                  str(len(app.source_stack.get_children())))
            check("wod banner visible", app.wod_banner.get_visible())

            for view in (app.dict_view, app.thes_view,
                         app.wiki_view, app.apple_view):
                view.load_html = mock.MagicMock()
                view.load_uri = mock.MagicMock()

            app.search_entry.set_text("finder")
            app.on_search(app.search_entry)
            Gtk.main_iteration_do(False)
            check("search sets current word", app.current_word == "finder")
            check("search loads apple tab",
                  app.apple_view.load_html.called)
            check("search records history", app.history == ["finder"])
            check("history persisted", m.load_history() == ["finder"])
            check("bookmark button sensitive",
                  app.bookmark_btn.get_sensitive())
            check("speak button sensitive", app.speak_btn.get_sensitive())

            app.bookmark_btn.set_active(True)
            check("bookmark added", app.bookmarks == ["finder"])
            check("bookmark persisted", m.load_bookmarks() == ["finder"])
            app.bookmark_btn.set_active(False)
            check("bookmark removed", app.bookmarks == [])

            app.hist_btn.set_active(True)
            Gtk.main_iteration_do(False)
            check("history revealer open",
                  app.history_revealer.get_reveal_child())
            check("history row populated",
                  len(app.history_list.get_children()) == 1)

            app.search_entry.set_text("dock")
            app.on_search(app.search_entry)
            app.search_entry.set_text("finder")
            app.on_search(app.search_entry)
            check("history dedupes", app.history == ["finder", "dock"],
                  str(app.history))

            app.on_search_changed(app.search_entry)
            check("search-as-you-type schedules",
                  app._search_timeout != 0)
            app._cancel_search()
            check("search cancel clears timeout", app._search_timeout == 0)

            app.search_entry.set_text("ab")
            app._deferred_search(app._search_gen)
            check("deferred search fires", app.current_word == "ab")
            app.search_entry.set_text("x")
            app._deferred_search(app._search_gen)
            check("deferred search ignores short", app.current_word == "ab")
            app.search_entry.set_text("somethingelse")
            import time
            time.sleep(0.4)
            Gtk.main_iteration_do(False)
            check("superseded timeout no spurious search",
                  app.current_word == "ab")

            app.emit("key-press-event", key_event(Gdk.KEY_1, ctrl=True))
            Gtk.main_iteration_do(False)
            check("ctrl+1 switches tab",
                  app.source_stack.get_visible_child_name() == "dictionary",
                  app.source_stack.get_visible_child_name())
            app.emit("key-press-event", key_event(Gdk.KEY_3, ctrl=True))
            Gtk.main_iteration_do(False)
            check("ctrl+3 switches tab",
                  app.source_stack.get_visible_child_name() == "wikipedia",
                  app.source_stack.get_visible_child_name())
            app.emit("key-press-event", key_event(Gdk.KEY_l, ctrl=True))
            check("ctrl+l focuses search",
                  app.search_entry.is_focus()
                  or app.search_entry.get_mapped())
            app.search_entry.set_text("something")
            app.emit("key-press-event", key_event(Gdk.KEY_Escape))
            check("escape clears search",
                  app.search_entry.get_text() == "")

            app.search_entry.set_text("finder")
            app.on_search(app.search_entry)
            app.emit("key-press-event", key_event(Gdk.KEY_b, ctrl=True))
            check("ctrl+b bookmarks", app.bookmark_btn.get_active())
            app.emit("key-press-event", key_event(Gdk.KEY_b, ctrl=True))
            check("ctrl+b unbmbookmarks", not app.bookmark_btn.get_active())

            fake_view = mock.MagicMock()
            result = app.on_load_failed(fake_view, 0, "http://x",
                                        Exception("boom"))
            check("load-failed handler runs", fake_view.load_html.called)
            check("load-failed returns True", result is True)

            app.wod_banner.emit("response", Gtk.ResponseType.CLOSE)
            Gtk.main_iteration_do(False)
            check("wod banner dismisses", not app.wod_banner.get_visible())

            app.destroy()

            app2 = m.DictionaryWindow()
            Gtk.main_iteration_do(False)
            check("history restored", app2.history == ["finder", "ab", "dock"],
                  str(app2.history))
            app2.hist_btn.set_active(True)
            Gtk.main_iteration_do(False)
            check("history rows restored",
                  len(app2.history_list.get_children()) == 3)
            app2.destroy()

            app3 = m.DictionaryWindow()
            Gtk.main_iteration_do(False)
            app3.hist_btn.set_active(True)
            Gtk.main_iteration_do(False)
            for child in list(app3.history_list.get_children()):
                app3.history_list.remove(child)
            app3.history = []
            app3.refresh_history()
            check("history empty state",
                  len(app3.history_list.get_children()) == 1)
            lbl = app3.history_list.get_children()[0].get_child()
            check("history empty text", "No recent" in lbl.get_label(),
                  lbl.get_label())
            app3.destroy()

            with mock.patch.object(m, "WebKit2", None):
                local = m.DictionaryWindow()
                Gtk.main_iteration_do(False)
                check("local mode constructs", local is not None)
                check("local mode view type",
                      type(local.dict_view).__name__ == "LocalView")
                local.search_entry.set_text("finder")
                local.on_search(local.search_entry)
                Gtk.main_iteration_do(False)
                check("local mode search works",
                      local.current_word == "finder")
                local.search_entry.set_text("xyzzy")
                local.on_search(local.search_entry)
                Gtk.main_iteration_do(False)
                check("local mode unknown word",
                      local.current_word == "xyzzy")
                local.thes_view.load_uri("https://example.com")
                check("local mode uri degrades",
                      "unavailable" in local.thes_view.buf.get_text(
                          local.thes_view.buf.get_start_iter(),
                          local.thes_view.buf.get_end_iter(), False))
                local.destroy()

            real_webkit = m.WebKit2
            with mock.patch.object(m.shutil, "which", return_value=None):
                m.WebKit2 = None
                noespeak = m.DictionaryWindow()
                Gtk.main_iteration_do(False)
                check("speak button hidden without espeak",
                      not noespeak.speak_btn.get_visible())
                noespeak.destroy()
                m.WebKit2 = real_webkit

            app4 = m.run("apple")
            Gtk.main_iteration_do(False)
            check("run() prefills word", app4.current_word == "apple")
            check("run() records history", "apple" in app4.history)
            app4.destroy()


def main():
    m = load_app()
    test_pure(m)
    test_gui(m)
    print("\n%d passed, %d failed" % (ok.count, len(bad.failures)))
    return 1 if bad.failures else 0


if __name__ == "__main__":
    sys.exit(main())
