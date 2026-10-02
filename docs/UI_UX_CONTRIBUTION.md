# UI/UX Contribution Guide — Mavericks Fidelity Axes

**Target: macOS 10.9 Mavericks (skeuomorphic). NOT modern macOS, NOT GNOME, NOT "pretty Linux".**

Every user-facing component is evaluated on four axes. An item is **COMPLETE** only when
all four pass pre-hardware. Color-only changes are explicitly **insufficient**.

---

## Axis 1 — Visual Design (Mavericks Visual Language)

| Element | Mavericks Spec | Implementation |
|---------|----------------|----------------|
| **Surfaces** | Grey/translucent, subtle gradients (`#f6f6f6→#eaeaea`), 1px borders `#c6c6c6` | GTK theme `_windows.scss` + `gtk.scss` shared tokens |
| **Toolbar** | 38px height, inset top sheen `rgba(255,255,255,0.8)`, button margin 0 2px / padding 4px 6px | `userChrome.css` (Firefox) + GTK `headerbar`/`toolbar` |
| **Buttons** | Traffic lights: close `#ff5c5c`, minimize `#4cd964`, zoom `#ffbd4c` with gradients + symbols (X/–/+) | xfwm4 theme (67 XPM assets) + GTK `.titlebutton` states |
| **Typography** | `"Lucida Grande", Cantarell, "Noto Sans", sans-serif`, 13px base | `userChrome.css:156-163` + GTK theme font stack |
| **Spacing** | Consistent 4px/8px/12px rhythm, 5px tab radius, 6px panel radius | Shared SCSS variables (`$space-1`..`$space-4`) |
| **Icons** | Skeuomorphic (leather, paper, metal, glass), 16-512px + SVG scalable | `packages/mavericks-theme/icons/` (28 core + 30+ symlinks) |
| **Cursors** | Classic Mac arrow, beach ball wait, I-beam, resize, hand | `packages/mavericks-theme/cursors/` (13 base + 30+ symlinks) |
| **Selection** | Blue `#6ea8e8` focus ring 3px `rgba(66,133,244,0.35)` | `userChrome.css:48-52` + GTK `:focus-visible` |
| **Shadows** | Subtle `rgba(0,0,0,0.12)` active, `rgba(0,0,0,0.06)` hover | Transitions: `opacity` + `background-color` 120ms only |

**Pass:** Visual coherence across Finder, Spotlight, Settings, Control Center, apps —
opening 3+ apps feels like one OS.

---

## Axis 2 — Interaction (Keyboard + Mouse)

| Behavior | Mavericks Spec | Implementation |
|----------|----------------|----------------|
| **Global shortcuts** | Super-layer: Spotlight (Super+Space), Launchpad (Super+L), Mission Control (Super+Tab), Finder (Super+Shift+F), Control Center (Super+Shift+C), New Folder (Ctrl+Alt+N) | `xfce4-keyboard-shortcuts.xml` + `mv-hotkeys` daemon-less |
| **App shortcuts** | Ctrl-layer (not Super): Ctrl+T/W/N/Q/F/G/L/R, Ctrl+Tab/Shift+Tab | Firefox native + documented in `docs/KEYBOARD.md` |
| **Keyboard nav** | Tab/Shift+Tab focus, Arrows navigate, Escape cancels, Enter default, Space activates | GTK native + per-app test assertions |
| **Context menus** | Right-click → Mavericks-styled menu (gray hover, separator, disabled state) | GTK theme `_menus.scss` + Firefox `userChrome.css:266-301` |
| **Drag-drop** | File operations, dock reorder, sidebar bookmarks | Thunar UCA + GTK native |
| **Window ops** | Minimize (genie to Dock), Maximize (zoom), Fullscreen (native), Close | xfwm4 + plank integration |

**Pass:** All shortcuts unique (no conflicts), all scripts exist (no orphans), keyboard nav works in every dialog/menu.

---

## Axis 3 — Desktop Integration

