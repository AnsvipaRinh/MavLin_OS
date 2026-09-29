#!/usr/bin/env bash
# install.sh — install mavericks-lab-agent on the target system.
#
# Sets up:
#   1. Agent binary at /usr/local/bin/mavericks-lab-agent
#   2. ed25519 machine identity key on DATA partition
#   3. SSH forced-command in authorized_keys (no shell access)
#   4. systemd oneshot unit for boot-time state machine advancement
#   5. Narrow sudoers for efibootmgr (Mac backend, documented)
#
# Usage: sudo ./install.sh [--data-dir /mnt/data] [--user mavericks-lab]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_SRC="$SCRIPT_DIR/mavericks-lab-agent"
DATA_DIR="${MAVERICKS_LAB_DATA:-/var/lib/mavericks-lab}"
LAB_USER="${MAVERICKS_LAB_USER:-mavericks-lab}"
INSTALL_DIR="/usr/local/bin"

log() { echo "[install] $*"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --user) LAB_USER="$2"; shift 2 ;;
        *) echo "unknown arg: $1"; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "must run as root (sudo)"
    exit 1
fi

# 1. Install agent binary
log "installing agent to $INSTALL_DIR"
install -Dm755 "$AGENT_SRC" "$INSTALL_DIR/mavericks-lab-agent"

# 2. Create data dir + identity
log "creating data dir: $DATA_DIR"
mkdir -p "$DATA_DIR"
export MV_LAB_DATA="$DATA_DIR"
"$INSTALL_DIR/mavericks-lab-agent" identity

# 3. Create lab user (if missing) + SSH forced-command
if ! id "$LAB_USER" &>/dev/null; then
    log "creating user: $LAB_USER"
    useradd -r -m -s /usr/sbin/nologin "$LAB_USER"
fi
LAB_HOME="$(eval echo ~$LAB_USER)"
mkdir -p "$LAB_HOME/.ssh"
chmod 700 "$LAB_HOME/.ssh"

# Host public key (paste host's host.pub.pem here)
HOST_PUB="$LAB_HOME/.ssh/host.pub.pem"
if [[ ! -f "$HOST_PUB" ]]; then
    log "WARNING: host public key not found at $HOST_PUB"
    log "  Generate on host: mavericks-lab init-host"
    log "  Copy host.pub.pem to target: $HOST_PUB"
    touch "$HOST_PUB"
fi

AUTHORIZED_KEYS="$LAB_HOME/.ssh/authorized_keys"
FORCED_CMD="command=\"$INSTALL_DIR/mavericks-lab-agent serve\",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding $(cat "$HOST_PUB")"
if ! grep -qF "$INSTALL_DIR/mavericks-lab-agent serve" "$AUTHORIZED_KEYS" 2>/dev/null; then
    log "adding forced-command to authorized_keys"
    echo "$FORCED_CMD" >> "$AUTHORIZED_KEYS"
fi
chmod 600 "$AUTHORIZED_KEYS"
chown -R "$LAB_USER:$LAB_USER" "$LAB_HOME/.ssh"

# 3b. Enable sshd — EXPLICIT OPT-IN for remote bring-up (P0-J1).
#     The ISO and installed system ship sshd OFF with root locked. Installing
#     the lab agent is the deliberate act that turns remote management on.
#     Access is key-based forced-command as the unprivileged $LAB_USER only.
log "enabling sshd (explicit remote-bring-up opt-in)"
systemctl enable --now sshd.service

# 4. systemd oneshot unit
log "installing systemd oneshot unit"
cat > /etc/systemd/system/mavericks-lab-agent-boot.service <<EOF
[Unit]
Description=Mavericks Lab Agent — boot state machine + health check
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_DIR/mavericks-lab-agent boot
RemainAfterExit=yes
Environment=MV_LAB_DATA=$DATA_DIR

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable mavericks-lab-agent-boot.service

# 5. Narrow sudoers for Mac backend (efibootmgr only)
#     On QEMU/simulation: not needed. On real Mac: allows boot slot selection
#     without granting root shell.
SUDOERS_FILE="/etc/sudoers.d/mavericks-lab"
if [[ ! -f "$SUDOERS_FILE" ]]; then
    log "installing narrow sudoers (efibootmgr -n only)"
    cat > "$SUDOERS_FILE" <<EOF
# mavericks-lab-agent: boot slot selection only
$LAB_USER ALL=(root) NOPASSWD: /usr/sbin/efibootmgr -n *
$LAB_USER ALL=(root) NOPASSWD: /usr/sbin/efibootmgr -o *
EOF
    chmod 440 "$SUDOERS_FILE"
fi

# Fix ownership of data dir
chown -R "$LAB_USER:$LAB_USER" "$DATA_DIR" 2>/dev/null || true

log "installation complete"
log "  agent:    $INSTALL_DIR/mavericks-lab-agent"
log "  data:     $DATA_DIR"
log "  user:     $LAB_USER"
log "  identity: $DATA_DIR/identity.pem"
log ""
log "Next steps:"
log "  1. On host: mavericks-lab init-host  (generate signing key)"
log "  2. Copy host.pub.pem to target: $HOST_PUB"
log "  3. On host: mavericks-lab status  (verify connectivity)"
