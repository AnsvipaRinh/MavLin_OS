"""Fixture builder for the mavericks-lab harness.

Creates the per-scenario fixture layout shared by all backends:

    fixture/
    ├── esp/                       # ESP (sim: dir; qemu: FAT32 image)
    │   └── EFI/BOOT/
    │       ├── BOOTX64.EFI        # kernel (qemu: patched vmlinuz)
    │       └── initramfs.img      # guest initramfs
    ├── data/                      # DATA dir (agent state)
    │   ├── fixture.env            # fixture params (network, agent, ...)
    │   ├── boot/{current,next}-boot.txt
    │   ├── state.json             # optional pre-populated agent state
    │   ├── journal.jsonl             # optional pre-populated journal
    │   ├── slots/A/...            # slot A image metadata
    │   ├── slots/B/...            # slot B image metadata
    │   └── deploy-inbox/          # images waiting to be deployed
    ├── rootfs-A/                  # slot A rootfs (9p share / sim dir)
    │   └── etc/mavericks/{slot-ok,systemd-ok,version.txt}
    ├── rootfs-B/                  # slot B rootfs
    └── serial.log                 # serial log (ground truth)

The QEMU backend additionally builds esp.img (FAT32) + OVMF vars and boots
it. The sim backend uses the same layout with directories only.
"""
import os
import shutil
import struct
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
AGENT_SRC = REPO / "lab/agent/mavericks-lab-agent"
GUEST_INIT_SRC = Path(__file__).resolve().parent / "guest_init.py"

# Kernel + initramfs sources (copied to builder-owned locations by the harness)
KERNEL_SRC = Path("/tmp/mavericks-lab-kernel/vmlinuz-linux-zen")
INITRD_SRC = Path("/tmp/mavericks-lab-kernel/initramfs-linux-zen.img")

STDLIB_EXCLUDE = {
    "site-packages", "__pycache__", "idlelib", "tkinter", "turtledemo",
    "ensurepip", "lib2to3", "test", "distutils", "pydoc_data", "__pypackages__",
}


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ensure_kernel_sources():
    """Copy kernel + initramfs to builder-owned locations (sudo)."""
    KERNEL_SRC.parent.mkdir(parents=True, exist_ok=True)
    if not KERNEL_SRC.exists():
        _run(["sudo", "cp", "/boot/vmlinuz-linux-zen", str(KERNEL_SRC)])
        _run(["sudo", "chown", "builder:builder", str(KERNEL_SRC)])
        _run(["sudo", "chmod", "664", str(KERNEL_SRC)])
    if not INITRD_SRC.exists():
        _run(["sudo", "cp", "/boot/initramfs-linux-zen.img", str(INITRD_SRC)])
        _run(["sudo", "chown", "builder:builder", str(INITRD_SRC)])
        _run(["sudo", "chmod", "664", str(INITRD_SRC)])


def patch_kernel_cmdline(kernel_path, cmdline):
    """Patch the bzImage/EFI-stub cmdline (console + initrd on ESP).

    The cmdline must live inside the setup sector (first setup_sects*512
    bytes) so it survives kernel decompression — the EFI stub reads it
    from ext_cmd_line_ptr in the setup header.
    """
    data = bytearray(Path(kernel_path).read_bytes())
    hdr = bytes(data).find(b"HdrS")
    if hdr < 0:
        raise RuntimeError("no HdrS magic in kernel")
    if data[hdr + 0x2F] and b"console=ttyS0" in bytes(data):
        return True
    setup_sects = data[0x1F1] or 4
    setup_end = setup_sects * 512
    cmd_bytes = cmdline.encode() + b"\0"
    # place at end of setup area, 16-byte aligned
    cmd_off = (setup_end - len(cmd_bytes)) & ~0xF
    if cmd_off < 0x400:
        raise RuntimeError("setup area too small for cmdline")
    data[cmd_off:cmd_off + len(cmd_bytes)] = cmd_bytes
    struct.pack_into("<I", data, hdr + 0x22, cmd_off)
    data[hdr + 0x2F] = len(cmd_bytes)
    Path(kernel_path).write_bytes(data)
    return True


