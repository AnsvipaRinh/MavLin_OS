#!/usr/bin/env python3
"""Live transport tests A-D for the Qwen web worker (headless, network SSE)."""
import asyncio
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "qwen_web_worker", "/home/builder/projects/MavLinOS/scripts/qwen-integration/qwen-web-worker.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
QwenWorker = mod.QwenWorker

PROMPT_B = ("Reply with exactly the single string QWEN_TRANSPORT_TEST_7F3A. "
            "Do not create files. Do not browse. Do not perform any other action. "
            "Do not explain anything.")
PROMPT_C = ("Reply with exactly the single string QWEN_FOLLOWUP_TEST_91C2. "
            "Do not perform any other action.")


def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


async def main():
    results = []

    # Test A: authenticated headless startup
    worker = QwenWorker(profile_path="/tmp/chromium-qwen-profile", timeout=240)
    print("=== Test A: authenticated headless startup ===")
    connected = await worker.run(mode="start")
    results.append(report("A: headless connect with preserved profile", bool(connected)))
    if not connected:
        sys.exit(1)

    # Test B: deterministic request
    print("=== Test B: deterministic request ===")
    resp_b = await worker.run(mode="send", prompt=PROMPT_B)
    results.append(report("B: response contains QWEN_TRANSPORT_TEST_7F3A",
                          bool(resp_b) and "QWEN_TRANSPORT_TEST_7F3A" in resp_b,
                          f"completed={worker._completed} chat_id={worker._chat_id} "
                          f"resp={str(resp_b)[:80]!r}"))
    results.append(report("B: completion detected (answer phase finished)", worker._completed))
    chat_id_b = worker._chat_id
    results.append(report("B: chat_id captured", bool(chat_id_b)))

    # Test C: same conversation followup
    print("=== Test C: followup in same conversation ===")
    resp_c = await worker.run(mode="send", prompt=PROMPT_C)
    chat_id_c = worker._chat_id
    results.append(report("C: response contains QWEN_FOLLOWUP_TEST_91C2",
                          bool(resp_c) and "QWEN_FOLLOWUP_TEST_91C2" in resp_c,
                          f"completed={worker._completed} resp={str(resp_c)[:80]!r}"))
    results.append(report("C: same chat_id as Test B",
                          bool(chat_id_b) and chat_id_b == chat_id_c,
                          f"{chat_id_b} == {chat_id_c}"))

    # Test D: restart without re-auth
    print("=== Test D: restart without re-authentication ===")
    await worker.run(mode="stop")
    worker2 = QwenWorker(profile_path="/tmp/chromium-qwen-profile", timeout=240)
    reconnected = await worker2.run(mode="start")
    results.append(report("D: reconnect after restart (no re-auth)", bool(reconnected)))
    resp_d = await worker2.run(mode="send", prompt=PROMPT_B)
    results.append(report("D: deterministic test after restart",
                          bool(resp_d) and "QWEN_TRANSPORT_TEST_7F3A" in resp_d,
                          f"completed={worker2._completed} resp={str(resp_d)[:80]!r}"))
    await worker2.run(mode="stop")

    print("\n=== SUMMARY ===")
    print(f"{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


asyncio.run(main())
