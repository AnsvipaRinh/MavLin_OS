# LICENSES.md — License matrix for MavLinOS (OS-4a audit)

Generated 2026-10-02. All determinations are establishable facts; no legal claims beyond what can be verified from source headers, package metadata, and upstream project licenses.

## 1. Custom Packages (PKGBUILD license() fields)

| Package | license() | Source | Notes |
|---|---|---|---|
| mavericks-theme | GPL-3.0-or-later | packages/mavericks-theme/PKGBUILD:8 | Theme assets (icons, cursors, wallpapers, GTK CSS, xfwm4 theme, plank theme) |
| epiphany-mavericks-theme | GPL-3.0-or-later | packages/epiphany-mavericks-theme/PKGBUILD:8 | Epiphany-specific CSS/JS overrides; DEFERRED (not in ISO) |
| mavericks-apps | GPL-2.0-or-later (GPL2) | packages/mavericks-apps/PKGBUILD:8 | All mv-* Python/C apps, rofi themes, thunar-uca, keyboard shortcuts |
| macbook12-audio-driver | GPL-2.0-or-later | packages/macbook12-audio-driver/PKGBUILD:8 | DKMS wrapper for tanisperez/macbook12-audio-driver (GPL-2.0-or-later) |

## 2. Reused Backend Packages (per APPS.md)

| Backend | License | Source | Redistributable | Role in MavLinOS |
|---|---|---|---|---|
| rofi | MIT | APPS.md:125 | Yes | Spotlight/Launchpad/Mission Control UI |
| Thunar | GPL-2.0-or-later | APPS.md:121 | Yes | Finder backend (GVfs/GIO) |
| xfce4-panel | GPL-2.0-or-later | APPS.md:121 | Yes | Menu Bar |
| xfce4-settings | GPL-2.0-or-later | APPS.md:121 | Yes | System Settings backend |
| xfce4-notifyd | GPL-2.0-or-later | APPS.md:121 | Yes | Notification Center backend |
| xfce4-screenshooter | GPL-2.0-or-later | APPS.md:121 | Yes | Screenshot backend |
| xarchiver | GPL-2.0-or-later | APPS.md:121 | Yes | Archive Utility backend |
| mousepad | GPL-2.0-or-later | APPS.md:121 | Yes | TextEdit alternative (not primary) |
| galculator | GPL-2.0-or-later | APPS.md:121 | Yes | Calculator alternative (not primary) |
| gcolor3 | GPL-2.0-or-later | APPS.md:121 | Yes | Digital Color Meter handoff |
| gnome-disk-utility | GPL-2.0-or-later | APPS.md:121 | Yes | Disk Utility format/partition fallback |
| seahorse | GPL-2.0-or-later | APPS.md:121 | Yes | Keychain Access full GUI handoff |
| plocate | GPL-2.0-or-later | APPS.md:121 | Yes | Spotlight file index backend |
| trash-cli | GPL-2.0-or-later | APPS.md:121 | Yes | Trash restore backend |
| gtksourceview4 | GPL-2.0-or-later | APPS.md:121 | Yes | TextEdit/Notes/Reminders/Calendar editor widget |
| poppler-glib | LGPL-2.1-or-later | APPS.md:124 | Yes | Quick Look/Preview PDF rendering |
| GTK3 | LGPL-2.1-or-later | APPS.md:124 | Yes | UI toolkit |
| GLib/GIO | LGPL-2.1-or-later | APPS.md:124 | Yes | Core libraries |
| lollypop | GPL-3.0-or-later | APPS.md:124 | Yes | Music backend (MPRIS) |
| geary | GPL-3.0-or-later | APPS.md:124 | Yes | Mail backend |
| NetworkManager | GPL-2.0-or-later | (standard) | Yes | Control Center Wi-Fi |
| BlueZ | GPL-2.0-or-later | (standard) | Yes | Control Center Bluetooth |
| PipeWire | MIT | (standard) | Yes | Audio backend |
| UPower | GPL-2.0-or-later | (standard) | Yes | Battery/power data |
| libsecret | LGPL-2.1-or-later | (standard) | Yes | Keychain Access backend |
| gnome-keyring | GPL-2.0-or-later | (standard) | Yes | Secret daemon |
| restic | BSD-2-Clause | APPS.md:109 | Yes | Time Machine backend |
| btrfs-progs | GPL-2.0 | (standard) | Yes | Time Machine btrfs layer |
| xfce4-genmon-plugin | GPL-2.0-or-later | APPS.md:68 | Yes | Energy HUD panel host |
| evince | GPL-2.0-or-later | APPS.md:124 optdep | Yes | Preview full PDF reading (optdep) |
| gthumb | GPL-2.0-or-later | APPS.md:93 | Yes | Photos edit backend |
| xdotool | BSD-2-Clause | APPS.md:65 | Yes | Screenshot/Preview integration |
| ffmpeg | LGPL-2.1-or-later / GPL-2.0-or-later | APPS.md:65 | Yes | Quick Look media metadata, screen recording |
| localsend-bin | Apache-2.0 | APPS.md:125 | Yes | AirDrop receive GUI (AUR optdep, NOT in ISO) |
| localsend-cli-bin | AGPL-3.0-only | APPS.md:126 | Yes | AirDrop send CLI (AUR optdep, NOT in ISO) |
| espeak-ng | GPL-3.0-or-later | APPS.md:102 optdep | Yes | Dictionary pronunciation (optdep) |
| dictd | GPL-2.0-or-later | APPS.md:102 optdep | Yes | Dictionary WordNet (optdep) |
| gnome-font-viewer | GPL-2.0-or-later | APPS.md:97 optdep | Yes | Font Book handoff (optdep) |

