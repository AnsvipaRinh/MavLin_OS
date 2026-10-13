# E — Linux Application Integration

## E.1 Three strategies, chosen per application

| | Strategy A — native SDK | Strategy B — toolkit adaptation | Strategy C — backend/frontend split |
|---|---|---|---|
| **What the app is** | new app written against `libmavui` / `mvsdk` | existing GTK/Qt/EFL app, kept functional | existing app whose backend is good and whose UI is foreign |
| **How Mavericks appears** | widgets, chrome, menus, dialogs are the platform | compatibility layer maps its controls to Mavericks equivalents | the app's UI is replaced by a MavLinOS-native frontend |
| **Cost** | low (best case) | low–medium per app, once the layer exists | high (new UI, same data contract) |
| **Fidelity ceiling** | full | good for GTK3; medium for others | full |
| **When to choose** | every app we write (mv-*, Tools, Preferences) | third-party GTK apps we must keep (Thunar, Epiphany, Xfce panels) | apps where Linux UI cannot look or behave Mavericks-like (rofi surfaces, some legacy helpers, apps with unusable chrome) |
| **Examples in this repo** | `mv-diskutil`, `mv-activity`, `mv-settings` | Thunar (Finder), xfce4-panel (menu bar/Dock), xfce4-notifyd (notifications) | Spotlight/Launchpad (rofi frontends today), Mission Control, `mv-quicklook` behaviour shell |

### E.1.1 Strategy A — native SDK integration

An app links `libmavui`, uses `MV*` widgets, registers with the shell services
and follows D.3. This is the default for everything MavLinOS writes. Nothing in
the app hardcodes colour, metric, duration or wording.

### E.1.2 Strategy B — toolkit adaptation

A compatibility layer (`MavAdapt`, plane 2) sits between the toolkit and the
platform:

| Toolkit | Adaptation mechanism | Result |
|---|---|---|
| GTK3 | generated CSS from tokens + custom widget replacements for the 8 controls that matter (button, entry, tree/list, toolbar, menu, dialog, scrollbar, combo) | high fidelity; Thunar, most GNOME apps |
| GTK2 | same CSS subset via `gtk2-theme` bridge | medium (older layout metrics differ) |
| Qt5/6 | optional `MavStyle` QStyle + icon/font substitution | medium–high; only when a Qt app must stay |
| XUL/Firefox | `userChrome.css` (already used for the browser) + `mv-*` protocol handlers | medium, limited to chrome; enough for the browser |
| Electron/Java | not adapted | **out of scope** (`AGENTS.md` §7) |

Honest limits: GTK apps can be themed and partly re-widgeted, but non-standard
layouts, embedded web views and custom-drawn areas stay as the app drew them.
Where that breaks Mavericks coherence, the app is a Strategy C candidate.

### E.1.3 Strategy C — application shell / backend separation

Keep the backend, replace the frontend:

```
backend (unchanged, mature)        data contract                MavLinOS frontend
─────────────────────────          ─────────────                ─────────────────
plocate / locate index        →    result records            →  Spotlight UI
Thunar/GVfs operations        →    file ops + models         →  Finder-like UI
rofi/other launcher state     →    app/desktop-id list       →  Launchpad UI
X11 window enumeration        →    window records            →  Mission Control UI
libnotify/xfce4-notifyd       →    notification records      →  Notification Center
libarchive / 7z / tar         →    archive entries           →  Archive Utility
UDisks2 / smartctl            →    disk/partition records    →  Disk Utility
libsecret                    →    item records              →  Keychain Access
```

Contract for Strategy C: the data contract between backend and frontend must be
written down (usually a JSON-lines or D-Bus schema in `docs/APPS.md` or the
platform spec), so the backend can be replaced without touching the UI (and vice
versa: a plocate → tracker swap must not change one pixel of Spotlight).

## E.2 What integration gives an application (the shell contract)

| Capability | How the app gets it |
|---|---|
| MavLinOS windows | `MVWindow` (A) or a plane-3 window rule (B/C) |
| Native menus | app menu registration (§D.2.7) |
| Native dialogs / sheets | `MVAlert`, `MVSheet`, `MVOpenPanel` (§D.2.8) |
| Native notifications | `org.mavericks.Notifications` (§D.2.9) |
| System icons & typography | icon service + `mv_font_for` (§D.2.10, §D.2.11) |
| Focus / window model | `mv_focus_*` + window behaviour records |
| Consistent animation | named animation records (§D.2.5) |
| System services | D-Bus: storage, network, power, sound, secrets |
| Launch / open-with / MIME | `org.mavericks.App` + `mimeapps.list` (already mirrored by `check-sync.sh`) |
| Quick Look | `org.mavericks.App.QuickLook` |
| Session behaviour | session service (§D.2.14) |

## E.3 Suitability matrix

| App architecture | Strategy | Notes |
|---|---|---|
| Python3 + GTK3 (mv-* today) | A | directly portable to `libmavui` |
| C + GTK3 | A/B | theme-layer suffices if layout is standard |
| Thunar (C, GTK3, extensible actions) | B (+C for Finder-specific parts) | UCA actions already used; toolbar/sidebar chrome needs adaptation |
| xfce4-panel + plugins | B | menu bar and Dock visuals; behaviour via panel config |
| rofi surfaces | C | replace with platform frontends (Spotlight/Launchpad) |
| skippy-xd (experiment) | C | fold into a plane-3 Mission Control service or keep as backend |
| xfce4-notifyd | B/C | keep the daemon, own the presentation |
| GTK apps with custom drawing | B where possible, C when the chrome cannot be fixed | |
| Qt apps | optional B (`MavStyle`) or run themed-but-foreign | |
| Browsers | B limited (userChrome) | |

## E.4 Frontend replacement workflow (Strategy C)

1. **Name the backend capability** and its data contract (records, fields, ids).
2. **Name the Mavericks surface** it serves (which `surface.*`/`component.*`
   records it must render, which behaviors it must implement).
3. **Build the frontend on the platform** (plane 2 widgets + plane 3 services),
   not from scratch.
4. **Accept per §F** (visual, behavioural, integration, resource cost).
5. **Swap the backend** behind the contract and re-run the acceptance tests —
   the UI must not change at all.

## E.5 What cannot be integrated automatically

* Apps whose entire UI is a single custom-drawn canvas (games, some media
  players): only their window chrome can be Mavericks.
* Web-application wrappers: chrome-level theming only.
* Apps requiring global hotkeys or overlay windows that conflict with the
  platform layer: must be routed through the global shortcut registry, not
  registered independently.
* Anything requiring a resident daemon: rejected unless an explicit, measured
  justification is recorded (power baseline, `AGENTS.md` §7).
