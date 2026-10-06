# MavLinOS visual direction — Mavericks 10.9

This document is the visual acceptance baseline for the desktop shell and shared GTK surfaces.

## Target

MavLinOS should read as **OS X 10.9 Mavericks**, not as a generic Linux desktop with an Apple logo. The target is the 2013 Aqua/skeuomorphic interface: restrained brushed-metal chrome, compact controls, muted blue selections, Lucida Grande-like typography, small traffic lights, translucent menu bar, and the dark 3D Dock.

## Reference characteristics

- menu bar is a thin, quiet light/translucent strip;
- window chrome is compact and mostly neutral gray;
- Finder toolbar is denser than modern GTK headerbars;
- content areas are white/light gray with strong text contrast;
- selections are muted blue, not saturated iOS blue;
- buttons are compact beveled controls, not large rounded modern pills;
- corner radii are small (generally 2–4 px);
- System Preferences uses a clean icon grid with large ~40 px icons and generous whitespace;
- Dock is dark/translucent 3D glass with large application icons and magnification;
- Launchpad is a wallpaper-backed translucent application surface, not an opaque near-black panel;
- shadows are soft and restrained; excessive glow, blur, and giant rounded cards are out of scope.

## Shared geometry tokens

- menu bar: 24 px;
- ordinary control height: ~22–26 px;
- small radius: 2–4 px;
- compact horizontal control padding: 8–12 px;
- primary system font target: Lucida Grande 11; when unavailable, use the closest installed sans-serif rather than shipping proprietary Apple fonts;
- primary selection: muted Mavericks blue around #6f8fbd, with white text;
- application surfaces: neutral gray/white, not iOS-style blue/gray palettes.

## Visual acceptance

Reject a new surface if it visibly introduces large pill controls, saturated iOS-blue controls, oversized rounded cards, dark modern glass panels, neon focus glows, excessive drop shadows, or mixed visual languages between adjacent windows without a strong Mavericks analogue.

The theme is the foundation. Individual applications may add historically accurate textures/materials where Mavericks actually used them (for example Calendar/Notes), but they must inherit the same typography, spacing, selection, dialog, and window geometry.

## Validation loop

Every visual milestone must be captured through the repository demo harness and compared against real Mavericks references. Functional correctness alone does not qualify a surface as visually complete.
