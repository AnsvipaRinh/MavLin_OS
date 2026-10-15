#!/usr/bin/env bash
# build-probe-insert.sh - build the minimal DYLD_INSERT_LIBRARIES probe.
#
# Answers, with no ambiguity, what an injected library may safely do on
# Mavericks: can its constructor run at all, can it start a thread, and is the
# Objective-C runtime usable from there.  Everything else we tried failed for
# reasons that only this probe separates cleanly.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
outdir="${1:-$here/../../build}"
mkdir -p "$outdir/stubs"

cat > "$outdir/stubs/probe_objc.c" <<'STUB'
/* link-time stub only - never shipped */
void objc_getClass(void) {}
void sel_registerName(void) {}
STUB
clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -nostdlib -fuse-ld=lld -shared -w \
      -Wl,-install_name,/usr/lib/libobjc.A.dylib \
      -o "$outdir/stubs/libobjc.A.dylib" "$outdir/stubs/probe_objc.c"

clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -O1 -fno-stack-protector \
      -nostdlib -fuse-ld=lld \
      "$outdir/stubs/libobjc.A.dylib" -Wl,-undefined,dynamic_lookup \
      -dynamiclib -o "$outdir/probe-insert.dylib" "$here/probe-insert.c"
file "$outdir/probe-insert.dylib"
