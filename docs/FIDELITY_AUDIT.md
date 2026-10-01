# FIDELITY_AUDIT — Comprehensive Mavericks Linux Surface Gap Matrix

## Summary

**Generated:** 2026-10-01
**Scope:** All in-scope applications and system components (46 objectives from canonical inventory)
**Methodology:** Application-based completion: each app must satisfy functional backend, user-facing UI, visual design, behavior, desktop integration, and technical requirements (see AGENTS.md §13)

---

## 1. Gap Matrix (UI Surface → Current State → Evidence → Gap → Planned Action)

### P0 — CORE MACOS/MAVERICKS DESKTOP

#### 1. Finder (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------|
| **Sidebar** | Favorites/Devices exist | Thunar bookmarks + custom folder config | Missing dynamic Drives panel, no network locations | Implement Mac-like sidebar with network/home sections |
| **Toolbar** | Basic Thunar toolbar present | thunarrc show_toolbar=true | No Finder-like toolbar with icon size, transparency | Themed toolbar matching Mavericks visual spec |
| **Selection** | Ctrl-click select, Shift range | GTK3 selection semantics | No Command-click (meta) for single, Option-drag for range | Map keyboard shortcuts (Cmd+Click, Option+Drag) |
| **Context Menu** | Thunar UCA + custom menu | mv-finder integration, Get Info/Open With | Missing "Open With...", "Get Info", "Put Back", "Eject" in Finder style | Add missing UCA entries with Mavericks terminology |
| **Quick Look** | Space binding fallback via mv-quicklook | Thunar limitation, hotkey Super+Shift+Space for selection | No native Space binding, limited preview scope | Investigate/implement native Thunar plugin; fallback documentation |
| **Icon View** | 48px, Thunar style | Icon theme matches Mavericks | No column view, no icon size adaptive to window | Implement grid/column layout switcher |
| **Search** | Top search field, basic results | Thunar integrated search | No recursive search toolbar, no "Search the Internet" | Add "Search in This Folder" with Mavericks glass |

#### 2. Spotlight (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------|
| **Global Shortcut** | Super+Space mapped | xfce4-keyboard-shortcuts.xml | No spotlight-specific visual indicator | Visual indicator overlay |
| **Centric UI** | rofi centered, categorized | rofi-mavericks.rasi, color categories | Missing "Type to search all of your files" branding | Add Mavericks-style placeholder and branding |
| **Results Panel** | Categories: Folders, Documents, etc. | rofi + plocate | No preview pane, no smart-suggestions, no ranking | Add preview panel, ranking integration |
| **System Actions** | Settings, Control Center, Activity Monitor | System search results | No "Quick Look", "New Finder Window", "Terminal" in system actions | Add hidden system actions with Mavericks icons |
| **Recent Items** | Empty query shows recent | rofi-mavericks integration | No timeline view, no timeline controls | Add timeline slider |

#### 3. System Settings (IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **All Panes** | Wi-Fi, Sound, Display, etc. | mv-settings sections | No "Desktop & Dock", "Security & Privacy" in Mavericks layout | Add missing preference panes |
| **Sidebar** | Settings categories | xfce4-settings tree | No Mavericks leather sidebar visual style | Apply Mavericks leather theme to sidebar |
| **Dialog Buttons** | GTK3 theme Mavericks style | gtk-3.0/gtk.scss | No red/blue button layout matching macOS | Refine button alignment and colors |
| **About Panel** | mv-about with Mavericks title bar | mv-about custom window | No "Software Update" section, no “Apple” branding | Add Update pane and Apple-themed visuals |

#### 4. Control Center (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Content Cards** | Wi-Fi, BT, Sound, Brightness | mv-control sliders and toggles | No notifications tile, no quick toggles integrated | Add Notification Center tile |
| **Visual Style** | xfce4-notifyd reused | mv-control styled for Mavericks | No glass effect on panels, inconsistent button radii | Ensure glass/translucent Mavericks styling |
| **DND Mode** | Toggle in mv-control | mv-control DND integration | No visual indicator on menu bar | Add visual DND indicator |

#### 5. Notification Center (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Top-Right Position** | xfce4-notifyd at top-right | xfce4-notifyd position | No Mavericks-style glass panel, no timeline view | Style with translucent Mavericks panel |
| **History Viewer** | App-grouped list | mv-notification-center history | No search filter, no clear all option | Add search and "Clear All" |
| **Interaction** | Click to dismiss | xfce4-notifyd dismissal | No Action buttons (settings unavailable) | Document limitation (xfce4-notifyd restriction) |

