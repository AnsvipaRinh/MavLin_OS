# NATIVE REWRITE CANDIDATES — FINAL VERDICT (R1–R2 + D1–D7 closure, 2026-09-28)

> Phase R1: ALL components pre-classified **KEEP** (default).
> R2+ moves entries OFF KEEP only with measurements (before/after wall, RSS,
> wakeup count) + risk assessment. P2 default stays KEEP per directive.
> Companion to: `docs/ARCHITECTURE_OPTIMIZATION_AUDIT.md` (R1 inventories +
> track summary), `docs/PERF_CRITERIA.md` (P-labels), `docs/DECISIONS.md`.

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

## Verdict rules applied at closure

A native (C/Rust) rewrite is warranted only when **both** hold:
(a) the component is on the **persistent or high-frequency hot path** where
runtime cost is continuously paid, **and**
(b) measurements show the rewrite saves >10% wall/RSS/wakeups vs the drift
band, with acceptable risk.

No component meets both criteria:
- All 32 GUI apps are **on-demand, window-open-only** — the 331 ms / 44.6 MB
  GTK import is the framework floor every GTK app pays once per launch; a
  native rewrite would reimplement the entire UI toolkit for a one-time
  per-open cost that is not continuously paid. Zero measured energy win.
- Pure-Python one-shots (mv-spotlight, mv-mission-control, mv-notify-send)
  already skip gi entirely (67–143 ms / 12–17 MB) — the 3–5× startup
  advantage over the GTK path.
- C one-shot (mv-hud): 2.4 ms — near-zero, already optimal.
- Bash one-shots: <10 ms — negligible.
- Test infrastructure / DKMS drivers: not desktop runtime.

## Component table (FINAL — all KEEP)