## 3. Fonts

| Font | License | Source | Redistributable | Notes |
|---|---|---|---|---|
| gsfonts (URW Base 35) | GPL-2.0-only with font exception | Arch extra/gsfonts | Yes | Provides Z003 (URW Chancery L) — used by Stickies via fontconfig |
| Z003 (URW Chancery L) | GPL-2.0-only with font exception | gsfonts package | Yes | Free chancery/cursive face; mapped as `cursive` generic |
| Bradley Hand | Proprietary (Apple) | NOT included | NO | Referenced only as CSS fallback in mv-stickies (line 247); not shipped |
| Comic Sans MS | Proprietary (Microsoft) | NOT included | NO | Referenced only as CSS fallback in mv-stickies (line 247); not shipped |

## 4. Icons (mavericks-theme)

| Asset | Count | License Claimed | Redistributable | Verdict |
|---|---|---|---|---|
| Icon theme (Mavericks) | 457 icon files (PNG/SVG, 16–512px + scalable; verified by `git ls-files`) | GPL-3.0-or-later (PKGBUILD) | **YES (current tree)** | All 457 files are original/generic designs. The 3 formerly Apple-derived icons (`help-about`, `preferences-desktop-display`, `preferences-desktop-mouse` — 30 files across sizes) have been generic replacements since `522ab98`; the Apple-derived ORIGINALS were removed from the repo entirely (user decision D1, 2026-10-03, see §6/§8). Pre-`522ab98` history is purged by the publication rewrite (§8). |
| Cursor theme (Mavericks-Cursors) | 13 base + 30+ symlinks | GPL-3.0-or-later (PKGBUILD) | Yes | Original SVG/PNG sources; compiled to .cursor format |
| Wallpaper (mavericks-desktop.png) | 1 file (2304×1440) | GPL-3.0-or-later (PKGBUILD) | Yes | Original blue-green gradient; no Apple asset detected |

## 5. Copied/Adapted Code from Other Projects

