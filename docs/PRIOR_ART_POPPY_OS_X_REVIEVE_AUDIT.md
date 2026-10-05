# Prior-art audit: Poppy OS X Revieve

Date: 2026-10-06

## Executive conclusion

Poppy OS X Revieve is valuable prior art for **visual reference and selected theme ideas**, but the evidence currently available is insufficient to justify importing its code or assets into MavLinOS.

The project is explicitly a Mavericks-oriented GTK/GNOME theme, and the author's public notes show substantial attention to pixel-level GTK styling, fonts, menus, Nautilus sidebar styling, cursors, and GNOME Shell presentation. The same notes also explicitly acknowledge GTK/GNOME limitations, incomplete GNOME Shell work, unresolved browser-specific styling differences, and icon-pack quality/coverage problems.

Therefore the current decision is:

| Area | Decision |
|---|---|
| GTK visual measurements / styling reference | **USE AS REFERENCE** |
| Fonts / sizing assumptions | **USE AS REFERENCE** |
| GTK widgets and menu styling ideas | **USE AS REFERENCE** |
| Nautilus/sidebar visual ideas | **USE AS REFERENCE** |
| GNOME Shell code | **DO NOT IMPORT** |
| Nautilus integration | **DO NOT IMPORT** |
| Icon assets | **DO NOT IMPORT YET** |
| Cursor assets | **DO NOT IMPORT YET** |
| Wallpapers/assets of uncertain provenance | **DO NOT IMPORT YET** |
| Runtime components | **DO NOT IMPORT** |

## Source and provenance

Primary project referenced by the author's public project page:

- Repository: https://github.com/sziberov/Poppy-OS-X-Revieve
- Author/project page: https://www.xfce-look.org/member/370920/

The xfce-look project history identifies Poppy OS X Revieve as a GTK3/4 theme and separately identifies Poppy OS X Revieve icon themes and Poppy OS X cursors.

The public discussion also states that the author based portions of the GNOME Shell work on Gnome-OS-X-Dark-Shell and another OS X theme. This makes provenance especially important for any asset/code import.

## What the public evidence establishes

The author describes the project as a Mavericks-oriented Linux interface and explicitly targeted a close OS X 10.9 appearance. Public comments document work on:

- GTK3/GTK4 CSS styling;
- menus and menu bars;
- widget sizing;
- font family and font-size assumptions;
- Nautilus sidebar styling;
- GNOME Shell top panel/menu/dock styling;
- cursors;
- icons;
- browser-specific GTK notebook/tab limitations.

The project was still described as being in development in 2017, with the author explicitly stating that not all elements were themed. The author also noted that GTK/GNOME Shell imposed limitations on reproducing Mavericks details.

The icon project was separately described by the author as having incomplete resolution coverage, bugs, raster assets, and ongoing processing work.

## Comparison with MavLinOS

MavLinOS is deliberately not a GNOME Shell distribution. Its current architecture is Arch + Xfce/X11 + xfwm4 + Plank plus dedicated Mavericks application surfaces.

Consequently, importing Poppy's GNOME Shell implementation would introduce the wrong desktop architecture rather than solve a MavLinOS problem.

The useful overlap is primarily the **visual design knowledge**, not the runtime architecture.

MavLinOS should continue to own:

- xfwm4 decorations;
- Xfce panel/menu semantics;
- Plank/Dock integration;
- Mission Control;
- Finder/file-manager surface;
- Spotlight;
- Launchpad;
- Control Center;
- Notification Center;
- Quick Look;
- application-specific Mavericks UI.

## Quality assessment

### GTK widgets

**Classification: reusable reference.**

Poppy demonstrates detailed attention to widget geometry, menu heights, font sizing, status bars, entries, sidebars, and state styling. The author's comments show direct comparison against OS X screenshots and attempts to control exact dimensions.

However, the evidence does not establish that the old theme remains compatible with the current Arch/Xfce/GTK versions targeted by MavLinOS. It therefore should not be dropped into the current system wholesale.

### Fonts

**Classification: reusable reference.**

