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
