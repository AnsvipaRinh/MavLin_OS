# Poppy OS X Revieve — Prior Art Audit

**Date:** 2026-10-04
**Source:** https://github.com/sziberov/Poppy-OS-X-Revieve
**Issue:** https://github.com/AnsvipaRinh/MavLin_OS/issues/2
**Auditor:** Build agent (static inspection only)

---

## 1. Executive Summary

Poppy OS X Revieve is a **theme-only** repository — it contains GTK3 CSS, icons, cursors, and a Plank dock theme. It has **no application code**, **no daemons**, **no scripts**, and **no desktop integration logic**. It is a visual layer designed for GNOME Shell + Ubuntu, not a standalone desktop environment.

**Headline verdict:** The repository is **not a competitor** to MavLinOS. It is a **visual reference** that can inform our GTK3 theme, but it offers **zero reusable code** for our application layer, desktop integration, or system services.

**Reuse potential:** LOW. The GTK3 CSS is comprehensive but targets GNOME Shell widgets (which we don't use). The icons are macOS-style but our icon theme is already more comprehensive. The cursors are Artistic License 1.0 (compatible with GPL-3.0-or-later). The Plank theme is minimal compared to ours.

---

## 2. Repository Inventory

### 2.1 Structure

```
Poppy-OS-X-Revieve/
├── README.md                          # Installation notes (GNOME extensions)
├── Brand Images/                      # Logo (SVG)
├── Cursors/
│   └── Poppy-OS-X-Cursors/
│       ├── LICENSE                    # Artistic License 1.0
│       └── source/                    # Cursor source files + make.sh scripts
├── Icons/
│   └── Poppy-OS-X-Revieve/
│       ├── index.theme
│       └── System/                    # 568 SVG + 34 PNG icons
│           ├── Status/                # Dialog icons (error, warning, etc.)
│           ├── Preferences/           # Settings icons
│           ├── Places/                # Folder/trash/home icons
│           ├── Panel/                 # Panel icons (16, 20px)
│           ├── Mimetypes/             # File type icons
│           └── ...
├── Required/
│   └── Fonts/                         # macOS-like fonts (proprietary?)
├── Screenshots/                       # Theme preview images
├── Theme/
│   └── Poppy OS X 1.2.5 Revieve Developer Preview 7/
│       ├── gtk-3.0/
│       │   ├── gtk.css               # 8367 lines, comprehensive
│       │   └── Resources/            # ArtFile.bin (GTK render assets)
│       ├── gtk-2.0/                  # Legacy GTK2 theme
│       ├── gtk-2.0-etoile/           # Legacy GTK2 variant
│       ├── metacity-1-etoile/        # Metacity window border
│       ├── gnome-shell/              # GNOME Shell theme
│       └── plank/
│           ├── dock.theme            # Plank dock theme
│           ├── hover.theme
│           └── ...
└── Presentation/                      # Marketing images
```

### 2.2 What Poppy Actually Implements

| Component | Implementation | Lines/Files | Quality |
|-----------|---------------|-------------|---------|
| GTK3 CSS | Comprehensive widget styling | 8367 lines | B (adapt-port) |
| GTK2 CSS | Legacy styling | ~2000 lines | D (obsolete) |
| Icons | macOS-style skeuomorphic | 568 SVG + 34 PNG | B (adapt-port) |
| Cursors | macOS-style cursors | 13 base + 30+ symlinks | A (reuse-as-is) |
| Plank theme | Dock styling | 64 lines | C (reference) |
| GNOME Shell | Shell theme | ~500 lines | D (wrong DE) |
| Metacity | Window borders | ~200 lines | D (wrong WM) |
| Fonts | Required fonts | Unknown | D (proprietary?) |
| Applications | **NONE** | 0 | N/A |
| Scripts | **NONE** | 0 | N/A |
| Daemons | **NONE** | 0 | N/A |

### 2.3 What Poppy Does NOT Implement

- No Finder/Spotlight/Launchpad/Mission Control equivalents
- No system settings application
- No control center / notification center
- No Quick Look / Preview
- No Activity Monitor / System Information
- No Disk Utility
- No TextEdit / Notes / Reminders / Calendar
- No Music / Photos / Voice Memos
- No Console / Keychain / Font Book
- No Calculator / Dictionary / Stickies
- No menu bar / Dock / window management logic
- No keyboard shortcut layer
- No file manager integration
- No MIME associations
- No desktop session behavior
- No power management UI
- No screenshots / screen recording
- No archive utility
- No drag-and-drop logic
- No context menu customization
- No dialog customization (beyond GTK defaults)
- No file chooser customization

---

## 3. Detailed Component Analysis

### 3.1 GTK3 CSS (8367 lines)

**Coverage:**
- Window frames, titlebars, headerbars
- Buttons (default, flat, suggested-action, destructive-action, OSD)
- Entries, spinbuttons, textviews
- Comboboxes
- Scales, sliders, progressbars
- Scrollbars
- Notebooks/tabs
- Menus, menubars, popovers
- Tooltips
- Sidebars, treeviews, iconviews
- Frames, separators, expanders
- Calendars
- Colorchoosers, fontchoosers, filechoosers
- Levelbars, switches, checks, radios
- Infobars
- OSD (on-screen display)
- CSD (client-side decoration)
- DND (drag-and-drop)

**Strengths:**
- Comprehensive widget coverage
- Consistent color palette (warm grays, blue accent)
- Proper state handling (hover, active, disabled, focus, backdrop)
- Skeuomorphic gradients and shadows
- macOS-like traffic light buttons (close/minimize/maximize)

**Weaknesses:**
- Targets GNOME Shell widgets (not Xfce)
- Uses GNOME-specific CSS properties
- No Xfce panel plugin styling
- No Thunar file manager styling
- No xfwm4 window manager styling
- Monolithic file (not modular like our SCSS)
- No build system (raw CSS, not SCSS)
- No variables/mixins (hardcoded colors)

**Verdict:** B (adapt-port) — useful as a reference for widget styling, but requires significant adaptation for Xfce.

### 3.2 Icons (568 SVG + 34 PNG)

**Coverage:**
- System status icons (error, warning, info, password, loading)
- Preferences icons (settings, display, sound, etc.)
- Places icons (trash, home, desktop, bookmarks)
- Panel icons (16, 20px)
- Mimetypes (file type icons)

**Strengths:**
- macOS-style skeuomorphic design
- SVG format (scalable)
- Consistent visual language

**Weaknesses:**
- Limited coverage (no app icons, no device icons, no action icons)
- No HiDPI variants (only 1x)
- No symbolic icons
- No cursor icons
- No emblem icons
- No category icons

**Verdict:** B (adapt-port) — useful for status/preferences icons, but our icon theme is already more comprehensive.

### 3.3 Cursors (13 base + 30+ symlinks)

**Coverage:**
- left_ptr (classic Mac arrow)
- hand1/hand2 (pointing hand)
- text/xterm (I-beam)
- crosshair/cross
- watch/wait (spinning beach ball)
- sb_h_double_arrow/ew-resize
- sb_v_double_arrow/ns-resize
- corner resizes (nwse, nesw, nw, ne, sw, se)
- move/all-scroll

**Strengths:**
- Proper hotspots
- 32px base with 16/24px variants
- Compiled to X11 .cursor format
- Artistic License 1.0 (GPL-compatible)

**Weaknesses:**
- Limited cursor set (no text cursors, no resize cursors for all directions)
- No animated cursors
- No HiDPI variants

**Verdict:** A (reuse-as-is) — high quality, GPL-compatible, can be used directly.

### 3.4 Plank Theme (64 lines)

**Coverage:**
- Dock background (gradient)
- Item padding, indicators
- Icon shadows
- Bounce animations
- Hide/show animations
- Urgent glow

**Strengths:**
- Clean, minimal configuration
- Proper Mavericks-style glass effect
- Smooth animations

**Weaknesses:**
- Minimal compared to our dock.theme
- No reflection effect
- No zoom effect
- No separator styling
- No Slingscold/Mission Control integration

**Verdict:** C (reference) — our Plank theme is already more comprehensive.

### 3.5 GNOME Shell Theme (~500 lines)

**Coverage:**
- Top panel
- Activities overview
- Dash
- Search
- Notifications
- OSD
- Window switcher

**Verdict:** D (do-not-reuse) — targets GNOME Shell, not Xfce. No value for MavLinOS.

### 3.6 Metacity Theme (~200 lines)

**Coverage:**
- Window borders
- Titlebar
- Buttons

**Verdict:** D (do-not-reuse) — targets Metacity, not xfwm4. No value for MavLinOS.

### 3.7 Fonts

**Status:** Unknown. The README mentions "Required/Fonts" but the repository does not contain font files. The installation notes say "You must install the fonts manually from `/Required/Fonts` directory" — but this directory is empty or contains proprietary fonts.

**Verdict:** D (do-not-reuse) — unclear provenance, potentially proprietary.

---

## 4. Comparison with MavLinOS

### 4.1 GTK3 Theme

| Aspect | Poppy | MavLinOS | Winner |
|--------|-------|----------|--------|
| File format | Raw CSS (8367 lines) | SCSS (modular, ~2000 lines) | MavLinOS |
| Variables | None (hardcoded) | Full variable system | MavLinOS |
| Mixins | None | Comprehensive mixin library | MavLinOS |
| Widget coverage | Comprehensive | Comprehensive | Tie |
| Xfce support | None | Full | MavLinOS |
| GNOME support | Full | None | Poppy |
| Build system | None | sassc | MavLinOS |
| Color palette | Warm grays, blue accent | Warm grays, blue accent | Tie |
| State handling | Full | Full | Tie |
| Skeuomorphism | Yes | Yes | Tie |

**Verdict:** MavLinOS is already better. Poppy's CSS is comprehensive but monolithic and GNOME-specific. Our SCSS is modular, maintainable, and Xfce-optimized.

### 4.2 Icons

| Aspect | Poppy | MavLinOS | Winner |
|--------|-------|----------|--------|
| Coverage | 568 SVG + 34 PNG | 28 core + 30+ symlinks | MavLinOS |
| App icons | None | 28 core app icons | MavLinOS |
| Device icons | None | 10+ device icons | MavLinOS |
| HiDPI | No | Yes (all sizes) | MavLinOS |
| Symbolic | No | Yes | MavLinOS |
| Cursors | No | Yes | MavLinOS |
| Emblems | No | Yes | MavLinOS |
| Actions | No | Yes | MavLinOS |
| Categories | No | Yes | MavLinOS |
| Filesystems | No | Yes | MavLinOS |
| Status | Yes (dialog icons) | Yes | Tie |
| Preferences | Yes | Yes | Tie |
| Places | Yes | Yes | Tie |
| Mimetypes | Yes | Yes | Tie |

**Verdict:** MavLinOS is already better. Poppy has status/preferences/places/mimetypes icons, but we already have those plus much more.

### 4.3 Cursors

| Aspect | Poppy | MavLinOS | Winner |
|--------|-------|----------|--------|
| Coverage | 13 base + 30+ symlinks | 13 base + 30+ symlinks | Tie |
| Quality | High | High | Tie |
| License | Artistic 1.0 | Unknown (custom) | Poppy |
| HiDPI | No | Yes (16/24/32px) | MavLinOS |
| Animated | No | No | Tie |

**Verdict:** Tie. Both have similar cursor sets. Poppy's license is clearer (Artistic 1.0), but ours has HiDPI variants.

### 4.4 Plank Theme

| Aspect | Poppy | MavLinOS | Winner |
|--------|-------|----------|--------|
| Lines | 64 | 57 | Tie |
| Reflection | No | Yes | MavLinOS |
| Zoom | No | Yes | MavLinOS |
| Separators | No | Yes | MavLinOS |
| Slingscold | No | Yes | MavLinOS |
| Mission Control | No | Yes | MavLinOS |
| Indicators | Yes | Yes | Tie |
| Animations | Yes | Yes | Tie |

**Verdict:** MavLinOS is already better. Our Plank theme has more features (reflection, zoom, separators, Slingscold, Mission Control).

### 4.5 Applications

| Aspect | Poppy | MavLinOS | Winner |
|--------|-------|----------|--------|
| Finder | None | Thunar + custom integration | MavLinOS |
| Spotlight | None | plocate + rofi + custom UI | MavLinOS |
| Launchpad | None | rofi + custom theme | MavLinOS |
| Mission Control | None | skippy-xd + custom integration | MavLinOS |
| System Settings | None | mv-settings (comprehensive) | MavLinOS |
| Control Center | None | mv-control (comprehensive) | MavLinOS |
| Notification Center | None | mv-notification-center | MavLinOS |
| Quick Look | None | mv-quicklook + Thunar integration | MavLinOS |
| Preview | None | mv-preview | MavLinOS |
| Screenshot | None | mv-shot | MavLinOS |
| Activity Monitor | None | mv-activity | MavLinOS |
| System Information | None | mv-about | MavLinOS |
| Disk Utility | None | mv-diskutil | MavLinOS |
| TextEdit | None | mv-textedit | MavLinOS |
| Notes | None | mv-notes | MavLinOS |
| Reminders | None | mv-reminders | MavLinOS |
| Calendar | None | mv-calendar | MavLinOS |
| Music | None | mv-music | MavLinOS |
| Photos | None | mv-photos | MavLinOS |
| Voice Memos | None | mv-voice | MavLinOS |
| Console | None | mv-console | MavLinOS |
| Keychain | None | mv-keychain | MavLinOS |
| Font Book | None | mv-fontbook | MavLinOS |
| Digital Color Meter | None | mv-colormeter | MavLinOS |
| Stickies | None | mv-stickies | MavLinOS |
| Calculator | None | mv-calculator | MavLinOS |
| Dictionary | None | mv-dictionary | MavLinOS |

**Verdict:** MavLinOS is vastly superior. Poppy has zero applications.

### 4.6 Desktop Integration

| Aspect | Poppy | MavLinOS | Winner |
|--------|-------|----------|--------|
| Menu bar | None | xfce4-panel + custom | MavLinOS |
| Dock | Plank theme only | Plank + full integration | MavLinOS |
| Window management | None | xfwm4 + custom | MavLinOS |
| Keyboard shortcuts | None | Comprehensive layer | MavLinOS |
| File manager | None | Thunar + custom | MavLinOS |
| MIME associations | None | Full | MavLinOS |
| Context menus | None | Thunar UCA | MavLinOS |
| Dialogs | None | mv_dialogs.py | MavLinOS |
| File chooser | None | GTK filechooser | MavLinOS |
| Notifications | None | xfce4-notifyd | MavLinOS |
| Power management | None | TLP + custom | MavLinOS |
| Session behavior | None | xfce4-session | MavLinOS |

**Verdict:** MavLinOS is vastly superior. Poppy has zero desktop integration.

---

## 5. Energy/Performance Analysis

### 5.1 Poppy

| Component | Runtime Cost | Energy Impact |
|-----------|-------------|---------------|
| GTK3 CSS | Negligible (static) | None |
| Icons | Negligible (static) | None |
| Cursors | Negligible (static) | None |
| Plank theme | Negligible (static) | None |
| GNOME Shell | High (if used) | High |
| Metacity | Low (if used) | Low |

**Total energy impact:** ZERO (theme-only, no runtime components)

### 5.2 MavLinOS

| Component | Runtime Cost | Energy Impact |
|-----------|-------------|---------------|
| GTK3 SCSS | Negligible (static) | None |
| Icons | Negligible (static) | None |
| Cursors | Negligible (static) | None |
| Plank theme | Negligible (static) | None |
| Applications | Low (one-shot) | Low |
| Desktop integration | Low (event-driven) | Low |

**Total energy impact:** LOW (all components are event-driven or one-shot)

### 5.3 Comparison

Both projects have negligible energy impact from their theme components. The energy consumption comes from the underlying desktop environment (GNOME Shell vs Xfce), not from the themes themselves.

**Verdict:** No energy advantage to either project. Both are theme-only with zero runtime cost.

---

## 6. Legal/Provenance Analysis

### 6.1 Repository License

**Status:** UNKNOWN

The repository does not contain a top-level LICENSE file. The only license file is `Cursors/Poppy-OS-X-Cursors/LICENSE`, which is Artistic License 1.0.

**Implication:** The GTK3 CSS, icons, and Plank theme have **no explicit license**. This means they are **all rights reserved** by default (copyright law).

**Resolution:** DO NOT IMPORT any Poppy assets without explicit permission from the copyright holder (sziberov).

### 6.2 Component Licenses

| Component | License | GPL-3.0 Compatible | Notes |
|-----------|---------|-------------------|-------|
| Cursors | Artistic License 1.0 | Yes | Explicit license |
| GTK3 CSS | Unknown | Unknown | No license file |
| Icons | Unknown | Unknown | No license file |
| Plank theme | Unknown | Unknown | No license file |
| GNOME Shell | Unknown | Unknown | No license file |
| Metacity | Unknown | Unknown | No license file |
| Fonts | Unknown | Unknown | Potentially proprietary |

### 6.3 Apple-Derived Assets

**Status:** UNKNOWN

The icons and cursors are "macOS-style" but it is unclear if they are:
- Original designs inspired by macOS
- Direct copies of Apple assets
- Modified versions of Apple assets

**Resolution:** DO NOT IMPORT any assets that may be Apple-derived without legal review.

### 6.4 Attribution Requirements

**Status:** UNKNOWN

Without explicit license terms, attribution requirements are unclear.

**Resolution:** DO NOT IMPORT any Poppy assets without explicit license clarification.

### 6.5 GPL-3.0-or-later Compatibility

| Component | Compatible | Notes |
|-----------|-----------|-------|
| Cursors | Yes | Artistic License 1.0 is GPL-compatible |
| GTK3 CSS | Unknown | No license |
| Icons | Unknown | No license |
| Plank theme | Unknown | No license |
| GNOME Shell | Unknown | No license |
| Metacity | Unknown | No license |
| Fonts | Unknown | Potentially proprietary |

---

## 7. Reuse Map

| Area | Poppy Impl | Quality | MavLinOS Impl | Decision | Reason | License | Energy | Effort |
|------|------------|---------|---------------|----------|--------|---------|--------|--------|
| GTK3 CSS | 8367 lines | B | SCSS modular | C (reference) | Ours is better | Unknown | None | N/A |
| Icons | 568 SVG | B | 28 core + symlinks | D (reject) | Ours is better | Unknown | None | N/A |
| Cursors | 13 base | A | 13 base | A (reuse) | GPL-compatible | Artistic 1.0 | None | Low |
| Plank theme | 64 lines | C | 57 lines | D (reject) | Ours is better | Unknown | None | N/A |
| GNOME Shell | ~500 lines | D | N/A | D (reject) | Wrong DE | Unknown | N/A | N/A |
| Metacity | ~200 lines | D | N/A | D (reject) | Wrong WM | Unknown | N/A | N/A |
| Fonts | Unknown | D | N/A | D (reject) | Unclear provenance | Unknown | N/A | N/A |
| Applications | None | N/A | 40+ apps | N/A | N/A | N/A | N/A | N/A |
| Desktop integration | None | N/A | Full | N/A | N/A | N/A | N/A | N/A |

---

## 8. Integration Objectives

### 8.1 Accepted Pieces

| Piece | Objective | Status | Effort |
|-------|-----------|--------|--------|
| Cursors | Import Poppy cursors as alternative | PENDING | Low |

**Integration steps:**
1. Verify Artistic License 1.0 compatibility with GPL-3.0-or-later
2. Import cursor files to `packages/mavericks-theme/src/mavericks-theme/cursors/`
3. Add attribution in `docs/APPS.md`
4. Test cursor rendering in X11
5. Commit

### 8.2 Rejected Pieces

| Piece | Reason |
|-------|--------|
| GTK3 CSS | Ours is better (modular, Xfce-optimized) |
| Icons | Ours is better (more comprehensive, HiDPI) |
| Plank theme | Ours is better (more features) |
| GNOME Shell | Wrong DE |
| Metacity | Wrong WM |
| Fonts | Unclear provenance |

### 8.3 Reference-Only Pieces

| Piece | Use |
|-------|-----|
| GTK3 CSS | Reference for widget styling ideas |
| Icons | Reference for status/preferences icon design |
| Plank theme | Reference for animation timing |

---

## 9. Open Questions

### 9.1 Legal

1. What is the license for Poppy's GTK3 CSS, icons, and Plank theme?
2. Are the icons and cursors original designs or Apple-derived?
3. Can we get explicit permission from sziberov to use the cursors?

### 9.2 Technical

1. Do the cursors work correctly in X11 (not just XWayland)?
2. Are the cursors compatible with our existing cursor theme?
3. Do we need to create a cursor theme index.theme file?

### 9.3 Hardware

1. N/A (theme-only, no hardware dependencies)

---

## 10. Conclusion

Poppy OS X Revieve is a **theme-only** repository with **no application code**, **no desktop integration**, and **no runtime components**. It is a **visual reference** for macOS-style GTK3 theming, but it offers **zero reusable code** for MavLinOS.

**Headline reuse wins:**
- Cursors (Artistic License 1.0, GPL-compatible)

**Headline rejects:**
- GTK3 CSS (ours is better)
- Icons (ours is better)
- Plank theme (ours is better)
- GNOME Shell (wrong DE)
- Metacity (wrong WM)
- Fonts (unclear provenance)

**Integration objective list:**
1. Import Poppy cursors as alternative (pending legal verification)

**Recommendation:** Do not invest significant effort in integrating Poppy assets. Focus on improving our own theme and applications instead.

---

## 11. References

- Poppy OS X Revieve: https://github.com/sziberov/Poppy-OS-X-Revieve
- MavLinOS: https://github.com/AnsvipaRinh/MavLin_OS
- Issue #2: https://github.com/AnsvipaRinh/MavLin_OS/issues/2
- Artistic License 1.0: https://opensource.org/licenses/Artistic-1.0