def build_initramfs(dest):
    """Build the guest initramfs: python + stdlib + libffi + wrapper + init + agent."""
    dest = Path(dest)
    if dest.exists():
        dest.unlink()
    root = dest.parent / (dest.name + "-root")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    # python runtime + shared library deps for lib-dynload C extensions
    for src, dst in [
        ("/usr/bin/python3.14", "usr/bin/python3.14"),
        ("/usr/lib/libpython3.14.so.1.0", "usr/lib/libpython3.14.so.1.0"),
        ("/usr/lib/libc.so.6", "usr/lib/libc.so.6"),
        ("/usr/lib/libm.so.6", "usr/lib/libm.so.6"),
        ("/usr/lib/libffi.so.8", "usr/lib/libffi.so.8"),
        ("/usr/lib64/ld-linux-x86-64.so.2", "lib64/ld-linux-x86-64.so.2"),
        ("/usr/lib/libz.so.1", "usr/lib/libz.so.1"),
        ("/usr/lib/libcrypto.so.3", "usr/lib/libcrypto.so.3"),
        ("/usr/lib/libssl.so.3", "usr/lib/libssl.so.3"),
        ("/usr/lib/libbrotlienc.so.1", "usr/lib/libbrotlienc.so.1"),
        ("/usr/lib/libbrotlidec.so.1", "usr/lib/libbrotlidec.so.1"),
        ("/usr/lib/libbrotlicommon.so.1", "usr/lib/libbrotlicommon.so.1"),
        ("/usr/lib/libzstd.so.1", "usr/lib/libzstd.so.1"),
        ("/usr/lib/liblzma.so.5", "usr/lib/liblzma.so.5"),
        ("/usr/lib/libgcc_s.so.1", "usr/lib/libgcc_s.so.1"),
        ("/usr/lib/libkmod.so.2", "usr/lib/libkmod.so.2"),
        ("/usr/sbin/modprobe", "usr/sbin/modprobe"),
        ("/usr/sbin/insmod", "usr/sbin/insmod"),
    ]:
        s = Path(src)
        if not s.exists():
            continue
        d = root / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        d.chmod(0o755)

    # python3 symlink
    os.symlink("python3.14", root / "usr/bin/python3")

    # trimmed stdlib
    stdlib_src = Path("/usr/lib/python3.14")
    stdlib_dst = root / "usr/lib/python3.14"
    stdlib_dst.mkdir(parents=True, exist_ok=True)
    for item in stdlib_src.iterdir():
        if item.name in STDLIB_EXCLUDE:
            continue
        d = stdlib_dst / item.name
        if item.is_dir():
            shutil.copytree(item, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, d)

    # static wrapper as /init
    wrapper = root / "init.c"
    wrapper.write_text(
        '#include <unistd.h>\n#include <stdlib.h>\n'
        'int main(void){setenv("PYTHONHASHSEED","0",1);'
        'setenv("PYTHONHOME","/usr",1);'
        'char *a[]={"python3.14","/init.py",NULL};'
        'execv("/usr/bin/python3.14",a);return 127;}\n'
    )
    wrapper.chmod(0o644)
    _run(["gcc", "-static", "-o", str(root / "init"), str(wrapper)], check=True)
    wrapper.unlink()
    (root / "init").chmod(0o755)

    # guest init
    shutil.copy2(GUEST_INIT_SRC, root / "init.py")
    (root / "init.py").chmod(0o755)

    # agent
    agent_dst = root / "opt/mavericks-lab-agent"
    agent_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AGENT_SRC, agent_dst)
    agent_dst.chmod(0o755)

    # virtio core + virtio-net + net_failover modules (for QEMU network-up)
    virtio_dir = root / "lib/modules/7.2.6-zen2-1-zen/kernel/drivers/virtio"
    virtio_dir.mkdir(parents=True, exist_ok=True)
    net_dir = root / "lib/modules/7.2.6-zen2-1-zen/kernel/drivers/net"
    net_dir.mkdir(parents=True, exist_ok=True)
    for mod in ["virtio.ko.zst", "virtio_ring.ko.zst", "virtio_pci.ko.zst",
                "virtio_pci_modern_dev.ko.zst", "virtio_pci_legacy_dev.ko.zst"]:
        src = f"/usr/lib/modules/7.2.6-zen2-1-zen/kernel/drivers/virtio/{mod}"
        if Path(src).exists():
            _run(["sudo", "cp", src, str(virtio_dir)], check=True)
    for mod in ["virtio_net.ko.zst", "net_failover.ko.zst"]:
        _run(["sudo", "cp", f"/usr/lib/modules/7.2.6-zen2-1-zen/kernel/drivers/net/{mod}", str(net_dir)], check=True)
    _run(["sudo", "chown", "-R", "builder:builder", str(root / "lib/modules")], check=False)

    # build cpio
    subprocess.run(
        f"cd {root} && find . -print0 | cpio --null -o -H newc | gzip -9 > {dest}",
        shell=True, check=True,
    )
    shutil.rmtree(root)
    return dest


