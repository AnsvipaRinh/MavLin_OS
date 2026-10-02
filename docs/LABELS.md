# GitHub Labels for Mavericks Linux

> Labels are created on GitHub via `gh label create`. This document records the canonical label set and when each is applied.
> **Do NOT run these commands from the build environment** (no `gh` auth). They are documented for maintainers with repo access.

## Label Categories

### Priority
| Label | Color | Description | When Applied |
|-------|-------|-------------|--------------|
| `P0` | `#B60205` | Critical path - blocks desktop coherence | Finder, Spotlight, Launchpad, Mission Control, Control Center, Notification Center, Quick Look, Settings, Dock, Menu Bar, Window Mgmt, Global Dialogs, File Chooser, Context Menus, Shortcut Layer, Desktop/Session, Power UI |
| `P1` | `#D93F0B` | Important - application completeness | Activity Monitor, System Info, Disk Utility, Screenshot, Preview, TextEdit, Notes, Reminders, Calendar, Music, Photos, Voice Memos, Console, Keychain, Font Book, Color Meter, Stickies, Calculator, Dictionary |
| `P2` | `#FBCA04` | Future/Advanced - research phase | AirDrop, Time Machine UI, Automator/Shortcuts, Grapher, Migration Assistant, App Store, Software Update polish |

### Type
| Label | Color | Description | When Applied |
|-------|-------|-------------|--------------|
| `ui-discrepancy` | `#5319E7` | Visual difference from Mavericks 10.9 | Screenshots show wrong colors, spacing, icons, chrome, typography, states |
| `ux-discrepancy` | `#5319E7` | Behavior/interaction difference from Mavericks | Wrong keyboard nav, focus, gestures, shortcuts, animation timing, drag-drop |
| `missing-animation` | `#A2EEEF` | Mavericks animation absent/incorrect | Genie minimize, Mission Control zoom, Dock bounce, sheet slide, menu fade |
| `missing-interaction` | `#A2EEEF` | Mavericks interaction absent | Missing shortcut, gesture, menu item, context action, dock behavior |
| `backend-mismatch` | `#F9D0C4` | Linux backend ≠ macOS expectation | Sleep/wake, thermal, input, audio, display, storage, network divergence |
| `historical-behavior` | `#C2E0C6` | Documented Mavericks reference for impl | Authoritative source for how 10.9 actually behaved |
| `theme` | `#BF8700` | GTK/icon/cursor/wallpaper changes | CSS, SVG, icon theme, cursor theme, wallpaper, xfwm4 theme |
| `integration` | `#006B75` | Desktop integration gaps | Dock, menu bar, Finder, MIME, .desktop, notifications, file chooser |
| `performance` | `#1D76DB` | Runtime cost, energy, startup, memory | Benchmarks, wakeups, battery, CPU, RAM, cold/warm start |
| `security` | `#EE0701` | Privilege, perms, sandbox, secrets | Root, sudo, polkit, capabilities, keyring, CVE |
| `packaging` | `#0E8A16` | PKGBUILD, ISO, install, deps | Arch packages, mkarchiso, pacstrap, firstboot, profile select |
| `docs` | `#0075CA` | Documentation updates | APPS.md, PROGRESS.md, DECISIONS.md, HARDWARE.md, NEEDS_HARDWARE_TEST.md |
| `ci` | `#6F42C1` | GitHub Actions, gates, templates | Workflow files, PR template, issue templates, labels doc |
| `refactor` | `#8D6E63` | Code restructure without behavior change | Cleanup, deduplication, architecture improvement |

### Status
| Label | Color | Description | When Applied |
|-------|-------|-------------|--------------|
| `status:not-started` | `#E4E669` | No work begun | Initial triage |
| `status:audit-required` | `#FEF2C0` | Needs app-surface audit per §9/§13.5 | Before implementation |
| `status:in-progress` | `#FBCA04` | Active implementation | Work assigned/started |
| `status:partially-implemented` | `#D4C5F9` | Some DoD criteria met, gaps remain | Most common during dev |
| `status:implemented-hw-validation` | `#BFDADC` | All pre-hardware DoD met, needs real Mac | Ready for hardware test |
| `status:verified` | `#0E8A16` | Hardware validated on MacBook10,1 | Final state |
| `status:hardware-blocked` | `#E99695` | Cannot proceed without hardware | Applespi, BCM43602, Cirrus, S3X NVMe |
| `status:deferred` | `#C5C5C5` | Explicitly postponed with reason | Documented in DECISIONS.md |
| `status:excluded` | `#FFFFFF` | Out of scope (Contacts, TV, Podcasts, etc.) | Per §13.2 EXCLUDED list |

