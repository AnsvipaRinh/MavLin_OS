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
import glob
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
AGENT_SRC = REPO / "lab/agent/mavericks-lab-agent"
GUEST_INIT_SRC = Path(__file__).resolve().parent / "guest_init.py"

# Kernel + initramfs sources (copied to builder-owned locations by the harness)
KERNEL_SRC = Path("/tmp/mavericks-lab-kernel/vmlinuz-linux-zen")
INITRD_SRC = Path("/tmp/mavericks-lab-kernel/initramfs-linux-zen.img")


def _host_python_binary():
    """Absolute path of the running interpreter's real python binary."""
    exe = Path(sys.executable).resolve()
    if exe.name.startswith("python"):
        return exe
    # sys.executable may be a venv wrapper; fall back to versioned name.
    cand = exe.parent / f"python{sys.version_info.major}.{sys.version_info.minor}"
    return cand if cand.exists() else exe


def _host_python_stdlib_dir():
    """Path of the host stdlib dir matching _host_python_binary()."""
    home = getattr(sys, "base_prefix", sys.prefix)
    ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for cand in (Path(home) / "lib" / ver, Path("/usr/lib") / ver):
        if cand.is_dir():
            return cand
    raise FileNotFoundError(f"no stdlib dir found for {ver}")


def _find_runtime_lib(patterns):
    """Locate a shared library on the host across common lib dirs."""
    for pat in patterns:
        hits = sorted(
            glob.glob(f"/usr/lib64/{pat}")
            + glob.glob(f"/usr/lib/{pat}")
            + glob.glob(f"/usr/lib/x86_64-linux-gnu/{pat}")
            + glob.glob(f"/lib/x86_64-linux-gnu/{pat}")
            + glob.glob(f"/lib64/{pat}")
        )
        if hits:
            return Path(hits[0])
    return None

