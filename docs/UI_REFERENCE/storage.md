# MavlinOS storage awareness (Arch Linux under WSL2)

## Why this exists

MavlinOS is developed inside Arch Linux running under Windows 10 through WSL.
That makes two numbers that look alike mean completely different things:

| Number | Where it comes from | What it means |
|---|---|---|
| free space inside the WSL virtual disk | `df /` (`/dev/sde`, ext4, 1 TiB max) | room for data *inside* Linux |
| free space on the Windows volume | `df /mnt/c` (9p mount) | room left on the host disk that stores the virtual disk |

The virtual disk is a file on the Windows volume. Writing inside WSL grows that
file. So the Windows figure is the hard ceiling even when Linux reports hundreds
of gigabytes free.

### The 8.5 GB versus 561 GB discrepancy

Both numbers were correct; they described different filesystems.

* An earlier audit ran `df -h /` and reported **561 GB free**. That is the ext4
  virtual disk, which is configured with a 1 TiB maximum and was only 42%
  full.
* The owner's ~8.5 GB is the **Windows `C:` volume**, mounted into WSL as `9p` at
  `/mnt/c` and at `/usr/lib/wsl/drivers`. It was 468 GB used of 476 GB, i.e.
  **99% full**.

The virtual disk had grown to roughly 393 GB of allocated data inside it, which
is what consumed the Windows volume. Quoting only the Linux figure would have
made a machine that cannot accept another gigabyte look idle.

The current inventory reports both, and marks the Windows volume as the binding
constraint.

## Usage

```sh
python3 scripts/storage-audit.py inventory --save     # full report, refresh baseline
python3 scripts/storage-audit.py diff                 # growth since the baseline
python3 scripts/storage-audit.py preflight --need 20  # gate an operation
```

`preflight` exits `0` NORMAL, `1` WARNING, `2` CRITICAL, `3` EMERGENCY, `4` on a
measurement error. It targets the Windows volume when one is mounted, because
that is where growth is charged.

Baseline: `docs/UI_REFERENCE/storage-baseline.json`.
Policy and thresholds: `config/storage-policy.json`.
Tests: `tests/storage/test_storage_audit.py`.

## Accounting rules

* Sizes are reported as both **apparent** (`st_size`) and **allocated**
  (`st_blocks * 512`). The macOS disk images are sparse, so the two differ by
  more than 240 GiB across the tree; quoting apparent size would badly overstate
  real consumption.
* Hard links and repeated inodes are counted once.
* Nested roots collapse to the outermost path and the skipped paths are listed,
  so a subsystem is never counted twice.
* Symlinks are not followed and paths never cross into another filesystem.
* Unreadable directories are recorded as errors rather than aborting the scan.

## Retention rules

Categories are assigned in `config/storage-policy.json` and printed per
subsystem. In short:

* active research inputs and outputs stay local;
* verified completed research is committed to the private repository
  `AnsvipaRinh/MavlinOS` before any local removal;
* reproducible intermediates may go once inputs, scripts and the reproduction
  command are preserved;
* QEMU disks, VM backups, installation media, saved states and irreplaceable raw
  evidence are never removed automatically — `cleanup_guard` refuses them.

When reporting where something is kept, name the state exactly: committed to
Git, in Git LFS, in another verified archive, or **local only**. A hash or a
summary in GitHub is not the artifact.
