# DECISIONS

## Model: MacBook10,1 (Mid 2017) — explicit, not assumption

**Date:** 2026-09-25
**Decision:** Target hardware model explicitly set to MacBook10,1 (Mid 2017), replacing conservative assumption of MacBook9,1 (Early 2016).

**Reasoning:**
- Development now targets MacBook10,1 specifically, eliminating the 

- Wi-Fi chip revision differs between MacBook9,1 and MacBook10,1: MacBook10,1 uses a specific Broadcom BCM43602 revision that requires broadcom-wl-dkms or specific brcmfmac firmware, whereas MacBook9,1 may use brcmfmac in-kernel
- SPI controller behavior differs: MacBook10,1 has SPI controller rev 3+ which exhibits timeout issues on kernels 6.15+ affecting applespi-driven keyboard/trackpad; the AUR macbook12-spi-driver-dkms package has different compatibility characteristics between the two models
- Keyboard/trackpad bring-up strategy differs: MacBook10,1 requires different quirks and fallback planning than MacBook9,1

**Impact on driver selections (drivers/README.md):'
- Wi-Fi: Prioritize broadcom-wl-dkms for MacBook10,1; brcmfmac may work but requires firmware revision matching
- Keyboard/Trackpad: macbook12-spi-driver-dkms AUR package must be evaluated for MacBook10,1 specifically; external USB-C input remains mandatory for bring-up
- Webcam: facetimehd project compatibility may differ between model revisions

**Rollback path:** If real hardware identifies as MacBook9,1 or MacBook8,1, revert HARDWARE.md model field and adjust driver selections accordingly. Document actual model in DECISIONS.md with date.
