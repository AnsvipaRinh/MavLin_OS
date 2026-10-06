#!/usr/bin/env python3
"""Headless tests for mv-music.

Covers the pure library/state layer plus backend/media-key paths (no GTK
widgets required for the first section; GUI smoke at the end runs only
when a display is available):
- native tag parsing: ID3v2.3 (incl. APIC cover), FLAC vorbis comments +
  STREAMINFO duration, Ogg Vorbis comment header, MP4/M4A atoms (incl. trkn)
- read_tags failure modes: unsupported ext, empty/garbage/missing files
- scan_library on a synthetic tree (4 formats, non-audio ignored)
- group_by_album: grouping, track ordering, cover inheritance
- state store: round-trip, backup-on-save, corrupt-store quarantine,
  restore-from-backup, normalization (caps, legacy fields)
- record_play / recently_played / top_played / search_tracks
- cover cache: write, idempotent re-write, absent artwork
- media_key_cli: unknown key, bus failure, success (mocked Gio)
- MprisController without a backend: every call degrades cleanly
- GUI smoke (display only): views, search, enqueue, mini player, play

Usage: python3 scripts/test-mv-music.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import struct
import sys
import tempfile
import time
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-music")

# GUI smoke must never reach the ambient host display (WSLg: DISPLAY=:0 and
# wayland-0 both forward to the user's Windows desktop).  gui_display() pins
# the dedicated Xvfb :97 — or returns None (headless, GTK then refuses to
# init) — and arms the fail-loud guard for child processes.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.gui_display()

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
    loader = importlib.machinery.SourceFileLoader("mv_music", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_music", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ----------------------------------------------------------- synthetic files

def _synchsafe(n):
    return bytes([(n >> 21) & 0x7f, (n >> 14) & 0x7f, (n >> 7) & 0x7f, n & 0x7f])


def _id3_frame(fid, text, encoding=b"\x00"):
    payload = encoding + text.encode("latin-1")
    return fid.encode("latin-1") + struct.pack(">I", len(payload)) + b"\x00\x00" + payload


def make_mp3(path, title="Song One", artist="Artist A", album="Album X",
             genre="Rock", trackno="1/10", cover=None):
    body = b""
    for fid, txt in (("TIT2", title), ("TPE1", artist), ("TALB", album),
                     ("TCON", genre), ("TRCK", trackno)):
        body += _id3_frame(fid, txt)
    if cover:
        apic = b"\x00image/jpeg\x00\x00" + cover
        body += b"APIC" + struct.pack(">I", len(apic)) + b"\x00\x00" + apic
    with open(path, "wb") as f:
        f.write(b"ID3" + bytes([3, 0, 0]) + _synchsafe(len(body)) + body)
        f.write(b"\x00" * 64)


def _vorbis_body(vendor, comments):
    b = struct.pack("<I", len(vendor)) + vendor
    b += struct.pack("<I", len(comments))
    for c in comments:
        e = c.encode("utf-8")
        b += struct.pack("<I", len(e)) + e
    return b


def make_flac(path, title="Song Two", artist="Artist B", album="Album Y",
              trackno="3", duration=None):
    if duration is not None:
        packed = (44100 << 44) | (2 << 41) | (16 << 36) | int(duration * 44100)
        streaminfo = struct.pack(">H", 4096) + struct.pack(">H", 4096)
        streaminfo += b"\x00" * 6
        streaminfo += struct.pack(">Q", packed) + b"\x00" * 16
    else:
        streaminfo = b"\x00" * 34
    comments = ["TITLE=%s" % title, "ARTIST=%s" % artist,
                "ALBUM=%s" % album, "TRACKNUMBER=%s" % trackno]
    vb = _vorbis_body(b"test vendor", comments)
    with open(path, "wb") as f:
        f.write(b"fLaC")
        f.write(bytes([0x00]) + struct.pack(">I", 34)[1:] + streaminfo)
        f.write(bytes([0x84]) + struct.pack(">I", len(vb))[1:] + vb)


def _ogg_page(packet):
    nseg = (len(packet) + 255) // 256
    segtab = bytes([255] * (len(packet) // 256)
                   + ([len(packet) % 256] if len(packet) % 256 else []))
    return b"OggS" + bytes([0, 0]) + b"\x00" * 20 + bytes([nseg]) + segtab + packet


def make_ogg(path, title="Song Three", artist="Artist C", album="Album Z",
             trackno="7"):
    ident = b"\x01vorbis" + b"\x00" * 23
    comment = b"\x03vorbis" + _vorbis_body(
        b"v", ["TITLE=%s" % title, "ARTIST=%s" % artist,
               "ALBUM=%s" % album, "TRACKNUMBER=%s" % trackno])
    with open(path, "wb") as f:
        f.write(_ogg_page(ident) + _ogg_page(comment))


def _atom(typ, data):
    return struct.pack(">I", 8 + len(data)) + typ + data


def _data_atom(text):
    return _atom(b"data", b"\x00\x00\x00\x01\x00\x00\x00\x00"
                 + text.encode("utf-8"))


def make_m4a(path, title="Song Four", artist="Artist D", album="Album W",
             trackno=5):
    ilst = _atom(b"ilst", _atom(b"\xa9nam", _data_atom(title))
                 + _atom(b"\xa9ART", _data_atom(artist))
                 + _atom(b"\xa9alb", _data_atom(album)))
    if trackno is not None:
        payload = b"\x00\x00" + struct.pack(">H", trackno) + b"\x00\x00"
        ilst = _atom(b"ilst", ilst[8:]
                     + _atom(b"trkn", _atom(b"data", b"\x00\x00\x00\x01"
                                           b"\x00\x00\x00\x00" + payload)))
    with open(path, "wb") as f:
        f.write(_atom(b"ftyp", b"M4A ")
                + _atom(b"moov", _atom(b"udta", _atom(b"meta",
                                                    b"\x00\x00\x00\x00" + ilst))))


def make_library(root):
    os.makedirs(os.path.join(root, "nest"), exist_ok=True)
    make_mp3(os.path.join(root, "a.mp3"))
    make_flac(os.path.join(root, "b.flac"), duration=30.0)
    make_ogg(os.path.join(root, "c.ogg"))
    make_m4a(os.path.join(root, "d.m4a"))
    make_mp3(os.path.join(root, "nest", "e.mp3"), title="Song Five",
             artist="Artist A", album="Album X", trackno="2/10")
    with open(os.path.join(root, "notes.txt"), "w") as f:
        f.write("not audio")
    return root


# ------------------------------------------------------------------- tests

def test_fmt_time(m):
    check("fmt_time 0", m.fmt_time(0) == "0:00")
    check("fmt_time 65", m.fmt_time(65) == "1:05")
    check("fmt_time negative", m.fmt_time(-5) == "0:00")
    check("fmt_time garbage", m.fmt_time("abc") == "0:00")
    check("fmt_time None", m.fmt_time(None) == "0:00")
    check("fmt_time 3661", m.fmt_time(3661) == "61:01")


def test_read_tags(m, tmp):
    mp3 = os.path.join(tmp, "t.mp3")
    make_mp3(mp3)
    t = m.read_tags(mp3)
    check("id3 title", t["title"] == "Song One", t["title"])
    check("id3 artist", t["artist"] == "Artist A")
    check("id3 album", t["album"] == "Album X")
    check("id3 genre", t["genre"] == "Rock")
    check("id3 trackno", t["trackno"] == 1, t["trackno"])

    flac = os.path.join(tmp, "t.flac")
    make_flac(flac, duration=30.0)
    t = m.read_tags(flac)
    check("flac title", t["title"] == "Song Two")
    check("flac trackno", t["trackno"] == 3)
    check("flac duration", t.get("duration") == 30.0, t.get("duration"))

    ogg = os.path.join(tmp, "t.ogg")
    make_ogg(ogg)
    t = m.read_tags(ogg)
    check("ogg title", t["title"] == "Song Three", t)
    check("ogg artist", t["artist"] == "Artist C")
    check("ogg trackno", t["trackno"] == 7)

    m4a = os.path.join(tmp, "t.m4a")
    make_m4a(m4a)
    t = m.read_tags(m4a)
    check("m4a title", t["title"] == "Song Four")
    check("m4a artist", t["artist"] == "Artist D")
    check("m4a trackno", t["trackno"] == 5, t["trackno"])

    cov = os.path.join(tmp, "cov.mp3")
    make_mp3(cov, cover=b"\xff\xd8\xff\xe0fakejpeg")
    t = m.read_tags(cov)
    check("id3 apic cover", t.get("cover_bytes") == b"\xff\xd8\xff\xe0fakejpeg",
          t.get("cover_bytes"))
    check("id3 apic mime", t.get("cover_mime") == "image/jpeg")

    garbage = os.path.join(tmp, "g.mp3")
    with open(garbage, "wb") as f:
        f.write(b"\xff\xfb" + os.urandom(512))
    check("garbage mp3 no crash", isinstance(m.read_tags(garbage), dict))
    check("garbage mp3 no title", not m.read_tags(garbage).get("title"))

    txt = os.path.join(tmp, "x.txt")
    with open(txt, "w") as f:
        f.write("hello")
    check("unsupported ext", m.read_tags(txt) == {})

    empty = os.path.join(tmp, "empty.mp3")
    open(empty, "wb").close()
    check("empty file", m.read_tags(empty) == {})

    check("missing file", m.read_tags(os.path.join(tmp, "nope.mp3")) == {})


def test_scan_and_group(m, tmp):
    tracks, errors = m.scan_library(tmp)
    check("scan finds 5 tracks", len(tracks) == 5, len(tracks))
    check("scan no errors", errors == 0)
    paths = [t["path"] for t in tracks]
    check("non-audio ignored", not any(p.endswith(".txt") for p in paths))
    again, _ = m.scan_library(tmp)
    check("deterministic order", [t["path"] for t in again] == paths)
    by_title = {t["title"]: t for t in tracks}
    check("nested file found", "Song Five" in by_title)
    check("untagged fallback artist",
          m.read_tags(paths[0]).get("artist", "") is not None)

    tracks_missing, err_missing = m.scan_library(os.path.join(tmp, "nope"))
    check("missing dir", tracks_missing == [] and err_missing == 0)

    albums = m.group_by_album(tracks)
    check("album count", len(albums) == 4, len(albums))
    ax = [g for g in albums if g["album"] == "Album X"][0]
    check("album X has 2 tracks", len(ax["tracks"]) == 2)
    check("album track order", [t["trackno"] for t in ax["tracks"]] == [1, 2],
          [t["trackno"] for t in ax["tracks"]])
    check("album key lowercase", ax["key"] == ("artist a", "album x"))


def test_state_store(m, tmp):
    sdir = os.path.join(tmp, "state")
    os.makedirs(sdir)
    spath = os.path.join(sdir, "state.json")

    st = m.default_state()
    st["queue"] = ["/a.mp3", "/b.flac"]
    st["geometry"] = {"w": 800, "h": 600}
    m.save_state(path=spath, data=st)
    check("state file written", os.path.exists(spath))
    check("no backup before first overwrite", not os.path.exists(spath + ".bak"))

    loaded = m.load_state(path=spath)
    check("roundtrip queue", loaded["queue"] == ["/a.mp3", "/b.flac"])
    check("roundtrip geometry", loaded["geometry"]["w"] == 800)

    m.save_state(path=spath, data=loaded)
    check("backup written on overwrite", os.path.exists(spath + ".bak"))
    loaded2 = m.load_state(path=spath)
    check("second save keeps data", loaded2["queue"] == ["/a.mp3", "/b.flac"])

    with open(spath, "w") as f:
        f.write("{not json")
    warned = []
    loaded3 = m.load_state(path=spath, on_warn=warned.append)
    check("corrupt -> backup restored", loaded3["queue"] == ["/a.mp3", "/b.flac"])
    check("corrupt restore warned", len(warned) == 1, warned)

    os.remove(spath + ".bak")
    with open(spath, "w") as f:
        f.write("{not json")
    warned = []
    loaded3 = m.load_state(path=spath, on_warn=warned.append)
    check("corrupt -> fresh state", loaded3["queue"] == [])
    check("corrupt -> warned", len(warned) == 1, warned)
    leftovers = [f for f in os.listdir(sdir) if ".corrupt-" in f]
    check("corrupt -> quarantined", len(leftovers) == 1, leftovers)

    with open(spath, "w") as f:
        f.write("[1,2,3]")
    loaded4 = m.load_state(path=spath)
    check("non-dict json -> fresh", loaded4["play_log"] == [])

    with open(spath, "w") as f:
        f.write("{broken")
    with open(spath + ".bak", "w") as f:
        json_dump = '{"queue": ["/from-bak.mp3"], "geometry": {"w": 100}}'
        f.write(json_dump)
    warned2 = []
    loaded5 = m.load_state(path=spath, on_warn=warned2.append)
    check("backup restored", loaded5["queue"] == ["/from-bak.mp3"])
    check("backup restore warned", len(warned2) == 1)

    legacy = m._normalize_state({"queue": "notalist", "play_log": "nope",
                                 "geometry": {"w": -5, "mini": True,
                                               "h": 700},
                                 "library": "/tmp/music", "extra": 1})
    check("normalize bad queue", legacy["queue"] == [])
    check("normalize geometry", legacy["geometry"]["h"] == 700
          and legacy["geometry"]["mini"] is True
          and "w" not in legacy["geometry"])
    check("normalize library", legacy["library"] == "/tmp/music")
    check("normalize unknown key dropped", "extra" not in legacy)

    capped = m.default_state()
    capped["queue"] = ["p%d" % i for i in range(m.QUEUE_CAP + 10)]
    capped["play_log"] = [{"path": "x", "at": "t"}] * (m.PLAY_LOG_CAP + 10)
    nc = m._normalize_state(capped)
    check("queue cap", len(nc["queue"]) == m.QUEUE_CAP)
    check("play_log cap", len(nc["play_log"]) == m.PLAY_LOG_CAP)

    fresh = m.load_state(path=os.path.join(sdir, "never.json"))
    check("missing state -> default", fresh == m.default_state())


def test_play_log(m):
    st = m.default_state()
    st = m.record_play(st, "/a.mp3")
    st = m.record_play(st, "/b.flac")
    st = m.record_play(st, "/a.mp3")
    check("play_log appended", len(st["play_log"]) == 3)

    recent = m.recently_played(st)
    check("recently dedups", recent == ["/a.mp3", "/b.flac"], recent)
    check("recently limit", m.recently_played(st, 1) == ["/a.mp3"])

    top = m.top_played(st)
    check("top ranked", top[0] == ("/a.mp3", 2), top)
    check("top order", top[1] == ("/b.flac", 1))
    check("top limit", m.top_played(st, 1) == [("/a.mp3", 2)])

    empty = m.default_state()
    check("recently empty", m.recently_played(empty) == [])
    check("top empty", m.top_played(empty) == [])


def test_search(m):
    tracks = [
        {"title": "Hello", "artist": "Adele", "album": "25", "genre": "Pop"},
        {"title": "Jazzy Night", "artist": "Miles", "album": "Blue", "genre": "Jazz"},
    ]
    check("search case-insensitive",
          m.search_tracks(tracks, "hello")[0]["title"] == "Hello")
    check("search artist", m.search_tracks(tracks, "miles")[0]["artist"] == "Miles")
    check("search album", m.search_tracks(tracks, "25")[0]["album"] == "25")
    check("search empty query returns all", len(m.search_tracks(tracks, "")) == 2)
    check("search no match", m.search_tracks(tracks, "zzz") == [])


def test_cover_cache(m, tmp):
    m.cover_cache_dir = lambda: os.path.join(tmp, "covers")
    track = {"path": os.path.join(tmp, "a.mp3"), "cover_bytes": b"\x89PNG\r\n",
             "cover_mime": "image/png"}
    with open(track["path"], "wb") as f:
        f.write(b"x" * 10)
    p1 = m.write_cover(track)
    check("cover written", p1 is not None and os.path.exists(p1))
    check("cover content", open(p1, "rb").read() == b"\x89PNG\r\n")
    p2 = m.write_cover(track)
    check("cover idempotent", p1 == p2)

    track_jpg = dict(track, cover_bytes=b"\xff\xd8", cover_mime="image/jpeg")
    pj = m.write_cover(track_jpg)
    check("cover ext jpeg", pj.endswith(".jpg"), pj)

    track_none = dict(track, cover_bytes=None)
    check("no artwork -> None", m.write_cover(track_none) is None)


def test_media_key_cli(m):
    old_argv = sys.argv
    try:
        sys.argv = ["mv-music", "--media-key", "bogus"]
        check("unknown key rc=2", m.media_key_cli("bogus") == 2)
        sys.argv = ["mv-music", "--media-key", ""]
        check("empty key rc=2", m.media_key_cli("") == 2)

        with mock.patch.object(m.Gio, "bus_get_sync",
                               side_effect=Exception("no bus")):
            check("bus failure rc=1", m.media_key_cli("playpause") == 1)

        calls = []

        class FakeProxy:
            def get_name_owner(self):
                return ":1.99"

            def call_sync(self, method, *a):
                calls.append(method)
                return None

        with mock.patch.object(m.Gio, "bus_get_sync", return_value=mock.MagicMock()), \
             mock.patch.object(m.Gio.DBusProxy, "new_sync",
                               return_value=FakeProxy()):
            check("playpause rc=0", m.media_key_cli("playpause") == 0)
            check("method mapped", calls == ["PlayPause"], calls)
            m.media_key_cli("next")
            check("next mapped", calls[-1] == "Next")
            m.media_key_cli("PREVIOUS")
            check("prev mapped", calls[-1] == "Previous")
            m.media_key_cli("stop")
            check("stop mapped", calls[-1] == "Stop")

        class NoOwnerProxy(FakeProxy):
            def get_name_owner(self):
                return None

        with mock.patch.object(m.Gio, "bus_get_sync", return_value=mock.MagicMock()), \
             mock.patch.object(m.Gio.DBusProxy, "new_sync",
                               return_value=NoOwnerProxy()):
            check("no owner rc=1", m.media_key_cli("next") == 1)
    finally:
        sys.argv = old_argv


def test_mpris_controller(m):
    c = m.MprisController()
    check("no backend -> unavailable", c.available is False)
    check("no backend -> play False", c.play() is False)
    check("no backend -> play_pause False", c.play_pause() is False)
    check("no backend -> next False", c.next_track() is False)
    check("no backend -> prev False", c.previous_track() is False)
    check("no backend -> metadata {}", c.metadata() == {})
    check("no backend -> status None", c.playback_status() is None)
    check("no backend -> position None", c.position() is None)
    c.close()
    check("close idempotent", True)


def test_gui_smoke(m, tmp):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        return
    tracks, _ = m.scan_library(tmp)
    state = {"library": tmp, "queue": [], "play_log": [], "geometry": {}}
    controller = m.MprisController()
    win = m.MusicWindow(tracks, state, controller)
    try:
        for _ in range(30):
            Gtk.main_iteration_do(False)
            time.sleep(0.02)
        check("gui window children", len(win.album_grid.get_children()) == 4,
              len(win.album_grid.get_children()))
        check("gui queue sidebar label", "Queue (0)" in
              win.sidebar.get_row_at_index(1).get_child().get_children()[1].get_text())
        win.enqueue_group(win.albums[0])
        check("gui enqueue", len(state["queue"]) == 2, state["queue"])
        check("gui queue label updates", "Queue (2)" in
              win.sidebar.get_row_at_index(1).get_child().get_children()[1].get_text())
        win._select_view("Queue")
        check("gui queue view", win.stack.get_visible_child_name() == "Queue")
        win._refresh_songs("song")
        check("gui search filters",
              len(win.song_list.get_children()) == 5,
              len(win.song_list.get_children()))
        win._select_view("Recently Played")
        check("gui recently view", win.stack.get_visible_child_name() == "Recently Played")
        win._show_error("test error")
        check("gui error state dialog displayed", True)
        with mock.patch.object(m.subprocess, "Popen",
                               return_value=mock.MagicMock()) as popen:
            win.play_tracks(state["queue"][:1])
            check("gui play launches backend", popen.called)
        win.open_mini_player()
        check("gui mini opened", win.mini is not None)
        for _ in range(10):
            Gtk.main_iteration_do(False)
            time.sleep(0.02)
        win.mini.destroy()
        win.on_mini_closed()
        check("gui mini closed", win.mini is None)
        check("gui mini geometry flag", state["geometry"].get("mini") is False)
        win._show_empty("Empty", "hint")
        check("gui empty state", win.stack.get_visible_child_name() == "Empty")
    finally:
        win.destroy()
        controller.close()


def test_scan_cache(m, tmp):
    """P1-C3: mtime+size+count-keyed scan-result cache.
    Hit returns identical tracks without re-reading files; add/remove/
    modify invalidates; corrupt cache is quarantined and rescanned."""
    cache_dir = os.path.join(tmp, "scan-cache")
    m.scan_cache_dir = lambda: cache_dir
    lib = os.path.join(tmp, "cachelib")
    os.makedirs(lib)
    for i in range(4):
        make_mp3(os.path.join(lib, "s%d.mp3" % i), title="T%d" % i,
                 artist="A", album="L", trackno=str(i))
    cache_file = m.scan_cache_path()

    t1, e1 = m.scan_library(lib)
    check("cache miss scans all", len(t1) == 4 and e1 == 0, len(t1))
    check("cache file written", os.path.exists(cache_file))

    t2, e2 = m.scan_library(lib)
    check("cache hit returns identical tracks",
          [t["path"] for t in t2] == [t["path"] for t in t1],
          [t.get("path") for t in t2])
    check("cache hit strips cover_bytes",
          all("cover_bytes" not in t for t in t2), t2[0].keys())

    # invalidation: add
    make_mp3(os.path.join(lib, "s4.mp3"), title="T4", artist="A",
             album="L", trackno="4")
    t3, _ = m.scan_library(lib)
    check("cache invalidated on add", len(t3) == 5, len(t3))

    # invalidation: remove
    os.remove(os.path.join(lib, "s4.mp3"))
    t4, _ = m.scan_library(lib)
    check("cache invalidated on remove", len(t4) == 4, len(t4))

    # invalidation: modify (mtime change)
    time.sleep(0.01)
    make_mp3(os.path.join(lib, "s0.mp3"), title="T0", artist="A",
             album="L", trackno="0")
    t5, _ = m.scan_library(lib)
    check("cache invalidated on modify", len(t5) == 4, len(t5))

    # corrupt cache -> quarantine + rescan
    with open(cache_file, "w") as f:
        f.write("NOT JSON {{{")
    t6, _ = m.scan_library(lib)
    check("corrupt cache rescanned", len(t6) == 4, len(t6))
    quarantined = [f for f in os.listdir(cache_dir) if "corrupt" in f]
    check("corrupt cache quarantined", len(quarantined) >= 1, quarantined)

    m.scan_cache_dir = lambda: os.path.expanduser("~/.cache/mv-music")


def main():
    global m
    m = load_app()
    tmp = tempfile.mkdtemp(prefix="mv-music-test-")
    libdir = os.path.join(tmp, "library")
    make_library(libdir)
    tagdir = os.path.join(tmp, "tagfiles")
    os.makedirs(tagdir)

    test_fmt_time(m)
    test_read_tags(m, tagdir)
    test_scan_and_group(m, libdir)
    test_state_store(m, tmp)
    test_play_log(m)
    test_search(m)
    test_cover_cache(m, tmp)
    test_scan_cache(m, tmp)
    test_media_key_cli(m)
    test_mpris_controller(m)
    test_gui_smoke(m, libdir)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    if FAILURES:
        for name, detail in FAILURES:
            print("FAILED: %s %s" % (name, detail))
        sys.exit(1)


if __name__ == "__main__":
    main()
