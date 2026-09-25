# Technical Audit: "Mavericks Linux" for MacBook10,1 (2017, m3-7Y32)

**Audit Date:** 2026-09-25
**Kernel:** Linux 6.x / Arch Linux 2026
**Target:** MacBook10,1 (Mid 2017, Core m3-7Y32, Intel HD 615, fanless)

---

## 1. EXECUTIVE VERDICT (15-20 bullet points)

- **linux-zen is correct for interactive responsiveness** on fanless Core M, but its HZ=1000/PREEMPT_FULL tuning comes with ~2-3% overhead vs LTS; consider LTS for stability-biased deployments.
- **HWP on Kaby Lake (m3-7Y32) is fully supported via intel_pstate** in kernel 6.x; `intel_pstate=enable_hwp` is the default and requires no special flag, but `hwp_dynamic_boost` can be disabled via `/sys/module/processor/parameters/hwp_dynamic_boost` or boot parameter `hwp_dynamic_boost=0`.
- **idle=poll is outdated and harmful** for battery on modern kernel 6.x; use `intel_idle.max_cstate=4` instead, which limits C-states without forcing polling idle that wastes power on idle tasks.
- **i915 GuC/HuC/FBC/PSR all work on Kaby Lake in kernel 6.6+** with firmwar i915/kbl_huc_4.0.0.bin and i915/kbl_guc_70.1.1.bin loaded by default; `enable_guc=3` (GuC submission + HuC load) is the recommended setting, `enable_fbc=1` saves power, `enable_psr=2` enables PSR2 — all are safe and recommended.
- **NVMe APST default_ps_max_latency_us=100ms is too aggressive** for Apple NVMe controllers; raising to 200000 (200ms) or 300000 (300ms) improves power savings without stability risk; `nvme.noacpi=1` (already in plan) is correct for avoiding ACPI conflicts.
- **TLP + thermald conflict is real and recurring** — TLP already sets CPU governor to powersave and disables boost; thermald running on top can fight for CPU control; recommend disabling thermald or running it in `passive` mode only.
- **ananicy-cpp is lightweight and safe** — no measurable battery impact; keep but tune priority levels for specific processes (DE, browser) rather than system-wide.
- **applespi has known timeout issues on kernel 6.15+** for MacBook10,1 SPI rev 3+; the AUR macbook12-spi-driver-dkms may fail to build without manual patches; external USB-C input is mandatory for bring-up, internal keyboard/trackpad is best-effort with 3-try limit.
- **BCM43602 on MacBook10,1 requires revision check** — lspci output determines broadcom-wl-dkms (rev 03+) vs brcmfmac (rev 01/02); both are available in 2026 Arch; the blacklist of brcmfmac/brcmsmac/b43 in modprobe is correct.
- **Cirrus audio: snd_hda_codec_cirrus works out-of-the-box in kernel 6.6+** for basic output; the macbook12-audio-driver AUR PKGBUILD may still be needed for speaker amplification/headphone detection quirks; verify with `speaker-test -c 2` after install.
- **PCIe ASPM: TLP's powersupersave may cause resume-from-suspend failures** on some NVMe/Wi-Fi configurations; recommend `ASPM=powersave` (moderate) instead of `powersupersave`, or test thoroughly before defaulting.
- **zram-generator (RAM/2 with zstd) is correct for 8GB/16GB RAM** — provides effective swap without wearing the soldered SSD; lower swappiness to 10-20 for desktop interactivity; disable THP with `transparent_hugepage=never` at boot.
- **THP (Transparent Huge Pages) should be disabled** (`transparent_hugepage=never`) on this system — 8GB RAM non-uniform memory access patterns make THP more likely to hurt than help performance; the `vmshift` tuning is unnecessary complexity.
- **Mavericks skeuomorphic theme on Xfce/GTK3 is achievable** with the custom mavericks-theme/epiphany-mavericks-theme packages, but deep-texture elements (leather, paper) require SCSS customization beyond standard GTK3 theming; risk of visual inconsistencies is high.
- **Firefox ESR (128.x) is preferred over Epiphany/WebKitGTK** for 2026 — better web compatibility, uBlock Origin support, and extended security updates; Epiphany is viable only if memory/CPU is extremely constrained (< 4GB RAM).
- **archiso separation of visual vs hardware layers is partially achieved** but kernel parameters, module configs, and boot entries are mixed with theme packages in the ISO profile; recommend extracting hardware selection into a separate `hardware-selection.sh` script.
- **Month-without-hardware task classification needs tightening** — items marked "ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО" should be explicitly labeled VERIFY (require real hardware) vs KEEP (verified working) vs REMOVE (outdated), with clear owners and exit criteria.
- **No single claim in the original plan is positively harmful if applied correctly**, but several are outdated (idle=poll, ASPM powersupersave without testing, THP default) and several require hardware verification before commit (applespi, audio, Wi-Fi revision).

