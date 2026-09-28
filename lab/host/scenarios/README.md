# Lab Scenarios (Phase 2 seam)

This directory will contain external test/benchmark scenario scripts for the
mavericks-lab control plane.

## Phase 1

Built-in scenarios only (defined in `lab/host/lib/scenarios.py`):

- `echo` — connectivity test
- `disk-write` — write/read/verify 1MB, measure latency
- `cpu-load` — brief CPU load, measure iterations
- `memory` — allocate/touch/free memory
- `bench-disk` — benchmark disk I/O
- `bench-cpu` — benchmark CPU

## Phase 2

External scenario scripts will be placed here. Each scenario is a shell or
python script that:

1. Receives the target's data dir as `$1`
2. Performs the test/benchmark
3. Exits 0 on pass, non-zero on fail
4. Writes metrics to stdout as JSON

The host controller's `test_scenario` will:
1. Deploy image to inactive slot
2. Select-boot + reboot
3. Wait for HEALTHY
4. Execute scenario script on target
5. Collect results
6. Commit or rollback

Failure injection scenarios will simulate:
- Network interruption during deploy
- Agent crash mid-boot
- Health check failure (disk full, network down)
- Boot-loop (repeated failures)
- Power-loss during state transition
