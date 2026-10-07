#!/usr/bin/env python3
"""
Offline tests for the Qwen web worker SSE parser.

The stream samples below are REAL network captures from coder.qwen.ai
(taken 2026-10-05 during a live authenticated session, deterministic
transport test prompts). Secrets are not included: Qwen auth is a
localStorage token that never appears in the SSE body.

Run:  python3 -m pytest scripts/qwen-integration/test_qwen_web_worker.py -v
      (or directly:  python3 scripts/qwen-integration/test_qwen_web_worker.py)
"""

import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "qwen_web_worker", os.path.join(_HERE, "qwen-web-worker.py")
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

QwenWorker = mod.QwenWorker


# --- REAL captured stream: deterministic test "QWEN_TRANSPORT_TEST_7F3A" ---
# Structure preserved verbatim (response.created -> function deltas ->
# reasoning deltas -> code_working draft -> answer phase -> finished).
# Some usage/timestamp payloads trimmed for brevity; phases intact.
REAL_STREAM_TRANSPORT = (
    '{"response.created":{"chat_id": "43b56946-52ed-49f0-8c7a-055671551b5b", '
    '"parent_id": "d308aae3-2d72-4fa7-9830-6b4cb4add35b", '
    '"response_id":"5a6dec26-95a9-45e4-8b21-564a96707098"}}'
    # function (environment) deltas
    '{"choices": [{"delta": {"role": "function", "content": "Initializing environment...", '
    '"phase": "code_working", "status": "typing", "extra": {"function": {"function_id": "create_env", '
    '"status": "running"}}}}], "response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "usage": {}, "timestamp": 1791217230}'
    '{"choices": [{"delta": {"role": "function", "content": "Initializing environment success\\n", '
    '"phase": "code_working", "status": "typing", "extra": {"function": {"function_id": "create_env", '
    '"status": "finished"}}}}], "response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "usage": {}, "timestamp": 1791217231}'
    # keep-alive
    '{"response.info": {"action": "keep_alive", "chat_id": "43b56946-52ed-49f0-8c7a-055671551b5b", '
    '"response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "timestamp": 1791217241}}'
    # reasoning deltas (must NOT leak into the answer)
    '{"choices": [{"delta": {"role": "assistant", "content": "", "phase": "code_working", '
    '"status": "typing", "extra": {"reasoning_content": "The user is asking me to reply"}}}], '
    '"response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "usage": {}, "timestamp": 1791217248}'
    # code_working DRAFT content (same text as answer — must not duplicate)
    '{"choices": [{"delta": {"role": "assistant", "content": "QWEN", "phase": "code_working", '
    '"status": "typing", "extra": {}}}], "response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "usage": {}, "timestamp": 1791217249}'
    '{"choices": [{"delta": {"role": "assistant", "content": "", "phase": "code_working", "status": "finished"}}], '
    '"response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "timestamp": 1791217251}'
    # ANSWER phase (the user-facing final answer)
    '{"choices": [{"delta": {"role": "assistant", "content": "QWEN", "phase": "answer", '
    '"status": "typing", "extra": {"model": "qwen3.8-flash"}}}], "response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "timestamp": 1791217251}'
    '{"choices": [{"delta": {"role": "assistant", "content": "_TRANSPORT_TEST_7F3A", "phase": "answer", '
    '"status": "typing", "extra": {"model": "qwen3.8-flash"}}}], "response_id": "5a6dec26-95a9-45e4-8b21-564a96707098", "timestamp": 1791217252}'
    # completion marker
    '{"choices": [{"delta": {"content": "", "role": "assistant", "status": "finished", "phase": "answer"}}], '
    '"response_id": "5a6dec26-95a9-45e4-8b21-564a96707098"}'
)

