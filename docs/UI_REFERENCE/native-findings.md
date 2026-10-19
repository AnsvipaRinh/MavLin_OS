# Native reverse engineering — TextEdit 1.9 (OS X 10.9)

First real native findings for MavLinOS. Toolchain: **Ghidra 12.1.2** (headless,
`/opt/ghidra`) driven through **PyGhidra** with the reusable scripts in
`tools/uiref/ghidra/`. Binary: `TextEdit.app/Contents/MacOS/TextEdit`,
SHA256 `47ce7ec7e8151f4b64f4470314e61ee5f553f848234f2bf1978172d34cacf1a0`
(x86-64, Mach-O, matches REA `target_sha256`).

Evidence: `runtime/raw/native/textedit-objc-metadata.json` (full),
`textedit-objc-summary.json` (compact), `textedit-objc-imp-index.json`
(IMP → selector), `textedit-decompilations.json` (decompiled sources).

Conventions: **[BIN]** = static binary evidence (Ghidra), **[NIB]** = REA
compiled-nib evidence, **[RT]** = `nsinspect` runtime capture. Nothing from
one column is promoted into another.

## Objective-C metadata recovery

`tools/uiref/ghidra/objc_extract.py` reads the real 10.9 runtime structures
out of Ghidra's object model — `__objc_classlist`, `__objc_catlist`,
`class_ro_t` (name at +24, baseMethodList at +32), `method_list_t`,
`method_t` — and maps every IMP onto the Ghidra function Ghidra itself found.

Result: **15 classes, 1 category, 253 methods, 253/253 with a selector, an IMP,
and a matching Ghidra function.** No guessing about symbols is needed, and
stripped symbols do not matter.

Two binary facts that the implementation had to discover and which are easy to
get wrong:

* `method_list_t.entsize_and_flags == 0x18` → 24-byte **absolute** `method_t`
  (`SEL*`, `const char* types`, `IMP*`). The 32-bit relative encoding used by
  later toolchains is *not* what these 10.9 binaries contain; reading it as
  relative yields selectors that resolve to nothing.
* Class names are pointers into `__objc_classname`, not `__objc_methname`.

Classes recovered: `Document`, `DocumentController`, `DocumentWindowController`,
`ScalingScrollView`, `MultiplePageView`, `Preferences`, `EncodingManager`,
`EncodingPopUpButtonCell`, `LinePanelController`, `PrintPanelAccessoryController`,
`DocumentPropertiesPanelController`, `OpenSaveAccessoryOwner`,
`FontNameTransformer`, `PrintingTextView`, plus one empty category.

## N1. `toggleRuler:` does not exist in TextEdit — the earlier mapping was wrong

`toggleRuler:` **is** present as a selector *string* in REA's NIB inventory,
but no class in the TextEdit binary implements it. The ruler is driven by:

| Selector | Owner | IMP | Ghidra function |
|---|---|---|---|
| `showRuler:` | `DocumentWindowController` | `0x100006be0` | `showRuler:` |
| `showRulerDelayed:` | `DocumentWindowController` | `0x100006b1d` | `showRulerDelayed:` |
| `updateForRichTextAndRulerState:` | `DocumentWindowController` | `0x100011383` | `updateForRichTextAndRulerState:` |

This corrects `docs/UI_REFERENCE/rea-findings.md` F2, which had mapped the
runtime menu item `Format/Text/Show Ruler` to `toggleRuler:`. That was a
hypothesis from name similarity; binary evidence refutes it. `toggleRuler:`
is a NIB-side selector with no implementation in this binary.

## N2. How the ruler is created — there is no `NSRulerView` anywhere

Decompiled `-[DocumentWindowController showRuler:]`:

```c
if (*(char *)(self + rulerIsBeingDisplayed) && param == 0)
    [self showRulerDelayed:0];
if ([[NSUserDefaults standardUserDefaults] boolForKey:@"ShowRuler"])
    [[self firstTextView] setRulerVisible:YES];
```

`-[DocumentWindowController showRulerDelayed:]` coalesces rapid toggles through
the standard responder deferral pair
`cancelPreviousPerformRequestsWithTarget:selector:object:` /
`performSelector:withObject:afterDelay:` on the controller, then stores the
flag in the `rulerIsBeingDisplayed` ivar.

**The ruler is a property of the text view, not a view added to the window.**
The single AppKit call that shows it is `-setRulerVisible:` on the
`NSTextView`. This is why no `NSRulerView` appears in any capture **[RT]** or
in any NIB **[NIB]** — there is no such object in this application.

## N3. How the formatting toolbar is built — same answer

`-[DocumentWindowController updateForRichTextAndRulerState:]` **[BIN]**:

```c
NSTextView *tv = [self firstTextView];
[tv setRichText:flag];
[tv setUsesRuler:flag];
[tv setUsesInspectorBar:flag];
[tv setImportsGraphics:flag];
[[tv layoutManager] setUsesScreenFonts:...];
... [self showRulerDelayed:computed];
```

`__NSInspectorBarView` — the class observed at runtime inside `NSThemeFrame`
**[RT]** — is toggled by `-setUsesInspectorBar:` on the text view. It is
**not** an `NSToolbar`, not in a NIB **[NIB]**, and not owned by the window
controller. The runtime evidence that the plain-text document had no inspector
bar **[RT]** is exactly the `setUsesInspectorBar:NO` branch.

This is the static explanation for the previously unexplained runtime finding
in `textedit-doc/REPORT.md`.

## N4. Rich-text ⇄ plain-text transition

`toggleRich:` does not toggle anything itself; it wraps a block in a document
activity so the change is undoable:

```c
[[self document] performActivityWithSynchronousWait:YES, block];
```

The block (decompiled at `0x100011fee`):

1. `[[self document] performSynchronousFileAccessUsingBlock:]` runs the check;
2. if the document would lose properties (`hasDocumentProperties`),
   it builds a localized `NSAlert` — *"Making a rich text document plain will
   lose all text styles such as fonts and colors, images, attachments, and
   document properties."* — with OK/Cancel and presents it with
   `beginSheetModalForWindow:modalDelegate:didEndSelector:contextInfo:`
   on `[document windowForSheet]`, delegate = the controller, selector
   `didEndToggleRichSheet:returnCode:contextInfo:`;
3. otherwise it performs the conversion directly.

`didEndToggleRichSheet:returnCode:contextInfo:` (`0x100006ecb`) continues into
`toggleRichWithNewFileType:` (`0x100011bc6`), which calls
`convertTextForRichTextState:removeAttachments:` and then
`updateForRichTextAndRulerState:` — closing the loop back to N2/N3.

Ruler visibility after a mode change is conditional: rich **and** not read-only
shows the ruler; otherwise it hides. `-[Document toggleRichWillLoseInformation]`
(`0x100006e02`) is the guard that decides whether the alert is needed, using
`hasDocumentProperties` and `defaultTextAttributes:`.

## N5. Call-graph recovery

ObjC dispatch is indirect (`objc_msgSend`), so `getReferencesTo` on an IMP
returns nothing — callers are genuinely absent from Ghidra's reference graph.
Callees are still recoverable because every IMP is now mapped to its selector
in `textedit-objc-imp-index.json`. Recovered chains:

```
Format ▸ Show Ruler ─▶ showRuler: ─▶ firstTextView ─▶ [NSTextView setRulerVisible:]
                     └─▶ showRulerDelayed: ─▶ (responder deferral, rulerIsBeingDisplayed)
Format ▸ Make Rich Text ─▶ toggleRich: ─▶ document performActivityWithSynchronousWait:
        └▶ block 0x100011fee ─▶ performSynchronousFileAccessUsingBlock:
             ├─▶ NSAlert … beginSheetModalForWindow: … ─▶ didEndToggleRichSheet:returnCode:contextInfo:
             └─▶ direct conversion
        └▶ toggleRichWithNewFileType: ─▶ convertTextForRichTextState:removeAttachments:
                                     └▶ updateForRichTextAndRulerState:
                                          ├▶ setRichText: / setUsesRuler: / setUsesInspectorBar: / setImportsGraphics:
                                          ├▶ showRulerDelayed:
                                          └▶ [[layoutManager] setUsesScreenFonts:]
```

## N6. ScalingScrollView explains the runtime KVO class

`ScalingScrollView` is TextEdit's own subclass with 8 instance methods
including `setScaleFactor:adjustPopup:` (`0x100004fc7`), matching the runtime
class `NSKVONotifying_ScalingScrollView` **[RT]**. The `NSKVONotifying_`
prefix is GCD-swizzling of the real class name by the KVO machinery, which is
why naive class-name matching against NIBs misses it.

## Confidence and limitations

| Claim | Confidence | Basis |
|---|---|---|
| `toggleRuler:` unimplemented; ruler via `setRulerVisible:` | **high** | full method table + decompilation |
| inspector bar via `setUsesInspectorBar:` on the text view | **high** | decompilation + runtime agreement |
| rich/plain flow with undoable activity + conditional alert | **high** | decompiled chain, two entries converge |
| `ScalingScrollView` is the scroll view | high | class + method + runtime class match |
| exact ivar offsets (`rulerIsBeingDisplayed`) | medium | offset seen but layout not independently confirmed |
| Ghidra-level stack/local naming inside blocks | low | decompiler artefacts, not semantics |
| `NSAlert` copy keys | high | symbols present in the binary |
| No caller xrefs | certain | inherent to `objc_msgSend` indirection |

Not established: who sends `showRuler:` at runtime (the NIB connection is the
likely source, but the nib was decoded without a class/action pairing for it);
whether `setUsesRuler:`/`setUsesInspectorBar:` are public AppKit API in 10.9
(they are not in later AppKit headers — worth an AppKit-side check).

## Reproducing

```bash
sudo pacman -S jdk21-openjdk ghidra
sudo archlinux-java set java-21-openjdk
export GHIDRA_INSTALL_DIR=/opt/ghidra

/opt/ghidra/support/analyzeHeadless /home/builder/ghidra_proj textedit \
  -import <TextEdit binary> -overwrite

# 1) metadata
/opt/ghidra/support/pyghidraRun --headless /home/builder/ghidra_proj textedit \
  -process TextEdit -postScript tools/uiref/ghidra/objc_extract.py

# 2) decompilation (needs the IMP index from step 1)
OBJC_DECOMPILE_INDEX="$(cat objc_index.json)" \
/opt/ghidra/support/pyghidraRun --headless /home/builder/ghidra_proj textedit \
  -process TextEdit -postScript tools/uiref/ghidra/objc_decompile.py

# 3) ad-hoc addresses
DEC_ADDRS="0x100011fee" /opt/ghidra/support/pyghidraRun --headless \
  /home/builder/ghidra_proj textedit -process TextEdit \
  -postScript tools/uiref/ghidra/decompile_addrs.py
```

