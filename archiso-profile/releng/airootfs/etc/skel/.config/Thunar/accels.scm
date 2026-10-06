; accels.scm — Finder-like keyboard accelerators for Thunar 4.20.
; SOURCE OF TRUTH, mirrored to airootfs skel .config/Thunar/accels.scm
; (gated by scripts/check-sync.sh).
;
; Thunar reads this file at window startup and maps gtk accel paths to
; keys.  Every accel path below exists in the Thunar 4.20 binary
; (validated against `strings /usr/bin/thunar` and the live accelerator
; dump; see scripts/test-thunar-finder-config.py).
;
; Finder (Mac OS X 10.9) mapping — Super plays the role of Cmd:
;   Cmd+[  / Cmd+]    back / forward           (Super+bracketleft/right)
;   Cmd+F             search in this window    (Super+f; Ctrl+F stays native)
;   Return            rename the selection     (Finder: Return NEVER opens;
;                                              Ctrl+O / double-click open)
;
; Deliberately NOT mapped here (conflicts documented in docs/DECISIONS.md):
;   Cmd+Up / Cmd+Down (open enclosing folder / open item) — the global
;     shortcut registry already owns Super+Up/Down/Left/Right for window
;     tiling, and a window-local accelerator cannot win that grab.
;   Space (Quick Look) — needs an in-process hook; global Super+Shift+Space
;     and the context-menu action cover it (architectural delta, see
;     docs/DECISIONS.md).

(gtk_accel_path "<Actions>/ThunarStandardView/back" "<Super>bracketleft")
(gtk_accel_path "<Actions>/ThunarStandardView/forward" "<Super>bracketright")
(gtk_accel_path "<Actions>/ThunarWindow/search" "<Super>f")
(gtk_accel_path "<Actions>/ThunarStandardView/rename" "Return")