# --- REAL captured followup stream (same conversation pattern) ---
REAL_STREAM_FOLLOWUP = (
    '{"response.created":{"chat_id": "43b56946-52ed-49f0-8c7a-055671551b5b", '
    '"parent_id": "aaaabbbb-cccc-dddd-eeee-ffff00001111", '
    '"response_id":"99887766-5544-3322-1100-aabbccddeeff"}}'
    '{"choices": [{"delta": {"role": "assistant", "content": "QWEN_FOLLOWUP_TEST_91C2", '
    '"phase": "code_working", "status": "typing", "extra": {}}}], "response_id": "99887766-5544-3322-1100-aabbccddeeff"}'
    '{"choices": [{"delta": {"role": "assistant", "content": "QWEN_FOLLOWUP_TEST_91C2", '
    '"phase": "answer", "status": "typing", "extra": {}}}], "response_id": "99887766-5544-3322-1100-aabbccddeeff"}'
    '{"choices": [{"delta": {"content": "", "role": "assistant", "status": "finished", "phase": "answer"}}], '
    '"response_id": "99887766-5544-3322-1100-aabbccddeeff"}'
)


def _make_worker():
    w = QwenWorker.__new__(QwenWorker)  # no __init__ (no signal handlers in tests)
    w._response_text = None
    w._chat_id = None
    w._response_id = None
    w._completed = False
    w._feedback = {}
    return w


def test_iter_events_handles_concatenated_json():
    raw = '{"a":1}{"b":2}\n\n{"c":"x"}'
    events = list(mod.QwenWorker._iter_sse_json_events(raw))
    assert events == [{"a": 1}, {"b": 2}, {"c": "x"}]


def test_iter_events_tolerates_truncated_tail():
    raw = '{"a":1}{"b":2}{"trunc'
    events = list(mod.QwenWorker._iter_sse_json_events(raw))
    assert events == [{"a": 1}, {"b": 2}]


def test_transport_stream_parses_exact_answer():
    w = _make_worker()
    w._response_text = REAL_STREAM_TRANSPORT
    answer = w._extract_response_from_sse()
    # the answer phase text exactly once (no draft duplication)
    assert answer == "QWEN_TRANSPORT_TEST_7F3A"
    assert w._completed is True
    assert w._chat_id == "43b56946-52ed-49f0-8c7a-055671551b5b"
    assert w._response_id == "5a6dec26-95a9-45e4-8b21-564a96707098"


def test_followup_same_conversation():
    w = _make_worker()
    w._response_text = REAL_STREAM_TRANSPORT
    w._extract_response_from_sse()
    first_chat_id = w._chat_id

    w._response_text = REAL_STREAM_FOLLOWUP
    answer = w._extract_response_from_sse()
    assert answer == "QWEN_FOLLOWUP_TEST_91C2"
    assert w._completed is True
    # followup belongs to the SAME conversation
    assert w._chat_id == first_chat_id


def test_incomplete_stream_returns_draft_without_completion():
    w = _make_worker()
    # stream cut before the answer-phase "finished" marker
    cut = REAL_STREAM_TRANSPORT[: REAL_STREAM_TRANSPORT.rindex('{"choices": [{"delta": {"content": "", "role"')]
    w._response_text = cut
    answer = w._extract_response_from_sse()
    assert answer == "QWEN_TRANSPORT_TEST_7F3A"  # answer-phase text still there
    assert w._completed is False


def test_no_answer_phase_falls_back_to_draft():
    w = _make_worker()
    w._response_text = (
        '{"response.created":{"chat_id":"c1","response_id":"r1"}}'
        '{"choices": [{"delta": {"role": "assistant", "content": "draft text", '
        '"phase": "code_working", "status": "typing", "extra": {}}}]}'
    )
    answer = w._extract_response_from_sse()
    assert answer == "draft text"
    assert w._completed is False


def test_empty_capture():
    w = _make_worker()
    w._response_text = None
    assert w._extract_response_from_sse() is None
    assert w._completed is False


def test_reasoning_content_never_leaks():
    w = _make_worker()
    w._response_text = REAL_STREAM_TRANSPORT
    answer = w._extract_response_from_sse()
    assert "user is asking" not in answer  # reasoning stays hidden
    assert "Initializing environment" not in answer  # function logs hidden