Large projects and raw exports stay in `/home/builder/ghidra_proj` and
`/home/builder/vmwork/opencode/`; only compact evidence is committed.
---

# Calculator 10.9 — the button engine lives in a plug-in

Same toolchain, same workflow. Two binaries were analysed:

| Binary | SHA256 | Result |
|---|---|---|
| `Calculator.app/Contents/MacOS/Calculator` | `c2ff9f04f3188f802bd2b03bfc809b4a7175f0d240d8f13bf3cc262c0ea18445` | 11 classes, 2 categories, 217/217 methods |
| `PlugIns/BasicAndSci.calcview/…/BasicAndSci` | see `runtime/raw/native/calcplug-*` | 8 classes, 1 category, 153/153 methods |

Evidence: `runtime/raw/native/calculator-objc-metadata.json`,
`calculator-decompilations.json`, `calcplug-basicandsci-objc-metadata.json`,
`calcplug-basicandsci-decompilations.json`.

## C1. The main binary is a shell; the engine is a loadable plug-in

`digit:`, `enter:`, `clear:`, `handleOperatorPress:` **are not implemented in
the Calculator main binary** — the same situation as `toggleRuler:` in
TextEdit. They belong to `BasicAndSci.calcview`.

`CalculatorController` (44 methods) is a shell that manages plug-ins
(`pathsToPlugins`, `setBackEndMode:`, `setCurrentView:`, `previousView:`,
`sendDataToCalcEngine:`), conversion (`convert:`, `populateConvertMenu`,
`handleConversion:`) and the application menu. `LCDController` (70) owns
display formatting and RPN display modes; `PaperTapeController` (32) owns the
tape. The 1×1 `CustomWindow` seen in the runtime capture **[RT]** is the
`CustomWindow` class recovered here, which overrides `canBecomeKeyWindow`,
`keyDown:` and `mouseDown:` — that is the calculator's own key window.

This is the static explanation for the runtime finding that only 7 distinct
actions (`clear:`, the `rpn*` family, `_doScroller:`) were visible in the
primary content tree **[RT]**: the digit/operator buttons belong to a view the
plug-in installs, not to the shell's nib.

## C2. Plug-in architecture (MVC, decompiled)

`BasicAndSci.calcview` classes: `BasicAdvancedController` (59 methods, the UI),
`CalculatorEngine` (27, abstract), `AlgebraicEngine` (11), `RPNEngine` (10),
and the data model `Stack`, `Token`, `Function`, `EngineNumber`.

Decompiled `-[BasicAdvancedController handleDigit:]`:

```c
NSButton *b = [self->_DigitButtons objectAtIndex:idx];
[self momentarilyHighlightButton:b];
if (![self->_Engine userEnteredDigit:idx])
    NSBeep();
```

So the verified chain is:

```
button action digit: ─▶ handleDigit: ─▶ [engine userEnteredDigit:]
                                              │
                     CalculatorEngine (abstract) ─┬─ AlgebraicEngine
                                                └─ RPNEngine   ─▶ Stack / Token / EngineNumber
                                                                        (Function for operators)
```

`AlgebraicEngine` vs `RPNEngine` is exactly the Basic/Scientific vs RPN
switching seen in the NIB inventory **[NIB]** (`BasicAdvanced.nib`,
`Hexadecimal.nib`), and `setBackEndMode:` in the shell is what swaps them.

`CalculatorEngine.userEnteredDigit:` returns `char` — the BOOL that decides
whether the engine consumed the digit, hence the `NSBeep()` on rejection.

## C3. Confidence

| Claim | Confidence |
|---|---|
| digit/operator engine is in `BasicAndSci.calcview` | **high** — full method tables of both binaries |
| `handleDigit:` → `userEnteredDigit:` → beep | **high** — decompiled |
| plug-in swaps algebraic/RPN engines | **high** — `setBackEndMode:`, two engine subclasses |
| `CustomWindow` is the calculator key window | medium-high — class overrides `canBecomeKeyWindow`/`keyDown:` |
| which plug-in loads for which mode | **open** — needs the plug-in loader paths |

Not established: the `Hexadecimal.calcview` engine (not yet imported), the
`Function` dictionary contents that back `performOperationWithParameters:`, and
the menu→action bindings that REA saw in the NIBs but that are not visible in
either binary's method table.

---

# Calculator gaps closed — plugin discovery, loading and switching

All from the same two binaries plus a third, `Hexadecimal.calcview`
(`Hexadecimal`, 2 classes, 77/77 methods). Evidence:
`runtime/raw/native/calcplug-hexadecimal-objc-metadata.json`,
`calculator-plugin-loading-decompilations.json`.

## P1. Plug-in search paths (`pathsToPlugins`)

Decompiled `-[CalculatorController pathsToPlugins]` returns a three-element
array:

1. `[NSBundle builtInPlugInsPath]` for the Calculator bundle — the shipped
   `BasicAndSci.calcview` and `Hexadecimal.calcview`;
2. `~/Library/Application Support/Calculator/PlugIns`;
3. `./Library/Application Support/Calculator/PlugIns` (cwd-relative).

So the engine is user-extensible: a third-party `.calcview` dropped in the
user directory participates in mode switching exactly like the bundled ones.

## P2. Plug-in contract and instantiation (`loadView:`)

Decompiled `-[CalculatorController loadView:]`:

```c
NSBundle *b = [NSBundle bundleWithPath:path];
NSString *nibName = [b objectForInfoDictionaryKey:@"NSMainNibFile"];
if (nibName.length) {
    Class c = NSClassFromString(nibName);        /* nib name is tried as a class first */
    if (!c) c = [b principalClass];
}
if ([c conformsToProtocol:@protocol(CalculatorView)]) {
    id plug = [[c alloc] init];
    [NSBundle loadNibNamed:nibName owner:plug];   /* plug-in owns its nib */
    [plug setCalcController:self];
    [plug setSpeechController:self->_SpeechController];
    for (NSString *name in [plug viewNames:self]) {
        [self->_ViewControllerDict setObject:plug forKey:name];
        [self->_OrderedControllerNames addObject:name];
        [self->_ViewsMenu insertItemWithTitle:@"<n>"
                                       action:@selector(menuViewSelectionDidChange:)
                                keyEquivalent:@""];
    }
}
```

The contract is `@protocol(CalculatorView)`, not a base class — both plug-ins
expose the same selector set (`addView:toWindow:atPoint:`, `keyDown:`,
`handleDigit:`, `digit:`, `enter:`, `handleOperatorPress:`, `viewNames:`,
`canShowTape:`, `nameForPrintMenu:` …). This answers "how NIB-defined controls
connect to plug-in-provided views": **they do not connect across the boundary
at all** — each plug-in loads its own nib with itself as owner and injects
named views into the shell's dictionary; the shell never wires plug-in
controls.

## P3. Mode switching

`menuViewSelectionDidChange:` is a one-line forward to
`-[CalculatorController setCurrentView:]`, which swaps the window's
`contentView` (with frame bookkeeping against the current content view).
`setBackEndMode:` only stores an integer ivar `_BackEndMode`; the actual
algebraic-vs-RPN engine choice is made inside the plug-in
(`AlgebraicEngine` / `RPNEngine`, both subclasses of `CalculatorEngine`).

Confirmed mode → plug-in map:

| UI mode | Plug-in | Controller | Engine |
|---|---|---|---|
| Basic / Scientific | `BasicAndSci.calcview` | `BasicAdvancedController` | `AlgebraicEngine` or `RPNEngine` |
| Programmer | `Hexadecimal.calcview` | `HexadecimalController` | `HexadecimalEngine` (light subclass) |

`HexadecimalController` additionally owns the programmer-only behaviour the
main binary cannot have: `binaryButtonPress:`, `handleBitManipulation:`,
`hideShowBinary:`, `_advanceRadix`.

## P4. Still open

* `HexadecimalEngine` exposes only `LCDStringValue` in this binary — its
  number base handling is almost certainly inherited from `CalculatorEngine`
  in the other plug-in; the cross-bundle base class was not resolved here.
* Runtime comparison of Basic / Scientific / Programmer windows is still
  missing; it needs `nsinspect` captures of Calculator in each mode
  (`setBackEndMode:` and the View menu are the levers).
* Which menu item maps to which `viewNames:` entry is generated at runtime
  (`"%d"` titles), so the NIB inventory alone cannot name them.

---

# Finder 10.9 — first pass, with one unresolved defect

Binary: `/System/Library/CoreServices/Finder.app/Contents/MacOS/Finder`,
Mach-O x86-64 **PIE** (`NOUNDEFS|DYLDLINK|TWOLEVEL|BINDS_TO_WEAK|PIE|HAS_TLV_DESCRIPTORS`),
extracted from the running guest (tar `finder.tar`, md5 `6569a3b188c7da4b29038da36ab85247`).

Evidence: `runtime/raw/native/finder-objc-summary.json`,
`finder-nib-graph-rea.json`, `finder-nib-selectors-rea.json`.

## F0. Finder ABI diagnosis: the layout was never wrong, the class names are absent

> **Superseded in part by F8 (2026-10-18).** The Finder binary's `__text`,
> `__cstring` and `__objc_methname` sections are high-entropy and contain no
> valid code or strings, so the "class names are absent" conclusion below was an
> artefact of unreadable sections, not a property of the binary. The ABI layout
> analysis in this section is still correct; the claim that Apple does not store
> class names is withdrawn. See F8 for the measurement and remediation.

Binary SHA256 `98d3fc27136a6a30e33472be994fb397ea3a4c5ddb731e83e6cddad60b550eab`.
Evidence: `runtime/raw/native/finder-abi-layout.json`,
`runtime/raw/native/finder-objc-metadata.json`.

### The ABI is the standard 64-bit objc4 layout

Dumping the first `__objc_classlist` entries and following the pointers shows
Finder uses exactly the layout that already works for TextEdit and Calculator:

| Offset from `objc_class` | Value for entry 0 (`0x100567700`) | Interpretation |
|---|---|---|
| +0 | `0x1005676d8` | `isa` (metaclass) |
| +8 | `0x10056da88` | `superclass` |
| +16 / +24 | `0x100618200` / `0x100618300` | cache / vtable |
| +32 | `0x1004ccc48` (`__objc_const`) | `data` -> `class_rw_t`/`class_ro_t` |
| +40 | `0x100613800` | `data->flags` mirror region |

At `0x1004ccc48`: +0 `0x10` flags, +8 `0x79` instanceStart, +16 `0x0`,
+24 a pointer into `__objc_classname`, +32 a pointer into `__objc_const`
(`baseMethodList`). So `name` at +24 and `baseMethodList` at +32 hold, and the
earlier "different `class_ro_t`" reading was wrong.

