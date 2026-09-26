# APPS.md — Mavericks surface inventory (pre-hardware, commit 6309a34 baseline preserved)
# Statuses: IMPLEMENTED | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | EXPERIMENT READY | DEFERRED | EXCLUDED
# All custom code: packages/mavericks-apps/ (GPL-2.0-or-later). No Apple assets.

## P0 — core surface

| Name | State | Backend reused (license) | UI | Deps added | Runtime | HW dep | Next action |
|---|---|---|---|---|---|---|---|
| Finder | PARTIALLY IMPLEMENTED | Thunar 4.x (GPL-2.0+) + GVfs/GIO + trash-cli (GPL-2.0) | themed + uca.xml (Quick Look, Put Back, Get Info, Open With, Rename, Eject, Empty Trash, mv-newfolder auto-numbered, Compress, Terminal) + bookmarks + keyboard shortcuts (Super+N/Shift+N New Folder, Super+I Get Info, Super+O Open With) | trash-cli | on-demand | none | no Space key binding for Quick Look (Thunar limitation); no column view; no recursive search toolbar; Space binding documented as accepted delta |
| System Settings | IMPLEMENTED | xfce4-settings, nm-connection-editor, pavucontrol, blueman*, gnome-disks (their licenses) | custom mv-settings launcher (Python/GTK3, exits on close) | — (backend pkgs) | on-demand | BT manager pkg | install blueman on HW test |
| About / System Report | IMPLEMENTED | /proc /sys / DMI + lspci/lsusb/nmcli (cached) | custom mv-about | — | on-demand | values real on HW | validate fields |
| Spotlight | PARTIALLY IMPLEMENTED | rofi 2.0 (MIT) + mv-spotlight script + plocate (GPL-2.0) | rofi-mavericks.rasi (categorized, Mavericks-style) | rofi, plocate | on-demand + daily updatedb oneshot | index builds on installed system | calculator/conversion implemented; categorized file results (Folders, Documents, Images, Audio, Video, Archives, Code, etc.); recent items on empty query; ranking improved (exact/prefix/word/substring); system actions (Settings, Control Center, Activity Monitor, Disk Utility, Terminal); file open via xdg-open; error states (missing plocate, empty index, no results); no preview pane; test Super+Space on HW |
| Launchpad | PARTIALLY IMPLEMENTED | rofi 2.0 (MIT) + mv-launchpad script + XDG .desktop | rofi-launchpad.rasi fullscreen paginated grid (skeuomorphic accents, rounded corners, scrollbar) | rofi, mv-launchpad script | on-demand | keybinding feel | pagination (Left/Right, PgUp/PgDn); folders config (folders.json) with auto-population (Utilities/Other); search filtering; custom positions (positions.json); folder navigation (open/back); empty search/state handling; icon fallback validation; mv-launchpad.desktop entry; no jiggle mode; no App Store integration; test Super+L on HW |
| Mission Control | PARTIALLY IMPLEMENTED | rofi 2.0 (MIT) + mv-mission-control script (wmctrl backend) + skippy-xd-git (GPL-2.0-or-later, AUR VCS) as E-MC experiment | rofi-mission-control.rasi (window overview, Mavericks-style) + E-MC-skippy-xd.sh apply/revert/status | rofi, wmctrl, skippy-xd-git (E-MC only, NOT in ISO) | on-demand | live expose on xfwm4 | mv-mission-control: wmctrl-based window overview (groups by workspace, active window marked, empty workspaces shown, error handling for missing wmctrl); E-MC: skippy-xd one-shot expose with fallback to rofi; test Super+Tab on HW |
| Control Center | PARTIALLY IMPLEMENTED | NM/UPower/BlueZ via Gio.DBus + pactl + sysfs + xfconf | custom mv-control with sliders (Wi-Fi, BT, Sound, Display, Battery, DND) | — | on-demand | brightness path | Wi-Fi connect/disconnect with password prompt; BT device list with connect/disconnect/pair via BlueZ D-Bus; output device switching via pactl; brightness shows unavailable state; power mode shows TLP mode; error/empty states for all sections; verify on HW |
| Notification Center | PARTIALLY IMPLEMENTED | xfce4-notifyd 0.9 (GPL-2.0) + libnotify | Mavericks theme (top-right, rounded, translucent) + DND toggle in mv-control + mv-notification-center history viewer (app-grouped, clear actions, keyboard nav) + mv-notify-send logging wrapper | — | event-driven + on-demand history | banner look needs HW validate | action buttons not feasible (xfce4-notifyd limitation); test Super+Shift+V on HW |
| Quick Look | PARTIALLY IMPLEMENTED | GdkPixbuf + poppler-glib (GPL) + GtkSourceView4 + ffprobe | custom mv-quicklook single-shot (images, PDF, text, media metadata); multi-file nav (←/→, Space); fullscreen (F); Open button; mv-quicklook-thunar global hotkey (Super+Shift+Space) for Thunar selection preview via clipboard | poppler-glib, ffmpeg (opt), xdotool | on-demand | Space binding* | *Thunar has no native Space hook; UCA right-click menu + Super+Shift+Space global hotkey (clipboard-based selection grab) implemented; native Thunar plugin not feasible pre-hardware; test Super+Shift+Space on HW |
| Screenshot | PARTIALLY IMPLEMENTED | xfce4-screenshooter (GPL-2.0) + ffmpeg x11grab (record arch) | mv-shot CLI (macOS flag subset) + keybindings | flameshot (alt backend), ffmpeg | on-demand | shortcuts | no annotation tools; no preview after capture; recording experimental; test Super+Shift+3/4/5 |
| Disk Utility | PARTIALLY IMPLEMENTED | gnome-disk-utility 46 (GPL-2.0+) + UDisks2 | stock gnome-disks UI (no Mavericks theming) | gnome-disk-utility | on-demand | S3X display | no Mavericks UI; validate NVMe shown on HW |
| Activity Monitor | IMPLEMENTED | /proc (no new deps) | custom mv-activity (2s refresh only while open) | — | 0 when closed | values real on HW | validate tabs |
| Energy HUD | IMPLEMENTED — HARDWARE VALIDATION REQUIRED | /sys powercap RAPL + thermal zones (no deps) | custom mv-hud (C, 14KB, one-shot) in xfce4-genmon-plugin (GPL-2.0) | xfce4-genmon-plugin | 1 exec/5s | RAPL on m3-7Y32 | verify watts appear |
| Trash | IMPLEMENTED | GVfs trash + trash-cli restore | Thunar + Put Back action | trash-cli | on-demand | — | validate restore |
| Archive Utility | IMPLEMENTED | xarchiver 0.5 (GPL-2.0+) + libarchive tools | stock + alias | xarchiver | on-demand | — | validate zip flow |

