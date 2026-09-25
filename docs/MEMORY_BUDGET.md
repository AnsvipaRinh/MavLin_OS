# MEMORY BUDGET — 16 GB MacBook10,1 (estimates; UNKNOWN = measure on hardware)

| Consumer | Est. steady-state | Notes |
|---|---|---|
| kernel + drivers | ~400MB | incl. i915, NVMe, brcmfmac fw |
| Xorg | ~60MB | UNKNOWN — measure via `smem` |
| xfwm4 + xfdesktop + panel | ~55MB | 6 panel plugins only |
| Plank | ~25MB | HideMode=1 |
| LightDM (greeter idle) | ~20MB | post-login greeter exits |
| PipeWire + WirePlumber | ~25MB | idle; rises with streams |
| NetworkManager + wpa_supplicant | ~20MB | |
| upower/udisks2/polkit | ~20MB | D-Bus activated |
| xfce4-power-manager + screensaver + notifyd | ~30MB | |
| bluetoothd | ~5MB | rfkill-blocked until use |
| systemd (PID1 + journald + logind) | ~40MB | journald volatile in ISO |
| TLP / zram-setup | 0 | oneshot, exit after apply |
| Firefox ESR (5 tabs, uBO) | ~800–1500MB | dominant consumer; UNKNOWN on HD 615 |
| caches (pagecache/dentries) | dynamic | kernel defaults; NO vfs tuning |
| zram0 (4–8GB device, zstd ~2:1) | ~0 idle; grows under pressure | swap device, not reservation |
| **Total idle (desktop, no browser)** | **~700MB** | leaves ~15GB for apps/cache |
| **Total typical (desktop + browser)** | **~2GB** | leaves ~14GB headroom |

No memory sysctl tuning justified: 16GB is ample; zram covers spikes.
If 8GB variant exists, same config works (zram0=4GB); re-measure only.