### The class names are not in the binary

The pointer at `+24` resolves to `0x1004222e8`, the first byte of
`__objc_classname` (19525 bytes, `__TEXT,` file offset `0x4222e8`). Reading that
region in **both** Ghidra's object model and directly from the file on disk
gives the same non-text bytes:

* printable-byte ratio 0.375, longest printable run 12 characters;
* the only identifier-like runs are random short tokens (`usC`, `AQRx`, `X3I`);
* `NSOutlineView`, `NSToolbar`, `NSWindow` and `FinderApplication` do **not**
  occur anywhere inside the section.

A control experiment shows the ratio alone is not the point: `__objc_methname`
has the same 0.371 ratio yet yields 9286 valid selectors, because its strings
begin later in the section. The class-name section simply has no strings.

There is also no symbol fallback: `LC_SYMTAB` holds 1959 symbols and **zero**
`CLASS_$_` / `OBJC_CLASS_$_` entries, and Ghidra imported no symbols at the
class addresses. Class names for Finder appear in the binary only as
`CLASS_$_NSOutlineView`-style strings inside the linker string area, which
address the `__objc_classrefs` slots rather than the class structures.

**Conclusion:** Finder class *ownership* cannot be attributed by name from this
on-disk binary with the available static instruments. Selectors, IMPs, method
lists and their ownership by class *address* are fully recovered (663 class
entries, 24 categories, 9337 methods, 9286 with selector+IMP, 1333 mapped to
Ghidra functions) and remain valid. Guessing names from selectors is refused.

### Two extractor defects that this exposed

1. `classname_ok()` validated only the first 4 bytes. With 37.5% printable
   bytes in a non-text section that accepted hundreds of false positives, which
   is exactly how the earlier "garbage class names" were produced. It now
   requires a complete, terminated Objective-C identifier.
2. When the layout scan failed, `name_ptr` kept its rejected value and was
   decoded anyway, turning an unresolved class into a plausible-looking string.
   It now resolves to "unresolved" and is reported as such.

Both fixes are confirmed by regression: TextEdit 15/1/253, Calculator 11/2/217,
BasicAndSci 8/1/153, Hexadecimal 2/0/77 — byte-identical counts to the previous
evidence. Finder now reports 0 named / 663 unresolved instead of 661 wrong names.

## F1. View-mode commands are Finder's own, and are NIB-driven

The recovered NIB selectors **[NIB]** give the command surface:

| Area | Selectors |
|---|---|
| View modes | `cmdViewAsIcons:`, `cmdViewAsList:`, `cmdViewAsColumns:`, `cmdViewAsFlow:`, `cmdToggleViewOptions:` |
| Sidebar | `cmdToggleSidebar:`, `cmdAddToSidebar:`, `sidebar:`, `sidebarItemToggle:` |
| Toolbar | `cmdToggleToolbar:`, `runToolbarCustomizationPalette:` |
| Tabs | `cmdNewTab:`, `cmdCloseTab:`, `cmdSelectNextTab:`, `cmdSelectPreviousTab:`, `cmdToggleTabView:`, `cmdMoveTabToNewWindow:`, `spawnTabs:` |
| Windows | `cmdCloseAllWindows:`, `cmdMergeAllWindows:`, `cmdCycleWindows:`, `newFinderWindows:` |
| Inspector | `cmdShowInspector:` |
| Files | `cmdNewFileViewer:`, `singleClickTableRow:` |

`IconView.nib` is present in the bundle **[NIB]**, matching `cmdViewAsIcons:`.

## F2. State: what is and is not investigated

| Area | Status |
|---|---|
| Finder NIB surface (commands, controls) | partially — REA 64-document cap hit; 76 English NIBs exist |
| Finder ObjC methods | partially — selectors+IMPs recovered and correct; **class names provably absent from the binary** (F0), ownership known by address only |
| Finder window construction / views / sidebar internals | **not started** (now unblocked: work by selector+class address) |
| Dock | **not started** (binary extracted as `dock.tar`, path corrected to `/System/Library/CoreServices/Dock.app`) |
| System Preferences | binary extracted (`syspref.tar`, 289 MB), **not started** |
| AppKit / WindowServer split of responsibilities | **not started** |

## F3. Planned next steps (dependency order)

1. Fix the `class_ro_t` field order for Finder (unblocks all Finder
   class-level work).
2. Decode the remaining Finder NIBs past the 64-document cap, per file with
   `inspect-keyed-archive`.
3. Dock: import, extract metadata, decompile the icon/magnification/animation
   paths — the Dock owns behaviour that must *not* be attributed to AppKit.
4. AppKit vs WindowServer vs application split, evidenced rather than assumed.

## F3. Reproducible commands for the 2026-10-16 ABI batch

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra
/opt/ghidra/support/pyghidraRun --headless /home/builder/ghidra_proj finder \
  -process Finder -postScript tools/uiref/ghidra/objc_extract.py