## P1 — after P0 core

| Name | State | Backend | UI Type | Deps | Runtime | HW dep | Known Gaps / Next Action |
|---|---|---|---|---|---|---|---|
| TextEdit | PARTIALLY IMPLEMENTED | custom mv-textedit (GtkSourceView4) | custom frontend (Category B) | gtksourceview4 | on-demand | — | custom app implemented; missing Mavericks visual integration (ruler, document inspector, leather texture, rich text/RTF support, spelling) |
| Calculator | PARTIALLY IMPLEMENTED | custom mv-calculator (Python/GTK3, math backend) | custom frontend (Category B) | — | on-demand | — | custom app implemented (Basic/Scientific/Programmer modes, paper tape); missing Mavericks visual integration (metal buttons, LED display, history drawer, RPN mode) |
| Notes | PARTIALLY IMPLEMENTED | custom mv-notes (local JSON + GTK3) | custom frontend (Category B) | — | on-demand | — | custom app implemented; Mavericks visual integration added (leather folder sidebar, lined paper editor, custom checkboxes, pin indicators, search highlighting) |
| Reminders | PARTIALLY IMPLEMENTED | custom mv-reminders (local JSON + systemd timer) | custom frontend (Category B) | libnotify | timer 1/h | — | custom app exists; Mavericks visual integration added (paper task list, leather sidebar, priority badges, due date indicators, overdue highlighting) |
| Calendar | PARTIALLY IMPLEMENTED | custom mv-calendar (libical + local JSON) | custom frontend (Category B) | — | on-demand | — | custom app implemented (Month/Week/Day views, ICS import/export, multiple calendars); missing Mavericks visual integration (leather texture, paper page flip, birthdays from Contacts) |
| Music | PARTIALLY IMPLEMENTED | custom mv-music (lollypop backend wrapper) | custom frontend (Category B) | lollypop | on-demand | audio backend | custom wrapper with Mavericks sidebar/theme; missing Mavericks visual integration (cover flow, mini player, lyrics panel, smart playlists) |
| Photos | PARTIALLY IMPLEMENTED | custom mv-photos (gthumb backend wrapper) | custom frontend (Category B) | gthumb | on-demand | — | custom wrapper with Mavericks sidebar/theme; missing Mavericks visual integration (moments, memories, people/faces, shared albums) |
| Voice Memos | PARTIALLY IMPLEMENTED | custom mv-voice (pw-record/parec backend) | custom frontend (Category B) | pw-record, parec | on-demand | audio backend | custom app implemented (cassette tape UI, waveform visualization, rename/delete); missing Mavericks visual integration (cassette tape animation, real-time waveform during recording, metadata editing, iCloud sync placeholder) |
| Console | PARTIALLY IMPLEMENTED | custom mv-console (journalctl + dmesg backend) | custom frontend (Category B) | — | on-demand | values real on HW | custom app implemented (sidebar sources, severity tags, live tail, search, source filter); missing Mavericks visual integration (leather sidebar, severity badges, log line formatting, export) |
| Keychain Access | PARTIALLY IMPLEMENTED | custom mv-keychain (seahorse backend wrapper) | custom frontend (Category B) | seahorse | on-demand | libsecret backend | custom wrapper with Mavericks sidebar/theme; missing Mavericks visual integration (keychain list, certificate details, password generator, secure notes) |
| Font Book | PARTIALLY IMPLEMENTED | custom mv-fontbook (gnome-font-viewer backend wrapper) | custom frontend (Category B) | gnome-font-viewer | on-demand | — | custom wrapper with Mavericks sidebar/theme; missing Mavericks visual integration (font preview waterfall, glyph grid, validation, collections) |
| Digital Color Meter | PARTIALLY IMPLEMENTED | custom mv-colormeter (gcolor3 backend wrapper) | custom frontend (Category B) | gcolor3 | on-demand | — | custom wrapper with Mavericks aperture/picking; missing Mavericks visual integration (multiple apertures, pixel loupe, color palette export) |
| Stickies | PARTIALLY IMPLEMENTED | custom mv-stickies (native GTK3) | custom frontend (Category B) | — | on-demand | — | custom app implemented (yellow stickies, handwriting font, color picker, desktop persistence); missing Mavericks visual integration (window shadow, transparency, print, sync) |
| Mail | PARTIALLY IMPLEMENTED | custom mv-mail (geary backend wrapper) | custom frontend (Category B) | geary | on-demand | protocol backend | custom wrapper with Mavericks sidebar/theme; missing Mavericks visual integration (conversation view, VIP flags, rules, signatures) |
| Preview | PARTIALLY IMPLEMENTED | custom mv-preview (evince backend wrapper) | custom frontend (Category B) | evince | on-demand | PDF render on panel | custom wrapper with annotation toolbar; missing Mavericks visual integration (thumbnail sidebar, markup toolbar, form filling, export) |
| Dictionary | PARTIALLY IMPLEMENTED | custom mv-dictionary (GTK3+WebKit2) | custom frontend (Category B) | webkit2gtk | on-demand | — | custom app implemented (Dictionary/Thesaurus/Wikipedia/Apple tabs, history, bookmarks); missing Mavericks visual integration (leather binding, page flip animation, pronunciation audio, word of the day) |

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