def build_esp_image(esp_img, kernel, initramfs):
    """Build a FAT32 ESP image with EFI/BOOT/{BOOTX64.EFI,initramfs.img}."""
    esp_img = Path(esp_img)
    if esp_img.exists():
        esp_img.unlink()
    _run(["dd", "if=/dev/zero", f"of={esp_img}", "bs=1M", "count=64"], check=True)
    _run(["mkfs.vfat", "-F", "32", "-n", "ESP", str(esp_img)], check=True)
    stage = esp_img.parent / "esp-stage"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "EFI/BOOT").mkdir(parents=True)
    shutil.copy2(kernel, stage / "EFI/BOOT/BOOTX64.EFI")
    shutil.copy2(initramfs, stage / "EFI/BOOT/initramfs.img")
    _run(["mmd", "-i", str(esp_img), "::EFI"], check=True)
    _run(["mmd", "-i", str(esp_img), "::EFI/BOOT"], check=True)
    _run(["mcopy", "-o", "-i", str(esp_img), str(stage / "EFI/BOOT/BOOTX64.EFI"), "::EFI/BOOT/"], check=True)
    _run(["mcopy", "-o", "-i", str(esp_img), str(stage / "EFI/BOOT/initramfs.img"), "::EFI/BOOT/"], check=True)
    shutil.rmtree(stage)
    return esp_img


