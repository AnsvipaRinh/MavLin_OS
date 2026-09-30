#!/usr/bin/python3.14
"""Guest init for the mavericks-lab QEMU harness.

Runs as PID 1 inside the QEMU guest. Implements the boot environment:
  - mounts proc/sys/dev
  - mounts the DATA disk (virtio-scsi, vfat) at /mnt/data
  - reads fixture.env + boot selection from DATA
  - runs boot stages (rootfs markers, systemd, network) with serial markers
  - runs the mavericks-lab-agent boot oneshot (state machine + health)
  - enters a command loop processing cmd.json files from DATA

Serial log is the ground-truth boot trace. The agent journal + state.json
on DATA are the agent-side evidence.
"""
import ctypes
import fcntl
import json
import os
import socket
import struct
import subprocess
import sys
import time

SERIAL = "/dev/ttyS0"
DATA = "/mnt/data"
CMD_DIR = "/mnt/cmd"
AGENT = "/opt/mavericks-lab-agent"
INBOX = os.path.join(DATA, "deploy-inbox")
CMD = os.path.join(CMD_DIR, "cmd.json")
RESP = os.path.join(CMD_DIR, "resp.json")


def serial(msg):
    line = str(msg)
    for dev in (SERIAL, "/dev/console"):
        try:
            with open(dev, "w") as f:
                f.write(line + "\n")
                f.flush()
            return
        except OSError:
            pass


def _libc():
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
    libc.mount.restype = ctypes.c_int
    return libc


def mount(src, target, fstype, options="", retries=20, delay=0.3):
    try:
        os.makedirs(target, exist_ok=True)
    except OSError:
        pass
    libc = _libc()
    for i in range(retries):
        ret = libc.mount(src.encode(), target.encode(), fstype.encode(), 0, options.encode())
        if ret == 0:
            return True
        if i == 0:
            errno = ctypes.get_errno()
            serial(f"MOUNT_TRY src={src} fstype={fstype} ret={ret} errno={errno} {os.strerror(errno)}")
        time.sleep(delay)
    errno = ctypes.get_errno()
    serial(f"MOUNT_ERR src={src} fstype={fstype} errno={errno} {os.strerror(errno)}")
    return False


def wait_for_dev(path, retries=120, delay=0.5):
    for _ in range(retries):
        if os.path.exists(path):
            return True
        time.sleep(delay)
    return False


def poweroff():
    serial("POWEROFF")
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    try:
        libc.sync()
    except Exception:
        pass
    libc.reboot(0x4321FEDC)
    time.sleep(1)
    try:
        with open("/dev/port", "wb") as f:
            f.seek(0xF4)
            f.write(b"\x02")
    except OSError:
        pass
    while True:
        time.sleep(1)


def read_fixture():
    env = {}
    try:
        with open(os.path.join(DATA, "fixture.env")) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except OSError:
        pass
    return env


def read_slot():
    try:
        with open(os.path.join(DATA, "boot", "next-boot.txt")) as f:
            return f.read().strip()
    except OSError:
        return "A"


