"""Scenario registry for the mavericks-lab host controller.

Phase 1: built-in scenarios only. Phase 2: external scenario scripts
in lab/host/scenarios/ with failure injection and full QEMU harness.
"""

BUILTIN_SCENARIOS = {
    "echo": {"cmd": "run-test", "args": {"name": "echo", "args": {"text": "lab-test"}}},
    "disk-write": {"cmd": "run-test", "args": {"name": "disk-write"}},
    "cpu-load": {"cmd": "run-test", "args": {"name": "cpu-load", "args": {"duration": 0.5}}},
    "memory": {"cmd": "run-test", "args": {"name": "memory", "args": {"size_mb": 5}}},
    "bench-disk": {"cmd": "benchmark", "args": {"name": "disk-write"}},
    "bench-cpu": {"cmd": "benchmark", "args": {"name": "cpu-load", "args": {"duration": 1.0}}},
}


def get_scenario(name):
    return BUILTIN_SCENARIOS.get(name)


def list_scenarios():
    return sorted(BUILTIN_SCENARIOS.keys())
