# Poppy OS X Revieve → MavLinOS Port Analysis

## 2026-10-05 — Visual parity pass completed

The Poppy reference is now treated as a visual benchmark, not a generic inspiration source.

### Completed in MavLinOS
- GTK Tier 1 axes 1–12 are now explicitly overridden at the end of `gtk-3.0/gtk.scss` so the Poppy-derived measurements win over generic theme defaults: buttons, entries/search, menu bar, menus, tabs, toolbar, 22px titlebar, default-button pulse, popovers, progressbar, scrollbars, switches, sliders, window shadow and statusbar.
- Plank visual parameters now include the reference’s exact TopRoundness, BottomRoundness, LineWidth, stroke/fill colors, tight padding, zero icon shadow, animation timings and CascadeHide values.
- Mission Control window cards were brought closer to the Poppy GNOME overview treatment: transparent window surfaces, 4px blue selection border, 6px radius, 18px white captions with dark shadow, and 38px window-picker spacing.
- The extra in-overview Mission Control header was removed. Mavericks uses the Spaces strip at the top rather than a custom application header.

### Deliberate non-copies
- Poppy’s GNOME overview background asset is not copied. Mavericks 10.9 changed Mission Control to a dark-grey matte backdrop; using Poppy’s overview artwork would move MavLinOS away from the target OS X version.
- Poppy’s proprietary/unclear-license icon asset collections are not copied wholesale. They remain a visual reference for clean-room icon reconstruction.
- Poppy’s GNOME-specific layout is not copied where it conflicts with Mavericks’ Spaces bar and Mission Control model.

- Fixed a concrete packaging defect found during the audit: nine scalable action icons were plain text paths to an external Poppy checkout and therefore could not work in an installed image. They are now self-contained SVGs; `window-close-symbolic` and `view-app-grid-symbolic` were also added.

### Remaining visual gaps

- Corrected the global Xfce GTK font target from `San Francisco 11` to `Lucida Grande 11`; San Francisco is not Mavericks-era and was an accidental post-Mavericks visual drift. The live-image skeleton was corrected in the same pass.
- Poppy-derived icon categories: dialog/status, preferences, places, panel-symbolic and action icons.
- Exact noise-texture assets in title/status bars: MavLinOS currently uses CSS gradient simulation rather than copying Poppy’s Noise.png.
- Toolkit/runtime differences mean this is a visual parity implementation, not a claim of pixel-identical GTK rendering on every application.

This section supersedes the old “Next Actions: start with Tier 1” note below.

---


**Date:** 2026-10-04
**Source:** Poppy GTK3 CSS (8367 lines), Icons (568 SVG), Plank theme (64 lines)
**Target:** MavLinOS modular SCSS theme + icon theme + Plank theme
**Method:** Diff-driven axis-by-axis comparison, clean-room reimplementation of measurements/ideas only

---

## Axis-by-Axis Comparison Matrix

