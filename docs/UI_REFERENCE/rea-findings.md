# REA findings: TextEdit 1.9 and Calculator (10.9)

Source binaries (SHA256-verified, extracted from the running Mavericks guest
2026-10-16 via FAT share + tar, symlinks preserved):
- `TextEdit.app/Contents/MacOS/TextEdit`:
  `47ce7ec7e8151f4b64f4470314e61ee5f553f848234f2bf1978172d34cacf1a0`
- `Calculator.app/Contents/MacOS/Calculator`:
  `c2ff9f04f3188f802bd2b03bfc809b4a7175f0d240d8f13bf3cc262c0ea18445`
  (both match REA `target_sha256` — cross-checked, not trusted blindly).

REA `6.4.0`, provider `rea-artifact-graph v1` (no disassembler).
Summaries: `runtime/raw/rea/rea_te_summary.json` (108 selectors),
`runtime/raw/rea/rea_calc_summary.json` (52 selectors).

Conventions: **[NIB]** = REA static evidence, **[RT]** = nsinspect runtime
capture (`raw/textedit-doc/`, `raw/calculator-full-run-a.json`).
A mapping states both sides; neither side is promoted to the other.

## F1. TextEdit toolbar and ruler are code-constructed, not NIB-defined

**[NIB]** No `__NSInspectorBarView`, `__NSInspectorBarItemController`,
`NSRulerView`, `ScalingScrollView` or font/color control appears in any of
the 8 decoded TextEdit NIBs (full-text search over all nodes).
`DocumentWindow.nib` (31 objects, 3 connections) defines only the shell:
`NSWindowTemplate` + `NSView` + `NSClipView` + `NSCustomView` (text-view
placeholder). There is no `MainMenu.nib` at all.

**[RT]** The live document window shows `NSKVONotifying_ScalingScrollView`,
`__NSInspectorBarView` with 10 controls, traffic-light widgets — none of
which exist in any NIB.

**Consequence:** NIB analysis alone can never reveal the toolbar or ruler;
`nsinspect` live extraction is the only observation path (audit verdict:
retain). Conversely, anything below that IS in a NIB should be read from
REA, not re-derived.

## F2. Menu item → implementation selector mapping (TextEdit)

**[RT]** menu titles + enabled/state from `textedit-doc-blank.json` (166
items). **[NIB]** 108 implementation selectors. Joins established by title
semantics (titles are localised, selectors are not — the mapping is by
meaning, flagged as such):

| Runtime menu item | NIB selector | Notes |
|---|---|---|
| `Format/Text/Show Ruler` | `toggleRuler:` | implementation name; enabled=True at runtime |
| `Format/Make Rich Text` | `toggleRich:` | |
| `Format/Text/Copy Ruler`, `Paste Ruler` | `copyRuler:`, `pasteRuler:` | ruler clipboard exists as concept |
| `Format/Font/Show Fonts`, `Show Colors` (inferred) | `orderFrontFontPanel:`, `orderFrontColorPanel:` | panel commands |
| `Format/Font/*`, `Format/Text/Writing Direction/*` | `makeBaseWritingDirection*:`, `makeTextWritingDirection*:` (6) | |
| `Edit/Spelling and Grammar/*`, `Substitutions/*` | `toggleAutomatic*:` (7), `toggleContinuousSpellChecking:`, `toggleGrammarChecking:` | |
| `Format/Text/Wrap to Page`, `Allow Hyphenation` | `togglePageBreaks:`, `toggleHyphenation:` | |
| `Format/Make Vertical Layout` | `toggleLayoutOrientation:` | |

**Limitation (explicit):** selector *bodies* are unknown without a
disassembler — `toggleRuler:` names the implementation but its effects are
verified only through the runtime state comparison (F4), never assumed.

## F3. Calculator: NIB action inventory exceeds the runtime-visible set

