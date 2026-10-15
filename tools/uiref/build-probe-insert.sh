#!/usr/bin/env bash
# build-probe-insert.sh - build the minimal DYLD_INSERT_LIBRARIES probe.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
outdir="${1:-$here/../../build}"
mkdir -p "$outdir"
clang -target x86_64-apple-macos10.9 -nostdinc -fPIC -O1 -fno-stack-protector \
      -nostdlib -fuse-ld=lld -Wl,-undefined,dynamic_lookup \
      -dynamiclib -o "$outdir/probe-insert.dylib" "$here/probe-insert.c"
file "$outdir/probe-insert.dylib"
echo "run in the guest:"
echo "  DYLD_INSERT_LIBRARIES=./probe-insert.dylib /Applications/Calculator.app/Contents/MacOS/Calculator"