| Integration Point | Mavericks Spec | Implementation |
|-------------------|----------------|----------------|
| **Dock** | Running indicators, zoom, reflection, glassy theme, bottom auto-hide | plank + `dock1-settings` + `mavericks-theme` plank theme |
| **Menu Bar** | Top, translucent gradient, app menu left, system status right | xfce4-panel + `panel.css` + `xfce4-panel.xml` |
| **App Menu** | App name left, standard menus (File/Edit/View/Window/Help) | xfce4-panel `applicationsmenu` plugin |
| **Notifications** | Top-right, rounded, translucent, DND toggle, history viewer | xfce4-notifyd Mavericks theme + `mv-notification-center` |
| **File Chooser** | Mavericks-styled sidebar/path-bar/file-list/column-headers | GTK theme `_widgets.scss` filechooser selectors |
| **Dialogs** | Gradient background, shadow, button-box styling, alert icons | GTK theme `_windows.scss` dialog styling |
| **MIME/Trash** | Open With, Get Info, Put Back, Empty Trash, Eject | Thunar UCA + `trash-cli` + GVfs |
| **Quick Look** | Space preview (images/PDF/text/media), multi-file nav, fullscreen | `mv-quicklook` + Thunar UCA + Super+Shift+Space global |

**Pass:** No stock GTK dialog/file chooser/context menu visible in normal use.

---

## Axis 4 — Behavior (App + System)

| Behavior | Mavericks Spec | Implementation |
|----------|----------------|----------------|
| **Launch** | Single click (Dock/Launchpad), bounce feedback (plank), window appears | plank zoom + `.desktop` `StartupNotify=true` |
| **Quit** | Cmd+Q → Super+Q quits app (not just closes window) | `mv-power-ui` chooser + xfce4-session-logout |
| **Workspaces** | Mission Control overview, Super+Arrows switch, Super+Alt+Arrows move | xfwm4 workspaces + `mv-mission-control` / `skippy-xd` |
| **Search** | Spotlight: global, categorized, ranked, keyboard-driven, open action | rofi + `mv-spotlight` + `plocate` daily updatedb |
| **Settings** | Single coherent app (not disjoint dialogs), Mavericks sections | `mv-settings` launcher → backend tools |
| **Power UI** | Sleep/Restart/Shut Down/Log Out chooser, 60s countdown, battery footer | `mv-power-ui` (undecorated Mavericks alert) |

**Pass:** End-to-end user flows (launch → work → quit, search → open, settings → apply) feel coherent.

---

## Completion Criteria (from `docs/APPS.md` status machine)

| Status | Meaning |
|--------|---------|
| `NOT_STARTED` | No implementation |
| `AUDIT_REQUIRED` | Exists but not evaluated against 4 axes |
| `IN_PROGRESS` | Active work |
| `PARTIALLY_IMPLEMENTED` | **Some axes pass, gaps documented** — work remains |
| `IMPLEMENTED — HARDWARE VALIDATION REQUIRED` | All 4 axes pass pre-hardware; only HW pixel/perf validation remains |
| `VERIFIED` | HW validated |
| `HARDWARE_BLOCKED` | Cannot proceed without hardware (applespi, BCM43602, Cirrus, S3X resume) |
| `DEFERRED` | Explicitly postponed with reason |
| `EXCLUDED` | Out of scope (Contacts, TV, Podcasts, Siri, AirPlay, Chess, Game Center, Printer Discovery clone, Image Capture, Terminal replacement, account infra) |

**Do not promote** `PARTIALLY_IMPLEMENTED` → `IMPLEMENTED` without all four axes + HW_PENDING entry (if applicable).

---

## Historical Evidence Rule

Every visual/interaction claim must trace to **historical Mavericks 10.9 reference** (not modern macOS):

- Screenshots from 2013-era reviews (Ars Technica, Macworld, Siracusa)
- Apple HIG archives (developer.apple.com/design/human-interface-guidelines/osx/2013/)
- Reference implementations: "MacBuntu Mavericks transformation pack" (aesthetic reference only — code not copied)
- **No** macOS 11+ Big Sur / Monterey / Ventura references

Document the reference in `docs/DECISIONS.md` when adding new UI patterns.

---

## Checklist for PR Review

```markdown
- [ ] Visual: Uses shared Mavericks tokens (gradients, colors, spacing, typography)
- [ ] Interaction: Keyboard nav + shortcuts documented + tested
- [ ] Integration: Dock/Menu Bar/Notifications/File Chooser/Dialogs styled
- [ ] Behavior: Launch/quit/workspace/search/settings flows coherent
- [ ] HW_PENDING: Added to NEEDS_HARDWARE_TEST.md if hardware-dependent
- [ ] APPS.md: Status + gaps + next action updated
- [ ] DECISIONS.md: Non-obvious choices recorded
- [ ] check-sync.sh: 221 checks pass
- [ ] Tests: Relevant test-mv-*.py pass
```