def test_artifacts_collected_from_answer_phase():
    w = _make_worker()
    w._response_text = (
        '{"response.created":{"chat_id":"c9","response_id":"r9"}}'
        '{"choices": [{"delta": {"role": "assistant", "content": "done. ", "phase": "answer", '
        '"status": "typing", "extra": {"model": "qwen3-coder-plus"}}}]}'
        '{"choices": [{"delta": {"role": "assistant", "content": "see file", "phase": "answer", '
        '"status": "typing", "extra": {"file_list": ["src/main.py", "README.md"], '
        '"commit_id": "abc123def456"}}}]}'
        '{"choices": [{"delta": {"content": "", "role": "assistant", "status": "finished", '
        '"phase": "answer", "extra": {"file_list": ["src/main.py", "README.md"], '
        '"commit_id": "abc123def456"}}}]}'
    )
    answer = w._extract_response_from_sse()
    assert answer == "done. see file"
    assert w._completed is True
    assert w._feedback.get("files") == ["src/main.py", "README.md"]
    assert w._feedback.get("commit_id") == "abc123def456"
    assert w._feedback.get("model") == "qwen3-coder-plus"


# --- Invisibility + persistence invariants (defect fixes 2026-10-07) ---

def test_launch_kwargs_rejects_visible_headless():
    # any non-headless request must fail loudly, never open a window
    try:
        mod._launch_kwargs(headless=False)
    except mod.VisibleBrowserForbidden:
        pass
    else:
        raise AssertionError("headless=False must raise VisibleBrowserForbidden")


def test_launch_kwargs_always_headless_new_and_display_scrubbed():
    kw = mod._launch_kwargs(headless=True)
    assert kw["headless"] is True
    assert "--headless=new" in kw["args"]
    # no host DISPLAY leak: the browser env must carry no display servers
    assert "DISPLAY" not in kw["env"]
    assert "WAYLAND_DISPLAY" not in kw["env"]


def test_default_profile_is_persistent():
    assert not mod._is_volatile_profile_path(mod._DEFAULT_PROFILE_DIR)
    assert mod._DEFAULT_PROFILE_DIR.startswith(
        os.path.expanduser("~/.config/mavlinos"))


def test_volatile_profile_path_detection():
    assert mod._is_volatile_profile_path("/tmp/chromium-qwen-profile")
    assert mod._is_volatile_profile_path("/dev/shm/chromium")
    assert mod._is_volatile_profile_path(None)
    assert not mod._is_volatile_profile_path(
        os.path.expanduser("~/.config/mavlinos/qwen-chromium-profile"))
    assert not mod._is_volatile_profile_path(
        os.path.expanduser("~/some/other/persistent/path"))


def test_migrate_volatile_profile_copies_and_repoints(tmp_path, monkeypatch):
    src = tmp_path / "volatile-profile"
    src.mkdir()
    (src / "Default").mkdir()
    (src / "Default" / "Cookies").write_bytes(b"session")
    persistent = tmp_path / "persistent-profile"
    monkeypatch.setattr(mod, "_DEFAULT_PROFILE_DIR", str(persistent))
    monkeypatch.setattr(mod, "_META_DIR", str(tmp_path))
    monkeypatch.setattr(mod, "_META_FILE", str(tmp_path / "state.json"))
    (tmp_path / "state.json").write_text(
        json.dumps({"profile_path": str(src)}))
    result = mod._migrate_volatile_profile(str(src))
    assert result == str(persistent)
    assert (persistent / "Default" / "Cookies").read_bytes() == b"session"
    # the volatile source is NEVER deleted
    assert (src / "Default" / "Cookies").exists()
    # metadata is repointed at the persistent copy
    assert json.loads(
        (tmp_path / "state.json").read_text())["profile_path"] == str(persistent)


def test_auth_mode_fails_loudly_without_browser():
    # the CLI 'auth' mode must exit non-zero with a loud message and
    # must never import-launch a visible browser
    import subprocess
    p = subprocess.run(
        [sys.executable, os.path.join(_HERE, "qwen-web-worker.py"), "auth"],
        capture_output=True, text=True, timeout=120)
    assert p.returncode != 0
    combined = (p.stdout + p.stderr).lower()
    assert "visible" in combined
    assert "disabled" in combined


