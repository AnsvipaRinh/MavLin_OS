#!/usr/bin/env python3
"""Static guard for NetworkManager/systemd-networkd ownership on installed systems."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRSTBOOT = ROOT / "archiso-profile/releng/airootfs/usr/local/bin/mavericks/mavericks-firstboot.sh"
PACKAGES = ROOT / "archiso-profile/releng/packages.x86_64"


def main():
    firstboot = FIRSTBOOT.read_text(encoding="utf-8")
    packages = PACKAGES.read_text(encoding="utf-8").splitlines()

    assert "systemctl enable NetworkManager.service" in firstboot
    assert "systemd-networkd.service" in firstboot
    assert "systemd-networkd-wait-online.service" in firstboot
    assert "systemctl disable --now systemd-networkd.service systemd-networkd-wait-online.service" in firstboot
    assert "systemctl disable --now iwd.service" in firstboot

    assert "networkmanager" in packages
    assert "wpa_supplicant" in packages
    assert "iwd" not in packages
    assert "modemmanager" not in packages

    print("PASS: installed network stack has explicit NetworkManager ownership")


if __name__ == "__main__":
    main()
