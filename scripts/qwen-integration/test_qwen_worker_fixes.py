#!/usr/bin/env python3
"""Offline tests for the 2026-10-09 fixes in qwen-web-worker.py:
honest failure states, SIGTERM kept while typing, fast chunked typing,
designated chat survives an empty sidebar, server-side login check.
Browser calls are mocked; no Playwright session is started.

Run: python3 scripts/qwen-integration/test_qwen_worker_fixes.py"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "qwen_web_worker_fixes", os.path.join(_HERE, "qwen-web-worker.py"))
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)
QwenWorker = mod.QwenWorker

# NEVER touch the owner's real worker state (~/.config/mavlinos/...): point the
# metadata helpers at a temporary directory for the whole run.
_TMP = tempfile.mkdtemp(prefix="qwen-fixes-test-")
mod._META_DIR = _TMP
mod._META_FILE = os.path.join(_TMP, "qwen-worker-state.json")

FAILS = []
PASSED = [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print("ok - %s" % name)
    else:
        FAILS.append(name)
        print("FAIL - %s %s" % (name, detail))


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def reset_meta(designated=None):
    try:
        os.remove(mod._META_FILE)
    except OSError:
        pass
    if designated:
        mod._save_metadata({mod._DESIGNATED_CHAT_KEY: designated})


def make_worker():
    w = QwenWorker.__new__(QwenWorker)  # no __init__: no signal handlers in tests
    w._stop_requested = False
    w._prompt_sent = False
    w._fail_reason = None
    w._repo = None
    w._response_text = None
    w._chat_id = None
    w._response_id = None
    w._completed = False
    w._feedback = {}
    w.base_url = "https://coder.qwen.ai"
    return w


class FakePage:
    """evaluate() answers by script content; everything else is a no-op."""
    url = "https://coder.qwen.ai/"

    def __init__(self, token=True, status=None, raise_on_fetch=False):
        self.token, self.status, self.raise_on_fetch = token, status, raise_on_fetch

    async def evaluate(self, script, *args):
        if "localStorage" in script:
            return self.token
        if "/coder/api/v2/task/" in script:
            if self.raise_on_fetch:
                raise RuntimeError("boom")
            return self.status
        return None

    async def wait_for_timeout(self, ms):
        return None

    async def goto(self, url):
        return None

    async def wait_for_load_state(self, state):
        return None


class FakeLocator:
    def __init__(self, on_type=None):
        self.typed, self.delays, self.pressed = [], [], []
        self.on_type = on_type

    @property
    def first(self):
        return self

    async def wait_for(self, state=None, timeout=None):
        return None

    async def click(self):
        return None

    async def fill(self, text):
        return None

    async def type(self, text, delay=0):
        self.typed.append(text)
        self.delays.append(delay)
        if self.on_type:
            self.on_type(len(self.typed))

    async def press(self, key):
        self.pressed.append(key)


class TypingPage(FakePage):
    def __init__(self, locator):
        super().__init__()
        self.locator_obj = locator

    def locator(self, selector):
        return self.locator_obj


def main():
    # -- typing speed --------------------------------------------------
    check("short prompt keeps human-like 30 ms", mod._type_delay_ms(400) == 30)
    check("long prompt is typed at 5 ms", mod._type_delay_ms(401) == 5)

    # -- failure states -------------------------------------------------
    w = make_worker()
    check("default failure state is needs_auth", mod._fail_state(w) == "needs_auth")
    for reason in ("profile_in_use", "launch_failed", "needs_auth"):
        w._fail_reason = reason
        check("failure state %s is reported as is" % reason, mod._fail_state(w) == reason)
    check("a worker without the attribute still reports needs_auth",
          mod._fail_state(object()) == "needs_auth")

    # -- server-side login check ------------------------------------------
    for status, want in ((401, False), (403, False), (200, True), (404, None), (500, None)):
        reset_meta("chat-1")
        w = make_worker()
        w.page = FakePage(status=status)
        check("task status %s -> session_valid %s" % (status, want),
              run(w._session_valid()) is want)
    reset_meta()
    w = make_worker()
    w.page = FakePage(status=200)
    check("no designated chat -> unknown (None), old behaviour kept",
          run(w._session_valid()) is None)
    reset_meta("chat-1")
    w = make_worker()
    w.page = FakePage(raise_on_fetch=True)
    check("probe failure -> unknown (None)", run(w._session_valid()) is None)

    reset_meta("chat-1")
    w = make_worker()
    w.page = FakePage(token=False, status=200)
    check("no token -> not authenticated", run(w._verify_session()) is False)
    w.page = FakePage(token=True, status=401)
    check("token present but HTTP 401 -> not authenticated", run(w._verify_session()) is False)
    w.page = FakePage(token=True, status=200)
    check("token present and HTTP 200 -> authenticated", run(w._verify_session()) is True)
    w.page = FakePage(token=True, status=None)
    check("token present, status unknown -> still authenticated", run(w._verify_session()) is True)

    # -- designated chat survives an empty sidebar --------------------------
    for task_status, expect_new in ((200, False), (404, True)):
        reset_meta("chat-keep")
        w = make_worker()
        w.page = FakePage(status=task_status)
        calls = {"new": 0, "listed": 0}

        async def list_chats():
            calls["listed"] += 1
            return [] if (calls["new"] == 0) else [{"chat_id": "chat-new", "title": "n"}]

        async def start_new_task():
            calls["new"] += 1
            return True

        async def set_conversation(cid):
            return True

        async def delete_chat(cid):
            return True

        w.list_chats, w.start_new_task = list_chats, start_new_task
        w.set_conversation, w.delete_chat = set_conversation, delete_chat
        result = run(w.ensure_designated_chat())
        if expect_new:
            check("empty sidebar + designated chat gone on server -> new chat",
                  result == "chat-new" and calls["new"] == 1, "result=%s calls=%s" % (result, calls))
        else:
            check("empty sidebar + designated chat alive -> reused, NO new chat",
                  result == "chat-keep" and calls["new"] == 0 and calls["listed"] >= 2,
                  "result=%s calls=%s" % (result, calls))

    # -- typing: chunks, delay, SIGTERM ---------------------------------------
    async def done():
        return "answer"

    reset_meta()
    loc = FakeLocator()
    w = make_worker()
    w.page = TypingPage(loc)
    w._await_completion = done
    prompt = "x" * 1000
    result = run(w.send_prompt(prompt))
    check("1000-char prompt: 5 chunks, all typed, Enter pressed",
          result == "answer" and len(loc.typed) == 5 and "".join(loc.typed) == prompt
          and loc.pressed == ["Enter"] and w._prompt_sent is True,
          "typed=%d pressed=%s" % (len(loc.typed), loc.pressed))
    check("long prompt typed at 5 ms per key", set(loc.delays) == {5}, str(loc.delays))

    loc = FakeLocator()
    w = make_worker()
    w.page = TypingPage(loc)
    w._await_completion = done
    run(w.send_prompt("short prompt"))
    check("short prompt typed at 30 ms per key", loc.delays == [30], str(loc.delays))

    holder = {}
    loc = FakeLocator(on_type=lambda n: holder["w"].__setattr__("_stop_requested", True) if n == 2 else None)
    w = make_worker()
    holder["w"] = w
    w.page = TypingPage(loc)
    w._await_completion = done
    result = run(w.send_prompt("y" * 1000))
    check("SIGTERM while typing: stops before submit",
          result is False and loc.pressed == [] and len(loc.typed) == 2 and w._prompt_sent is False,
          "typed=%d pressed=%s" % (len(loc.typed), loc.pressed))

    holder = {}
    loc = FakeLocator(on_type=lambda n: holder["w"].__setattr__("_stop_requested", True) if n == 5 else None)
    w = make_worker()
    holder["w"] = w
    w.page = TypingPage(loc)
    w._await_completion = done
    result = run(w.send_prompt("z" * 1000))
    check("SIGTERM on the LAST chunk is not erased: nothing submitted",
          result is False and loc.pressed == [] and w._prompt_sent is False,
          "pressed=%s" % loc.pressed)

    loc = FakeLocator()
    w = make_worker()
    w._stop_requested = True  # left over from a clean close in the snapshot-restore path
    w.page = TypingPage(loc)
    w._await_completion = done
    result = run(w.send_prompt("hello"))
    check("stale stop flag from an earlier clean close does not block the send",
          result == "answer" and loc.pressed == ["Enter"])

    async def none_answer():
        return None
    loc = FakeLocator()
    w = make_worker()
    w.page = TypingPage(loc)
    w._await_completion = none_answer
    result = run(w.send_prompt("hello"))
    check("submitted prompt without answer: returns None and _prompt_sent is True (state=timeout)",
          result is None and w._prompt_sent is True)

    print("\n%d passed, %d failed" % (PASSED[0], len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
