# APPS.md — Mavericks surface inventory (pre-hardware, commit 6309a34 baseline preserved)
# Statuses: IMPLEMENTED | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | EXPERIMENT READY | DEFERRED | EXCLUDED
# All custom code: packages/mavericks-apps/ (GPL-2.0-or-later). No Apple assets.

## P0 — core surface

| Name | State | Backend reused (license) | UI | Deps added | Runtime | HW dep | Next action |
|---|---|---|---|---|---|---|---|
| Finder | PARTIALLY IMPLEMENTED | Thunar 4.x (GPL-2.0+) + GVfs/GIO + trash-cli (GPL-2.0) | themed + uca.xml (Quick Look, Put Back, Get Info, Open With, Rename, Eject, mv-newfolder auto-numbered, Compress, Terminal) + bookmarks | trash-cli | on-demand | none | no Space key binding for Quick Look (Thunar limitation); no column view; no recursive search toolbar; Space binding documented as accepted delta |
| System Settings | IMPLEMENTED | xfce4-settings, nm-connection-editor, pavucontrol, blueman*, gnome-disks (their licenses) | custom mv-settings launcher (Python/GTK3, exits on close) | — (backend pkgs) | on-demand | BT manager pkg | install blueman on HW test |
| About / System Report | IMPLEMENTED | /proc /sys / DMI + lspci/lsusb/nmcli (cached) | custom mv-about | — | on-demand | values real on HW | validate fields |
| Spotlight | PARTIALLY IMPLEMENTED | rofi 2.0 (MIT) + mv-spotlight script + plocate (GPL-2.0) | rofi-mavericks.rasi (categorized) | rofi, plocate | on-demand + daily updatedb oneshot | index builds on installed system | calculator/conversion implemented; categorized file results (Folders, Documents, Images, Audio, Video, Archives, Code, etc.); recent items on empty query; ranking improved (exact/prefix/word/substring); no preview pane; test Super+Space on HW |
| Launchpad | PARTIALLY IMPLEMENTED | rofi 2.0 (MIT) + mv-launchpad script + XDG .desktop | rofi-launchpad.rasi fullscreen paginated grid | rofi, mv-launchpad script | on-demand | keybinding feel | pagination (Left/Right, PgUp/PgDn); folders config (folders.json); search filtering; custom positions (positions.json); no jiggle mode; no App Store integration; test Super+L |
| Mission Control | EXPERIMENT READY | rofi window mode (baseline); skippy-xd-git (GPL-2.0-or-later, AUR VCS) expose as experiment E-MC | rofi theme + configs/desktop/skippy-xd/skippy-xd.rc (cosmos, one-shot) + E-MC-skippy-xd.sh apply/revert/status | skippy-xd-git (E-MC only, NOT in ISO) | 0 idle (no daemon by design) | live expose on xfwm4 | run E-MC apply on HW, validate expose/select/Escape |
| Control Center | IMPLEMENTED | NM/UPower/BlueZ via Gio.DBus + pactl + sysfs + xfconf | custom mv-control popup (exits on focus loss) | — | on-demand | brightness path | verify backlight sysfs |
| Notification Center | IMPLEMENTED | xfce4-notifyd 0.9 (GPL-2.0, log included) + libnotify | themed + DND toggle in mv-control | — | event-driven | banner look | validate on HW |
| Quick Look | IMPLEMENTED | GdkPixbuf + poppler-glib (GPL) + GtkSourceView4 + ffprobe | custom mv-quicklook single-shot | poppler-glib, ffmpeg (opt) | on-demand | Space binding* | *Thunar has no Space hook; use uca + Super+Space-file? document |
| Screenshot | IMPLEMENTED | xfce4-screenshooter (GPL-2.0) + ffmpeg x11grab (record arch) | mv-shot CLI (macOS flag subset) + keybindings | flameshot (alt backend), ffmpeg | on-demand | shortcuts | test Super+Shift+3/4/5 |
| Disk Utility | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | gnome-disk-utility 46 (GPL-2.0+) + UDisks2 | stock UI + Mavericks alias .desktop | gnome-disk-utility | on-demand | S3X display | validate NVMe shown |
| Activity Monitor | IMPLEMENTED | /proc (no new deps) | custom mv-activity (2s refresh only while open) | — | 0 when closed | values real on HW | validate tabs |
| Energy HUD | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | /sys powercap RAPL + thermal zones (no deps) | custom mv-hud (C, 14KB, one-shot) in xfce4-genmon-plugin (GPL-2.0) | xfce4-genmon-plugin | 1 exec/5s | RAPL on m3-7Y32 | verify watts appear |
| Trash | IMPLEMENTED | GVfs trash + trash-cli restore | Thunar + Put Back action | trash-cli | on-demand | — | validate restore |
| Archive Utility | IMPLEMENTED | xarchiver 0.5 (GPL-2.0+) + libarchive tools | stock + alias | xarchiver | on-demand | — | validate zip flow |
| TextEdit | IMPLEMENTED | mousepad 0.7 (GPL-2.0+, gtksourceview4) | stock + alias + config | mousepad | on-demand | — | validate |
| Calculator | IMPLEMENTED | galculator 2.1 (GPL-2.0+) | stock + alias | galculator | on-demand | — | validate |
| Music | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | lollypop 1.4 (GPL-3.0+, GStreamer) | stock + alias | lollypop | on-demand | audio backend | test playback on HW |
| Reminders | IMPLEMENTED | local JSON + notify-send + user systemd timer (hourly oneshot) | custom mv-reminders | libnotify (present) | timer 1/h | notification look | validate timer |
| Calendar | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | orage 4.20 (GPL-2.0+, libical) | stock + alias | orage | on-demand | — | validate ICS |
| Notes | IMPLEMENTED | local JSON (no deps beyond GTK3) | custom mv-notes | — | on-demand | — | validate |
| Lock curtain | IMPLEMENTED | xfce4-screensaver (present) | theme config; lock DISABLED by default (no password infra) | — | on-demand | screensaver on panel | validate |
| Power UI | IMPLEMENTED | systemd/logind | custom mv-power-ui dialog | — | on-demand | suspend backend | test on HW |
| Settings pages (KB/mouse/display/sound/net/BT) | IMPLEMENTED | libinput/X11/xrandr/NM/BlueZ/PipeWire/UPower/dbus | via mv-settings → real tools (no fake toggles) | blueman* | on-demand | applespi/BCM43602 | *blueman NOT in ISO yet — add on HW validation |

