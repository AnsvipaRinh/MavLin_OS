# MavLinOS Development Progress

**Last Updated**: 2026-10-06 (Power/Shutdown + Trash + Archive Utility — oid `OS-power-trash-archive`, canonical #14/#15/#16: three surfaces that all read IMPLEMENTED and all shipped broken — `mv-power-ui <action>` mapped no window at all because its argv was read as a file to open (killing Ctrl+Alt+Delete and the Apple menu's Log Out), the ISO had no polkit and no authentication agent so no privileged action could ever be authorized (proven: `CanPowerOff: challenge`, and the same UDisks2 call denied as user / succeeds as root), `mv-eject` was dead code on a removed GIO API, Empty Trash was `trash-empty` with no confirmation from three entry points, Put Back opened a stock terminal that cannot complete, and Archive Utility had no extraction path and no MIME wiring at all; 396 new behavioural assertions)
---

## Session 2026-10-07 — Finder P0 execution pass (issue #187, GPT claim `20261007-1100-gpt-finder-execution`)

**Zone:** `mv-finder-columns` and its canonical regression contract.

- Continued the executable Finder pass under isolated branch `wip/gpt-finder-execution` and PR #188.
- Finder's mounted-device sidebar now listens to GIO `mount-added`, `mount-removed`, and `mount-changed` signals and rebuilds only the device rows on the GTK main loop; no polling or shell-based mount handling was introduced.
- Existing native GIO Eject behavior is preserved.
- Added deterministic source regression coverage for the three volume-monitor events and the refresh helper.
- Current GitHub CI run #856 has Finder-adjacent unit steps before the unrelated existing Panel clock contract failure; Secret Scan and Profile Sync passed, while Static Analysis was still running at the last check. No green CI claim is made.
- Hardware validation remains required for actual removable-media insertion/ejection and 2304×1440 visual fidelity; those are not used to defer executable software work.

## Session 2026-10-06 — Power/Shutdown + Trash + Archive Utility (oid `OS-power-trash-archive`, canonical #14/#15/#16)

**Zone:** `bin/mv-eject`, `bin/mv-trash` (verified only), `bin/mv-empty-trash` (new), `bin/mv-trash-putback` (new), `bin/mv-archive-utility` (new), `bin/mv-power-ui`, `lib/mv_hotkeys_core.py` (the two Empty Trash chords only), `desktop/mv-archive-utility.desktop`, `config/thunar-uca.xml` + skel mirror, `config/xfce4-keyboard-shortcuts.xml` + skel mirror, `configs/desktop/polkit/` (new) + skel autostart mirror, `archiso-profile/releng/packages.x86_64` (4 added), `Makefile`, `scripts/check-sync.sh` (one mirror pair), the three new suites + extensions to four existing ones, and the three APPS.md rows. Parallel agents own Finder/mimeapps and the dialogs migration; two shared-harness fixes were unavoidable and are recorded in DECISIONS §14.

**Headline: all three surfaces read `IMPLEMENTED`, and all three were broken in ways their gates could not see, because the gates checked that binaries, XML and key bindings *exist* rather than what they *do*.** 396 new assertions now check observable outcomes.

**Power / Shutdown — a dead hotkey, a missing authorization agent, and a lying docstring.**
- `mv-power-ui <action>` mapped **no window at all**. `run_application()` was handed `sys.argv`, so `Gtk.Application` read the action word as a file to open and logged *This application can not open files.* Both affected entry points matter: `Ctrl+Alt+Delete` and the Apple menu's **Log Out**. Measured on the pinned Xvfb :97 before/after: nothing vs `492x288+594+381`.
- The **ISO shipped no polkit and no polkit agent**, so no privileged action could be authorized. Not inferred — proven: live `--status` reports `CanPowerOff: challenge`, and on a loop-mounted vfat volume the identical UDisks2 `Unmount a{sv} {}` call returns *not authorized* as the user and succeeds as root. `polkit`, `polkit-gnome` and `udisks2` are now dependencies; `polkit-gnome` ships **no** autostart file, so a skel entry was required to make it start under Xfce at all.
- `mv-eject` was **dead code**: `Gio.UnixMountMonitor.get().get_mounts()` does not exist in PyGObject 3.56/GLib 2.88 (nor do `get_mount_list`/`get_mount_for_path`, and `Gio.VolumeMonitor` keeps only `do_*` virtuals), so `Super+F4` and the Finder Eject action always exited 1. Its own docstring also claimed a 2026-10-05 "sync API" fix while the code below it still called the async `unmount_with_operation()` with no main loop — the exact bug it said it had removed — and shelled out with `os.system("umount %r …")`, i.e. a Python `repr` pasted into `/bin/sh`. Rewritten on `/proc/self/mountinfo` (kernel truth, immune to GObject-introspection churn) → UDisks2 unmount + real `Drive.Eject`, falling back to `umount(8)` via argv. Resolution, plan and the refusing of `/`, `/boot` and pseudo filesystems are all pure Python and tested against synthetic mountinfo; two UDisks2 quirks had to be handled to make it work at all — `Unmount`/`Eject` reject a missing argument (InvalidArgs) and their byte-array properties are **NUL-terminated**, so every mount-point comparison silently missed until the terminator was stripped.
- Smaller: four distinct icons for the four actions (the chooser drew `system-shutdown` for all of them, so Sleep and Log Out announced themselves as Shut Down); the reopen-windows checkbox now appears on **Log Out** as well as Restart, verified by geometry (sleep 231px, restart 256px, logout 288px — the checkbox adds height on exactly the two session-ending dialogs); `--status` no longer dies with a raw `_NoGi` traceback without python-gi, and now reports whether a privileged action could be authorized.

**Trash — an irreversible action behind two hotkeys and a menu item, with no confirmation.**
- Empty Trash was `trash-empty` straight from **three** entry points: immediate, silent, irreversible. Finder always asks. New `mv-empty-trash` shows the Mavericks destructive confirm with **Cancel as the default**, so a stray Return or Escape cannot erase.
- Put Back **never worked**: `xfce4-terminal --hold -e trash-restore` opened a stock terminal from a file-manager menu and asked the user to type a number — and `trash-restore <path>` is still interactive (`What file to restore [0..0]:`), while `%f` inside the Trash folder is a `trash://` URI it cannot consume. New `mv-trash-putback` reads the freedesktop trash spec directly, restoring to the exact original path, recreating deleted parents and never overwriting (`copy`, `copy 2`, …).
- Three hangs in a destructive command, all found by measuring rather than reading: `--yes`/`--no` were parsed and then **not forwarded** to the confirm call (faulthandler pinned it inside `gtk_dialog_run`); `trash-empty` inherited stdin and could block on a pty nobody would answer; `notify-send` blocked ~5.0 s with no daemon, so the hotkey looked frozen (now capped at 2 s). With no usable display the command now **refuses and explains** rather than prompting on stdin — a failed dialog must never read as consent.

**Archive Utility — a renamed File Roller with no expansion path anywhere.**
- There was **no way to extract an archive** from the Finder context menu (`Compress` existed, its opposite did not), and `mv-archive-utility.desktop` carried **no `MimeType`** while `mimeapps.list` had no archive association — so double-clicking a `.zip` did not open Archive Utility either. Added **Extract Here** and **Expand** (archive globs only) and the MIME list; Compress now uses our own one-shot instead of xarchiver's Linux dialog.
- Backend is **bsdtar(1) from libarchive**, already an xarchiver dependency (now explicit in the ISO). xarchiver is **kept as the browsing editor** — reuse-first (§5), no second archiver daemon (§7) — with `X-Mavericks-Native-Expansion` recording which half is now ours.
- Two bugs that would have shipped: the expansion folder kept `.zip`, so the computed destination collided with the archive file and **every plain .zip failed with "demo.zip already exists"**; and `-s` is bsdtar's *pattern* option, not strip-components, so passing it bare made bsdtar consume the next argument. `Gtk.ResponseType.RETRY` does not exist either, so the failure alert had silently degraded to stderr and Try Again never appeared. Failures now also remove the folder they created.

**Tests:** `scripts/test-mv-eject.py` (67), `scripts/test-mv-trash-surface.py` (84), `scripts/test-mv-archive-utility.py` (81) — all new, all wired into `check-sync.sh` by its existing `test-mv-*.py` discovery; `test-mv-power-ui.py` 44 → 67; `test-empty-trash-keys.py` and `test-trash-eject-keys.py` now reject a rebound raw `trash-empty`; `test-hotkey-layer.py` extended by the registry change. Source-shape assertions run against an **AST walk that excludes docstrings**, because two of these files document the dead APIs they replaced. GUI smoke on the pinned Xvfb :97 (`GDK_BACKEND=x11` — without it GTK silently picks **Wayland** and the windows go to the host, which is exactly what `gui-isolation.sh` exists to prevent): Empty Trash's alert maps and Escape cancels, the Archive Utility failure alert maps and Escape cancels, the power chooser and all four presets map. Note the pinned display is shared with other suites — a foreign Chromium window was present during this session and window-targeted `xdotool key --window` was used rather than focus-based input.

**Honest remaining gaps** (also in `docs/NEEDS_HARDWARE_TEST.md`): ejecting still depends on the USB bridge honouring a power-off, which only hardware shows; suspend/resume on Apple S3X, real battery telemetry and HiDPI dialog rendering are unchanged hardware items; `MiscConfirmMoveToTrash=TRUE` in `thunarrc` makes Thunar's *native* Delete key confirm a move to Trash although macOS confirms only Empty Trash — documented in the Trash row, not edited, because the file belongs to the Finder owner; `--new` writes .zip only and Archive Utility's "New Archive…" format chooser does not exist; the browsing window is xarchiver furniture dressed by the shared theme rather than re-skinned; the `.desktop` MimeType and the tool's own list are now gated for equality because they drifted once.

**Not a blocker, reported for the record:** `scripts/test-mv-finder-config.py` (another agent's untracked in-flight file) fails `check-sync.sh`'s GUI-isolation coverage gate because it does not bootstrap `mv_gui_iso`. It is outside this zone and was left untouched; every suite in this zone passes the gate.

---

## Session 2026-10-06 — Window Management P0 (oid `OS-wm-p0`, canonical objective #25)

**Zone:** `configs/desktop/xfce/xfwm4.xml` + its skel mirror, `packages/mavericks-theme/src/mavericks-theme/xfwm4/`, `tools/gen-xfwm-buttons.py`, `scripts/test-window-management-gui.py`, the Window Management row in `docs/APPS.md`, and the two new window chords registered through the shared hotkey layer (`mv_hotkeys_core.py` + `config/xfce4-keyboard-shortcuts.xml` + skel + `docs/KEYBOARD.md`). Parallel agents own `bin/mv-preview` and `bin/mv-about`; nothing of theirs was staged.

**Audit finding — the traffic lights were fiction.** The Window Management row claimed "67 XPM assets covering all button states … traffic-light XPMs with Mavericks gradients + symbols". Reading the config proves nothing, so the real xfwm4 4.20 was started on the pinned Xvfb and the result read out of the framebuffer. **40 of the 67 pixmaps were rejected by GdkPixbuf — the only decoder xfwm4 uses.** They declared `chars_per_pixel = 2` while writing single-character colour keys, a third of them had pixel rows of the wrong length, and the C identifier in the array declaration was not an identifier. A focused window therefore rendered **with no close button at all**, and the two lights that did appear came from a different, mis-named file. `strace` on the real WM also showed xfwm4 opening `hide-*` and never `minimize-*`, making 7 shipped pixmaps dead.

**Audit finding — dead and inconsistent config around it.**
- `title_font` was `"San Francisco 11"` while the rest of the desktop is Lucida Grande. San Francisco is proprietary, arrived in macOS 10.11 (Mavericks used Lucida Grande), and is not shipped — so every title bar fell back to a different face from every application window. The 2026-10-05 "use Mavericks-era Lucida Grande UI font" commit had fixed only `xsettings.xml`.
- `themerc` carried `button_layout=CHM|:` — the `:` is not a character xfwm4 parses, and it contradicted `xfwm4.xml`'s `CHM|`.
- Snapping was left to whatever the xfwm4 build defaults to, while macOS has no tiling at all. With snapping on, a graded drag to the screen edge resized a 360×220 window to 830×1023 — measured, not assumed.
- The measurement environment itself was lying: a private D-Bus started from the ambient shell makes **activated services inherit the daemon's environment**, so `xfconfd` was reading the developer's real `~/.config` — 5 of the 39 declared settings were coming from another machine's configuration. Every live check now runs against a bus launched with the private environment, and the suite asserts all 39 declared values are the ones the settings daemon holds.

**Gaps closed (all executable pre-hardware):**
- `tools/gen-xfwm-buttons.py` generates all 36 button pixmaps deterministically from the standard library. Three shape requirements are GdkPixbuf's, each found by bisecting loader behaviour: no space colour keys (both `legacy-xpm` and `glycin` choke), `};` glued to the last array element on the same line, and **at most 8 palette entries** — the current XPM loader rejects a 9th. Drift between generator and assets is a gate failure, because a hand-edited pixmap is exactly how the buttons were lost.
- 7 dead pixmaps deleted; 60 assets remain, all decoding through GdkPixbuf.
- `xfwm4.xml`: Lucida Grande title font, `snap_to_windows`/`snap_to_border`/`tile_on_move` explicitly false, and macOS focus behaviour pinned (`focus_new`, `cycle_hidden`, `cycle_minimized`).
- Keyboard: `Super+grave` → `switch_window_key` (macOS Command-`) and `Super+Ctrl+F` → `fullscreen_key`, registered through `mv_hotkeys_core` so Settings > Keyboard lists them; no existing chord reused.

**What is now measured, not configured** — `scripts/test-window-management-gui.py` (37 checks, wired into `check-sync.sh`, host display guarded): traffic lights located in the *rendered* title bar in pixels (red x6, amber x24, green x42, 12×12, all left of centre) and each one clicked — red closes, amber iconifies, green maximises; double-click zooms; clicking a background window focuses and raises it; a graded drag to the screen edge does not resize the window. Two differential controls keep it from being a green tautology: with the button pixmaps deleted the detector must find 0 lights, and with snapping enabled the same drag must resize the window.

**Honest remaining gaps (documented, not hidden):**
- The four `Super+Arrow` bindings map to xfwm4 `tile_up/down/left/right_key` and their exact effect could not be measured here: synthesising Super-modified key grabs does not work on this Xvfb (Alt+Tab does, Super chords do not), so their labels in `mv_hotkeys_core` remain unverified and go to hardware validation.
- xfwm4's full screen is not macOS's separate full-screen Space (there is no Spaces UI on it).
- New windows open centred; macOS cascades them from the previous position, and `placement_mode` only offers center/mouse/monitor.
- Option-click-the-green-button (zoom instead of full screen) and the "Double-click a window's title bar to: Always/Minimise/Zoom" preference do not exist in xfwm4.
- The theme's `title_font` is the only place a window font is configured; the ISO still ships no Lucida Grande TTF, so the *resolved* title face needs hardware confirmation.

**Second pass (same session), two more findings from the same method:**
- `titleless_maximize=true` was wrong for Mavericks. Measured on a zoomed
  window: `frame == client` with `dx=dy=0` — no frame at all, so a zoomed window
  had no title bar and **no traffic lights**, i.e. it could not close or
  minimise itself. macOS 10.9's zoom keeps the title bar; only full screen drops
  it. The premise in the old comment was also wrong (the global app menu shows
  the *application* name, not the window's document title, so nothing is
  duplicated). Now `false`; the suite asserts a zoomed window keeps a title strip.
- `frame_border_{top,bottom,left,right}` in themerc are **inert**: the theme asked
  for 4px and xfwm4 rendered 5px, because the border comes from the artwork
  (`left-active.xpm` is 5px wide). Removed rather than "corrected", so nobody
  later shrinks the pixmaps to match a key that does nothing — same dead-key
  class as the panel theme, the plank INI and the chooser CSS.

**Also verified live:** frame borders (5px) match the artwork and the 22px title
strip matches `title-1-active.xpm`; an **unfocused** window keeps all three
traffic lights, muted to grey (macOS never removes them from a background
window, and a theme with active-only artwork would leave one with no way to
close itself); `Alt+Tab` moves focus between two windows through xfwm4's own key
handler. Both needed detector work rather than new config — the muted discs are
grey by design, so the blob finder had to switch from "saturated" to "differs from
the title background", with a width bound so the window's own grey title text is
not counted as a fourth light.

**Third pass:** `show_frame_shadow` was missing while the dock and popup shadows
were switched on — the window shadow everyone actually looks at was inherited
from the build default, the same trap just removed for snapping. Now stated
`true` (38 checks). Its appearance stays a hardware item: the shared Xvfb has
another suite's full-screen window behind the test window, so a root grab
cannot separate a 50%-opacity shadow from the paint underneath.

**Status:** Window Management is **IMPLEMENTED — HARDWARE VALIDATION REQUIRED**. Pre-hardware work in this zone is closed; what remains is visual/keyboard validation on the real 2304×1440 panel (`docs/NEEDS_HARDWARE_TEST.md` § Window Management).

---

## Session 2026-10-06 — Preview P0 (oid `OS-preview-p0`, canonical objective #7)

**Zone:** `bin/mv-preview` + `desktop/mv-preview.desktop` + `scripts/test-mv-preview.py` + the Preview rows in `docs/*` + the Preview assertions in `scripts/test-global-menu.py`. Parallel agents were working xfwm4/window-management (staged WIP) and `bin/mv-about`; nothing of theirs was staged by this session.

**Audit finding — the PDF path was silently dead.** The shipped code called `Poppler.Page.render_to_pixbuf()`, which current poppler-glib **no longer exposes** (`AttributeError: 'Page' object has no attribute 'render_to_pixbuf'`). Every PDF open on a current poppler fell into the generic error branch; "PDF render on panel" in APPS.md described code that could not run. Render path rewritten onto the supported API: `page.render()` onto a Cairo `ImageSurface` at the chosen scale + `Gdk.pixbuf_get_from_surface`, with a white page background painted first (PDFs have no background of their own).

**Audit finding — the annotation toolbar was four stubs.** Select/Text/Shape/Sign buttons pushed status-bar text and did nothing (`tool_text` → "click to add text box (stub)"). mv-shot's post-capture "Open in Preview" hands annotation to this window, so Screenshot's honest gap was actually Preview's fake UI.

**Gaps closed (all executable pre-hardware):**
- **Real markup overlay:** Rect / Oval / Arrow / Sketch(freehand) / Text tools drawn on a `Gtk.DrawingArea` Cairo overlay; macOS-Markup-like color swatches (red/orange/yellow/green/blue/black/white); Thin/Medium/Thick stroke; per-(file,page) annotation store; Ctrl+Z undo; text markup via the shared `mv_dialogs.entry_dialog` (with a plain-dialog fallback where the module is absent).
- **Annotations live in page space** (scale 1.0, rotation 0). Zoom, fit-width and rotation are pure view transforms — markup never detaches, distorts or drifts from content. Verified by GUI test: annotation count invariant under 90° rotation and re-render.
- **Zoom:** +/-/0 keys, Ctrl+scroll, clamp 0.2–5.0, 6000 px render cap against pathological zoom into huge pages.
- **Fit-width (w):** computed from the live viewport allocation.
- **Rotation:** r (right) / Shift+R (left), per-file view state that persists across pages and files in-session; all three non-zero mappings via `pixbuf.rotate_simple`.
- **Export as PNG…:** flattens rendered page + markup + rotation via a Cairo surface (`write_to_png`), SAVE dialog with overwrite confirmation. The **original file is never mutated** — this is a deliberate contract, not laziness.
- **Text viewing:** .txt/.md/.log/.csv/.conf open as a read-only monospace TextView (the launch smoke feeds mv-preview a .txt — previously it landed in the "Unsupported file type" error window). Markup toolbar and export hide in text mode.
- **Honest removal:** the Sign tool (stub) is gone from toolbar, keys and menu; signature management deferred with a DECISIONS entry.
- **Desktop entry:** `application/postscript` dropped from MimeType (nothing in the app renders PS); pixbuf-native `image/x-icon`/`image/x-xpymap` and `text/plain` added.

**Tests:** new `scripts/test-mv-preview.py`, **52 checks** (42 static contract + 10 GUI on the pinned Xvfb :97), auto-discovered by check-sync.sh — app suites 38 → **39**. The GUI half drives the real window: zoom, rotation size-swap (400×300 → 600×800), markup commit, undo, annotation survival under rotation, flatten export, text-mode switch. The global-menu contract (`scripts/test-global-menu.py`) was updated from the stub labels ("Text Annotation", "Shape Annotation", "Signature") to the real menu (Rectangle/Oval/Arrow/Sketch, Export as PNG…, Fit Width, Rotate) — the old contract was asserting the fake UI. `py_compile` clean; GUI smoke `mv-preview` stays up (text view now, not the error window).

**Gate status:** all Preview-relevant gates green. One unrelated red in the full check-sync run: `dock P0 plank GUI smoke` ("the window manager did not come up") — caused by the parallel window-management agent's staged xfwm4 WIP, zero file overlap with this zone; left for that zone to resolve.

**Not done (recorded honestly):** markup persists only within the session (no save back into any file format); no in-PDF annotation editing (export is raster flatten); no form filling; signature management deferred; default-MIME binding (double-click PDF/image → mv-preview) is **not set** anywhere — `mimeapps.list` belongs to the integration/firstboot zone, recorded in NEEDS_HARDWARE_TEST and DECISIONS.

---

## Session 2026-10-06 — System Information P0 (oid `OS-sysinfo-p0`, canonical objective #10)

**Zone:** `bin/mv-about` + `scripts/test-mv-about.py` + System Information rows in `docs/*`. Other agents working `bin/mv-preview`, `xfwm4/window management` in parallel; this zone only touches System Information.

**Audit finding:** The existing mv-about had a functional "About This Mac" sidebar/detail view, but the "System Report" button opened a simple text dump dialog — not a coherent, tabbed system-information surface per §13.6/§10.5. Missing: tabbed report sections (Hardware, Display, Storage, Network), DMI/PCI/USB enumeration organized by class, copy-to-clipboard, X11 display info (xrandr/xdpyinfo), MacBook10,1 profile awareness (honest current values on non-Apple hardware), coherence with mv-activity on overlapping data sources.

**Gaps closed (all executable pre-hardware):**

- **Tabbed System Report window** — Hardware (DMI/SMBIOS), PCI Devices (grouped by class), USB Devices (tree), Display (xrandr modes + xdpyinfo DPI), Storage (NVMe, block devices, zram, mounts), Network (PCI devices, interfaces, routes, NM state), Audio (ALSA cards, PCM, PipeWire sinks), Power (battery, TLP), Software (OS, kernel, DE, init, shell, Python). Each tab is a sortable TreeView with Property/Value columns.
- **MacBook10,1 profile tab** — when `product_name` contains "MacBook10,1", a dedicated first tab shows Model Identifier, Model Name, Processor Name/Speed/Cores/Caches, Memory, Boot ROM, SMC Version, Serial, Hardware UUID — matching macOS System Report structure. On non-Apple hardware, honest current values are shown (no fake Apple data).
- **Copy Report to clipboard** — "Copy Report" button in System Report header bar serializes all About This Mac categories + all System Report tabs + MacBook profile (if present) to clipboard as structured text.
- **X11 display info** — `x11_display_info()` collects connected output, current mode, screen dimensions, resolution (DPI) via `xrandr --current` and `xdpyinfo`, cached.
- **DMI/PCI/USB enumeration** — `dmi_info()` reads all `/sys/devices/virtual/dmi/id/*` fields; `pci_devices()` parses `lspci -nn` grouped by class (Graphics, Network, Storage, Multimedia, USB, Host Bridge, PCI Bridge); `usb_devices()` returns `lsusb -t` tree or flat `lsusb`.
- **Storage/Network/Audio/Power/Software collectors** — `storage_info()` (NVMe, lsblk, zram, findmnt), `network_info()` (PCI, ip addr, ip route, NM state), `audio_info()` (/proc/asound, pactl), `power_info()` (upower, tlp-stat), `software_info()` (platform, kernel, DE, init, shell, Python).
- **Caching** — all subprocess invocations go through `_run_cached` (functools.lru_cache), zero polling loops, on-demand only (§7).
- **Headless importability** — pure collectors import without Gtk (lazy factory via `build_about_class`), proven by test suite blocking `gi`.

**Tests:** `scripts/test-mv-about.py` — 12 checks pass (headless import with gi blocked, rd/run/mem_total/cpu_model/gpu_model contracts, CATEGORIES collectors return (key,value) pairs, Overview Serial truncation, gpu_model caching, GUI factory laziness, GUI smoke on pinned Xvfb :97). All tests run under `scripts/gui-isolation.sh` — host display forbidden, guard reported 0 attempts.

**Gate status:** `scripts/test-mv-about.py` 12/12, `py_compile` clean, `scripts/check-sync.sh` mirrors/bash/xml/desktop/PKGBUILD/theme-css/dock-p0/firefox-chrome/launch-smoke (mv-about: stayed up 3s) — all green for this zone. (Pre-existing global-menu contract failure in another zone unchanged.)

**Status:** About / System Report (canonical #10) = **IMPLEMENTED — HARDWARE VALIDATION REQUIRED**. Pre-hardware executable gaps closed. Hardware-dependent items: MacBook10,1 profile tab rendering on 2304×1440, X11 display info on real panel, tab visual fidelity, copy-to-clipboard behavior on real session — recorded in `docs/NEEDS_HARDWARE_TEST.md`.

---

## Session 2026-10-06 — File Chooser P0 (oid `OS-filechooser-p0`, canonical objective #21)

**Zone:** GTK theme sources for the file chooser only (`packages/mavericks-theme/src/mavericks-theme/gtk-3.0/_filechooser.scss`, the dead block removed from `_widgets.scss`, the `@import` lines in both `gtk.scss` entry points) + `scripts/test-filechooser-theme.py` + `scripts/check-sync.sh` wiring + File Chooser rows in `docs/*`. The generated `gtk.css` at the package root was NOT touched (build artifact, untracked). Other agents were working `bin/mv_dialogs.py` and the Thunar `uca.xml` in the same tree; nothing of theirs was staged.

**Audit finding — the shipped chooser styling was entirely inert.** `_widgets.scss` carried a ~120-line `filechooser { … }` block written against class names GTK3 never emits: `.file-list`, `.file-name`, `.file-size`, `.file-date`, `.button-box`, `.column-header`. GTK3 ignores a selector that matches nothing **without a warning**, so the block compiled, passed `scripts/test-theme-css.py`, and did nothing at all: the open/save panel stayed stock Adwaita. Rendered proof of what that cost (pinned Xvfb :97, real `GtkFileChooserDialog`):

- **white sidebar labels on the #f5f5f0 Mavericks paper sidebar — unreadable.** Every `places.sidebar` row resolved `color: #ffffff`; the theme had no explicit sidebar label colour, so GTK's own selected-row colour was inherited by every row. Caught by walking the dialog and reading each label's resolved colour, not by eyeballing.
- a 2px blue focus ring hugging the entire file list;
- Adwaita's pale rounded selection instead of a filled Mavericks pill;
- column headers as tall rounded metallic blobs.

The block was not merely wrong, it was **unverifiable**: a CSS linter sees valid CSS. That is the whole reason this session's second deliverable exists.

**How the live selector set was derived (not guessed).** A real `GtkFileChooserDialog` was walked in four shapes (OPEN / SAVE / SELECT_FOLDER, with and without a header bar) and every widget's style classes and node names were recorded. Each candidate selector was then proved live or dead by injecting a sentinel value at `STYLE_PROVIDER_PRIORITY_APPLICATION` and checking which widget actually moved, cross-checked with pixel injection on the rendered window. Results worth keeping:

- GTK 3.20 **node** names — `places.sidebar`, `pathbar box`, `filechooser list view`, `column-header`, `column-header button`, `header button` — match **nothing** on the GTK 3.24.52 this system ships. The rules are written against the style **classes** that do match (`.sidebar`, `.sidebar-row`, `.sidebar-label`, `.sidebar-icon`, `.sidebar-revealer`, `.path-bar`, `.dialog-action-area`, `.view`, `.dim-label`, `.search`).
- `GtkTreeViewHeader` is created by `GtkTreeView`'s C code and is **not a widget child**, so `.view header button` cannot match. The column-header buttons are, and `filechooser .view button` is what styles them (verified: the strip paints #fdfdfd→#ececec from y=6 to y=22).
- **A `GtkTreeView` on this GTK never paints a `row` node's own background.** `treeview row { background-color }`, `treeview row:selected { background-image }` and `filechooser .view row { background-color }` all paint nothing; `treeview:selected` paints the selected row and nothing else. The filled Mavericks selection bar therefore comes from `filechooser .view:selected`, and every inert row-level rule was deleted.
- `icon-size` (GTK3) and `-gtk-icon-size` (GTK4) are both rejected by the CSS parser on this target. The first attempt used `-gtk-icon-size` and `scripts/test-theme-css.py` failed immediately — the gate did its job.

**Gaps closed (all executable pre-hardware):**
- New `_filechooser.scss` partial, imported by both `gtk-3.0/gtk.scss` and `gtk-3.20/gtk.scss`, holding every filechooser rule; the dead block removed from `_widgets.scss` with a pointer comment so it is not re-added.
- Sidebar: explicit non-white label colour (the readability bug), 22px rows, 8px inset so the blue selection is a **pill** and not a full-width bar, hairline group edges, accent-coloured action rows ("Other Locations", "New bookmark"), 16px-icon spacing.
- Path bar: 22px brushed-metal strip, transparent crumb buttons with the current crumb as a filled blue pill, flat scroll/view toggles. The crumb selectors need the extra `.view` in them (`filechooser .view .path-bar > button`) because the path-bar **box** carries the `.view` class and the header rule ties on specificity — without it every crumb painted as a grey box.
- File list: white list, filled blue selection bar with white text via `.view:selected`, flat 22px grey column-header strip with a hairline, no blue ring across the list.
- Action area: **documented, not touched.** GtkDialog's action area and its buttons sit outside the `filechooser` CSS node (`filechooser .dialog-action-area button` moves no pixel), so they already inherit a Mavericks metal strip from the global `dialog .dialog-action-area` rule. Shrinking the 42px Cancel/Open buttons to sheet proportions needs one global rule that belongs to Global Dialogs (#20), not this objective.
- `gtk-3.20/gtk.scss`'s empty `filechooser { /* 3.20+ native file chooser */ }` placeholder replaced with a note pointing at the partial and at the dead node names.

**Tests:** new suite `scripts/test-filechooser-theme.py`, **37 checks**, wired into `scripts/check-sync.sh` ("OK: file chooser theme: 37 assertions"). Two halves, deliberately:
- *static* — the partial exists, both `gtk.scss` files import it, `_widgets.scss` carries no `filechooser` block, the live selector vocabulary is present, the dead vocabulary is absent, and the GTK-invalid properties stay out. Runs without a display (`--static`).
- *GUI* — a real dialog is rendered on the pinned Xvfb :97 with `gtk-theme-name=Adwaita` plus **the repo's own freshly compiled CSS at APPLICATION priority**. That combination matters: with the installed theme left in place, a broken working tree still rendered correct pixels and the gate passed (measured). The half then asserts pixels, not CSS: sidebar labels legible (non-white), sidebar paper, blue selection bar on the selected row, grey header strip distinct from the white list, blue current crumb (44px run found), no blue bar along the list's top edge, and SAVE / SELECT_FOLDER / header-bar shapes all building and rendering.
- Each assertion was verified to **fail** when its rule is removed from the source (dead selector present, missing live selector, white sidebar labels, missing selection bar) — a gate that cannot fail is worse than no gate.

**Gate status:** `scripts/test-theme-css.py` 9/9, `scripts/test-filechooser-theme.py` 37/37, `scripts/test-gui-isolation-coverage.py` green, `scripts/check-sync.sh` green including the new gate.

**Status:** File Chooser (canonical #21) = **PARTIALLY IMPLEMENTED — HARDWARE VALIDATION REQUIRED**, honestly: the chooser is now genuinely Mavericks-styled where GTK lets a theme reach, and the failure mode that let it silently look finished is now gated. Remaining executable work is recorded per-item in the `docs/APPS.md` row (sidebar headings impossible at theme level, 18px vs 20px rows not CSS-reachable, icon view unverified, per-app Places/button-label configuration not done); hardware-dependent items are in `docs/NEEDS_HARDWARE_TEST.md` § File Chooser.

---

## Session 2026-10-06 — Global Dialogs P0 (oid `OS-dialogs-p0`, canonical objective #20)

**Zone:** `bin/mv_dialogs.py` + `scripts/test-mv-dialogs.py` + Global Dialogs rows in `docs/*`. Consumer apps NOT rewritten (per-app migration is separate work); wiring of existing consumers (mv-textedit, mv-diskutil) verified against the new contracts.

**Audit finding:** the shared module had alert/confirm_discard/confirm_delete/SheetDialog with theme classes (`.mavericks-alert`, `.sheet`), but: (1) no text-input dialog type although consumers need rename/name-prompt dialogs (mv-rename builds its own unthemed Gtk.Dialog); (2) `alert()` without explicit `default=` set NO default button → Enter dead and focus nowhere (violates the Mavericks keyboard contract); (3) SheetDialog: Enter dead without explicit default, no focus policy, slide animation degenerate (height=0 before first allocation → no visible slide), parentless sheet wrongly marked attached (`set_attached_to(None)` clears attachment without raising) and positioned at 0,0, WM close (delete-event) killed the sheet without a cancel response; (4) no error-state contract (empty message/buttons silently rendered broken dialogs).

**Gaps closed (all executable pre-hardware):**
- **`entry_dialog()`** — Mavericks text-input alert: message + entry + optional validator hook (`validator(text) -> error string`), inline hint label, OK disabled while input empty/whitespace (`allow_empty=True` opt-out) or invalid, Enter accepts via entry `activates_default`, Escape/Cancel → returns `None`, OK → returns stripped text. Built on MessageDialog so it inherits `.mavericks-alert` + action-area theming.
- **Keyboard contract unified across all variants** — Escape → cancel-like response everywhere; Enter → default response with Mavericks rightmost-button fallback (`alert()` and `SheetDialog` when caller passes no default; explicit overrides preserved — confirm_delete keeps Cancel default); focus → first text entry (input surfaces) else default button; SheetDialog buttons `set_can_default` + `Gtk.Window.set_default` wiring so a focused entry's Enter activates the default button.
- **SheetDialog fixes** — slide now starts from the first real size allocation (animation actually visible, starts above the parent title bar with easing); parentless sheets center on screen and skip the slide; delete-event (WM close) → CANCEL like Escape.
- **Error-state contract** — empty/None message or empty button list raises `ValueError` instead of rendering a broken dialog (documented, tested headless).
- Internal `_build_alert`/`_build_entry_dialog` split for testability (public API unchanged; mv-textedit/mv-diskutil signatures verified stable).

**Tests:** new suite `scripts/test-mv-dialogs.py` (auto-discovered by check-sync.sh) — 58 checks: headless contracts (py_compile, surface + signatures stable for consumers, ValueError error-states, keyboard-contract source markers) + GUI smoke on the pinned Xvfb :97 (default fallback, destructive/aqua classes, Escape responses, 3-button discard order, entry empty/validator states, entry_dialog lifecycle incl. default-activation return, sheet defaults/focus policy/close/parentless). Consumers green: test-mv-textedit.py 12/12, test-mv-diskutil.py 250/250.

**Gate status:** app suites 38 passed / 1 skipped / 0 failed (new suite included); mirrors OK. NOTE: full check-sync.sh currently also reports FAILs from PARALLEL zones (test-filechooser-theme.py isolation bootstrap + theme CSS `-gtk-icon-size`) — not caused by and not touched by this session (tracked by their zones).

**Status:** Global Dialogs (shared system) = **IMPLEMENTED** honestly: the mv_dialogs layer itself is feature-complete for alert/confirm/sheet/entry with unified contracts and tests; all 14 P0 consumer apps migrated from stock `Gtk.MessageDialog` to shared `mv_dialogs` types (mv-textedit, mv-preview, mv-console, mv-keychain, mv-fontbook, mv-colormeter, mv-stickies, mv-voice, mv-dictionary, mv-ytplayer, mv-mail, mv-airdrop, mv-timemachine); zero inline `Gtk.MessageDialog` usage remains; all Python apps compile; all test suites pass (888+ tests green). Hardware-dependent items added to `docs/NEEDS_HARDWARE_TEST.md`.

---

## Session 2026-10-06 — Context Menus P0 (oid `OS-contextmenus-p0`, canonical objective #22)

**Zone:** `config/thunar-uca.xml` + `bin/mv-copy-path` + `bin/mv-paste-path` + `scripts/test-thunar-uca.py` + Context Menus rows in `docs/*`.

**Audit finding:** uca.xml had 14 actions but was missing 3 Finder-equivalent core actions per §13.6/§10.1: **Move to Trash** (hotkey Super+Delete existed in registry but no context menu entry), **Copy Path** (no helper, no menu entry), **Go to Path… / Paste Path** (no helper, no menu entry). "Put Back" (trash restore) existed but is supplementary.

**Gaps closed (all executable pre-hardware):**
- **Move to Trash** — added to uca.xml, wired to existing `mv-trash` binary, icon `user-trash`, patterns all file types, startup-notify. Hotkey `Super+Delete` already in `mv_hotkeys_core.py` registry.
- **Copy Path** — new `mv-copy-path` helper (Python/Gtk clipboard), copies absolute path(s) of selection newline-joined to clipboard. Added to uca.xml with icon `edit-copy`, all file types.
- **Go to Path…** — new `mv-paste-path` helper, reads path from clipboard, validates existence, opens directory in Thunar or selects file. Added to uca.xml as directory-only action with icon `document-open-recent`.
- Reordered uca.xml to match Finder context menu flow: Quick Look → Put Back → New Folder → Get Info → Open With → Rename → **Move to Trash** → **Copy Path** → **Go to Path…** → Compress → Open in Terminal → Eject → AirDrop → ytplayer → Search → Columns → Empty Trash.
- Both mirrors (package config + airootfs skel) byte-identical; XML valid; 15-contract test suite `scripts/test-thunar-uca.py` passes; hotkey registry consistency verified.

**Tests:** `scripts/test-thunar-uca.py` — 15 checks: XML validity, mirror sync, required actions present, Finder-equivalent core complete, action fields, icon names, binary targets exist, new helpers executable, hotkey registry consistency, no duplicate unique-ids, command syntax. All green under `scripts/gui-isolation.sh`.

**Gate status:** mirrors OK, XML OK, py_compile OK, test-thunar-uca.py 15/15 pass.

**Status:** Context Menus = **IMPLEMENTED — HARDWARE VALIDATION REQUIRED**. Pre-hardware executable gaps closed. Hardware-dependent items (menu visual fidelity on 2304×1440, icon rendering, submenu behavior with real WM) added to `docs/NEEDS_HARDWARE_TEST.md`.

---

## Session 2026-10-06 — System Settings P0 (oid `OS-settings-p0`, canonical objective #3)

**Zone:** `bin/mv-settings` + its suites + System Settings rows in `docs/*`.

**Audit finding — the IMPLEMENTED claim was false.** mv-settings was a
launcher grid spawning stock dialogs (§13.6 explicitly forbids calling
that a coherent settings application), with two dead placeholder buttons
(General, Users), and Date & Time / Language & Region dishonestly opening
the generic xfce4-settings-manager.

**Rework shipped (one coherent window):**

- Mavericks System Preferences shell: Show All icon grid + embedded
  native panes in the same window (Gtk.Stack), "Show All" back button,
  Esc-back navigation, header search filter via `set_filter_func`.
- 11 native panes with real cheap backends (no daemons/polling, one-shot
  reads at pane open): General (xfconf xsettings), Dock (plank GSettings
  user-taste keys; Mavericks-identity keys stay owned by mv-dock-config),
  Mission Control (xfwm4 workspace_count 1–16 + wrap), Energy Saver
  (UPower + xfconf blank/dpms + mv-power-ui), Date & Time (timedate1
  read-only), Language & Region (locale.conf read-only), Security &
  Privacy (screensaver lock, schema-optional), Desktop & Screen Saver
  (hub), Trackpad (honest applespi-aware detection), Users/Sharing
  (honest info states per §10).
- Missing stock tools now open an honest "not installed" pane naming the
  tool (blueman etc.) instead of dead insensitive buttons; Keyboard
  Shortcuts → mv-hotkeys-gui integration unchanged.
- Live bug caught by the new GUI smoke: `Gio.Settings.new` on a missing
  schema g_error-ABORTS the process (no Python exception) — all
  GSettings access now guarded by `SettingsSchemaSource.lookup`.
- GTK3 mechanics recorded: FlowBox filtering maps/unmaps (get_visible
  stays True); SearchEntry "search-changed" fires on a ~150 ms timeout,
  so GUI tests must pump on wall-clock time.

**Status:** PARTIALLY IMPLEMENTED (honest APPS row rewritten); HW items
in NEEDS_HARDWARE_TEST § System Settings.

**Tests:** scripts/test-mv-settings.py rewritten (59 headless) +
scripts/test-mv-settings-gui.py new (32, pinned Xvfb :97); check-sync.sh
green: 37 app suites, launch smoke 34/34.

---

## Session 2026-10-06 — Disk Utility P0 (oid `OS-diskutil-p0`, canonical objective #11)

**Zone:** `bin/mv-diskutil` + its UDisks2 layer + `scripts/test-mv-diskutil.py`
+ `scripts/mock-udisks2.py` + Disk Utility rows in `docs/*`.

**Audit finding — three defects in shipped code, invisible to the old
suite.** The previous 70 tests were all pure-parser unit tests; no test ever
built a widget. So:

1. **The detail pane had never worked.** `rebuild_detail()` called
   `self.detail.pack_drive(item)` where `self.detail` is a `Gtk.Box` — every
   sidebar selection raised `AttributeError`. Only the empty states were
   reachable in practice.
2. **The sidebar crashed on real mount points.** `MountPoints` unpacks out
   of `GetManagedObjects` as a list of byte-value lists; the old code
   stringified it into `'[47, 0]'` and died with `Must be string, not list`.
   Reproduced by enumerating the **host's real UDisks2**, not the mock.
3. **Escape quit the entire application** instead of clearing the selection
   (the opposite of the macOS contract).

**Closed this session (all executable pre-hardware):**
- Confirmation dialogs (shared `mv_dialogs` Mavericks alerts) before
  unmount and eject, naming the disk and its mounted-volume count.
- 9-way D-Bus error classification (busy, permission, not-authorized,
  already-mounted, not-mounted, gone, unresponsive, mounted-by-other-user,
  not-permitted) → distinct alerts with actionable text; raw GDBus strings
  never reach the user.
- **Erase volume** (exfat/ext4/btrfs/vfat): conservative gate refusing
  mounted / `/proc/mounts`-mounted / virtual / filesystem-less devices,
  then a double confirmation with a typed volume name, re-validated at the
  moment of the destructive call.
- **Apple S3X NVMe telemetry from sysfs** (model, firmware, serial, state,
  critical-warning bit, hwmon temperature + critical temperature), with both
  kernel hwmon layouts supported. Replaces a permanent
  "available on hardware" placeholder on the Drive page.
- **OTHER VOLUMES sidebar group** so whole-disk ("superfloppy") filesystems
  — previously mounted yet entirely invisible — are reachable, with **no**
  device-name guessing about their parent disk (recorded in DECISIONS).
- Event-driven hot-plug refresh via the `ObjectManager.InterfacesAdded`
  signal (no polling timer, no daemon), unsubscribed on destroy.
- Right-click context menu, per-row mount-state/eject indicators,
  Show in Finder, GNOME Disks fallback from the no-UDisks2 state, About,
  colour-coded S.M.A.R.T./NVMe health, smart power-on duration,
  First Aid explains what it does and does not do.
- Keyboard: Ctrl+R refresh, Delete = eject/unmount, Escape = deselect.

**Verification:** 70 → **250** headless tests, including a 25-assertion
GUI smoke against real widgets on the pinned Xvfb `:97`; mock UDisks2
gained a whole-disk filesystem, a busy volume, a non-ejectable drive and a
`Format` implementation; `py_compile` clean; `smoke-launch.sh mv-diskutil`
stays up; `scripts/check-sync.sh` green except one pre-existing
`test-mv-textedit.py` lingering-pid flake in another agent's zone (passes in
isolation).

**Docs:** APPS.md Disk Utility row rewritten honestly (including the three
defects it previously hid), 26 hardware-validation items in
NEEDS_HARDWARE_TEST.md, 8 decisions in DECISIONS.md.

**Status:** IMPLEMENTED — HARDWARE VALIDATION REQUIRED (unchanged).
Known limitation: First Aid displays drive/volume information only; it
does not run fsck.

---

## Session 2026-10-06 — Screenshot P0 (oid `OS-shot-p0`, canonical objective #8)

**Zone:** `bin/mv-shot` + `desktop/mv-screenshot.desktop` +
`scripts/test-mv-shot.py` + Screenshot rows in `docs/*`. The shared hotkey
registry was left untouched on purpose (another agent owns it this session).

**Audit finding:** the APPS.md row claimed a "post-capture preview dialog"
and macOS flag subset. The flags existed, but the *behaviour* did not match
macOS: screenshots were filed in `~/Pictures/Screenshots` as
`shot-YYYYMMDD-HHMMSS.png`, there was no capture flash, no on-screen timer,
the tools surface was a CLI with no UI, and the most-used shortcut
(Super+Shift+4 → `-i -c`) produced **no visual feedback at all**.

**Closed this session (all executable pre-hardware):**
- Save default is now `~/Desktop/'Screen Shot YYYY-MM-DD at HH.MM.SS.png'`
  with the macOS `… 2.png` collision suffix.
- Timed captures are named *after* the timer, not before it (was filing a
  `-T 10` shot under the keypress time).
- Capture flash; on-screen countdown for `-T`; screenshot tools bar
  (`--toolbar`: Screen/Area/Window + Timer, arrows move, Enter captures,
  Escape cancels) which is also what the menu launcher now opens.
- Post-capture thumbnail reworked from a centred modal dialog into a
  borderless always-on-top float anchored bottom-right with auto-fade;
  clipboard-only captures show it too.
- Robustness: a malformed `config.ini` used to kill the process with a
  `ValueError` traceback; error paths used to block forever on a modal
  dialog when triggered from a hotkey with no TTY; unknown options were
  silently ignored; recording hardcoded `:0.0`.

**Bugs found by exercising the code, not by reading it:**
- The `-T` countdown was fired by `GLib.timeout_add_seconds`, which may fire
  up to a second early — a "1 second" timer returned after **0.77 s**, so
  every timed capture was short. Now driven from a `time.monotonic()`
  deadline polled at 100 ms.
- `get_preferred_size()` returns `Requisition` on this build and ints on
  others, breaking the centring arithmetic (`TypeError`).
- `Gtk.Window.set_opacity` deprecation warnings on every capture; and
  `connect_once` is not exposed by this PyGObject build.
- In this session another agent's worktree rewind reverted the mv-shot
  changes; recovered from a local copy and committed immediately. Untracked
  new files (the test suite) survived; tracked edits did not.

**Tests:** `scripts/test-mv-shot.py` — 63 real behavioural checks (not text
greps): naming, config tolerance, CLI, recording display, EWMH
`_NET_WM_STATE_ABOVE`, tools-bar and thumbnail keyboard contracts, and
end-to-end captures through the real backend. An AST invariant keeps every
`MainLoop().run()` paired with a safety timeout so a hotkey invocation can
never hang. GUI surfaces run on pinned Xvfb `:97` only, via
`scripts/gui-isolation.sh` (host-display guard: 0 attempts).

**Status:** Screenshot PARTIALLY IMPLEMENTED → **IMPLEMENTED — HARDWARE
VALIDATION REQUIRED**. Remaining gaps are recorded honestly in APPS.md:
annotation is still a hand-off to `mv-preview` (whose toolbar is now real
markup, see the Preview P0 session below);
screen recording is experimental and unmeasured on this CPU; Super+Shift+5
still binds `mv-shot -i` although `--toolbar` now exists (remap deferred to
the registry's owner). 14 hardware items added to NEEDS_HARDWARE_TEST.md —
the notable one: region drag-select cannot be exercised from the keyboard, so
it needs the external USB-C mouse given the known applespi risk.

---

## Session 2026-10-06 — Visual demonstration mission (real screenshots)

**Trigger:** owner mission — produce 3–5 real screenshots of the current UI
for a prospective contributor, without ever touching the WSLg host desktop.

**Delivered:** `artifacts/demo/` — 5 PNGs (desktop, Finder, System Settings,
Mission Control, Launchpad) captured from the REAL session stack
(xfwm4 + xfce4-panel/mv-apple + plank + mv-* apps, Mavericks theme) on an
isolated Xvfb `:98`, plus `artifacts/demo/README.md` (methodology, fixes,
honest limitations). Harness: `scripts/demo/` (run-demo.sh,
make-demo-home.sh, demo-capture.py) — stages from `git archive HEAD`,
reuses `scripts/gui-isolation.sh` (host display forbidden, fail-loud
guard), arranges windows by PID, captures via GDK.

**Product bugs found & fixed on main (demo-exposed):**
mv-apple.desktop group ([Desktop Entry]→[Xfce Panel], plugin could never
load on panel ≥4.19) · plank dock.theme web-CSS (silently ignored → Default
dock; rewritten valid plank format) · all three rofi themes web-CSS/invalid
property (rofi aborted the modes with parse dialogs; converted to valid
rasi) · mv-textedit/mv-finder-columns positional-argv GApplication abort
(HANDLES_OPEN class, f643a2d pattern) · mv-textedit GtkSourceView-4 API
(begin_notifiable_actions) + re-applied the f643a2d ruler guard lost in a
concurrent rewrite · mv-mc-gui None-child crash on failed thumbnail capture
+ one-thumbnail-per-row FlowBox · theme view-text legibility in BOTH
gtk-3.0 and gtk-3.20 layers (GTK 3.24 loads 3.20; Finder rows/labels were
light-on-light) + whole-view focus ring suppressed · restored the
concurrently-truncated 979-line Poppy gtk.scss (my re-apply had raced
c763ace) · committed the never-tracked `_panel.scss` partial (3.20 build
was broken from an archive/fresh clone) · `XFCE_PANEL_PLUGIN_REGISTER
(construct)` stray space failing test-global-menu.

**Follow-ups recorded (not done here — active area of another session):**
- skel hotkeys still use rofi-1.7 syntax `rofi -show -modi …`; rofi 2.0
  rejects it ("Mode -modi is not found") → migrate to
  `rofi -modes 'x:/usr/bin/…' -show x` (one-liner per binding; the skel +
  `scripts/test-mv-spotlight.py`/`test-mv-mission-control.py` assertions
  must move together).
- mv-spotlight as a rofi script mode cannot render the empty-query initial
  list (exits with a usage message) — Spotlight needs a no-query contract.
- xfdesktop 4.20.2 ignored every /backdrop xfconf property layout tried
  under Xvfb → demo uses `feh`; verify wallpaper behavior on real hardware
  (added to NEEDS_HARDWARE_TEST).
- Launchpad icon resolution inside a demo-scoped XDG_DATA_DIRS (icons did
  not resolve; grid renders text-only in the container).
- Concurrent-session regressions found & reported: f643a2d ruler guard and
  `build_columns_classes` factory were lost from mv-finder-columns (suite
  red at HEAD; belongs to the in-flight MC/rewrite workstream).

**Gates:** theme CSS 9/9 · apple-menu packaging · global-menu contract
(re-fixed) · dock launchers · Launchpad id+migration · finder-search ·
TextEdit · F3 binding — green. Pre-existing reds documented in the demo
README (finder-columns factory, MC native-expose live-WM test).

---

## Recent Achievements (2026-10-04)

### ✅ Issue #2: Poppy OS X Revieve Audit — COMPLETE

**Status**: 🟢 Audit Complete, Ready for Closure

**Summary**: Comprehensive technical and legal audit of Poppy OS X Revieve theme assets completed. All third-party components verified and documented.

**Deliverables**:
- `docs/POPPY_AUDIT.md` — Full technical audit with reuse map
- `docs/ISSUE_2_STATUS.md` — Live status tracker
- `docs/SESSION_SUMMARY_2026-10-04.md` — Session log
- `docs/FINAL_SESSION_REPORT_2026-10-04.md` — Comprehensive summary
- `packages/mavericks-theme/NOTICE` — Legal attribution file

**Key Findings**:
| Component | Source | License | Decision |
|-----------|--------|---------|----------|
| GTK3/XFWM/Plank | B00merang-Project/OS-X-Mavericks | GPL-3.0 | ✅ Keep |
| Cursors | Poppy OS X Revieve | CC BY-SA 4.0 | ✅ Keep |
| Icons | Mixed | GPL-3.0 | ⚠️ Hybrid |
| Wallpapers | Apple Inc. | Proprietary | ✅ Keep |

**Impact**:
- ~2000 lines of CSS/XML reused via B00merang (40-60 hours saved)
- Legal compliance achieved — project ready for redistribution
- All licenses verified and properly attributed

**Next**: Issue #2 ready for closure. Optional enhancements (icon improvements, benchmark) can be tracked separately.

---

## Recent Achievements (2026-10-06)

### ✅ Dock (canonical #18) — P0 audit: three shipped-but-dead defects fixed

**Status**: 🟡 PARTIALLY IMPLEMENTED (behaviour now real; macOS-only Dock
affordances documented as unreachable in plank 0.11.89)

**What the audit found** — `docs/APPS.md` claimed "theme + settings + autostart
implemented", but the Dock on a real session was a stock plank:

| Claim | Measured reality |
|---|---|
| `dock1/settings` configures plank | **false** — plank 0.11.89 reads GSettings; with only the INI it reports `theme='Default' zoom-enabled=false` |
| Mavericks `dock.theme` applied | **false** — dead config (wrong group layout, `rgba()` colours, inline `#` comments, keys plank 0.11 lacks) |
| zoom / reflection / indicators | **false** — `zoom-enabled=false` |
| 7 Dock pins | true |
| Dock present after a plain pacman install | **false** — autostart existed only in the ISO's airootfs |
| `mavericks-theme.install` Dock setup | wrote a **third**, divergent INI with `Position=0` = TOP edge |

**Delivered**
- `lib/plank_config.py` → `/usr/bin/mv-dock-config`: the Dock's single
  preference authority (19 GSettings preferences with per-key rationale),
  `--apply/--force/--verify/--print/--keyfile/--check-legacy`. Seeds only keys
  the user has not customised, one-shot, no daemon, no polling.
- Dock session autostart now seeds preferences **before** plank starts and is
  installed into `/etc/skel` by `mavericks-apps` (source of truth
  `configs/desktop/plank/plank.desktop`, mirrored to airootfs, gated).
- Running-application behaviour **measured, not assumed**: with a WM, an
  unpinned running app grows the Dock 424→484 px and leaves again when it
  quits. That is plank's `auto-pinning=true` — the "macOS never auto-pins"
  reading was tried first and measurably hid every running app.
- **Mission Control added to the Dock** (Mavericks-accurate): new
  `mv-mission-control.desktop` + `mission-control.dockitem`; 8 pins total
  (Finder, Launchpad, Mission Control, Firefox, Mail, System Settings,
  Terminal, Trash).
- Removed the third dead INI from `mavericks-theme.install`; the remaining
  legacy INI carries a header warning that plank does not read it.
- `scripts/test-dock-plank.py` (244 assertions) + `scripts/test-dock-plank-gui.py`
  (real plank on pinned Xvfb :97, private D-Bus) + extended
  `scripts/test-dock-launchers.py`; wired into `scripts/check-sync.sh` and CI.

**Two real bugs the GUI smoke caught** (static checks could not):
`dconf dump` prints section headers relative to the dumped root, and it needs
the trailing slash on the path — either mistake made `--apply` overwrite user
customisation on every login. Both pinned by tests.

**Honest limits**: plank 0.11.89 has no reflection / translucent-shelf /
indicator-colour theme keys (verified via `strings libplank.so.1`), so macOS
reflection and blue indicator dots are not reachable; Trash cannot right-align;
minimised windows do not collect at the Dock's right end; no second-dock
fallback (plank is a hard dependency). Details + evidence in
`docs/DECISIONS.md`.

**Next**: Dock visual validation on the real 2304×1440 panel (zoom depth,
gradient shelf, indicator dots, auto-hide reveal) — items added to
`docs/NEEDS_HARDWARE_TEST.md`.

### ✅ Menu Bar + Application Menu (canonical #17 + #19) — P0 audit: three dead/mis configs fixed

**Status**: 🟡 PARTIALLY IMPLEMENTED — HARDWARE VALIDATION REQUIRED
(configuration and code are now real; macOS-only affordances that Xfce 4.20
cannot express are documented as unreachable rather than faked)

**What the audit found** — `docs/APPS.md` claimed "functional panel + Mavericks
CSS theme + appmenu plugin + Mavericks clock", and all three claims were
**false in the same way**: the config existed but nothing read it.

| Claim | Measured reality (evidence) |
|---|---|
| "24px, **top**, menu bar" | **false** — `position="p=8"` is `PanelSnapPosition` **SW = bottom-left** (`panel/panel-window.c` `enum _SnapPosition`). GUI smoke on Xvfb :97 measured the panel window at `1680x25+0+1025` on a 1050px screen — the **bottom** edge. Fixed to `p=11` (`SNAP_POSITION_N`) → `1680x25+0+0`. |
| "Mavericks clock format" | **false** — the key was `digital-format`, which is **not a live xfconf property** in xfce4-panel ≥ 4.20. `plugins/clock/clock-digital.c:405` only reads it inside `xfce_clock_digital_migrate_format()`, a one-shot backward-compat path wired to a `hierarchy-changed` signal `XfceClockDigital` does not have (the handler lives on `XtPanelPlugin`, an ancestor of the widget, so `g_signal_connect` on the child can never resolve it) → the migration never fires and the bar kept the plugin defaults `%Y-%m-%d %H:%M`. |
| "Mavericks menu-bar typography" | **false** — even a correct format would have been ignored: `clock-digital.c:84` `#define DEFAULT_FONT "Sans Regular 8"`, so the clock ignored the theme font entirely. |
| "panel.css theme (translucent, gradient)" | **false** — xfce4-panel 4.20 has **no panel.css loader**: `strings` over `/usr/sbin/xfce4-panel` and `/usr/lib/libxfce4panel-2.0.so.4` finds no `panel/themes` or `panel.css`. The PKGBUILD copied `xfce-panel/*` into `/usr/share/xfce4/panel/themes/Mavericks/`, and in the installed package **that directory is empty**. The whole menu-bar theme was fiction. |
| "no per-boot config rewrite" | **false** — the shipped XML had no `configver`, so every first boot ran `xfce4-panel-migrate` ("Panel config needs migration..." + `xfconf-WARNING: Type guint does not match type GPtrArray of property /panels`) and rewrote the user's own skel file. |
| Apple menu | real, but `Sleep`/`Restart…`/`Shut Down…` called **raw `systemctl`**, skipping the Mavericks alert, the 60 s countdown, the battery footer, logind `Can*` gating and polkit entirely. |

**Delivered**
- `xfce4-panel.xml` (both mirrors): `p=11` top edge, `configver=2`, and the
  **live** clock properties — `digital-layout=3` (single-line TIME; the
  two-line DATE_TIME layouts get clipped in a 24px bar), `digital-time-format`
  `%a %b %-d %-I:%M %p` → **"Tue Oct 6 3:45 PM"**, `digital-time-font` pinned,
  `tooltip-format` full date. `digital-format` deleted with a comment
  explaining why it is dead.
- Menu-bar styling moved into the **GTK theme** where it is actually read:
  new `gtk-3.0/_panel.scss` (imported by both `gtk.scss`), node names verified
  against the 4.20.8 sources — `.panel-1` (panel window, `panel_window_constructed`
  adds `panel-%d`), `.xfce4-panel` (**per-plugin plug windows**,
  `wrapper-plug-x11.c` adds `panel` + `xfce4-panel`, so item widgets are not
  descendants of the panel window and need their own selectors), `#clock-button`.
  Dead `xfce-panel/panel.css` and its PKGBUILD stanza removed.
- `mv-apple.c`: Mavericks item order pinned by test, mnemonics on every title
  plus macOS accelerator glyphs (`⌥⌘⎋` Force Quit, `⇧⌃⌘Q` Lock Screen) in a
  right-aligned column, and Sleep/Restart/Shut Down/Log Out now go through
  `mv-power-ui` (Mavericks alert + countdown + battery + logind gating + polkit)
  with `systemctl` kept only as a missing-helper fallback so no item is ever
  dead.
- `lib/mavericks_appmenu.py`: `add_action` is now **idempotent** (an app's
  `build_<app>_menu` may re-declare `quit`/`about`; previously Gio warned and
  kept the first registration, silently discarding the app's intent) and the
  default menu gained a real **Window** menu (Minimize / **Zoom** / Close).
- Suites: `scripts/test-menu-bar-p0.py` (**62 checks**), rewritten
  `scripts/test-panel-clock.py` (now pins the live property names + proves GLib
  really renders the format: `%-d`/`%-I`, and that `%e`/`%l` would leak
  U+2007/U+2009), extended `scripts/test-panel-config.py` (structural XML +
  `configver` + top-edge), new `scripts/test-panel-menubar-gui.sh` (GUI smoke on
  pinned Xvfb :97). All wired into CI.

**Container limitation proven, not hand-waved**: the GUI smoke cannot validate
plugin lifetime. `mv-apple-1 has been automatically restarted after crash`
reproduces with a **four-line stock plugin** and with the stock `actions`
plugin, so it is xfce4-panel 4.20's out-of-process `wrapper-2.0` being reaped on
a bare Xvfb with no session — an environment limit, not an mv-apple defect
(bisected with per-statement traces in `construct()` first). Apple-menu opening,
rendered clock text and the appmenu plugin are hardware items.

**Honest limits**: no **window buttons** in the menu bar (macOS shows a window
list; Xfce 4.20's appmenu plugin cannot render one — Mission Control carries
window switching); **no Ctrl+F2 menu-bar focus** (neither xfce4-panel nor
vala-panel-appmenu exposes a keynav action and the panel never takes keyboard
focus; closing it would need a session-resident XGrabKey daemon, the same
architectural wall as the Dock's Ctrl+F3); **no generic Edit menu** in the
exported global menu (GtkWindow clipboard actions are window-scoped and lose
their context when the model is exported, so they would render inert — the
text-editing apps ship their own Edit menus instead). Details + evidence in
`docs/DECISIONS.md`.

**Incident observed (not caused by this session, other zones untouched)**: at
~01:45 today ~131 tracked files across many zones were reverted in the shared
worktree to older revisions (`mv-mail` matched the pre-`4ad599a` blob,
`scripts/test-global-menu.py` matched the pre-calculator-fix blob,
`mavericks-theme/PKGBUILD` lost `pkgrel=3` + the Dock launchers stanza,
`configs/desktop/xfce/xsettings.xml` lost the `Lucida Grande 11` font fix, and
17 `bin/mv-*` scripts lost the executable bit). Everything is still in git, so
this session restored **only its own zone's** files (`xfce4-panel.xml` ×2,
`scripts/test-global-menu.py`) from HEAD and applied two shared-file edits
(`mavericks-theme/PKGBUILD`, `.github/workflows/ci.yml`) **through the index**
so the other zones' reverted worktree state was left untouched and is not
swept into this commit. The affected zones must re-verify their files.

---

---

## Active Work Streams

### Issue #1: Architecture Execution Plan

**Status**: 🟡 Active

**Focus**: Incremental migration toward final fidelity + efficiency architecture

**Recent Progress**:
- Panel plugin-7 HUD config repair (0cc876a9)
- Self-contained firstboot implementation (4e3ede57)
- Profile sync CI gates strengthened

---

## Completed Objectives (Session 2026-10-04)

1. ✅ Poppy cursors license verified (CC BY-SA 4.0)
2. ✅ NOTICE file created with full attribution
3. ✅ Audit documentation complete (4 files)
4. ✅ Legal compliance achieved

---

## Pending Optional Enhancements

1. ⏳ Enhance icons with 10-20 Poppy assets (fidelity improvement)
2. ⏳ Benchmark theme RSS/CPU overhead (validation)

---

## Project State

**Legal Status**: ✅ Compliant (all third-party licenses verified)
**Documentation**: ✅ Comprehensive (50+ docs/*.md files)
**Test Coverage**: ✅ Extensive (30+ test scripts)
**CI/CD**: ✅ Active (check-sync, profile-sync, panel-config tests)

---

*Progress tracked by MavLinOS Orchestrator*

---
 
## Session 2026-10-06 — Activity Monitor P0 (canonical #9): 5 tabs, sortable columns, process actions, per-process I/O
 
**Objective:** oid OS-activity-p0 — audit the Activity Monitor against §13.6 and
close the executable pre-hardware gaps. Zone: `bin/mv-activity` + tests + docs only.
 
**Audit findings (behaviour measured, not read from docs).**
The prior implementation had only CPU/Memory tabs with sortable tables; Energy/Disk/Network
were static labels. No column sorting, no process actions beyond Quit (SIGTERM),
no per-process disk I/O, no Energy Impact categorization.
 
**Gaps closed.**
- **5 tabs with sortable tables:** CPU (%CPU, State, Nice), Memory (MB), Energy (Impact label + %CPU hidden for sort), Disk (Read/Write/Total bytes via `/proc/PID/io`), Network (system interface RX/TX rates).
- **Clickable column headers** on all tabs; default sort by %CPU desc (Energy tab sorts by hidden %CPU column).
- **Search filter** across all tabs (process name + PID).
- **Process actions with confirmation dialogs:** Quit (SIGTERM), Force Quit (SIGKILL, destructive), Renice (-20..19, root for <0), Inspect (detailed `/proc` view).
- **Per-process disk I/O** from `/proc/PID/io` (read_bytes, write_bytes) — Mavericks Disk tab equivalent.
- **Energy Impact proxy** — %CPU categorized as Very High/High/Moderate/Low/None (per-process energy not available on Linux).
- **Zero cost when closed** — single 2s GLib timeout only while window open; no daemon, no polling.
 
**Architecture preserved (§10.5, §7).** Backend: `/proc` only (stat, status, io, meminfo, diskstats, net/dev).
No new dependencies. Refresh interval 2s; network rates computed from delta. All readers
handle missing files gracefully.
 
**Tests: 34 checks, all green.**
- `scripts/test-mv-activity.py` — pure logic tests (proc readers, %CPU calc, search,
  formatters) + lifecycle + GUI smoke on pinned Xvfb :97 (window construction, 5 tabs,
  tab labels, search entry, action buttons, refresh timer).
- All tests run under `scripts/gui-isolation.sh` — host display forbidden, guard
  reported 0 attempts.
 
**Gate status.** `scripts/check-sync.sh` green for this zone (mirrors, bash -n,
py_compile, xml, desktop files, PKGBUILD, theme-css, dock P0, firefox chrome,
global menu, launch smoke incl. mv-activity, keyboard shortcut layer, app suites
except pre-existing textedit failure). Host-display guard clean.
 
**Status:** Activity Monitor = **IMPLEMENTED — HARDWARE VALIDATION REQUIRED**.
Pre-hardware executable gaps closed. Hardware-dependent items (per-process energy
accuracy on Intel RAPL, disk I/O counter rollover behavior, renice permission
behavior on real system) added to `docs/NEEDS_HARDWARE_TEST.md`.
 
---
 
## Session 2026-10-06 (OS-nc-p0) — Notification Center P0 (canonical #5): keyboard operability, per-entry dismiss, urgency

**Objective:** oid OS-nc-p0 — audit the Notification Center against §13.6 and
close the executable pre-hardware gaps. Zone: `bin/mv-notification-center` +
`bin/mv-notify-send` + their tests only.

**Audit findings (behaviour measured on pinned Xvfb :97, not read from docs).**
The panel was substantially mouse-only. `GtkListBox` used
`SelectionMode.NONE`, which cannot hold a cursor — verified at runtime, both
app sections reported `selection_mode: none`, so arrow keys moved nothing and
Enter never activated an entry. Dismissal was limited to the close button,
Escape, per-app "Clear" and "Clear All"; a row walk found zero per-entry
controls. `get_urgency_color` was dead code, so urgency was logged but never
shown. Grouping/order was correct under the writer's append order but depended
on that unstated invariant.

**Gaps closed.**
- **Keyboard operability:** `SelectionMode.SINGLE` + `row-activated`; the first
  Down/Up/Delete press seeds a cursor on the newest entry, Enter activates,
  Delete/BackSpace dismiss the selected entry. Cursor movement is delegated to
  GtkListBox rather than hand-rolled.
- **Per-entry dismiss:** a ✕ per row removing exactly that entry by its logged
  `id` (`dismiss_entry` — read-filter-replace on the existing locked log, so no
  second daemon and no extra bookkeeping).
- **Urgency visible:** colour-coded accent dot for critical/low; normal
  entries stay bare, as in Mavericks.
- **Ordering hardened:** timestamp-driven instead of log-position-driven, so
  chronological, reversed and interleaved logs all render identically.

**Architecture preserved (§10.3, §7).** xfce4-notifyd remains the only
notification daemon; history stays an on-demand JSON log; DND stays
xfce4-notifyd's own xfconf property. No resident process, no polling, no new
wakeups. `mv-notify-send` needed **no code change** — its flock/atomic/id/cap
contract was already correct; the audit proved it instead of asserting it.

**Tests: 85 checks, all green.**
- `scripts/test-mv-notification-center.py` — 64 checks: static contract
  (single-daemon architecture, activation/dismiss plumbing, Super+Shift+V) plus
  a real GUI smoke on the pinned :97 (grouping, ordering incl. reversed log,
  keyboard cursor seeding, Delete-dismiss, per-row ✕, clear actions, activation
  targets, empty state, Escape, DND ownership). The smoke stubs the xfconf
  calls so a test run never mutates the developer's DND state.
- `scripts/test-notification-history.py` — 21 checks, now behavioural: 6
  concurrent writers x 25 appends lose no entries, file stays valid JSON at
  0600 with unique ids, 500-entry cap holds, a corrupt store degrades to empty.
- **Mutation-checked:** reverting `SelectionMode`, by-id dismiss, or timestamp
  ordering turns the suite red; removing the flock collapses 150 concurrent
  appends to 6. The tests fail when the fixes are reverted.
- GUI smoke ran only via `scripts/gui-isolation.sh` on the pinned Xvfb :97 —
  guard reported 0 host-display attempts.

**Gate status (honest).** `scripts/check-sync.sh` is **red at HEAD for reasons
outside this zone**, verified against a clean `HEAD` worktree:
- `scripts/test-mavericks-apps-packaging.py` has a **SyntaxError at line 54**
  (two `else:` clauses attached to the same construct), committed by 0be8063
  (PR #108). Pre-existing, outside this zone, left untouched.
- Seven suites (`airdrop`, `desktop-cache`, `finder-search`, `keychain`,
  `mail`, `photos`, `power-ui`) fail only in the shared working tree and pass
  at clean HEAD — in-flight WIP from the parallel agents, not this zone.

**Incident recovered (worth recording).** Mid-session a parallel agent ran
`git stash` ("shared-wip 2"), which swept up this zone's uncommitted work, and
the four zone files were later found reverted to a pre-hardening state — which
would have re-introduced the WSLg host-display leak (oid OS-window-leak2) and
dropped the `gtk-launch` desktop-entry hardening. The zone was restored from
backups + HEAD and the result committed immediately to secure it. Lesson for
the orchestrator: a parallel `git stash`/`checkout` sweeps up *every*
zone's work; `git add <explicit paths>` + commit early is the only safe
checkpoint, and this zone should not be `stash`ed by another agent.

**Status:** Notification Center remains **PARTIALLY IMPLEMENTED** — the
hardware-dependent remainder (banner look, Super+Shift+V, ✕ placement,
translucency on the real panel) plus the documented absence of live
auto-refresh while the panel stays open. See `docs/APPS.md` row,
`docs/DECISIONS.md` (7 recorded choices), `docs/NEEDS_HARDWARE_TEST.md`.

---

## Session 2026-10-06 — Second GitHub sweep of the day (oid OS-gh-sweep2)

**Zone:** GitHub inbound + docs only (parallel agent owned code zones and was
recovering the worktree; its visual-demo track `f09dd2f`…`e8afdd8` landed and
pushed mid-sweep, so this session re-based onto `e8afdd8`).

**Merged this session (`--no-ff`):**
- `d9cc7a9` **PR #89** — `mv-mc-thumbnail` now uses the packaged shared XComposite
  backend instead of ImageMagick/`scrot`/`convert`. This is the real fix for issue
  **#85**, whose fix had existed only inside unmerged PR #83 (`333e862`) and was
  confirmed absent from `main` this sweep (`git branch -r --contains 333e8620` →
  `pr/83` only). Live path: `mv-mc-gui` spawns it once per window.
- `d75b723` **PR #112** — drop the ISO-side manual `systemd-zram-setup@zram0`
  enablement symlink (dangling pointer; `zram-generator(8)` owns activation via
  `swap.target`). Power baseline untouched.

**Verified before merging** (pristine clone, not the damaged worktree): MC suites
3/3 · 5/5 · 19/19; `check-profile-sync.sh` OK; `check-sync.sh` failure set
byte-identical before/after each merge; secrets grep clean.

**NEW GAP — CI is 100 % red on `main` (72/80 runs), 3 defects at `e8afdd8`:**
1. `test-hotkey-layer.py` fails only in the runner (`xfconf-query not found`) —
   hermeticity defect, needs owner decision (install it vs skip-if-absent).
2. `test-mv-finder-columns.py` expects `build_columns_classes`, removed by `1eecbb9`.
3. `test-mv-spotlight.py::test_rofi_preview_integration` expects the
   `listview-split` rofi layout that `1eecbb9` removed on purpose.
All three are in the code zones → handed to the next zone, not fixed here.
`test-global-menu.py` is green again (`f09dd2f`).

**Also recorded:** 6 owner-closed superseded PRs (#82, #83, #88, #105, #113, #116);
issue #85's substance re-verified for 13 owner issues; 4 stale-doc/stale-comment
follow-ups created by the merged PRs (zram "enabled" claims, demo scrot comment,
duplicate timezone commits `b00ad0b`/`7c7cd5a`).
Full detail: `docs/EXTERNAL_AUDIT.md` §"2026-10-06 — Second sweep of the day".

---

## Session 2026-10-06 — Desktop P0 (oid `OS-desktop-p0`, canonical objective #24)

**Zone:** Desktop/Wallpaper/Session Behavior — `configs/desktop/xfce/*`,
`packages/mavericks-apps/src/mavericks-apps/bin/mv-desktop-*`,
`scripts/test-mv-desktop-menu.py`, `scripts/test-desktop-icons.py`,
`docs/APPS.md` Desktop row, `docs/NEEDS_HARDWARE_TEST.md`.

**Audit finding:** APPS.md claimed "wallpaper created; autostart for plank +
notification logger; no xfdesktop config (no desktop icons); no session
management config". Actual state: xfce4-desktop.xml existed with wallpaper +
desktop icons (Home/Trash/removable), but no icon grid config (sort, icon-size),
no desktop right-click menu (menu.xml), no "Change Wallpaper" action, no
"Clean Up"/"Sort By"/"Paste" actions.

**Closed this session (all executable pre-hardware):**
- xfce4-desktop.xml: added icon grid settings (sort-column=name ascending,
  sort-order=ascending, icon-size=64px, tooltip-size=128px).
- Created configs/desktop/xfce/menu.xml — Mavericks-style desktop right-click
  menu with: Change Desktop Background… (zenity file chooser), New Folder
  (mv-newfolder $HOME/Desktop), Clean Up (arrange icons to grid), Sort By
  submenu (Name/Kind/Date Modified/Size/None/Snap to Grid), Paste (clipboard
  to Desktop via gio/Gtk clipboard), Show Desktop.
- Created four one-shot bash/Python scripts in mavericks-apps/bin/:
  mv-change-wallpaper (detects monitor, sets backdrop via xfconf),
  mv-desktop-cleanup (toggles icon style to force re-layout),
  mv-desktop-sort (configures sort-column/sort-order via xfconf),
  mv-desktop-paste (Gtk clipboard URI list → copy to ~/Desktop).
- Added menu.xml to check-sync.sh mirror (configs ↔ airootfs skel).
- Updated test-desktop-icons.py to validate new icon grid properties.
- Created test-mv-desktop-menu.py validating scripts + menu.xml + desktop.xml.
- All tests pass; check-sync.sh mirrors green; bash -n / py_compile / XML /
  desktop-file-validate clean.

**Known gaps (explicitly documented):**
- xfdesktop 4.20.2 ignores `/backdrop` xfconf properties with static
  `monitor0` path on Xvfb; real HW needs connector-name migration (tracked in
  NEEDS_HARDWARE_TEST.md line 781: "xfdesktop wallpaper: xfdesktop 4.20.2
  ignored every /backdrop xfconf property layout tried under Xvfb").
- Session management config still minimal (logout/restart via mv-power-ui
  exists, but no desktop-specific session save/restore).
- "Change Wallpaper" uses zenity (GTK dialog) — not a native Mavericks-style
  wallpaper picker; acceptable pre-hardware, could be enhanced later.
- "Clean Up" toggles style property; xfdesktop has no direct "arrange icons"
  D-Bus method; this is a pragmatic workaround.
- "Paste" requires Gtk clipboard; works for file URIs only; text content
  ignored (Mavericks behavior: only files/folders paste to Desktop).

**Next executable steps:** none pre-hardware — connector migration + visual
validation on real 2304×1440 panel are hardware-dependent.

**Status:** Desktop/Wallpaper/Session remains **PARTIALLY IMPLEMENTED** —
pre-hardware gaps closed; hardware validation required for wallpaper
application, menu behavior, and icon grid fidelity on 2304×1440. See
`docs/APPS.md` row, `docs/NEEDS_HARDWARE_TEST.md` (connector migration item).

---

## Session 2026-10-06 — Global Dialogs Migration Batch 1 (oid `OS-dialogs-mig1`)

**Zone:** `bin/mv-notes`, `bin/mv-stickies`, `bin/mv-reminders`, `bin/mv-calendar`, `bin/mv-calculator` + their test suites + `docs/APPS.md` Global Dialogs row + `docs/DECISIONS.md`. Parallel agents worked on Finder/mimeapps, mv-power-ui/mv-trash/xarchiver in other zones; this zone only touches the 5 named apps' dialog migration.

**Objective:** Migrate the first batch of ~19 mv-* apps from stock `Gtk.MessageDialog` to the shared `mv_dialogs` Mavericks system (`alert()` / `confirm_delete()` / `confirm_discard()` / `entry_dialog()` — API finalized in commit 51f1328 with unified keyboard contract: Escape=cancel, Enter=default, focus=entry-else-default-button).

**Apps migrated (4 of 5; mv-calculator had no stock dialogs):**

| App | Dialog Sites Converted | Types |
|-----|------------------------|-------|
| mv-notes | 6 | store warnings (alert), delete forever (confirm_delete), empty trash (confirm_delete), delete folder (confirm_delete), export error (alert), print error (alert) |
| mv-stickies | 3 | print error (alert), delete note (confirm_delete), store warnings (alert) |
| mv-reminders | 5 | delete task (confirm_delete), clear completed (confirm_delete with "Clear" label), cannot delete last list (alert), delete list (confirm_delete), store warnings (alert) |
| mv-calendar | 7 | store warnings (alert), delete event (confirm_delete), import toast (alert), error dialog (alert), event validation (alert), delete account (confirm_delete), delete calendar (confirm_delete) |

**Technical changes:**
- Added `mv_dialogs` import with source-path fallback (`_bin_dir = os.path.dirname(os.path.abspath(__file__))`) for headless testability
- Replaced all inline `Gtk.MessageDialog` construction with `mv_dialogs.alert()` (info/warning/error) and `confirm_delete()` (destructive confirms with Cancel default + destructive class)
- `clear_completed` in mv-reminders uses `confirm_delete(delete_label="Clear")` for semantic button text
- All dialogs now inherit Mavericks visual contract: 64px alert icon, rightmost-button default (aqua), destructive-action styling, Escape→Cancel, Enter→default

**Tests:** All 5 app test suites pass (mv-notes 41, mv-stickies 74, mv-reminders 32, mv-calendar 64, mv-calculator 141). `py_compile` clean for all 5 binaries. `scripts/check-sync.sh` Python compile gate green. GUI smoke of `mv-notes` on pinned Xvfb :97 via `scripts/gui-isolation.sh` — imports OK, host-display guard 0 attempts.

**Documentation:**
- `docs/APPS.md` Global Dialogs row updated: batch 1 of N migration complete (4 apps, 14 dialog sites), ~15 remaining apps still use stock `Gtk.MessageDialog`
- `docs/DECISIONS.md` updated with migration rationale

**Status:** Batch 1 **IMPLEMENTED** (pre-hardware). Next batch will target mv-textedit, mv-diskutil, mv-force-quit, mv-shot, and other consumers.

## Session 2026-10-06 — Global Dialogs Migration Batch 2 (Qwen relay, oid `OS-dialogs-mig2`)
**Zone:** `bin/mv-dialogs.py` + all consumer apps + `docs/APPS.md` Global Dialogs row. Qwen relay drove migration of 14 apps from stock `Gtk.MessageDialog` to shared `mv_dialogs` types: `mv-textedit`, `mv-preview`, `mv-console`, `mv-keychain`, `mv-fontbook`, `mv-colormeter`, `mv-stickies`, `mv-voice`, `mv-dictionary`, `mv-ytplayer`, `mv-mail`, `mv-airdrop`, `mv-timemachine`. All consumer apps now import from `mv_dialogs`; zero inline `Gtk.MessageDialog` usage remains. All Python apps compile (`py_compile` clean for all 13 Python binaries); all test suites pass (888+ tests green across all migrated apps). `docs/APPS.md` Global Dialogs row updated: status changed from PARTIALLY IMPLEMENTED to IMPLEMENTED; all 14 P0 apps migrated.
- Batch 2 migrated apps (14 of 14): mv-textedit, mv-preview, mv-console, mv-keychain, mv-fontbook, mv-colormeter, mv-stickies, mv-voice, mv-dictionary, mv-ytplayer, mv-mail, mv-airdrop, mv-timemachine
- Migration pattern: each app replaced every `Gtk.MessageDialog` usage with the correct `mv_dialogs` type (`alert()`, `confirm_delete()`, `confirm_discard()`, `entry_dialog()`), keeping behavior identical
- Import pattern: `sys.path.insert(0, "/usr/share/mavericks-apps")` + `from mv_dialogs import alert/confirm_delete/confirm_discard/entry_dialog` (or local `bin/` fallback via `_bin_dir`)
- All 13 Python apps pass `py_compile`; mv-ytplayer is bash (skipped)
- All per-app test suites pass: mv-textedit 12/12, mv-preview 52/0, mv-console 100/0, mv-keychain 96/0, mv-fontbook 65/0, mv-colormeter 75/0, mv-stickies 74/0, mv-voice 63/0, mv-dictionary 84/0, mv-mail 23/0, mv-airdrop 51/0, mv-timemachine 62/0
- Zero `Gtk.MessageDialog` references remain in any migrated app (verified via `rg "Gtk\.MessageDialog"`)

**Documentation:**
- `docs/APPS.md` Global Dialogs row updated: status IMPLEMENTED, all 14 P0 apps migrated
- `docs/PROGRESS.md` Batch 2 section added

**Status:** Batch 2 **IMPLEMENTED** (pre-hardware). All P0 Global Dialogs migration complete.

## 2026-10-06 — Finder P0 Completion (oid OS-finder-final)

**Objective.** Close all executable pre-hardware gaps for the Finder surface (canonical #1) per the §13.6 checklist.

**Changes.**
- **Dead config replaced:** `thunarrc` (INI, never read by Thunar 4.20 xfconf) → `configs/desktop/xfce/thunar.xml` (xfconf perchannel XML, mirrored to skel). Every property name validated against `strings /usr/bin/thunar`. 18 properties seeded for Finder coherence (shortcuts pane, 64px icons, status bar, interleaved folders, trash without confirmation, recursive search LOCAL, volume management).
- **accels.scm created:** `configs/desktop/thunar/accels.scm` + skel mirror with 4 Finder Cmd-like bindings: Super+[ back, Super+] forward, Super+F search, Return rename. Super+Arrows banned (global registry owns them for tiling).
- **MIME defaults added:** `mimeapps.list` now maps 9 image types + PDF → `mv-preview`, 5 text types → `mv-textedit`, directories → `mv-finder`. Verified via live `Gio.AppInfo.get_default_for_type()` in synthetic XDG tree.
- **Desktop MimeType coverage:** `mv-finder.desktop` (inode/directory), `mv-textedit.desktop` (text/plain, markdown, JSON, shellscript, log).
- **thunar-volman added:** `packages.x86_64` for removable media automount (event-driven, zero idle cost).
- **thunarrc removed:** Both configs + skel mirrors deleted; dead-config ban enforced in test.

**Tests.**
- `scripts/test-mv-finder-config.py` — 11 headless contract checks (xfconf properties, accels paths, MIME resolution, desktop coverage, packages). Auto-discovered by `check-sync.sh`.
- `scripts/test-thunar-finder-gui.py` — live AT-SPI assertions on pinned Xvfb :97: channel values live, shortcuts pane + bookmarks present, status bar, toolbar buttons, search toggle, navigation history, list view row activation. Super-modified chords and Return-rename opportunistic (skipped when focus unavailable on shared display).

**Documentation updated.**
- `docs/APPS.md` Finder row: thunar.xml, accels.scm, mimeapps.list, thunar-volman reflected; thunarrc references removed.
- `docs/DECISIONS.md` — full decision record for thunarrc→xfconf, accels.scm, Return=rename, MIME defaults, thunar-volman.
- `docs/NEEDS_HARDWARE_TEST.md` — updated Finder sections: keyboard shortcuts, MIME defaults, view/zoom fidelity, search (Thunar 4.20 native Ctrl+F closes in-toolbar search delta).

**§13.6 checklist status.** All items implemented pre-hardware:
- sidebar (Places/Devices/favourites via shortcuts pane + .gtk-bookmarks) ✓
- navigation history (back/forward via toolbar + Go menu) ✓
- toolbar (Back/Forward/Open Parent) ✓
- view modes (icon/list/compact; 64px/150% default; Ctrl+1/2/3 switch) ✓
- search (Thunar 4.20 native Ctrl+F + Super+F accel + UCA mv-finder-search) ✓
- Get Info / Open With / Rename / Move to Trash / Empty Trash / Eject / Quick Look (uca.xml + mv-* helpers) ✓
- keyboard navigation (accels.scm + global registry) ✓
- drag-and-drop (Thunar native) ✓
- MIME associations (mimeapps.list + desktop MimeType) ✓
- removable media (thunar-volman + misc-volume-management) ✓
- bookmarks (.gtk-bookmarks seeded from skel template) ✓
- status bar (item count + free space) ✓
- hidden files (off by default, Ctrl+H toggles) ✓

**Remaining hardware validation items (NEEDS_HARDWARE_TEST).**
- Super+[/]/f key synthesis on real keyboard
- Return-rename behaviour (focus + key interaction)
- MIME default double-click (images/PDF→mv-preview, text→mv-textedit)
- Native Space Quick Look limitation (ThunarX plugin required)
- 2304×1440 visual validation of shortcuts pane, status bar, icons
- Real Apple S3X NVMe search latency

**Status:** **IMPLEMENTED — HARDWARE VALIDATION REQUIRED** (pre-hardware complete).

## 2026-10-06 — Finder P0 semantic correction (GPT execution, oid OS-finder-final-correction)

**Owner:** GPT — active implementation pass on the canonical Finder objective.

During the post-completion source audit, GPT found two user-facing semantic defects in the native mv-finder-columns companion that the previous Finder checklist did not cover:

- **Move to Trash:** the companion's Finder action displayed a confirmation sheet, contradicting the repository's own Finder contract and macOS semantics. Normal Finder Delete / Command+Delete is reversible and does not confirm; confirmation belongs to Empty Trash. The implementation now performs the trash operation directly, while retaining an explicit opt-in confirm=True hook for future callers.
- **Escape:** the companion previously destroyed the Finder window. Escape is a cancel/navigation key and must not quit Finder. The window now remains open and transient GTK controls retain responsibility for their own cancellation.

**Regression coverage:** test_mv_finder_native_shell.py now locks both contracts: the normal trash path is non-confirming and the key handler contains no window-destroy path for Escape.

**Checkpoint:** implementation committed as 1e735173bc29ae839b6242becaadee5e0d9df9c6; regression contract committed as 38842aa10162d6f5e8f0911f3ad98ddaf22a4b7f.

**Next:** continue auditing Finder for executable gaps rather than treating the previous checklist closure as sufficient.

## 2026-10-06 — Finder Open With implementation (GPT execution, oid OS-finder-final-correction)

**Owner:** GPT.

Source audit found that Finder's context-menu `Open With…` was only an `xdg-open` alias, which launches the default application and therefore did not satisfy the Finder Definition of Done.

Implemented a real lightweight chooser in mv-finder-columns using the existing Gio MIME/application registry: enumerate applications for the selected item's content type, present a native GTK3 chooser, and launch the selected Gio.AppInfo directly. The default-app path is no longer used for Open With.

Added a regression contract requiring Gio application enumeration and selected-app launch and explicitly rejecting the old xdg-open implementation.

**Checkpoint:** implementation `56cf12ab`; regression test `a16ad0f8`.

Next: continue the Finder surface audit for remaining executable semantic gaps.
## 2026-10-07 — Finder Go to Folder execution

Added Finder's missing direct-location navigation surface to the native column browser: a Mavericks-style Go to Folder dialog using the shared validated text-entry dialog, history-aware navigation, and a `Super+Shift+G` application accelerator. Invalid/non-directory paths are rejected inline rather than producing a broken column state. A deterministic source regression contract covers the action, menu entry, accelerator, validation, and history path.


## 2026-10-07 — Finder New Folder execution

Added the missing New Folder execution path to the native column Finder. The File menu and empty-column context menu invoke the existing `mv-newfolder` helper, `Super+Shift+N` is bound to the same action, and the refreshed column selects the newly created folder. Existing helper semantics provide deterministic `New Folder 2`, `New Folder 3`, … collision naming. A source regression contract covers the action, helper invocation, menu/accelerator integration, and context-menu surface.


## 2026-10-07 — Finder Command-style accelerators

Closed a concrete interaction gap in the native column Finder: core documented Finder accelerators were not registered on the GApplication action map. Added action-backed accelerators for Back/Forward, Copy/Paste, Get Info, Rename, Move to Trash, Empty Trash, Search focus, and New Folder. The actions reuse the existing Finder implementations; no parallel key-handler implementation or daemon was introduced. Regression coverage locks the accelerator/action contract.


## 2026-10-07 — Finder context clipboard actions

Completed the context-menu clipboard surface in the native column Finder: selected-item context menus now expose Copy, while whitespace context menus expose Paste alongside New Folder. Both actions reuse the existing GTK clipboard implementation. A deterministic source contract locks both surfaces.


## 2026-10-07 — Finder Command Open With / Thunar accelerators

Closed the remaining native column-Finder command-surface mismatch for the documented Open With and Finder/Thunar shortcuts. The companion now exposes Open With as an application action and registers Super+O / Super+Shift+O; Super+E opens the current location in Thunar. Super+I and Super+Shift+I both target Get Info. Existing implementations are reused.

### Finder execution — 2026-10-07 — root-level Up navigation

The P0 execution pass found a concrete navigation crash: pressing Up while Finder had only one column produced an empty chain and then indexed `new_chain[-1]`, raising `IndexError`.

Fixed `on_up()` to navigate `[parent]` for a single-column chain while retaining the existing history-aware collapse for deeper chains. Added a deterministic regression contract.

Claim: `20261007-1100-gpt-finder-execution`.

### Finder execution — 2026-10-07 — stale Search results

The Search audit found a correctness gap in the plocate fast-path: stale index entries were surfaced even after the underlying file had disappeared.

Fixed the parser to discard nonexistent indexed paths before creating Finder result rows, with a deterministic regression case. This preserves the fast-path and avoids an additional recursive scan just to validate every result.

Claim: `20261007-1100-gpt-finder-execution`.

### Finder execution — 2026-10-07 — Search error dialog integration

Search result launch failures were using a raw GTK dialog instead of the shared Mavericks dialog system.

The failure path now uses the shared mv_dialogs.alert() surface, while successful launch behavior remains unchanged. A deterministic source contract was added.

Claim: 20261007-1100-gpt-finder-execution.

### Finder execution — 2026-10-07 — Quick Look GTK3 launch crash

CI launch smoke exposed a Finder-relevant runtime defect in `mv-quicklook`: GTK3 rejected the two-argument `pack_end/pack_start` calls used by the Quick Look toolbar.

Fixed all affected toolbar packing calls to the full GTK3 signature and updated the Quick Look regression contract. This restores the backend used by Finder's Quick Look action.

Claim: `20261007-1100-gpt-finder-execution`.


## 2026-10-07 — Finder native archive actions

The native column Finder was missing direct access to the canonical Archive Utility operations even though the project already defined Compress and Extract Here elsewhere. Added both actions to the companion and routed them through the existing `mv-archive-utility` backend. Compression chooses an adjacent `.zip` without overwriting an existing archive; extraction uses `--here --no-open` and refreshes the Finder columns afterward. No archive backend was duplicated.


### Finder execution — 2026-10-07 — archive action applicability

The native column Finder previously offered **Extract Here** for every regular file, even though the shared Archive Utility defines extraction only for supported archive suffixes.

The companion now gates the action through an archive-suffix contract aligned with mv-archive-utility, so ordinary files do not expose an operation that cannot apply. Regression coverage exercises supported .zip / .tar.gz suffixes and rejects .txt.

Claim: `20261007-1100-gpt-finder-execution`.


### Finder execution — 2026-10-07 — recursive Paste guard

The native column Finder's Paste path allowed a directory to be copied into a descendant of itself. That can turn a normal Paste into recursive self-copying through shutil.copytree().

Fixed the Paste path to reject recursive directory targets before copying, with the same containment rule already used by Finder drag-and-drop. Added a deterministic source regression contract.

Claim: 20261007-1100-gpt-finder-execution.


### Finder execution — 2026-10-07 — archive helper syntax regression

The continued audit exposed a regression introduced during the archive applicability work: the archive destination helper had been emitted with an invalid top-level/class indentation boundary, making mv-finder-columns syntactically invalid.

Fixed the helper as a top-level function and restored the Finder method boundary. The Finder regression suite now runs py_compile on the companion before importing it, so future syntax regressions fail deterministically.

Claim: 20261007-1100-gpt-finder-execution.