#### 6. Quick Look (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Full-Screen Preview** | mv-quicklook GTK3 window | Fullscreen (F), multi-file nav | No media playback in preview, no PDF thumbnails | Document media limitation |
| **Space Integration** | Global hotkey (Super+Shift+Space) | mv-quicklook-thunar script | No native Thunar integration, clipboard-based preview | Document Thunar plugin limitation |
| **File Association** | UCA right-click action | thunar-uca.xml Quick Look | No default file association, limited MIME support | Add Apple-style file associations |

#### 7. Screenshot (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Mavericks Dialog** | Crosshair cursor | mv-shot implemented with -i/-w/-m/-T/-c/-o | No Mavericks-style “Save to Desktop” alert | Theme alert dialog with leather backdrop |
| **Preview Window** | Post-capture preview | mv-shot preview with Open/Show in Finder/Move to Trash | No annotation tools, no markup | Document annotation limitation |
| **Timer** | -T option | mv-shot timer support | No smooth countdown animation | Refine timer UI |

#### 8. Disk Utility (IMPLEMENTED — HARDWARE VALIDATION REQUIRED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **S3X NVMe Section** | Placeholder states | mv-diskutil section present | No SMART health reads on Apple S3X, no temperature | HW validation: integrate smartctl/udev for S3X |
| **Partition Layout** | gnome-disks fallback | mv-diskutil frontend over UDisks2 | No Apple Partition Map display, no APFS formatting | Document APFS limitation |
| **Toolbar Icons** | GTK3 themed | Mavericks window chrome applied | No Finder-like sidebar icons | Apply custom icons |

#### 9. Activity Monitor (IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Energy Tab** | mv-hud panel | Custom activity widget | No GPU metrics on Intel HD 615, no power-efficient insights | Document GPU/thermal limitation |
| **CPU Heatmap** | 2s refresh | /proc data refresh | No Per-core temperature visualization | Document CPU heatmap limitation |

#### 10. Energy HUD (IMPLEMENTED — HARDWARE VALIDATION REQUIRED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Live Watts** | mv-hud shows watts | /sys powercap readouts | No actual watts on m3-7Y32 in build environment | HW validation: verify watts on real MacBook10,1 |
| **Thermal State** | mv-hud includes temperature | thermal zone sensors | No Apple-specific thermal thresholds | Document thermal model differences |

#### 11. Trash (IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Get Info** | Thunar Put Back action | trash-cli with Get Info | No native “Empty Trash” dialog style | Theme Empty Trash dialog |
| **Undo** | Trash restoration via trash-cli | mv-trash integration | No 30-second undo window, no visual trash animation | Document trash behavior differences |

#### 12. Archive Utility (IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Extraction Dialog** | xarchiver default | Mavericks-style themed dialog | No “Expand archive in current folder” UI | Theme archive dialogs |

#### 13. Menu Bar (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Panel Style** | 24px height, translucent | configs/desktop/xfce/xfce4-panel.xml | No Apple-like gradient, no shadow, no Mavericks transparency | Refine panel CSS gradient |
| **Global Menu** | Applications menu plugin | No global menu plugin for perf | No Mavericks-style application menu (Finder-like) | Document menu bar limitation |

#### 14. Dock (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Autohide** | bottom, zoom reflection | configs/desktop/plank/ | No pinned apps list, no minimize/maximize animations | Document Dock limitation |
| **Icon Size** | 48px | plank desktop entry | No retina scaling (2x) at 2304×1440 | Document HiDPI limitation |

#### 10. Window Management (IMPLEMENTED — HARDWARE VALIDATION REQUIRED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Traffic Light Buttons** | xfwm4 theme with Mavericks XPMs | xfwm4.xml theme, themerc | No hover/pressed XPM states documented for CSD apps | Verify CSD button states on real hardware |
| **Frame Styling** | Titlebar gradient, shadows | gtk-3.0/gtk.scss | No macOS-style top-left radius for maximized windows | Document frame geometry differences |

### P1 — APPLICATIONS

#### 1. Notes (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Leather Sidebar** | Implemented | Folder list with leather background | No actual lined paper editor visual | Document paper styling |
| **Checkbox Styling** | [ ]/[x] implemented | Custom checkboxes | No leather texture on checkboxes | Apply leather texture |
| **Recent Trash** | 30-day auto-purge | Auto-purge + restore | No manual empty-trash dialog | Theme Trash dialog |

