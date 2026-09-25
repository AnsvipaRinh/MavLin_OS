# RESEARCH: Time Machine backend (P2, pre-hardware, 2026-09-25)

Goal (future): Time Machine-like UI — timeline, hourly/daily ounshots,
browse-and-restore single files, off-device target (USB-C disk; cloud optional).
UI after P1. This note picks the backend only. No code, no new deps yet.

## Verified facts (no guessing)

| Fact | Borg | Restic | btrfs snapshots |
|---|---|---|---|
| In Arch repos | extra, borg 1.4.5 | extra, restic 0.19.1 | core, btrfs-progs 7.1 |
| Upstream alive | pushed 2026-09-25 | pushed 2026-09-25 | kernel-tracked |
| License | BSD-3-Clause (upstream; re-verify SPDX in Arch PKGBUILD at packaging time) | BSD-2-Clause | GPL-2.0 (kernel) |
| Dedup | yes (chunker) | yes (CDC) | CoW (not dedup) |
| Compression | zstd (matches system: btrfs zstd + zram zstd) | zstd supported (newer) | zstd native |
| Encryption | yes (repokey) | yes (always-on) | no (dm-crypt layer separate) |
| Browse/restore UX | `borg mount` (FUSE) — browse any snapshot as files | `restic mount` (FUSE, fuse3 in extra) | subvolume mount / `btrfs send` |
| Backends | local disk, SSH, some cloud via rclone-ish | local, SFTP, S3, B2, Azure, rclone (rclone 1.75.1 in extra) | local + send/receive stream |
| Daemon needed | no (oneshot via systemd timer) | no (oneshot via systemd timer) | no (oneshot) |
| Memory on weak HW | low (documented ~GB-scale repos fine on 8GB) | higher on very large repos (index in RAM) | negligible |

## Recommendation (recorded, not yet implemented)

1. **Primary: Borg** — dedup + zstd + encrypted USB-C target + FUSE browse =
   closest to Time Machine semantics; fits fanless/SSD constraints
   (small backup writes, timer-oneshot, no daemon).
2. **Local instant layer: btrfs snapshots** — system already on btrfs
   (@, @home, @snapshots exist); zero new deps; `btrfs send/receive` gives
   off-device copy to the same USB disk. Complements Borg, not replaces it.
3. **Restic: deferred** — revisit only if cloud backends (S3/B2) become a
   requirement; otherwise redundant with Borg.

## UI sketch (for later, not now)

Mavericks-like timeline window over `borg list`/`borg mount`: snapshot list,
enter/exit animation cheap, file browse via mounted archive in Thunar,
restore = copy-out (no in-place overwrite without confirm). Space/Quick Look
reuse for preview-before-restore. Energy: timer daily + on-unplug inhibit,
never while on battery < 20% (UPower check in wrapper).

## HW-validation items (later)

- USB-C disk throughput on Apple S3X NVMe host (backup window size).
- Idle cost of daily timer wakeup (measure, expect ~zero when idle).
- `borg mount` FUSE responsiveness on Core M with large archive.

## Decision status

RESEARCH REQUIRED → done (this file). Next: EXISTING SOLUTION FOUND (Borg),
then P1-gated UI implementation. Do NOT add borg/restic to ISO yet.