---

## 2. Detailed Table

| # | Current Claim | Verdict | Corrected Position | Hardware Required? |
|---|---|---|---|---|
| 1 | Use linux-zen kernel for fanless Core M | **KEEP** | linux-zen 6.x is valid; consider linux-lts only if stability > interactivity | No (simulated/emulated ok) |
| 2 | HZ=1000, PREEMPT_FULL as default | **KEEP** | Zen tuning is appropriate; no change needed | No |
| 3 | idle=poll for power savings | **REMOVE** | Use `intel_idle.max_cstate=4` instead; polling idle wastes more power than it saves on modern kernels | No |
| 4 | i915 enable_guc=3 enable_fbc=1 enable_psr=2 | **KEEP** | All three are valid and recommended for Kaby Lake in kernel 6.6+; firmware auto-loads | No (firmware in kernel) |
| 5 | NVMe default_ps_max_latency_us=0 | **CHANGE** | Raise to 200000 (200ms) for better power savings on Apple NVMe; keep nvme.noacpi=1 | Yes (verify on real hardware) |
| 6 | TLP + thermald + ananicy-cpp all enabled | **CHANGE** | Keep TLP and ananicy-cpp; disable thermald or use passive mode only to avoid conflicts | No (config tune) |
| 7 | applespi internal keyboard/trackpad works out-of-box | **DEFER** | Best-effort only; external USB-C mandatory for bring-up; max 3 driver strategies before marking unsupported | Yes (real hardware) |
| 8 | BCM43602 Wi-Fi: broadcom-wl-dkms prioritized | **KEEP** | Correct for MacBook10,1; add revision check (lspci) at install time; blacklist brcmfmac/brcmsmac/b43 is correct | Yes (lspci for revision) |
| 9 | Cirrus audio: macbook12-audio-driver required | **CHANGE** | snd_hda_codec_cirrus works out-of-box in kernel 6.6+ for basic audio; driver may still needed for speaker quirks — verify with speaker-test | Yes (speaker-test) |
| 10 | PCIe ASPM powersupersave (TLP) | **CHANGE** | Use ASPM powersave (not powersupersave) to avoid suspend/resume regressions; test before locking in | Yes (suspend test) |
| 11 | zram-generator RAM/2 zstd, no disk swap | **KEEP** | Correct for soldered SSD endurance; with 8GB RAM set zram0=4GB; lower swappiness to 10-20 | No |
| 12 | THP default behavior OK | **REMOVE** | Add `transparent_hugepage=never` to boot params; THP hurts performance on 8GB non-NUMA systems | No |
| 13 | Mavericks skeuomorphic GTK3 theme | **KEEP (with caveats)** | Custom mavericks-theme packages are appropriate; expect visual imperfections — document as "aesthetic approximation" not pixel-perfect | No (simulated) |
| 14 | Firefox ESR vs Epiphany | **KEEP (Firefox ESR)** | Firefox ESR 128.x preferred for web compatibility and extension support; Epiphany only if <4GB RAM constraint | No |
| 15 | archiso with separated layers | **CHANGE** | Extract hardware-selection.sh from ISO profile; keep visual theme as separate package layer; reduce ISO build coupling | No (build system) |
| 16 | Phase tasks labeled "ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО" | **CHANGE** | Explicitly classify each as VERIFY (hardware test), KEEP (verified), or REMOVE (outdated); add exit criteria | Yes (real hardware) |