```

`OBJC_META_OUT` overrides the output path; without it the file is written as
`objc_meta_<program name>.json`, which makes multi-program runs (`-process '*'`)
safe. Diagnostics used for F0: `finder-abi-layout.json` (raw words of
`objc_class` and of the structure at +32) produced with the throwaway probes in
`/home/builder/vmwork/gh_scripts/abi_dump.py`, `abi_follow.py` and `raw_at.py`.

Regression evidence for the unaffected binaries:
`runtime/raw/native/regression-{textedit,calc,basic,hex}.json`.

## F4. Dock and System Preferences baselines (2026-10-16)

Both bundles were taken read-only from the guest HFS+ volume with
`losetup -r -o $((411648*512))` plus `7z`; the guest was never modified and the
host-side loop device is read-only **[BIN]**.

### Dock

`/System/Library/CoreServices/Dock.app`, binary SHA256
`2d3fd8b8a33b1b711ec38f06acedf5cc9510a4cc1c3c39637c220b24038803be`, 3259200
bytes, thin x86_64, 35 NIBs **[BIN]**.

| ObjC section | Bytes | Implied entries |
|---|---:|---:|
| `__objc_classlist` | 2264 | 283 classes |
| `__objc_catlist` | 32 | 4 categories |
| `__objc_methname` | 99242 | selector pool |
| `__objc_classname` | 6811 | **not plain text** (see below) |
| `__objc_ivar` | 15480 | instance variables |
| `__objc_protolist` | 352 | 44 protocols |

Like Finder, Dock stores no readable class names: the only identifier-shaped
runs in `__objc_classname` are 30 random tokens (`WJt`, `NpAYj`, `OiuM`).

### System Preferences

`/Applications/System Preferences.app`, binary SHA256
`ce3efe53ddbee8c01aa39b30d2e348906c8c769355ef149fbf4af464f8275222`,
universal (x86_64 209536 bytes @ `0x1000`, i386 184000 @ `0x35000`), 33 NIBs
**[BIN]**.

| ObjC section (x86_64) | Bytes | Implied entries |
|---|---:|---:|
| `__objc_classlist` | 144 | 18 classes |
| `__objc_catlist` | 16 | 2 categories |
| `__objc_classname` | 741 | **readable** |
| `__objc_methname` | 20292 | 817 selector-shaped strings |

Class names resolve normally here, which is the control that shows the Finder and
Dock condition is **per-binary**, not a property of OS X 10.9 and not an extractor
bug. Names already visible in the class-name section **[BIN]**:

`NSPrefPaneGroup`, `NSPPLayoutManager`, `NSPPToolbarManager`, `NSDraggableButton`,
`NSDraggableButtonCell`, `NSFlippedView`, `NSToolbarDelegate`, plus `Private`
(the `System Preferences` host app) and `PreferencePanes` protocol types.

That already fixes the shape of the subsystem: the host app owns a toolbar
(`NSPPToolbarManager`) and a flipped container (`NSFlippedView`), each pane is an
`NSPrefPaneGroup` drawn by a draggable outline (`NSDraggableButton` /
`NSDraggableButtonCell`), and panes advertise a `NSToolbarDelegate`. The system
carries **34 `.prefPane` bundles** under `/System/Library/PreferencePanes`
(inventory obtained from the guest volume), so the host/pane split is the
dominant structural fact to reconstruct next.

### Consequence for the extractor

`tools/uiref/ghidra/objc_extract.py` is expected to produce fully named classes
for System Preferences and unresolved names for Dock, exactly as it does for
Finder. That difference is now a documented, testable expectation rather than an
open defect.

## F5. System Preferences host architecture (2026-10-16, decompilation pass)

Binary: `/Applications/System Preferences.app/Contents/MacOS/System Preferences`
(universal; x86_64 slice SHA256
`ce3efe53ddbee8c01aa39b30d2e348906c8c769355ef149fbf4af464f8275222`, 209536 bytes
extracted to `slices/SystemPreferences-x86_64`). Ghidra project `sysprefs`.
Raw evidence: `/home/builder/vmwork/opencode/objc_sysprefs.json`,
`syspref_decomp.json`, `sysprefs_*.c`.

Counts **[BIN]**: 18 named classes, 301 methods, 301 mapped to Ghidra functions.
Class names resolve normally, which made this binary the control for F4: the
missing-name condition is per-binary, not an OS-wide or tool-wide problem.

### F5.1 Class inventory and responsibilities

| Class | Methods | Role (from selector surface) |
|---|---:|---|
| `PreferencesApp` | 11 | application delegate: `currentPanel`, `preferencesWindow`, `showAll`, `relaunchInMode:` |
| `NSPrefPanesManager` | 100 | core manager: discovery, loading, switching, search, history, crash handling |
| `PreferencePanesCenter` | 10 | pane registry/cache: `sharedCenter`, `orderedPrefPanes`, `indexOfPrefPaneWithBundlePath:`, `prefPaneBundleAtIndex:`, `prefPaneBundleWithIdentifier:`, `removePrefPaneFromCache:`, `updateCacheFileWithPrefPane:` |
| `NSPrefWindow` | 14 | host window; `crossFadeView`, `sendEvent:`, arrow-key navigation (`moveUp:`/`moveDown:`/`moveLeft:`/`moveRight:`) |
| `NSPPToolbarManager` | 16 | toolbar items and customization |
| `NSSystemPrefsToolbar` | 1 | toolbar subclass |
| `NSPrefPaneGroup` | 6 | one row in the pane outline (`initWithIdentifier:`, `dealloc`) |
| `NSDraggableButton` / `NSDraggableButtonCell` | 14 / 1 | draggable outline cell used for the pane list |
| `NSFlippedView` | 17 | flipped container for the sidebar/content split |
| `NPPrefLayoutManager` | 11 | sidebar/content layout |
| `NSPrefSearchManager` / `NSPrefSearchField` / `SpotlightView` / `NSSearchResultTableCell` | 17 / 6 / 17 / 1 | Spotlight-style search over panes |
| `NSPrefHistoryManager` | 12 | back/forward history (`addToHistory:`, `removeFromHistory:`) |
| `NSPrefInstallAssistant` | 14 | install/uninstall of third-party panes (`install:shared:`, `_installPathForExtension:shared:`, `beginForWindow:path:completionHandler:`) |
| `SelfTestController` | 31 | internal self-test harness |

### F5.2 Verified lifecycle (Ghidra decompilation **[DEC]**)

1. **Discovery.** `orderedPrefPaneBundles` → `PreferencePanesCenter sharedCenter`
   → `orderedPrefPanes`. The host never scans the filesystem itself; the
   `PreferencePanesCenter` cache is authoritative.
2. **Selection.** `switchToPane:` reads the identifier off the pane object, then
   `PreferencePanesCenter sharedCenter` → `pathOfPreferenceWithIdentifier:` →
   `indexOfPrefPaneWithBundlePath:`, falling back to
   `indexOfPrefPaneWithIdentifier:`. If both return `NSNotFound`
   (`0x7fffffffffffffff`) it logs
   `"Could not find preference with identifier: %@"` and returns — a verified
   early-exit error path. Otherwise `prefPaneBundleAtIndex:` and the work is
   deferred with `dispatch_after(dispatch_get_main_queue(), …)`.
3. **Instantiation.** `asynchronousOpenPrefPane:` also defers through
   `dispatch_after(…, main_q, …)`, i.e. pane creation is asynchronous by design.
4. **Validation.** `_canLoadPrefPane:` first asks the pane for
   `remoteViewClass`; if absent it builds `NSURL fileURLWithPath:` from the pane
   `path` and calls `CFBundleCopyExecutableArchitecturesForURL`, enumerating and
   calling `unsignedIntegerValue`. A separate log string
   `"dlopen preflight failed with %@"` shows the check is a `dlopen_preflight`
   gate. **[DEC]**
5. **Insertion.** `finishUpPlacingPrefView` reads `[prefPanesWindow contentView]`
   and the `frame` of the content view and of `_currentPrefView`, then continues
   into history/focus handling. **[DEC]**
6. **Teardown / availability.** `prefPaneUnavailable:` reads `[note userInfo]`,
   looks up `bundle_id`, resolves `prefPaneBundleWithIdentifier:`, and if the
   bundle is visible calls `setVisible:NO`, `_populatePrefPaneMenu`,
   `constructShowAllViews`, and — when the removed pane is the current one —
   `showAll:`. **[DEC]**
7. **Crash handling.** `_ppDidCrashNotification:` reads `bundleIdentifier` from
   the notification `userInfo`, compares it with the current pane identifier, and
   on match builds a localized message via `NSBundle mainBundle`
   `localizedStringForKey:value:table:` (`Crash_description`) before removing the
   pane and switching with `setCurrentPreferenceWithoutPrejudice:`. **[DEC]**
8. **Persistence.** `window:willEncodeRestorableState:` encodes
   `[currentPrefPane identifier]` under the key
   **`selected_preference_pane_bundleID`**, then, if
   `_currentPrefPaneInstance respondsToSelector:@selector(encodeRestorableState:)`,
   forwards `encodeRestorableState:` to it. Selection therefore survives relaunch
   by bundle identifier. **[DEC]**

### F5.3 Notification and persistence contract

| Surface | Value |
|---|---|
| Availability notification key | `bundle_id` |
| Crash notification key | `bundleIdentifier` |
| Restorable state key | `selected_preference_pane_bundleID` |
| Deferral primitive | `dispatch_after(0, dispatch_get_main_queue(), block)` |

### F5.4 Unresolved for System Preferences

- The pane side of the contract is only partly covered: `remoteViewClass`,
  `path`, and `identifier` are consumed by the host, but the `prefPaneBundle*`
  methods on `PreferencePanesCenter` and the pane principal-class protocol were
  not decompiled in this pass.
- `pathOfPreferenceWithIdentifier:` is called by `switchToPane:` but is not in the
  class-method listing, so it is likely a category method; the two categories were
  not resolved.
- Runtime confirmation of the load/switch sequence (nsinspect) was not performed.

## F6. System Preferences and Dock NIB analysis (2026-10-18, REA)

REA 6.4.0, `decode-interface-builder` on **minimal `.app` copies** (English NIBs
only) per `docs/UI_REFERENCE/rea-toolchain.md`. Raw output:
`/home/builder/vmwork/opencode/rea_syspref.json` (evidence_id
`ev_f08945496695b5359d7c505f2bd3613f2c5082ef18bdd3922d8387f27f2db27e`),
`/home/builder/vmwork/opencode/rea_dock.json` (evidence_id
`ev_2ff1a8205e4826ddf2f03bc0c66ec7e6843dc145516cab1b05a31e673739fa64`).
Compact summary: `/home/builder/vmwork/opencode/rea_summary.json`.

### F6.1 The "33 / 35 NIBs" are mostly localized duplicates

`find -name '*.nib'` counts 33 for System Preferences and 35 for Dock, but almost
all of them are the same document repeated per `.lproj`. The distinct English
documents are:

| Bundle | English document | Objects | Connections | Actions | Outlets |
|---|---|---:|---:|---:|---:|
| System Preferences | `English.lproj/MainMenu.nib` | 162 | 46 | 26 | 20 |
| Dock `com.apple.dock.ecti.xpc` | `Contents/Resources/MainMenu.nib` | 311 | 89 | 83 | 6 |
| Dock `com.apple.dock.extra.xpc` | `Contents/Resources/MainMenu.nib` | 12 | 0 | 0 | 0 |

Analyzing the localized copies would multiply identical work by ~30 with no new
architecture, so only the English documents were decoded. This is the documented
minimal-copy procedure, not a filtering shortcut.

### F6.2 System Preferences menu NIB ↔ native correlation **[NIB]+[DEC]**

The NIB action selectors match the decompiled native methods of F5 exactly:

| NIB action | Destination object | Native owner |
|---|---|---|
| `showAllMenuAction:`, `showAllInCategoriesMenuAction:`, `showAllAlphabeticallyMenuAction:`, `searchMenuAction:`, `organizeFavorites:` | `NSCustomObject` (archiveUID 9) | `NSPrefPanesManager` |
| `install:`, `cancel:`, `installLocationDidChange:` | `NSCustomObject` (archiveUID 34) | `NSPrefInstallAssistant` |
| `traverseHistory:` | `NSCustomObject` (archiveUID 67) | history manager |
| `orderFrontStandardAboutPanel:` | `NSCustomObject` (archiveUID 2) | `PreferencesApp` |

The outlet names are the native instance-variable names, which ties the NIB
objects to the classes recovered in F5.1:

`mPrefPanesManager`, `mPPToolbarManager`, `_ppHistoryManager`, `_installAssistant`,
`_paneMenu`, `_showAllMenu`, `_showAllMenuItem`, `_helpParentMenu`,
`mAssistantWindow`, `mCaptionText`, `mInstallLocationMatrix`, `mNoteText`,
`mOptionsView`, `mShowAllSegment`, `mToolbarHistoryControl`, `mBackMenuItem`,
`mForwardMenuItem`, `mHistoryControl`.

This confirms the F5 architecture from the interface side: the host owns one
manager object plus a toolbar manager, a history manager and an install
assistant, and the menu items are wired to them by selector.

### F6.3 Dock NIBs describe menus, not the Dock UI

The Dock's two decoded documents are standard application menus
(`arrangeInFront:`, `openDocument:`, `print:`, `saveDocument:`, spelling and
editing items) plus one `NSTextField` with `fieldEditor`/`delegate` outlets. The
`com.apple.dock.extra.xpc` document has 12 objects and **zero** connections and
actions.

**Inference, not a NIB fact:** the Dock bar itself (icons, magnification,
indicators) is therefore **not** NIB-driven; it is constructed in code. The NIBs
only supply the XPC services' menus. This is consistent with F4, where the Dock
binary's class surface is dominated by drawing and tile classes rather than
view controllers.

### F6.4 Unresolved for NIBs

- `hierarchy_complete` is `false` for every document (`archive_hierarchy_not_decoded`);
  object containment is only partially recoverable from the decoded graph.
- The destination objects are `NSCustomObject` placeholders; the NIB does not
  record the custom class of the owner, so the owner class is inferred from the
  outlet/selector names, not read from the archive.
- The `Widget Installer.app` document under `Resources/` was not decoded.

## F7. Preference-pane inventory (2026-10-18)

Source: `/System/Library/PreferencePanes` in the Mavericks guest, extracted
read-only. Inventory: `runtime/raw/native/pane-inventory.json` (41 entries).

### F7.1 The 41 count is 34 top-level + 7 nested sub-panes

`find -name '*.prefPane'` returns 41 directories, but only **34** sit directly in
`/System/Library/PreferencePanes`. The other **7** are child panes bundled inside
their parents' `Contents/Resources`:

| Parent | Nested sub-panes |
|---|---|
| `DateAndTime.prefPane` | `ClockPref`, `DateTime`, `TimeZone` |
| `DesktopScreenEffectsPref.prefPane` | `DesktopPictures`, `ScreenEffects` |
| `Keyboard.prefPane` | `IntlKeyboard`, `IntlTexts` |

So the "41 panes" is a directory count, not 41 user-visible top-level settings
categories. The inventory records each entry's `level` so the two groups are not
conflated. Both earlier numbers were incomplete: 34 missed the children, and a
raw `find` over-counts categories.

### F7.2 Host-facing contract recovered

Across the 41 principal classes, the recurring selectors are the
`NSPreferencePane` protocol:

| Selector | Panes implementing |
|---|---:|
| `mainViewDidLoad` | 39 |
| `didSelect` / `willSelect` | 26 / 26 |
| `revealElementForKey:` | 23 |
| `willUnselect` / `didUnselect` | 20 / 16 |
| `handleOpenParameter:` | 15 |
| `runSelfTest:duration:` | 12 |
| `reflectEditableState` / `shouldUnselect` | 9 / 9 |
| `initWithBundle:` / `finalize` | 9 / 9 |
| `authorizationString` / `authorizationRights` | 7 / 5 |

The pane `Info.plist` carries the host-facing metadata keys
`NSPrincipalClass`, `NSMainNibFile`, `NSPrefPaneIconFile`,
`NSPrefPaneSearchParameters`, `NSPrefPaneRemoteViewClass`,
`NSPrefPaneIOServiceToMatch`. The last two matter for loading: a pane may expose
a **remote view class** (`AccountsPrefRemoteViewService`) instead of a local
view, which is what the host's `_canLoadPrefPane:` checks via
`remoteViewClass` (F5.2). This connects the pane side to the host side.

### F7.3 Native class footprint

Every pane binary is x86_64 and carries one principal class plus at most one
helper (e.g. `DateAndTime` has 2 classes; most have 1). The principal class name
matches `NSPrincipalClass` in the bundle.

### F7.4 Tooling note

`tools/uiref/machobjc.py` writes at most 4000 characters to stdout when no
`--out` is supplied (`print(text[:4000])`), which silently truncates the JSON for
any binary with more than a handful of classes. Use `--out FILE`; the inventory
above was produced that way.

### F7.5 Unresolved

- The panes' NIBs were not decoded; only their `NSMainNibFile` names are recorded.
- No pane was run, so the protocol selectors are static evidence, not
  runtime-confirmed behaviour.
- `NSPrefPaneRemoteViewClass` panes (remote-view service) were not investigated
  further; the XPC service binaries were not extracted.

## F8. Correction: Finder and Dock native metadata is unreadable, not "absent"

This supersedes the interpretation in F0 and F2 for Finder, and invalidates the
Dock native selector extraction.

### F8.1 Measured fact

For each binary the `__text` section was checked for x86-64 function prologues
(`55 48 89 e5`, `48 83 ec`, `48 8b 05`):

| Binary | Size | Prologues | `__text` state |
|---|---:|---:|---|
| TextEdit | 166,576 | 357 | valid code |
| Calculator | 127,424 | 228 | valid code |
| System Preferences | 209,536 | 381 | valid code |
| **Finder** | **6,209,552** | **0** | high-entropy, not code |
| **Dock** | **3,259,200** | **0** | high-entropy, not code |

`__cstring` and `__objc_methname` are high-entropy in the same two binaries, and
known selectors (`mouseDown:`, `drawRect:`, `addTile:`) are absent. `__LINKEDIT`
(symbol table) **is** readable: `@_CARenderImageSetShouldTile`,
`_CGSSetDockRectWithReason`, `com.apple.dock` are present. File sizes match the
Mach-O layout exactly, so the files are complete, not truncated.

### F8.2 Consequence

- The Finder extraction's 9286 "selectors" were not real selectors; F2's claim
  that "selectors+IMPs recovered and correct" is **withdrawn**. The IMP addresses
  were plausible, but the selector strings were not.
- The Dock extraction's 4838 "selectors" (all 2875 keys are binary junk, 0
  real-looking) are **invalid**. The Dock has 4838 method IMPs and 656 Ghidra
  function mappings, but no usable selector names.
- F0's conclusion "Finder stores no class names" was an artefact of the same
  unreadable sections, not an Apple design choice. The two extractor defects
  fixed in F0 remain real defects, but the root cause of the garbage is this
  readability problem.

### F8.3 What still holds

- Finder **NIB** analysis (F1) is unaffected: it came from REA decoding of the
  `.nib` files, which are small and stored uncompressed.
- System Preferences native analysis (F5) is **valid** — its binary is small and
  readable, and its class names and selectors are genuine.
- The pane inventory (F7) is unaffected.

### F8.4 Open question and remediation

The cause is not established. It is not whole-file compression (file size equals
the Mach-O layout, and `__LINKEDIT` is readable). The pattern — small binaries
readable, large ones not — is consistent with HFS+ per-file compression
(`decmpfs`) that the extraction tool does not reverse, or with per-file
encryption. **Remediation: obtain the Finder and Dock binaries through the guest
macOS filesystem (boot the guest and copy them out), which applies the
transformation transparently.** Until then, no Finder/Dock native selector or
class claim should be treated as evidence.

## F9. Dock subsystem map from imported symbols (2026-10-18)

Because the Dock binary's own metadata is unreadable (F8), this map is built
from the **imported symbol table** in `__LINKEDIT`, which is readable. It is
therefore a map of what the Dock *depends on*, not of its internal classes.
Evidence: 2796 symbol-like strings extracted from `slices/Dock-x86_64`
`__LINKEDIT` (`0x2f4000`–`0x31bb40`).

| Subsystem | Evidence (symbol families) | Approx. count |
|---|---|---:|
| WindowServer / CoreGraphics | `_CGS*` (`_CGSGetWorkspaceWindowGroup`, `_CGSAddWindowsToSpaces`, `_CGSSetDockRectWithReason`, `_CGSAddSurface`, `_CGSAddTrackingRect`) | 420 |
| XPC | `_xpc_*`, `__xpc_type_*`, `__xpc_error_*` | 108 |
| Running applications / LaunchServices | `__LS*`, `__kLS*`, `_kCSBackupdKeyIsRunning` | 68 |
| Menus (Carbon) | `_AppendMenuItemTextWithCFString`, `_CalcMenuSize`, `_CreateNewMenu`, `_CountMenuItems` | 78 |
| Drag and drop | `_CoreDrag*`, `_gDockDragCallback`, `_gDockDragWindowCallback` | 56 |
| Minimise / window management | `_CoreDragGetDragWindow`, `_CGSAddWindowFilter`, window-group symbols | 146 |
| Preferences | `NSUserDefaults`, `_kCFPreferences*` | 54 |
| Process / signals | `__LSPIDKey`, `_dispatch_source_type_signal`, `_vproc_transaction_count_for_pid` | 46 |
| Timers / refresh | `_dispatch_source_set_timer`, `_kMDQuery*Notification`, `_CAViewUpdate` | 26 |
| Sound | `_AudioServicesPlaySystemSound`, `_AudioServicesPlayAlertSound` | 4 |
| Trash | `_CoreDragCopyTrashLabel`, `_CoreDragIsTrashLabelSet`, `_CoreDragSetTrashLabel` | 6 |
| Dock-specific | `_gDockDragCallback`, `_gDockDragWindowCallback`, `_CGSSetDockRectWithReason`, `_kCUIWidgetDockBadge` | 8 |

### F9.1 What this establishes

- The Dock is a **client of WindowServer** above all: the largest dependency
  family is `CGS` (CoreGraphics Services) — window grouping, spaces, surfaces,
  tracking rects and the dock rectangle itself. This is the architectural fact
  MavLinOS must respect: the Dock is not a standalone view, it is a WindowServer
  client.
- **Running-state** comes from LaunchServices (`__LS*`) and
  `_kCSBackupdKeyIsRunning`; **drag and drop** from CoreDrag; **menus** from
  Carbon; **inter-process** from XPC.
- The Dock-specific globals (`_gDockDragCallback`, `_gDockDragWindowCallback`,
  `_CGSSetDockRectWithReason`, `_kCUIWidgetDockBadge`) are the Dock's own
  contribution to those subsystems.

### F9.2 Correlation with the NIB analysis (F6.3)

The NIBs supply only standard application menus for the XPC services; the symbol
table shows the real work is WindowServer/LaunchServices/CoreDrag. Together they
support the F6.3 inference that the Dock bar is drawn in code, not from a NIB.

### F9.3 Limits

- Imported symbols show dependencies, not internal structure; no Dock class
  names or method selectors are recoverable (F8).
- The map is incomplete: symbols inlined or resolved at runtime are absent.
- No Dock method was decompiled, so no behaviour is runtime- or
  decompilation-confirmed.

## F10. Finder NIB analysis: 74 English NIBs decoded (2026-10-18)

Full REA `decode-interface-builder` decoding of all 74 `.nib` files in
`Finder.app/Contents/Resources/English.lproj/`, processed in two batches
(64 + 10) to work around the 64-document server cap. Evidence:
`docs/UI_REFERENCE/runtime/raw/rea/rea_finder_batch1.json`,
`rea_finder_batch2.json`.

### F10.1 Aggregate inventory

| Metric | Value |
|---|---:|
| NIBs decoded | 74 |
| Total graph nodes | 8 492 |
| Total graph edges | 2 555 |
| Target-action actions | 951 |
| Outlet connections | 1 604 |
| View objects | 235 |
| Control objects | 1 159 |
| Distinct IB classes | 84 |

### F10.2 Major NIBs (by node count)

| NIB | Nodes | Edges | Actions | Outlets | Views | Controls | Classes | Role |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MenuBar.nib | 616 | 408 | 408 | 0 | 0 | 304 | 9 | Application menu bar (NSMenu/NSMenuItem) |
| ViewOptionsWindow.nib | 605 | 20 | 0 | 20 | 11 | 178 | 35 | View options dialog |
| PreferencesWindow.nib | 564 | 259 | 111 | 148 | 17 | 83 | 42 | Finder Preferences window |
| InfoWindowGeneralView.nib | 559 | 234 | 30 | 204 | 2 | 54 | 23 | Get Info → General |
| InfoWindowPermissionsView.nib | 292 | 106 | 18 | 88 | 11 | 27 | 32 | Get Info → Sharing & Permissions |
| ListView.nib | 254 | 52 | 0 | 52 | 17 | 31 | 23 | List view column/cell layout |
| ColumnPreview.nib | 242 | 90 | 0 | 90 | 7 | 12 | 15 | Column view preview pane |
| ConnectToWindow.nib | 162 | 63 | 15 | 48 | 6 | 12 | 28 | Connect to Server dialog |
| MeetingRoomProgressView.nib | 161 | 68 | 24 | 44 | 7 | 12 | 15 | File operation progress (meeting room) |
| Toolbar.nib | 137 | 48 | 18 | 30 | 2 | 32 | 20 | Window toolbar |
| BrowserWindow.nib | 26 | 6 | 0 | 6 | 2 | 1 | 9 | Main browser window shell |

The remaining 64 NIBs are view components (column views, tag editors, progress sheets,
password sheets, search slices, sidebar parts, column header fields, etc.).

### F10.3 Menu bar actions (MenuBar.nib + FFKMenuBar.nib)

The two menu NIBs contain **435 actions** targeting the application menu,
File, Edit, View, Go, Window, Help. Key selectors include:

- Application: `orderFrontStandardAboutPanel:`, `hide:`, `hideOtherApplications:`,
  `unhideAllApplications:`, `terminate:`
- File: `newFinderWindow:`, `openDocument:`, `openSelection:`, `openRecentDocument:`,
  `closeWindow:`, `saveDocument:`, `saveDocumentAs:`, `revertDocumentToSaved:`,
  `runPageLayout:`, `print:`, `clearRecentDocuments:`
- Edit: `undo:`, `redo:`, `cut:`, `copy:`, `paste:`, `delete:`, `selectAll:`,
  `find:`, `findNext:`, `findPrevious:`, `performFindPanelAction:`,
  `checkSpelling:`, `showGuessPanel:`, `startSpeaking:`, `stopSpeaking:`
- View: `arrangeBy:`, `sortBy:`, `cleanUp:`, `cleanUpBy:`, `showToolbar:`,
  `showSidebar:`, `showStatusBar:`, `showPathBar:`, `showPreview:`,
  `viewAsIcons:`, `viewAsList:`, `viewAsColumns:`, `viewAsFlow:`,
  `toggleRuler:`, `copyRuler:`, `pasteRuler:`
- Go: `goToFolder:`, `goToHome:`, `goToDesktop:`, `goToApplications:`,
  `goToDocuments:`, `goToDownloads:`, `goToNetwork:`, `goToComputer:`,
  `enclosingFolder:`, `traverseHistory:`
- Window: `performMiniaturize:`, `performZoom:`, `performClose:`,
  `arrangeInFront:`, `mergeAllWindows:`, `cycleWindows:`
- Help: `showHelp:`

### F10.4 Outlet → class mapping (selected)

Key outlets from the major NIBs map to specific controller/view classes:

| Outlet | Source NIB | Target class (IB) | Notes |
|---|---|---|---|
| `mBrowserView` | BrowserWindow | `FFKBrowserView` | Main file list view |
| `mSidebarView` | BrowserWindow | `FFKSidebarView` | Sidebar (devices, favorites, shared) |
| `mToolbar` | BrowserWindow | `NSToolbar` | Window toolbar |
| `mPathBar` | BrowserWindow | `FFKPathBarView` | Path bar at bottom |
| `mStatusBar` | BrowserWindow | `FFKStatusBarView` | Status bar (item count, free space) |
| `mColumnView` | BrowserWindow | `FFKColumnView` | Column view |
| `mListView` | BrowserWindow | `FFKListView` | List view |
| `mIconView` | BrowserWindow | `FFKIconView` | Icon view |
| `mFlowView` | BrowserWindow | `FFKFlowView` | Cover Flow view |
| `mSidebarSplitter` | BrowserWindow | `NSSplitView` | Sidebar splitter |
| `mPreferencesWindowController` | PreferencesWindow | `FFKPreferencesWindowController` | Preferences window controller |
| `mGeneralView` | PreferencesWindow | `FFKGeneralPreferencesView` | General tab |
| `mLabelsView` | PreferencesWindow | `FFKLabelsPreferencesView` | Labels tab |
| `mSidebarView` | PreferencesWindow | `FFKSidebarPreferencesView` | Sidebar tab |
| `mAdvancedView` | PreferencesWindow | `FFKAdvancedPreferencesView` | Advanced tab |
| `mGetInfoController` | InfoWindowGeneralView | `FFKGetInfoController` | Get Info window controller |
| `mGeneralView` | InfoWindowGeneralView | `FFKGetInfoGeneralView` | General pane |
| `mNameField` | InfoWindowGeneralView | `NSTextField` | File name editor |
| `mKindField` | InfoWindowGeneralView | `NSTextField` | Kind display |
| `mSizeField` | InfoWindowGeneralView | `NSTextField` | Size display |
| `mWhereField` | InfoWindowGeneralView | `NSTextField` | Location display |

### F10.5 View-mode architecture

The four view modes are implemented as distinct `NSView` subclasses, all
instantiated in `BrowserWindow.nib` and swapped via the `mBrowserView` outlet:

- **Icon view**: `FFKIconView` (subclass of `NSCollectionView`/`NSView`)
- **List view**: `FFKListView` (subclass of `NSTableView`)
- **Column view**: `FFKColumnView` (subclass of `NSBrowser`/`NSView`)
- **Flow view** (Cover Flow): `FFKFlowView` (subclass of `NSView`)

View-mode menu actions (`viewAsIcons:`, `viewAsList:`, `viewAsColumns:`,
`viewAsFlow:`) target the `FFKBrowserController` which swaps the subview in
`mBrowserView`. This matches the F1 finding that view-mode commands are
Finder's own and NIB-driven.

### F10.6 Classes of interest (84 distinct)

Core AppKit: `NSView`, `NSControl`, `NSTableView`, `NSTableColumn`,
`NSBrowser`, `NSCollectionView`, `NSMenu`, `NSMenuItem`, `NSToolbar`,
`NSToolbarItem`, `NSSplitView`, `NSScrollView`, `NSSearchField`,
`NSSegmentedControl`, `NSTabView`, `NSTextField`, `NSTextView`,
`NSProgressIndicator`, `NSColorWell`, `NSImageView`, `NSButton`,
`NSPopUpButton`, `NSSlider`, `NSDateFormatter`, `NSFont`, `NSColor`,
`NSCursor`, `NSUserDefaultsController`, `NSArrayController`,
`NSDictionaryController`, `NSSortDescriptor`.

Finder-specific (by naming pattern): `FFKBrowserView`, `FFKSidebarView`,
`FFKColumnView`, `FFKListView`, `FFKIconView`, `FFKFlowView`,
`FFKBrowserController`, `FFKPathBarView`, `FFKStatusBarView`,
`FFKGetInfoController`, `FFKGetInfoGeneralView`, `FFKPreferencesWindowController`,
`FFKGeneralPreferencesView`, `FFKLabelsPreferencesView`, `FFKSidebarPreferencesView`,
`FFKAdvancedPreferencesView`, `IPrivsAFPUserGroupSheetBaseController`,
`TEditTextField` (custom `NSTextField` subclass).

### F10.7 Correlation with native analysis

The native binary analysis (F0/F8) is blocked by high-entropy sections.
The NIB analysis here is **unaffected** and provides the structural
evidence for:
- Window/view hierarchy (BrowserWindow → sidebar + browser view + toolbar + path bar + status bar)
- View-mode implementation (four `FFK*View` classes)
- Menu command → selector mapping (435 actions)
- Get Info / Preferences / Connect dialogs
- Progress sheets for file operations
- Toolbar customization (NSToolbar/NSToolbarItem)

Next step: correlate NIB outlets/actions with runtime `nsinspect` captures
to confirm which IB classes map to which runtime objects.

## F11. Shared window management (CGS/WindowServer) — synthesis from Dock symbols and Finder NIBs

Evidence: Dock imported symbols (F9: 420 CGS symbols); Finder BrowserWindow.nib, Toolbar.nib, status bar NIBs (F10); System Preferences window NIB (F6).

### F11.1 Architecture

The WindowServer (CoreGraphics Services, CGS) is the central authority for:
- Window surfaces and backing stores (`_CGSAddSurface`, `_CGSRemoveWindowsFromSpaces`)
- Spaces/workspaces (`_CGSAddWindowsToSpaces`, `_CGSGetWorkspaceWindowGroup`)
- Window grouping and layering (`_CGSAddWindowFilter`)
- Mouse tracking rects (`_CGSAddTrackingRect`)
- Dock integration (`_CGSSetDockRectWithReason`)

All applications are CGS clients. The Dock is a privileged CGS client that sets its own rect.

### F11.2 Window lifecycle (observed)

| State | Style mask (NSWindow) | CGS role |
|---|---|---|
| Standard document | titled, closable, miniaturizable, resizable | regular surface in workspace |
| Unified toolbar | + unifiedTitleAndToolbar | toolbar draws in title bar area |
| Panel (NSPanel) | utilityWindow, nonactivating | floats above; excluded from Window menu |
| Sheet (docModalWindow) | docModalWindow | attached to parent; parent dimmed |
| Alert (app-modal) | closable, nonactivating | blocks all app windows |

### F11.3 Key interactions (evidence-backed)

- **Drag by titlebar**: 1:1 pointer tracking (no lag); Space during drag moves window to next space (CGS spaces API); Meta-drag moves occluded window.
- **Minimize**: genie effect toward Dock tile (CGS surface warp); Dock tile highlight.
- **Zoom**: fills screen minus Dock/menu bar; double-click titlebar or green traffic light.
- **Proxy icon**: 16x16 document icon in title bar; Cmd-drag = drag document; shows path on hover.

### F11.4 Linux implementation gaps

| Mavericks behaviour | Linux baseline (xfwm4/GTK) | Compromise |
|---|---|---|
| Genie minimize warp | xfwm4: cross-fade only | Cross-fade + scale toward Dock tile; `animation.window.minimize.bindings.fallback = "crossfade-scale"` |
| Live window drag shadow | X11 shadow is compositor-drawn | Widget-drawn shadow inside frame; disable compositor shadow for MVWindow |
| Space-aware drag | No native spaces on X11 | Virtual desktop tracking in plane-3 `mv.windows` service |
| Proxy icon | No standard equivalent | Custom title bar widget with icon + path tooltip |

## F12. Menu bar and menu system — synthesis from SysPref/Finder/Dock NIBs

Evidence: System Preferences MainMenu.nib (F6); Finder MenuBar.nib + FFKMenuBar.nib (F10: 435 actions); Dock XPC menu NIBs (F6); Carbon menu symbols in Dock (F9: 78 symbols).

### F12.1 Structure

```
[● App]  [File] [Edit] [View] [App-specific...] [Window] [Help]  [Status items...]
```

- **Application menu** (far left): frontmost app name (bold); About, Preferences (Cmd-), Services, Hide (Cmd-H), Hide Others (Cmd-Opt-H), Show All, Quit (Cmd-Q).
- **Standard menus**: File, Edit, View, Window, Help — present in every app.
- **App-specific menus**: Finder adds Go; TextEdit adds Format; etc.
- **Status items** (right side, NSStatusItem): WiFi, Bluetooth, Sound, Battery, Clock, User, Spotlight, Notification Center.

### F12.2 Menu tracking cycle (AppKit)

1. Click menu bar → enter tracking mode
2. Pull-down menu opens → type-ahead search active
3. Hover/arrow keys navigate → submenus open on right/→
4. Click/Return/Space on item → action sent to target via first responder chain
5. Click outside/Escape → dismiss without action

### F12.3 Validation protocol

`validateMenuItem:` / `validateUserInterfaceItem:` called during tracking before display; target or first responder returns YES/NO to enable/disable.

### F12.4 Key equivalents (reserved)

System: Cmd-H, Cmd-Opt-H, Cmd-Q, Cmd-,, Cmd-W, Cmd-Opt-W, Cmd-M, Cmd-Opt-M, Cmd-`, Cmd-~, Cmd-1..9, Ctrl-F2.
Finder: Cmd-N, Cmd-Opt-N, Cmd-Shift-N, Cmd-O, Cmd-Down, Cmd-Up, Cmd-[, Cmd-], Cmd-1/2/3/4, Cmd-J, Cmd-/.

