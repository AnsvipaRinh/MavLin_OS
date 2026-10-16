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