| File | Origin | License | Attribution Present | Notes |
|---|---|---|---|---|
| mv-hud.c | Original (this project) | GPL-2.0-or-later (header line 6) | N/A | No external code copied |
| mv_desktop_cache.py | Original (this project) | GPL-2.0-or-later (implied by PKGBUILD) | N/A | No external code copied |
| rofi-mavericks.rasi | Original (this project) | MIT (compatible with rofi MIT) | N/A | Config only; no code |
| rofi-launchpad.rasi | Original (this project) | MIT (compatible with rofi MIT) | N/A | Config only; no code |
| rofi-mission-control.rasi | Original (this project) | MIT (compatible with rofi MIT) | N/A | Config only; no code |
| thunar-uca.xml | Original (this project) | GPL-2.0-or-later | N/A | Thunar custom actions |
| xfce4-keyboard-shortcuts.xml | Original (this project) | GPL-2.0-or-later | N/A | Xfce shortcut config |
| GTK3 theme SCSS partials | Original (this project) | GPL-3.0-or-later | N/A | No upstream theme code copied |

## 6. Questionable Assets — Disposition (REMOVED / REPLACE / KEEP)

**Update 2026-10-03 (user decision D1):** all three Apple-derived
assets below were REMOVED from the public tree (not merely isolated).
Isolation prevented installation but not redistribution; a public
repository publishes its whole tree, so the originals must not be
tracked at all. They are gone from the worktree; pre-`522ab98`
historical versions are purged by the publication rewrite (§8).
The theme UI uses the generic replacements that have been in place
since `522ab98` (30 files at the same icon names, all original).

| Asset (historical, removed) | Source | License | Redistributable? | Final disposition |
|---|---|---|---|---|
| `icons/scalable/apps/preferences-desktop-mouse.svg` (original) | mavericks-theme source (≤`522ab98`) | GPL-3.0-or-later (claimed) | **NO** — contains Apple logo path | **REMOVED (D1)** — Apple logo vector path ("Apple logo on mouse"); Apple trademark + copyright. Generic replacement ships since `522ab98` |
| `icons/scalable/apps/preferences-desktop-display.svg` (original) | mavericks-theme source (≤`522ab98`) | GPL-3.0-or-later (claimed) | **NO** — contains Apple logo path | **REMOVED (D1)** — Apple logo vector path ("Apple logo on back"); Apple trademark + copyright. Generic replacement ships since `522ab98` |
| `icons/scalable/apps/help-about.svg` (original) | mavericks-theme source (≤`522ab98`) | GPL-3.0-or-later (claimed) | **NO** — Apple shape + "Mac OS X 10.9 Mavericks" text | **REMOVED (D1)** — Apple logo silhouette + "Mac OS X"/"10.9 Mavericks" text; Apple trademark + copyright. Generic replacement ships since `522ab98` |
| `icons/scalable/apps/finder.svg` | mavericks-theme source | GPL-3.0-or-later (claimed) | **UNCERTAIN** — "happy mac style" face | **KEEP** (with monitoring) | "Finder face - classic Mavericks happy mac style" (line 43) is a generic smiling folder face; not the Apple Happy Mac trademark (distinct 1984-era icon). No Apple logo or text. Retained but documented. |
| All other icons (426 files) | mavericks-theme source | GPL-3.0-or-later (claimed) | **YES** | **KEEP** | No Apple logos, trademarks, or copyrighted artwork detected. Generic skeuomorphic designs (folder, calculator, calendar, etc.) |
| Cursor theme sources | mavericks-theme source | GPL-3.0-or-later (claimed) | **YES** | **KEEP** | Original SVG/PNG cursor designs; standard X11 cursor shapes |
| Wallpaper (mavericks-desktop.png) | mavericks-theme source | GPL-3.0-or-later (claimed) | **YES** | **KEEP** | Original gradient; no Apple asset detected |

## 7. Uncertain-but-Kept (with justification)

