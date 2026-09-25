#!/usr/bin/env bash
cat > /etc/mkinitcpio.d/linux.preset <<'EOF'
# mkinitcpio preset file for the 'linux' package on archiso

PRESETS=('archiso')

ALL_kver='/boot/vmlinuz-linux'
archiso_config='/etc/mkinitcpio.conf.d/archiso.conf'

archiso_image="/boot/initramfs-linux.img"
EOF