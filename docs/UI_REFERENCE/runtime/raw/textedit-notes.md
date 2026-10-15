# TextEdit runtime capture — notes

Host: OS X 10.9 (13A603), TextEdit 1.9 (build 310).
Tool: `tools/uiref/nsinspect.c`, mode `full-capture`, launched through a guest
runner script so that `DYLD_INSERT_LIBRARIES` is set by the script instead of
being typed (the virtual keyboard cannot produce `_`).

## States

| State | Description | Result |
|---|---|---|
| A | TextEdit launched with no argument | captured, `textedit-launch-state-a.json` |
| B | TextEdit launched with a text document as argument | **not captured** |

State A is not an "empty application" state: TextEdit opens its blank
`Untitled` document window during launch, so state A already contains a real
document view tree, a real text view and a real application menu.

## State A facts (observed, not inferred)

- `pid 1099`, `window_count 2`, `primary_window_index 0`
- Primary window: `NSWindow`, title `Untitled`, visible, level 0,
  frame `[133, 208, 550, 468]` — a plausible centred document window
- Second window: `NSComboBoxWindow`, title `""`, not visible, frame `[0,0,0,0]`
  (an internal helper window, correctly not reported as primary)
- `views_visited 8`, `controls_found 2`, distinct view objects 8,
  duplicate visits 0, non-numeric geometry 0
- Content view tree classes:
  `NSKVONotifying_ScalingScrollView` -> `NSClipView` ->
  `_NSClipViewOverhangView` x2 + `NSKVONotifying_NSTextView`, plus
  `NSKVONotifying_NSScroller` / `NSScroller`
- Application menu: `NSMenu` with 7 top-level items, **166 menu items in total**,
  including `TextEdit` (11 items), `File` (21), `Edit` (23), each with
  `isEnabled` and `state` read live

These are runtime-observed objects; nothing here is derived from a NIB or from
source code.

## Menu capture defects found and fixed

Menu walking was added in this iteration and failed three times against the
real framework. All three are recorded because they are framework facts, not
style choices:

1. `-[NSMenu submenu]: unrecognized selector` — `submenu` exists on
   `NSMenuItem`, **not** on `NSMenu`. Querying it unconditionally raised an
   Objective-C exception that aborted the entire capture.
2. `-[NSMenu items]: unrecognized selector` — `NSMenu` has no `items` method
   either. The documented key-value key is `itemArray`.
3. The first `NSMenuItem` without a submenu (a leaf) still needs the same
   guard, so branching is done by `isKindOfClass:` rather than by trying the
   selector.

The working path: `NSMenuItem` -> `submenu` -> `itemArray`; a bare `NSMenu`
-> `itemArray` directly. Both are reached with `valueForKey:` so no
struct-return ABI is involved.

## Known gaps

- **State B is missing.** With a document passed on the command line the
  inspector reaches `main-thread: capture begin` and then produces no JSON
  (raw evidence: `textedit-with-text-state-b.raw`, 95 bytes of banner output
  only). The plain-launch state completes in the same runner, so the hang is
  specific to the document-present tree and is not yet diagnosed.
- One attempt at state B never ran at all: the command had to be typed into
  the guest and `_` renders as `-`, so `DYLD-INSERT_LIBRARIES` became
  `DYLD-INSERT-LIBRARIES`. All environment-carrying commands must go through
  the runner script on the share, never through typed input.
- Text content of the document is not extracted. Only the view hierarchy,
  geometry, control list and menus are in scope for this milestone.
- `controls_found 2` is low for TextEdit and is expected to grow once state B
  and the toolbar/ruler are covered.

## Comparison with Calculator

Both captures come from the same tool and the same host, so they are directly
comparable:

| | Calculator | TextEdit (state A) |
|---|---|---|
| primary window | `Calculator` | `Untitled` |
| windows | 4 | 2 |
| views visited | 29 | 8 |
| controls | 19 | 2 |
| application menu | not captured (added after) | 166 items, 7 top-level |

The menu extractor was introduced during this iteration, which is why
Calculator has no menu data yet; that asymmetry is a property of when each
capture ran, not of the applications.
