# HARDWARE

**Model: MacBook10,1 (Mid 2017)**

**Known A1534 revisions:**
- Keyboard/Trackpad: AppleSPI protocol — behavior differs from MacBook9,1; SPI controller rev 3+ on kernels 6.15+ may have timeout issues; external USB-C input mandatory for bring-up
- Audio: Cirrus codex — patch required for built-in speakers (same codec, different revision than MacBook9,1)
- Wi-Fi: Broadcom BCM43602 — revision dependent on lspci; MacBook10,1 uses specific rev requiring broadcom-wl-dkms or specific brcmfmac firmware build
- Webcam: FaceTime HD — facetimehd project, low priority if not critical

**Critical note:** Internal keyboard/trackpad via applespi has known issues on kernels 6.15+ (SPI timeouts, driver from AUR fails to build without manual patches). External USB-C keyboard/mouse via hub is mandatory for bring-up, not optional fallback.

**Verification:** Upon first real hardware boot, confirm via dmidecode -s system-product-name outputs MacBook10,1. If different revision, adjust driver selections and rebuild ISO.
