# Reference guest tooling (macOS 10.9 under QEMU)

Everything needed to rebuild the Mavericks reference guest that produces the
runtime half of `docs/UI_REFERENCE/` (probe output, component states,
animations). Nothing here is part of the desktop product; it is extraction
infrastructure and it is kept in the repo so the procedure is reproducible
instead of tribal knowledge.

Host assumptions: Arch Linux on WSL2 (2 vCPU, no `/dev/kvm`, TCG only),
`qemu-system-x86_64`, `p7zip`, `aria2`, `mtools`, `dmg2img`, `clang`, `zstd`.

## 1. Source image

```
aria2c -x12 -s12 -O MavericksDVD.dmg \
  "https://archive.org/download/OSXMavericksInstallDVD/OS%20X%20Mavericks%20Install%20DVD.dmg"
md5sum MavericksDVD.dmg      # ff49a78b86dfc0930baded7357889797
dmg2img -i MavericksDVD.dmg -o installer.raw     # 17.4 GB GPT + HFSX installer volume
```

`installer.raw` is the bootable installer DVD (partition 1: EFI, partition 2:
HFSX with `SharedSupport/InstallESD.dmg`). The system payload is obtained with
`tools/uiref/extract-osx109.sh`, which unpacks `InstallESD.dmg` →
`Packages/Essentials.pkg` → `Payload` (bzip2 cpio) into the real `/System` tree.

## 2. Why the install is done off-line, and how

A GUI install of 10.9 under TCG needs pointer and keyboard automation against a
framebuffer, which is slow and unverifiable. Two off-line routes were built:

* `rescue-init.c` — a static Linux `init` (PID 1) for an initramfs that mounts a
  **squashfs** payload and an **HFS+** volume and copies the tree with
  `cp`-like semantics (modes, owners, symlinks, mtimes). It loads the modules it
  needs (`squashfs`, `hfsplus`, `nls_utf8`, `cdrom`, `ata_piix`) with
  `finit_module` and prints `MVSTEP …` lines plus a final `MV_INSTALL_DONE`
  marker on the serial console. Built with `clang -static`.
  Blocker found on the way: the kernel refuses a **newly formatted, empty**
  HFS+ volume (`EINVAL`), and this WSL kernel has no `hfsplus` at all, so the
  guest could not format it either.
* `mvinstall.sh` — the same idea as a shell script, kept for reference.

Host-side helpers that are needed to create the volume at all:

* `newfs_hfs` (Apple's own tool) built from the Fedora/Arch `hfsprogs`
  (diskdev_cmds 540.1.linux3) — `newfs_hfs -v "Macintosh HD" target.hfs`.
* `hfsutils` (Robert Leslie's suite) — `hmount`, `hcopy`, `hformat` — useful for
  classic HFS volumes; note that this implementation does **not** write HFS+.

## 3. Driving macOS itself

Once the target volume exists, the payload is installed with Apple's own tools
from inside the installer environment, without a GUI:

* `drive_guest.py` boots the guest and types into it blindly: Darwin has no
  serial console, so commands are injected as keystrokes over QMP
  (`send-key`, qcode objects, modifiers as separate simultaneous keys) and
  results come back as files on a small FAT disk labelled **MAVLOG**, which the
  host reads with `mtools` while the guest runs. Every step is therefore
  verifiable without reading the framebuffer.
* The OpenCore bootloader lives on a FAT ESP image built with `mtools`
  (`mformat` + `mcopy`) and patched with `boot-args … init=/bin/sh`, so the
  installer environment comes up as a root shell instead of the GUI installer.
* `serial_drive.py` / `vm_ser.py` drive the *Linux* rescue guest over a serial
  unix socket (`-serial unix:…,server=on`), which is where all of its output
  is text.

QEMU line that boots the reference guest (TCG, headless):

```
qemu-system-x86_64 -machine pc-q35-6.1,vmport=off -accel tcg,thread=multi \
  -cpu Penryn,vendor=GenuineIntel,+sse4.1,+sse4.2,+ssse3 -smp 2,cores=2 -m 4G \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2-ovmf/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=OVMF_VARS.fd \
  -device "isa-applesmc,osk=ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc" \
  -vga none -device vmware-svga -device e1000,netdev=net0 \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -usb -device usb-kbd,bus=usb-bus.0 -device usb-tablet,bus=usb-bus.0 \
  -device ide-hd,bus=ide.0,drive=ESP,bootindex=0   -drive if=none,id=ESP,file=esp.img,format=raw \
  -device ide-hd,bus=ide.1,drive=TGT,bootindex=1   -drive if=none,id=TGT,file=mavericks-hdd.raw,format=raw \
  -device ide-cd,bus=ide.2,drive=DVD,bootindex=2   -drive if=none,id=DVD,file=installer.raw,format=raw,readonly=on,media=cdrom \
  -device ide-hd,bus=ide.3,drive=LOG,bootindex=3   -drive if=none,id=LOG,file=logdisk.img,format=raw \
  -display none -qmp unix:/tmp/opencode/qmp.sock,server=on,wait=off
```

Notes learned the hard way:

* split pflash is required (`OVMF_CODE.4m.fd` + a writable copy of
  `OVMF_VARS.4m.fd`); `-bios OVMF_CODE.fd` does not exist on this host;
* the read-only installer DVD must be an `ide-cd` device, otherwise QEMU
  refuses the read-only block node;
* QEMU 11 rejects `send-key` strings: keys are objects
  `{"type":"qcode","data":"a"}` and `shift-x` must be split into two entries;
* run long-lived QEMU with `setsid --fork`/`start_new_session=True`, otherwise
  a tool timeout takes the guest down with the shell.

## 4. Current state

* `phase1.txt` is the first typing script (prove the shell, list `/Volumes`,
  enumerate `/dev/disk*`, look for a mounted `InstallESD`).
* Open still running: the guest boots but the screen stays blank with the
  patched config, so OpenCore is not yet handing over to the installer kernel.
  Diagnostics to resume with: keep `ShowPicker=True` + `Debug.Target=67` and
  take a QMP `screendump` a few seconds into the boot to see which stage the
  firmware reaches.
* Everything here is only about *producing* runtime evidence; the evidence
  itself is written to `docs/UI_REFERENCE/data/` by the tools in
  `tools/uiref/`.