def corrupt_esp_file(esp_img, member, size=4096):
    """Overwrite an ESP member with garbage (kernel/initramfs failure injection)."""
    _run(["mcopy", "-o", "-i", str(esp_img), "/dev/null", f"::{member}"], check=False)
    # mcopy from /dev/null won't corrupt; write garbage via a temp file
    tmp = esp_img.parent / "corrupt.tmp"
    tmp.write_bytes(b"\xde\xad\xbe\xef" * (size // 4))
    _run(["mcopy", "-o", "-i", str(esp_img), str(tmp), f"::{member}"], check=True)
    tmp.unlink()


def build_data_image(data_dir, data_img, size_mb=128):
    """Build an ext4 DATA image from the data/ directory (for virtio-blk).

    Uses loop mount (root) to populate the image. The QEMU guest mounts it
    as /dev/vda (virtio-blk, ext4 built-in).
    """
    data_img = Path(data_img)
    if data_img.exists():
        data_img.unlink()
    _run(["dd", "if=/dev/zero", f"of={data_img}", "bs=1M", f"count={size_mb}"], check=True)
    _run(["mkfs.ext4", "-q", "-F", "-L", "DATA", str(data_img)], check=True)
    mnt = data_img.parent / "data-mnt"
    if mnt.exists():
        _run(["sudo", "umount", str(mnt)], check=False)
        shutil.rmtree(mnt, ignore_errors=True)
    mnt.mkdir(parents=True, exist_ok=True)
    _run(["sudo", "mount", "-o", "loop", str(data_img), str(mnt)], check=True)
    try:
        # copy the data/ tree into the image
        for item in Path(data_dir).iterdir():
            _run(["sudo", "cp", "-a", str(item), str(mnt)], check=True)
    finally:
        _run(["sudo", "umount", str(mnt)], check=True)
        shutil.rmtree(mnt, ignore_errors=True)
    return data_img


def create_fixture(fixture_dir, params):
    """Create the fixture layout from params.

    Creates:
      data/           — DATA directory (sim backend + staging for image)
      data.img        — FAT32 DATA image (QEMU backend, virtio-scsi)
      esp/EFI/BOOT/   — kernel + initramfs (EFI stub / documentation)

    params keys:
      slot_a_image, slot_b_image: version strings or None
      network: up|down
      agent: on|off
      pre_state: dict to seed state.json
      pre_journal: list of entries to seed journal.jsonl
      rootfs_a_ok, rootfs_b_ok: bool (slot-ok marker)
      systemd_a_ok, systemd_b_ok: bool (systemd-ok marker)
      max_attempts: int
    """
    fixture_dir = Path(fixture_dir)
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    data = fixture_dir / "data"
    (data / "boot").mkdir(parents=True)
    (data / "slots/A").mkdir(parents=True)
    (data / "slots/B").mkdir(parents=True)
    (data / "deploy-inbox").mkdir(parents=True)
    (data / "rootfs-A/etc/mavericks").mkdir(parents=True)
    (data / "rootfs-B/etc/mavericks").mkdir(parents=True)
    (fixture_dir / "esp/EFI/BOOT").mkdir(parents=True)

    # boot selection
    (data / "boot/current-boot.txt").write_text("A\n")
    (data / "boot/next-boot.txt").write_text("A\n")

    # fixture.env
    env_lines = [
        f"network={params.get('network', 'up')}",
        f"agent={params.get('agent', 'on')}",
        f"max_boots={params.get('max_boots', '10')}",
    ]
    (data / "fixture.env").write_text("\n".join(env_lines) + "\n")

    # slot rootfs markers
    for slot in ("A", "B"):
        rdir = data / f"rootfs-{slot}" / "etc/mavericks"
        if params.get(f"rootfs_{slot.lower()}_ok", True):
            (rdir / "slot-ok").write_text("ok\n")
        if params.get(f"systemd_{slot.lower()}_ok", True):
            (rdir / "systemd-ok").write_text("ok\n")
        ver = params.get(f"slot_{slot.lower()}_image")
        if ver:
            (rdir / "version.txt").write_text(ver + "\n")

    # slot image metadata (image.json) — represents a deployed image
    for slot in ("A", "B"):
        ver = params.get(f"slot_{slot.lower()}_image")
        if ver:
            import hashlib, json
            content = f"fixture-image-{ver}".encode()
            sha = hashlib.sha256(content).hexdigest()
            meta = {
                "deployment_id": f"img-{sha[:16]}",
                "version": ver,
                "slot": slot,
                "sha256": sha,
                "size": len(content),
                "verified": True,
            }
            (data / f"slots/{slot}/image.json").write_text(
                json.dumps(meta, indent=2) + "\n"
            )

    # pre-populated agent state
    if params.get("pre_state"):
        import json
        (data / "state.json").write_text(
            json.dumps(params["pre_state"], indent=2) + "\n"
        )

    # pre-populated journal
    if params.get("pre_journal"):
        import json
        lines = [json.dumps(e) for e in params["pre_journal"]]
        (data / "journal.jsonl").write_text("\n".join(lines) + "\n")

    # ESP contents (sim uses these as files; qemu copies to image)
    ensure_kernel_sources()
    initrd = fixture_dir / "esp/EFI/BOOT/initramfs.img"
    cached = Path("/tmp/mavericks-lab-initramfs-cache.img")
    if cached.exists() and cached.stat().st_mtime > (AGENT_SRC.stat().st_mtime if AGENT_SRC.exists() else 0):
        shutil.copy2(cached, initrd)
    else:
        build_initramfs(initrd)
        shutil.copy2(initrd, cached)
    shutil.copy2(KERNEL_SRC, fixture_dir / "esp/EFI/BOOT/BOOTX64.EFI")

    # build the FAT32 DATA image for the QEMU backend
    build_data_image(data, fixture_dir / "data.img")

    return fixture_dir