def net_up():
    try:
        # First, wait for eth0 (built-in virtio-net case: CONFIG_VIRTIO_NET=y).
        # If not found, try loading the module (modular kernel case).
        if not wait_for_dev("/sys/class/net/eth0", retries=20, delay=0.3):
            serial("NET_WAIT_ETH0 timeout, trying insmod virtio_net + deps")
            # Load dependencies in order: failover -> net_failover -> virtio_net
            base = "/lib/modules/7.2.6-zen2-1-zen/kernel"
            for mod_path in [
                f"{base}/net/core/failover.ko.zst",
                f"{base}/drivers/net/net_failover.ko.zst",
                f"{base}/drivers/net/virtio_net.ko.zst",
            ]:
                mp = subprocess.run(["/usr/sbin/insmod", mod_path],
                           timeout=10, capture_output=True, text=True)
                serial(f"INSMOD {mod_path} rc={mp.returncode} out={mp.stdout.strip()[:120]} err={mp.stderr.strip()[:120]}")
            if not wait_for_dev("/sys/class/net/eth0", retries=20, delay=0.3):
                serial("NET_NO_ETH0")
                # debug: list available interfaces
                try:
                    import os
                    ifaces = os.listdir("/sys/class/net")
                    serial(f"NET_IFACES: {ifaces}")
                except Exception:
                    pass
                return False
        # bring interface up
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack("16sH", b"eth0", 0x1 | 0x10)  # IFF_UP | IFF_RUNNING
        fcntl.ioctl(s, 0x8914, ifreq)  # SIOCSIFFLAGS
        # set IP address (QEMU user-mode default gateway is 10.0.2.2)
        ifreq = struct.pack(
            "16sH2s4s8s", b"eth0", socket.AF_INET, b"\0" * 2,
            socket.inet_aton("10.0.2.15"), b"\0" * 8,
        )
        fcntl.ioctl(s, 0x8916, ifreq)  # SIOCSIFADDR
        ifreq = struct.pack(
            "16sH2s4s8s", b"eth0", socket.AF_INET, b"\0" * 2,
            socket.inet_aton("255.255.255.0"), b"\0" * 8,
        )
        fcntl.ioctl(s, 0x891b, ifreq)  # SIOCSIFNETMASK
        # add default route via 10.0.2.2
        try:
            subprocess.run(["ip", "route", "add", "default", "via", "10.0.2.2", "dev", "eth0"],
                           timeout=5, capture_output=True, check=False)
        except Exception:
            pass
        serial(f"NET_DONE route={dump_proc('/proc/net/route')}")
        return True
    except OSError as e:
        serial(f"NET_IOCTL fail {e}")
        return False


def _netlink_addr():
    NETLINK_ROUTE = 0
    RTM_NEWADDR = 20
    NLM_F_REQUEST = 0x01
    NLM_F_CREATE = 0x400
    NLM_F_ACK = 0x04
    s = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)
    s.bind((0, 0))
    # ifaddrmsg: family, prefixlen, flags, scope, index
    ifmsg = struct.pack("BBBBI", socket.AF_INET, 8, 0, 0, 1)
    # IFA_LOCAL (1) = 127.0.0.1
    local = struct.pack("HH", 8, 1) + socket.inet_aton("127.0.0.1")
    # IFA_ADDRESS (2) = 127.0.0.1
    addr = struct.pack("HH", 8, 2) + socket.inet_aton("127.0.0.1")
    payload = ifmsg + local + addr
    nlmsg_len = 16 + len(payload)
    nlmsg = struct.pack("IHHII", nlmsg_len, RTM_NEWADDR, NLM_F_REQUEST | NLM_F_CREATE | NLM_F_ACK, 1, 0)
    nlmsg += payload
    s.send(nlmsg)
    resp = s.recv(4096)
    s.close()
    if len(resp) >= 16:
        rlen, rtype = struct.unpack("IH", resp[:6])
        if rtype == 2:
            err = struct.unpack("i", resp[16:20])[0]
            serial(f"NETLINK_NEWADDR err={err}")


def _netlink_route():
    NETLINK_ROUTE = 0
    RTM_NEWROUTE = 24
    NLM_F_REQUEST = 0x01
    NLM_F_CREATE = 0x400
    NLM_F_ACK = 0x04
    s = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)
    s.bind((0, 0))
    rtmsg = struct.pack("BBBBBBBBI", socket.AF_INET, 8, 0, 0, 254, 3, 0, 1, 0)
    dst = struct.pack("HH", 8, 1) + socket.inet_aton("127.0.0.0")
    oif = struct.pack("HH", 8, 4) + struct.pack("I", 1)
    payload = rtmsg + dst + oif
    nlmsg_len = 16 + len(payload)
    nlmsg = struct.pack("IHHII", nlmsg_len, RTM_NEWROUTE, NLM_F_REQUEST | NLM_F_CREATE | NLM_F_ACK, 1, 0)
    nlmsg += payload
    s.send(nlmsg)
    resp = s.recv(4096)
    s.close()
    # parse ACK/error
    if len(resp) >= 16:
        rlen, rtype, rflags, rseq, rpid = struct.unpack("IHHII", resp[:16])
        if rtype == 2:  # NLMSG_ERROR
            err = struct.unpack("i", resp[16:20])[0]
            serial(f"NETLINK_ACK err={err}")
        else:
            serial(f"NETLINK_ACK type={rtype} len={rlen}")