The author explicitly treated font selection and sizing as a requirement for achieving the intended visual proportions. This is useful for MavLinOS's visual regression work.

The correct integration path is to encode measured font choices and geometry in MavLinOS's own theme/configuration, not to import an opaque font bundle.

### GNOME Shell

**Classification: reject for direct integration.**

The implementation targets GNOME Shell and explicitly relied on GNOME Shell CSS constraints. MavLinOS does not use GNOME Shell.

The author's own notes also identify limitations in reproducing Mavericks effects through GNOME Shell CSS.

### Icons

**Classification: do not import yet.**

The author explicitly documented incomplete resolution coverage and raster/vector inconsistencies during development. More importantly, asset provenance/licensing must be established before redistribution.

A visually attractive icon is not sufficient evidence for legal or technical reuse.

### Cursors

**Classification: do not import yet.**

The cursor project is separately published. Before reuse, the exact repository license and asset provenance must be verified and attribution requirements recorded.

### Wallpapers

**Classification: do not import yet.**

MavLinOS should not redistribute Apple-derived artwork merely because it is useful for visual fidelity. Use original/clearly redistributable assets or document a user-supplied asset path.

## Energy/performance

No reliable runtime energy measurements were found in the public material reviewed for this audit.

Therefore the performance classification is **UNKNOWN**, not “efficient”.

Static observations:

- GTK themes themselves do not introduce a permanent daemon.
- CSS/images can affect rendering cost, memory footprint, and startup/resource loading.
- GNOME Shell-specific work is not directly applicable to MavLinOS.
- Asset size and format should be measured before importing large icon sets.

Required future benchmark if an asset/theme component is ever imported:

1. clean boot;
2. idle CPU and wakeups for 5 minutes;
3. resident memory;
4. GTK application launch latency;
5. panel/menu interaction latency;
6. Mission Control open/close latency;
7. display/GPU activity at idle;
8. comparison against the existing MavLinOS implementation.

## Legal/provenance gate

This audit deliberately does **not** classify Poppy assets as legally reusable merely because a public repository exists.

Before any direct import, verify:

1. repository license;
2. per-file/asset licensing where applicable;
3. upstream projects from which components were derived;
4. whether Apple/macOS artwork or other third-party assets are bundled;
5. attribution/notice requirements;
6. GPL compatibility where MavLinOS code is concerned.

Until these are established, imported Poppy assets must remain **DO NOT IMPORT YET**.

## Concrete MavLinOS actions

### Objective A — visual reference extraction

Create a small internal reference sheet for:

- menu height;
- menu font size/weight;
- widget corner radius;
- button geometry;
- scrollbar geometry;
- sidebar background;
- inactive/active state treatment;
- title-bar spacing.

Do this from evidence rather than copying CSS wholesale.

### Objective B — visual regression

Compare MavLinOS GTK applications against known Mavericks reference screenshots and the Poppy implementation where useful.

The Poppy theme is a **reference baseline**, not the authority.

### Objective C — provenance gate

Do not import Poppy assets until license and provenance are verified.

### Objective D — reject architecture duplication

Do not introduce GNOME Shell or Nautilus solely because Poppy implements them. MavLinOS's Xfce/X11 architecture is intentional.

## Final decision

Poppy OS X Revieve has already answered an important question: **MavLinOS should not independently rediscover every historical Mavericks GTK styling detail from scratch.**

However, it does **not** justify importing the project wholesale.

The correct strategy is:

**measure -> compare -> reproduce/adapt in MavLinOS -> regression-test -> only then consider direct asset reuse after provenance verification.**

This preserves the useful prior art while avoiding architectural coupling, stale GTK assumptions, unverified third-party assets, and unnecessary runtime overhead.

## External evidence

The author's public project page identifies the Poppy OS X Revieve GTK3/4 theme, icon theme, cursors, and related assets, and contains the author's own technical comments about GTK limitations, font requirements, Nautilus styling, GNOME Shell work, and icon quality. See:

- https://www.xfce-look.org/member/370920/
