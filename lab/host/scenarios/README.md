# Lab Scenarios

Scenario inventory for the mavericks-lab control plane.

## Current: Declarative YAML Harness (Phase 2, commit 1d56515)

Failure-injection scenarios live in `lab/harness/scenarios/*.yaml` (25 scenarios)
and run against pluggable backends (sim/qemu/mac-stub) via
`python3 lab/harness/harness.py --backend <b> --all`. See `docs/LAB_HARNESS.md`.

## Built-in Scenarios (host controller, `lab/host/lib/scenarios.py`)

Run on-demand via `mavericks-lab test <name>`:

- `echo` — connectivity test
- `disk-write` — write/read/verify 1MB, measure latency
- `cpu-load` — brief CPU load, measure iterations
- `memory` — allocate/touch/free memory
- `bench-disk` — benchmark disk I/O
- `bench-cpu` — benchmark CPU

## Superseded: External Scenario Scripts (Phase 2 seam — NOT implemented)

The original Phase 2 plan was external shell/python scripts in this directory
(receive target data dir as `$1`, exit 0 on pass, JSON metrics on stdout).
This was superseded by the declarative YAML harness, which separates scenario
from target backend and covers failure injection (network down, agent crash,
corrupted image, checksum failure, host crash, power loss, boot loop) that
external scripts could not express. This directory is retained for future
external scenario scripts only if a need arises that the YAML harness cannot
express.
