# SERVICE AUDIT — Phase 0.5 (installed system, not live ISO)
# Legend: KEEP = required; ON-DEMAND = socket/timer; OFF = disable; VM-ONLY = guest agents

| Service | Persistent? | Activation | CPU/Wakeups | RAM | Verdict |
|---|---|---|---|---|---|
| systemd-journald | yes | boot | low; rate-limited | ~10MB | KEEP (Storage=volatile in ISO; persistent=auto on install) |
| systemd-logind | yes | boot | event-driven (D-Bus) | ~5MB | KEEP |
| systemd-networkd + resolved | yes | boot | event-driven (netlink) | ~10MB | KEEP in ISO; installed system uses NetworkManager instead |
| NetworkManager | yes | boot | event-driven (netlink/D-Bus) | ~15MB | KEEP (installed system; disable systemd-networkd+iwd there) |
| wpa_supplicant | yes | via NM | event-driven | ~5MB | KEEP (child of NM) |
| iwd | yes | boot (ISO) | event-driven | ~5MB | ISO: KEEP; installed: OFF (NM owns Wi-Fi) |
| tlp.service | no | boot (oneshot) + suspend/resume hook | zero when idle | 0 | KEEP |
| systemd-zram-setup@zram0 | no | boot (oneshot) | zero when idle | 0 | KEEP |
| lightdm | yes | boot | idle sleep; wakes on input | ~20MB | KEEP |
| bluetooth.service | yes | boot | idle sleep; LE scan only on demand | ~5MB | KEEP but RFKILL soft-block until first use |
| upower | yes | D-Bus activation | event-driven (uevent) | ~5MB | KEEP (Xfce power manager needs it) |
| polkit | yes | D-Bus activation | on-demand | ~8MB | KEEP |
| udisks2 | yes | D-Bus activation | on-demand | ~8MB | KEEP (Thunar volumes) |
| pipewire + wireplumber | yes | socket activation | idle sleep; wakes on stream | ~25MB total | KEEP |
| xfce4-power-manager | yes | session | event-driven (UPower) | ~10MB | KEEP |
| fstrim.timer | no | weekly timer | one shot/week | 0 | KEEP |
| reflector.service | no | boot (oneshot, ISO only) | one shot | 0 | ISO: KEEP; installed: OFF (use reflector.timer weekly or remove) |
| sshd | yes | boot | idle sleep | ~5MB | ISO: KEEP (bring-up); installed: OFF (enable on demand) |
| ModemManager | yes | D-Bus activation | polls serial unless filtered | ~10MB | OFF (no modem on MacBook; mask) |
| thermald | — | — | — | — | REMOVED (Phase 0.2: no DPTF profile need demonstrated) |
| ananicy-cpp | — | — | — | — | REMOVED (Phase 0.2: no measurable benefit) |
| power-profiles-daemon | — | — | — | — | NOT INSTALLED (conflicts with TLP) |
| hv_* / vbox* / vmware* | VM-only | VM detection | zero on bare metal | 0 | KEEP in ISO (QEMU test); harmless on MacBook |

## Actions
- Installed system: `systemctl disable iwd systemd-networkd; systemctl enable NetworkManager`
- Installed system: `systemctl mask ModemManager; systemctl disable sshd reflector`
- Live ISO: unchanged (needs iwd+networkd+sshd for install)
