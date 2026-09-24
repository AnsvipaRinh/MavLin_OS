# HARDWARE

**Model: MacBook9,1**


**Known A1534 revisions:**
- Keyboard/Trackpad: AppleSPI protocol
- Audio: Cirrus codex — patch required
- Wi-Fi: Broadcom BCM43602 — brcmfmac or broadcom-wl-dkms
- Webcam: FaceTime HD — facetimehd project, low priority

**Critical note:** Internal keyboard/trackpad via applespi has known issues on kernels 6.15+. External USB-C keyboard/mouse via hub is mandatory.

**Assumption flag:** Conservative assumption (MacBook9,1). Verify via dmidecode on real hardware.
