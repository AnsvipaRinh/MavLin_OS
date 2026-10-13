# UI Reference — Mavericks ground truth

**Purpose.** Single authoritative, data-first catalog of the *real* OS X 10.9 "Mavericks" UI/UX: colors, pixel metrics, typography, window chrome, controls, dialogs, menus and interaction behaviour. It exists so implementers never have to guess and never have to re-verify against macOS again.

**Hard rule (owner directive): the map is built from the code, not from pictures.**
Every fact below is derived from an artifact we can re-run: compiled `.nib` archives,
Mach-O Objective-C metadata, string tables and AppKit's own colour sections. Reading
screenshots (or OCR-ing them) is *not* part of the method; it produced guesses, and guesses
are exactly what this catalog exists to eliminate. Screenshots/recordings remain a
validation track for behaviour we cannot express statically (animation timing), never a
source of geometry or colour.

**How facts are stored (data-first).**

| Layer | File | Contents |
|---|---|---|
| Evidence (code) | `data/nib_geometry.json` | every decoded nib: windows, views, frames, sizes, fonts, menu trees, artwork names |
| Contract (code) | `data/ui-api.json` | ObjC class model per responsibility bucket (geometry, focus, keyboard, mouse, drawing, animation, window, control, menu, text, dragdrop) |
| Surfaces | `data/surfaces.json` | 1198 surfaces: window frames, required controls, menu items, artwork per surface — the assembly rules |
| Components | `data/components.json` | 15 prefabricated "skin + bones" pieces with a coverage report |
| Controls | `data/controls.json` | 14375 decoded cell objects of 38 NS*Cell classes: bezel/flags bitfields, images, titles, key equivalents |
| Asset geometry | `data/assets.json` | 15582 assets with pixel sizes: icon grid, chrome/toolbar art, retina pairs (headers only, no artwork) |
| Window geometry | `data/windows.json` | 1373 NSWindowTemplate records: designer rects, style masks, size frequencies |
| Palette | `data/palette.json` | 275 colours decoded from AppKit's `__color/__gray/__mac_color/__color_alpha` ramps |
| Wording | `data/terminology.json` | 3910 exact English strings of system apps (menus, alerts, buttons) |
| Rendering | `catalog/*.md` | generated from the data by `tools/uiref/render.py` (never hand-edit) |
| Validation | `tests/uiref/test_catalog.py` | fails on missing evidence, duplicate ids, md5 drift, docs drift, broken component contracts |

**Toolchain (all stdlib, reproducible on Linux):**

```
tools/uiref/extract-osx109.sh   installer DMG -> real /System tree (7z + bsdtar)
tools/uiref/nib_geometry.py    NSKeyedArchiver nib -> frames, fonts, menu trees
tools/uiref/machobjc.py        Mach-O __objc_classlist -> classes/methods/ivars/IMPs
tools/uiref/objc_index.py      class model -> responsibility index
tools/uiref/colors_decode.py   AppKit colour sections -> palette
tools/uiref/strings_extract.py Mach-O string literals -> terminology
tools/uiref/surfaces.py        nib inventory -> surfaces + assembly rules
tools/uiref/components.py      merge of the above -> component library
tools/uiref/uifuncs.py         per-method code profile (floats, immediates, colour refs)
tools/uiref/mvprobe.c          runtime probe (compiled from Linux, runs in the guest)
tools/uiref/http_collect.py    host<->guest file bridge over QEMU slirp
```

**Optional external tool: REA** (`npm i -g rea-agents`, installed at
`~/.local/npm-global/bin/rea`, v6.4.0). On Linux it can run `decode_interface_builder`
(nib/storyboard archives), `inspect_artifact`, `inspect_keyed_archive` and
`trace_dylib_resolution`; its native capabilities (`inspect_macho`, `observe_native_calls`,
`observe_native_ui`, `capture_native_ui_scenario`, `inspect_asset_catalog`) require a macOS
host. Used here as an independent cross-check of our nib decoder, not as the primary path.

**Reproduce the guest.** See `PROVENANCE.md`.

**Refresh flow.**

```
tools/uiref/extract-osx109.sh <installer.dmg> ~/vmwork   # code artifacts
tools/uiref/nib_geometry.py  ~/vmwork/sys --out docs/UI_REFERENCE/data/nib_geometry.json
tools/uiref/machobjc.py <AppKit|app binary> --out .../objc-<module>.json
tools/uiref/objc_index.py --dump ... --name <module> --out .../ui-api.json
tools/uiref/surfaces.py ~/vmwork/sys --geometry ... --out .../surfaces.json
tools/uiref/components.py --nib ... --api ... --probe ... --out .../components.json
tools/uiref/render.py && python3 tests/uiref/test_catalog.py
```