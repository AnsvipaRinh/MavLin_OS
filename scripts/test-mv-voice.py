#!/usr/bin/env python3
"""Headless tests for mv-voice.

Pure-logic section (no GTK widgets):
- backend/playback detection (pw-record/parec, pw-play/paplay) incl. no-PATH
- wav_info / wav_duration on synthetic PCM wavs + garbage + missing files
- sanitize_memo_name (path traversal, unsafe chars, .wav suffix, empty)
- list_memos ordering + non-wav skipping
- waveform_peaks on synthetic loud/silent/garbage files
- rms_level on synthetic PCM data
- trim_wav frame-aligned cut, clamping, empty-selection + garbage errors
- fmt_time

GUI smoke (display only, skipped headless):
- window construction, list/empty states, backend-unavailable state
- record start/stop with mocked Popen, cassette state, meter
- play start/stop with mocked Popen + playback_cmd, waveform progress
- trim integration via _apply_trim, rename via _rename_dialog (mocked modal
  dialog), info lines, delete via trash fallback, key handler routing

Usage: python3 scripts/test-mv-voice.py
Exit 0 = all tests passed."""
import importlib.machinery
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import wave
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(
    REPO, "packages/mavericks-apps/src/mavericks-apps/bin/mv-voice")

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
    loader = importlib.machinery.SourceFileLoader("mv_voice", APP_PATH)
    spec = importlib.util.spec_from_loader("mv_voice", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def make_wav(path, seconds=1.0, rate=8000, channels=1, amp=0.5,
             sampwidth=2):
    frames = int(seconds * rate)
    data = b"".join(
        struct.pack("<h", int(amp * 32767 *
                             (1 if (i // 40) % 2 == 0 else -1)))
        for i in range(frames * channels))
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(data)
    return path


# ------------------------------------------------------------------ pure


def test_fmt_time(m):
    check("fmt_time 0", m.fmt_time(0) == "0:00")
    check("fmt_time 65", m.fmt_time(65) == "1:05")
    check("fmt_time 599", m.fmt_time(599) == "9:59")


def test_backend_detection(m):
    be = m.backend_cmd()
    check("backend_cmd returns list or None", be is None or isinstance(be, list))
    if be:
        check("backend_cmd exe is pw-record/parec",
              be[0] in ("pw-record", "parec"), be)
    with mock.patch.object(m.subprocess, "run",
                           side_effect=OSError("no exe")):
        check("backend_cmd no exe -> None", m.backend_cmd() is None)
    with mock.patch.object(m.subprocess, "run", return_value=None):
        check("backend_cmd mocked pw-record first",
              m.backend_cmd()[0] == "pw-record", m.backend_cmd())
    pb = m.playback_cmd()
    check("playback_cmd returns list or None", pb is None or isinstance(pb, list))
    with mock.patch.object(m.subprocess, "run",
                           side_effect=OSError("no exe")):
        check("playback_cmd no exe -> None", m.playback_cmd() is None)


def test_wav_info_duration(m, td):
    p = make_wav(os.path.join(td, "a.wav"), seconds=2.0, rate=8000)
    info = m.wav_info(p)
    check("wav_info parses header", info and info["rate"] == 8000
          and info["channels"] == 1 and abs(info["duration"] - 2.0) < 0.01,
          info)
    check("wav_duration wav", abs(m.wav_duration(p) - 2.0) < 0.01)
    with open(os.path.join(td, "garbage.wav"), "wb") as f:
        f.write(b"not a wav file at all" * 10)
    check("wav_info garbage -> None", m.wav_info(os.path.join(td, "garbage.wav")) is None)
    check("wav_duration missing -> None",
          m.wav_duration(os.path.join(td, "missing.wav")) is None)
    check("wav_duration garbage -> None",
          m.wav_duration(os.path.join(td, "garbage.wav")) is None)


def test_sanitize(m):
    check("sanitize strips unsafe", m.sanitize_memo_name('a/b:c*d?') == "a_b_c_d_.wav")
    check("sanitize adds .wav", m.sanitize_memo_name("memo") == "memo.wav")
    check("sanitize keeps .wav", m.sanitize_memo_name("memo.wav") == "memo.wav")
    check("sanitize traversal", m.sanitize_memo_name("../../etc/passwd") == ".._.._etc_passwd.wav")
    check("sanitize empty", m.sanitize_memo_name("   ") == "")
    check("sanitize null-ish", m.sanitize_memo_name("a\0b") == "a_b.wav")


def test_list_memos(m, td):
    d = os.path.join(td, "memos")
    os.makedirs(d)
    make_wav(os.path.join(d, "b.wav"), seconds=1.0)
    make_wav(os.path.join(d, "a.wav"), seconds=0.5)
    with open(os.path.join(d, "notes.txt"), "w") as f:
        f.write("ignore me")
    os.makedirs(os.path.join(d, "sub.wav"))  # directory must be skipped
    memos = m.list_memos(d)
    check("list_memos only wav files", [x["name"] for x in memos] == ["b.wav", "a.wav"],
          [x["name"] for x in memos])
    check("list_memos duration str", memos[0]["duration_str"] == "0:01", memos[0])
    check("list_memos date field", " " in memos[0]["date"])
    check("list_memos missing dir -> []", m.list_memos(os.path.join(td, "nope")) == [])


def test_waveform_peaks(m, td):
    loud = make_wav(os.path.join(td, "loud.wav"), seconds=1.0, amp=0.8)
    peaks = m.waveform_peaks(loud, buckets=80)
    check("peaks length", peaks is not None and len(peaks) == 80,
          None if peaks is None else len(peaks))
    check("peaks in range", peaks and max(peaks) > 0.5 and min(peaks) >= 0.0)
    with open(os.path.join(td, "garbage.wav"), "wb") as f:
        f.write(b"junk")
    check("peaks garbage -> None", m.waveform_peaks(os.path.join(td, "garbage.wav")) is None)
    with open(os.path.join(td, "silence.wav"), "wb") as f:
        pass
    make_wav(os.path.join(td, "silence.wav"), seconds=0.5, amp=0.0)
    sp = m.waveform_peaks(os.path.join(td, "silence.wav"), buckets=40)
    check("peaks silent all zero", sp and max(sp) == 0.0)


def test_rms_level(m):
    check("rms silence", m.rms_level(b"\x00\x00" * 100) == 0.0)
    data = struct.pack("<h", 32767) * 200
    check("rms full scale ~1.0", m.rms_level(data) > 0.9, m.rms_level(data))
    check("rms empty", m.rms_level(b"") == 0.0)


def test_trim_wav(m, td):
    p = make_wav(os.path.join(td, "t.wav"), seconds=2.0, rate=8000)
    orig_frames = m.wav_info(p)["frames"]
    new_dur = m.trim_wav(p, 0.5, 1.5)
    check("trim duration", abs(new_dur - 1.0) < 0.05, new_dur)
    info = m.wav_info(p)
    check("trim frame count", info["frames"] == orig_frames // 2, info["frames"])
    check("trim preserves rate/channels",
          info["rate"] == 8000 and info["channels"] == 1)
    check("trim clamps end beyond duration",
          abs(m.trim_wav(p, 0.5, 99.0) - 0.5) < 0.05)
    try:
        m.trim_wav(p, 1.0, 1.0)
        check("trim empty selection raises", False)
    except ValueError:
        check("trim empty selection raises", True)
    with open(os.path.join(td, "garbage.wav"), "wb") as f:
        f.write(b"junkjunk")
    try:
        m.trim_wav(os.path.join(td, "garbage.wav"), 0, 1)
        check("trim garbage raises", False)
    except ValueError:
        check("trim garbage raises", True)


# --------------------------------------------------------------- gui smoke


def test_gui_smoke(m, td):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gtk, Gdk
    if not Gtk.init_check()[0]:
        print("ok - gui smoke skipped (no display)")
        return

    d = os.path.join(td, "gui")
    os.makedirs(d)
    make_wav(os.path.join(d, "memo-20260101-120000.wav"), seconds=1.0)
    make_wav(os.path.join(d, "memo-20260102-120000.wav"), seconds=2.0)

    win = m.VoiceMemos(memo_dir=d)
    try:
        for _ in range(20):
            Gtk.main_iteration_do(False)
        check("gui constructs", True)
        check("gui list rows", len(win.store) == 2, len(win.store))
        check("gui stack shows list",
              win.list_stack.get_visible_child_name() == "list")
        win.tv.get_selection().select_path(0)
        for _ in range(5):
            Gtk.main_iteration_do(False)
        check("gui selection loads waveform",
              len(win.waveform.peaks) > 0, len(win.waveform.peaks))
        check("gui time shows duration",
              win.time_label.get_text() == "0:02", win.time_label.get_text())

        fake_sub = mock.MagicMock()
        fake_sub.SubprocessError = subprocess.SubprocessError

        class FakeProc:
            def __init__(self, *a, **k):
                pass

            def poll(self):
                return None

            def send_signal(self, _s):
                pass

            def wait(self, timeout=None):
                return 0

        fake_sub.Popen = FakeProc
        with mock.patch.object(m, "subprocess", fake_sub):
            win.toggle_record(None)
            check("gui record starts", win.rec_proc is not None)
            check("gui cassette recording",
                  win.cassette.state == "recording", win.cassette.state)
            check("gui status recording",
                  "Recording" in win.status.get_text())
            win.stop_recording()
            check("gui record stops", win.rec_proc is None)
            check("gui cassette idle", win.cassette.state == "idle")
            check("gui saved status", "Saved:" in win.status.get_text(),
                  win.status.get_text())

        with mock.patch.object(m, "playback_cmd", return_value=["pw-play"]), \
                mock.patch.object(m, "subprocess", fake_sub):
            win.tv.get_selection().select_path(0)
            for _ in range(5):
                Gtk.main_iteration_do(False)
            win.toggle_play()
            check("gui play starts", win.play_proc is not None)
            check("gui cassette playing",
                  win.cassette.state == "playing", win.cassette.state)
            win.stop_playback()
            check("gui play stops", win.play_proc is None)
            check("gui play stop status", "Stopped:" in win.status.get_text(),
                  win.status.get_text())

        wav_path = os.path.join(d, "memo-20260101-120000.wav")
        win.tv.get_selection().select_path(1)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        win._apply_trim(wav_path, 0.0, 0.5)
        check("gui trim applies", abs(m.wav_duration(wav_path) - 0.5) < 0.05,
              m.wav_duration(wav_path))

        with mock.patch.object(m.Gtk, "Dialog") as dlg:
            inst = dlg.return_value
            inst.run.return_value = Gtk.ResponseType.OK
            entry = inst.get_content_area.return_value
            entry.pack_start = mock.MagicMock()
            with mock.patch.object(m.Gtk, "Entry") as ent_cls:
                ent_cls.return_value.get_text.return_value = "renamed memo"
                new_name = win._rename_dialog("memo-20260102-120000.wav")
        check("gui rename dialog returns sanitized",
              new_name == "renamed memo.wav", new_name)

        lines = win._info_lines(wav_path)
        check("gui info lines", any("Duration:" in x for x in lines)
              and any("Format:" in x for x in lines), lines)

        win.tv.get_selection().select_path(1)
        for _ in range(3):
            Gtk.main_iteration_do(False)
        rows_before = len(win.store)
        with mock.patch.object(m.Gio.File, "new_for_path",
                               side_effect=OSError("no gvfs")), \
                mock.patch.object(m.Gtk, "MessageDialog") as md:
            md.return_value.run.return_value = Gtk.ResponseType.YES
            win.delete_memo(None)
        check("gui delete removes row", len(win.store) == rows_before - 1,
              (rows_before, len(win.store)))

        ev = Gdk.EventKey()
        ev.type = Gdk.EventType.KEY_PRESS
        ev.keyval = Gdk.keyval_from_name("r")
        ev.state = Gdk.ModifierType.CONTROL_MASK
        with mock.patch.object(m, "backend_cmd", return_value=None):
            check("gui key ctrl+r routes", win.on_key(None, ev) is True)
        ev2 = Gdk.EventKey()
        ev2.type = Gdk.EventType.KEY_PRESS
        ev2.keyval = Gdk.KEY_Delete
        ev2.state = 0
        with mock.patch.object(m.Gtk, "MessageDialog") as md:
            md.return_value.run.return_value = Gtk.ResponseType.NO
            check("gui key delete routes", win.on_key(None, ev2) is True)

        empty_dir = os.path.join(td, "empty")
        os.makedirs(empty_dir)
        win2 = m.VoiceMemos(memo_dir=empty_dir)
        try:
            for _ in range(10):
                Gtk.main_iteration_do(False)
            check("gui empty state",
                  win2.list_stack.get_visible_child_name() == "empty")
            check("gui empty no rows", len(win2.store) == 0)
        finally:
            win2.destroy()

        with mock.patch.object(m, "backend_cmd", return_value=None):
            win3 = m.VoiceMemos(memo_dir=empty_dir)
            try:
                for _ in range(10):
                    Gtk.main_iteration_do(False)
                check("gui no-backend disables record",
                      not win3.rec_btn.get_sensitive())
                check("gui no-backend status",
                      "No audio recorder" in win3.status.get_text(),
                      win3.status.get_text())
            finally:
                win3.destroy()
    finally:
        win.destroy()


def main():
    m = load_app()
    check("module imports headless", True)

    with tempfile.TemporaryDirectory() as td:
        test_fmt_time(m)
        test_backend_detection(m)
        test_wav_info_duration(m, td)
        test_sanitize(m)
        test_list_memos(m, td)
        test_waveform_peaks(m, td)
        test_rms_level(m)
        test_trim_wav(m, td)
        test_gui_smoke(m, td)

    print("\n%d passed, %d failed" % (PASSED, len(FAILURES)))
    if FAILURES:
        for name, detail in FAILURES:
            print("FAILED: %s %s" % (name, detail))
        sys.exit(1)


if __name__ == "__main__":
    main()
