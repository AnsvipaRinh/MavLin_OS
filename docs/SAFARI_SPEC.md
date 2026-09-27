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
| New Tab | Cmd+T | Super+T | NOT BOUND (see KEYBOARD.md) |
| Close Tab | Cmd+W | Super+W | NOT BOUND |
| Next Tab | Cmd+Option+Right | Super+Alt+Right | CONFLICT (workspace) |
| Previous Tab | Cmd+Option+Left | Super+Alt+Left | CONFLICT (workspace) |
| New Window | Cmd+N | Super+N | CONFLICT (New Folder) |
| New Private Window | Cmd+Shift+N | Super+Shift+N | CONFLICT (New Folder Home) |
| Find | Cmd+F | Super+F | CONFLICT (Finder) |
| Find Again | Cmd+G | — | app-level only |
| Address Field | Cmd+L | — | app-level only |
| Reload | Cmd+R | — | app-level only |
| Stop | Cmd+. | — | app-level only |
| Downloads | Cmd+Option+L | — | app-level only |
| Bookmarks Sidebar | Cmd+Option+B | — | app-level only |
| History | Cmd+Y | — | app-level only |
| Zoom In | Cmd+Plus | — | app-level only |
| Zoom Out | Cmd+Minus | — | app-level only |
| Zoom Reset | Cmd+0 | — | app-level only |
| Toggle Toolbar | Cmd+Option+T | — | app-level only |
| Reader View | Cmd+Shift+R | — | app-level only |

**Resolution**: Firefox app-level shortcuts use Ctrl layer (not Super) to avoid
global conflicts. Super layer remains for global desktop actions (Spotlight,
Launchpad, Finder, etc.). This is the correct Mavericks-like separation: app
shortcuts don't steal global shortcuts.

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

### Active Firefox prefs (in user.js):
```
browser.uidensity=0
browser.theme.color_scheme=1
browser.tabs.drawInTitlebar=true
browser.tabs.closeButtons=1
browser.tabs.firefox-view=false
browser.tabs.firefox-view-next=false
browser.tabmanager.enabled=false
browser.newtabpage.enabled=true
browser.newtabpage.activity-stream.showSponsored=false
browser.newtabpage.activity-stream.showSponsoredTopSites=false
browser.newtabpage.activity-stream.feeds.topsites=true
browser.newtabpage.activity-stream.feeds.section.highlights=false
browser.toolbars.bookmarks.visibility="newtab"
browser.download.useDownloadDir=true
browser.download.start_downloads_in_tmp_dir=false
browser.sharepane.enabled=false
places.history.enabled=true
findbar.highlightAll=true
findbar.findAgainOnScroll=false
```

### Commented-out proposals (uncertain, not yet active):
```
// user_pref("browser.tabs.unloadOnLowMemory", false);  // E-MEM: test on 8GB
// user_pref("dom.ipc.processCount", 6);                // E-PROC: test 4 vs 6 vs 8
```

### userChrome.css (theme-only, not engine fork):
- Toolbar gradient, tab shape, Top Sites grid, downloads popover, find bar,
  private browsing dark mode, context menu style, sheet dialog animation.
- Full userChrome.css lives in mavericks-theme package (not Firefox fork).

---

## 15. Hardware Validation Required

- Actual HiDPI rendering at 2304×1440 (2x scaling)
- VAAPI video decode performance (H.264/VP9/HEVC)
- AV1 software decode cost (expected high on Core M)
- WebRender vs basic compositor on HD 615
- Memory pressure with 6 content processes on 8-16GB RAM
- Tab thrashing behavior with many tabs on fanless Core M
