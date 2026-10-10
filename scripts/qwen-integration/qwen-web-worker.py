#!/usr/bin/env python3
"""
Qwen Web Worker - Playwright-based automation for coder.qwen.ai

Machine-readable interface for OpenCode registrar integration.

INVARIANT (enforced since 2026-10-07): this worker NEVER opens a
visible browser window. Every Chromium launch is headless (new
headless mode), the host DISPLAY/WAYLAND_DISPLAY are scrubbed from
the browser environment, and the only display fallback is a pinned
Xvfb virtual framebuffer (renders to memory only). Any code path
that would produce a visible window fails loudly instead. The
interactive 'auth' mode is therefore DISABLED: the authenticated
profile lives on persistent storage and is auto-restored from the
auth snapshot, so a visible login is never needed (and never run).

Modes:
  start       - Start/resume worker (headless, persistent authenticated profile)
  status      - Get worker state
  check       - Verify auth state (headless)
  send        - Send a prompt
  wait        - Wait for completion
  stop        - Stop worker
  auth        - DISABLED: fails loudly, never opens a browser

Usage:
    qwen-web-worker.py start                    # Start/resume worker (headless)
    qwen-web-worker.py check --json             # Auth gate (machine-readable)
    qwen-web-worker.py send --prompt "text"   # Send a prompt
"""

import asyncio
import json
import os
import re
import sys
import time
import argparse
import signal
import tempfile
from playwright.async_api import async_playwright


_META_DIR = os.path.expanduser("~/.config/mavlinos")
_META_FILE = os.path.join(_META_DIR, "qwen-worker-state.json")
_AUTH_BACKUP_DIR = os.path.join(_META_DIR, "qwen-auth-backup")
# Single designated chat: all sends go to this chat; all others are deleted.
_DESIGNATED_CHAT_KEY = "designated_chat_id"
# Persistent Chromium profile. MUST NOT live under /tmp (or any
# tmpfs): a volatile profile wipes the coder.qwen.ai login on every
# reboot — the root cause of the repeated logins (defect 2).
_DEFAULT_PROFILE_DIR = os.path.join(_META_DIR, "qwen-chromium-profile")
# Roots whose contents do not survive a reboot (tmpfs / volatile).
_VOLATILE_ROOTS = ("/tmp", "/dev/shm")
# Pinned Xvfb display range (last-resort fallback; virtual framebuffer
# only — nothing ever appears on the host desktop).
_XVFB_DISPLAY_MIN = 99
_XVFB_DISPLAY_MAX = 109
# Auth-critical profile subpaths (relative to the profile root) that get
# snapshotted after a successful login and restored if the live profile
# ever loses the session.
_AUTH_STORAGE_RELPATHS = (
    os.path.join("Default", "Local Storage"),
    os.path.join("Default", "Cookies"),
    os.path.join("Default", "Network", "Cookies"),
)


def _ensure_meta_dir():
    os.makedirs(_META_DIR, exist_ok=True)


def _load_metadata():
    try:
        with open(_META_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_metadata(metadata):
    _ensure_meta_dir()
    with open(_META_FILE, "w") as f:
        json.dump(metadata, f, indent=2)


def _is_volatile_profile_path(path):
    """True when the profile path lives on volatile storage (tmpfs)
    whose contents are wiped on reboot — such a profile silently
    loses the coder.qwen.ai login."""
    if not path:
        return True
    try:
        real = os.path.realpath(os.path.abspath(path))
        roots = [os.path.realpath(r) for r in _VOLATILE_ROOTS]
        roots.append(os.path.realpath(tempfile.gettempdir()))
    except Exception:
        return True
    for root in roots:
        if real == root or real.startswith(root + os.sep):
            return True
    return False


def _migrate_volatile_profile(volatile_path):
    """Move a volatile (/tmp) profile to the persistent default
    location by COPYING it (the source is NEVER deleted) and
    repointing the metadata at the persistent copy. Returns the
    persistent profile path."""
    import shutil

    persistent = _DEFAULT_PROFILE_DIR
    if os.path.isdir(volatile_path):
        if os.path.isdir(persistent):
            print(
                "[QwenWorker] Persistent profile already exists at {dst}; "
                "keeping it (volatile copy at {src} left untouched).".format(
                    dst=persistent, src=volatile_path),
                file=sys.stderr,
            )
        else:
            try:
                _ensure_meta_dir()
                shutil.copytree(volatile_path, persistent)
                print(
                    "[QwenWorker] Migrated volatile profile {src} -> {dst} "
                    "(copied, never deleted; the /tmp copy is wiped on "
                    "reboot anyway).".format(src=volatile_path, dst=persistent),
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    "[QwenWorker] WARNING: profile migration failed: {e} "
                    "(the login will not survive a reboot until this is "
                    "fixed; attempting a fresh persistent profile with "
                    "auth-snapshot restore).".format(e=e),
                    file=sys.stderr,
                )
    metadata = _load_metadata()
    metadata["profile_path"] = persistent
    _save_metadata(metadata)
    return persistent


def _browser_env():
    """Browser-process environment with the host's display servers
    REMOVED. Headless Chromium needs no display at all; scrubbing
    DISPLAY/WAYLAND_DISPLAY guarantees no host-display leak — even a
    hypothetical headed launch could not reach the user's desktop."""
    env = dict(os.environ)
    for var in ("DISPLAY", "WAYLAND_DISPLAY"):
        env.pop(var, None)
    return env


class VisibleBrowserForbidden(RuntimeError):
    """Raised when any code path would open a visible Chromium window."""


def _launch_kwargs(headless=True):
    """Single choke point for EVERY Chromium launch in this worker.
    Enforces the invisibility invariant: headless ALWAYS (new headless
    mode), host display scrubbed from the browser environment. Raises
    VisibleBrowserForbidden loudly instead of ever opening a visible
    window."""
    if headless is not True:
        raise VisibleBrowserForbidden(
            "refusing to launch Chromium with headless={0!r}: this "
            "worker NEVER opens a visible browser window".format(headless))
    return {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--headless=new",
        ],
        "env": _browser_env(),
        "viewport": {"width": 1920, "height": 1080},
    }