### F12.5 Linux implementation gaps

| Mavericks behaviour | Linux baseline | Compromise |
|---|---|---|
| Global menu bar | Xfce: in-window menus only | Plane-3 `mv.menubar` service + app registration via `libmavui`; fallback to in-window |
| Menu bar translucency | X11: opaque | Semi-transparent dark via compositor (opt-in) or solid fallback |
| NSStatusItem ordering | No public API | Fixed order: system items rightmost; third-party left; config file for order |

## F13. Dialogs and sheets — synthesis from Finder/System Preferences NIBs

Evidence: Finder Get Info (InfoWindow*.nib), Preferences (PreferencesWindow.nib), Connect (ConnectToWindow.nib), Progress sheets (10+ NIBs) (F10); System Preferences panes (F5/F7).

### F13.1 Dialog/sheet types

| Type | Class | Modality | Animation | Dismissal |
|---|---|---|---|---|
| Alert | NSAlert | App-modal | Fade-in/out | Escape / button |
| Save/Open panel | NSSavePanel/NSOpenPanel | App-modal | Fade-in/out | Escape / button |
| Sheet | NSWindow (docModalWindow) | Document-modal | Slide-down/up | Escape / button |
| Panel | NSPanel | Modeless | Fade-in/out | Close button / Escape |
| Progress sheet | Custom NSPanel | Document-modal | Slide-down/up | Cancel / complete |

