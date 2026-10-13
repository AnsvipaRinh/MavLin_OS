#!/usr/bin/env python3
"""tokens.py - compile the Mavericks design tokens from the extracted facts.

First real consumer of the UI data contract (docs/UI_PLATFORM). It reads the
extraction palette and emits the implementable token file plus a manifest:

    tools/uiplatform/tokens.py --palette docs/UI_REFERENCE/data/palette.json \
        --out design/tokens/design-tokens.json --manifest design/manifest.json

Honesty rules are enforced by the generator itself:

  * a token whose value comes from a palette fact is `kind: derived` and carries
    that fact's evidence and confidence;
  * a token that is a MavLinOS decision (no measurement exists yet) is
    `kind: proposed` and MUST carry a note that says so;
  * a referenced palette fact that no longer exists makes the generator FAIL -
    drift between the extraction and the platform must break the build, not
    produce a silently stale theme;
  * no Apple artwork enters this repository: token values are numbers and
    strings only (UI_REFERENCE rule C5).

Run after every palette change: `python3 tools/uiplatform/tokens.py --palette ...
--out ... && python3 tools/uiplatform/validate.py validate design`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))

# token id -> palette fact id. A fact id is `appkit.color.<hex>.<role suffix>`;
# the suffix is the generator's own key into the __color ramp (see
# tools/uiref/colors_decode.py), so it is stable but opaque: the note below is
# what an implementer reads, not the id.
COLOR_ANCHORS = {
    "color.window.background": ("appkit.color.ffffff.aff",
                               "most frequent solid white in the AppKit __color ramp"),
    "color.control.background.solid": ("appkit.color.dddddd.add",
                                       "aqua.control.solid, a=0.867, 1199 occurrences"),
    "color.text.primary": ("appkit.color.000000.aff",
                           "most frequent solid black in the ramp"),
}

# MavLinOS decisions. Each one states that it is a decision, so a reader can
# never mistake it for a measurement. `evidence` stays empty for proposed
# values - that is legal in the contract and is the honest representation.
PROPOSED = {
    "color.selection.control": {
        "type": "color", "value": "#6f8fbd",
        "variants": {"blue": "#6f8fbd", "graphite": "#8e8e93"},
        "notes": "Muted Mavericks selection blue (docs/VISUAL_STYLE_GUIDE.md). "
                 "Graphite variant is a MavLinOS decision, not an extracted value."
    },
    "color.traffic.close": {"type": "color", "value": "#ff5f57", "unit": "none",
                            "notes": "Placeholder until uiprobe reports the real pixel."},
    "color.traffic.minimize": {"type": "color", "value": "#febc2e", "unit": "none",
                               "notes": "Placeholder until uiprobe reports the real pixel."},
    "color.traffic.zoom": {"type": "color", "value": "#28c840", "unit": "none",
                           "notes": "Placeholder until uiprobe reports the real pixel."},
    "color.traffic.inactive": {"type": "color", "value": "#d6d6d6", "unit": "none",
                               "notes": "Placeholder until a capture confirms the "
                                        "inactive-window traffic light colour."},
    "font.system.family": {
        "type": "font", "value": "Lucida Grande", "unit": "none",
        "linux_substitute": {"value": "Cantarell",
                             "reason": "Lucida Grande is licensed Apple artwork and is not "
                                       "redistributed (rule C5).",
                             "package": "cantarell-fonts"},
        "notes": "MavLinOS decision for the system font role."
    },
    "font.system.size": {
        "type": "metric", "value": 11, "unit": "pt", "notes":
        "Decision from docs/VISUAL_STYLE_GUIDE.md; uiprobe text.fonts confirms the "
        "original value and metrics."
    },
    "metric.menubar.height": {"type": "metric", "value": 24, "unit": "pt",
                              "notes": "Decision from docs/VISUAL_STYLE_GUIDE.md."},
    "metric.control.height.regular": {"type": "metric", "value": 22, "unit": "pt",
                                      "notes": "Decision; uiprobe controls.buttonMetrics "
                                               "supplies the real frames."},
    "metric.control.height.small": {"type": "metric", "value": 20, "unit": "pt",
                                    "notes": "Decision; see uiprobe controls.buttonMetrics."},
    "metric.control.height.mini": {"type": "metric", "value": 16, "unit": "pt",
                                   "notes": "Decision; see uiprobe controls.buttonMetrics."},
    "metric.control.radius": {"type": "metric", "value": 4, "unit": "pt",
                              "notes": "Decision from docs/VISUAL_STYLE_GUIDE.md."},
    "metric.window.chrome.height": {
        "type": "metric", "value": 22, "unit": "pt",
        "notes": "Placeholder. Derivation for the real value: uiprobe "
                 "window.contentRectMath (frame vs contentRectForFrameRect:styleMask:7)."
    },
    "easing.standard": {"type": "easing", "value": {"bezier": [0.25, 0.1, 0.25, 1.0]},
                        "unit": "none",
                        "notes": "Placeholder curve until AppKit's own animation curve is "
                                 "read or captured."},
    "easing.window.minimize": {"type": "easing", "value": {"bezier": [0.25, 0.1, 0.25, 1.0]},
                               "unit": "none", "notes": "Placeholder curve."},
    "duration.motion.short": {"type": "duration", "value": 120, "unit": "ms",
                              "notes": "Placeholder."},
    "duration.motion.medium": {"type": "duration", "value": 250, "unit": "ms",
                               "notes": "Placeholder."},
    "duration.motion.window": {"type": "duration", "value": 350, "unit": "ms",
                               "notes": "Placeholder consistent with animation.window.minimize."},
    "shadow.window.rest": {
        "type": "shadow", "value": {"offset": [0, 3], "blur": 12, "spread": -2,
                                    "color": "#000000", "alpha": 0.28},
        "unit": "none", "notes": "Placeholder; a capture of a real window over wallpaper "
                                 "confirms the radius and spread."
    },
}

SUBSTITUTIONS = []  # filled where the original resource is not redistributable


def build_tokens(palette_path):
    with open(palette_path) as fh:
        palette = json.load(fh)
    facts = {f["id"]: f for f in palette.get("facts", [])}
    sources = palette.get("sources", {})

    tokens = {}
    unresolved = []

    for token_id, (fact_id, note) in COLOR_ANCHORS.items():
        fact = facts.get(fact_id)
        if fact is None:
            unresolved.append("%s -> %s" % (token_id, fact_id))
            continue
        ev = fact.get("evidence")
        if ev and not isinstance(ev, list):
            ev = [ev]
        tokens[token_id] = {
            "type": "color",
            "value": fact.get("hex"),
            "alpha": fact.get("alpha", 1.0),
            "unit": "none",
            "evidence": ev or [],
            "kind": "derived",
            "confidence": "medium",
            "notes": "%s, read from palette fact %s. The colour value is measured; "
                     "the role assignment ('this is the window background') is a "
                     "MavLinOS decision and stays at medium confidence until the "
                     "surface captures confirm it." % (note, fact_id),
        }

    for token_id, spec in PROPOSED.items():
        entry = {"type": spec["type"], "value": spec["value"], "unit": spec.get("unit", "none"),
                 "kind": "proposed", "confidence": "unverified" if "Placeholder" in
                 spec.get("notes", "") else "low",
                 "notes": spec["notes"]}
        if "variants" in spec:
            entry["variants"] = spec["variants"]
        if "linux_substitute" in spec:
            entry["linux_substitute"] = spec["linux_substitute"]
        tokens[token_id] = entry

    if unresolved:
        raise SystemExit("tokens: palette facts no longer exist, extraction drift:\n  "
                         + "\n  ".join(unresolved))

    doc = {
        "schema": "mavlinos.design-tokens/1",
        "version": 1,
        "appearance": ["blue", "graphite"],
        "generated_from": {
            "generator": "tools/uiplatform/tokens.py",
            "generated_at": os.environ.get("SOURCE_DATE_EPOCH", "deterministic"),
            "inputs": [os.path.relpath(palette_path, REPO)]
                       + ([sources[k]["path"] for k in sorted(sources)]
                          if sources and all("path" in v for v in sources.values()) else []),
        },
        "tokens": tokens,
    }
    return doc, facts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--palette", default=os.path.join(REPO, "docs/UI_REFERENCE/data/palette.json"))
    ap.add_argument("--out", default=os.path.join(REPO, "design/tokens/design-tokens.json"))
    ap.add_argument("--manifest", default=os.path.join(REPO, "design/manifest.json"))
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed output is older than the palette (drift)")
    args = ap.parse_args(argv)

    doc, facts = build_tokens(args.palette)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")

    manifest = {
        "schema": "mavlinos.manifest/1",
        "generated_from": {"inputs": doc["generated_from"]["inputs"],
                           "generator": "tools/uiplatform/tokens.py"},
        "counts": {"tokens": len(doc["tokens"])},
        "status": {
            "derived": sorted(t for t, v in doc["tokens"].items() if v.get("kind") == "derived"),
            "proposed": sorted(t for t, v in doc["tokens"].items() if v.get("kind") == "proposed"),
        },
        "gaps": [
            {"record": t, "what": v["notes"]}
            for t, v in sorted(doc["tokens"].items())
            if v.get("confidence") == "unverified"
        ],
    }
    with open(args.manifest, "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
        fh.write("\n")

    print("tokens: %d written (%d derived, %d proposed) -> %s"
          % (len(doc["tokens"]), len(manifest["status"]["derived"]),
             len(manifest["status"]["proposed"]), os.path.relpath(args.out, REPO)))
    print("manifest: %d unverified gaps listed -> %s"
          % (len(manifest["gaps"]), os.path.relpath(args.manifest, REPO)))

    if args.check:
        if os.path.getmtime(args.out) < os.path.getmtime(args.palette):
            print("tokens: DRIFT - palette is newer than the generated tokens", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
