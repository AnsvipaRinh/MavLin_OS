# Safari-Mavericks UX Specification

Target: macOS Mavericks (10.9) Safari 7-era UX, adapted for Firefox ESR on
MacBook10,1 (2304×1440 HiDPI, Intel HD 615). Implementation surface:
userChrome.css-compatible theme notes + Firefox preferences. NO engine fork.

---

## 1. Toolbar

**Mavericks Safari 7**: Single unified toolbar row. Back/Forward (left),
unified address+search field (center, ~60% width), Share button (right),
Downloads button (right), Show All Tabs (right, optional), Bookmarks Sidebar
toggle (optional, left of address field).

**Firefox mapping**:
- `browser.toolbars.bookmarks.visibility` = `"newtab"` — bookmarks bar only on New Tab (not persistent chrome clutter)
- Unified address/search: Firefox's default `urlbar` IS a unified field. No pref needed.
- Share button: `browser.sharepane` — disable via `browser.sharepane.enabled=false` (no native share integration on Linux)
- Downloads button: default in toolbar. Keep.
- Show All Tabs: `browser.tabs.tabmanager.enabled=false` — Mavericks has no tab manager button
- New Tab page: `browser.newtabpage.enabled=true` (Top Sites grid)

**userChrome.css notes**:
- Toolbar gradient: `linear-gradient(to bottom, #f8f8f8, #e8e8e8)` 1px bottom border `#c0c0c0`
- Height: 38px at 1x (76px @2x HiDPI) — `browser.uidensity=0` (normal)
- Buttons: 24×24px icons, 4px horizontal padding, no text labels

---

## 2. Tabs

**Mavericks Safari 7**: Tabs above toolbar, trapezoid shape, active tab lighter,
inactive tabs darker gradient. Tab height ~30px. Close button on hover (active tab only).
Favicon shown. Pinned tabs: favicon only, no close button.

**Firefox mapping**:
- `browser.tabs.drawInTitlebar=true` — tabs in title bar (compact vertical space)
- `browser.tabs.closeButtons=1` — close button on active tab only
- `browser.tabs.firefox-view=false` — disable Firefox View (not Mavericks)
- `browser.tabs.firefox-view-next=false` — disable Firefox View Next
- `browser.tabmanager.enabled=false` — no tab manager

**userChrome.css notes**:
- Tab shape: `border-radius: 4px 4px 0 0` + slight `transform: perspective(100px) rotateX(5deg)` for trapezoid illusion
- Active tab: `#f0f0f0` background, 1px border `#a0a0a0`
- Inactive tab: `linear-gradient(to bottom, #d0d0d0, #b8b8b8)`
- Tab height: 30px min
- Favicon: 16×16px, left padding 8px
- Close button: 16×16px, `opacity: 0` → `opacity: 1` on tab hover
- New tab button: `+` icon, 20×20px, right of last tab

---

## 3. Unified Address / Search

**Mavericks Safari 7**: Single field. Type URL → navigate. Type search → Google.
Security indicator (lock) left. Reload button right (spinning during load).
Reader button appears when available.

**Firefox mapping**: Default Firefox behavior already matches. No prefs needed.

**userChrome.css notes**:
- Field height: 24px, `border-radius: 4px`
- Background: `#ffffff`, border: `1px solid #a0a0a0`
- Focus: `border-color: #4a90d9`, `box-shadow: 0 0 3px rgba(74,144,217,0.5)`
- Font: 13px San Francisco / system-ui fallback
- Placeholder: `#888888`
- Reload button: circular arrow icon, animates during load

---

## 4. Bookmarks Bar + Sidebar

**Mavericks Safari 7**: Bookmarks bar below toolbar (optional). Bookmarks sidebar
in sidebar panel (toggle from View menu). Sidebar width ~200px. Bookmarks,
Reading List, Shared Links sections.

**Firefox mapping**:
- `browser.toolbars.bookmarks.visibility="newtab"` — bar visible only on new tab
- Bookmarks sidebar: `viewBookmarksSidebar` — default Ctrl+B (Mavericks: Cmd+Option+B)
- Reading List: not applicable (no iCloud sync) — omit
- Shared Links: not applicable — omit