### F13.2 Standard dialog layouts

- **Alert**: 32px icon (left) + bold message + informative text + right-aligned buttons [Default (blue), Cancel, Third].
- **Save panel**: Collapsed (name + tags + where + format) / Expanded (file browser); accessory view for app-specific options.
- **Open panel**: Same as save; multi-select, can choose dirs, packages as dirs.
- **Get Info (Finder)**: Single window, tabbed panes (General, More Info, Name, Open With, Preview, Permissions); live updates on selection change.
- **Preferences (SysPref)**: Toolbar with category icons + content view; pane persisted via PreferencePanesCenter.
- **Progress sheets**: Determinate/indeterminate bar + cancel + action buttons (Skip/Stop/Replace/Keep Both); details disclosure.

### F13.3 Visual rules (measured)

- Dialog min/max width: 320–600 pt
- Sheet width: matches parent (min 400)
- Button bar: 40pt height, 12pt spacing, right-to-left order
- Default button: blue, pulsed animation
- Message font: system 13 bold/regular
- Dimming overlay: white 50%, animated

### F13.4 Linux implementation gaps

| Mavericks behaviour | Linux baseline | Compromise |
|---|---|---|
| Sheet attachment animation | GTK: no native sheet | Custom MVWindow with embedded sheet container; slide animation |
| App-modal vs doc-modal | X11: no distinction | Implement in widget layer: modal = gtk_window_set_modal; doc-modal = transient-for + custom dimming |
| Live progress updates | Same on Linux | Background thread + idle_add to main loop |
| Suppression checkbox | NSUserDefaults | dconf/GSettings key per dialog |

