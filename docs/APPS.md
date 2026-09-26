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
| Mission Control | PARTIALLY IMPLEMENTED | rofi 2.0 (MIT) + mv-mission-control script (wmctrl backend) + skippy-xd-git (GPL-2.0-or-later, AUR VCS) as E-MC experiment | rofi-mission-control.rasi (window overview) + E-MC-skippy-xd.sh apply/revert/status | rofi, wmctrl, skippy-xd-git (E-MC only, NOT in ISO) | on-demand | live expose on xfwm4 | mv-mission-control: wmctrl-based window overview (rofi script mode); E-MC: skippy-xd one-shot expose; test Super+Tab on HW |
| Control Center | PARTIALLY IMPLEMENTED | NM/UPower/BlueZ via Gio.DBus + pactl + sysfs + xfconf | custom mv-control with sliders (Wi-Fi, BT, Sound, Display, Battery, DND) | — | on-demand | brightness path | no network connect UI; no BT device pairing; no output device switching; verify on HW |
| Notification Center | PARTIALLY IMPLEMENTED | xfce4-notifyd 0.9 (GPL-2.0) + libnotify | Mavericks theme (top-right, rounded, translucent) + DND toggle in mv-control + notifyd config | — | event-driven | no history UI; no grouping; no action buttons; banner look needs HW validate |
| Quick Look | PARTIALLY IMPLEMENTED | GdkPixbuf + poppler-glib (GPL) + GtkSourceView4 + ffprobe | custom mv-quicklook single-shot (images, PDF, text, media metadata) | poppler-glib, ffmpeg (opt) | on-demand | Space binding* | *Thunar has no Space hook; UCA workaround via right-click menu; Space binding not feasible without Thunar plugin; test Super+Space-file on HW |
| Screenshot | PARTIALLY IMPLEMENTED | xfce4-screenshooter (GPL-2.0) + ffmpeg x11grab (record arch) | mv-shot CLI (macOS flag subset) + keybindings | flameshot (alt backend), ffmpeg | on-demand | shortcuts | no annotation tools; no preview after capture; recording experimental; test Super+Shift+3/4/5 |
| Disk Utility | PARTIALLY IMPLEMENTED | gnome-disk-utility 46 (GPL-2.0+) + UDisks2 | stock gnome-disks UI (no Mavericks theming) | gnome-disk-utility | on-demand | S3X display | no Mavericks UI; validate NVMe shown on HW |
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

| Menu Bar | PARTIALLY IMPLEMENTED | xfce4-panel (GPL-2.0) | Mavericks-style top panel (applicationsmenu, tasklist, separator, systray, clock, actions) + panel theme | xfce4-panel | on-demand | panel position/size | no global app menu integration; no app name in panel; test on HW |
| Dock | PARTIALLY IMPLEMENTED | plank (GPL-3.0) | Mavericks theme (reflection, zoom, intellihide) + config | plank | on-demand | — | no running app indicators from Xfce tasklist sync; test on HW |
| Application Menu | PARTIALLY IMPLEMENTED | xfce4-panel applicationsmenu plugin | Mavericks-style app menu (Apple logo, About, Preferences, Services, Hide, Quit) | xfce4-panel | on-demand | — | no dynamic app name; no recent items; test on HW |
| Global Dialogs | PARTIALLY IMPLEMENTED | GTK3 (built-in) | Mavericks theme (filechooser, message dialogs, color/font choosers) | gtk3 | on-demand | — | theming via GTK theme; test on HW |
| File Chooser | PARTIALLY IMPLEMENTED | GTK3 (built-in) | Mavericks theme (sidebar, path-bar, file-list, button-box) | gtk3 | on-demand | — | theming via GTK theme; test on HW |
| Context Menus | PARTIALLY IMPLEMENTED | GTK3 (built-in) + Thunar UCA | Mavericks theme (menu, context-menu, popup-menu) + Thunar custom actions | gtk3 | on-demand | — | theming via GTK theme; Thunar UCA for Finder actions; test on HW |
| Keyboard Shortcut Layer | IMPLEMENTED | xfce4-keyboard-shortcuts (xfconf) | Centralized Mavericks-like shortcuts (Super=Command) | xfconf | on-demand | — | Super+Space/Spotlight, Super+L/Launchpad, Super+Tab/MC, Super+F/Finder; test on HW |
| Desktop / Wallpaper / Session Behavior | PARTIALLY IMPLEMENTED | xfdesktop (GPL-2.0) | Mavericks wallpapers + desktop icons config | xfdesktop | on-demand | — | wallpapers in ISO; no stacked desktop icons; test on HW |
| Window Management | PARTIALLY IMPLEMENTED | xfwm4 (GPL-2.0) | Mavericks theme (titlebar, buttons, shadows) + tiling shortcuts | xfwm4 | on-demand | — | titlebar buttons (close/min/max); shadows; tiling via Super+arrows; test on HW |

