# mavericks-lab — Remote Lab Control Plane

Lightweight A/B deployment and test orchestration for MacBook10,1 bring-up.
Zero idle overhead, SSH forced-command activatable, NOT a resident daemon.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  HOST (build controller)                            │
│  mavericks-lab CLI                                  │
│    ├── client.py    (SSH / Local transport)         │
│    ├── controller.py (deploy + test orchestration)  │
│    ├── store.py     (SQLite result store)           │
│    └── scenarios.py (scenario registry)             │
└──────────────────────┬──────────────────────────────┘
                       │ SSH forced-command (NDJSON)
                       │ or local pipe (testing)
┌──────────────────────▼──────────────────────────────┐
│  TARGET (lab machine / QEMU guest)                  │
│  mavericks-lab-agent                                │
│    ├── protocol.py   (NDJSON framing + dispatch)    │
│    ├── state.py      (A/B state machine)            │
│    ├── deploy.py     (image deploy + verify)        │
│    ├── boot.py       (boot selection abstraction)   │
│    ├── identity.py   (ed25519 machine identity)     │
│    └── health.py     (health checks)                │
│                                                     │
│  systemd oneshot: mavericks-lab-agent boot          │
│  (advances state machine at boot, then exits)       │
└─────────────────────────────────────────────────────┘
```

## A/B State Machine

```
UNKNOWN → BOOTING → NETWORK_READY → AGENT_READY → HEALTH_CHECK → HEALTHY → COMMITTED
                                                                        ↓
FAIL ←──────────────────────────────────────────────────────────────────┘
  ↓
ROLLBACK → BOOTING (reboot into previous slot)
```

- **Attempt counter**: incremented on each FAIL, reset on HEALTHY
- **Max attempts** (default 3): if reached, halt auto-rollback and wait for host
- **Boot-loop protection**: prevents infinite rollback loops
- **Persistent state**: atomic file writes (temp + rename) on DATA partition
- **Event journal**: append-only JSONL, survives crashes and power loss

## Protocol

NDJSON over stdin/stdout of SSH forced command.

**Request:**
```json
{"id": "<uuid>", "cmd": "deploy", "args": {"version": "v1", "slot": "B", "sha256": "...", "image_b64": "..."}}
```

**Response:**
```json
{"id": "<uuid>", "ok": true, "result": {"deployment_id": "img-abc123", "slot": "B", "verified": true}}
```

**Idempotent replay:** if `id` matches a completed job in the journal, the cached
response is returned without re-executing the command.

### Commands

| Command | Args | Description |
|---------|------|-------------|
| `status` | — | Machine status (state, slot, deployment, health) |
| `inventory` | — | Hardware/software inventory |
| `collect` | `lines` | Collect dmesg, journal, agent logs |
| `run-test` | `name`, `args` | Run built-in test on target |
| `benchmark` | `name`, `args` | Run benchmark on target |
| `deploy` | `version`, `slot`, `sha256`, `image_b64`, `signature_b64` | Deploy image to slot |
| `verify` | `slot` | Verify slot image (sha256 + signature) |
| `reboot` | — | Reboot target |
| `shutdown` | — | Shutdown target |
| `select-boot` | `slot` | Select A/B boot slot |
| `commit` | — | Commit current deployment |
| `rollback` | — | Rollback to previous slot |
| `snapshot` | `name` | Create state snapshot |
| `restore` | `name` | Restore state snapshot |
| `logs` | `lines` | Show agent journal |
| `trace` | `lines` | Show event trace |
| `ping` | — | Connectivity check |

## Deployment Format

Images are deployed to the **inactive slot only**. The active slot is never
modified during deployment.

```
slots/
├── A/
│   ├── image.tar         — deployed image
│   ├── image.sig         — ed25519 signature (optional)
│   └── image.json        — metadata (deployment_id, version, sha256, size)
└── B/
    └── ...
```

**Deployment ID:** `img-<sha256[:16]>` — deterministic, content-based.

**Verification:** SHA-256 checksum + ed25519 signature (if host key installed).

**Activation:** `select-boot <slot>` + `reboot()`. The boot oneshot advances
the state machine and runs health checks. Only after HEALTHY does the host
issue `commit`.

## Boot Selection

### QEMU Backend (Phase 1)

File-based simulation of systemd-boot A/B slot selection:

```
boot/
├── current-boot.txt  — slot currently booted
├── next-boot.txt     — slot selected for next boot
└── entries/
    ├── A.conf        — systemd-boot entry for slot A
    └── B.conf        — systemd-boot entry for slot B
```

`reboot()` updates `current-boot.txt` from `next-boot.txt`. In Phase 2, this
will trigger an actual QEMU reboot.

### Mac Backend (documented, Phase 2)

```python
class MacBootBackend(BootBackend):
    def select_boot(self, slot):
        # Map slot → boot number (from efibootmgr -v)
        bootnum = self._slot_to_bootnum(slot)
        # Try BootNext first
        subprocess.run(["sudo", "efibootmgr", "-n", bootnum])
        # Fallback: rewrite loader.conf default entry
        # (some firmware ignores BootNext)
        self._rewrite_default_entry(slot)

    def reboot(self):
        subprocess.run(["systemctl", "reboot"])
