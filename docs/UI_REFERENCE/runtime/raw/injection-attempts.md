# Injected-flavour attempts (chronological, with exact guest errors)

Target: make `nsinspect.dylib` load into a running Mavericks app via
`DYLD_INSERT_LIBRARIES` and write a document describing that app's real
`NSWindow` / `NSView` graph.

Host app for the trials: `/Applications/Calculator.app`.
Runner (in the guest): `sh /Volumes/NSINSPECT/run.sh /Applications/Calculator.app calc`.

## 1. Original build (`-nostdlib -undefined dynamic_lookup`)

```
Segmentation fault: 11   DYLD_INSERT_LIBRARIES=... /Applications/Calculator.app/Contents/MacOS/Calculator
```

No breadcrumb file, no dyld message. The app died at load.

## 2. Standalone tool, same build — different failure

```
dyld: Symbol not found: __stack_chk_guard
  Referenced from: /Users/builder/ns/nsinspect-tool
  Expected in: flat namespace
```

`-nostdlib` leaves `__stack_chk_guard` unresolvable in the flat namespace.
Fixed with `-fno-stack-protector`.

## 3. After that fix

```
dyld: Symbol not found: dyld_stub_binder
```

The main executable cannot obtain dyld's lazy-binding callback because it has
no library dependencies at all. (The same error never appeared for the
*dylib*; only the executable needs the binder imported by name.)

### 3a. Defining the binder in the source

A C definition became an `N_ABS` symbol outside any section (dyld will not
bind it). Emitting it into `__TEXT,__text` by hand did produce a real symbol —
but it was a bare `ret`, which **replaced lld's own working binder** and broke
every lazy call, so the injected image then died before its constructor.
Reverted: lld's binder must be left alone.

## 4. Link-time stubs with real guest install names

Built stub dylibs carrying the install names the guest actually has:

```
LC_LOAD_DYLIB: /usr/lib/libSystem.B.dylib
LC_LOAD_DYLIB: /usr/lib/libobjc.A.dylib
```

The stubs are never shipped; the guest resolves every symbol from its own
libSystem/libobjc at launch.

- With `-nostdlib` and no `-undefined dynamic_lookup`, `lld` refuses the link:
  `ld64.lld: error: undefined symbol: dyld_stub_binder`.
- With the stubs **plus** `-Wl,-undefined,dynamic_lookup`, the link succeeds
  and the standalone tool runs in the guest (`exit=0`, valid 246-byte
  document). This is the first successful real-guest execution.

## 5. Injected dylib after the fix — still fails

```
Segmentation fault: 11   DYLD_INSERT_LIBRARIES="$HOME/ns/nsinspect.dylib" ...
```

Breadcrumb file `/tmp/nsinspect-stage.log` was **never created**, so the fault
happens before the constructor's first statement, i.e. during image
initialisation rather than in our code. Three code variants were tried, all
with the same result:

| Constructor behaviour | Result |
|---|---|
| inspect immediately, then `_exit` | app exited without a document |
| swizzle `-[NSApplication run]`, dump from the run loop | `SIGSEGV`, no breadcrumb |
| start one worker thread, sleep, `performSelectorOnMainThread:` | `SIGSEGV`, no breadcrumb |

The consistent absence of the first breadcrumb points at dyld's early
initialisation of an inserted image, not at our logic: at that point the host
process' own dependencies are not yet initialised, and our image's lazy
symbols still have nothing to bind against.

## Conclusion / next step

The `-nostdlib` + link-time-stub approach is good enough to produce a binary
the guest **executes**, but not one it will accept as an *inserted* library.
Closing this needs a real SDK (or libSystem/libobjc import libraries) so the
image is linked with genuine dependencies and eager binding. The alternative,
which avoids injection entirely, is to collect the same facts through
`AXUIElement` from a separate process.

Keep this file: a future toolchain change must be able to tell whether the
failure moved, or disappeared.