def _netlink_route():
    """Add a connected route for 127.0.0.0/8 via netlink RTM_NEWROUTE."""
    NETLINK_ROUTE = 0
    RTM_NEWROUTE = 24
    NLM_F_REQUEST = 0x01
    NLM_F_CREATE = 0x400
    NLM_F_ACK = 0x04
    s = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)
    s.bind((0, 0))
    # rtmsg: family, dst_len, src_len, tos, table, protocol, scope, type, flags
    rtmsg = struct.pack("BBBbBBBBI", socket.AF_INET, 8, 0, 0, 254, 3, 0, 1, 0)
    # RTA_DST (1) = 127.0.0.0
    dst = struct.pack("HH", 1, 4) + socket.inet_aton("127.0.0.0")
    dst += b"\0" * (8 - len(dst) % 8)
    # RTA_OIF (4) = ifindex of lo
    ifindex = 1
    oif = struct.pack("HH", 4, 4) + struct.pack("I", ifindex)
    oif += b"\0" * (8 - len(oif) % 8)
    payload = rtmsg + dst + oif
    nlmsg_len = 16 + len(payload)
    nlmsg = struct.pack("IHHII", nlmsg_len, RTM_NEWROUTE, NLM_F_REQUEST | NLM_F_CREATE | NLM_F_ACK, 1, 0)
    nlmsg += payload
    s.send(nlmsg)
    s.recv(4096)
    s.close()


def agent_env():
    env = dict(os.environ)
    env["MV_LAB_DATA"] = DATA
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONHOME"] = "/usr"
    return env