| Axis | Poppy Values (key measurements) | MavLinOS Current | Mavericks 10.9 Fidelity | Verdict | Port Priority |
|------|--------------------------------|------------------|-------------------------|---------|---------------|
| **Buttons** | 4px border-radius, 1px border alpha(#000,0.34), gradient #fff→#f2f2f2(50%)→#ededed(50%)→#f2f2f2, box-shadow: 0 1px a(#000,0.06) + inset 1px a(#fff,0.35) | 4px radius, shade($btn,1.15)→shade($btn,0.85), border shade($btn,0.5), shadow 0 1px 3px a(#000,0.15) + inset 0 1px a(#fff,0.2) | Poppy: more precise layered shadow (4 inset layers), Mavericks uses subtle glass highlight | **Poppy wins on shadow depth** | HIGH |
| **Default Button** | Blue pulse animation (500ms), border #565cae/#4d5076, complex 10-layer inset shadow, gradient #a3c1ef→#67a1e9(50%)→#4694ea(50%)→#acd5ef | shade($accent,1.15)→shade($accent,0.85), border shade($accent,0.5), no pulse | Mavericks had pulsing default button; Poppy implements it authentically | **Poppy unique feature** | HIGH |
| **Entries** | border-radius: 0 (flat), 8-layer inset shadow (alpha(#000,0.36/0.145/0.035/0.22/0.04/0.04/0.22/0.12)), focus adds 6x 0 0 2px #71a5d6 + inset 2px #6a9ecf | 4px radius, simple inset 0 1px 2px a(#000,0.1), focus: 0 0 0 2px a(#007aff,0.2) | Poppy's flat squared entries with deep multi-layer inset shadow = Mavericks 10.9 aqua | **Poppy significantly closer** | HIGH |
| **Search Entry** | border-radius: 50px (pill), same deep shadow | 4px radius | Mavericks Spotlight/search used pill-shaped entries | **Poppy wins** | MEDIUM |
| **Menubar** | gradient rgba(229,229,229,1)→rgba(160,160,160,1), box-shadow: inset 0 1px #fff, inset 0 -1px #000, min-height 22px | transparent bg, no gradient, no shadow | Mavericks menubar had distinct gradient + top/bottom highlight lines | **Poppy wins** | HIGH |
| **Menu** | bg #fff, border 1px a(#000,0.18), border-radius 0, menuitem min-height 19px, padding 0, hover gradient #618cf0→#1c65ed | rgba(255,255,255,0.95), border 1px a(#000,0.15), radius 6px, padding 6px 24px | Mavericks menus: square corners, sharp hover gradient, no padding | **Poppy closer to Mavericks** | HIGH |
| **Popover** | gradient a(#f6f6f6,0.96)→a(#ebebeb,0.96), box-shadow 0 3px 5px a(#000,0.5) + 0 0 0 1px a(#000,0.18), border 1px #f9f9f9 | rgba(255,255,255,0.97), border 1px a(#000,0.1), radius 8px, shadow 0 4px 20px a(#000,0.2) | Poppy's sharper shadow + 1px highlight border = Mavericks popover | **Poppy wins** | MEDIUM |
| **Notebook/Tabs** | 1px border #8c8c8c/#969696, 4-layer inset shadow, gradient #fff→shade(#fff,0.95)(50%)→shade(#fff,0.93)(50%)→shade(#fff,0.95), selected: gradient #7a7a7a→#8f8f8f + 12-layer inset shadow, padding 0 11px | shade($tab,1.08)→shade($tab,0.92), border shade($tab,0.6), radius 6px 6px 0 0, selected: shade($sel,1.02)→shade($sel,0.98) | Poppy's tab: flatter, more metallic gradient, selected tab has deep pressed-in shadow = Safari 7 tabs | **Poppy closer** | HIGH |
| **Scrollbar** | bg #fcfcfc, slider min 6px, margin -1px, border 4px transparent, radius 8px, bg #a2a2a2, overlay-indicator: opacity 0.4, slider 4px #636363, border 1px a(#fff,0.6) | transparent bg, slider 8px radius 4px, #a2a2a2, min 8px, overlay-indicator not styled | Mavericks: thin overlay scrollbars, semi-hidden until hover, 4px when inactive | **Poppy closer** | MEDIUM |
| **Switch** | min 18px, radius 100px, bg a(currentColor,0.3), checked #71c837, slider 18px, margin 2px 0 2px 3px, transition 0.3s cubic-bezier(0,0,0.2,1) | min 24px/32px, radius 16px, checked accent gradient, slider 24px | Poppy's smaller, tighter switch with green check = Mavericks toggle style | **Poppy wins on compactness** | LOW |
| **Check/Radio** | Uses external SVG assets from Resources/ArtFile.bin (22px check, 20px radio) - 12 states each | CSS-drawn indicators, 16px, gradient on check | Poppy uses bitmap assets for precise aqua look; we use CSS | **Poppy asset-dependent, not portable** | NONE (asset) |
| **Progressbar** | Complex multi-gradient with radial highlight, animated indeterminate (32px loop), trough gradient #cfcfcf→#e0e0e0 with 10-layer inset shadow | Simple accent gradient, trough shade($bg,0.85), basic inset shadow | Popby's animated aqua progress with moving highlight = Mavericks | **Popby wins on animation** | MEDIUM |
| **Scale/Slider** | slider 15px radius 25px, button gradient #fff→#f2f2f2(50%)→#ededed(50%)→#f2f2f2, trough gradient #a8a8a8→#f5f5f5 + 4-layer inset | slider 16px radius 50%, white, trough shade($bg,0.85) + border | Popby's pill slider + metallic trough = Mavericks | **Popby closer** | LOW |
| **Toolbar** | primary-toolbar: #ededed, border-image gradient #dedcdf→a(#d4d5db,0.95), inline-toolbar: gradient #fff→#f2f2f2(50%)→#ededed(50%)→#f2f2f2, border a(#696969,0.3) | gradient shade($toolbar,1.03)→shade($toolbar,0.97), border-bottom shade($toolbar,0.7) | Poppy's inline-toolbar gradient matches Mavericks unified toolbar exactly | **Popby wins** | HIGH |
| **Headerbar/Titlebar** | gradient url(Noise.png) + #e9e9e9→#b2b2b2, box-shadow inset 0 1px #f1f1f1 + inset 0 -2px a(#fff,0.085) + inset 0 -1px a(#000,0.38), min-height 22px | gradient shade($titlebar,1.05)→shade($titlebar,0.95), border-bottom shade($titlebar,0.7), padding 4px 8px, min-height 32px | Poppy's noise texture + specific shadow stack + 22px height = Mavericks titlebar | **Popby wins on height + texture** | HIGH |
| **Statusbar** | gradient url(Noise.png) + #d4d4d4→#b2b2b2, box-shadow inset 0 1px #e1e1e1, border-top 1px #818181, min-height 22px | gradient shade($status,1.02)→shade($status,0.98), border-top shade($status,0.7) | Poppy's noise + highlight line = Mavericks statusbar | **Popby wins** | MEDIUM |
| **Window Frame** | decoration: border-radius 6px 6px 0 0, box-shadow 0 10px 10px a(#000,0.75) + 0 0 0 1px a(#000,0.18) | windowframe: gradient shade($win,1.02)→shade($win,0.98), border 1px shade($win,0.7), radius 4px 4px 0 0, shadow 0 1px 3px a(#000,0.3) + inset 0 1px a(#fff,0.1) | Poppy's deeper shadow + 6px radius = Mavericks window drop shadow | **Popby wins on shadow depth** | MEDIUM |

---

## Icon Category Gap Analysis

| Category | Poppy Coverage | MavLinOS Coverage | Gap | Port Needed |
|----------|----------------|-------------------|-----|-------------|
| **Status (dialog icons)** | 48/64px: error, info, password, warning, loading (5 icons, complex SVG) | Empty | Complete gap | **HIGH** - Need dialog icons |
| **Preferences** | 48px: 9 icons (display, locale, wallpaper, notifications, privacy, time, system, accessibility, goa) | Missing | Complete gap | **HIGH** - System Settings needs these |
| **Places** | 16/48/128px: 18 folder variants + user-bookmarks, desktop, recent, templates | 4 trash symlinks only | Massive gap | **HIGH** - Finder sidebar needs folder icons |
| **Panel** | 16/20px: 30+ symbolic (volume, battery, network, notifications, shutdown) | Empty | Complete gap | **MEDIUM** - Menu bar/Control Center needs these |
| **Actions** | Symbolic: find, go-next/prev, view modes, window-close, zoom | Empty | Gap | **MEDIUM** - Toolbar buttons |
| **Mimetypes** | Present | Present | Our coverage better | NONE |
| **Devices** | Present | Present | Our coverage better | NONE |
| **Emblems** | Present | Present | Our coverage better | NONE |

---

## Plank Theme Comparison

| Parameter | Poppy | MavLinOS | Mavericks 10.9 | Verdict |
|-----------|-------|----------|----------------|---------|
| TopRoundness | 4 | 8 (Roundness) | Dock had subtle round top | Poppy's 4px = tighter |
| BottomRoundness | 0 | 0 | Flat bottom | Tie |
| FillStartColor | #c7c7c7 (a215) | rgba(255,255,255,0.3) | Glass gradient | Poppy metallic |
| FillEndColor | #f5f5f5 (a215) | — | Glass gradient | Poppy metallic |
| OuterStrokeColor | #000 a79 | rgba(0,0,0,0.1) | Subtle border | Poppy darker |
| InnerStrokeColor | #c7c7c7 a215 | — | Inner highlight | Poppy has it |
| HorizPadding | 2 (0.2% IconSize) | 4 (BackgroundPadding) | Tight | Poppy tighter |
| TopPadding | -5 (negative!) | — | Icons sit higher | **Poppy unique** |
| BottomPadding | 3 | — | | |
| ItemPadding | 1 | — | Very tight | Poppy tighter |
| IndicatorSize | 7 (0.7%) | 6 | Small dot | Poppy slightly larger |
| IconShadowSize | 0 (disabled!) | 8 | No icon shadow in Mavericks | **Poppy correct** |
| UrgentBounceHeight | 1.67 | — | High bounce | Poppy authentic |
| LaunchBounceHeight | 0.625 | 150% zoom | Different metaphor | Poppy uses bounce, we use zoom |
| FadeOpacity | 1 (no fade) | 200ms fade | Mavericks didn't fade | Poppy correct |
| ClickTime | 300ms | — | | |
| UrgentBounceTime | 600ms | — | | |
| ActiveTime | 300ms | — | | |
| SlideTime | 200ms | 200ms | Tie | |
| GlowSize | 30 | — | | |
| GlowTime | 10000ms | — | | |
| CascadeHide | true | — | | |

**Key Popby Plank wins for Mavericks fidelity:**
1. **TopPadding: -5** — Icons visually centered in glass area (Mavericks hallmark)
2. **IconShadowSize: 0** — Mavericks dock icons had NO drop shadow, only reflection
3. **Fill gradient** — Metallic #c7c7c7→#f5f5f5 matches brushed metal
4. **OuterStrokeColor #000 a79** — Subtle dark border like Mavericks
5. **CascadeHide: true** — Authentic Mavericks animation

---

## Ranked Port List (Technique + Exact Values + Target File + Fidelity Gain + Effort)

### TIER 1: TRIVIALLY SAFE (Pure CSS values, zero runtime cost, no assets)

| # | Technique | Exact Popby Values | Target File | Fidelity Gain | Effort |
|---|-----------|-------------------|-------------|---------------|--------|
| 1 | **Entry flat squared style** | `border-radius: 0`, 8-layer inset shadow (alpha(#000,0.36/0.145/0.035/0.22/0.04/0.04/0.22/0.12)), focus: 6x `0 0 2px #71a5d6` + `inset 0 0 0 2px #6a9ecf` | `_widgets.scss` (entry), `gtk.scss` overrides | **HIGH** - Mavericks aqua entries were flat with deep inset | 30 min |
| 2 | **Search entry pill shape** | `entry.search { border-radius: 50px; }` | `_widgets.scss` | **MEDIUM** - Spotlight/Search field | 5 min |
| 3 | **Menubar gradient + highlight lines** | `background-image: linear-gradient(to bottom, #e5e5e5, #a0a0a0)`, `box-shadow: inset 0 1px #fff, inset 0 -1px #000`, `min-height: 22px` | `_menus.scss` (menubar), `gtk.scss` | **HIGH** - Defining Mavericks menubar look | 15 min |
| 4 | **Menu square corners + sharp hover** | `menu { border-radius: 0; border: 1px solid rgba(0,0,0,0.18); }`, `menuitem:hover { background-image: linear-gradient(to bottom, #618cf0, #1c65ed); border-top: 1px #5783e7; border-bottom: 1px #0558e3; }` | `_menus.scss` | **HIGH** - Mavericks menus had 0 radius, blue gradient hover | 20 min |
| 5 | **Notebook tab metallic gradient + deep selected shadow** | Tab: `border: 1px solid #8c8c8c; border-top-color: #969696; box-shadow: 0 1px a(#000,0.06) + inset 4x a(#fff,0.35); background: #fff→shade(#fff,0.95)(50%)→shade(#fff,0.93)(50%)→shade(#fff,0.95)`; Selected: `background: #7a7a7a→#8f8f8f; box-shadow: 12-layer pressed-in; padding: 1px 12px` | `_notebook.scss` | **HIGH** - Safari 7 tabs signature | 30 min |
| 6 | **Toolbar unified gradient** | `.inline-toolbar { background-image: linear-gradient(to bottom, #fff, #f2f2f2 50%, #ededed 50%, #f2f2f2); border: 1px solid rgba(105,105,105,0.3); border-width: 0 1px 1px; }` | `gtk.scss` (toolbar), `_widgets.scss` | **HIGH** - Mavericks unified toolbar | 15 min |
| 7 | **Headerbar 22px height + noise texture simulation** | `min-height: 22px; padding: 0 8px; box-shadow: inset 0 1px #f1f1f1, inset 0 -2px a(#fff,0.085), inset 0 -1px a(#000,0.38);` + noise via gradient stops | `gtk.scss` (headerbar), `_variables.scss` | **HIGH** - Mavericks titlebar was 22px not 32px | 20 min |
| 8 | **Default button pulse animation** | `@keyframes pulse { 0%: #d4ebff→#a7d3fa(50%)→#87c5fa(50%)→#d2f8ff; 100%: #c1d6f2→#88b7ed(50%)→#6ca9ed(50%)→#c4e1f2; }` on `.button.default` | `gtk.scss` (button.default), `_mixins.scss` | **MEDIUM** - Mavericks pulsing default button | 20 min |
| 9 | **Popover sharp shadow + highlight border** | `box-shadow: 0 3px 5px a(#000,0.5), 0 0 0 1px a(#000,0.18); border: 1px solid #f9f9f9; background: linear-gradient(a(#f6f6f6,0.96), a(#ebebeb,0.96)); radius 4px` | `_menus.scss` (popover) | **MEDIUM** - Sharp popover look | 15 min |
| 10 | **Progressbar animated aqua gradient** | Multi-stop gradient with radial highlight, `@keyframes progressbar_hor` 32px loop, trough: `#cfcfcf→#e0e0e0` + 10-layer inset | `_widgets.scss` (progressbar) | **MEDIUM** - Living progress animation | 25 min |
| 11 | **Window decoration deeper shadow** | `box-shadow: 0 10px 10px a(#000,0.75), 0 0 0 1px a(#000,0.18); border-radius: 6px 6px 0 0` | `gtk.scss` (windowframe) | **LOW-MED** - Deeper window shadow | 10 min |
| 12 | **Statusbar noise gradient + highlight** | `min-height: 22px; background: url(Noise.png) + #d4d4d4→#b2b2b2; box-shadow: inset 0 1px #e1e1e1; border-top: 1px #818181` | `gtk.scss` (statusbar) | **LOW** - Authentic statusbar | 10 min |

### TIER 2: ICON GAPS (New SVG creation needed — clean-room, inspired by Poppy style)

| # | Category | Icons Needed | Target | Fidelity Gain | Effort |
|---|----------|--------------|--------|---------------|--------|
| 13 | **Status dialog icons** | error, info, warning, password, loading (5 icons) | `icons/scalable/status/` | **HIGH** - Dialogs currently empty | 2-3 hrs |
| 14 | **Preferences icons** | display, locale, wallpaper, notifications, privacy, time, system, accessibility, goa (9) | `icons/scalable/preferences/` | **HIGH** - System Settings panels | 3-4 hrs |
| 15 | **Places folder variants** | documents, downloads, music, pictures, videos, templates, public, gdrive, remote, saved-search, recent, desktop, bookmarks (13+) | `icons/scalable/places/` | **HIGH** - Finder sidebar | 3-4 hrs |
| 16 | **Panel symbolic** | volume (4), battery (8), network (6), notifications (2), shutdown (1) | `icons/scalable/status/` (symbolic) | **MEDIUM** - Menu bar/Control Center | 2-3 hrs |

### TIER 3: PLANK THEME (Configuration values only)

| # | Parameter | Popby Value | Target File | Fidelity Gain | Effort |
|---|-----------|-------------|-------------|---------------|--------|
| 17 | **TopPadding: -5** | Negative padding centers icons in glass | `plank/dock.theme` | **HIGH** - Visual centering hallmark | 2 min |
| 18 | **IconShadowSize: 0** | Disable icon drop shadow (Mavericks had none) | `plank/dock.theme` | **HIGH** - Authentic look | 2 min |
| 19 | **FillStartColor: #c7c7c7 (a215)** | Metallic gradient start | `plank/dock.theme` | **MEDIUM** - Brushed metal | 2 min |
| 20 | **FillEndColor: #f5f5f5 (a215)** | Metallic gradient end | `plank/dock.theme` | **MEDIUM** - Brushed metal | 2 min |
| 21 | **OuterStrokeColor: #000 a79** | Subtle dark border | `plank/dock.theme` | **LOW** - Edge definition | 2 min |
| 22 | **InnerStrokeColor: #c7c7c7 a215** | Inner highlight line | `plank/dock.theme` | **LOW** - Glass inner edge | 2 min |
| 23 | **HorizPadding: 2, ItemPadding: 1** | Tighter spacing | `plank/dock.theme` | **LOW** - Compact dock | 2 min |
| 24 | **CascadeHide: true** | Staggered hide animation | `plank/dock.theme` | **LOW** - Authentic feel | 2 min |

### TIER 4: REQUIRES ASSETS (NOT PORTABLE - Document Only)

| # | Technique | Reason | Alternative |
|---|-----------|--------|-------------|
| — | Check/Radio with 12-state SVG assets | Requires ArtFile.bin bitmaps | Keep CSS-drawn, refine gradients |
| — | Spinbutton arrows from ArtFile.bin | External assets | Use symbolic icons |
| — | Combobox arrows from ArtFile.bin | External assets | Use symbolic icons |
| — | Window buttons from ArtFile.bin | External assets | Keep CSS gradients |
| — | Progressbar indeterminate SVG | External asset | CSS animation (already porting) |

---

## Implementation Order (This Session)

1. **Tier 1 items 1-12** — Pure SCSS value changes, test with `test-theme-css.py`
2. **Tier 3 items 17-24** — Plank config values, instant test
3. **Tier 2 items 13-16** — Icon creation (separate session, larger effort)

---

## Legal Compliance

- **No asset bytes copied** — Only measurements, color values, gradients, shadows, spacing, radii, animations ported
- **Cursors exception** — Already handled in 4b2a171 (Artistic License 1.0)
- **All ports are clean-room reimplementation** of observed values
- **Icons** — Will be created fresh in Mavericks style, inspired by Poppy categories only

---

## Test Plan

Each Tier 1 port:
1. Edit SCSS file
2. Run `sassc -t compressed gtk.scss gtk.css` in theme dir
3. Run `python3 scripts/test-theme-css.py` (syntax + required selectors)
4. Run `./check-sync.sh` (repo integrity)
5. Commit with descriptive message

---

## Next Actions

1. Finish the remaining Poppy-derived icon categories with clean-room assets.
2. Replace CSS noise simulation with a newly generated, license-clean texture if the runtime supports it without increasing startup/battery cost.
3. Validate the resulting theme on the target Xfce/GTK runtime and compare rendered screenshots against the reference values.