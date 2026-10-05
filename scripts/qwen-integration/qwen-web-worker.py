#!/usr/bin/env python3
"""
Qwen Web Worker - Playwright-based automation for coder.qwen.ai

Machine-readable interface for OpenCode registrar integration.

Modes:
  auth        - Authentication bootstrap mode (visible browser, wait for user login)
  start       - Start/resume worker (headless, uses preserved authenticated profile)
  status      - Get worker state
  send        - Send a prompt
  wait        - Wait for completion
  stop        - Stop worker

Usage:
    qwen-web-worker.py auth                    # Auth bootstrap mode (visible, one-time)
    qwen-web-worker.py start                    # Start/resume worker (headless)
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
from playwright.async_api import async_playwright


_META_DIR = os.path.expanduser("~/.config/mavlinos")
_META_FILE = os.path.join(_META_DIR, "qwen-worker-state.json")
_AUTH_BACKUP_DIR = os.path.join(_META_DIR, "qwen-auth-backup")
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


class QwenAuthWorker:
    """
    Authentication bootstrap mode.
    Visible Chromium: user manually logs into Google/Qwen.
    Persistent authenticated profile is established and saved.
    Subsequent worker starts use this profile in headless mode.
    """

    def __init__(self, profile_path="/tmp/chromium-qwen-profile", timeout=300):
        # Ensure we have a valid profile path
        if profile_path is None:
            profile_path = "/tmp/chromium-qwen-profile"
        self.profile_path = profile_path
        self.timeout = timeout
        self.base_url = "https://coder.qwen.ai"
        self.token_detected = False
        self.auth_time = None
        self._stop_requested = False
        self.page = None
        self.browser = None
        self.context = None
        self.playwright = None
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self._stop_requested = True

    async def _detect_token(self):
        try:
            if self.page:
                token = await self.page.evaluate(
                    "( () => localStorage.getItem('token') )"
                )
                if token:
                    self.token_detected = True
                    self.auth_time = time.time()
                    return True
        except Exception:
            pass
        return False

    async def run(self):
        self._stop_requested = False
        self.token_detected = False
        self.auth_time = None
        metadata = _load_metadata()
        saved_profile = metadata.get("profile_path", self.profile_path)
        # Use explicit default if no profile in metadata
        if not saved_profile:
            saved_profile = self.profile_path or "/tmp/chromium-qwen-profile"

        # Refuse to share the profile with another live Chromium instance:
        # concurrent instances on one user-data-dir corrupt localStorage
        # (that is exactly how a valid session was lost on 2026-10-05).
        if _profile_in_use(self.profile_path):
            print(
                "[QwenAuth] Profile is already in use by a running browser. "
                "Close it first (this sharing corrupts the saved session).",
                file=sys.stderr,
            )
            return

        self.playwright = await async_playwright().start()

        # Launch persistent context with saved profile; headless=False for auth bootstrap
        args = ["--no-sandbox", "--disable-dev-shm-usage"]
        self.context = await self.playwright.chromium.launch_persistent_context(
            self.profile_path,
            headless=False,
            args=args,
            viewport={"width": 1920, "height": 1080},
        )
        self.browser = self.context.browser
        self.page = await self.context.new_page()
        await self.page.goto(self.base_url)
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        print(
            "[QwenAuth] Browser opened visibly. Navigate to coder.qwen.ai and log in.",
            file=sys.stderr,
        )
        print(
            "[QwenAuth] Use the window's mouse/keyboard to complete login.",
            file=sys.stderr,
        )
        print(
            "[QwenAuth] WAIT until the page fully loads after login (you'll see dashboard/chat).",
            file=sys.stderr,
        )
        print(
            "[QwenAuth] THEN RETURN HERE and I'll detect your session.",
            file=sys.stderr,
        )

        start_time = time.time()
        while not self._stop_requested and (time.time() - start_time) < self.timeout:
            if await self._detect_token():
                self._stop_requested = True
                self.auth_time = time.time()
                if self.page and self.page.context:
                    try:
                        chat_id = await self.page.evaluate(
                            "( () => { const s = window.uc?.getState?.()?.chatId || window.store?.getState?.()?.chatId || null; return s; } )"
                        )
                        _save_metadata({"chat_id": chat_id, "profile_path": self.profile_path})
                        print(
                            "[QwenAuth] Authentication detected! Session metadata saved.",
                            file=sys.stderr,
                        )
                        print(
                            "[QwenAuth] Profile path: {self.profile_path}".format(
                                self_profile_path=self.profile_path
                            ),
                            file=sys.stderr,
                        )
                        print(
                            "[QwenAuth] You may now close this message and run:",
                            file=sys.stderr,
                        )
                        print(
                            "[QwenAuth]   python3 scripts/qwen-integration/qwen-web-worker.py start",
                            file=sys.stderr,
                        )
                        print(
                            "[QwenAuth]   or run prompts with: python3 scripts/qwen-integration/qwen-web-worker.py send --prompt 'your prompt'",
                            file=sys.stderr,
                        )
                    except Exception:
                        print(
                            "[QwenAuth] Authentication detected! Could not extract chat_id.",
                            file=sys.stderr,
                        )
                        _save_metadata({"chat_id": None, "profile_path": self.profile_path})
                    break
            await asyncio.sleep(3)

        if not self._stop_requested:
            print(
                "[QwenAuth] Timeout waiting for authentication ({max_sec}s).".format(
                    max_sec=self.timeout
                ),
                file=sys.stderr,
            )

        # CLEAN CLOSE is critical: Chromium flushes localStorage/leveldb only
        # on an orderly shutdown. Hard kills lose recently written state —
        # a valid session was lost exactly this way. Never keep the auth
        # browser open: a leftover visible browser + a headless worker on the
        # same profile corrupt each other.
        print(
            "[QwenAuth] Closing browser cleanly to persist the session...",
            file=sys.stderr,
        )
        for closer in (self._close_context, self._stop_playwright):
            try:
                await closer()
            except Exception:
                pass

        if self.token_detected:
            backup_ok = _snapshot_auth_storage(self.profile_path)
            if backup_ok:
                print(
                    "[QwenAuth] Auth storage snapshot saved to {dir} "
                    "(auto-restore available if the live profile ever loses the session).".format(
                        dir=_AUTH_BACKUP_DIR
                    ),
                    file=sys.stderr,
                )
            else:
                print(
                    "[QwenAuth] WARNING: auth storage snapshot failed; "
                    "session persists only in the live profile.",
                    file=sys.stderr,
                )
        print(
            "[QwenAuth] Auth bootstrap complete. The persistent profile at: {profile_path} "
            "is ready for subsequent INVISIBLE (headless) worker starts.".format(
                profile_path=self.profile_path
            ),
            file=sys.stderr,
        )

    async def _close_context(self):
        if self.context:
            await self.context.close()

    async def _stop_playwright(self):
        if self.playwright:
            await self.playwright.stop()


class QwenWorker:
    """
    Headless worker mode.
    Uses the authenticated persistent profile established during auth bootstrap.
    Operates invisibly - no Chromium window appears on the Windows desktop.
    Extracts responses via network-level SSE/event-stream interception.
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
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self._stop_requested = True

    async def _connect(self):
        """
        Connect to the authenticated persistent profile.
        headless=True for normal operation - no visible Chromium window.
        If the live profile lost its token, auto-restore from the auth
        snapshot (taken at last successful login) before giving up.
        """
        metadata = _load_metadata()
        profile = metadata.get("profile_path", self.profile_path)
        if not profile or not os.path.exists(profile):
            print(
                "[QwenWorker] No authenticated profile found in metadata.",
                file=sys.stderr,
            )
            return False

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
                "[QwenWorker] No auth snapshot available (needs_auth). "
                "Run the visible one-time 'auth' mode to login again.",
                file=sys.stderr,
            )
            return False

        if not await self._launch(profile):
            return False
        self.authenticated = await self._has_token()
        if not self.authenticated:
            print(
                "[QwenWorker] Snapshot token rejected/expired (needs_auth). "
                "Run the visible one-time 'auth' mode to login again.",
                file=sys.stderr,
            )
            await self._disconnect()
            return False
        print("[QwenWorker] Session restored from auth snapshot.", file=sys.stderr)
        return True

    async def _launch(self, profile):
        """Launch headless Chromium on the profile and arm the SSE listener."""
        try:
            self.playwright = await async_playwright().start()
            args = ["--no-sandbox", "--disable-dev-shm-usage"]
            self.context = await self.playwright.chromium.launch_persistent_context(
                profile,
                headless=True,
                args=args,
                viewport={"width": 1920, "height": 1080},
            )
            self.browser = self.context.browser
            self.page = await self.context.new_page()
        except Exception as e:
            print(
                "[QwenWorker] Browser launch failed: {e}".format(e=e), file=sys.stderr
            )
            return False

        # Intercept network responses for SSE extraction
        self._response_text = None
        self._response_url = None
        self._chat_id = None
        self._response_id = None
        self._completed = False

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
            self._stop_requested = False

            await textarea.press("Enter")
            await asyncio.sleep(1)

            print(
                "[QwenWorker] Prompt sent: {0}[{1}]".format(prompt[:60], len(prompt)),
                file=sys.stderr,
            )

            # Wait for the SSE response stream (response.text() in the network
            # handler resolves only when the SSE stream completes)
            start_time = time.time()
            while (time.time() - start_time) < self.timeout:
                if self._response_text is not None:
                    break
                # Check if stop was requested
                if self._stop_requested:
                    return False
                await asyncio.sleep(0.5)

            # Extract response from SSE chunks
            response_text = self._extract_response_from_sse()
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
        Wait for the captured SSE stream to complete, then return the answer.
        Polls the captured stream; completion is the delta event with
        phase == "answer" and status == "finished".
        Returns the answer text or None if no response captured.
        """
        start_time = time.time()
        while (time.time() - start_time) < self.timeout:
            response_text = self._extract_response_from_sse()
            if response_text is not None and self._completed:
                return response_text
            if self._stop_requested:
                break
            await asyncio.sleep(0.5)
        # timeout or stop requested: return best effort
        return self._extract_response_from_sse()

    async def run(self, mode="start", prompt=None):
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
    parser.add_argument("mode", choices=["start", "auth", "status", "check", "send", "wait", "stop"], help="Worker mode")
    parser.add_argument("--profile", default=None, help="Persistent Chromium profile path (defaults to metadata)")
    parser.add_argument("--prompt", default=None, help="Prompt text to send (for send mode)")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum wait time in seconds (default: 300 = 5 min)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output for send/check/status")
    args = parser.parse_args()

    if args.mode == "auth":
        auth_worker = QwenAuthWorker(profile_path=args.profile, timeout=args.timeout)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(auth_worker.run())
        finally:
            loop.close()
        return

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
            send_result = loop.run_until_complete(worker.run(mode="send", prompt=args.prompt))
            response = loop.run_until_complete(worker.run(mode="wait"))
            if args.json:
                print(json.dumps({
                    "mode": "send",
                    "ok": bool(response),
                    "completed": bool(worker._completed),
                    "chat_id": worker._chat_id,
                    "response": response,
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