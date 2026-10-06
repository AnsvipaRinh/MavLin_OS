# MavLinOS — Keyboard Shortcut Reference

Source of truth for the **global** shortcut layer is the action registry in
`packages/mavericks-apps/src/mavericks-apps/lib/mv_hotkeys_core.py`
(`ACTIONS`). The factory XML
(`packages/mavericks-apps/src/mavericks-apps/config/xfce4-keyboard-shortcuts.xml`,
mirrored into `airootfs` skel) is *generated from* that registry and checked
against it — `mv-hotkeys verify --xml <path>` fails the build on drift.

Reconfigure anything with the CLI or the editor:

```
mv-hotkeys list [--group G] [--skill S] [--json]
mv-hotkeys show ACTION
mv-hotkeys set ACTION ACCEL          # e.g. mv-hotkeys set spotlight Super+Shift+P
mv-hotkeys reset [ACTION]            # back to factory defaults
mv-hotkeys verify --xml <path>       # registry vs XML vs skel mirror
mv-hotkeys verify --live             # registry vs the live xfconf channel
mv-hotkeys export -o shortcuts.json  # portable copy
mv-hotkeys import shortcuts.json
mv-hotkeys gui                       # System Settings ▸ Keyboard Shortcuts
```

User overrides live in `~/.config/mfkeys/overrides.json` and are applied to
the live `xfce4-keyboard-shortcuts` channel immediately — no daemon, no
restart, nothing left running when a window closes.

Super = Windows / Command key. Keys in the "macOS 10.9" column are the
Mavericks mental model, not literal claims about macOS.

## Protected (not rebindable)

Rebinding these is refused, so the layer can never swallow standard Linux
shortcuts or the hardware function row:

| Binding | Why protected |
|---|---|
| Ctrl+Alt+T, Ctrl+Alt+L | standard Linux Terminal / screen lock |
| Alt+Tab, Alt+Shift+Tab | standard Linux window cycling |
| XF86Audio{raise,lower,mute,play,next,prev,stop} | hardware function row |
| XF86MonBrightness{up,down} | hardware function row |

## Spotlight / Launchpad / Mission Control / Quick Look / Screenshot

| Shortcut | Action | macOS 10.9 | Backend |
|---|---|---|---|
| Super+Space | Spotlight Search | Cmd+Space | mv-spotlight-gui |
| Super+L | Launchpad | Cmd+L | mv-launchpad-gui |
| Super+Shift+L | Launchpad Edit Mode | — | mv-launchpad-edit |
| Super+Tab | Mission Control | Ctrl+Up | mv-mission-control --native |
| Super+F3 | Mission Control (window overview) | F3 | mv-mc-gui |
| Super+Shift+Space | Quick Look (Finder selection) | Space | mv-quicklook-thunar |
| Super+Shift+3 | Screenshot: full screen | Cmd+Shift+3 | mv-shot -m |
| Super+Shift+4 | Screenshot: selection | Cmd+Shift+4 | mv-shot -i -c |
| Super+Shift+5 | Screenshot: interactive tools | Cmd+Shift+5 | mv-shot -i |

## Finder

| Shortcut | Action | macOS 10.9 | Backend |
|---|---|---|---|
| Super+E | Finder | Cmd+E (Home) | mv-finder-columns |
| Super+Shift+F | Finder (Browse as Columns) | — | mv-finder-columns |
| Ctrl+Alt+N | New Folder on Desktop | — | mv-newfolder $HOME/Desktop |
| Super+Shift+N | New Folder in Home | Cmd+Shift+N | mv-newfolder $HOME |
| Super+Shift+R | Rename | Return (on selection) | mv-rename |
| Super+I | Get Info | Cmd+I | mv-getinfo $HOME |
| Super+O | Open With | Cmd+O | mv-openwith $HOME |
| Super+Delete | Move to Trash | Cmd+Delete | mv-trash |
| Super+Shift+Delete | Empty Trash (asks first) | — | mv-empty-trash |
| Super+Shift+E | Empty Trash (alternate, asks first) | — | mv-empty-trash |
| Super+Shift+A | AirDrop | — | mv-airdrop |
| Super+F4 | Eject | Cmd+E | mv-eject |

## Application switching

| Shortcut | Action | macOS 10.9 | Backend |
|---|---|---|---|
| Alt+Tab | Cycle windows | — | xfwm4 cycle_windows_key |
| Alt+Shift+Tab | Cycle windows backwards | — | xfwm4 cycle_reverse_windows_key |
| Super+Q | Quit Application | Cmd+Q | mv-quit-app |
| Super+Shift+Q | Force Quit Applications… | — | mv-force-quit |
| Super+Alt+Escape | Force Quit (dialog) | Cmd+Opt+Esc | mv-force-quit |
| Super+H | Hide Application | Cmd+H | mv-hide-app |

## Window management