**[RT]** `calculator-full-run-a.json` primary content tree exposes 7
distinct actions (`clear:`, `rpnDrop:`, `rpnExchange:`, `rpnRollDown:`,
`rpnRollUp:`, `_doScroller:`).

**[NIB]** 52 selectors including the full button set the runtime capture
does not show: `digit:`, `decimal:`, `enter:`, `handleOperatorPress:`,
`handleMemoryOperatorPress:`, `handleEEPress:`, `handleSecondFunctionPress:`,
`handleModePress:`, `handleBitManipulation:`, `toggleRPNMode:`,
`toggleSeparators:`, `toggleTape:`, `saveTape:`, `printTape:`, `clearTape:`,
`setPrecision:`, `selectInputMode:`, `selectAltDisplayMode:`,
`conversion*DidChange:` (3), `updateCurrencyRates:`.

**[NIB]** 163 `NSButton` + 163 `NSButtonCell`, 212 `NSNibControlConnector`,
636 `target_action` edges; control classes also include `NSTextField` (19),
`NSSegmentedControl` (2), `NSPopUpButton` (3), `NSMenuItem` (76).

**Consequence:** the runtime capture shows one mode's visible surface; the
NIB inventory defines the complete behaviour space (all modes incl. RPN,
programmer, conversion sheet). Mode coverage for future extraction should
be driven by this list, not by guessing buttons.

## F4. TextEdit state comparison (runtime, REA-assisted vocabulary)

Blank vs plain-text doc (`textedit-doc-blank.json` vs
`textedit-doc-with-text.json`):
- Window: `Untitled [550×468]` vs `te.txt [640×412]` — the document window
  resizes itself for content; geometry is state, captured per state.
- Content tree: identical classes (scroll + clip + overhangs + text view +
  2 scrollers); only frames differ.
- Frame tree: blank has `__NSInspectorBarView` (10 controls) + autosave
  button; text has `NSThemeDocumentButton` (proxy icon) and NO inspector
  bar — plain-text mode confirmed structurally, matching the absence of
  font selectors being *needed* (they remain *available* per F2).
- Controls: identical target/action pairs
  (`__NSInspectorBarItemController::_fontPopupAction:` etc. — 10 toolbar
  actions fully mapped, see Phase-3 analysis).
- Menus: differ ONLY in `Window/Untitled` vs `Window/te.txt` entries; all
  164 other items identical in enabled/state — menu state is stable across
  document states (one measurement each; repeat runs of blank confirm).
- Blank vs blank-repeat: content tree, frame tree identical; object
  addresses differ (expected, per-process).

## F5. Calculator unnamed NSPanel (Phase-3 §4)

**[RT]** `calculator-regression.json` window 3: `NSPanel`, title `""`,
frame `[430, 397, 420, 193]`, `vis=True`. The geometry matches Apple's
standard alert-panel slot, but the title is empty and no crash-reporter
involvement was recorded for this run (`exc=0`, clean quit path).

**[NIB]** Calculator NIBs contain `ConversionSheet.nib` (96 objects, 17
connections, `okayConvertSheet:`/`cancelConvertSheet:`) — a sheet, not a
free panel — and no free-floating untitled panel definition.

**Verdict:** unrelated to Calculator's application UI (no NIB definition,
empty title, alert-slot geometry). Most likely a transient system panel
captured mid-flight. Per instructions, no disproportionate effort spent;
recorded as an open item with the evidence pointer above.

## F6. Ruler status (Phase-3 §1)

`toggleRuler:` exists **[NIB]**; `Format/Text/Show Ruler` is enabled
**[RT]**; no `NSRulerView` in any NIB **[NIB]** or any capture **[RT]**.
Ruler visibility was NOT toggled in this milestone (no verified
actuation path without GUI/menu automation executes it — performing the
menu action programmatically via injected `sendAction:` is the planned
mechanism, unimplemented). Ruler structure, geometry and behaviour remain
**unresolved gaps**, explicitly not inferred.