```

**Narrow sudoers** (installed by `install.sh`):
```
mavericks-lab ALL=(root) NOPASSWD: /usr/sbin/efibootmgr -n *
mavericks-lab ALL=(root) NOPASSWD: /usr/sbin/efibootmgr -o *
```

## Security

- **Machine identity**: ed25519 keypair generated at install, stored on DATA
- **Host auth**: SSH key auth + forced-command restriction (no shell)
- **Image signing**: ed25519 signature verification (openssl)
- **Idempotency**: job IDs prevent replay attacks
- **No root shell**: forced-command + narrow sudoers only
- **Atomic state**: temp + rename for all persistent state

## Installation

### On target (lab machine / QEMU guest):

```bash
sudo ./lab/agent/install.sh --data-dir /mnt/data --user mavericks-lab
```

This installs:
1. Agent binary at `/usr/local/bin/mavericks-lab-agent`
2. ed25519 machine identity key
3. SSH forced-command in `authorized_keys`
4. systemd oneshot unit for boot-time state machine
5. Narrow sudoers for efibootmgr (Mac backend)

### On host (build controller):

```bash
# Generate host signing keypair
mavericks-lab init-host

# Copy host public key to target
scp ~/.mavericks-lab/host.pub.pem target:/home/mavericks-lab/.ssh/host.pub.pem

# Verify connectivity
mavericks-lab status
```

## Usage

### Local mode (testing):

```bash
export MAVERICKS_LAB_AGENT=./lab/agent/mavericks-lab-agent
export MAVERICKS_LAB_DATA=/tmp/lab-data
export MAVERICKS_LAB_STORE=/tmp/lab-store.sqlite

mavericks-lab status
mavericks-lab deploy ./image.tar
mavericks-lab test echo
mavericks-lab results
```

### SSH mode (real hardware):

```bash
export MAVERICKS_LAB_SSH_HOST=192.168.1.100
export MAVERICKS_LAB_SSH_USER=mavericks-lab
export MAVERICKS_LAB_SSH_KEY=~/.ssh/id_ed25519

mavericks-lab status
mavericks-lab test echo ./image.tar
```

### Full A/B test scenario:

```bash
# Deploy image, boot into it, run test, commit
mavericks-lab test disk-write ./image.tar

# Results
mavericks-lab results --scenario disk-write --result pass
```

## SQLite Schema

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    boot_id TEXT,
    image_version TEXT,
    slot TEXT,
    deployment_id TEXT,
    job_id TEXT,
    scenario TEXT,
    start_ts TEXT,
    end_ts TEXT,
    result TEXT,
    failure_reason TEXT,
    log_paths TEXT
);

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    machine_id TEXT,
    event_type TEXT,
    data TEXT
);
```

## Testing

```bash
python3 lab/tests/test_agent_protocol.py   # NDJSON protocol + idempotency
python3 lab/tests/test_agent_state.py      # A/B state machine
python3 lab/tests/test_agent_deploy.py     # Deploy + verify + commit/rollback
python3 lab/tests/test_agent_boot.py       # Boot backend + A/B lifecycle
python3 lab/tests/test_agent_identity.py   # ed25519 identity
python3 lab/tests/test_host_store.py       # SQLite store
python3 lab/tests/test_e2e.py              # Full lifecycle end-to-end
```

## Phase 2 — QEMU/OVMF Test Harness

Phase 2 implements a deterministic A/B test harness with 25 failure-injection
scenarios. See `docs/LAB_HARNESS.md` for full documentation.

### Layout

```
lab/harness/
├── harness.py              # driver: scenario loader, step interpreter, assertions
├── backends/
│   ├── base.py             # TargetBackend ABC (narrow API)
│   ├── sim_backend.py      # virtual-target simulation (rootless, always works)
│   ├── qemu_backend.py     # real QEMU guest boot (virtio-blk + ext4)
│   └── mac_backend.py      # documented stub for MacBook10,1
├── fixtures/
│   ├── builder.py          # builds ESP/DATA/rootfs + initramfs
│   └── guest_init.py       # guest init (python, PID 1)
├── scenarios/*.yaml        # 25 declarative scenarios
├── tests/test_harness.py   # harness tests (110 checks)
└── run via: python3 lab/harness/harness.py --backend sim --all
```

### Results

- **Sim backend**: 25/25 scenarios pass (rootless, deterministic)
- **QEMU backend**: real guest boot works; network-up is a known limitation
  (virtio-net module fails — virtio_ring not exported in this kernel)
- **Existing tests**: 158/158 pass (lab/tests/)

### Key Design Decisions

- **Direct kernel boot** for QEMU (EFI stub cmdline patching doesn't produce
  serial output for kernel 7.2.6-zen in this QEMU/OVMF config — documented)
- **virtio-blk + ext4** for DATA disk (both built-in; vfat is a module)
- **Loopback ioctl** for network (no route created — network-up limitation)
- **Declarative YAML** scenarios separate SCENARIO from TARGET BACKEND
- **Narrow boot API**: get_boot_state / select_boot / reboot / shutdown

## Phase 2 Seam (remaining)

The following are intentionally deferred:

- **Chunked deploy**: for large images (currently base64 in single NDJSON message)
- **Raw stream deploy**: separate SCP channel for image transfer
- **QEMU network-up**: requires working route creation (virtio-net module issue)
- **Mac backend**: documented stub, not wired to production bootloader