**userChrome.css notes**:
- Bookmarks bar: height 22px, background `#f5f5f5`, bottom border `#d0d0d0`
- Sidebar: width 200px, background `#f8f8f8`, right border `#d0d0d0`
- Sidebar items: 28px height, 12px font, icon 16×16px

---

## 5. Top Sites

**Mavericks Safari 7**: Grid of website thumbnails (default 12, 4×3).
Rounded corners, site name below. Edit mode: drag to reorder, × to remove.
Dark background (not light).

**Firefox mapping**:
- `browser.newtabpage.enabled=true`
- `browser.newtabpage.activity-stream.showSponsored=false` — no sponsored tiles
- `browser.newtabpage.activity-stream.showSponsoredTopSites=false`
- `browser.newtabpage.activity-stream.feeds.topsites=true` — enable Top Sites section
- `browser.newtabpage.activity-stream.feeds.section.highlights=false` — no highlights (not Mavericks)

**userChrome.css notes**:
- Grid: 4 columns, gap 16px
- Thumbnail: 120×90px, `border-radius: 6px`, border `1px solid #333`
- Site name: 11px, white text, centered below thumbnail
- Background: `#1a1a1a` (dark)
- Hover: `transform: scale(1.05)`, `transition: transform 0.15s`
- Edit mode: `opacity: 0.9`, × button top-right of each tile

---

## 6. Downloads Popover

**Mavericks Safari 7**: Downloads button in toolbar. Popover shows recent downloads
with progress bars. Completed items show file icon + name + path. "Clear" button.
"Show in Finder" option.

**Firefox mapping**:
- Downloads button: default in toolbar
- Downloads panel: default behavior (bottom-right popover)
- `browser.download.useDownloadDir=true` — save to default dir without asking (Mavericks behavior)
- `browser.download.start_downloads_in_tmp_dir=false` — don't use tmp dir

**userChrome.css notes**:
- Downloads button: downward arrow icon, 24×24px
- Popover: `border-radius: 8px`, `box-shadow: 0 4px 12px rgba(0,0,0,0.3)`
- Progress bar: 4px height, `border-radius: 2px`, fill `#4a90d9`
- File item: 40px height, icon 24×24px, name 13px, path 11px #666

---

## 7. History

**Mavericks Safari 7**: History menu (menu bar) + History sidebar. Grouped by date.
Search field. "Clear History" option.

**Firefox mapping**:
- History sidebar: `viewHistorySidebar` — default Ctrl+H
- History menu: default in Library menu
- `places.history.enabled=true` — ensure history recording on

**userChrome.css notes**:
- Sidebar: same style as bookmarks sidebar
- Date headers: bold, 11px, `#666`, uppercase
- Items: 28px height, favicon 16×16px + title 13px + URL 11px #888

---

## 8. Find Bar

**Mavericks Safari 7**: Bottom of page, slides up. Search field, "3 of 12" counter,
up/down arrows, "Done" button. Highlight all matches in yellow.

**Firefox mapping**:
- Find bar: default bottom-positioned
- `findbar.highlightAll=true` — highlight all matches
- `findbar.findAgainOnScroll=false` — don't re-find on scroll

**userChrome.css notes**:
- Find bar: height 32px, background `#f0f0f0`, top border `#c0c0c0`
- Search field: 24px height, `border-radius: 4px`
- Counter: 11px, `#666`
- Highlight: `background-color: #ff9632`, `color: #000`

---

## 9. Private Browsing

**Mavericks Safari 7**: "File → New Private Window". Dark chrome. No history saved.
Masked toolbar. Purple/blue tint.

**Firefox mapping**:
- Private window: default Ctrl+Shift+P
- `browser.privatebrowsing.autostart=false` — not always-on
- `privacy.trackingprotection.enabled=true` — already in baseline

**userChrome.css notes**:
- Private window toolbar: `linear-gradient(to bottom, #2a2a2a, #1a1a1a)`
- URL bar: dark background `#2a2a2a`, text `#e0e0e0`
- New tab page: dark background `#1a1a1a`
- Purple accent: `#8e44ad` for links/highlights

---

## 10. Context Menus

