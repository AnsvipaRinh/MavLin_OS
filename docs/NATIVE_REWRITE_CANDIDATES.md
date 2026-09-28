# NATIVE REWRITE CANDIDATES — skeleton (R1)

> Phase R1: ALL components pre-classified **KEEP** (default).
> R2+ moves entries OFF KEEP only with measurements (before/after wall, RSS,
> wakeup count) + risk assessment. P2 default stays KEEP per directive.
> Companion to: `docs/ARCHITECTURE_OPTIMIZATION_AUDIT.md` (R1 inventories),
> `docs/PERF_CRITERIA.md` (P-labels), `docs/DECISIONS.md`.

## Classification key

| Label | Meaning |
|---|---|
| **KEEP** | Current implementation is acceptable; no rewrite warranted |
| **INVESTIGATE** | R2+ may investigate a change if measurements justify it |
| **REWRITE** | R2+ has measured evidence that a rewrite is warranted |
| **REJECTED** | Considered and rejected; reason recorded |

## Decision rules (R2+)

1. Move KEEP → INVESTIGATE only when a P0/P1 criterion is crossed
   (see `docs/PERF_CRITERIA.md`).
2. Move INVESTIGATE → REWRITE only with before/after measurements on
   the same host, same scenario, delta >10% (host drift band).
3. Move INVESTIGATE → KEEP when measurements show delta <10% or risk
   outweighs benefit.
4. P2 items stay KEEP unless new evidence (hardware measurement, user
   report) reopens them.
5. Every move OFF KEEP requires a commit in `docs/DECISIONS.md`.

## Component table

| Component | Lang | Current | Status | Measurement | Risk | R2 trigger |
|---|---|---|---|---|---|---|
| mv-about | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.383s / 45.9MB | — | — |
| mv-activity | Python/GTK3 | GTK3 gui-mainloop + 2s /proc poll | KEEP | 0.363s / 46.1MB | — | — |
| mv-airdrop | Python/GTK3 | GTK3 gui-mainloop + NM D-Bus | KEEP | 0.394s / 48.0MB | — | NM State→signal (low) |
| mv-calculator | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.348s / 47.2MB | — | — |
| mv-calendar | Python/GTK3 | GTK3 gui-mainloop + 5min timer | KEEP | 0.399s / 50.4MB | — | — |
| mv-colormeter | Python/GTK3 | GTK3 gui-mainloop + 5Hz tick | KEEP | 0.356s / 47.6MB | — | — |
| mv-console | Python/GTK3 | GTK3 gui-mainloop + journalctl follow | KEEP | 0.362s / 47.1MB | — | — |
| mv-control | Python/GTK3 | GTK3 gui-mainloop + NM signals + BlueZ sync + pactl | KEEP | 0.423s / 46.9MB | — | BlueZ signals + pactl→D-Bus (medium) |
| mv-dictionary | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.407s / 51.7MB | — | — |
| mv-diskutil | Python/GTK3 | GTK3 gui-mainloop + UDisks2 sync | KEEP | 0.353s / 47.1MB | — | ObjectManager signals (low) |
| mv-eject | Python/Gio | cli Gio (mount ops, no Gtk) | KEEP | 0.256s / 29.3MB | — | — |
| mv-fontbook | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.384s / 47.5MB | — | — |
| mv-getinfo | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.353s / 46.2MB | — | — |
| mv-hud | C | one-shot energy/thermal readout | KEEP | 0.002s / 11.8MB | — | — |
| mv-keychain | Python/GTK3 | GTK3 gui-mainloop + libsecret | KEEP | 0.358s / 49.1MB | — | — |
| mv-launchpad | Python/GTK3 | GTK3 gui-mainloop + rofi | KEEP | 0.380s / 45.8MB | — | — |
| mv-mail | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.332s / 45.6MB | — | — |
| mv-mission-control | Python/pure | cli-pure (rofi wrapper) | KEEP | 0.067s / 12.8MB | — | — |
| mv-music | Python/GTK3 | GTK3 gui-mainloop + MPRIS worker threads | KEEP | 0.376s / 51.2MB | — | — |
| mv-newfolder | bash | one-shot mkdir + notify | KEEP | 0.008s* / 11.9MB | — | — |
| mv-notes | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.350s / 47.8MB | — | — |
| mv-notification-center | Python/GTK3 | GTK3 gui-mainloop + xfconf | KEEP | 0.356s / 46.4MB | — | — |
| mv-notify-send | Python/pure | one-shot libnotify forward | KEEP | 0.143s / 16.5MB | — | — |
| mv-openwith | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.337s / 46.1MB | — | — |
| mv-photos | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.376s / 49.1MB | — | — |
| mv-power-ui | Python/GTK3 | GTK3 gui-mainloop + UPower on-open | KEEP | 0.384s / 47.6MB | — | — |
| mv-preview | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.369s / 46.1MB | — | — |
| mv-quicklook | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.338s / 45.7MB | — | — |
| mv-quicklook-thunar | Python/GTK3 | cli-gtk-import (Thunar action) | KEEP | 2.343s* / 44.8MB | — | — |
| mv-reminders | Python/GTK3 | GTK3 gui-mainloop + hourly timer | KEEP | 0.354s / 47.5MB | — | — |
| mv-rename | Python/GTK3 | one-shot Gtk dialog | KEEP | 0.379s / 44.7MB | — | — |
| mv-settings | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.333s / 45.7MB | — | — |
| mv-shot | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.435s / 46.9MB | — | — |
| mv-spotlight | Python/pure | cli-pure (rofi script mode) | KEEP | 0.088s / 14.5MB | — | — |
| mv-stickies | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.360s / 47.1MB | — | — |
| mv-textedit | Python/GTK3 | GTK3 gui-mainloop + 30s autosave | KEEP | 0.383s / 47.1MB | — | — |
| mv-timemachine | Python/GTK3 | GTK3 gui-mainloop + hourly timer | KEEP | 0.368s / 48.7MB | — | — |
| mv-voice | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.387s / 48.8MB | — | — |
| mv-ytplayer | bash | one-shot mpv launcher | KEEP | 0.008s* / 12.0MB | — | — |
| tools/diagnostics/*.sh | bash | one-shot diagnostics | KEEP | — | — | — |
| scripts/install/*.sh | bash | one-shot firstboot | KEEP | — | — | — |
| mock-logind.py | Python | test infrastructure | KEEP | — | — | — |
| mock-udisks2.py | Python | test infrastructure | KEEP | — | — | — |
| bench harness | Python | test infrastructure | KEEP | — | — | — |
| 22× test-*.py | Python | test infrastructure | KEEP | — | — | — |
| patch_cirrus.c | C | DKMS driver (not desktop runtime) | KEEP | — | — | — |
| cs420x.c | C | DKMS driver (not desktop runtime) | KEEP | — | — | — |

\* Headless artifact — on-target <50ms.

## Summary

| Status | Count |
|---|---|
| KEEP | 48 |
| INVESTIGATE | 0 |
| REWRITE | 0 |
| REJECTED | 0 |

**R2 entry point:** `docs/ARCHITECTURE_OPTIMIZATION_AUDIT.md` §R2 proposal
lists 6 candidates for investigation. All are KEEP until measurements
justify a move.