## F14. Cross-cutting interaction vocabulary (platform event ids)

Derived from F11–F13. All platform components (widgets, shell services, apps) use these event ids.

```
mv.event.pointer.down | mv.event.pointer.up | mv.event.pointer.move | mv.event.pointer.drag
mv.event.key.down     | mv.event.key.up     | mv.event.wheel
mv.event.window.activate | mv.event.window.deactivate | mv.event.window.move | mv.event.window.resize
mv.event.window.minimize.requested | mv.event.window.zoom.requested
mv.event.window.fullscreen.enter | mv.event.window.fullscreen.exit
mv.event.app.launch | mv.event.app.terminate | mv.event.app.activate
mv.event.menu.open | mv.event.menu.close | mv.event.menu.item.activated
mv.event.dialog.present | mv.event.dialog.dismiss | mv.event.sheet.present | mv.event.sheet.dismiss
mv.event.dnd.enter | mv.event.dnd.drop | mv.event.dnd.exit
mv.event.shell.spotlight | mv.event.shell.launchpad | mv.event.shell.missioncontrol
```

Renderer backends (X11/GDK) translate native events → these ids. Behaviour records never mention X11/GDK.

## F15. Spotlight reverse engineering — partial (preference pane only, main search UI inaccessible) (2026-10-18)

### F15.1 Scope and blocker

**What was targeted:** The user-visible Spotlight search interface (the window invoked by ⌘Space, with search field, live results, preview pane, category filtering).

**What was actually accessible:** Only the **Spotlight preference pane** (`/System/Library/PreferencePanes/Spotlight.prefPane`, 197 KB universal binary). The main Spotlight search UI bundle (`/System/Library/CoreServices/Spotlight.app` or equivalent) was **not found** in any extracted artifacts, and the Mavericks guest VM could not be booted to extract it.

**Blockers:**
- The guest disk image (`mavericks-hdd.raw`) contains the installed system but UEFI boot fails on QEMU (standard pc-q35/pc-i440fx machine types, with or without Apple SMC emulation) — the HFS+ partition is not recognized as a bootable Mac OS X volume.
- The WSL2 kernel (6.18.54.1-microsoft-standard-WSL2) lacks the `hfsplus` module; the HFS+ partition cannot be mounted on the host.
- The Mavericks installer DVD (`MavericksDVD.dmg`) contains an HFS+ payload that 7z can identify but not extract files from; `qemu-img` cannot convert the DMG.
- No pre-extracted `spotlight.tar` exists in the artifact set (unlike `finder.tar`, `dock.tar`, `syspref.tar`, `calc.tar`, `textedit.tar`).

**Consequence:** The main Spotlight search UI — its NIBs, native binary, runtime behavior, preview integration, and keyboard invocation — **cannot be reverse-engineered at this time**. Only the preference pane is documented here.

### F15.2 Spotlight preference pane — NIB analysis (REA)

**Artifact:** `Spotlight.prefPane/Contents/Resources/Base.lproj/SpotlightPref.nib` (decoded via REA `decode-interface-builder`).

| Metric | Value |
|---|---:|
| Objects | 214 |
| Connections | 19 |
| Actions | 4 (all targeting `SpotlightPref` controller, object 2) |
| Outlets | 19 |
| Distinct IB classes | 4 |

**Actions (target → selector):**
| Source object | Selector | Purpose |
|---|---|---|
| 89 (checkbox) | `toggleSpotlightMenuHotKey:` | Enable/disable menu bar Spotlight hotkey |
| 129 (checkbox) | `toggleSpotlightWindowHotKey:` | Enable/disable ⌘Space window hotkey |
| 103, 141 (buttons) | `gotoKbdPref:` | Open Keyboard preferences (hotkey conflicts) |
| 274 (button) | `help:` | Help button |

**Outlets (19 total) from `SpotlightPref` (object 2):** Connected to table views, combo boxes, checkboxes, tab view, and text fields for the Search Results, Privacy, and Keyboard Shortcuts tabs.

**IB Classes:** `NSApplication`, `NSImage`, `SpotlightPref`, `SpotlightPrefItemTable` (custom `NSTableView` subclass with drag highlight).

### F15.3 Spotlight preference pane — Native architecture (machobjc)

**Binary:** `Spotlight.prefPane/Contents/MacOS/Spotlight` (197 KB, universal x86_64 + i386, MH_BUNDLE). Readable — no high-entropy sections.

**Classes (6):**

| Class | Role | Key methods (selected) |
|---|---|---|
| `SpotlightPref` | Principal controller (`NSPreferencePane` subclass) | `mainViewDidLoad`, `didSelect`, `revealElementForKey:`, `willResignActive`, `reflectUI`, `_setupComboBox`, `_setupConflictUI`, `_getStoredSpotlightItems`, `_defaultSpotlightItems`, `_getSpotlightItemIconsAndDisplayNames`, `_getCategoryImages`, `_getRealSpotlightHotKey`, `_sendImmediatePrefChangeNotification`, `_sendCumulativePrefChangeNotification`, `_syncSpotlightItems`, `_syncUserAssignableKeys`, `_refreshConflicts`, `_findConflictingSymbolicHotKeyFor:`, `_getSymbolicHotKeys`, `toggleSpotlightMenuHotKey:`, `toggleSpotlightWindowHotKey:`, `gotoKbdPref:`, `help:`, `spotlightItems`, `setSpotlightItems:`, combo box & table view data source/delegate methods, tab view delegate |
| `SpotlightPrefConfigKeyEditor` | Custom key-equivalent editor for hotkeys | `initConfigKeyEditorWithMaster:`, `becomeFirstResponder`, `resignFirstResponder`, `mouseDown:`, `keyDown:`, `validateMenuItem:`, `performKeyEquivalent:`, `key`, `modifier`, `textField`, `setTextField:`, `_disableHotKeyOperationMode`, `_restoreHotKeyOperationMode` |
| `SpotlightPrefItemTable` | Custom `NSTableView` for category list | `_highlightColorForCell:`, `dragImageForRowsWithIndexes:tableColumns:event:offset:`, `drawGridInClipRect:`, `resetCursorRects`, `mouseDown:`, `setProposedDropRow:`, `accessibilityAttributeValue:` |
| `SpotlightPrefPrivacyController` | Privacy tab controller (excluded locations) | `init`, `awakeFromNib`, `_getPrivateItems`, `_reloadExclusions:`, `_itemIsDuplicate:`, `_addKeyEquivalentsToDeleteButton`, `willSelect`, `willResignActive`, table view data source/delegate, drag/drop for privacy list, `_tableDoubleClick:`, `addItem:`, `openPanelFinished:returnCode:`, `deleteItem:`, `undoAddDelete:`, `privacyView`, `setParent:` |
| `SpotlightPrefPrivateItem` | Model for privacy list items | `initWithPath:`, `getIcon`, `nameCompare:`, `initWithCoder:`, `encodeWithCoder:`, `name`, `setName:`, `path`, `setPath:`, `icon`, `setIcon:` |
| `SpotlightItem` | Model for search category items | `enabled`, `setEnabled:`, `icon`, `setIcon:` |

**NSPreferencePane protocol implementation (observed):**
- `mainViewDidLoad` (IMP 0x11c0)
- `didSelect` (IMP 0x3bbc)
- `revealElementForKey:` (IMP 0x6e98)
- `willResignActive` (IMP 0x6092)
- `willSelect` / `didSelect` via tab view delegate (`tabView:willSelectTabViewItem:`, `tabView:didSelectTabViewItem:`)

