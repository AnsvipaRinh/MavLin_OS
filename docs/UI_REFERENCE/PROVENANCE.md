# PROVENANCE — Mavericks reference guest

## Image
- Item: `https://archive.org/details/OSXMavericksInstallDVD`
- File: `OS X Mavericks Install DVD.dmg` (5 649 418 164 bytes)
- SHA-256: ____ (recorded after local verification)
- Harvested via parallel HTTP ranged GET (12 connections), no third-party mirror.

## Offline route (preferred: no VM, no GUI, reproducible)
The visible installer volume is only a stub (1185 files). The real 10.9 system lives inside
`InstallESD.dmg` as the flat package `Essentials.pkg` (Payload = bzip2 cpio):

```
dmg2img -i "OS X Mavericks Install DVD.dmg" -o installer.raw          # 18.7 GB raw
7z e installer.raw -o stub "*/SharedSupport/InstallESD.dmg" -y        # 5.29 GB ESD
7z x InstallESD.dmg -o esd -y                                         # -> "OS X Install ESD/" (HFSX tree)
bsdtar -xf "OS X Install ESD/Packages/Essentials.pkg" -C esdpkg       # flat xar
bsdtar -xf esdpkg/Payload -C sys                                      # -> real /System tree (~9 GB)
```
`tools/uiref/extract-osx109.sh` automates exactly this. The kernel here has no `hfsplus`
module (WSL2), hence the user-space HFS reading (7-Zip `Dmg`+`Hfs` handlers) instead of
loop mounts; `hfsprogs` (AUR) is still required only for *writing* a disk image.

This route is used for static ground truth (nibs, Assets.car, dictionaries, frameworks,
Mach-O metadata). The QEMU guest remains the route for runtime behaviour (real windows,
animation, focus) that no offline artifact can provide.

## Host
- Arch Linux, x86_64, WSL2, qemu-system-x86_64 11.1.1, no `/dev/kvm` (TCG software emulation, `thread=multi`).
- Consequence: guest runs well below real-time. Pixel/color/geometry facts are unaffected; **animation timings are not frame-derived** (rule C2).

## Boot chain
1. `qemu-img convert -f dmg -O raw "OS X Mavericks Install DVD.dmg" mavericks-dvd.raw` (QEMU native DMG reader).
2. Clover r5175 `Clover-5175-X64.iso` copied to a 512 MB FAT ESP (`clover-esp.img`), `config.plist` patched:
   `SMBIOS ProductName=iMac13,2`, `CPU.QEMU=true`, `KernelAndKextPatches.KernelPm=true`, `Graphics.ScreenResolution=1600x900` (must equal the OVMF preferred resolution).
3. QEMU (key arguments):
   ```
   -machine pc-q35-6.1,vmport=off -accel tcg,thread=multi
   -cpu Penryn,vendor=GenuineIntel,+sse4.1,+sse4.2,+ssse3
   -bios /usr/share/edk2-ovmf/x64/OVMF_CODE.4m.fd  (+ pflash unit0/unit1 vars)
   -m 4G -smp 2
   -device isa-applesmc,osk=<Apple OSK from Clover default>
   -device vmware-svga -device e1000 ...   # no audio device at all: no host mic/speaker access
   -usb-ehci + usb-kbd/usb-mouse/usb-tablet
   -monitor unix:mon.sock -qmp unix:qmp.sock -serial file:serial.log
   disks: ESP (bootindex 0), Install DVD raw (1), target HDD raw (2)
   ```
4. Input automation: QMP `input-send-event` (absolute pointer), HMP `sendkey` (keyboard), HMP `screendump` (PPM->PNG via Pillow). Driver: local `mvvm.py` (not in repo; recipe above is complete).

## Capture settings
- Resolution 1600x900 @1x, 32 bpp, no scaling, no cursor-drawing tricks beyond the guest's own.
- Guest clock set to a fixed date for reproducibility of time-dependent chrome (clock, calendar).

## Hashes of committed facts
`captures/index.json` stores md5 per capture; `tests/uiref/test_catalog.py` fails when a referenced capture is missing or altered.