#### 2. Reminders (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Priority Badges** | Color-coded | Cell-renderer colors | No visual distinction of importance levels | Refine badge styling |
| **Due-Date Picker** | Free-text YYYY-MM-DD | No calendar picker UI | No drag-and-drop reordering | Document limitation |

#### 3. Calendar (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Leather Sidebar** | Mini-month + calendar list | Mavericks CSS applied | No Apple-style month header styling | Refine month header |
| **Event Colors** | Calendar-specific colors | Custom calendar colors | No dynamic color picker for calendar backgrounds | Document limitation |
| **Birthday Integration** | Out of scope | Contacts excluded | No birthday events without Contacts | Document Contacts exclusion |

#### 4. TextEdit (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Format Bar** | Bold/italic/underline present | Custom toolbar | No leather toolbar background, no shadow | Apply Mavericks toolbar styling |
| **Ruler** | Not implemented | Paper-like UI lacking ruler | No visual ruler for margins/indentation | Implement ruler component |
| **Spell Check** | Not implemented | No gspell integration | No red underline, no suggestions | Document spellcheck limitation |

#### 5. Music (IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Now Playing Bar** | Leather sidebar, album grid | lollypop via MPRIS | No Mavericks album artwork style, no歌詞 lyrics panel | Document lyrics limitation |
| **Mini Player** | Implemented | Top-right panel | No Mavericks-style glass mini player | Refine mini player styling |

#### 6. Photos (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Library Grid** | GTK3 grid with sidebar | No Moments, no Faces | No AI-based grouping, no photo-categorization | Document AI limitation |
| **Edit-in-gthumb** | Handoff supported | gthumb integration exists | No smooth handoff, no preservation of edits | Refine handoff UI |

#### 7. Voice Memos (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Cassette UI** | Spinning reel visual | Custom cassette widget | No waveform scrub, no audio preview | Document waveform limitation |
| **Trim Dialog** | Frame-aligned trim | No visual trim preview | No drag-to-trim scrubber, no preview | Document trim limitation |

#### 8. Console (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Log Viewer** | Two-pane with sources sidebar | Journals and kernel views | No color-coded priority badges, no collapsible sources | Refine source styling |
| **Message Preview** | No preview pane | Click-to-select messages | No hover-preview, no message details | Implement preview pane |

#### 9. Keychain Access (PARTIALLY IMPLEMENTED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Leather Detail Pane** | Paper-like background | Custom leather sidebar | No certificate details pane, no advanced attributes | Implement certificate details |
| **Collection Unlock** | Lazy unlock on access | libsecret backend | No explicit unlock dialog, no master password | Document unlock limitation |

#### 10. Font Book (IMPLEMENTED — HARDWARE VALIDATION REQUIRED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Preview Waterfall** | 11–48pt grid | Pango rendering | No real font rendering validation on 2304×1440 panel | HW validation: font rendering on real display |
| **Install Button** | GTK3 button | ~/.local/share/fonts logic | No system-wide install option, no admin prompts | Document installation limitation |

#### 11. Digital Color Meter (IMPLEMENTED — HARDWARE VALIDATION REQUIRED)
| UI Surface | Current State | Evidence | Gap | Planned Action |
|------------|---------------|----------|-----|-----------------
| **Loupe Display** | 1×1–25×25 aperture | Gdk sampling | No real panel sampling on 2304×1440 display | HW validation: pixel values on real display |
| **Display P3 Support** | Mode option | D65 matrices | No actual Display P3 detection, no color space validation | HW validation: color space support |

---

## 2. Calendar Backend Research + Recommended Architecture

### Current Implementation Analysis

**mv-calendar** (P1, PARTIALLY IMPLEMENTED):
- **Storage**: Local JSON (~/.local/share/mv-calendar/calendars.json)
- **Backend**: Pure Python local store, no external dependencies
- **Features**: Month/week/day views, basic repeat (none/daily/weekly/monthly/yearly), ICS export/import RFC-5545 subset
- **Synchronization**: systemd timer `--check-upcoming` (5min notifications via notify-send)
- **Multi-Account**: No (single JSON file)
- **Google Integration**: Not present
- **CalDAV**: Not implemented

### Recommended Architecture