### Hardware Scope
| Label | Color | Description | When Applied |
|-------|-------|-------------|--------------|
| `hw:pre-hardware` | `#C2E0C6` | Fully implementable without Mac hardware | UI, theme, integration, packaging, most backend |
| `hw:validation-needed` | `#FBCA04` | Implemented, needs real hardware verify | Display calibration, HiDPI, thermal, power metrics |
| `hw:blocked` | `#E99695` | Cannot implement/test without hardware | Applespi keyboard/trackpad, Wi-Fi, audio, NVMe quirks |

## gh label create Commands

```bash
# Priority
gh label create "P0" --color "B60205" --description "Critical path - blocks desktop coherence"
gh label create "P1" --color "D93F0B" --description "Important - application completeness"
gh label create "P2" --color "FBCA04" --description "Future/Advanced - research phase"

# Type
gh label create "ui-discrepancy" --color "5319E7" --description "Visual difference from Mavericks 10.9"
gh label create "ux-discrepancy" --color "5319E7" --description "Behavior/interaction difference from Mavericks"
gh label create "missing-animation" --color "A2EEEF" --description "Mavericks animation absent/incorrect"
gh label create "missing-interaction" --color "A2EEEF" --description "Mavericks interaction absent"
gh label create "backend-mismatch" --color "F9D0C4" --description "Linux backend diverges from macOS expectation"
gh label create "historical-behavior" --color "C2E0C6" --description "Documented Mavericks reference for implementation"
gh label create "theme" --color "BF8700" --description "GTK/icon/cursor/wallpaper changes"
gh label create "integration" --color "006B75" --description "Desktop integration gaps"
gh label create "performance" --color "1D76DB" --description "Runtime cost, energy, startup, memory"
gh label create "security" --color "EE0701" --description "Privilege, perms, sandbox, secrets"
gh label create "packaging" --color "0E8A16" --description "PKGBUILD, ISO, install, deps"
gh label create "docs" --color "0075CA" --description "Documentation updates"
gh label create "ci" --color "6F42C1" --description "GitHub Actions, gates, templates"
gh label create "refactor" --color "8D6E63" --description "Code restructure without behavior change"

# Status
gh label create "status:not-started" --color "E4E669" --description "No work begun"
gh label create "status:audit-required" --color "FEF2C0" --description "Needs app-surface audit per §9/§13.5"
gh label create "status:in-progress" --color "FBCA04" --description "Active implementation"
gh label create "status:partially-implemented" --color "D4C5F9" --description "Some DoD criteria met, gaps remain"
gh label create "status:implemented-hw-validation" --color "BFDADC" --description "All pre-hardware DoD met, needs real Mac"
gh label create "status:verified" --color "0E8A16" --description "Hardware validated on MacBook10,1"
gh label create "status:hardware-blocked" --color "E99695" --description "Cannot proceed without hardware"
gh label create "status:deferred" --color "C5C5C5" --description "Explicitly postponed with reason"
gh label create "status:excluded" --color "FFFFFF" --description "Out of scope per §13.2 EXCLUDED list"

# Hardware Scope
gh label create "hw:pre-hardware" --color "C2E0C6" --description "Fully implementable without Mac hardware"
gh label create "hw:validation-needed" --color "FBCA04" --description "Implemented, needs real hardware verify"
gh label create "hw:blocked" --color "E99695" --description "Cannot implement/test without hardware"
```

## Label Application Rules

1. **Every issue/PR must have exactly one Priority label** (P0/P1/P2)
2. **Every issue must have at least one Type label** (ui-discrepancy, ux-discrepancy, etc.)
3. **Every issue must have exactly one Hardware Scope label** (hw:pre-hardware, hw:validation-needed, hw:blocked)
4. **Every issue/PR must have exactly one Status label** (updated as work progresses)
5. **PRs inherit labels from linked issues** + add `ci` if modifying workflows/templates
6. **Do not create ad-hoc labels** — propose additions via issue with `docs` label