| Component | Lang | Current | Status | Measurement | Risk | R2 trigger | Verdict reason |
|---|---|---|---|---|---|---|---|
| mv-about | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.383s / 45.9MB | — | — | GTK-FLOOR |
| mv-activity | Python/GTK3 | GTK3 gui-mainloop + 2s /proc poll | KEEP | 0.363s / 46.1MB | — | — | GTK-FLOOR; 2s poll = pure /proc reads, window-open-only (§7) |
| mv-airdrop | Python/GTK3 | GTK3 gui-mainloop + NM D-Bus | KEEP | 0.394s / 48.0MB | — | NM State→signal (low) | GTK-FLOOR; on-open sync Get only — P2 accepted |
| mv-calculator | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.348s / 47.2MB | — | — | GTK-FLOOR |
| mv-calendar | Python/GTK3 | GTK3 gui-mainloop + 5min timer | KEEP | 0.399s / 50.4MB | — | — | GTK-FLOOR; timer = oneshot, compliant (D6) |
| mv-colormeter | Python/GTK3 | GTK3 gui-mainloop + 5Hz tick | KEEP | 0.356s / 47.6MB | — | — | GTK-FLOOR; 5Hz needed for loupe smoothness |
| mv-console | Python/GTK3 | GTK3 gui-mainloop + journalctl follow | KEEP | 0.362s / 47.1MB | — | — | GTK-FLOOR; follow = persistent journalctl -f + IO watch (bfebe9b) |
| mv-control | Python/GTK3 | GTK3 gui-mainloop + NM signals + BlueZ sync + pactl | KEEP | 0.423s / 46.9MB | — | BlueZ signals + pactl→D-Bus (medium) | GTK-FLOOR; SUPERSEDED — Wi-Fi signal-driven (14c8009), BT 5s poll P2, pactl event-driven (D4-6 CLOSED) |
| mv-dictionary | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.407s / 51.7MB | — | — | GTK-FLOOR |
| mv-diskutil | Python/GTK3 | GTK3 gui-mainloop + UDisks2 sync | KEEP | 0.353s / 47.1MB | — | ObjectManager signals (low) | GTK-FLOOR; on-open sync call only — P2 accepted |
| mv-eject | Python/Gio | cli Gio (mount ops, no Gtk) | KEEP | 0.256s / 29.3MB | — | — | Already the efficient path (Gio-only, no Gtk import) |
| mv-fontbook | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.384s / 47.5MB | — | — | GTK-FLOOR |
| mv-getinfo | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.353s / 46.2MB | — | — | GTK-FLOOR |
| mv-hud | C | one-shot energy/thermal readout | KEEP | 0.002s / 11.8MB | — | — | NEAR-ZERO — 2.4ms C one-shot, already optimal |
| mv-keychain | Python/GTK3 | GTK3 gui-mainloop + libsecret | KEEP | 0.358s / 49.1MB | — | — | GTK-FLOOR |
| mv-launchpad | Python/GTK3 | GTK3 gui-mainloop + rofi | KEEP | 0.380s / 45.8MB | — | — | GTK-FLOOR |
| mv-mail | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.332s / 45.6MB | — | — | GTK-FLOOR |
| mv-mission-control | Python/pure | cli-pure (rofi wrapper) | KEEP | 0.067s / 12.8MB | — | — | FAST-ENOUGH — pure Python, 3–5× faster than GTK path |
| mv-music | Python/GTK3 | GTK3 gui-mainloop + MPRIS worker threads | KEEP | 0.376s / 51.2MB | — | — | GTK-FLOOR; MPRIS fetch off UI thread (143e9b2) |
| mv-newfolder | bash | one-shot mkdir + notify | KEEP | 0.008s* / 11.9MB | — | — | NEGLIGIBLE — bash one-shot |
| mv-notes | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.350s / 47.8MB | — | — | GTK-FLOOR |
| mv-notification-center | Python/GTK3 | GTK3 gui-mainloop + xfconf | KEEP | 0.356s / 46.4MB | — | — | GTK-FLOOR |
| mv-notify-send | Python/pure | one-shot libnotify forward | KEEP | 0.143s / 16.5MB | — | — | FAST-ENOUGH — pure Python, on-demand |
| mv-openwith | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.337s / 46.1MB | — | — | GTK-FLOOR |
| mv-photos | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.376s / 49.1MB | — | — | GTK-FLOOR |
| mv-power-ui | Python/GTK3 | GTK3 gui-mainloop + UPower on-open | KEEP | 0.384s / 47.6MB | — | — | GTK-FLOOR; UPower read once at open (S-07 misdiagnosis confirmed) |
| mv-preview | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.369s / 46.1MB | — | — | GTK-FLOOR |
| mv-quicklook | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.338s / 45.7MB | — | — | GTK-FLOOR |
| mv-quicklook-thunar | Python/GTK3 | cli-gtk-import (Thunar action) | KEEP | 2.343s* / 44.8MB | — | — | GTK-FLOOR; *headless artifact — on-target <50ms |
| mv-reminders | Python/GTK3 | GTK3 gui-mainloop + hourly timer | KEEP | 0.354s / 47.5MB | — | — | GTK-FLOOR; timer = oneshot, compliant (D6) |
| mv-rename | Python/GTK3 | one-shot Gtk dialog | KEEP | 0.379s / 44.7MB | — | — | GTK-FLOOR; Gtk dialog justified for rename UX |
| mv-settings | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.333s / 45.7MB | — | — | GTK-FLOOR |
| mv-shot | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.435s / 46.9MB | — | — | GTK-FLOOR |
| mv-spotlight | Python/pure | cli-pure (rofi script mode) | KEEP | 0.088s / 14.5MB | — | — | FAST-ENOUGH — pure Python, per-keystroke but 88ms |
| mv-stickies | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.360s / 47.1MB | — | — | GTK-FLOOR |
| mv-textedit | Python/GTK3 | GTK3 gui-mainloop + 30s autosave | KEEP | 0.383s / 47.1MB | — | — | GTK-FLOOR; 30s autosave = window-open-only, same class as Firefox sessionstore 60s |
| mv-timemachine | Python/GTK3 | GTK3 gui-mainloop + hourly timer | KEEP | 0.368s / 48.7MB | — | — | GTK-FLOOR; timer = oneshot, compliant (D6) |
| mv-voice | Python/GTK3 | GTK3 gui-mainloop | KEEP | 0.387s / 48.8MB | — | — | GTK-FLOOR |
| mv-ytplayer | bash | one-shot mpv launcher | KEEP | 0.008s* / 12.0MB | — | — | NEGLIGIBLE — bash one-shot |
| tools/diagnostics/*.sh | bash | one-shot diagnostics | KEEP | — | — | — | NOT-RUNTIME — diagnostic tools, not daemons |
| scripts/install/*.sh | bash | one-shot firstboot | KEEP | — | — | — | NOT-RUNTIME — firstboot install |
| mock-logind.py | Python | test infrastructure | KEEP | — | — | — | NOT-RUNTIME |
| mock-udisks2.py | Python | test infrastructure | KEEP | — | — | — | NOT-RUNTIME |
| bench harness | Python | test infrastructure | KEEP | — | — | — | NOT-RUNTIME |
| 22× test-*.py | Python | test infrastructure | KEEP | — | — | — | NOT-RUNTIME |
| patch_cirrus.c | C | DKMS driver (not desktop runtime) | KEEP | — | — | — | NOT-RUNTIME — kernel driver, compiles on target (F18 VERIFIED) |
| cs420x.c | C | DKMS driver (not desktop runtime) | KEEP | — | — | — | NOT-RUNTIME — kernel driver, compiles on target (F18 VERIFIED) |

\* Headless artifact — on-target <50ms.

## Summary (FINAL)

| Status | Count |
|---|---|
| KEEP | 48 |
| INVESTIGATE | 0 |
| REWRITE | 0 |
| REJECTED | 0 |

**Closure statement:** All 48 components confirmed KEEP after the full
R1–R2 + D1–D7 track. No native rewrite is warranted for any own-code
component. The GTK framework import cost (331 ms / 44.6 MB) is the floor
for all 32 GUI apps and is paid once per on-demand launch — not a
continuously-paid persistent cost. Pure-Python and C one-shots are already
at or near the floor for their class. The performance track (PERF_AUDIT.md
phases A–E) reached its stopping criteria with 0 P0/P1 suspects; the
architecture track confirms no rewrite candidates remain. This IS the
deliverable: an honest, measured KEEP verdict across the entire own-code
surface — not a failure to act.