| Shortcut | Action | macOS 10.9 | Backend |
|---|---|---|---|
| Super+M | Minimise Window | Cmd+M | mv-minimize-window |
| Super+W | Close Window | Cmd+W | mv-close-window |
| Super+Up | Maximise Window | — | xfwm4 tile_up_key |
| Super+Down | Minimise Window (wm) | — | xfwm4 tile_down_key |
| Super+Left | Tile Window Left Half | — | xfwm4 tile_left_key |
| Super+Right | Tile Window Right Half | — | xfwm4 tile_right_key |
| Super+` | Cycle Windows of This Application | Cmd+` | xfwm4 switch_window_key |
| Super+Ctrl+F | Full Screen | Ctrl+Cmd+F | xfwm4 fullscreen_key |

The registry spells the first one `Super+grave` (the X keysym for the backquote
key); `Super+`` and `Super+Ctrl+F` are the two window-manager actions macOS has and
this layer did not: Alt+Tab only cycles across applications, so a multi-window
application (Settings, TextEdit with several documents) had no keyboard route to
its own windows. Both run inside xfwm4's key handler, so neither adds a resident
process.

These bindings are the *window-manager* actions only. Drag-to-edge snapping and
tile-on-drop are a different feature and are deliberately off (`snap_to_windows`,
`snap_to_border`, `tile_on_move` in `configs/desktop/xfce/xfwm4.xml`): macOS
never resizes a window you merely dragged next to something.

## Spaces

| Shortcut | Action | Backend |
|---|---|---|
| Super+1, Super+2, Super+3, Super+4 | Switch to Space 1 / 2 / 3 / 4 | xfwm4 workspace_1_key … workspace_4_key |
| Super+Alt+Left | Move to Previous Space | xfwm4 left_workspace_key |
| Super+Alt+Right | Move to Next Space | xfwm4 right_workspace_key |

Super+Left/Right tile the focused window; Space switching uses Super+Alt+Arrow.

## System

| Shortcut | Action | macOS 10.9 | Backend |
|---|---|---|
| Super+Comma | System Settings | Cmd+, | mv-settings |
| Super+Shift+C | Control Center | — | mv-control |
| Super+Shift+V | Notification Center | — | mv-notification-center |
| Ctrl+Alt+C | Calendar | — | mv-calendar |
| Ctrl+Alt+T | Terminal | — | xfce4-terminal |
| Ctrl+Alt+L | Lock Screen | Ctrl+Cmd+Q | xfce4-screensaver-command --lock |
| Ctrl+Alt+Escape | Power / Restart / Shut Down… | Ctrl+Cmd+Q | mv-power-ui |
| Ctrl+Alt+Delete | Log Out… | Shift+Cmd+Q | mv-power-ui logout |

## Keyboard & input (hardware function row)

| Key | Action | Backend |
|---|---|---|
| XF86AudioRaiseVolume | Volume Up | pactl |
| XF86AudioLowerVolume | Volume Down | pactl |
| XF86AudioMute | Mute | pactl |
| XF86AudioPlay | Play / Pause | mv-music --media-key playpause |
| XF86AudioNext | Next Track | mv-music --media-key next |
| XF86AudioPrev | Previous Track | mv-music --media-key prev |
| XF86AudioStop | Stop | mv-music --media-key stop |
| XF86MonBrightnessUp | Brightness Up | mv-brightness up |
| XF86MonBrightnessDown | Brightness Down | mv-brightness down |

Function and media keys depend on firmware and the `Fn` modifier.

## Contextual (not global)

Finder's own accelerators live in the Thunar user-customisations file
(`config/thunar-uca.xml`, mirrored into skel) — Rename, Compress, Put Back,
Open With, Get Info, Eject, Empty Trash, Search in This Folder, Browse as
Columns. Those apply to the focused Finder window and therefore have no global
key; app-level accelerators (Ctrl+C/V/T/F, Thunar Ctrl+1/2/3) stay in the app.

## Editing the layer

System Settings ▸ **Keyboard Shortcuts** (`mv-hotkeys-gui`) mirrors macOS 10.9
System Preferences ▸ Keyboard ▸ Shortcuts: skill-category sidebar, shortcut
label + Apple-glyph (⌃⌥⇧⌘) key column, enabled checkbox, click a row and press
the new combination to rebind, *All Defaults* to restore everything. Protected
rows explain why they cannot change. Rebinding onto an occupied combination
names the owner instead of silently stealing it.

## Regression gates

- `scripts/test-hotkey-layer.py` — registry invariants, accelerator parsing,
  conflict/protection rules, override round-trip, XML↔registry↔skel drift,
  import/export, CLI contract, GUI pure helpers (79 checks; the live xfconf
  rebind path is opt-in via `MV_HOTKEYS_LIVE_TEST=1`).
- `scripts/test-hotkey-layer-gui.py` — static Mavericks-look contract plus a
  real GTK smoke on the pinned Xvfb (:97) via `scripts/gui-isolation.sh`.
- Existing per-topic gates: `test-window-keys.py`, `test-empty-trash-keys.py`,
  `test-trash-eject-keys.py`, `test-force-quit-key.py`, `test-terminal-key.py`,
  `test-brightness-keys.py`, `test-alt-tab.py`, `test-workspaces.py`,
  `test-lock-screen.py`, `test-mv-mission-control.py`.
- All of the above run inside `scripts/check-sync.sh`.
