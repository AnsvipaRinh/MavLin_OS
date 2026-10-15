# Injected-flavour attempts (chronological, with exact guest errors)

Target: make `nsinspect.dylib` load into a running Mavericks app via
`DYLD_INSERT_LIBRARIES` and write a document describing that app's real
`NSWindow` / `NSView` graph.

Host apps for the trials: `/Applications/Calculator.app`, `/System/Library/…/Finder.app`.
Runner (in the guest): `sh /Volumes/NSINSPECT/run.sh /Applications/Calculator.app calc`.

## Summary of the final state

Injection **works**; it was misdiagnosed for most of this investigation. The
three real mechanisms behind every crash are now identified and each is backed
by an isolated experiment, not by guesswork:

| # | Finding | How it was proved |
|---|---|---|
| F1 | A `DYLD_INSERT_LIBRARIES` constructor **does** run inside a Mavericks app | `probe-insert.dylib` printed its banner inside Calculator and the app stayed alive |
| F2 | Calling **`pthread_create` from that constructor deadlocks** on 10.9 | `probe-insert` thread starts, then never finishes; the host hangs |
| F3 | Calling **`dlsym` from that constructor segfaults** | the fault moved between runs, once inside the resolver and once past it |
| F4 | **Platform binaries strip `DYLD_*`** — injection is impossible for Finder and System Preferences | Finder launched with an injected library produced an empty log: the library was never loaded |

## 1. Original build (`-nostdlib -undefined dynamic_lookup`)

```
Segmentation fault: 11   DYLD_INSERT_LIBRARIES=... /Applications/Calculator.app/Contents/MacOS/Calculator
```

No breadcrumb file, no dyld message. The app died at load.

## 2. Standalone tool, same build — a different failure

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
no library dependencies at all.

### 3a. Defining the binder in the source

A C definition became an `N_ABS` symbol outside any section (dyld will not bind
it). Emitting it into `__TEXT,__text` by hand did produce a real symbol — but
it was a bare `ret`, which **replaced lld's own working binder** and broke every
lazy call, so the injected image then died before its constructor. Reverted:
lld's binder must be left alone.

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
- With the stubs **plus** `-Wl,-undefined,dynamic_lookup`, the link succeeds and
  the standalone tool runs in the guest (`exit=0`, valid 246-byte document).

**This was the fix that made the binary loadable at all.**

## 5. Isolating the injection itself (F1, F2)

Built `tools/uiref/probe-insert.c`: the smallest possible injected dylib, whose
constructor calls only `write(2)` and `getpid()`.

```
== injecting minimal probe into Calculator ==
probe-insert: constructor ran, pid=1112
Calculator still running (pid 1112)
```

Injection is fine. Adding one line — `pthread_create` — produced:

```
probe-insert: constructor ran, pid=1262
probe-insert: thread started
Calculator still running (pid 1262)
```

and **never** printed either `pthread_create returned` (emitted by the
constructor after the call) or `thread slept ok` (emitted by the thread after a
3 s sleep). Both the thread and the constructor are blocked: spawning a thread
from an injected constructor deadlocks on Mavericks. That rules out the entire
"background worker" design for in-process capture.

## 6. Fixing the constructor (F3)

Moving every external call out of the constructor into a worker thread moved
the failure exactly as F2 predicts. An intermediate revision still called
`resolve_runtime()` (i.e. `dlsym`) in the constructor and produced:

```
nsinspect: constructor entered
nsinspect: worker: start
nsinspect: worker: runtime resolved      <- one run
...
nsinspect: worker: start                 <- another run died inside resolve
```

A failure that changes position between runs is a race, not a bad call. The
constructor now does nothing but `write(2)` and `pthread_create`; `dlsym` was
moved after a delay. Both are still blocked by F2.

## 7. Platform binaries (F4)

```
== launching Finder with the extractor injected ==
== finder stderr ==
                        <- empty: the library never loaded
```

Finder and System Preferences live under `/System` and are signed as part of
the OS. macOS removes `DYLD_*` from the environment of such binaries, so
**injection into Finder and System Preferences is not possible on 10.9** by
this route, and no amount of code in our dylib can change that. Any native
in-process capture of those two applications needs a different mechanism
(a debugger, Mach task APIs, or an OS-level capture such as the accessibility
API from a trusted client).

## 8. Where this leaves Track B

* Injection into non-platform apps: **proven**.
* Thread/worker hand-off from an injected constructor: **deadlocks** (F2), so
  the capture must run on a thread that already exists.
* Signal-driven capture is the remaining option and is implemented in
  `mvax.c` (`-DMVAX_INJECT`): a `SIGALRM` handler needs no thread and no run
  loop. It loads and arms correctly (`mvax-inject: loaded`,
  `mvax-inject: SIGALRM armed for 9s`) but has not yet produced a document; that
  step is still open.

Keep this file: a future toolchain or OS change must be able to tell whether a
finding moved, or disappeared.