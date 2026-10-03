# Vibe Coding Protocol — External Agent Workflow

This document describes how an external AI agent (OpenCode, Claude, Codex, Gemini, Cursor, etc.)
should work in this repository. You do not need OpenCode installed.

---

## 1. Read Order (mandatory before first change)

```
1. AGENTS.md                    # Constitution — read entirely
2. docs/HARDWARE.md             # Target hardware + base config
3. docs/APPS.md                 # 46-objective inventory + statuses
4. docs/NEEDS_HARDWARE_TEST.md  # What requires real MacBook10,1
5. docs/PROGRESS.md             # Latest phase log (last 3 sections)
6. docs/DECISIONS.md            # Last 5 entries (rationale for recent choices)
7. CONTRIBUTING.md              # This repo's contribution rules
8. SECURITY.md                  # Threat model + verdicts
```

**Do not skip.** The agent constitution (AGENTS.md §0) binds autonomous behavior.

---

## 2. Check-Sync Gate (run before every commit)

```bash
./scripts/check-sync.sh --check-repos
```

144 checks: config mirrors, shell/XML/desktop/PKGBUILD syntax, py_compile,
Firefox seed validation, ISO security (sshd off, root locked), secret scan.
**Must pass.** No exceptions.

---

## 3. Bench / Tests (run for your change area)

```bash
# Per-app (pick relevant)
python3 scripts/test-mv-<app>.py

# Theme
python3 scripts/test-theme-css.py

# Firefox chrome
python3 scripts/test-firefox-chrome.py

# Full suite (if broad change)
python3 -m pytest lab/harness/tests/ -v
python3 lab/tests/test_agent_boot.py  # etc (7 scripts, 158 assertions)

# Benchmarks (if perf claim)
./scripts/bench/run-bench.sh
```

---

## 4. Fidelity Classification (every UI change)

Classify your change against **four axes**. A `PARTIALLY IMPLEMENTED` item becomes
`IMPLEMENTED` only when **all four** are satisfied pre-hardware.

| Axis | Question | Evidence Required |
|------|----------|-------------------|
| **Visual** | Does it use the common Mavericks visual language? (grey/translucent surfaces, toolbar gradients, traffic-light buttons, Lucida Grande stack, consistent spacing/radius/shadows) | Screenshot or CSS diff showing shared tokens |
| **Interaction** | Keyboard nav (Tab/Arrows/Escape/Enter), context menus, drag-drop, Mavericks shortcuts (Super global, Ctrl app) | Test script assertions for key bindings + focus order |
| **Integration** | Dock indicator, menu bar presence, notification style, file chooser, dialogs, MIME associations, Trash/Quick Look/Open With | `.desktop` + D-Bus + GTK theme integration verified |
| **Behavior** | Window minimize/maximize/fullscreen, app quit, workspace switching, launch behavior | Manual test steps documented in PR |

**Color-only = NOT sufficient.** "GTK theme applied" ≠ Mavericks fidelity.

---

## 5. HW_PENDING Marking

If your change touches something that **cannot be validated without real MacBook10,1 hardware**,
add it to `docs/NEEDS_HARDWARE_TEST.md` with:

```markdown
## Your Component — hardware validation
- [ ] Specific test case (e.g., "HiDPI rendering of dialog at 2304×1440")
- [ ] Expected outcome
- [ ] Measurement command (if applicable)
```

Do NOT claim `IMPLEMENTED — HARDWARE VALIDATION REQUIRED` without this entry.

---

## 6. No MacBook Needed for Generic UI

The **generic profile** (`configs/profiles/baseline.conf`) builds a fully functional
Mavericks-themed Arch + Xfce desktop on any x86_64 machine. Use it for:

- Visual regression (GTK theme, icons, cursors, rofi themes)
- Keyboard shortcut layer testing
- Application launch/integration (`.desktop`, MIME, D-Bus)
- Dialog/file chooser/context menu styling
- Window management (xfwm4 theme)
- Dock (plank) + menu bar (xfce4-panel) behavior

**QEMU+OVMF smoke test** validates ISO boot + DE start without hardware.

---

## 7. Commit & Update Cycle

After implementing a feasible gap:

```bash
# 1. Test
./scripts/check-sync.sh --check-repos
python3 scripts/test-mv-<your-app>.py

# 2. Update docs (mandatory)
# - docs/APPS.md: status, known gaps, next action
# - docs/PROGRESS.md: append to latest phase or new subsection
# - docs/DECISIONS.md: if non-obvious choice made

# 3. Commit (small, logical)
git add -p
git commit -m "feat: mv-<app> — <specific change>"

# 4. Continue to next unfinished objective (AGENTS.md §10)
```

---

## 8. What NOT To Do

- ❌ Rewrite mature Linux backends (Thunar, rofi, xfwm4, NetworkManager, etc.)
- ❌ Add Electron / Java / persistent daemons
- ❌ Claim "IMPLEMENTED" for color-only or wrapper-only changes
- ❌ Add MacBook-specific config to generic profile
- ❌ Skip `check-sync.sh` or tests
- ❌ Invent Apple-proprietary assets (use reimplementation only)
- ❌ Break power baseline (TLP powersave, zram, no thermald/ananicy)
- ❌ Wait for hardware to do pre-hardware work