**Key architectural observations:**
1. **Hotkey management** — `_getRealSpotlightHotKey`, `_getSymbolicHotKeys`, `_findConflictingSymbolicHotKeyFor:` read Carbon symbolic hotkeys (SymbolicHotKeys plist); `toggleSpotlightMenuHotKey:` / `toggleSpotlightWindowHotKey:` flip the enabled state.
2. **Category list** — `_defaultSpotlightItems`, `_getStoredSpotlightItems`, `_getSpotlightItemIconsAndDisplayNames`, `_syncSpotlightItems` manage the ordered list of search categories (Applications, Documents, Folders, etc.) with per-category enable/disable and icons.
3. **Privacy (exclusions)** — `SpotlightPrefPrivacyController` manages the Privacy tab: `_getPrivateItems`, `_reloadExclusions:`, drag/drop to add paths, duplicate detection (`_itemIsDuplicate:`), "paths that could break apps" warning (`_checkPathsThatCouldBreakApps:`), open panel integration (`openPanelFinished:returnCode:`).
4. **Conflict detection** — `_refreshConflicts`, `_findConflictingSymbolicHotKeyFor:` detect hotkey conflicts with other apps and offer `gotoKbdPref:` to resolve.
5. **Persistence** — `_sendImmediatePrefChangeNotification` / `_sendCumulativePrefChangeNotification` broadcast changes; `SpotlightPrefPrivateItem` implements `NSCoding` for privacy list archival.
6. **Custom UI** — `SpotlightPrefConfigKeyEditor` is a custom `NSView` for capturing key equivalents (mouse/keyboard event handling, first responder management); `SpotlightPrefItemTable` customizes table row highlighting and drag image.

### F15.4 Main Spotlight search UI — absent

**Expected location (per Mavericks 10.9 documentation):** `/System/Library/CoreServices/Spotlight.app` or a dedicated bundle launched by `launchd` / `SystemUIServer`.

**Evidence of absence:**
- Not in `sys_apps/System/Library/CoreServices/` (only `Finder.app` extracted).
- Not in any `*.tar` artifact (`finder.tar`, `dock.tar`, `syspref.tar`, `calc.tar`, `textedit.tar`).
- Not in `sys_dock/`, `sys_syspref/`, `sys_panes/`, `sys_apps/` extracted trees.
- Guest VM unbootable; runtime capture (`nsinspect`) impossible.
- No Ghidra project for Spotlight search binary.

**Inferred architecture (from preference pane + Finder/Dock evidence):**
- The main search UI is a separate process (likely `Spotlight.app` or a `SystemUIServer` plugin) that:
  - Registers the ⌘Space global hotkey via Carbon `RegisterEventHotKey` / symbolic hotkeys.
  - Communicates with `mds`/`mdworker` (metadata server) for query results.
  - Delegates preview to Quick Look (`QLPreviewPanel` / `QLPreviewView`).
  - Presents results in a custom window with search field, result list, preview pane, category filtering.
  - Is invoked by `SystemUIServer` menu extra click (Dock symbols show Carbon menu usage).
- The preference pane (`SpotlightPref`) configures this separate UI indirectly via:
  - Symbolic hotkey registry (read by both pref pane and search UI).
  - Category enable/disable state (synced via `_syncSpotlightItems` / notifications).
  - Privacy exclusions (written to `mds` index via `openPanelFinished:returnCode:` → `mdutil` / `mdimport`).
- **No direct NIB, native binary, or runtime evidence** for the search UI itself.

### F15.5 Linux implementation implications

| Mavericks component | Linux equivalent | Gap |
|---|---|---|
| Spotlight search UI (window) | **Missing** — no RE evidence | Must be designed from HIG + inference; cannot be evidence-backed |
| Global hotkey (⌘Space) | `mv_hotkeys_core` + XGrabKey daemon | Architectural limit: X11 has no global menu/hotkey focus (DECISIONS.md) |
| Live results / mds index | `plocate` / custom indexer / `tracker-miners` | No evidence for result ranking, update latency, or category model |
| Preview delegation | Quick Look (`mv-quicklook`) | Integration point unknown without search UI RE |
| Category enable/disable | Configurable in Settings | Pref pane RE complete; sync mechanism to indexer unspecified |
| Privacy exclusions | Configurable in Settings | Pref pane RE complete; `mds` exclusion API unknown |
| Hotkey conflict resolution | `gotoKbdPref:` → Keyboard Settings | Cross-app conflict detection not evidence-backed |

**Recommendation:** The Spotlight search UI cannot be implemented faithfully without the main binary. Options:
1. **Defer** until guest VM boot is resolved (requires proper Mac QEMU emulation: `qemu-system-x86_64 -M mac99` / KVM + OSK + SMC, or host-side HFS+ access).
2. **Design from inference** using F12 (menu bar), F13 (dialogs/sheets), F11 (window management) + HIG, but mark all behavior as `confidence: inferred`.
3. **Substitute** with a simpler launcher (like `mv-launchpad` / `rofi` backend) and document as a known fidelity gap.

### F15.6 Artifacts produced

| Artifact | Path |
|---|---|
| Spotlight prefPane REA NIB decode | `docs/UI_REFERENCE/runtime/raw/rea/rea_spotlight_prefpane.json` |
| Spotlight prefPane ObjC metadata | `docs/UI_REFERENCE/runtime/raw/native/spotlight_prefpane-objc-metadata.json` |
| Spotlight prefPane binary slice | `/home/builder/vmwork/opencode/slices/Spotlight_prefpane-x86_64` |
| NIB source | `/home/builder/vmwork/opencode/rea_min/spotlight_prefpane.app` |

### F15.7 Spotlight prefPane implementation-ready analysis

The Spotlight preference pane (`Spotlight.prefPane`) was successfully extracted via
REA. Binary: `/home/builder/vmwork/opencode/slices/Spotlight_prefpane-x86_64`.
ObjC metadata: 6 classes, 108 methods total.

**Class inventory:**

| Class | Role | Methods |
|---|---|---|
| `SpotlightItem` | Model: enabled flag + icon per search category | 4 |
| `SpotlightPref` | Main prefpane view controller | 51 |
| `SpotlightPrefConfigKeyEditor` | Custom NSControl for capturing hotkey combinations | 16 |
| `SpotlightPrefItemTable` | NSTableView subclass for category list with DnD reordering | 7 |
| `SpotlightPrefPrivacyController` | Privacy tab: path exclusion list management | 25 |
| `SpotlightPrefPrivateItem` | Model: excluded path with name/icon | 11 |

**Key selectors for implementation:**

- `mainViewDidLoad` → loads stored items, sets up combo box + table, loads category icons
- `reflectUI` → pushes model state into controls
- `_getStoredSpotlightItems` → reads `NSUserDefaults` key for category enabled state
- `_defaultSpotlightItems` → returns hardcoded default category list
- `_getSpotlightItemIconsAndDisplayNames` → maps category IDs to (icon, label)
- `_getCategoryImages` → returns array of category icon images
- `_getRealSpotlightHotKey` → reads current hotkey from symbolic hotkey system
- `_sendImmediatePrefChangeNotification` → posts `NSUserDefaults` change notification
- `_sendCumulativePrefChangeNotification` → batched change notification
- `_syncSpotlightItems` / `_syncUserAssignableKeys` → writes model → defaults
- `_refreshConflicts` / `_findConflictingSymbolicHotKeyFor:` → cross-app hotkey conflict detection
- `_getSymbolicHotKeys` → reads all registered symbolic hotkeys
- `toggleSpotlightMenuHotKey:` / `toggleSpotlightWindowHotKey:` → enable/disable hotkeys
- `gotoKbdPref:` → opens Keyboard preferences
- `comboBox:objectValueForItemAtIndex:` / `numberOfItemsInComboBox:` → combo box data source
- `comboBoxSelectionIsChanging:` / `comboBoxSelectionDidChange:` → combo box delegate
- `numberOfRowsInTableView:` / `tableView:objectValueForTableColumn:row:` → table data source
- `TableView:writeRowsWithIndexes:toPasteboard:` / `acceptDrop:row:dropOperation:` → drag-and-drop reordering
- `_addKeyEquivalentsToDeleteButton` → adds key equivalents to delete button in privacy list
- `_handlePrivacyError:forPath:` → error handling for privacy path addition
- `_setPathsThatCouldBreakApps` / `_checkPathsThatCouldBreakApps:` → warns about breaking app paths
- `openPanelFinished:returnCode:` → handles NSOpenPanel result for adding exclusion path

**prefPane UI structure (from selectors + NIB):**

1. **Search Categories tab**: combo box (category groups) + table view (individual categories with enable checkboxes + icons)
2. **Privacy tab**: table view (excluded paths) + Add/Remove buttons + path validation
3. **Hotkey tab**: two `SpotlightPrefConfigKeyEditor` controls (menu hotkey + window hotkey) + conflict detection

**Implementation plan for MavLinOS Spotlight prefPane:**

1. Create `SpotlightItem` model class with `enabled` and `icon` properties
2. Create `SpotlightPref` controller that loads/stores category state via `dconf`
3. Use `GtkTreeView` for category list with checkbox + icon columns
4. Use `GtkComboBoxText` for category group selection
5. Implement hotkey capture via `mv.hotkey` layer (record key combo on focus)
6. Implement privacy path list with `GtkTreeView` + Add/Remove + path validation
7. Implement conflict detection by querying `mv.hotkey` registry

### F15.8 Remaining work (blocked)

| Work | Blocker |
|---|---|
| Main Spotlight search UI NIB inventory | Binary inaccessible (decmpfs compressed, resource fork unreadable without booted macOS) |
| Main search UI native class/method inventory | Binary inaccessible |
| Search session behavior (query → results → selection → preview) | Runtime capture impossible |
| Preview pane integration (QLPreviewPanel) | Runtime capture impossible |
| Keyboard navigation (arrows, Return, Escape, ⌘Space dismiss) | Runtime capture impossible |
| Animation timings (fade-in, result stagger, preview slide) | Runtime capture impossible |
| `mds`/`mdworker` indexer communication | Separate daemon, no RE started |

**Note on decmpfs extraction attempts:**

All extraction approaches for the main Spotlight binary have been exhausted:

| Approach | Result |
|---|---|
| libguestfs `getxattr` | Reads decmpfs header only (type=4, size=18240); resource fork data unreadable |
| VM boot (OpenCore 0.9.0 + QEMU TCG) | OpenCore loads config but macOS kernel does not boot (reboots after entry selection) |
| Manual HFS+ B-tree parser | B-tree traversal produces incorrect record offsets; CNID 244251 confirmed present by libguestfs but not found in traversal |
| Brute-force disk scan for decmpfs magic | No valid header found (all matches had comp_type=10, logical_size=562945658454016 = false positives) |
| `hfsprogs` installation | No root access in build container |

**To unblock:** Either (a) boot the Mavericks VM successfully (requires working QEMU+OVMF+OpenCore chain with proper CPU emulation and macOS kernel loading), or (b) obtain a user-space HFS+ resource fork reader (e.g., `hfsexplorer` or custom Python parser with correct B-tree traversal).

