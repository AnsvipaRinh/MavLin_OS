# Contributing to MavLinOS

## Setup (one-time)

```bash
# Arch host or Arch-based container
sudo pacman -S base-devel git python python-gobject gtk3 libnotify rofi plocate \
  xfce4-panel xfce4-notifyd plank thunar gvfs trash-cli poppler-glib gtksourceview4 \
  ffmpeg xdotool gdk-pixbuf2 fontconfig gsfonts python-pip

# Python deps (if any app needs them)
pip install --user -r packages/mavericks-apps/requirements.txt 2>/dev/null || true

# Clone
git clone https://github.com/Ansvipa_Rinh/MavLinOS
cd MavLinOS
```

**Community rules:** this project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Report security issues privately per [SECURITY.md](SECURITY.md). AI-generated contributions are reviewed under the same rules as human ones — see `docs/CONTRIBUTION_PROTOCOL.md` and `docs/VIBE_CODING.md`.

## First Contribution Path

1. **Read** `AGENTS.md` (constitution), `docs/HARDWARE.md`, `docs/APPS.md`, `docs/NEEDS_HARDWARE_TEST.md`
2. **Pick** a `PARTIALLY IMPLEMENTED` or `EXPERIMENT READY` item from `docs/APPS.md` (P0 before P1)
3. **Implement** the feasible pre-hardware gap (UI, integration, keyboard, dialogs, MIME, theme)
4. **Test** locally: `./scripts/check-sync.sh --check-repos` + relevant `test-mv-*.py`
5. **Commit** small logical units (`feat:`, `fix:`, `theme:`, `docs:`)
6. **Update** `docs/APPS.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md` for your change

## Profile Rules (from OS-2c)

- **generic** profile: no MacBook-specific drivers, no `pcie_port_pm=off`, no applespi modules
- **macbook10,1** profile: includes applespi, brcmfmac/broadcom-wl-dkms, Cirrus audio DKMS, S3X NVMe cmdline
- Configs in `configs/profiles/` — baseline + 12 experiments (E1–E12)
- Selector script: `scripts/apply-hardware-selection.sh` (runs on first boot)
- **Never** add MacBook-specific config to generic profile

## Mavericks Fidelity Bar

**Target: macOS 10.9 Mavericks (skeuomorphic), NOT modern macOS.**

Every user-facing change must satisfy:

| Axis | Pass Criteria |
|------|---------------|
| **Visual** | Grey/translucent surfaces, toolbar gradients, traffic-light buttons (#ff5c5c/#4cd964/#ffbd4c), Lucida Grande font stack, consistent spacing/radius/shadows |
| **Interaction** | Keyboard nav (Tab/Arrows/Escape/Enter), context menus, drag-drop where feasible, Mavericks shortcuts (Super-layer global, Ctrl-layer app) |
| **Integration** | Dock indicator, menu bar presence, notification style, file chooser, dialogs, MIME associations, Trash/Quick Look/Open With |
| **Behavior** | Window minimize/maximize/fullscreen, application quit (Cmd+Q → Super+Q), workspace switching, launch behavior |

**Color-only changes = NOT sufficient.** A `PARTIALLY IMPLEMENTED` app becomes `IMPLEMENTED` only when visual + interaction + integration + behavior all pass.

## Performance & Security Bars

- **No persistent daemons** for UI features (event-driven, on-demand, one-shot only)
- **No Electron / Java / heavy web UI** — GTK3/X11/native only
- **No arbitrary script execution** on host (see `SECURITY.md`)
- **Power baseline frozen** (Section 7 AGENTS.md): TLP powersave, zram, no thermald/ananicy/powertop-auto-tune
- **Every change** must pass `./scripts/check-sync.sh --check-repos` (221 checks)

## Commit Style

```
feat: mv-notes — add search filter + match highlighting
fix: mv-control — refresh_all timer leak on destroy
theme: gtk.scss — repair dialog button-box CSS (was 65 parse errors)
docs: APPS.md — update mv-calendar status to PARTIALLY_IMPLEMENTED
perf: mv-music — lazy Gtk import in timer one-shot (0.41→0.10s)
```

One logical change per commit. No "WIP" or "misc" commits.

## Testing Checklist (pre-push)

```bash
# Syntax + mirrors + security + ISO hardening
./scripts/check-sync.sh --check-repos

# Per-app tests (pick relevant)
python3 scripts/test-mv-notes.py
python3 scripts/test-mv-control.py
# ... etc (23 test files)

# Theme CSS validation
python3 scripts/test-theme-css.py

# Firefox chrome validation
python3 scripts/test-firefox-chrome.py

# Benchmarks (if perf-related)
./scripts/bench/run-bench.sh
```

## What We Don't Accept

- Modern flat macOS / GNOME / KDE aesthetics
- Electron wrappers for native Linux apps
- New persistent background services
- Arbitrary kernel cmdline options without evidence + benchmark
- Apple proprietary assets (icons, sounds, fonts, images)
- Changes that break generic profile or x86_64 portability