## P1 — after P0 core

| Name | State | Decision |
|---|---|---|
| Mail | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | geary 46 (GPL-3.0) + alias; no protocol code written |
| Photos | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | gthumb 3.12 (GPL-2.0+) + alias; GdkPixbuf backend |
| Voice Memos | IMPLEMENTED | custom mv-voice (pw-record/parec backend); EXPERIMENT: recording power |
| Keychain Access | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | seahorse 47 (GPL-2.0) + alias over GNOME Keyring/libsecret |
| Console | IMPLEMENTED | custom mv-console (journalctl backend, live toggle) |
| Font Book | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | gnome-font-viewer 50 (GTK4/libadwaita) + alias |
| Digital Color Meter | IMPLEMENTED | gcolor3 2.4 (GPL-2.0) + alias |
| Stickies | IMPLEMENTED | xfce4-notes-plugin 1.12 (panel plugin; NOT added to panel by default) |
| Preview | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | evince (GPL, poppler backend) + alias mv-preview.desktop | stock + alias | evince (in ISO) | on-demand | PDF render on panel | validate open/pdf flow |

## P2 — research only

| Name | State | Notes |
|---|---|---|
| AirDrop | DEFERRED | No mature+legal Linux backend identified; revisit after P0/P1 |
| Time Machine | DEFERRED | Candidates evaluated 2026-09-25 (docs/RESEARCH_TIMEMACHINE.md): Borg 1.4.5 primary + btrfs snapshots local layer; restic deferred | UI after P1 |
| Automator/Shortcuts | DEFERRED | Architecture research only |
| Grapher | DEFERRED | Candidates: matplotlib/labplot; not prioritized |

## EXCLUDED (per task): Contacts, TV, Podcasts, Siri, AirPlay, DVD Player, Chess,
## Game Center, Printer Discovery, Image Capture, Migration Assistant, App Store,
## account/login infrastructure, password lock, Terminal replacement, Apple assets.

## Backend license summary (all OSI-approved)
MIT: rofi. GPL-2.0(-only/-or-later): Thunar, xfce4*, trash-cli, xarchiver,
mousepad, galculator, orage, gnome-disk-utility, seahorse, gcolor3,
xfce4-notes-plugin, gtksourceview4, plocate, custom mavericks-apps.
GPL-3.0-or-later: lollypop, geary. LGPL (libraries): poppler-glib, GTK3, GLib/GIO.
