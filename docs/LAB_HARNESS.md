# Lab Harness — QEMU/OVMF A/B Test Infrastructure

Deterministic test harness for the mavericks-lab A/B deployment system.
Runs 25 failure-injection scenarios against pluggable target backends.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  HARNESS DRIVER (harness.py)                        │
│  loads scenario YAML → executes steps → asserts     │
│  on serial log + journal + boot state + result DB   │
└──────────────────────┬──────────────────────────────┘
                       │ TargetBackend API
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     SimBackend   QemuBackend   MacBackend
     (dirs+host)  (real guest)  (documented stub)
```

## Backends

### SimBackend (primary, always works, rootless)
- Agent runs on host via `agent serve` / `agent boot`
- DATA dir = plain directory; rootfs = marker files
- Network-down: agent runs inside `unshare -rn` (empty /proc/net/route)
- Network-up: agent runs normally (host has routes)
- Serial log = file written by the backend

### QemuBackend (real guest boot)
- Direct kernel boot: `qemu-system-x86_64 -kernel vmlinuz -initrd initramfs -append "console=ttyS0"`
- DATA disk: virtio-blk (CONFIG_VIRTIO_BLK=y), ext4 (CONFIG_EXT4_FS=y)
- Guest init (python, PID 1): mounts DATA, runs boot stages + agent, command loop
- Host writes `cmd.json` to DATA → guest runs `agent serve` → host reads `resp.json`
- Serial log = QEMU `-serial file:` (ground truth)
- **Known limitation**: network-up cannot create a route in the guest
  (virtio-net module fails with "Unknown symbol" — virtio_ring not exported;
  netlink RTM_NEWROUTE/RTM_NEWADDR don't create routes for loopback).
  Network-down scenarios work correctly. Network-up scenarios are
  expected to fail the health check in QEMU mode (documented).
- **Full QEMU run (2026-09-29)**: 1 passed / 18 failed / 6 skipped.
  All 18 failures are this network-up limitation (health check fails →
  ROLLBACK). The 6 skips declare `backends: [sim]` only. The sim backend
  (primary) passes 25/25 and covers the network-up paths.

### MacBackend (documented stub)
- Placeholder for future MacBook10,1 hardware validation
- Documents intended efibootmgr -n/-o boot selection
- Raises NotImplementedError; does NOT modify production bootloader

## Scenario Format

Declarative YAML in `lab/harness/scenarios/*.yaml`:

```yaml
name: 03_b_boots
description: Deploy B, select-boot B, reboot, B boots healthy
backends: [sim, qemu]
fixture:              # initial conditions
  slot_a_image: v1
  slot_b_image: v2
  network: up
steps:                # executed in order
  - boot: {expect_state: HEALTHY}
  - deploy: {slot: B, image: v2, version: v2}
  - select_boot: B
  - reboot: {}
expected:             # assertions
  serial_contains: [BOOT slot=B, AGENT_BOOT state=HEALTHY]
  state: HEALTHY
  active_slot: B
```

### Step types
`boot`, `reboot`, `deploy`, `select_boot`, `commit`, `rollback`,
`status`, `verify`, `inject` (network_down/network_up/agent_off/
corrupt_rootfs/systemd_fail), `power_loss`, `host_crash`, `wait`

### Assertion types
`serial_contains`, `serial_not_contains`, `state`, `active_slot`,
`journal_contains`, `boot_current`, `boot_next`

## 25 Scenarios

| # | Name | Tests |
|---|------|-------|
| 01 | successful_a_boot | Fresh boot A → HEALTHY |
| 02 | deploy_b | Deploy image to slot B |
| 03 | b_boots | Select B, reboot, B boots |
| 04 | b_health_pass | B health check passes |
| 05 | b_commit | B commits |
| 06 | b_kernel_fail | Corrupted kernel marker → ROOTFS_FAIL |
| 07 | b_initramfs_fail | Initramfs failure → SYSTEMD_FAIL |
| 08 | b_rootfs_corruption | Rootfs corruption → ROOTFS_FAIL |
| 09 | b_systemd_fail | Systemd failure → SYSTEMD_FAIL |
| 10 | b_network_fail | Network down → health fail → rollback |
| 11 | agent_never_starts | Agent disabled → AGENT_SKIP |
| 12 | agent_crash | Agent crash (simulated) |
| 13 | health_timeout | Repeated failures → BOOT_LOOP_HALT |
| 14 | interrupted_transfer | Interrupted deploy, state consistent |
| 15 | corrupted_image | Corrupted image rejected |
| 16 | checksum_sig_fail | Wrong checksum rejected |
| 17 | host_crash_during_deploy | Host crash, state consistent |
| 18 | power_loss_during_deploy | Power loss, state consistent |
| 19 | power_loss_after_activation | Power loss before commit → HEALTHY |
| 20 | repeated_boot_failure | Repeated failures → BOOT_LOOP_HALT |
| 21 | auto_rollback | Health fail → auto rollback |
| 22 | successful_retry | Fix issue, retry succeeds |
| 23 | idempotent_duplicate | Same deploy twice → same ID |
| 24 | network_flap | Network down→up, recovers |
| 25 | stale_journal | Stale journal entries handled |

## Result DB

SQLite at `/tmp/mavericks-lab-harness/results.sqlite`:

```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario TEXT NOT NULL,
    backend TEXT NOT NULL,
    result TEXT NOT NULL,         -- pass/fail/skip
    failure_reason TEXT,
    started_at TEXT,
    finished_at TEXT,
    duration_s REAL,
    evidence TEXT                 -- JSON: fixture_dir
);
```

## Running

```bash
# All scenarios on sim backend (primary)
python3 lab/harness/harness.py --backend sim --all

# Single scenario
python3 lab/harness/harness.py --backend sim --scenario 03_b_boots

# QEMU backend (real guest boot)
python3 lab/harness/harness.py --backend qemu --all

# List scenarios
python3 lab/harness/harness.py --list

# Harness tests
python3 lab/harness/tests/test_harness.py
```

## EFI Stub Investigation

The OVMF + EFI-stub boot path was investigated extensively:
- OVMF boots the kernel from ESP (EFI/BOOT/BOOTX64.EFI = patched vmlinuz)
- The kernel's EFI stub (7.2.6-zen) does NOT apply the setup-header
  cmdline (ext_cmd_line_ptr) in this QEMU/OVMF configuration — no serial
  output is produced
- Direct kernel boot (-kernel/-initrd/-append) works reliably and uses
  the same kernel + initramfs + cmdline
- The ESP/A/B/DATA structure is fully represented in the fixture layout
- Future work: investigate the EFI stub cmdline issue or use a bootloader
  that passes the cmdline

## Manual Boundary

- The harness does NOT modify any production bootloader
- The QEMU backend requires root for loop mount (DATA image access)
- The sim backend is fully rootless
- The MacBackend is a documented stub only
