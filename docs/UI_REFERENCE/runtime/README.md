# Runtime capture — real Mavericks guest

Evidence here was produced **inside a running OS X 10.9 guest**, not from the
offline installer artifacts. Screenshots are supplementary only; the record is
the machine-readable document in `raw/`.

## Guest under test

| Property | Value | How it was confirmed |
|---|---|---|
| Product | `Mac OS X` | `sw_vers` in the guest Terminal |
| Version | `10.9` | `sw_vers` |
| Build | `13A603` | `sw_vers` |
| Root volume | `/dev/disk1s2` (`hfs, local, journaled`) | `mount \| head -3` |
| Boot disk | `disk1`, 68.7 GB, GPT + EFI 209.7 MB | `diskutil list` |
| User session | `uid=501(builder) gid=20(staff)`, groups include `80(admin)` | `id` |
| Session daemons | WindowServer + Finder present | `ps -Ao comm \| grep -Ec "WindowServer\|Finder"` → `2` |

Host: Arch Linux, `qemu-system-x86_64` (TCG, `thread=multi`), OVMF + OpenCore.
`mavericks-hdd.raw` is the installed target; it boots to the desktop and
survives a reboot (login window → desktop → session restored).

## Capture 1 — standalone tool, first successful real-guest run

Commands (executed in the guest Terminal; the share is a FAT32 volume
hot-plugged over USB so no host writes happen while it is mounted):

```
sh /Volumes/NSINSPECT/tool.sh
```

which runs:

```
NSINSPECT_OUT=/tmp/poc.json ~/ns/nsinspect-tool
```

Result: `exit=0`, `/tmp/poc.json` written, 246 bytes.

Raw output: [`raw/standalone-tool-poc.json`](raw/standalone-tool-poc.json)

What it proves:

- The Mach-O produced by `tools/uiref/build-nsinspect.sh` from Linux **loads and
  runs** in the real Mavericks guest — deployment target `10.9.0`, arch `x86_64`.
- `pid` is a genuine guest process id.
- The document is written through `NSINSPECT_OUT`, i.e. the output-path
  contract is honoured.

What it does **not** prove: no windows were listed. A command-line process owns
no `NSApplication` and no Aqua session, so `aqua_session` is `false` and
`windows` is empty. Listing another application's windows requires the
`DYLD_INSERT_LIBRARIES` flavour — see the blocker below.

## Blocker — `nsinspect.dylib` (injected flavour) still fails to load

The injected dylib aborts with `SIGSEGV` **before its constructor runs** (the
first breadcrumb written by the constructor never appears, and the guest's
crash reporter shows a plain segmentation fault with no dyld diagnostic).
`raw/injection-attempts.md` records every attempt in order.

Identified cause: dyld initialises a `DYLD_INSERT_LIBRARIES` image before the
host process' own dependencies, and our image was linked with
`-nostdlib`, so there was nothing to bind its lazy symbols against. Adding real
`LC_LOAD_DYLIB` records for `/usr/lib/libSystem.B.dylib` and
`/usr/lib/libobjc.A.dylib` (carried by link-time stubs that are never shipped)
fixed the *executable* but not the early initialisation path of an inserted
image.

What is needed to close it, in order of expected effect:

1. An Apple SDK (or `libSystem`/`libobjc` import libraries) so the image links
   with genuine dependencies and eager binding, instead of stubs.
2. Failing that, load the inspector through a host that is not started with
   `DYLD_INSERT_LIBRARIES` — e.g. `AXUIElement` from a separate process, which
   needs no injection and returns the same window/control facts (roles,
   geometry, enabled state, titles) without any Objective-C runtime access.
3. Failing that, build the tool inside the guest once a compiler exists there.

None of these blocks the static work in `docs/UI_REFERENCE/data/`: that is
separate ground truth and must not be overwritten by runtime observations.

## Rules

- Runtime facts (`kind: runtime-observed`) and static NIB facts stay in
  separate files; link them, never merge.
- Unavailable fields are recorded as unavailable, never guessed.
- Failed attempts are kept, including their exact error text.