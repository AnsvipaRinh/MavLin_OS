#!/usr/bin/env bash
# build-probe.sh - cross-compile the Mavericks runtime probe from Linux.
#
# Produces two Mach-O x86_64 binaries from one source file:
#   build/nsinspect.dylib   DYLD_INSERT_LIBRARIES flavour (constructor)
#   build/nsinspect-tool    standalone tool for the guest's Aqua session (preferred)
#
# Prerequisites (Arch):  clang lld llvm (Apple targets are in clang itself)
# Target:               x86_64-apple-macos10.9 (deployment 10.9 == Mavericks)
# No Apple SDK is needed: nsinspect.c declares every libc/AppKit symbol itself and
# resolves AppKit through the Objective-C runtime at run time.
#
# Usage:  tools/uiref/build-probe.sh [outdir]
# Smoke:  tools/uiref/build-probe.sh && file build/nsinspect.dylib build/nsinspect-tool
# Run in the guest (over SSH inside the Aqua session):
#         NSINSPECT_OUT=/tmp/uiprobe.json ./nsinspect-tool   # exit 0 complete, 2 partial
# With the dylib: DYLD_INSERT_LIBRARIES=./nsinspect.dylib NSINSPECT_OUT=/tmp/uiprobe.json \
#                /System/Library/CoreServices/Finder.app/Contents/MacOS/Finder
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/nsinspect.c"
outdir="${1:-$here/../../build}"
mkdir -p "$outdir"

command -v clang >/dev/null || { echo "clang is required (pacman -S clang lld)" >&2; exit 1; }

# --- link form -------------------------------------------------------------
# No Apple SDK is available, so the images link with -undefined
# dynamic_lookup and resolve libc/Objective-C in the guest.  Two consequences
# found in the real Mavericks guest, both fixed here:
#   * __stack_chk_guard is unreachable in the flat namespace -> -fno-stack-protector
#   * dyld imports dyld_stub_binder from the guest libSystem; overriding it with
#     a no-op breaks every lazy call, so lld's own binder must be left alone.

stubdir="$outdir/stubs"
mkdir -p "$stubdir"
gen_stub() {
  local src="$1"; shift
  : > "$src"
  echo '/* link-time stub only - never shipped to the guest */' >> "$src"
  local s
  for s in "$@"; do printf 'void %s(void) {}\n' "$s" >> "$src"; done
}
gen_stub "$stubdir/libsys.c" _dyld_stub_binder dlopen dlsym getenv fopen fclose fprintf \
    snprintf vsnprintf fflush fsync fileno rename unlink _exit strcmp fwrite getpid \
    pthread_create sleep
gen_stub "$stubdir/libobjc.c" objc_getClass sel_registerName objc_msgSend sel_getName \
    class_getName class_getSuperclass object_getClass class_getInstanceMethod \
    method_getImplementation method_setImplementation class_addMethod class_createInstance
clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -nostdlib -fuse-ld=lld -shared -w \
      -Wl,-install_name,/usr/lib/libSystem.B.dylib -o "$stubdir/libSystem.B.dylib" "$stubdir/libsys.c"
clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -nostdlib -fuse-ld=lld -shared -w \
      -Wl,-install_name,/usr/lib/libobjc.A.dylib  -o "$stubdir/libobjc.A.dylib"  "$stubdir/libobjc.c"

common=(
  -target x86_64-apple-macos10.9
  -nostdinc
  -fPIC -O1
  -fno-stack-protector   # __stack_chk_guard is not resolvable in the flat namespace
                         # of a -nostdlib binary; without this the guest dies with
                         # "dyld: Symbol not found: __stack_chk_guard" (exit 133).
  -Wall -Wextra -Wno-unused-parameter
  -fvisibility=hidden
  -nostdlib                        # no SDK, no libSystem: symbols resolve in the guest
  -fuse-ld=lld
  "$stubdir/libSystem.B.dylib" "$stubdir/libobjc.A.dylib"
  -Wl,-undefined,dynamic_lookup
  -Wno-deprecated-non-prototype
)

echo "building $outdir/nsinspect.dylib"
clang "${common[@]}" -dynamiclib -o "$outdir/nsinspect.dylib" "$src"

echo "building $outdir/nsinspect-tool"
clang "${common[@]}" -DNSINSPECT_TOOL -o "$outdir/nsinspect-tool" "$src"

echo "smoke: host-side self test (fake runtime, proves the JSON writer)"
clang -DNSINSPECT_SELFTEST -Wall -Wextra -o "$outdir/nsinspect-selftest" "$src"
"$outdir/nsinspect-selftest" "$outdir/nsinspect-selftest.json" || true
python3 - "$outdir/nsinspect-selftest.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["schema"] == "mavlinos.nsinspect/1", d.get("schema")
assert d["status"] in ("ok", "failed - no AppKit in this process")
assert "windows" in d and "controls_found" in d
print("self test OK: schema=%s status=%s windows=%s controls=%s" % (
    d["schema"], d["status"], d["windows"], d["controls_found"]))
PY

echo
file "$outdir/nsinspect.dylib" "$outdir/nsinspect-tool" 2>/dev/null || true
echo "done: $outdir"
