#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="mavericks-linux"
iso_label="MAVERICKS"
iso_publisher="MavLinOS <https://github.com/Ansvipa_Rinh/MavLinOS>"
iso_application="MavLinOS Live/Install DVD"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="mavericks"
buildmodes=('iso')
bootmodes=('uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86' '-b' '1M' '-Xdict-size' '1M')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/local/bin/mavericks/mavericks-firstboot.sh"]="0:0:755"
  ["/usr/local/bin/mavericks/extract-brcmfmac-nvram.sh"]="0:0:755"
  ["/usr/local/bin/mavericks/mv-collect.sh"]="0:0:755"
  ["/usr/local/bin/mavericks/mv-power.sh"]="0:0:755"
  ["/usr/local/bin/mavericks/mv-suspend-test.sh"]="0:0:755"
  ["/usr/local/bin/mavericks/mv-thermal.sh"]="0:0:755"
  ["/usr/local/bin/mavericks/mv-experiment.sh"]="0:0:755"
)