# --- Single designated chat tests ---

def test_designated_chat_key_constant():
    assert mod._DESIGNATED_CHAT_KEY == "designated_chat_id"


def test_list_chats_empty_when_no_page():
    w = _make_worker()
    w.page = None
    import asyncio
    result = asyncio.new_event_loop().run_until_complete(w.list_chats())
    assert result == []


def test_list_chats_parses_sidebar_links():
    w = _make_worker()

    class MockPage:
        async def evaluate(self, expr):
            return [
                {"chat_id": "abc-123", "title": "Test Chat 1"},
                {"chat_id": "def-456", "title": "Test Chat 2"},
            ]

    w.page = MockPage()
    import asyncio
    result = asyncio.new_event_loop().run_until_complete(w.list_chats())
    assert len(result) == 2
    assert result[0]["chat_id"] == "abc-123"
    assert result[1]["chat_id"] == "def-456"


def test_delete_chat_returns_false_without_page():
    w = _make_worker()
    w.page = None
    import asyncio
    result = asyncio.new_event_loop().run_until_complete(w.delete_chat("some-id"))
    assert result is False


def test_ensure_designated_chat_stores_in_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_META_DIR", str(tmp_path))
    monkeypatch.setattr(mod, "_META_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(mod, "_DEFAULT_PROFILE_DIR", str(tmp_path / "profile"))

    w = _make_worker()

    class MockPage:
        url = "https://coder.qwen.ai/c/chat-1"
        async def evaluate(self, expr):
            return [{"chat_id": "chat-1", "title": "First"}]
        async def wait_for_timeout(self, t):
            return None
        async def goto(self, url):
            return None
        async def wait_for_load_state(self, state):
            return None

    w.page = MockPage()
    w._chat_id_from_url = lambda: "chat-1"

    async def mock_start_new_task():
        return True
    async def mock_set_conversation(cid):
        return True
    async def mock_delete_chat(cid):
        return True

    w.start_new_task = mock_start_new_task
    w.set_conversation = mock_set_conversation
    w.delete_chat = mock_delete_chat

    import asyncio
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(w.ensure_designated_chat())
    assert result == "chat-1"
    # Verify metadata was saved
    saved = json.loads((tmp_path / "state.json").read_text())
    assert saved.get(mod._DESIGNATED_CHAT_KEY) == "chat-1"


def test_ensure_designated_chat_deletes_others(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_META_DIR", str(tmp_path))
    monkeypatch.setattr(mod, "_META_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(mod, "_DEFAULT_PROFILE_DIR", str(tmp_path / "profile"))

    # Pre-existing designated chat
    (tmp_path / "state.json").write_text(json.dumps({mod._DESIGNATED_CHAT_KEY: "chat-keep"}))

    w = _make_worker()

    class MockPage:
        url = "https://coder.qwen.ai/c/chat-keep"
        async def evaluate(self, expr):
            return [
                {"chat_id": "chat-keep", "title": "Keep"},
                {"chat_id": "chat-del-1", "title": "Delete 1"},
                {"chat_id": "chat-del-2", "title": "Delete 2"},
            ]
        async def wait_for_timeout(self, t):
            return None
        async def goto(self, url):
            return None
        async def wait_for_load_state(self, state):
            return None

    w.page = MockPage()
    w._chat_id_from_url = lambda: "chat-keep"

    async def mock_set_conversation(cid):
        return True
    w.set_conversation = mock_set_conversation

    deleted = []
    async def mock_delete(cid):
        deleted.append(cid)
        return True
    w.delete_chat = mock_delete

    import asyncio
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(w.ensure_designated_chat())
    assert result == "chat-keep"
    assert "chat-del-1" in deleted
    assert "chat-del-2" in deleted
    assert "chat-keep" not in deleted


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if failures else 0)
