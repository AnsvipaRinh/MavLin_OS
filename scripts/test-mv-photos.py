#!/usr/bin/env python3
"""Headless tests for mv-photos.

Covers the pure library/state layer (no GTK widgets required):
- image dimension parsing: PNG, JPEG, GIF, BMP, TIFF, WebP
- EXIF date parsing: JPEG APP1 with DateTimeOriginal
- read_image_dimensions failure modes: unsupported ext, empty/garbage files
- scan_library on a synthetic tree (multiple formats, non-image ignored)
- group_by_moment: date grouping, sorting, unknown dates
- search_photos: filename and date matching
- state store: round-trip, backup-on-save, corrupt-store quarantine,
  restore-from-backup, normalization
- toggle_favorite: add/remove
- albums: add/remove, add/remove photo
- record_import: append, cap
- photos_for_album: filtering
- thumb_path: deterministic, changes with mtime
- rotate_image: graceful failure when no backend
- open_in_editor: graceful failure when gthumb missing

Usage: python3 scripts/test-mv-photos.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import struct
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windowless app-suite: no window today, but app code and child
# interpreters run with the ambient environment — on WSLg that is
# the user's Windows desktop.  Arm the fail-loud guard so any future
# window-mapping path dies with HOST-DISPLAY-BLOCKED (oid
# OS-window-leak2) instead of popping a window on the host.
sys.path.insert(0, os.path.join(REPO, "scripts", "gui-guard"))
import mv_gui_iso

mv_gui_iso.arm_guard()

APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-photos")

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
    loader = importlib.machinery.SourceFileLoader("mv_photos", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_photos", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ----------------------------------------------------------- synthetic files


def make_png(path, w=4, h=3):
    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", 0)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b""
    for _ in range(h):
        raw += b"\x00" + b"\xff\x00\x00" * w
    import zlib
    idat = zlib.compress(raw)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))


def make_gif(path, w=4, h=3):
    with open(path, "wb") as f:
        f.write(b"GIF89a")
        f.write(struct.pack("<HH", w, h))
        f.write(b"\xf0\x00\x00")
        f.write(b"\xff\x00\x00" * (w * h))
        f.write(b"\x3b")


def make_bmp(path, w=4, h=3):
    row_size = (w * 3 + 3) & ~3
    pixel_data = b"\x00\x00\xff" * w * h
    padding = b"\x00" * (row_size - w * 3) * h
    file_size = 14 + 40 + len(pixel_data) + len(padding)
    with open(path, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<IHHI", file_size, 0, 0, 54))
        f.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                            len(pixel_data) + len(padding), 2835, 2835, 0, 0))
        f.write(pixel_data + padding)


def make_jpeg(path, w=4, h=3, exif_date=None):
    """Minimal JPEG with SOF0 and optional EXIF APP1."""
    buf = bytearray(b"\xff\xd8")
    if exif_date:
        exif = _build_exif(exif_date)
        buf += b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    buf += b"\xff\xc0" + struct.pack(">H", 11) + b"\x08"
    buf += struct.pack(">HH", h, w) + b"\x01\x01\x11\x00"
    buf += b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
    buf += b"\x7f" * 16
    buf += b"\xff\xd9"
    with open(path, "wb") as f:
        f.write(bytes(buf))


def _build_exif(date_str):
    """Build minimal EXIF TIFF blob with DateTimeOriginal."""
    tiff = bytearray(b"II")
    tiff += struct.pack("<H", 42)
    tiff += struct.pack("<I", 8)
    dt_bytes = date_str.encode("ascii") + b"\x00"
    entry_count = 1
    ifd_offset = 8
    ifd_size = 2 + entry_count * 12 + 4
    data_offset = ifd_offset + ifd_size
    tiff += struct.pack("<H", entry_count)
    tiff += struct.pack("<HHI", 0x9003, 2, len(dt_bytes))
    tiff += struct.pack("<I", data_offset)
    tiff += struct.pack("<I", 0)
    tiff += dt_bytes
    return b"Exif\x00\x00" + bytes(tiff)


def make_tiff(path, w=4, h=3):
    bo = b"II"
    e = "<"
    ifd_off = 8
    count = 2
    ifd_size = 2 + count * 12 + 4
    with open(path, "wb") as f:
        f.write(bo)
        f.write(struct.pack(e + "H", 42))
        f.write(struct.pack(e + "I", ifd_off))
        f.write(struct.pack(e + "H", count))
        f.write(struct.pack(e + "HHI", 256, 4, 1))
        f.write(struct.pack(e + "I", w))
        f.write(struct.pack(e + "HHI", 257, 4, 1))
        f.write(struct.pack(e + "I", h))
        f.write(struct.pack(e + "I", 0))


def make_webp(path, w=4, h=3):
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 26))
        f.write(b"WEBP")
        f.write(b"VP8 ")
        f.write(struct.pack("<I", 10))
        f.write(b"\x00\x00\x00")
        f.write(b"\x9d\x01\x2a")
        f.write(struct.pack("<HH", w, h))
        f.write(b"\x00" * 4)


def make_library(root):
    os.makedirs(os.path.join(root, "sub"), exist_ok=True)
    make_png(os.path.join(root, "a.png"), 8, 6)
    make_jpeg(os.path.join(root, "b.jpg"), 10, 8,
              exif_date="2024:03:15 10:30:00")
    make_gif(os.path.join(root, "c.gif"), 6, 4)
    make_bmp(os.path.join(root, "d.bmp"), 12, 9)
    make_tiff(os.path.join(root, "e.tiff"), 5, 5)
    make_webp(os.path.join(root, "f.webp"), 7, 3)
    make_jpeg(os.path.join(root, "sub", "g.jpg"), 4, 4,
              exif_date="2024:03:15 14:00:00")
    make_jpeg(os.path.join(root, "h.jpg"), 4, 4,
              exif_date="2023:12:25 08:00:00")
    with open(os.path.join(root, "notes.txt"), "w") as f:
        f.write("not an image")
    return root


# ------------------------------------------------------------------- tests


def test_dimensions(m, tmp):
    png = os.path.join(tmp, "t.png")
    make_png(png, 16, 9)
    w, h = m.read_image_dimensions(png)
    check("png dims", (w, h) == (16, 9), (w, h))

    gif = os.path.join(tmp, "t.gif")
    make_gif(gif, 12, 7)
    w, h = m.read_image_dimensions(gif)
    check("gif dims", (w, h) == (12, 7), (w, h))

    bmp = os.path.join(tmp, "t.bmp")
    make_bmp(bmp, 20, 11)
    w, h = m.read_image_dimensions(bmp)
    check("bmp dims", (w, h) == (20, 11), (w, h))

    tiff = os.path.join(tmp, "t.tiff")
    make_tiff(tiff, 9, 4)
    w, h = m.read_image_dimensions(tiff)
    check("tiff dims", (w, h) == (9, 4), (w, h))

    webp = os.path.join(tmp, "t.webp")
    make_webp(webp, 14, 6)
    w, h = m.read_image_dimensions(webp)
    check("webp dims", (w, h) == (14, 6), (w, h))

    jpg = os.path.join(tmp, "t.jpg")
    make_jpeg(jpg, 33, 17)
    w, h = m.read_image_dimensions(jpg)
    check("jpeg dims", (w, h) == (33, 17), (w, h))

    txt = os.path.join(tmp, "x.txt")
    with open(txt, "w") as f:
        f.write("hello")
    check("unsupported ext", m.read_image_dimensions(txt) == (None, None))

    empty = os.path.join(tmp, "empty.png")
    open(empty, "wb").close()
    check("empty file", m.read_image_dimensions(empty) == (None, None))

    garbage = os.path.join(tmp, "g.png")
    with open(garbage, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + os.urandom(32))
    check("garbage png no crash",
          m.read_image_dimensions(garbage) == (None, None))

    check("missing file",
          m.read_image_dimensions(os.path.join(tmp, "nope.png")) == (None, None))


def test_exif_date(m, tmp):
    jpg = os.path.join(tmp, "exif.jpg")
    make_jpeg(jpg, 4, 4, exif_date="2024:03:15 10:30:00")
    dt = m.read_exif_date(jpg)
    check("exif DateTimeOriginal", dt == "2024-03-15T10:30:00", dt)

    jpg2 = os.path.join(tmp, "exif2.jpg")
    make_jpeg(jpg2, 4, 4, exif_date="2023:12:25 08:15:45")
    dt2 = m.read_exif_date(jpg2)
    check("exif date 2", dt2 == "2023-12-25T08:15:45", dt2)

    noexif = os.path.join(tmp, "noexif.jpg")
    make_jpeg(noexif, 4, 4)
    check("no exif returns None", m.read_exif_date(noexif) is None)

    png = os.path.join(tmp, "noexif.png")
    make_png(png, 4, 4)
    check("png exif returns None", m.read_exif_date(png) is None)

    check("missing file exif", m.read_exif_date(os.path.join(tmp, "n.jpg")) is None)


def test_read_image_info(m, tmp):
    """Track 2/7: combined single-open read returns dims + EXIF date."""
    jpg = os.path.join(tmp, "info.jpg")
    make_jpeg(jpg, 40, 25, exif_date="2024:07:04 12:00:00")
    w, h, dt = m.read_image_info(jpg)
    check("info jpeg dims", (w, h) == (40, 25), (w, h))
    check("info jpeg exif", dt == "2024-07-04T12:00:00", dt)

    png = os.path.join(tmp, "info.png")
    make_png(png, 33, 17)
    w, h, dt = m.read_image_info(png)
    check("info png dims", (w, h) == (33, 17), (w, h))
    check("info png no exif", dt is None, dt)

    gif = os.path.join(tmp, "info.gif")
    make_gif(gif, 11, 9)
    w, h, dt = m.read_image_info(gif)
    check("info gif dims", (w, h) == (11, 9), (w, h))

    bmp = os.path.join(tmp, "info.bmp")
    make_bmp(bmp, 22, 13)
    w, h, dt = m.read_image_info(bmp)
    check("info bmp dims", (w, h) == (22, 13), (w, h))

    tiff = os.path.join(tmp, "info.tiff")
    make_tiff(tiff, 19, 7)
    w, h, dt = m.read_image_info(tiff)
    check("info tiff dims", (w, h) == (19, 7), (w, h))

    webp = os.path.join(tmp, "info.webp")
    make_webp(webp, 15, 5)
    w, h, dt = m.read_image_info(webp)
    check("info webp dims", (w, h) == (15, 5), (w, h))

    noexif = os.path.join(tmp, "info-noexif.jpg")
    make_jpeg(noexif, 8, 8)
    w, h, dt = m.read_image_info(noexif)
    check("info jpeg no exif dims", (w, h) == (8, 8), (w, h))
    check("info jpeg no exif date", dt is None, dt)

    check("info missing file",
          m.read_image_info(os.path.join(tmp, "nope.jpg")) == (None, None, None))
    empty = os.path.join(tmp, "empty-info.png")
    open(empty, "wb").close()
    check("info empty file", m.read_image_info(empty) == (None, None, None))
    txt = os.path.join(tmp, "x-info.txt")
    with open(txt, "w") as f:
        f.write("hello")
    check("info unsupported ext", m.read_image_info(txt) == (None, None, None))


def test_scan_single_open(m, tmp):
    """Track 2/7: scan_library opens each image file exactly once."""
    import builtins
    root = make_library(os.path.join(tmp, "lib"))
    cache_dir = os.path.join(tmp, "scan-cache-open")
    m.scan_cache_dir = lambda: cache_dir
    real_open = builtins.open
    open_count = [0]

    def counting_open(*args, **kwargs):
        if args and isinstance(args[0], str) and args[0].startswith(root):
            open_count[0] += 1
        return real_open(*args, **kwargs)

    builtins.open = counting_open
    try:
        photos, errors = m.scan_library(root)
    finally:
        builtins.open = real_open
    check("scan opens each file once", open_count[0] == len(photos),
          "%d opens for %d photos" % (open_count[0], len(photos)))
    check("scan single-open no errors", errors == 0)
    m.scan_cache_dir = lambda: os.path.expanduser("~/.cache/mv-photos")


def test_scan_library(m, tmp):
    root = make_library(os.path.join(tmp, "lib"))
    photos, errors = m.scan_library(root)
    check("scan finds 8 photos", len(photos) == 8, len(photos))
    check("scan no errors", errors == 0)
    paths = [p["path"] for p in photos]
    check("non-image ignored", not any(p.endswith(".txt") for p in paths))
    check("nested found", any(p.endswith("g.jpg") for p in paths))
    check("all have filename", all(p["filename"] for p in photos))
    check("all have ext", all(p["ext"] for p in photos))
    check("all have size", all(p["size"] > 0 for p in photos))
    check("all have mtime", all(p["mtime"] > 0 for p in photos))
    check("sorted by mtime desc",
          all(photos[i]["mtime"] >= photos[i + 1]["mtime"]
              for i in range(len(photos) - 1)))

    again, _ = m.scan_library(root)
    check("deterministic order", [p["path"] for p in again] == paths)

    missing, err = m.scan_library(os.path.join(tmp, "nope"))
    check("missing dir", missing == [] and err == 0)

    empty_dir = os.path.join(tmp, "empty")
    os.makedirs(empty_dir)
    photos2, _ = m.scan_library(empty_dir)
    check("empty dir", photos2 == [])


def test_scan_cache(m, tmp):
    """P1-C3: mtime+size+count-keyed scan-result cache.
    Hit returns identical photos without re-reading files; add/remove/
    modify invalidates; corrupt cache is quarantined and rescanned."""
    cache_dir = os.path.join(tmp, "scan-cache")
    m.scan_cache_dir = lambda: cache_dir
    lib = os.path.join(tmp, "cachelib")
    os.makedirs(lib)
    for i in range(4):
        make_png(os.path.join(lib, "p%d.png" % i), 8, 6)
    cache_file = m.scan_cache_path()

    p1, e1 = m.scan_library(lib)
    check("cache miss scans all", len(p1) == 4 and e1 == 0, len(p1))
    check("cache file written", os.path.exists(cache_file))

    p2, e2 = m.scan_library(lib)
    check("cache hit returns identical photos",
          [p["path"] for p in p2] == [p["path"] for p in p1],
          [p.get("path") for p in p2])

    # invalidation: add
    make_png(os.path.join(lib, "p4.png"), 8, 6)
    p3, _ = m.scan_library(lib)
    check("cache invalidated on add", len(p3) == 5, len(p3))

    # invalidation: remove
    os.remove(os.path.join(lib, "p4.png"))
    p4, _ = m.scan_library(lib)
    check("cache invalidated on remove", len(p4) == 4, len(p4))

    # invalidation: modify (mtime change)
    time.sleep(0.01)
    make_png(os.path.join(lib, "p0.png"), 16, 9)
    p5, _ = m.scan_library(lib)
    check("cache invalidated on modify", len(p5) == 4, len(p5))
    w0 = next(p["width"] for p in p5 if p["filename"] == "p0.png")
    check("modified file rescanned", w0 == 16, w0)

    # corrupt cache -> quarantine + rescan
    with open(cache_file, "w") as f:
        f.write("NOT JSON {{{")
    p6, _ = m.scan_library(lib)
    check("corrupt cache rescanned", len(p6) == 4, len(p6))
    quarantined = [f for f in os.listdir(cache_dir) if "corrupt" in f]
    check("corrupt cache quarantined", len(quarantined) >= 1, quarantined)

    m.scan_cache_dir = lambda: os.path.expanduser("~/.cache/mv-photos")


def test_group_by_moment(m, tmp):
    root = make_library(os.path.join(tmp, "lib"))
    photos, _ = m.scan_library(root)
    moments = m.group_by_moment(photos)
    check("moments count", len(moments) >= 2, len(moments))
    dates = [g["date"] for g in moments]
    check("moments sorted desc", dates == sorted(dates, reverse=True))
    check("2024-03-15 has 2", any(g["date"] == "2024-03-15" and g["count"] == 2
                                   for g in moments))
    check("2023-12-25 has 1", any(g["date"] == "2023-12-25" and g["count"] == 1
                                   for g in moments))
    check("unknown date group", any(g["date"] == "Unknown" for g in moments))
    total = sum(g["count"] for g in moments)
    check("moments total == photos", total == len(photos), total)


def test_search_photos(m, tmp):
    root = make_library(os.path.join(tmp, "lib"))
    photos, _ = m.scan_library(root)
    r = m.search_photos(photos, "a.png")
    check("search filename", len(r) == 1 and r[0]["filename"] == "a.png")
    r = m.search_photos(photos, "2024-03-15")
    check("search date", len(r) == 2, len(r))
    r = m.search_photos(photos, "2023")
    check("search year", len(r) == 1, len(r))
    r = m.search_photos(photos, "")
    check("empty query returns all", len(r) == len(photos))
    r = m.search_photos(photos, "nonexistent")
    check("no match", r == [])


def test_state_store(m, tmp):
    sdir = os.path.join(tmp, "state")
    os.makedirs(sdir)
    spath = os.path.join(sdir, "state.json")

    st = m.default_state()
    st["favorites"] = ["/a.jpg", "/b.png"]
    st["albums"] = [{"name": "Vacation", "paths": ["/a.jpg"]}]
    st["imports"] = [{"path": "/tmp/camera", "at": "2024-01-01T00:00:00"}]
    st["geometry"] = {"w": 1000, "h": 700, "sidebar": 240}
    m.save_state(path=spath, data=st)
    check("state file written", os.path.exists(spath))
    check("no backup before first overwrite", not os.path.exists(spath + ".bak"))

    loaded = m.load_state(path=spath)
    check("roundtrip favorites", loaded["favorites"] == ["/a.jpg", "/b.png"])
    check("roundtrip albums", loaded["albums"] == [{"name": "Vacation",
                                                    "paths": ["/a.jpg"]}])
    check("roundtrip imports", loaded["imports"] == [{"path": "/tmp/camera",
                                                       "at": "2024-01-01T00:00:00"}])
    check("roundtrip geometry", loaded["geometry"]["w"] == 1000)
    check("roundtrip sidebar", loaded["geometry"]["sidebar"] == 240)

    st2 = dict(loaded)
    st2["favorites"] = ["/c.gif"]
    m.save_state(path=spath, data=st2)
    check("backup created", os.path.exists(spath + ".bak"))
    loaded2 = m.load_state(path=spath)
    check("roundtrip after overwrite", loaded2["favorites"] == ["/c.gif"])

    with open(spath + ".bak") as f:
        bak_data = f.read()
    check("backup has old data", "/a.jpg" in bak_data)

    with open(spath, "w") as f:
        f.write("{corrupt json")
    loaded3 = m.load_state(path=spath)
    check("corrupt restores from backup",
          loaded3["favorites"] == ["/a.jpg", "/b.png"],
          loaded3["favorites"])

    for fn in os.listdir(sdir):
        if fn.startswith("state.json.corrupt-"):
            os.remove(os.path.join(sdir, fn))
    if os.path.exists(spath):
        os.remove(spath)
    if os.path.exists(spath + ".bak"):
        os.remove(spath + ".bak")
    with open(spath, "w") as f:
        f.write("{corrupt json")
    loaded4 = m.load_state(path=spath)
    check("corrupt no backup -> default", loaded4["favorites"] == [])
    check("corrupt quarantined", any(
        fn.startswith("state.json.corrupt-") for fn in os.listdir(sdir)))

    for fn in os.listdir(sdir):
        if fn.startswith("state.json.corrupt-"):
            os.remove(os.path.join(sdir, fn))
    with open(spath, "w") as f:
        f.write("{}")
    loaded5 = m.load_state(path=spath)
    check("missing state -> default", loaded5["favorites"] == [])

    with open(spath, "w") as f:
        json.dump({"favorites": "not-a-list", "albums": "bad"}, f)
    loaded6 = m.load_state(path=spath)
    check("normalize non-list favorites", loaded6["favorites"] == [])
    check("normalize non-list albums", loaded6["albums"] == [])


def test_favorites(m, tmp):
    st = m.default_state()
    st = m.toggle_favorite(st, "/a.jpg")
    check("fav added", "/a.jpg" in st["favorites"])
    st = m.toggle_favorite(st, "/b.png")
    check("fav added 2", "/b.png" in st["favorites"])
    st = m.toggle_favorite(st, "/a.jpg")
    check("fav removed", "/a.jpg" not in st["favorites"])
    check("fav 2 still there", "/b.png" in st["favorites"])


def test_albums(m, tmp):
    st = m.default_state()
    st = m.add_album(st, "Vacation")
    check("album added", any(a["name"] == "Vacation" for a in st["albums"]))
    st = m.add_album(st, "Vacation")
    check("album no dup", len([a for a in st["albums"]
                               if a["name"] == "Vacation"]) == 1)
    st = m.add_album(st, "Family")
    check("album 2 added", len(st["albums"]) == 2)

    st = m.album_add_photo(st, "Vacation", "/a.jpg")
    st = m.album_add_photo(st, "Vacation", "/b.png")
    st = m.album_add_photo(st, "Vacation", "/a.jpg")
    check("album photo added", len(st["albums"][0]["paths"]) == 2)

    st = m.album_remove_photo(st, "Vacation", "/a.jpg")
    check("album photo removed", st["albums"][0]["paths"] == ["/b.png"])

    st = m.remove_album(st, "Vacation")
    check("album removed", len(st["albums"]) == 1)
    check("remaining album", st["albums"][0]["name"] == "Family")


def test_record_import(m, tmp):
    st = m.default_state()
    st = m.record_import(st, "/tmp/camera1")
    check("import recorded", len(st["imports"]) == 1)
    check("import path", st["imports"][0]["path"] == "/tmp/camera1")
    check("import has timestamp", bool(st["imports"][0]["at"]))
    st = m.record_import(st, "/tmp/camera2")
    check("import 2", len(st["imports"]) == 2)


def test_photos_for_album(m, tmp):
    st = m.default_state()
    st = m.add_album(st, "Vacation")
    st = m.album_add_photo(st, "Vacation", "/a.jpg")
    st = m.album_add_photo(st, "Vacation", "/b.png")
    photos = [{"path": "/a.jpg"}, {"path": "/b.png"}, {"path": "/c.gif"}]
    result = m.photos_for_album(st, "Vacation", photos)
    check("album photos filtered", len(result) == 2)
    check("album photos correct", {p["path"] for p in result} == {"/a.jpg", "/b.png"})
    result2 = m.photos_for_album(st, "Nonexistent", photos)
    check("nonexistent album empty", result2 == [])


def test_thumb_path(m, tmp):
    jpg = os.path.join(tmp, "t.jpg")
    make_jpeg(jpg, 4, 4)
    p = {"path": jpg, "mtime": 1000, "size": 100}
    tp1 = m.thumb_path(p)
    check("thumb path not none", tp1 is not None)
    check("thumb path deterministic", m.thumb_path(p) == tp1)
    os.utime(jpg, (2000, 2000))
    p2 = dict(p, mtime=2000)
    check("thumb path changes with mtime", m.thumb_path(p2) != tp1)


def test_rotate_no_backend(m, tmp):
    # Assertion is about the MISSING-backend path: when gthumb/exiftool are
    # installed the helper really invokes them (spawns a GUI, slow), so only
    # exercise the graceful-failure contract on hosts without those tools.
    if shutil.which("gthumb") or shutil.which("exiftool"):
        print("skip - rotate graceful no backend (gthumb/exiftool installed)")
        return
    jpg = os.path.join(tmp, "r.jpg")
    make_jpeg(jpg, 4, 4)
    result = m.rotate_image(jpg, "right")
    check("rotate graceful no backend", result is False)


def test_open_editor_no_backend(m, tmp):
    if shutil.which("gthumb"):
        print("skip - open editor graceful no gthumb (gthumb installed)")
        return
    jpg = os.path.join(tmp, "e.jpg")
    make_jpeg(jpg, 4, 4)
    result = m.open_in_editor(jpg)
    check("open editor graceful no gthumb", result is False)


def test_fmt_date(m):
    check("fmt_date normal", m.fmt_date("2024-03-15T10:30:00") == "2024-03-15")
    check("fmt_date empty", m.fmt_date("") == "")
    check("fmt_date None", m.fmt_date(None) == "")


def test_fmt_size(m):
    check("fmt_size B", m.fmt_size(512) == "512 B")
    check("fmt_size KB", m.fmt_size(2048) == "2.0 KB")
    check("fmt_size MB", m.fmt_size(5 * 1024 * 1024) == "5.0 MB")
    check("fmt_size garbage", m.fmt_size("abc") == "?")


# -------------------------------------------------------------------- main


    path = os.path.join(BIN, "mv-photos")
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("photos: native XFWM4 decoration", "self.set_decorated(True)" in source)
    check("photos: no Gtk.HeaderBar/CSD", "Gtk.HeaderBar" not in source and "set_titlebar(" not in source)

def main():
    tmp = tempfile.mkdtemp(prefix="mv-photos-test-")
    try:
        m = load_app()
        test_dimensions(m, tmp)
        test_exif_date(m, tmp)
        test_read_image_info(m, tmp)
        test_scan_single_open(m, tmp)
        test_scan_library(m, tmp)
        test_scan_cache(m, tmp)
        test_group_by_moment(m, tmp)
        test_search_photos(m, tmp)
        test_state_store(m, tmp)
        test_favorites(m, tmp)
        test_albums(m, tmp)
        test_record_import(m, tmp)
        test_photos_for_album(m, tmp)
        test_thumb_path(m, tmp)
        test_rotate_no_backend(m, tmp)
        test_open_editor_no_backend(m, tmp)
        test_fmt_date(m)
        test_fmt_size(m)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    if FAILURES:
        for name, detail in FAILURES:
            print("  FAIL: %s %s" % (name, detail))
        sys.exit(1)


if __name__ == "__main__":
    main()