---

## 3. CORRECTED ARCHITECTURE RECOMMENDATIONS per Section

### 1. KERNEL
- **KEEP linux-zen** as default — MuQSS scheduler + HZ=1000 gives best interactivity on fanless Core M
- Add `intel_idle.max_cstate=4` and `transparent_hugepage=never` to boot parameters
- **OPTIONAL: linux-lts** as fallback for users prioritizing stability over interactivity
- Remove `idle=poll` from all kernel command lines
- modprobed-db: optional for auto-modprobing, but adds build complexity; not recommended for initial ISO

### 2. CPU/INTEL P-STATE/HWP
- m3-7Y32 (Kaby Lake-Y) supports intel_pstate with HWP — no special flags needed, `enable_hwp` is default
- **Disable dynamic boost**: `hwp_dynamic_boost=0` (boot parameter) or via `/sys/module/processor/parameters/hwp_dynamic_boost=0`
- Use **powersave governor** (TLP handles this); do NOT use performance governor — kills battery
- Remove `idle=poll`; use `intel_idle.max_cstate=4` instead

### 3. i915/HD 615 (Kaby Lake)
- **enable_guc=3** — enables both GuC submission and HuC load (default -1 is auto, but explicit 3 is safe)
- **enable_fbc=1** — frame buffer compression for power savings
- **enable_psr=2** — PSR2 enable for panel power savings
- These are all safe; firmware (kbl_huc_4.0.0.bin, kbl_guc_70.1.1.bin) loads automatically
- RC6/D3 power states: default kernel behavior is fine; no need to disable RC6 unless specific stability issues arise

### 4. NVMe/APST
- Change `default_ps_max_latency_us` from 0 to **200000** (200ms) for better ASPT power savings
- Keep `nvme.noacpi=1` — correct for avoiding ACPI/NVMe conflicts on MacBook10,1
- Test suspend/resume with these settings before finalizing

### 5. POWER MANAGEMENT
- **TLP: KEEP** — sets governor powersave, boost disabled, ASPM powersave (not powersupersave), USB autosuspend
- **thermald: REMOVE or PASSIVE** — TLP already manages CPU power; thermald fights TLP; if kept, use `thermald --passive` 
- **ananicy-cpp: KEEP** — lightweight; tune priority levels for DE and browser only
- **PCIe ASPM**: Change TLP setting from `powersupersave` to `powersave`; test suspend/resume
- **USB autosuspend**: Keep TLP-managed; add specific quirks for hub devices if needed

### 6. ZRAM/VM
- **zram-generator: KEEP** — zram0 = RAM/2 (4GB for 8GB, 8GB for 16GB) with zstd compression
- Add `swappiness=10` to `/etc/sysctl.d/99-mavericks.conf`
- Add `vfs_cache_pressure=200` to preserve dentry/inode cache for desktop interactivity
- **Add `transparent_hugepage=never`** to kernel command line (see section 1)
- No disk swap partition — zram covers swap needs

### 7. THERMAL POLICY
- **Boost disable**: `intel_pstate.no_turbo=1` or `hwp_dynamic_boost=0` — critical for fanless to prevent thermal throttling
- **intel_idle.max_cstate=4** — already in boot params; keep it
- **No thermald** by default — TLP + ananicy-cpp suffice for thermal management
- **Monitor** package temperature via `sensors` or `cat /sys/class/thermal/thermal_zone*/temp`
- If thermal throttling occurs: consider `cpupower frequency-set -g powersave` + reduce load