**Mavericks Safari 7**: Right-click on link → "Open Link in New Tab", "Open Link
in New Window", "Download Linked File", "Add to Reading List", "Copy Link".
Right-click on image → "Save Image to Downloads", "Copy Image", "Open Image
in New Tab". Right-click on page → "Back", "Reload", "Save As", "Print",
"Inspect Element".

**Firefox mapping**: Default Firefox context menus are close to Mavericks.
No prefs needed for basic behavior. uBO adds its own entries (acceptable).

**userChrome.css notes**:
- Menu: `border-radius: 4px`, `box-shadow: 0 2px 8px rgba(0,0,0,0.2)`
- Item: 26px height, 13px font
- Hover: `background: #4a90d9`, `color: #fff`
- Separator: 1px `#d0d0d0`

---

## 11. Keyboard (Cmd-layer mapping)

Maps to existing KEYBOARD.md Super (Cmd) bindings:

| Safari Action | macOS Shortcut | Linux/Super Equivalent | Status |
|---|---|---|---|
| New Tab | Cmd+T | Ctrl+T (app-level) | App-level — not globally bound |
| Close Tab | Cmd+W | Ctrl+W (app-level) | App-level — not globally bound |
| Next Tab | Cmd+Option+Right | Ctrl+Tab (app-level) | App-level — not globally bound |
| Previous Tab | Cmd+Option+Left | Ctrl+Shift+Tab (app-level) | App-level — not globally bound |
| New Window | Cmd+N | Ctrl+N (app-level) | App-level — not globally bound |
| New Private Window | Cmd+Shift+N | Ctrl+Shift+N (app-level) | App-level — not globally bound |
| Find | Cmd+F | Ctrl+F (app-level) | App-level — not globally bound |
| Find Again | Cmd+G | Ctrl+G (app-level) | App-level — not globally bound |
| Address Field | Cmd+L | Ctrl+L (app-level) | App-level — not globally bound |
| Reload | Cmd+R | Ctrl+R (app-level) | App-level — not globally bound |
| Stop | Cmd+. | Escape (app-level) | App-level — not globally bound |
| Downloads | Cmd+Option+L | Ctrl+J (app-level) | App-level — not globally bound |
| Bookmarks Sidebar | Cmd+Option+B | Ctrl+B (app-level) | App-level — not globally bound |
| History | Cmd+Y | Ctrl+H (app-level) | App-level — not globally bound |
| Zoom In | Cmd+Plus | Ctrl+Plus (app-level) | App-level — not globally bound |
| Zoom Out | Cmd+Minus | Ctrl+Minus (app-level) | App-level — not globally bound |
| Zoom Reset | Cmd+0 | Ctrl+0 (app-level) | App-level — not globally bound |
| Toggle Toolbar | Cmd+Option+T | — | Not applicable on Linux |
| Reader View | Cmd+Shift+R | — | Not applicable on Linux |

**Resolution**: Firefox app-level shortcuts use Ctrl layer (not Super) to avoid
global conflicts. Super layer remains for global desktop actions (Spotlight,
Launchpad, Finder, etc.). This is the correct Mavericks-like separation: app
shortcuts don't steal global shortcuts.

**Cmd-layer collision fixes (2026-09-28)**: Three global Super bindings conflicted
with Firefox app-level shortcuts and were rebound:
- Super+C → mv-control (Control Center) → **Super+Shift+C** (was killing Cmd+C = Copy)
- Super+F → thunar (Finder) → **Super+Shift+F** (was killing Cmd+F = Find)
- Super+N → mv-newfolder → **Ctrl+Alt+N** (was killing Cmd+N = New Window)

Remaining Cmd-layer shortcuts (Cmd+T/W/Q/1..9/[/]) are app-level and handled
by Firefox internally with Ctrl equivalents — NOT globally bound to avoid
breaking other apps. See docs/KEYBOARD.md for the full mapping.

---

## 12. Dialogs

**Mavericks Safari 7**: Sheet-style dialogs slide down from toolbar. Not modal
Windows-style dialogs. Rounded corners, grey background, default button blue.

**Firefox mapping**: Firefox on Linux uses GTK dialogs. Theme via GTK3 CSS
 Mavericks theme (already implemented in mavericks-theme package).

**userChrome.css notes**:
- Sheet animation: `transform: translateY(-20px)` → `translateY(0)` over 150ms
- Background: `#f0f0f0`
- Border-radius: 8px
- Default button: `background: #4a90d9`, `color: #fff`, `border-radius: 4px`