def run_agent_boot():
    try:
        result = subprocess.run(
            ["/usr/bin/python3", AGENT, "boot"], env=agent_env(), timeout=30,
            capture_output=True, text=True,
        )
        if result.returncode != 0 or result.stderr.strip():
            serial(f"AGENT_ERR rc={result.returncode} err={result.stderr.strip()[:200]}")
    except Exception as e:
        serial(f"AGENT_EXC {type(e).__name__}: {e}")
    try:
        with open(os.path.join(DATA, "state.json")) as f:
            return json.load(f).get("state", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


def run_agent_cmd():
    try:
        with open(CMD) as fin, open(RESP, "w") as fout:
            subprocess.run(
                ["/usr/bin/python3", AGENT, "serve"], stdin=fin, stdout=fout,
                env=agent_env(), timeout=60,
            )
    except Exception:
        pass


def stage_rootfs(slot):
    rdir = os.path.join(DATA, f"rootfs-{slot}", "etc", "mavericks")
    marker = os.path.join(rdir, "slot-ok")
    if not os.path.exists(marker):
        serial("ROOTFS_FAIL")
        return False
    serial("ROOTFS_MOUNT ok")
    return True


def stage_systemd(slot):
    marker = os.path.join(DATA, f"rootfs-{slot}", "etc", "mavericks", "systemd-ok")
    if not os.path.exists(marker):
        serial("SYSTEMD_FAIL")
        return False
    serial("SYSTEMD ok")
    return True


def stage_network(fixture):
    if fixture.get("network", "up") == "up":
        if net_up():
            serial("NETWORK up")
            serial(f"ROUTE: {dump_proc('/proc/net/route')}")
            return True
        serial("NETWORK_FAIL")
        return False
    serial("NETWORK down")
    return True


def stage_agent(fixture):
    if fixture.get("agent", "on") == "off":
        serial("AGENT_SKIP")
        return "SKIP"
    state = run_agent_boot()
    serial(f"AGENT_BOOT state={state}")
    return state


def boot_flow(fixture):
    slot = read_slot()
    serial(f"BOOT slot={slot}")
    if not stage_rootfs(slot):
        return "ROOTFS_FAIL"
    if not stage_systemd(slot):
        return "SYSTEMD_FAIL"
    stage_network(fixture)
    state = stage_agent(fixture)
    serial(f"BOOT_DONE state={state}")
    return state


def command_loop(fixture):
    serial("CMD_LOOP enter")
    while True:
        if os.path.exists(CMD):
            run_agent_cmd()
            try:
                os.unlink(CMD)
            except OSError:
                pass
        time.sleep(0.2)


def dump_proc(name):
    try:
        with open(name) as f:
            return f.read().strip()
    except OSError:
        return "<missing>"


def main():
    serial("GUEST_INIT start")
    mount("proc", "/proc", "proc")
    mount("sysfs", "/sys", "sysfs")
    mount("devtmpfs", "/dev", "devtmpfs")
    wait_for_dev("/dev/vda")
    if not mount("/dev/vda", DATA, "ext4"):
        serial("DATA_MOUNT fail")
        poweroff()
    serial("DATA_MOUNT ok")
    # mount 9p command channel
    os.makedirs(CMD_DIR, exist_ok=True)
    # load 9p modules in dependency order: netfs -> 9pnet -> 9pnet_virtio -> 9p
    for mod, base in [
        ("netfs.ko.zst", "/lib/modules/7.2.6-zen2-1-zen/kernel/fs"),
        ("9pnet.ko.zst", "/lib/modules/7.2.6-zen2-1-zen/kernel/net/9p"),
        ("9pnet_virtio.ko.zst", "/lib/modules/7.2.6-zen2-1-zen/kernel/net/9p"),
        ("9p.ko.zst", "/lib/modules/7.2.6-zen2-1-zen/kernel/fs/9p"),
    ]:
        mod_path = os.path.join(base, mod)
        if os.path.exists(mod_path):
            result = subprocess.run(["/usr/sbin/insmod", mod_path],
                                   timeout=10, capture_output=True, text=True)
            if result.returncode != 0:
                serial(f"INSMOD_FAIL mod={mod} rc={result.returncode} err={result.stderr.strip()[:200]}")
            else:
                serial(f"INSMOD_OK mod={mod}")
        else:
            serial(f"INSMOD_MISSING mod={mod} path={mod_path}")
    # wait for virtio 9p device to appear (max 10s)
    for _ in range(40):
        try:
            for d in os.listdir("/sys/bus/virtio/devices/"):
                try:
                    with open(f"/sys/bus/virtio/devices/{d}/device") as f:
                        dev_id = f.read().strip()
                        if dev_id == "9":  # virtio 9p device ID
                            serial(f"VIRTIO_9P_DEVICE_FOUND: {d}")
                            break
                except:
                    pass
            else:
                time.sleep(0.25)
                continue
            break
        except:
            time.sleep(0.25)
    # mount 9p with retries
    if not mount("cmd-channel", CMD_DIR, "9p", "trans=virtio,version=9p2000.L", retries=30, delay=0.3):
        serial("CMD_CHANNEL_MOUNT fail after retries")
    else:
        serial("CMD_CHANNEL_MOUNT ok")
    fixture = read_fixture()
    max_boots = int(fixture.get("max_boots", "10"))
    for _ in range(max_boots):
        state = boot_flow(fixture)
        if state in ("HEALTHY", "COMMITTED", "ROOTFS_FAIL", "SYSTEMD_FAIL", "SKIP"):
            break
        if state == "FAIL":
            try:
                with open(os.path.join(DATA, "state.json")) as f:
                    st = json.load(f)
                if st.get("attempt", 0) >= st.get("max_attempts", 3):
                    serial("BOOT_LOOP_HALT")
                    break
            except Exception:
                pass
            serial("REBOOT_ROLLBACK")
            continue
        serial("REBOOT")
    command_loop(fixture)


if __name__ == "__main__":
    main()
