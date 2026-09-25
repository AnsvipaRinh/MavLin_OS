# DEPENDENCY AUDIT — Phase 0.5 (packages.x86_64)

## Removed (Phase 0.2/0.3)
- `ananicy-cpp` — no measurable benefit; removed from packages + services.
- `thermald` — redundant with TLP/HWP; removed.
- `epiphany` (+ `epiphany-mavericks-theme` from ISO) — Firefox ESR is PRIMARY;
  Epiphany kept as source package in `packages/` but NOT in ISO (WebKitGTK +
  GNOME stack duplicates Firefox for marginal RAM saving, unvalidated).

## Added (required for feature-complete desktop)
- Xorg: `xorg-server xorg-xinit xorg-xrandr` (was missing — Xfce cannot run).
- Session: `lightdm lightdm-gtk-greeter` (was missing — no graphical login).
- Xfce completeness: `xfce4-appfinder xfce4-power-manager xfce4-screensaver
  xfce4-screenshooter xfce4-notifyd xfce4-taskmanager thunar-archive-plugin
  xdg-user-dirs` (notification daemon = xfce4-notifyd, NOT dunst: native,
  fewer deps, session-integrated).
- Audio: `pipewire pipewire-alsa pipewire-pulse wireplumber pavucontrol`
  (was missing — no sound server at all).
- Browser: `firefox firefox-ublock-origin` (replaces epiphany).
- Network: `networkmanager` (installed system; ISO keeps iwd+networkd for install).
- Power/debug: `powertop turbostat stress-ng intel-gpu-tools mesa-utils nvme-cli upower`.

## Kept deliberately
- `iwd + systemd-networkd + systemd-resolved` in ISO (installer networking).
  Installed system switches to NetworkManager (see mavericks-firstboot.sh).
- VM guest agents (`hv_*`, `vboxservice`, `vmtoolsd`) in ISO only — needed for
  QEMU smoke test; zero cost on bare metal (not started without hypervisor).
- `reflector`, `sshd` in ISO only; disabled on installed system.

## Duplicates eliminated
- notify: xfce4-notifyd ONLY (no dunst).
- browser: Firefox ONLY in ISO (no Epiphany/WebKitGTK runtime).
- power: TLP ONLY (no thermald/ananicy/power-profiles-daemon).
- audio: PipeWire ONLY (no PulseAudio daemon).