---

## 13. Typography / Spacing / Icons / Loading States

**Typography**:
- UI font: San Francisco (macOS) → system-ui / Cantarell fallback on Linux
- Base size: 13px
- Small: 11px (URLs, metadata)
- Large: 15px (tab titles)
- Line height: 1.4

**Spacing**:
- Toolbar height: 38px
- Tab height: 30px
- Bookmarks bar: 22px
- Button padding: 4px 8px
- Field padding: 4px 8px
- Icon size: 16×16px (toolbar), 24×24px (menu bar)

**Icons**: Pre-flat era. Glossy/gradient icons. Not monolithic SF Symbols.
Use Faenza/gnome-icon-theme-style icons (already in mavericks-theme).

**Loading States**:
- Tab throbber: circular spinner, top-left of tab
- URL bar: progress bar at bottom of field (thin, blue)
- Status bar: "Connecting to..." / "Transferring data from..." (bottom-left)
- Page: blank white until first paint, then content

---

## 14. Implementation Surface Summary

### Active Firefox prefs (in user.js, verified against current ESR):
```
browser.uidensity=0
browser.tabs.drawInTitlebar=true
browser.tabs.firefox-view=false
browser.newtabpage.enabled=true
browser.newtabpage.activity-stream.showSponsored=false
browser.newtabpage.activity-stream.showSponsoredTopSites=false
browser.newtabpage.activity-stream.feeds.topsites=true
browser.newtabpage.activity-stream.feeds.section.highlights=false
browser.toolbars.bookmarks.visibility="newtab"
browser.download.useDownloadDir=true
browser.download.start_downloads_in_tmp_dir=false
places.history.enabled=true
findbar.highlightAll=true
findbar.findAgainOnScroll=false
```

### Removed dead prefs (spec-claimed but non-functional in current ESR):
```
// browser.theme.color_scheme=1       — NOT a real pref. Light theme is Linux default.
// browser.tabs.closeButtons=1         — removed in FF89 (Proton). Close button on all tabs now.
// browser.tabs.firefox-view-next=false — NOT a real pref. Firefox View = browser.tabs.firefox-view only.
// browser.tabmanager.enabled=false   — removed in FF45. Tab manager no longer exists.
// browser.sharepane.enabled=false     — removed in FF95. Share button no longer exists.
```

### Commented-out proposals (uncertain, not yet active):
```
// user_pref("browser.tabs.unloadOnLowMemory", false);  // E-MEM: test on 8GB
// user_pref("dom.ipc.processCount", 6);                // E-PROC: test 4 vs 6 vs 8
```

### userChrome.css (theme-only, not engine fork):
- **STATUS: NOT IMPLEMENTED.** No userChrome.css exists anywhere in the repository.
- The mavericks-theme package contains GTK3 CSS for native GTK apps (Thunar, etc.),
  NOT Firefox chrome CSS. Firefox uses engine-rendered chrome (userChrome.css),
  which is a separate system from GTK3 CSS.
- All "userChrome.css notes" in sections 1-13 above are spec-only prose with zero
  implementation behind them. They describe intended CSS that was never written.
- Implementing userChrome.css is a feature-track task, not an audit fix.

---

## 15. Hardware Validation Required

- Actual HiDPI rendering at 2304×1440 (2x scaling)
- VAAPI video decode performance (H.264/VP9/HEVC)
- AV1 software decode cost (expected high on Core M)
- WebRender vs basic compositor on HD 615
- Memory pressure with 6 content processes on 8-16GB RAM
- Tab thrashing behavior with many tabs on fanless Core M

---

## 16. Audit Appendix (2026-09-28) — Fidelity Classification

Forensic audit of actual implementation vs spec claims. Evidence: file:line inspection
of user.js, policies.json, mavericks-theme GTK CSS, KEYBOARD.md. No userChrome.css exists.

### 16.1 Fidelity Table