## P1 — after P0 core

| Name | State | Backend | UI Type | Deps | Runtime | HW dep | Known Gaps / Next Action |
|---|---|---|---|---|---|---|---|
| TextEdit | PARTIALLY IMPLEMENTED | custom mv-textedit (GtkSourceView4) | custom frontend (Category B) | gtksourceview4 | on-demand | — | custom app implemented; missing Mavericks visual integration (ruler, document inspector, leather texture, rich text/RTF support, spelling) |
| Calculator | PARTIALLY IMPLEMENTED | custom mv-calculator (Python/GTK3, math backend) | custom frontend (Category B) | — | on-demand | — | custom app implemented (Basic/Scientific/Programmer modes, paper tape); missing Mavericks visual integration (metal buttons, LED display, history drawer, RPN mode) |
| Notes | PARTIALLY IMPLEMENTED | custom mv-notes (local JSON + GTK3) | custom frontend (Category B) | — | on-demand | — | custom app exists; missing Mavericks visual integration (leather texture, pin UI, folder sidebar styling) |
| Reminders | PARTIALLY IMPLEMENTED | custom mv-reminders (local JSON + systemd timer) | custom frontend (Category B) | libnotify | timer 1/h | — | custom app exists; missing Mavericks visual integration (paper texture, list styling, notification styling) |
| Calendar | PARTIALLY IMPLEMENTED | orage 4.20 (GPL-2.0+, libical) | alias/wrapper (Category D) | orage | on-demand | — | no Mavericks UI; stock orage only; .desktop alias only |
| Music | PARTIALLY IMPLEMENTED | lollypop 1.4 (GPL-3.0+, GStreamer) | alias/wrapper (Category D) | lollypop | on-demand | audio backend | no Mavericks UI; stock lollypop only; .desktop alias only |
| Photos | PARTIALLY IMPLEMENTED | gthumb 3.12 (GPL-2.0+) | alias/wrapper (Category D) | gthumb | on-demand | — | no Mavericks UI; stock gthumb only; .desktop alias only |
| Voice Memos | PARTIALLY IMPLEMENTED | custom mv-voice (pw-record/parec backend) | custom frontend (Category B) | pw-record, parec | on-demand | audio backend | custom app exists; missing Mavericks visual integration (cassette tape UI, waveform viz) |
| Console | PARTIALLY IMPLEMENTED | custom mv-console (journalctl backend) | custom frontend (Category B) | — | on-demand | values real on HW | custom app exists; missing Mavericks visual integration (sidebar sources, log filtering UI, severity badges) |
| Keychain Access | PARTIALLY IMPLEMENTED | seahorse 47 (GPL-2.0) + GNOME Keyring | alias/wrapper (Category D) | seahorse | on-demand | libsecret backend | no Mavericks UI; stock seahorse only; .desktop alias only |
| Font Book | PARTIALLY IMPLEMENTED | gnome-font-viewer 50 (GTK4/libadwaita) | alias/wrapper (Category D) | gnome-font-viewer | on-demand | — | no Mavericks UI; stock font viewer only; .desktop alias only; GTK4/libadwaita dependency |
| Digital Color Meter | PARTIALLY IMPLEMENTED | gcolor3 2.4 (GPL-2.0) | alias/wrapper (Category D) | gcolor3 | on-demand | — | no Mavericks UI; stock gcolor3 only; .desktop alias only |
| Stickies | PARTIALLY IMPLEMENTED | xfce4-notes-plugin 1.12 (panel plugin) | alias/wrapper (Category D) | xfce4-notes-plugin | on-demand | panel integration | no Mavericks UI; panel plugin only (not standalone); .desktop alias only |
| Mail | PARTIALLY IMPLEMENTED | geary 46 (GPL-3.0) | alias/wrapper (Category D) | geary | on-demand | protocol backend | no Mavericks UI; stock geary only; .desktop alias only |
| Preview | PARTIALLY IMPLEMENTED | evince (GPL, poppler backend) | alias/wrapper (Category D) | evince | on-demand | PDF render on panel | no Mavericks UI; stock evince only; .desktop alias only |
| Dictionary | NOT_STARTED | — | — | — | — | — | no implementation; no .desktop; no backend identified |

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
