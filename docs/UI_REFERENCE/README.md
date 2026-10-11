# UI Reference — Mavericks ground truth

**Purpose.** Single authoritative, data-first catalog of the *real* OS X 10.9 "Mavericks" UI/UX: colors, pixel metrics, typography, window chrome, controls, dialogs and interaction behaviour. It exists so implementers never have to guess and never have to re-verify against macOS again.

**How facts are stored (data-first).**

| Layer | File | Contents |
|---|---|---|
| Evidence | `captures/*.png` + `captures/index.json` | Raw reference screens (1 pt == 1 px, 1600x900) with md5 + surface/state description |
| Facts | `data/palette.json`, `data/metrics.json`, `data/typography.json`, `data/behaviors.json`, `data/patterns.json` | Machine-readable facts, each with `evidence`/`source` + confidence |
| Rendering | `catalog/*.md` | Generated from `data/*.json` by `tools/uiref/render.py` (never hand-edit) |
| Validation | `tests/uiref/test_catalog.py` | Fails when evidence is missing, ids collide, hexes are wrong, or docs drift from data |
| Provenance | `PROVENANCE.md` | Exact guest image + hypervisor recipe (reproducibility) |

**Fact format (all data files).**

```json
{"id": "chrome.titlebar.height", "value": 28, "unit": "pt",
 "kind": "measured", "evidence": "cap.finder.list.default", "confidence": "high",
 "notes": "active window, unified toolbar"}
```

- `kind`: `measured` (sampled), `derived` (computed from another fact, see `deriv`), `literature` (documented behaviour, e.g. animation timing), `design` (MavLinOS implementation decision).
- `confidence`: `high` / `medium` / `low`.
- `deriv`: formula or list of source fact ids for derived values.

**Why not commit Apple binaries/assets (meta rule C5).** We extract *numeric and behavioural facts* from a locally-run reference guest. Captures in `captures/` are reference evidence kept inside the repo (fair-use style documentation, like measurements), but no Apple-shipped image, icon, font or binary file is ever copied into MavLinOS sources. GTK3/CSS/icons/fonts are always our own work derived from these numbers.

**Reproduce the guest.**

See `PROVENANCE.md` (image URL + hashes, QEMU command line, Clover config). Reboot of the reference guest is cheap; re-measuring is not.

**Refresh flow.**

1. Boot guest (PROVENANCE.md), drive the UI to the target state.
2. `tools/uiref/build_index.py <shots-dir>` -> refreshes `captures/index.json`.
3. `tools/uiref/measure.py add ...` or `extract_palette.py` -> updates `data/*.json`.
4. `tools/uiref/render.py` -> regenerates `catalog/*.md`.
5. `python3 tests/uiref/test_catalog.py` must pass.