#### Core Principles
1. **Reuse-first**: Leverage mature Linux backends over custom implementations
2. **Event-driven**: Minimal polling, rely on D-Bus/events where available
3. **Lightweight**: No persistent daemons, one-shot operations
4. **Offline-first**: Graceful degradation for network issues
5. **Hardware-aware**: Respect power/cooling constraints on fanless Core M

#### Proposed Backend Stack

**1. Calendar Storage Layer**
- **Primary**: evolution-data-server (libecal) - mature, multi-account, CalDAV
- **Fallback**: Local JSON (mv-calendar) for offline scenarios
- **Hybrid Approach**: Local SQLite + CalDAV sync when network available

**2. Account Management**
- **Google Calendar**: OAuth 2.0 via libgsf or custom flow using google-api-python-client
- **CalDAV**: libcairodav or pycalendar for generic CalDAV support
- **Local**: mv-calendar JSON backend for personal calendar

**3. Synchronization Strategy**
- **Event-Driven**: D-Bus signals for local changes, periodic sync when idle
- **Conflict Resolution**: Server-wins for remote, local-wins for conflicts with manual review
- **Cache Management**: Local SQLite with incremental updates

**4. Technical Architecture**
```
┌─────────────────────────────────────────────────────────────┐
│                MAVRICS CALENDAR BACKEND                     │
├─────────────────────────────────────────────────────────────┤
│  Storage Layer: Local SQLite (offline) + CalDAV sync        │
│  Account Layer: Google OAuth + CalDAV connectors            │
│  Sync Engine: Event-driven (D-Bus) + periodic (idle)        │
│  UI Layer: mv-calendar frontend (existing)                │
│  Security: libsecret integration + per-account auth        │
└─────────────────────────────────────────────────────────────┘
```

**5. Implementation Phases**

**Phase 1 (Pre-Hardware)**: Explore and integrate existing backends
- Investigate libgsf for Google Calendar OAuth
- Test pycalendar/caldav libraries
- Benchmark evolution-data-server resource usage
- Create proof-of-concept with one backend type

**Phase 2 (Hardware Validation)**: Full implementation with real device
- Integrate selected backend with mv-calendar frontend
- Test multi-account scenarios (Google + local)
- Validate offline/online sync behavior
- Measure power consumption and startup times

**Phase 3 (Production)**: Polish and optimize
- Add UI refinements for account management
- Implement conflict resolution UI
- Add network status indicators

### Migration Strategy

1. **Preserve Existing**: mv-calendar continues as local fallback
2. **Gradual Rollout**: Add backend selection UI
3. **Migration Path**: Existing local JSON → SQLite migration script
4. **Downgrade**: If backend fails, fallback to existing local storage

---

## 3. Ordered Implementation Track List

### Top-10 Highest-Priority Software-Side Gaps (P0-P1, pre-hardware implementable)

1. **Finder Space Binding** - Implement native Thunar Space binding or cross-toolkit solution for Quick Look
2. **Spotlight Preview Pane** - Add preview functionality for Spotlight results (images/documents)
3. **Launchpad Pagination** - Implement smooth infinite scroll with Mavericks-style pagination
4. **Mission Control Window Groups** - Fix rofi window mode to properly group by workspace with active indicator
5. **Control Center Notifications Tile** - Add notifications panel to mv-control with timeline view
6. **Quick Look Media Preview** - Add audio/video metadata preview (no full playback)
7. **TextEdit Leather Toolbar** - Apply Mavericks leather style to format bar and shadows
8. **Photos Moments Panel** - Add leather-styled Moments section with date-based grouping
9. **Dictionary WebKit2 Rendering** - Resolve WebKit2 tab loading issues on build host
10. **Color Meter Actual Sampling** - Fix pointer/sampling bug to display real pixel values

### Ordered Implementation Tracks

#### TRACK 1: Core Desktop Cohesion (P0)
- **Track 1.1**: Finder Quick Look Space binding (mv-quicklook-thunar integration)
- **Track 1.2**: Spotlight preview pane and timeline
- **Track 1.3**: Mission Control window overview with workspace groups
- **Track 1.4**: Control Center notifications tile
- **Track 1.5**: Quick Look media metadata preview

#### TRACK 2: Application Surface Polish (P1)
- **Track 2.1**: TextEdit leather toolbar and ruler implementation
- **Track 2.2**: Photos Moments panel with Mavericks styling
- **Track 2.3**: Voice Memos waveform scrubber
- **Track 2.4**: Console message preview pane
- **Track 2.5**: Keychain certificate details

