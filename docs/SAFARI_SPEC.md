# Safari-Mavericks UX Specification

Target: macOS Mavericks (10.9) Safari 7-era UX, adapted for Firefox ESR on
MacBook10,1 (2304×1440 HiDPI, Intel HD 615). Implementation surface:
userChrome.css + userContent.css (pure CSS, no JS) + Firefox preferences.
NO engine fork.

**Status (2026-09-28): IMPLEMENTED (pre-hardware).** Phases S1a–S2e delivered
a 498-line userChrome.css + 65-line userContent.css + 112-selector inventory +
221-check validation gate (`scripts/test-firefox-chrome.py`, 0 failures).
Fidelity classification (20 priority items): **9 implemented /
9 partially-implemented / 2 Firefox-native / 0 impossible-without-fork /
0 intentionally-different** at item level; 4 sub-aspects intentionally-different
documented in §16. Pixel validation of all visual states →
`docs/NEEDS_HARDWARE_TEST.md` (browser-chrome visual checklist) — NOT claimed
validated.

---

## 1. Toolbar

**Mavericks Safari 7**: Single unified toolbar row. Back/Forward (left),
unified address+search field (center), Share button (right), Downloads button
(right), Bookmarks Sidebar toggle (optional).

**Firefox mapping**:
- `browser.toolbars.bookmarks.visibility = "newtab"` — bookmarks bar only on
  New Tab (user.js:8)
- `browser.tabs.drawInTitlebar = true` — tabs in title bar (user.js:16)
- `browser.tabs.firefox-view = false` — no Firefox View (user.js:19)
- Share button: pref removed as dead (FF95+, user.js:23) — no Share button in
  ESR 128 toolbar by default. Firefox-native.
- Show All Tabs: pref removed as dead (FF45+, user.js:22). Firefox-native.

**Implementation: IMPLEMENTED.**
- Toolbar gradient `#f6f6f6→#eaeaea` + 1px bottom border `#c6c6c6`:
  userChrome.css:7-10
- Height 38px, padding 0 4px: userChrome.css:12-16
- Button spacing (margin 0 2px, padding 4px 6px), 4px radius, hover
  `rgba(0,0,0,0.06)`, active `rgba(0,0,0,0.12)`: userChrome.css:19-32
- Inset top sheen `rgba(255,255,255,0.8)`: userChrome.css:473-475
- Nav-bar group separators (1px `#d4d4d4`, 20px): userChrome.css:478-482

---

## 2. Tabs

**Mavericks Safari 7**: Tabs above toolbar, trapezoid shape, active tab lighter,
inactive tabs darker gradient. Tab height ~30px. Close button on hover (active
tab only). Favicon shown. Pinned tabs: favicon only.

**Firefox mapping**:
- `browser.tabs.drawInTitlebar=true` (user.js:16)
- Close button active-only: dead pref (FF89+, user.js:17) — close button shows
  on all tabs. Firefox-native.

**Implementation: PARTIALLY-IMPLEMENTED.**
- Rounded top corners 5px, no transform (perf rule): userChrome.css:92-100
- Active tab gradient + 1px border `#c6c6c6`, connects to toolbar
  (margin-bottom −1px + inset highlight): userChrome.css:111-116, 486-489
- Inactive dimmed (opacity 0.75), hover 0.9, active `rgba(0,0,0,0.12)`:
  userChrome.css:98-109
