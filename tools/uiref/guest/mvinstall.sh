#!/bin/sh
# mvinstall.sh - offline installation of the OS X 10.9 payload into an HFS+
# volume, run as PID 1 of a QEMU Linux initramfs (console=ttyS0).
#
# Source:  squashfs image built from the extracted InstallESD payload
# Target:  HFS+ volume already formatted as "Macintosh HD"
# No GUI, no Apple installer: the payload is what the installer itself copies.
set -x
PATH=/usr/bin:/usr/sbin:/bin:/sbin
export PATH

MODDIR=/usr/lib/modules
KVER=$(ls $MODDIR | head -1)
K="$MODDIR/$KVER/kernel"

echo "MVSTEP modules"
insmod "$K/fs/squashfs/squashfs.ko" 2>/dev/null
insmod "$K/fs/hfsplus/hfsplus.ko" 2>/dev/null
sleep 2

echo "MVSTEP blockdev"
for d in /dev/sd* /dev/hd*; do
    [ -b "$d" ] && echo "found $d"
done

mkdir -p /mnt/src /mnt/tgt

SRC=""
for cand in /dev/sda /dev/sda1 /dev/sda2 /dev/sdb /dev/sdb1; do
    [ -b "$cand" ] || continue
    if mount -t squashfs -o loop "$cand" /mnt/src 2>/dev/null; then
        SRC="$cand"
        break
    fi
done
echo "MVSTEP src=$SRC"

TGT=""
for cand in /dev/sda /dev/sda1 /dev/sdb /dev/sdb1 /dev/sdc /dev/sdc1; do
    [ -b "$cand" ] || continue
    [ "$cand" = "$SRC" ] && continue
    if mount -t hfsplus "$cand" /mnt/tgt 2>/dev/null; then
        TGT="$cand"
        break
    fi
done
echo "MVSTEP tgt=$TGT"

if [ -z "$SRC" ] || [ -z "$TGT" ]; then
    echo "MVFAIL source or target not mountable"
    echo "MV_INSTALL_DONE"
    sleep 5
    echo o > /proc/sysrq-trigger 2>/dev/null
    while :; do sleep 60; done
fi

echo "MVSTEP copying payload"
START=$(date +%s)
# cp -a keeps symlinks, modes and mtimes; the payload is a plain file tree
cp -a /mnt/src/. /mnt/tgt/ 2>/tmp/cp.err
RC=$?
echo "MVSTEP cp rc=$RC after $(( $(date +%s) - START ))s"
[ -s /tmp/cp.err ] && head -5 /tmp/cp.err

echo "MVSTEP verifying"
ls /mnt/tgt | head -20
test -f /mnt/tgt/System/Library/CoreServices/boot.efi && echo "MVSTEP boot.efi present"
test -d /mnt/tgt/System/Library/Frameworks/AppKit.framework && echo "MVSTEP AppKit present"

echo "MVSTEP firstboot configuration"
mkdir -p /mnt/tgt/etc/ssh /mnt/tgt/Library/LaunchDaemons /mnt/tgt/var/root/Library/Preferences

cat > /mnt/tgt/etc/ssh/sshd_config <<'EOF'
PermitRootLogin yes
PasswordAuthentication yes
PermitEmptyPasswords yes
UsePAM no
X11Forwarding no
PrintMotd no
AcceptEnv *
Subsystem sftp /usr/lib/ssh/sftp-server
EOF

# Start sshd at boot even though Remote Login is "off" in a fresh install:
# a launchd job of our own, not an Apple modification.
cat > /mnt/tgt/Library/LaunchDaemons/com.mavlinos.sshd.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.mavlinos.sshd</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/sbin/sshd</string>
        <string>-D</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/mvsshd.log</string>
    <key>StandardErrorPath</key><string>/tmp/mvsshd.err</string>
</dict>
</plist>
EOF

sync
echo "MVSTEP done"
df -h /mnt/tgt 2>/dev/null | tail -2
echo "MV_INSTALL_DONE"
sync
sleep 3
echo o > /proc/sysrq-trigger 2>/dev/null
while :; do sleep 60; done
