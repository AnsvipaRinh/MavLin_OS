#!/usr/bin/env bash
# build-probe.sh - cross-compile the Mavericks runtime probe from Linux.
#
# Produces two Mach-O x86_64 binaries from one source file:
#   build/mvprobe.dylib   DYLD_INSERT_LIBRARIES flavour (constructor)
#   build/mvprobe-tool    standalone tool for the guest's Aqua session (preferred)
#
# Prerequisites (Arch):  clang lld llvm (Apple targets are in clang itself)
# Target:               x86_64-apple-macos10.9 (deployment 10.9 == Mavericks)
# No Apple SDK is needed: mvprobe.c declares every libc/AppKit symbol itself and
# resolves AppKit through the Objective-C runtime at run time.
#
# Usage:  tools/uiref/build-probe.sh [outdir]
# Smoke:  tools/uiref/build-probe.sh && file build/mvprobe.dylib build/mvprobe-tool
# Run in the guest (over SSH inside the Aqua session):
#         MVPROBE_OUT=/tmp/uiprobe.json ./mvprobe-tool   # exit 0 complete, 2 partial
# With the dylib: DYLD_INSERT_LIBRARIES=./mvprobe.dylib MVPROBE_OUT=/tmp/uiprobe.json \
#                /System/Library/CoreServices/Finder.app/Contents/MacOS/Finder
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/mvprobe.c"
outdir="${1:-$here/../../build}"
mkdir -p "$outdir"

command -v clang >/dev/null || { echo "clang is required (pacman -S clang lld)" >&2; exit 1; }

common=(
  -target x86_64-apple-macos10.9
  -nostdinc
  -fPIC -O1
  -Wall -Wextra -Wno-unused-parameter
  -fvisibility=hidden
  -nostdlib                        # no SDK, no libSystem: symbols resolve in the guest
  -fuse-ld=lld
  -Wl,-undefined,dynamic_lookup
  -Wno-deprecated-non-prototype
)

echo "building $outdir/mvprobe.dylib"
clang "${common[@]}" -dynamiclib -o "$outdir/mvprobe.dylib" "$src"

echo "building $outdir/mvprobe-tool"
clang "${common[@]}" -DMVPROBE_TOOL -o "$outdir/mvprobe-tool" "$src"

echo "smoke: host-side self test (fake runtime, proves the JSON writer)"
clang -DMVPROBE_SELFTEST -Wall -Wextra -o "$outdir/mvprobe-selftest" "$src"
"$outdir/mvprobe-selftest" "$outdir/mvprobe-selftest.json" || true
python3 - "$outdir/mvprobe-selftest.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["schema"] == "mavlinos.uiprobe/2", d.get("schema")
assert d["status"] in ("complete", "partial", "failed")
assert "errors" in d and "gaps" in d and "summary" in d
print("self test OK: status=%s items=%s errors=%s gaps=%s" % (
    d["status"], d["summary"]["items"], d["summary"]["errors"], d["summary"]["gaps"]))
PY

echo
file "$outdir/mvprobe.dylib" "$outdir/mvprobe-tool" 2>/dev/null || true
echo "done: $outdir"
