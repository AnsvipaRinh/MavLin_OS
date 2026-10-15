#!/usr/bin/env bash
# build-mvax.sh - cross-compile the Accessibility (AXUIElement) extractor from Linux.
#
# Produces build/mvax, a Mach-O x86_64 executable that runs inside the Mavericks
# guest and walks the accessibility tree of *other* applications without loading
# any code into them.
#
# There is no Apple SDK on this machine, so every external symbol is declared in
# mvax.c and linked against generated stubs.  The stubs carry the install names
# the guest really has, so dyld resolves each symbol from the guest's own
# CoreFoundation / HIServices at launch; they are never shipped.
#
# Prerequisites (Arch): clang lld
# Usage:  tools/uiref/build-mvax.sh [outdir]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/mvax.c"
outdir="${1:-$here/../../build}"
mkdir -p "$outdir"

command -v clang >/dev/null || { echo "clang is required (pacman -S clang lld)" >&2; exit 1; }

stubdir="$outdir/stubs"
mkdir -p "$stubdir"

gen_stub() {
  local out="$1"; shift
  : > "$out"
  echo '/* link-time stub only - never shipped to the guest */' >> "$out"
  local s
  for s in "$@"; do printf 'void %s(void) {}\n' "$s" >> "$out"; done
}

gen_stub "$stubdir/ax_libsys.c" _dyld_stub_binder dlopen dlsym getenv fopen fclose \
    fprintf snprintf vsnprintf fflush fsync fileno rename unlink strcmp fwrite \
    getpid sleep atoi

gen_stub "$stubdir/ax_cf.c" \
    _CFStringCreateWithCString _CFStringGetCString _CFGetTypeID \
    _CFStringGetTypeID _CFArrayGetTypeID _CFNumberGetTypeID _CFBooleanGetTypeID \
    _CFArrayGetCount _CFArrayGetValueAtIndex _CFNumberGetValue \
    _CFBooleanGetValue _CFRelease

gen_stub "$stubdir/ax_ax.c" \
    _AXUIElementCreateApplication _AXUIElementCreateSystemWide \
    _AXUIElementCopyAttributeValue _AXUIElementCopyAttributeNames \
    _AXUIElementCopyActionNames _AXUIElementPerformAction _AXIsProcessTrusted \
    _AXUIElementSetMessagingTimeout

build_stub() {  # build_stub <c> <out> <install_name>
  clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -nostdlib -fuse-ld=lld \
        -shared -w -Wl,-install_name,"$3" -o "$2" "$1"
}

CF=/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation
AX=/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/HIServices

build_stub "$stubdir/ax_libsys.c" "$stubdir/libSystem.B.dylib" /usr/lib/libSystem.B.dylib
build_stub "$stubdir/ax_cf.c"     "$stubdir/CoreFoundation"    "$CF"
build_stub "$stubdir/ax_ax.c"     "$stubdir/HIServices"        "$AX"
echo "built link-time stubs with guest install names"

echo "building $outdir/mvax"
clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -O1 \
  -fno-stack-protector \
  -Wall -Wextra -Wno-unused-parameter \
  -nostdlib -fuse-ld=lld \
  "$stubdir/libSystem.B.dylib" "$stubdir/CoreFoundation" "$stubdir/HIServices" \
  -Wl,-undefined,dynamic_lookup \
  -o "$outdir/mvax" "$src"

echo "building $outdir/mvax-inject.dylib"
clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -O1 \
  -fno-stack-protector -Wall -Wextra -Wno-unused-parameter \
  -nostdlib -fuse-ld=lld \
  "$stubdir/libSystem.B.dylib" "$stubdir/CoreFoundation" "$stubdir/HIServices" \
  -Wl,-undefined,dynamic_lookup -DMVAX_INJECT \
  -dynamiclib -o "$outdir/mvax-inject.dylib" "$src"

file "$outdir/mvax" "$outdir/mvax-inject.dylib" 2>/dev/null || true
echo "done: $outdir/mvax"
echo "run in the guest:  MVAX_OUT=/tmp/mvax.json ~/mvax /tmp/mvax.json <depth> Finder:<pid> ..."