STDLIB_EXCLUDE = {
    "site-packages", "__pycache__", "idlelib", "tkinter", "turtledemo",
    "ensurepip", "lib2to3", "test", "distutils", "pydoc_data", "__pypackages__",
}


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ensure_kernel_sources():
    """Copy kernel + initramfs to builder-owned locations (sudo)."""
    if os.environ.get("MAVLINOS_LAB_SKIP_FIXTURE_BUILD") == "1":
        raise RuntimeError(
            "kernel sources unavailable (MAVLINOS_LAB_SKIP_FIXTURE_BUILD=1); "
            "QEMU-grade fixtures need an Arch host with /boot/vmlinuz-linux-zen"
        )
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
    if os.environ.get("MAVLINOS_LAB_SKIP_FIXTURE_BUILD") == "1":
        raise RuntimeError(
            "initramfs build unavailable (MAVLINOS_LAB_SKIP_FIXTURE_BUILD=1); "
            "QEMU-grade fixture needs an Arch host with /boot/vmlinuz-linux-zen"
        )
    root = dest.parent / (dest.name + "-root")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    # python runtime + shared library deps for lib-dynload C extensions.
    # Resolved dynamically so the builder works on any host distro/python
    # version (previously hard-coded to Arch's python3.14 layout).
    py_bin = _host_python_binary()
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    guest_py_name = py_bin.name if py_bin.name.startswith("python") else f"python{py_ver}"
    lib_specs = [
        ([f"libpython{py_ver}*.so*"], f"usr/lib/libpython{py_ver}.so.1.0"),
        (["libc.so.6", "libc-*.so"], "usr/lib/libc.so.6"),
        (["libm.so.6", "libm-*.so"], "usr/lib/libm.so.6"),
        (["libffi.so.8*", "libffi.so*"], "usr/lib/libffi.so.8"),
        (["ld-linux-x86-64.so.2", "ld-*.so"], "lib64/ld-linux-x86-64.so.2"),
        (["libz.so.1*"], "usr/lib/libz.so.1"),
        (["libcrypto.so.3*"], "usr/lib/libcrypto.so.3"),
        (["libssl.so.3*"], "usr/lib/libssl.so.3"),
        (["libbrotlienc.so.1*"], "usr/lib/libbrotlienc.so.1"),
        (["libbrotlidec.so.1*"], "usr/lib/libbrotlidec.so.1"),
        (["libbrotlicommon.so.1*"], "usr/lib/libbrotlicommon.so.1"),
        (["libzstd.so.1*"], "usr/lib/libzstd.so.1"),
        (["liblzma.so.5*"], "usr/lib/liblzma.so.5"),
        (["libgcc_s.so.1*"], "usr/lib/libgcc_s.so.1"),
        (["libkmod.so.2*"], "usr/lib/libkmod.so.2"),
    ]
    for patterns, dst in lib_specs:
        src = _find_runtime_lib(patterns)
        if src is None or not src.exists():
            continue
        d = root / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, d)
        d.chmod(0o755)

    for src, dst in [(str(py_bin), f"usr/bin/{guest_py_name}")]:
        s = Path(src)
        if not s.exists():
            continue
        d = root / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        d.chmod(0o755)
    for tool in ("modprobe", "insmod"):
        src = f"/usr/sbin/{tool}"
        if not Path(src).exists():
            src = f"/sbin/{tool}"
        if Path(src).exists():
            d = root / f"usr/sbin/{tool}"
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, d)
            d.chmod(0o755)

    # python3 symlink (relative link into usr/bin, matching guest layout)
    bin_dir = root / "usr/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    py3_link = bin_dir / "python3"
    if not py3_link.exists():
        os.symlink(guest_py_name, py3_link)

    # trimmed stdlib
    stdlib_src = _host_python_stdlib_dir()
    stdlib_dst = root / f"usr/lib/{py_ver}"
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
        'char *a[]={"' + guest_py_name + '","/init.py",NULL};'
        'execv("/usr/bin/' + guest_py_name + '",a);return 127;}\n'
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

    # virtio-net is built-in (CONFIG_VIRTIO_NET=y) on target hardware;
    # but in test kernels it may be a module. Include virtio_net.ko + deps for modprobe.
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
        src = f"/usr/lib/modules/7.2.6-zen2-1-zen/kernel/drivers/net/{mod}"
        if Path(src).exists():
            _run(["sudo", "cp", src, str(net_dir)], check=True)
    # failover module (dependency of net_failover)
    core_dir = root / "lib/modules/7.2.6-zen2-1-zen/kernel/net/core"
    core_dir.mkdir(parents=True, exist_ok=True)
    src = "/usr/lib/modules/7.2.6-zen2-1-zen/kernel/net/core/failover.ko.zst"
    if Path(src).exists():
        _run(["sudo", "cp", src, str(core_dir)], check=True)
    # netfs module (dependency of 9pnet)
    fs_dir = root / "lib/modules/7.2.6-zen2-1-zen/kernel/fs"
    fs_dir.mkdir(parents=True, exist_ok=True)
    src = "/usr/lib/modules/7.2.6-zen2-1-zen/kernel/fs/netfs/netfs.ko.zst"
    if Path(src).exists():
        _run(["sudo", "cp", src, str(fs_dir)], check=True)
    # 9p modules for virtfs command channel
    p9_net_dir = root / "lib/modules/7.2.6-zen2-1-zen/kernel/net/9p"
    p9_net_dir.mkdir(parents=True, exist_ok=True)
    for mod in ["9pnet.ko.zst", "9pnet_virtio.ko.zst"]:
        src = f"/usr/lib/modules/7.2.6-zen2-1-zen/kernel/net/9p/{mod}"
        if Path(src).exists():
            _run(["sudo", "cp", src, str(p9_net_dir)], check=True)
    p9_fs_dir = root / "lib/modules/7.2.6-zen2-1-zen/kernel/fs/9p"
    p9_fs_dir.mkdir(parents=True, exist_ok=True)
    src = "/usr/lib/modules/7.2.6-zen2-1-zen/kernel/fs/9p/9p.ko.zst"
    if Path(src).exists():
        _run(["sudo", "cp", src, str(p9_fs_dir)], check=True)
    _run(["sudo", "chown", "-R", "builder:builder", str(root / "lib/modules")], check=False)
    # modprobe needs modules.dep etc.
    _run(["/usr/sbin/depmod", "-b", str(root), "7.2.6-zen2-1-zen"], check=False)

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
    if os.environ.get("MAVLINOS_LAB_SKIP_FIXTURE_BUILD") == "1":
        # Simulation-only mode: the sim backend never reads esp/ artifacts,
        # and data.img is only needed by the QEMU backend. Skip both so the
        # harness logic tests run on hosts without an Arch kernel/toolchain.
        return fixture_dir
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