def _start_pinned_xvfb():
    """LAST-RESORT display fallback: start a pinned Xvfb virtual
    framebuffer (renders to memory only — nothing can appear on the
    host desktop) and return (display, process). Used only if a
    headless launch fails for lack of an X socket. The caller MUST
    terminate the returned process (see QwenWorker._disconnect).
    Raises loudly when no pinned display is available — never falls
    back to the host display."""
    import subprocess

    for n in range(_XVFB_DISPLAY_MIN, _XVFB_DISPLAY_MAX + 1):
        display = ":{0}".format(n)
        socket_path = "/tmp/.X11-unix/X{0}".format(n)
        if os.path.exists(socket_path):
            continue
        proc = subprocess.Popen(
            ["Xvfb", display, "-nolisten", "tcp",
             "-screen", "0", "1920x1080x24"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            if os.path.exists(socket_path):
                return display, proc
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        proc.terminate()
    raise RuntimeError(
        "headless Chromium launch failed and no pinned Xvfb display "
        "({0}-{1}) is available; refusing to fall back to a visible "
        "window on the host display".format(
            _XVFB_DISPLAY_MIN, _XVFB_DISPLAY_MAX))


def _snapshot_auth_storage(profile_path):
    """
    Snapshot auth-critical storage (localStorage leveldb + cookies) from the
    profile into _AUTH_BACKUP_DIR. Called right after a successful manual
    login, once Chromium has flushed state to disk (browser closed cleanly).
    Never prints file contents (credentials stay on disk only).
    """
    import shutil

    src_root = os.path.abspath(profile_path)
    if not os.path.isdir(src_root):
        return False
    try:
        os.makedirs(_AUTH_BACKUP_DIR, exist_ok=True)
        copied = []
        for rel in _AUTH_STORAGE_RELPATHS:
            src = os.path.join(src_root, rel)
            if os.path.exists(src):
                dst = os.path.join(_AUTH_BACKUP_DIR, rel)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                copied.append(rel)
        # remember which profile the backup came from
        with open(os.path.join(_AUTH_BACKUP_DIR, "source.txt"), "w") as f:
            f.write(src_root + "\n")
        return bool(copied)
    except Exception:
        return False


def _restore_auth_storage(profile_path):
    """
    Restore auth-critical storage from the backup into the profile.
    Returns True if a backup existed and was restored.
    Must run BEFORE Chromium launches on the profile.
    """
    import shutil

    dst_root = os.path.abspath(profile_path)
    if not os.path.isdir(_AUTH_BACKUP_DIR):
        return False
    try:
        restored = False
        for rel in _AUTH_STORAGE_RELPATHS:
            src = os.path.join(_AUTH_BACKUP_DIR, rel)
            dst = os.path.join(dst_root, rel)
            if os.path.exists(src):
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                restored = True
        return restored
    except Exception:
        return False


def _profile_in_use(profile_path):
    """True if another Chromium instance holds the profile (Singleton* files
    are only valid while the owner is alive; a stale lock has a dead pid)."""
    import glob

    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        p = os.path.join(profile_path, name)
        if os.path.islink(p) or os.path.exists(p):
            # Chromium SingletonLock is a symlink "hostname-pid"; verify pid
            target = ""
            try:
                target = os.readlink(p)
            except OSError:
                pass
            pid = None
            if "-" in target:
                try:
                    pid = int(target.rsplit("-", 1)[1])
                except ValueError:
                    pid = None
            if pid is not None:
                try:
                    os.kill(pid, 0)
                    return True  # owner alive -> genuinely in use
                except OSError:
                    continue  # stale lock, ignore
            else:
                return True  # cannot verify -> assume in use
    return False


class QwenWorkerState:
    """Worker state enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    NEEDS_AUTH = "needs_auth"
    AUTHENTICATED = "authenticated"
    DISCONNECTED = "disconnected"



class QwenWorker:
    """
    Headless worker mode.
    Uses the authenticated profile on PERSISTENT storage
    (~/.config/mavlinos/qwen-chromium-profile; a volatile /tmp
    profile is migrated away automatically). Operates invisibly -
    no Chromium window ever appears on the desktop. Extracts
    responses via network-level SSE/event-stream interception.
    """

    def __init__(self, profile_path=None, timeout=300):
        self.profile_path = profile_path
        self.timeout = timeout
        self.base_url = "https://coder.qwen.ai"
        self._stop_requested = False
        self.authenticated = False
        self.page = None
        self.browser = None
        self.context = None
        self.playwright = None
        self._response_text = None
        self._chat_id = None
        self._response_id = None
        self._completed = False
        self._feedback = {}
        self._repo = None
        self._xvfb_proc = None
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self._stop_requested = True

    async def _connect(self):
        """
        Connect to the authenticated persistent profile.
        headless=True for normal operation - no visible Chromium
        window. The profile path is resolved to PERSISTENT
        storage: a volatile (/tmp) profile is migrated (copied,
        never deleted) to the persistent default, because a /tmp
        profile wipes the login on every reboot. If the profile
        or its token is missing, the auth snapshot (taken at the
        last successful login) is restored BEFORE giving up.
        """
        metadata = _load_metadata()
        # Explicit --profile wins; otherwise the metadata value;
        # the persistent default is the final fallback.
        profile = (self.profile_path
                   or metadata.get("profile_path")
                   or _DEFAULT_PROFILE_DIR)
        if _is_volatile_profile_path(profile):
            profile = _migrate_volatile_profile(profile)

        if not os.path.isdir(profile):
            # First use of the persistent profile (or it was
            # wiped): rebuild the auth-critical storage from the
            # last known-good snapshot BEFORE the first launch.
            # Restore only fills in missing auth state; nothing
            # is ever deleted.
            os.makedirs(profile, exist_ok=True)
            if _restore_auth_storage(profile):
                print(
                    "[QwenWorker] Fresh persistent profile: restored "
                    "auth storage from the snapshot at {dir}.".format(
                        dir=_AUTH_BACKUP_DIR),
                    file=sys.stderr,
                )

        # Never share the profile with another live Chromium instance:
        # concurrent instances corrupt localStorage (root cause of the
        # 2026-10-05 session loss).
        if _profile_in_use(profile):
            print(
                "[QwenWorker] Profile is already in use by a running browser. "
                "Close the other browser first (sharing corrupts the session).",
                file=sys.stderr,
            )
            return False

        if not await self._launch_and_verify(profile):
            return False

        # Session verified: refresh the safety snapshot so a future profile
        # corruption can always be repaired from the newest known-good state.
        _snapshot_auth_storage(profile)

        print(
            "[QwenWorker] Connected to authenticated profile (headless): {profile}".format(
                profile=profile
            ),
            file=sys.stderr,
        )
        return True

    async def _launch_and_verify(self, profile, allow_restore=True):
        """Launch headless Chromium on the profile; verify the auth token.
        On a missing token: cleanly close, restore from the auth snapshot
        once, and retry. Returns True when the session is verified."""
        if not await self._launch(profile):
            return False

        self.authenticated = await self._has_token()
        if self.authenticated:
            return True

        if not allow_restore:
            await self._disconnect()
            return False

        # Token missing in the live profile: try restoring the snapshot.
        print(
            "[QwenWorker] Live profile lost the auth token; "
            "attempting restore from the auth snapshot...",
            file=sys.stderr,
        )
        await self._disconnect()
        if not _restore_auth_storage(profile):
            print(
                "[QwenWorker] Live profile lost the auth token and no "
                "auth snapshot is available (needs_auth). The login "
                "loss must be REPORTED to the repository owner — this "
                "worker never opens a visible browser and cannot "
                "perform a login itself.",
                file=sys.stderr,
            )
            return False

        if not await self._launch(profile):
            return False
        self.authenticated = await self._has_token()
        if not self.authenticated:
            print(
                "[QwenWorker] Snapshot token rejected/expired "
                "(needs_auth). The login loss must be REPORTED to "
                "the repository owner — this worker never opens a "
                "visible browser and cannot perform a login itself.",
                file=sys.stderr,
            )
            await self._disconnect()
            return False
        print("[QwenWorker] Session restored from auth snapshot.", file=sys.stderr)
        return True

    async def _launch(self, profile):
        """Launch headless Chromium on the profile and arm the SSE
        listener. Invisibility is enforced by _launch_kwargs (the
        only launch choke point): headless=new always, host display
        scrubbed from the browser environment. If the headless
        launch fails for lack of an X socket, retry under a PINNED
        Xvfb virtual display (memory-only framebuffer) — never the
        host display, never a visible window. Any remaining failure
        is fatal and loud."""
        try:
            self.playwright = await async_playwright().start()
            kwargs = _launch_kwargs(headless=True)
            try:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    profile, **kwargs
                )
            except Exception:
                # Last-resort: pinned Xvfb (virtual framebuffer,
                # renders to memory only). DISPLAY is set ONLY to
                # the pinned virtual display — the host display was
                # already scrubbed by _launch_kwargs and is never
                # restored.
                display, proc = _start_pinned_xvfb()
                self._xvfb_proc = proc
                xvfb_kwargs = dict(kwargs)
                xvfb_env = dict(kwargs["env"])
                xvfb_env["DISPLAY"] = display
                xvfb_kwargs["env"] = xvfb_env
                self.context = await self.playwright.chromium.launch_persistent_context(
                    profile, **xvfb_kwargs
                )
            self.browser = self.context.browser
            self.page = await self.context.new_page()
        except Exception as e:
            print(
                "[QwenWorker] Headless browser launch failed (no "
                "visible window was or will be opened): {e}".format(e=e),
                file=sys.stderr,
            )
            return False

        # Intercept network responses for SSE extraction
        self._response_text = None
        self._response_url = None
        self._chat_id = None
        self._response_id = None
        self._completed = False
        self._repo = None

        async def _handle_response(response):
            url = response.url
            # We are interested in completions SSE endpoint
            if "/task/completions" in url:
                text = await response.text()
                self._response_text = text
                self._response_url = url

        self.page.on("response", _handle_response)

        await self.page.goto(self.base_url)
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)
        return True

    async def _has_token(self):
        try:
            return bool(
                await self.page.evaluate(
                    "() => !!localStorage.getItem('token')"
                )
            )
        except Exception:
            return False

    async def _disconnect(self):
        """
        Close the browser cleanly. CRITICAL: Chromium must be closed via
        context.close() so it flushes localStorage/leveldb. Hard-killing
        the process mid-write previously corrupted the persisted session.
        """
        self._stop_requested = True
        for step in (self._close_context, self._stop_playwright):
            try:
                await step()
            except Exception:
                pass
        # Retire the pinned Xvfb if the last-resort fallback started one.
        if self._xvfb_proc is not None:
            try:
                self._xvfb_proc.terminate()
            except Exception:
                pass
            self._xvfb_proc = None
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    async def _close_context(self):
        if self.context:
            await self.context.close()

    async def _stop_playwright(self):
        if self.playwright:
            await self.playwright.stop()

    @staticmethod
    def _iter_sse_json_events(raw):
        """
        Iterate JSON event objects from a Qwen SSE body.
        The stream is raw JSON objects concatenated with no 'data:' prefix
        and no separator, so use json.JSONDecoder.raw_decode repeatedly.
        """
        decoder = json.JSONDecoder()
        idx = 0
        n = len(raw)
        while idx < n:
            # skip whitespace / newlines between events
            while idx < n and raw[idx] in " \r\n\t":
                idx += 1
            if idx >= n:
                break
            try:
                obj, end = decoder.raw_decode(raw, idx)
                yield obj
                idx = end
            except json.JSONDecodeError:
                # tolerate trailing partial event: stream may be truncated
                break

    def _extract_response_from_sse(self):
        """
        Extract the final answer from the captured Qwen SSE stream.

        Observed stream structure (network-level, verified against live
        traffic from coder.qwen.ai):
          {"response.created": {"chat_id": ..., "response_id": ...}}
          {"choices": [{"delta": {"role": "function", "content": ...,
                                  "phase": "code_working", ...}}], ...}
          {"choices": [{"delta": {"role": "assistant", "content": ...,
                                  "phase": "code_working", ...}}], ...}  (draft)
          {"choices": [{"delta": {"role": "assistant", "content": ...,
                                  "phase": "answer", ...}}], ...}        (final)
          {"choices": [{"delta": {"role": "assistant", "status": "finished",
                                  "phase": "answer"}}], ...}              (completion)

        The final user-facing answer is the concatenation of delta.content
        from events with phase == "answer". Completion is a delta with
        phase == "answer" and status == "finished".

        Stores chat_id / response_id / completion on the worker instance.
        Returns the answer text, or None if nothing was captured.
        """
        self._chat_id = None
        self._response_id = None
        self._completed = False
        if self._response_text is None:
            return None

        answer_parts = []
        draft_parts = []
        activity_parts = []
        answer_finished = False
        draft_finished = False

        for event in self._iter_sse_json_events(self._response_text):
            if not isinstance(event, dict):
                continue
            created = event.get("response.created")
            if isinstance(created, dict):
                self._chat_id = created.get("chat_id")
                self._response_id = created.get("response_id")
                continue
            choices = event.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                phase = delta.get("phase")
                status = delta.get("status")
                content = delta.get("content")
                if phase == "answer":
                    if isinstance(content, str) and content:
                        answer_parts.append(content)
                    if status == "finished":
                        answer_finished = True
                    extra = delta.get("extra")
                    if isinstance(extra, dict) and extra:
                        fb = self._extract_artifacts([delta])
                        if fb:
                            self._feedback.update(fb)
                elif phase == "code_working":
                    role = delta.get("role")
                    if role == "assistant" and isinstance(content, str) and content:
                        draft_parts.append(content)
                    elif role == "function" and isinstance(content, str) and content:
                        activity_parts.append(content)
                    if status == "finished" and role == "assistant":
                        draft_finished = True

        # Completion semantics (forward pass, evaluated after the whole
        # stream is parsed): the answer-phase "finished" delta completes the
        # response. A draft-phase "finished" delta only counts when the
        # stream has no answer phase at all (some responses end in draft).
        self._completed = answer_finished or (draft_finished and not answer_parts)

        answer = "".join(answer_parts).strip()
        if answer:
            return answer
        # no explicit answer phase yet (still streaming or draft only):
        # fall back to draft content so callers get partial progress
        draft = "".join(draft_parts).strip()
        if draft:
            return draft
        activity = "".join(activity_parts).strip()
        if activity:
            return activity
        return None

    def _chat_id_from_url(self):
        """Extract the conversation id from the page URL (/c/{chat_id})."""
        try:
            url = self.page.url
            if "/c/" in url:
                return url.rstrip("/").split("/c/")[-1].split("/")[0].split("?")[0] or None
        except Exception:
            pass
        return None

    async def _fetch_task_answer(self, chat_id):
        """
        Fetch the authoritative answer for a conversation from the same
        REST endpoint the Qwen frontend uses:
            GET /coder/api/v2/task/{chat_id}
        Response shape (verified against live traffic 2026-10-05):
            data.task.history.messages = { msg_id: {role, content_list, ...} }
        The assistant message's content_list uses the SAME phase model as
        the SSE stream: code_working (draft) + answer (final). The answer
        entry's extra carries file_list + commit_id — the verifiable work
        artifacts produced in the Qwen sandbox (feedback for the caller).
        Returns (answer_text | None, finished: bool, feedback: dict | None).
        """
        if not chat_id:
            return None, False, None
        try:
            raw = await self.page.evaluate(
                "async (cid) => {"
                "  const r = await fetch('/coder/api/v2/task/' + cid);"
                "  return await r.text();"
                "}",
                chat_id,
            )
            obj = json.loads(raw)
            history = (obj.get("data") or {}).get("task", {}).get("history")
            if isinstance(history, str):
                history = json.loads(history)
            messages = history.get("messages") if isinstance(history, dict) else None
            if not isinstance(messages, dict):
                return None, False, None
            # last assistant message by timestamp
            assistants = [
                m for m in messages.values()
                if isinstance(m, dict) and m.get("role") == "assistant"
            ]
            if not assistants:
                return None, False, None
            last = max(assistants, key=lambda m: m.get("timestamp") or 0)
            content_list = last.get("content_list") or []
            answer_parts = [c.get("content") or "" for c in content_list
                            if isinstance(c, dict) and c.get("phase") == "answer"]
            finished = any(
                isinstance(c, dict) and c.get("phase") == "answer"
                and c.get("status") == "finished" for c in content_list
            )
            answer = "".join(answer_parts).strip()
            feedback = self._extract_artifacts(content_list)
            return (answer or None), finished, feedback
        except Exception:
            return None, False, None

    @staticmethod
    def _extract_artifacts(content_list):
        """Pull verifiable work artifacts (file_list, commit_id, model)
        from the answer-phase content entry of a task or SSE stream."""
        feedback = {}
        for c in content_list:
            if not isinstance(c, dict) or c.get("phase") != "answer":
                continue
            extra = c.get("extra") or {}
            if isinstance(extra.get("file_list"), list):
                feedback["files"] = extra.get("file_list")
            if extra.get("commit_id"):
                feedback["commit_id"] = extra.get("commit_id")
            if extra.get("model"):
                feedback["model"] = extra.get("model")
        return feedback

    async def _await_completion(self):
        """
        Wait for the response to complete using two independent
        network-level sources (whichever finishes first wins):
          1. the SSE stream body captured by the response handler
             (closes when the stream ends; verified ~30-40s in practice)
          2. the REST task object (GET /task/{chat_id}) — the assistant
             message's answer phase carries status == "finished"
        Also resolves chat_id from the page URL the moment the app
        navigates to /c/{chat_id}.
        Returns the answer text or None.
        """
        start_time = time.time()
        while (time.time() - start_time) < self.timeout:
            # source 1: SSE body captured and parsed
            if self._response_text is not None:
                answer = self._extract_response_from_sse()
                if answer is not None and self._completed:
                    print(
                        "[QwenWorker] SSE stream complete at t+{t:.1f}s.".format(
                            t=time.time() - start_time
                        ),
                        file=sys.stderr,
                    )
                    return answer
            # source 2: REST task object
            if self._chat_id is None:
                self._chat_id = self._chat_id_from_url()
            if self._chat_id:
                answer, finished, feedback = await self._fetch_task_answer(self._chat_id)
                if answer is not None and finished:
                    self._completed = True
                    if feedback:
                        self._feedback.update(feedback)
                    print(
                        "[QwenWorker] Task API reports completion at t+{t:.1f}s.".format(
                            t=time.time() - start_time
                        ),
                        file=sys.stderr,
                    )
                    return answer
            if self._stop_requested:
                return None
            await asyncio.sleep(1.5)
        # timeout: best effort from whatever we have
        if self._response_text is not None:
            return self._extract_response_from_sse()
        if self._chat_id:
            answer, _, feedback = await self._fetch_task_answer(self._chat_id)
            if feedback:
                self._feedback.update(feedback)
            return answer
        return None

    async def select_repository(self, repo):
        """
        Select a connected GitHub repository for the next task via the
        '.repo-selector' panel (verified live 2026-10-05):
          Start new / No Repository — blank workspace
          Recent repositories / <name> — <owner>/<name>
        Without a selected repository Qwen works in an empty sandbox and
        answers are useless for repo-bound objectives.
        Returns True when the selector shows the repo after selection.
        """
        if not self.page:
            return False
        try:
            selector = self.page.locator(".repo-selector").first
            current = None
            # The SPA sometimes auto-restores the last conversation shortly
            # after load (the selector element detaches mid-read). Retry a
            # couple of times, forcing the home screen each attempt.
            for attempt in range(3):
                try:
                    if "/c/" in (self.page.url or ""):
                        await self.page.goto(self.base_url)
                        await self.page.wait_for_load_state("networkidle")
                        await self.page.wait_for_timeout(1500)
                    await selector.wait_for(state="visible", timeout=8000)
                    current = (await selector.inner_text(timeout=8000)).strip()
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    await self.page.wait_for_timeout(1500)
            if current and repo.lower() in current.lower():
                print(
                    "[QwenWorker] Repository already selected: {0}".format(current),
                    file=sys.stderr,
                )
                self._repo = current
                self._feedback["repo"] = current
                return True
            await selector.click()
            await self.page.wait_for_timeout(1500)

            # find the overlay item for the repo: match either "owner/name"
            # or the bare name; click the deepest matching element
            clicked = await self.page.evaluate(
                """(repo) => {
                    const target = repo.toLowerCase();
                    const matches = [];
                    for (const el of document.querySelectorAll('div,li,button,[role=option],[role=menuitem]')) {
                        const cs = getComputedStyle(el);
                        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
                        const r = el.getBoundingClientRect();
                        if (r.width < 40 || r.height < 10) continue;
                        const t = (el.innerText || '').trim();
                        if (!t || t.length > 60) continue;
                        const tl = t.toLowerCase();
                        if (tl === target || tl.includes(target)) {
                            matches.push(el);
                        }
                    }
                    if (!matches.length) return null;
                    // deepest = the one with the fewest descendant matches
                    let best = matches[0];
                    for (const m of matches) {
                        if (m !== best && best.contains(m)) best = m;
                    }
                    best.click();
                    return (best.innerText || '').trim();
                }""",
                repo,
            )
            if clicked is None:
                print(
                    "[QwenWorker] Repository '{0}' not found in the selector panel "
                    "(is it connected to the Qwen account?)".format(repo),
                    file=sys.stderr,
                )
                await self.page.keyboard.press("Escape")
                return False
            await self.page.wait_for_timeout(1500)
            # verify: prefer reading the selector again, but after selecting
            # a repo the app may transition to the environment screen and
            # detach the selector — then trust the click result itself.
            try:
                now = (await selector.inner_text(timeout=4000)).strip()
                ok = repo.lower() in now.lower() or "no repository" not in now.lower()
            except Exception:
                now = clicked or repo
                ok = True
            print(
                "[QwenWorker] Repository selected: clicked={0!r}, selector now={1!r}".format(
                    clicked, now
                ),
                file=sys.stderr,
            )
            self._repo = now
            self._feedback["repo"] = now
            return ok
        except Exception as e:
            print(
                "[QwenWorker] Failed to select repository {repo}: {e}".format(repo=repo, e=e),
                file=sys.stderr,
            )
            return False

    async def start_new_task(self):
        """
        Click the sidebar 'New Chat' button so the next prompt starts a
        FRESH conversation. Without this, the SPA sometimes restores the
        previous conversation under the root URL and the prompt silently
        appends to it. Best-effort: returns True even if the button is not
        found (the prompt may still start a new chat on a clean home page).
        """
        try:
            clicked = await self.page.evaluate(
                """() => {
                    for (const el of document.querySelectorAll('button, [role=button], a, div, span')) {
                        const t = (el.innerText || '').trim();
                        if (t !== 'New Chat') continue;
                        const r = el.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) continue;
                        // click the deepest matching element (avoid container dupes)
                        let target = el;
                        for (const child of el.querySelectorAll('*')) {
                            if ((child.innerText || '').trim() === 'New Chat') target = child;
                        }
                        target.click();
                        return true;
                    }
                    return false;
                }"""
            )
            if clicked:
                await self.page.wait_for_timeout(1500)
                print("[QwenWorker] New task started (New Chat clicked).", file=sys.stderr)
            return True
        except Exception:
            return True

    async def set_conversation(self, chat_id):
        """
        Navigate the worker to an existing conversation (/c/{chat_id}) so the
        next send_prompt continues it. Without this, each worker session
        starts wherever the app lands (often a new conversation) — explicit
        navigation gives the orchestrator deterministic conversation control.
        """
        if not self.page:
            return False
        try:
            url = "{base}/c/{chat_id}".format(base=self.base_url, chat_id=chat_id)
            await self.page.goto(url)
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)
            self._chat_id = self._chat_id_from_url()
            print(
                "[QwenWorker] Conversation set to: {chat_id}".format(chat_id=self._chat_id),
                file=sys.stderr,
            )
            return self._chat_id == chat_id
        except Exception as e:
            print(
                "[QwenWorker] Failed to open conversation {chat_id}: {e}".format(
                    chat_id=chat_id, e=e
                ),
                file=sys.stderr,
            )
            return False

    async def list_chats(self):
        """
        List all chats from the sidebar. Returns a list of dicts with
        'chat_id' and 'title' keys. Scrapes the sidebar DOM for
        div.task-item-container elements with id="{title}_{chat_id}".
        """
        if not self.page:
            return []
        try:
            chats = await self.page.evaluate(
                """() => {
                    const seen = new Set();
                    const result = [];
                    for (const el of document.querySelectorAll('.task-item-container')) {
                        const id = el.id || '';
                        const m = id.match(/_([a-f0-9-]{36})$/);
                        if (!m) continue;
                        const chatId = m[1];
                        if (seen.has(chatId)) continue;
                        seen.add(chatId);
                        const title = (el.querySelector('.task-item-name-text') || {}).innerText || '';
                        result.push({chat_id: chatId, title: title.trim().slice(0, 80)});
                    }
                    return result;
                }"""
            )
            return chats or []
        except Exception as e:
            print("[QwenWorker] Failed to list chats: {e}".format(e=e), file=sys.stderr)
            return []

    async def delete_chat(self, chat_id):
        """
        Delete a chat by its ID. Finds the div.task-item-container with
        id="{title}_{chat_id}", hovers to reveal the "more" dropdown,
        clicks it, then selects "Delete" from the dropdown menu.
        Returns True on success.
        """
        if not self.page or not chat_id:
            return False
        try:
            locator = self.page.locator(
                '.task-item-container[id$="_{cid}"]'.format(cid=chat_id)
            )
            if await locator.count() == 0:
                return False
            # Hover to reveal the "more" dropdown button
            await locator.first.hover()
            await self.page.wait_for_timeout(500)
            # Click the "more" dropdown trigger
            more_btn = locator.first.locator(
                '.task-item-more-icon, .qwen-chat-v2-dropdown-menu-trigger, '
                '[class*="operation-drop-down"] span[role="img"]'
            )
            if await more_btn.count() == 0:
                return False
            await more_btn.first.click()
            await self.page.wait_for_timeout(500)
            # Click "Delete" from the dropdown menu
            delete_item = self.page.locator(
                '[role="menuitem"]:has-text("Delete"), '
                '[role="menuitem"]:has-text("delete"), '
                'li:has-text("Delete"), '
                '.qwen-chat-v2-dropdown-menu-item:has-text("Delete")'
            )
            if await delete_item.count() > 0:
                await delete_item.first.click()
                await self.page.wait_for_timeout(1000)
                # Confirm deletion if a dialog appears
                confirm = self.page.locator(
                    'button:has-text("Delete"), button:has-text("Confirm"), '
                    'button:has-text("Yes"), button:has-text("OK")'
                )
                if await confirm.count() > 0:
                    await confirm.first.click()
                    await self.page.wait_for_timeout(500)
                print("[QwenWorker] Deleted chat: {id}".format(id=chat_id), file=sys.stderr)
                return True
            return False
        except Exception as e:
            print("[QwenWorker] Failed to delete chat {id}: {e}".format(id=chat_id, e=e), file=sys.stderr)
            return False

    async def ensure_designated_chat(self):
        """
        Ensure exactly one designated chat exists. If a designated chat
        is already stored in metadata, navigate to it and delete all others.
        If no designated chat exists, use the most recent one (or create one)
        and store it as designated. Returns the designated chat_id or None.
        """
        metadata = _load_metadata()
        designated = metadata.get(_DESIGNATED_CHAT_KEY)

        chats = await self.list_chats()
        if not chats:
            # No chats exist — start a new one and wait for the sidebar to update
            await self.start_new_task()
            # Navigate to base URL to force sidebar refresh
            await self.page.goto(self.base_url)
            await self.page.wait_for_load_state("networkidle")
            for _ in range(5):
                await self.page.wait_for_timeout(2000)
                chats = await self.list_chats()
                if chats:
                    break
            if not chats:
                print("[QwenWorker] No chats available after starting new task.", file=sys.stderr)
                return None
            # Use the first (most recent) chat
            designated = chats[0]["chat_id"]
            metadata[_DESIGNATED_CHAT_KEY] = designated
            _save_metadata(metadata)
            print("[QwenWorker] Designated new chat: {id}".format(id=designated), file=sys.stderr)
            return designated

        # Check if designated chat still exists
        chat_ids = [c["chat_id"] for c in chats]
        if designated and designated not in chat_ids:
            # Designated chat was deleted externally — pick the first one
            designated = chats[0]["chat_id"]
            metadata[_DESIGNATED_CHAT_KEY] = designated
            _save_metadata(metadata)
            print("[QwenWorker] Designated chat was gone; re-designated: {id}".format(id=designated), file=sys.stderr)
        elif not designated and chats:
            # No designated chat yet — pick the first one
            designated = chats[0]["chat_id"]
            metadata[_DESIGNATED_CHAT_KEY] = designated
            _save_metadata(metadata)
            print("[QwenWorker] Auto-designated first chat: {id}".format(id=designated), file=sys.stderr)

        # Delete all non-designated chats
        for chat in chats:
            if chat["chat_id"] != designated:
                await self.delete_chat(chat["chat_id"])

        # Navigate to the designated chat
        if not await self.set_conversation(designated):
            print("[QwenWorker] Failed to navigate to designated chat: {id}".format(id=designated), file=sys.stderr)
            return None

        print("[QwenWorker] Using designated chat: {id}".format(id=designated), file=sys.stderr)
        return designated

    async def send_prompt(self, prompt):
        """
        Send a prompt to Qwen web UI and capture the SSE response stream.
        Uses network interception instead of DOM scraping.
        Interacts with the input via Playwright Locators (re-resolve on each
        action, immune to React re-renders, CDP-level input React accepts).
        """
        try:
            # Use a Locator: it re-resolves before every action, which avoids
            # "Element is not attached to the DOM" after React re-renders.
            # fill()/type()/press() emulate real CDP-level input that the
            # React-based Qwen UI accepts (unlike setting .value via evaluate).
            input_selectors = [
                'textarea.code-agent-input-textarea',
                'textarea',
                'input[placeholder*="message"]',
                '.prompt-input',
                '#prompt-input',
                'input[type="text"]',
            ]
            textarea = None
            for sel in input_selectors:
                try:
                    loc = self.page.locator(sel).first
                    await loc.wait_for(state="visible", timeout=5000)
                    textarea = loc
                    print(
                        "[QwenWorker] Found input with selector: {sel}".format(sel=sel),
                        file=sys.stderr,
                    )
                    break
                except Exception:
                    continue

            if textarea is None:
                # Fallback: click body and press Enter
                await self.page.click("body")
                await asyncio.sleep(0.5)
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(1)
                print("[QwenWorker] Prompt sent via Enter key (fallback)", file=sys.stderr)
                return True

            # Interact via locator: each action re-resolves the element
            await textarea.click()
            await asyncio.sleep(0.2)
            await textarea.fill("")
            await asyncio.sleep(0.2)
            await textarea.type(prompt, delay=30)
            await asyncio.sleep(0.5)

            # Reset response capture BEFORE pressing Enter to avoid a race
            # where a fast response gets wiped by a late reset.
            self._response_text = None
            self._chat_id = None
            self._response_id = None
            self._completed = False
            self._feedback = {}
            if self._repo:
                # keep the repo label across the reset (chosen before submit)
                self._feedback["repo"] = self._repo
            self._stop_requested = False

            await textarea.press("Enter")
            await asyncio.sleep(1)

            print(
                "[QwenWorker] Prompt sent: {0}[{1}]".format(prompt[:60], len(prompt)),
                file=sys.stderr,
            )

            # Wait for completion via SSE stream or REST task object
            response_text = await self._await_completion()
            print(
                "[QwenWorker] Response extracted: {0}[{1}]".format(
                    str(response_text)[:200], len(str(response_text)) if response_text else 0
                ),
                file=sys.stderr,
            )
            return response_text

        except Exception as e:
            print("[QwenWorker] Error sending prompt: {e}".format(e=e), file=sys.stderr)
            return False

    async def wait(self):
        """
        Wait for the response to complete (SSE stream or REST task object,
        whichever reports completion first) and return the answer text.
        Returns None if no response captured within the timeout.
        """
        return await self._await_completion()

    def current_repo_label(self):
        """Read the current repository selector label (async-safe call
        inside send flow); returns None when unknown."""
        try:
            return self._feedback.get("repo")
        except Exception:
            return None

    async def run(self, mode="start", prompt=None, chat_id=None, repo=None):
        if mode == "start":
            return await self._connect()
        elif mode == "send":
            if not prompt:
                print("[QwenWorker] --prompt is required for send mode", file=sys.stderr)
                return False
            if not self.page:
                print(
                    "[QwenWorker] Worker not connected. Run with 'start' mode first.",
                    file=sys.stderr,
                )
                return False
            if chat_id:
                # Explicit --chat: designate it and use it
                metadata = _load_metadata()
                metadata[_DESIGNATED_CHAT_KEY] = chat_id
                _save_metadata(metadata)
                if not await self.set_conversation(chat_id):
                    return False
            else:
                # Always use the single designated chat (owner directive:
                # never create new chats, delete old ones, all requests
                # sequential in one chat)
                designated = await self.ensure_designated_chat()
                if not designated:
                    return False
            if repo:
                # The .repo-selector lives on the home screen. If the app
                # restored a previous conversation (/c/{id}), its toolbar has
                # a different layout — go home so the repo can be selected
                # for a NEW task (a --chat continuation keeps its binding).
                if not chat_id and "/c/" in (self.page.url or ""):
                    await self.page.goto(self.base_url)
                    await self.page.wait_for_load_state("networkidle")
                    await self.page.wait_for_timeout(1000)
                if not await self.select_repository(repo):
                    return False
            return await self.send_prompt(prompt)
        elif mode == "wait":
            if not self.page:
                print(
                    "[QwenWorker] Worker not connected. Run with 'start' mode first.",
                    file=sys.stderr,
                )
                return None
            return await self.wait()
        elif mode == "stop":
            self._stop_requested = True
            print("[QwenWorker] Stop requested; closing browser cleanly.", file=sys.stderr)
            await self._disconnect()
            print("[QwenWorker] Stopped.", file=sys.stderr)
            return True
        elif mode == "check":
            return await self._connect()
        else:
            print("[QwenWorker] Unknown mode: {mode}".format(mode=mode), file=sys.stderr)
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Qwen Web Worker - Playwright-based automation for coder.qwen.ai"
    )
    parser.add_argument("mode", choices=["start", "auth", "status", "check", "send", "wait", "stop", "list-chats", "designate-chat"], help="Worker mode")
    parser.add_argument("--profile", default=None, help="Persistent Chromium profile path (defaults to metadata)")
    parser.add_argument("--prompt", default=None, help="Prompt text to send (for send mode)")
    parser.add_argument("--chat", default=None, help="Conversation/chat id to continue (send mode); omit to use the designated chat")
    parser.add_argument("--repo", default=None, help="Repository to select for the task (send mode), e.g. AnsvipaRinh/MavLin_OS or MavLinOS; omit for a blank workspace")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum wait time in seconds (default: 300 = 5 min)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output for send/check/status/list-chats/designate-chat")
    args = parser.parse_args()

    if args.mode == "auth":
        # DISABLED (2026-10-07): this worker must NEVER open a
        # visible browser window. Fail loudly instead. The
        # authenticated profile is persistent and auto-restored
        # from the auth snapshot, so an interactive login is
        # never needed; if the session is truly lost, the loss
        # is REPORTED — a login is never attempted here.
        print(
            "[QwenWorker] FATAL: 'auth' mode is permanently disabled. "
            "This worker NEVER opens a visible browser window "
            "(headless=new is enforced on every launch; the host "
            "display is scrubbed from the browser environment). The "
            "persistent profile is {profile} and the auth snapshot "
            "is {backup}. If the coder.qwen.ai session is truly "
            "lost, REPORT that to the repository owner — do not "
            "attempt an interactive login from this worker.".format(
                profile=_DEFAULT_PROFILE_DIR, backup=_AUTH_BACKUP_DIR),
            file=sys.stderr,
        )
        sys.exit(2)

    if args.mode == "status":
        metadata = _load_metadata()
        print(json.dumps({
            "mode": "status",
            "chat_id": metadata.get("chat_id"),
            "profile_path": metadata.get("profile_path"),
            "auth_backup_present": os.path.isdir(_AUTH_BACKUP_DIR),
        }))
        return

    # Worker modes: always close the browser cleanly at exit so Chromium
    # flushes its storage (a hard-killed browser loses localStorage writes).
    worker = QwenWorker(profile_path=args.profile, timeout=args.timeout)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if args.mode == "check":
            ok = loop.run_until_complete(worker.run(mode="check"))
            if args.json:
                print(json.dumps({
                    "mode": "check",
                    "authenticated": bool(ok),
                    "state": "authenticated" if ok else "needs_auth",
                    "profile_in_use": False,
                }))
            else:
                print(
                    "[QwenWorker] Auth check: {state}".format(
                        state="authenticated" if ok else "needs_auth"
                    ),
                    file=sys.stderr,
                )
        elif args.mode == "start":
            result = loop.run_until_complete(worker.run(mode="start"))
            if result:
                print(
                    "[QwenWorker] Started successfully (headless). Use 'send' and 'wait' modes.",
                    file=sys.stderr,
                )
        elif args.mode == "send":
            connect_result = loop.run_until_complete(worker.run(mode="start"))
            if not connect_result:
                if args.json:
                    print(json.dumps({"mode": "send", "ok": False, "state": "needs_auth"}))
                else:
                    print("[QwenWorker] Failed to connect (needs_auth).", file=sys.stderr)
                return
            send_result = loop.run_until_complete(
                worker.run(mode="send", prompt=args.prompt, chat_id=args.chat, repo=args.repo))
            if not send_result:
                # send failed (connect/input/repo/chat) — never fall through
                # to wait(): a restored old conversation would answer instead
                # of this prompt (stale-answer bug, fixed 2026-10-05)
                if args.json:
                    print(json.dumps({"mode": "send", "ok": False, "state": "send_failed"}))
                else:
                    print("[QwenWorker] Failed to send prompt.", file=sys.stderr)
                return
            response = loop.run_until_complete(worker.run(mode="wait"))
            if args.json:
                print(json.dumps({
                    "mode": "send",
                    "ok": bool(response),
                    "completed": bool(worker._completed),
                    "chat_id": worker._chat_id,
                    "response": response,
                    "repo": worker._feedback.get("repo"),
                    "files": worker._feedback.get("files"),
                    "commit_id": worker._feedback.get("commit_id"),
                    "model": worker._feedback.get("model"),
                }))
            else:
                if response:
                    print(
                        "[QwenWorker] Response: {response}[{len}]".format(
                            response=str(response)[:200], len=len(str(response))
                        ),
                        file=sys.stderr,
                    )
                else:
                    print(
                        "[QwenWorker] Waiting timed out or no response received.",
                        file=sys.stderr,
                    )
        elif args.mode == "wait":
            response = loop.run_until_complete(worker.run(mode="wait"))
            if args.json:
                print(json.dumps({
                    "mode": "wait",
                    "ok": bool(response),
                    "completed": bool(worker._completed),
                    "chat_id": worker._chat_id,
                    "response": response,
                }))
            elif response:
                print(
                    "[QwenWorker] Response: {response}[{len}]".format(
                        response=str(response)[:200], len=len(str(response))
                    ),
                    file=sys.stderr,
                )
            else:
                print("[QwenWorker] Waiting timed out or no response received.", file=sys.stderr)
        elif args.mode == "list-chats":
            connect_result = loop.run_until_complete(worker.run(mode="start"))
            if not connect_result:
                if args.json:
                    print(json.dumps({"mode": "list-chats", "ok": False, "state": "needs_auth"}))
                else:
                    print("[QwenWorker] Failed to connect (needs_auth).", file=sys.stderr)
                return
            chats = loop.run_until_complete(worker.list_chats())
            if args.json:
                print(json.dumps({"mode": "list-chats", "ok": True, "chats": chats, "count": len(chats)}))
            else:
                for c in chats:
                    print("[QwenWorker] Chat: {id} — {title}".format(id=c["chat_id"], title=c["title"]))
        elif args.mode == "designate-chat":
            connect_result = loop.run_until_complete(worker.run(mode="start"))
            if not connect_result:
                if args.json:
                    print(json.dumps({"mode": "designate-chat", "ok": False, "state": "needs_auth"}))
                else:
                    print("[QwenWorker] Failed to connect (needs_auth).", file=sys.stderr)
                return
            if args.chat:
                # Explicit designation
                metadata = _load_metadata()
                metadata[_DESIGNATED_CHAT_KEY] = args.chat
                _save_metadata(metadata)
                chats = loop.run_until_complete(worker.list_chats())
                for c in chats:
                    if c["chat_id"] != args.chat:
                        loop.run_until_complete(worker.delete_chat(c["chat_id"]))
                loop.run_until_complete(worker.set_conversation(args.chat))
                if args.json:
                    print(json.dumps({"mode": "designate-chat", "ok": True, "chat_id": args.chat}))
                else:
                    print("[QwenWorker] Designated chat: {id}".format(id=args.chat))
            else:
                # Auto-designate: use ensure_designated_chat
                designated = loop.run_until_complete(worker.ensure_designated_chat())
                if args.json:
                    print(json.dumps({"mode": "designate-chat", "ok": bool(designated), "chat_id": designated}))
                else:
                    if designated:
                        print("[QwenWorker] Designated chat: {id}".format(id=designated))
                    else:
                        print("[QwenWorker] Failed to designate a chat.", file=sys.stderr)
        elif args.mode == "stop":
            loop.run_until_complete(worker.run(mode="stop"))
    finally:
        try:
            loop.run_until_complete(worker._disconnect())
        except Exception:
            pass
        loop.close()


if __name__ == "__main__":
    main()