- Selected/inactive text colors (#1a1a1a / #555555): userChrome.css:118-124
- **Intentionally-different**: trapezoid `transform: perspective() rotateX()` —
  omitted; `transform` is outside the validation allowlist
  (test-firefox-chrome.py:28-34) and violates the §7 perf rule. Documented
  userChrome.css:80-81.
- **Not set**: tab height 30px (engine default); favicon 16px (engine default).

---

## 3. Unified Address / Search

**Mavericks Safari 7**: Single field. Type URL → navigate. Type search → Google.
Security indicator (lock) left. Reload button right (spinning during load).

**Firefox mapping**: Default Firefox behavior already matches (unified field).
Firefox-native.

**Implementation: IMPLEMENTED (styling).**
- Field min-height 30px: userChrome.css:35-37
- White bg, 1px `#c9c9c9` border, 5px radius, inset shadow: userChrome.css:39-45
- Mavericks blue focus ring (`#6ea8e8` border + 3px `rgba(66,133,244,0.35)`):
  userChrome.css:48-52
- Megabar breakout shadow: userChrome.css:55-58
- Reload/stop button styling (padding, radius, hover): userChrome.css:63-77
- **Not set**: placeholder color #888 (engine default).

---

## 4. Bookmarks Bar + Sidebar

**Mavericks Safari 7**: Bookmarks bar below toolbar (optional). Bookmarks
sidebar in sidebar panel. Sidebar width ~200px.

**Firefox mapping**:
- `browser.toolbars.bookmarks.visibility="newtab"` (user.js:8)
- Reading List / Shared Links: not applicable — omitted.

**Bookmarks bar: IMPLEMENTED.**
- Gradient `#f0f0f0→#e4e4e4`, 1px border, padding 2px 4px: userChrome.css:127-131
- Item radius 4px, padding 3px 6px, hover/active: userChrome.css:133-148

**Sidebar: PARTIALLY-IMPLEMENTED.**
- Container bg `#f6f6f6` + right border: userChrome.css:229-232
- Header gradient/border/padding: userChrome.css:234-238
- Title typography (Lucida Grande stack, 13px): userChrome.css:240-244
- Switcher/close buttons (padding, radius, hover, active): userChrome.css:246-261
- **Not set**: sidebar width 200px (engine default).
- **Not styled**: sidebar item rows — engine native.

---

## 5. Top Sites

**Mavericks Safari 7**: Grid of website thumbnails. Rounded corners, site name
below. Edit mode: drag to reorder, × to remove.

**Firefox mapping**:
- `browser.newtabpage.enabled=true` (user.js:7)
- `showSponsored=false`, `showSponsoredTopSites=false` (user.js:26-27)
- `feeds.topsites=true`, `feeds.section.highlights=false` (user.js:28-29)

**Implementation: PARTIALLY-IMPLEMENTED (userContent.css).**
- Light background `#f9f9fb`: userContent.css:8-10
- Wordmark 22px `#4a4a4a`: userContent.css:21-25
- Search input (border, radius, inset shadow, 13px): userContent.css:27-34
- Tile margin 6px, white bg, 1px `#dcdcdc` border, 6px radius, shadow, hover
  `#f2f2f2`: userContent.css:37-55
- Title 11px `#333333`: userContent.css:57-61
- Icon radius 4px: userContent.css:63-65
- **Intentionally-different**: spec's dark background `#1a1a1a` — light `#f9f9fb`
  chosen (matches Firefox newtab + light Google-search newtab; dark was a spec
  error for the target UX).
- **Not implemented**: 4×3 grid geometry, 120×90 thumbnails, hover scale
  (`transform` outside allowlist), edit mode — engine native.

---

## 6. Downloads Popover

**Mavericks Safari 7**: Downloads button in toolbar. Popover shows recent
downloads with progress bars. "Clear" button. "Show in Finder" option.

**Firefox mapping**:
- `browser.download.useDownloadDir=true` (user.js:65)
- `browser.download.start_downloads_in_tmp_dir=false` (user.js:66)

**Implementation: PARTIALLY-IMPLEMENTED.**
- Panel bg `#f6f6f6`, 1px border, 6px radius, shadow: userChrome.css:166-171
- Button padding/radius/hover: userChrome.css:173-181
- `[progress]` icon fill `rgba(66,133,244,0.30)`: userChrome.css:184-187
- Badge white on attention blue: userChrome.css:463-466
- **Not styled**: 4px progress bar, file item layout (40px rows, icon 24px) —
  engine native.

---

## 7. History

**Mavericks Safari 7**: History menu + History sidebar. Grouped by date.
Search field. "Clear History" option.

**Firefox mapping**:
- History sidebar: `viewHistorySidebar` (Ctrl+H)
- `places.history.enabled=true` (user.js:69)

**Implementation: FIREFOX-NATIVE.** No history-specific CSS. History sidebar
uses the sidebar chrome (§4). Date headers, item rows, search field: engine
native.

---

## 8. Find Bar

**Mavericks Safari 7**: Bottom of page, slides up. Search field, "3 of 12"
counter, up/down arrows, "Done" button. Highlight all matches in yellow.

**Firefox mapping**:
- `findbar.highlightAll=true` (user.js:70)
- `findbar.findAgainOnScroll=false` (user.js:71)

**Implementation: PARTIALLY-IMPLEMENTED.**
- Banner gradient, inset shadow, typography: userChrome.css:190-196
- Textbox white bg, 1px border, 4px radius, focus ring: userChrome.css:198-208
- **Not styled**: counter (11px #666), yellow match highlight `#ff9632` —
  engine native. `.findbar-highlight` rule sets label text color only
  (userChrome.css:210-212).

---

## 9. Private Browsing

**Mavericks Safari 7**: "File → New Private Window". Dark chrome. Purple/blue
tint.

**Firefox mapping**:
- Private window: Ctrl+Shift+P
- `browser.privatebrowsing.autostart=false` (default)
- `privacy.trackingprotection.enabled=true` (user.js:38)

**Implementation: PARTIALLY-IMPLEMENTED.**
- Purple-tinted toolbar gradient `#e8e4f0→#d9d2e4`: userChrome.css:304-307
- Purple-tinted bookmarks bar: userChrome.css:309-312
- Indicator pill (purple bg/text): userChrome.css:314-319
- **Intentionally-different**: spec's dark chrome `#2a2a2a` — light purple tint
  chosen (keeps Mavericks light chrome + signals private mode; matches Firefox
  private convention on Linux).
- **Not implemented**: dark urlbar/newtab in private windows.

---

## 10. Context Menus

**Mavericks Safari 7**: Right-click menus for links/images/page.

**Firefox mapping**: Default Firefox context menus are close to Mavericks.
uBO adds its own entries (acceptable).

**Implementation: IMPLEMENTED.**
- menupopup bg/border/radius/shadow/padding: userChrome.css:266-272
- menuitem padding 4px 16px 4px 24px, radius, color, font: userChrome.css:274-282
- Hover + `_moz-menuactive` `rgba(0,0,0,0.06)`: userChrome.css:284-289
- Disabled (color #9a9a9a, opacity 0.6): userChrome.css:291-295
- menuseparator 1px `#d4d4d4`: userChrome.css:297-301
- **Intentionally-different**: spec's blue hover `#4a90d9`/white text — subtle
  gray hover chosen (Mavericks toolbar-button language, consistent with §1).

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

**Mavericks Safari 7**: Sheet-style dialogs slide down from toolbar. Rounded
corners, grey background, default button blue.

**Firefox mapping**: Firefox on Linux uses GTK dialogs. Theme via GTK3 CSS
Mavericks theme (mavericks-theme package — separate from this chrome CSS).

**Implementation: FIREFOX-NATIVE (GTK layer).** Dialogs are GTK-native, themed
by the mavericks-theme GTK3 CSS. Sheet animation (slide-down from toolbar) is
not achievable via userChrome.css — not implemented.

---

## 13. Typography / Spacing / Icons / Loading States

**Typography: IMPLEMENTED.**
- Font stack `"Lucida Grande", Cantarell, "Noto Sans", sans-serif`, 13px base
  on navigator-toolbox/TabsToolbar/PersonalToolbar/nav-bar/urlbar:
  userChrome.css:156-163
- userContent typography (wordmark 22px, search 13px, tile title 11px):
  userContent.css:22-24, 31-33, 58-60
- Font prefs (San Francisco/Menlo): user.js:32-35 — fonts absent on Linux,
  falls back to Cantarell. Documented userChrome.css:151-154.
- **Not set**: line-height 1.4, 15px tab titles.

**Spacing: PARTIALLY-IMPLEMENTED.**
- Toolbar 38px, nav-bar padding 0 4px, button margin 0 2px / padding 4px 6px:
  userChrome.css:14-21
- Bookmarks bar padding 2px 4px: userChrome.css:130
- Menuitem padding 4px 16px 4px 24px: userChrome.css:276
- **Not set**: tab height 30px, bookmarks bar height 22px, field padding.

**Iconography: PARTIALLY-IMPLEMENTED.**
- Icon height 16px, opacity 0.92 softening, hover 1, active 0.8, disabled 0.45:
  userChrome.css:436-460
- **Impossible-without-fork**: glossy glyph recolor — `filter` tints and SVG
  `fill` recolors are outside the validation allowlist; a true glyph recolor
  needs an SVG skin. Documented userChrome.css:429-435. No binary assets
  invented.

**Loading States: PARTIALLY-IMPLEMENTED.**
- `#urlbar[busy]` gradient tint + 2px blue bottom border: userChrome.css:220-226
- Tab throbber, status bar ("Connecting to..."): FIREFOX-NATIVE (engine).

---

## 14. Implementation Surface Summary (actual)

### Files
- `configs/firefox/chrome/userChrome.css` — 498 lines, 191 `!important`
- `configs/firefox/chrome/userContent.css` — 65 lines
- `configs/firefox/chrome/element-inventory.json` — 112 selectors
  (verified-ESR / best-effort confidence per selector)
- `configs/firefox/user.js` — Firefox prefs
- `scripts/test-firefox-chrome.py` — 221-check validation gate (0 failures)

### Phase delivery (S1a–S2e)
| Phase | Content | Commit |
|---|---|---|
| S1a | Mavericks toolbar (gradient, 38px, buttons) | 28220a1 |
| S1b | Unified address field (focus ring, megabar) | 28220a1 |
| S1c | Safari-era tabs (rounded, active gradient) | 190fb2b |
| S1d | Bookmarks bar | 190fb2b |
| S1e | Typography (Lucida Grande stack, 13px) | 190fb2b |
| S2a | newtab userContent.css + selector inventory + gate | f4ea0e6 |
| S2b | downloads panel/button, findbar banner, urlbar loading | e1ed62b |
| S2c | sidebar, context menus, private browsing, focus states | 769590e |
| S2d | appMenu/PanelUI popup + urlbar results popup | 8184883 |
| S2e | toolbarbutton icon treatment + borders/gradients/textures | 4a23570 |

### Active Firefox prefs (user.js, verified against current ESR)
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
toolkit.legacyUserProfileCustomizations.stylesheets=true  // load userChrome.css
```

### Removed dead prefs (spec-claimed but non-functional in current ESR)
```
// browser.theme.color_scheme=1       — NOT a real pref. Light theme is Linux default.
// browser.tabs.closeButtons=1         — removed in FF89 (Proton). Close button on all tabs now.
// browser.tabs.firefox-view-next=false — NOT a real pref. Firefox View = browser.tabs.firefox-view only.
// browser.tabmanager.enabled=false   — removed in FF45. Tab manager no longer exists.
// browser.sharepane.enabled=false     — removed in FF95. Share button no longer exists.
```

### Commented-out proposals (uncertain, not yet active)
```
// user_pref("browser.tabs.unloadOnLowMemory", false);  // E-MEM: test on 8GB
// user_pref("dom.ipc.processCount", 6);                // E-PROC: test 4 vs 6 vs 8
```

---

## 15. Hardware Validation Required

- Actual HiDPI rendering at 2304×1440 (2x scaling)
- VAAPI video decode performance (H.264/VP9/HEVC)
- AV1 software decode cost (expected high on Core M)
- WebRender vs basic compositor on HD 615
- Memory pressure with 6 content processes on 8-16GB RAM
- Tab thrashing behavior with many tabs on fanless Core M

Browser-chrome visual checklist (all 23 states, pixel validation on HW):
see `docs/NEEDS_HARDWARE_TEST.md` → "Browser chrome visual checklist".

---

## 16. Fidelity Classification (20 priority items)

Forensic classification of actual implementation vs spec. Evidence: file:line
inspection of userChrome.css, userContent.css, user.js, test-firefox-chrome.py.

| # | Item | Status | Evidence | Notes |
|---|---|---|---|---|
| 1 | Toolbar | **implemented** | userChrome.css:7-16, 473-482; user.js:8,16 | gradient, 38px, buttons, sheen, separators |
| 2 | Unified field | **implemented** | userChrome.css:35-58, 63-77 | behavior Firefox-native (default) |
| 3 | Tabs geometry | **partially-implemented** | userChrome.css:83-124, 486-489 | trapezoid transform intentionally omitted (perf); tab height not set |
| 4 | States (hover/active/disabled/checked) | **implemented** | userChrome.css:26-32, 291-295, 330-333, 456-460 | |
| 5 | Bookmarks | **implemented** | userChrome.css:127-148; user.js:8 | bar only; sidebar = #9 |
| 6 | Top Sites | **partially-implemented** | userContent.css:8-65; user.js:26-29 | light bg intentionally-different; grid/thumbnails/edit native |
| 7 | Downloads | **partially-implemented** | userChrome.css:166-187, 463-466; user.js:65-66 | panel/button/progress; item rows native |
| 8 | Findbar | **partially-implemented** | userChrome.css:190-212; user.js:70-71 | banner/textbox/focus; counter/match-highlight native |
| 9 | Sidebar | **partially-implemented** | userChrome.css:229-261 | container/header/buttons; width + item rows native |
| 10 | Menus | **implemented** | userChrome.css:266-301, 336-383 | hover gray intentionally-different vs spec blue |
| 11 | Private | **partially-implemented** | userChrome.css:304-319 | light purple tint intentionally-different vs spec dark |
| 12 | Loading/progress | **partially-implemented** | userChrome.css:220-226 | urlbar busy; throbber/status native |
| 13 | Dialogs | **Firefox-native** | GTK layer (mavericks-theme) | sheet animation not achievable via userChrome.css |
| 14 | Typography | **implemented** | userChrome.css:156-163; userContent.css:22-60; user.js:32-35 | SF/Menlo absent → Cantarell fallback |
| 15 | Spacing | **partially-implemented** | userChrome.css:14-21, 130, 276 | tab/bar heights + field padding not set |
| 16 | Iconography | **partially-implemented** | userChrome.css:436-460 | glyph recolor impossible-without-fork (SVG skin) |
| 17 | Borders/gradients/textures | **implemented** | userChrome.css:468-498 + throughout | unified tokens |
| 18 | Focus/selection | **implemented** | userChrome.css:48-52, 205-208, 322-333, 403-405 | content text selection native |
| 19 | Scrolling | **Firefox-native** | — | no scrollbar CSS; chrome scrollbars not styleable via userChrome.css |
| 20 | Animations/timing | **implemented** | transition: opacity/background-color 120ms throughout | no keyframes (grep: only comment mentions) |

**Counts**: 9 implemented / 9 partially-implemented / 2 Firefox-native /
0 impossible-without-fork / 0 intentionally-different (item level).
4 sub-aspects intentionally-different: tabs trapezoid transform (#3), Top Sites
light bg (#6), menu gray hover (#10), private light purple tint (#11).

---

## 17. Validation Checklist (browser-chrome states)

Per-state status: **covered-by-CSS** (rules exist + gate-validated; pixels → HW),
**needs-pixel-validation-on-HW** (state exists in real browser; CSS coverage
partial/none; confirm on hardware), **untestable-headless** (cannot verify
without a browser/panel).

| State | Status | Evidence / reason |
|---|---|---|
| fresh launch | covered-by-CSS | base chrome rules; gate-validated |
| empty tab | covered-by-CSS | userContent.css activity-stream rules |
| 1 tab | covered-by-CSS | .tabbrowser-tab + [selected] |
| N tabs | covered-by-CSS | same rules; strip overflow native |
| active/inactive/hover | covered-by-CSS | [selected], :not([selected]), :hover, :active |
| focused field | covered-by-CSS | #urlbar[focused] ring |
| typed URL | covered-by-CSS | .urlbarView + rows + one-offs |
| loading | covered-by-CSS | #urlbar[busy] rules |
| loaded | covered-by-CSS | base styles (no dedicated rule needed) |
| error | needs-pixel-validation-on-HW | error pages = content docs; userContent.css scoped to activity-stream only |
| bookmarks | covered-by-CSS | #PersonalToolbar; visibility=newtab |
| Top Sites | covered-by-CSS | userContent.css tiles |
| downloads | covered-by-CSS | #downloadsPanel/button/[progress] |
| history | needs-pixel-validation-on-HW | sidebar container CSS-covered; history rows native |
| sidebar | covered-by-CSS | #sidebar-box/header/title/buttons |
| find | covered-by-CSS | findbar banner/textbox |
| private | covered-by-CSS | [privatebrowsingmode] rules |
| context menu | covered-by-CSS | menupopup/menuitem/separator |
| popup (appMenu/urlbar) | covered-by-CSS | #appMenu-popup, .urlbarView, .panel-arrowcontent |
| keyboard nav | untestable-headless | :focus-visible CSS gate-validated; nav behavior needs real browser |
| fullscreen | needs-pixel-validation-on-HW | no fullscreen CSS; native behavior to confirm |
| maximized | needs-pixel-validation-on-HW | window controls = GTK/xfwm4, not browser chrome |
| 2304×1440 HiDPI | untestable-headless | needs real panel |

**Counts**: 17 covered-by-CSS / 4 needs-pixel-validation-on-HW /
2 untestable-headless. Pixel states → `docs/NEEDS_HARDWARE_TEST.md`
(browser-chrome visual checklist) — NOT claimed validated.

---

## 18. Energy Sanity

Pure-CSS implementation. Grep evidence:
- **No JS**: two `.css` files only — no `<script>`, no `javascript:` URLs, no
  `@import` (gate: test-firefox-chrome.py:157 rejects @-rules).
- **No timers**: `grep -E "setInterval|setTimeout|requestAnimationFrame"` →
  0 matches.
- **No keyframes**: `grep "keyframes"` → 2 matches, both comments
  (userChrome.css:216-217). No `animation` property (outside allowlist by
  design).
- **Transitions**: only `opacity` + `background-color`, 120ms ease
  (allowlist-enforced, test-firefox-chrome.py:28-34).

Risk classes (one line each):
- **Idle cost**: ZERO — rules match only on state change; no animation loops,
  no polling, no timers.
- **Repaint cost**: LOW — transitions limited to opacity/background-color
  (compositor-friendly); no transform/width/height animation.
- **Memory**: NEGLIGIBLE — two static text files, no images/assets/fonts
  embedded.
- **Startup cost**: ONE-TIME — userChrome.css parsed once at browser start
  (`toolkit.legacyUserProfileCustomizations.stylesheets=true`, user.js:13);
  no runtime injection.
- **Gate enforcement**: 221-check test rejects out-of-allowlist properties and
  selector/inventory drift (test-firefox-chrome.py).