| Item | Uncertainty | Justification for Keeping |
|---|---|---|
| finder.svg "happy mac style" face | Visual similarity to vintage Apple Happy Mac icon (1984) | The Apple Happy Mac is a specific 1984 bitmap icon (12×12, 32×32). This SVG is a generic smiling folder face with different geometry, no rainbow colors, no "Mac" branding. Not substantially similar to the trademarked icon. |
| CSS font stack "Bradley Hand", "Comic Sans MS" | Referenced in mv-stickies CSS (line 247) | These are **fallback-only** font-family names in CSS. Neither font is shipped, installed, or depended upon. The fontconfig config maps `cursive` → Z003 (free). No redistribution of proprietary fonts occurs. |
| macbook12-audio-driver (tanisperez fork) | Upstream GPL but no formal release tags | PKGBUILD uses a specific commit (75884e2). Source is GPL-2.0-or-later per repo. DKMS builds from source at install time. Redistributable as source package. |

## 8. Removal Procedure for Apple-Derived Icons (D1, 2026-10-03)

The three Apple-derived originals were moved out of the theme source
tree in `522ab98` (generic replacements committed in the same commit)
and archived under `docs/isolated-assets/apple-derived/`. On
2026-10-03 (user decision D1) the archived originals were **deleted
from the tracked tree** (`git rm`): a public repository publishes its
entire tree, so "isolated but tracked" is not sufficient for
NON-redistributable material. The directory now holds only this
provenance note (`docs/isolated-assets/README.md`).

Current state of the icon names (all generic, no Apple artwork —
verified: 0 occurrences of the Apple vector strings in the current
theme):

```
packages/mavericks-theme/src/mavericks-theme/icons/{scalable,16x16,
22x22,24x24,32x32,48x48,64x64,128x128,256x256,512x512}/apps/
  ├── preferences-desktop-mouse.svg|.png      → GENERIC (since 522ab98)
  ├── preferences-desktop-display.svg|.png    → GENERIC (since 522ab98)
  └── help-about.svg|.png                     → GENERIC (since 522ab98)
```

The PKGBUILD `package()` function copies `icons/*` recursively; the
current tree contains only redistributable files, so no exclusion is
needed at build time.

**History purge (publication rewrite, see `docs/RELEASE_READINESS.md`
§3.1 and `scripts/contrib/publication-rewrite/`):** pre-`522ab98`
commits still contain the Apple-derived versions — the theme-tree
paths (SVG vector originals + 54 PNG rasterization blob IDs) and the
archived `docs/isolated-assets/apple-derived/` paths. The publication
rewrite removes them from all history via `--path ... --invert-paths`
(archived dir), `--replace-text` (Apple SVG vector strings in old
theme-tree SVGs) and `--strip-blobs-with-id` (pre-`522ab98` PNG
blobs). After the rewrite, the published history shows these icon
names only in their generic form (added at `522ab98`).

## 9. Gate Status

**GATE: GREEN** — All redistributable components have verified
OSI-approved licenses. Three Apple-derived trademark assets were
identified, isolated, and finally REMOVED from the public tree
(user decision D1, 2026-10-03); the theme ships only original
generic icons. No GPL/LGPL compliance issues (all source available,
no static linking of LGPL libs without shared object mechanism).
No AGPL network-service components in ISO (LocalSend CLI is AUR
optdep only).

## 10. Commits (this audit)

1. `docs: add LICENSES.md license matrix (OS-4a)`
2. `theme: isolate 3 Apple-derived SVG icons to docs/isolated-assets/`
3. `theme: add replacement generic icons for isolated assets`
4. `docs: update DECISIONS.md with OS-4a dispositions`
5. `git rm docs/isolated-assets/apple-derived/` (user decision D1,
   2026-10-03 — originals must not be published; provenance note
   remains in `docs/isolated-assets/README.md`; historical purge is
   part of the publication rewrite, §8)