| Element | Spec Claim | Actual Implementation | Class |
|---|---|---|---|
| Toolbar layout | Unified row, 38px, gradient | Stock Firefox toolbar. No userChrome.css. | Firefox-native |
| Unified address/search | Single field | Firefox default (already unified). | Firefox-native (matches by default) |
| Tabs shape | Trapezoid, gradient, 30px | Stock Firefox tabs. drawInTitlebar=true only. | Firefox-native |
| Tabs position | Above toolbar | drawInTitlebar=true (in titlebar). | Visually-adapted |
| Close button | Active tab only | Dead pref (FF89+). Shows on all tabs. | Firefox-native (spec-only) |
| Bookmarks bar | Below toolbar, optional | visibility="newtab" (only on new tab). | Visually-adapted |
| Sidebar | 200px, bookmarks/reading list | Stock Firefox sidebar. No styling. | Firefox-native |
| Downloads UI | Popover, progress bars | Stock Firefox downloads panel. | Firefox-native |
| Top Sites | 4×3 grid, dark bg, thumbnails | activity-stream prefs enable/disable sections. No custom grid CSS. | Firefox-native |
| Find bar | Bottom, 32px, yellow highlight | findbar.highlightAll=true. Stock styling. | Visually-adapted |
| Private browsing | Dark chrome, purple tint | No implementation. Stock private window. | Firefox-native (spec-only) |
| Context menus | Mavericks-style hover/selection | Stock Firefox context menus. | Firefox-native (spec-only) |
| Dialogs | Sheet-style, slide-down | GTK3 dialogs themed by mavericks-theme GTK CSS. | Visually-adapted (GTK layer) |
| Typography | San Francisco, 13px base | font prefs set but San Francisco/Menlo unavailable on Linux. Falls back to Cantarell. | Firefox-native (fallback) |
| Icons | Pre-flat, glossy | Stock Firefox icons. | Firefox-native |
| Keyboard (Cmd-layer) | Super=Cmd mapping | Ctrl-layer app-level (correct for Linux). Super layer for global actions. | Intentionally-different (correct) |
| Loading states | Tab throbber, URL progress | Stock Firefox loading indicators. | Firefox-native |
| HiDPI | 38px@1x, 76px@2x | uidensity=0 (normal). No resolution-aware CSS. | Firefox-native (1x assumption) |

### 16.2 Spec-Only Items (Zero Implementation)

All "userChrome.css notes" in sections 1-13 are spec-only prose:
- Toolbar gradient + 38px height
- Tab trapezoid shape + gradient + 30px height
- Top Sites grid styling (4×3, dark bg, thumbnails, hover scale)
- Downloads popover styling
- Find bar styling (32px, yellow highlight)
- Private browsing dark chrome
- Context menu styling
- Sheet dialog animation
- Typography/spacing/icon sizing

These describe CSS that was never written. No userChrome.css file exists in the
repository or in the mavericks-theme package.

### 16.3 Dead Prefs Removed (P1 Fix)

5 prefs in user.js were spec-claimed but non-functional in current Firefox ESR:
- `browser.theme.color_scheme` — not a real pref
- `browser.tabs.closeButtons` — removed in FF89
- `browser.tabs.firefox-view-next` — not a real pref
- `browser.tabmanager.enabled` — removed in FF45
- `browser.sharepane.enabled` — removed in FF95

Removed from user.js with explanatory comments. Spec updated to match.

### 16.4 HiDPI Assessment

- `browser.uidensity=0` (normal density) is the only HiDPI-relevant pref. Correct choice.
- No resolution-aware CSS exists (no userChrome.css).
- No icon size overrides for HiDPI.
- No toolbar density adjustments for HiDPI.
- Firefox renders at 1x and relies on OS scaling. At 2304×1440 with 2x scaling,
  Firefox UI will be scaled by the compositor. This is functional but not
  pixel-perfect Mavericks fidelity.
- Tracked in NEEDS_HARDWARE_TEST.md: "HiDPI rendering of Firefox UI (uidensity=0, 2x scaling)"

### 16.5 Verdict

Firefox chrome is **Firefox-native** for all visual elements. The only Mavericks
adaptation is: (1) behavioral prefs that disable non-Mavericks features (Firefox View,
tab manager, sponsored tiles), (2) bookmarks bar visibility, (3) find bar highlight,
(4) GTK3 dialog theming via mavericks-theme. The entire visual layer (userChrome.css)
is absent. This is the largest known gap in the Safari-Mavericks fidelity track.