### 8. APPLE HARDWARE
- **applespi**: Mandatory external USB-C input for bring-up; internal keyboard/trackpad = best-effort with 3-try strategy limit
  - Strategy 1: macbook12-spi-driver-dkms (AUR) on linux-zen
  - Strategy 2: linux-macbook kernel with applespi patches
  - Strategy 3: linux-lts + backport patches
  - If all 3 fail → mark "not supported", use USB-C permanently
- **BCM43602 Wi-Fi**: `lspci -nn -d 14e4:` to check revision
  - rev 03+ → broadcom-wl-dkms (AUR), blacklist brcmfmac/brcmsmac/b43/ssb/bcma
  - rev 01/02 → enable brcmfmac, blacklist broadcom-wl-dkms
- **Cirrus audio**: `speaker-test -c 2` to check built-in speakers
  - If silence → install macbook12-audio-driver (AUR)
  - If works → remove driver from auto-install list
- **applesmc**: loads automatically; reads fan/sensor data; no special config needed
- **Suspend/Resume**: test thoroughly after each driver change; applespi failures often cause freeze-on-resume

### 9. XFCE/MAVERICKS UI
- **Custom GTK3 theme (mavericks-theme)**: KEEP — provides skeuomorphic foundation (textures, gradients, shadows)
- **Icon theme**: Mavericks-era style; verify HiDPI (2304×1440) scaling works
- **Dock (plank)**: KEEP with ZoomEnabled=true and IconZoom=true
- **Top panel**: Xfce panel styled as minimal menu bar — no global menu plugin needed (adds complexity without benefit)
- **Cursor**: macOS-style cursor theme (Mavericks-Cursors)
- **Wallpapers**: Mavericks-inspired designs (no Apple assets)
- **Reality check**: True skeuomorphism (leather, paper textures) requires SCSS customization; expect "approximation" not replica

### 10. BROWSER
- **Firefox ESR 128.x: PREFERRED** — better web compatibility, uBlock Origin, extended security support
- **Epiphany/WebKitGTK 50.x**: viable alternative only if RAM < 4GB; lighter but fewer features and rendering quirks
- Install `uBlock Origin` and `Firefox SES` (Session Style Editor) for theme consistency
- Do NOT use Chrome/Chromium — they're heavier and less customizable for Mavericks aesthetic

### 11. PROJECT ARCHITECTURE
- **Separate hardware layer from visual layer** in archiso profile:
  - Move hardware selection (kernel params, modules, boot entries) to `scripts/hardware-selection.sh`
  - Keep theme packages (mavericks-theme, epiphany-mavericks-theme) as separate add-on layers
  - ISO profile should reference hardware script, not embed all config inline
- **archiso profile cleanup**: Remove embedded modprobe.conf, tlp.conf, kernel entries from releng — let hardware-selection.sh generate these at first boot
- **Bootloader**: Keep systemd-boot as primary; rEFInd as fallback in package list

### 12. MONTH-WITHOUT-HARDWARE PLAN
- **Classify each task explicitly**:
  - **VERIFY**: Requires real hardware test (applespi, audio, Wi-Fi revision, suspend/resume, thermal measurements) → owner + exit criteria
  - **KEEP**: Verified working in prior session → no further hardware test needed
  - **REMOVE**: Outdated or deprecated → document reason, remove from ISO profile
- **Create HARDWARE_TEST.md checklist** with specific commands + expected outcomes + go/no-go criteria
- **Set retry limit**: 3 different kernel/driver strategies maximum for any hardware component; after that, defer and document
- **Owner + deadline**: Each VERIFY task needs an assigned owner and realistic deadline; missed deadline → mark DEFERRED

---

**Audit Conclusion**: The original "Mavericks Linux" plan is largely sound in its core architecture (linux-zen, TLP, zram, Xfce base) but contains several outdated or unverified items that need correction before ISO finalization. The most critical items requiring hardware verification are: applespi keyboard/trackpad behavior, Cirrus audio speaker output, BCM43602 Wi-Fi revision detection, and NVMe APST stability. No claim is positively harmful if applied with the corrections noted above.