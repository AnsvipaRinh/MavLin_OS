# CPU-SPECIFIC COMPILATION — m3-7Y32 (Kaby Lake-Y)
# Target supports: SSE4.2, AVX, AVX2, BMI1/2, FMA, AES-NI, RDRAND, RDSEED, MPX (deprecated).
# Does NOT support: AVX-512, AMX, AVX-VNNI.

## Policy
1. Generic Arch binaries: KEEP (kernel, Mesa, Xfce, Firefox — distro builds are
   already -O2, audited, and receive security updates; rebuilding gains ~1-3%).
2. Software we compile ourselves (custom packages): use conservative target flags.
3. Small custom components: none currently (no C/Rust shipped — see RUNTIME_AUDIT).
4. Performance-critical: N/A pre-hardware (no measured hotspot).

## Flags for our own builds (PKGBUILDs we control)
```
CFLAGS="-march=skylake -mtune=skylake -O2 -pipe -fno-plt -fexceptions"
CXXFLAGS="${CFLAGS}"
LDFLAGS="-Wl,-O1,--sort-common,--as-needed"
# LTO: only if package builds cleanly with -flto (test per package)
# PGO: NOT USED (no representative workload profile without hardware)
# -march=native: FORBIDDEN in PKGBUILDs (ISO builds on arbitrary host)
```

## Applied to
- mavericks-theme, epiphany-mavericks-theme: arch=(any), no compiled code — N/A.
- macbook12-audio-driver (DKMS): inherits kernel build flags automatically — N/A.
- Future custom C tools (if any): use the flags above + `-Wl,--gc-sections -s`.

## Metric
energy-to-completion, not peak perf. Do not trade +5% power for +1% speed.