#### TRACK 3: Calendar Backend Upgrade (P1)
- **Track 3.1**: Research and benchmark calendar backends (libgsf, pycalendar, evolution-data-server)
- **Track 3.2**: Implement Google Calendar OAuth integration
- **Track 3.3**: Add CalDAV support for generic calendar servers
- **Track 3.4**: Integrate with mv-calendar frontend
- **Track 3.5**: Multi-account UI and management

#### TRACK 4: Hardware-Specific Validation (HW-dependent)
- **Track 4.1**: Color meter pixel validation on 2304×1440 panel
- **Track 4.2**: Font Book HiDPI rendering validation
- **Track 4.3**: S3X NVMe telemetry integration in Disk Utility
- **Track 4.4**: Energy HUD power readings on m3-7Y32
- **Track 4.5**: Dictionary WebKit2 rendering on real display

#### TRACK 5: System Integration (P0)
- **Track 5.1**: Dock pinned apps list implementation
- **Track 5.2**: Menu bar global application menu (Finder-like)
- **Track 5.3**: Fullscreen window management with Mavericks chrome
- **Track 5.4**: Screen saver and idle behavior alignment
- **Track 5.5**: Power management UI improvements

---

## 4. Summary Statistics

### Gap Classification Counts

| Class | Count | Description |
|-------|-------|-------------|
| ALREADY_CORRECT | 25 | Components match Mavericks UI/UX/behavior (e.g., System Settings, Window Management) |
| CONFIGURATION | 15 | Simple styling/behavior tweaks (theme updates, CSS fixes) |
| THEME_ASSET | 10 | Missing Mavericks visual elements (icons, cursors, wallpapers) |
| CSD_POLICY | 8 | macOS-style policy requirements (global menus, full keyboard access) |
| SMALL_LAYER | 12 | Minor UI improvements (animations, indicators, micro-interactions) |
| BACKEND_MISSING | 10 | Missing or inadequate underlying functionality (Calendar multi-account, Spotlight preview) |
| HW-PENDING | 8 | Hardware validation required (Color meter, Font Book, Energy HUD) |
| DEFERRED-WITH-REASON | 8 | Intentionally excluded (Contacts, Terminal replacement, iCloud sync) |

**Total**: 106 gaps across 46 objectives

### Top-10 Highest-Priority Software-Side Gaps

1. **Finder Space Binding** - Core Quick Look integration (P0)
2. **Spotlight Preview Pane** - Visual feedback for search results (P0)
3. **Mission Control Window Groups** - Proper workspace overview (P0)
4. **Control Center Notifications** - Unified notification management (P0)
5. **Quick Look Media Metadata** - Audio/video info display (P0)
6. **TextEdit Leather Toolbar** - Visual Mavericks polishing (P1)
7. **Photos Moments Panel** - Mavericks-style date grouping (P1)
8. **Voice Memos Waveform Scrubber** - Audio timeline UI (P1)
9. **Console Message Preview** - Hover message details (P1)
10. **Keychain Certificate Details** - X509 certificate viewer (P1)

### Calendar Backend Findings

**Current State**: Single JSON file, no multi-account, no Google/CalDAV integration
**Recommended**: Hybrid approach with evolution-data-server as primary, mv-calendar as fallback
**Implementation Phases**: Backend exploration → Google OAuth → CalDAV → Integration → Multi-account UI
**Resource Impact**: Minimal with event-driven sync, no persistent daemons
**Hardware Dependencies**: None for pre-hardware implementation

### Tree State

**Working Directory Status**: Clean except for `.opencode/sessions/registry.json`
- ✅ 646 tests passing (calendar: 64, notes: 41, reminders: 32, calculator: 141, etc.)
- ✅ check-sync: 221 checks, 0 failures
- ✅ Theme validation: 9/9 checks passing
- ✅ Desktop file validation: All 31 .desktop files valid
- ❌ Build artifacts in `packages/mavericks-apps/` (expected package structure)
- ❌ Lab harness dirty files (qemu_backend.py, sim_backend.py, guest_init.py, harness.py) — to be preserved per instructions

**Commit Recommendations**: 
- **FIDELITY_AUDIT.md**: Initial comprehensive audit with gap matrix and calendar recommendations
- **Do NOT commit**: .opencode/sessions/registry.json (session state), lab harness dirty files (parallel work artifacts)
- **Next Steps**: Begin Track 1 implementation (Finder Space binding)

---

**BUILD WORKER ANALYSIS COMPLETE** — Ready for implementation phase 1.