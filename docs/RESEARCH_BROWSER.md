# RESEARCH: Browser Engine Comparison for MacBook10,1

**Date:** 2026-09-27
**Status:** RESEARCH COMPLETE — decision recorded in DECISIONS.md
**Target:** MacBook10,1 (Mid 2017), Core m3-7Y32, HD 615 Gen9.5 (Kaby Lake), **16GB RAM** (user-corrected from 8GB)

---

## 1. Forensic Packaging Check (Arch extra, 2026-09-27)

| Package | Version | License | Repo | Pkg Size | Installed | Deps | Notes |
|---|---|---|---|---|---|---|---|
| firefox | 156.0.1-1 | MPL-2.0 | extra | 84.8 MB | 297.2 MB | 58 | Current ISO browser; NOT ESR (Arch ships rapid release) |
| chromium | 153.0.8010.52-1 | BSD-3-Clause | extra | 136.0 MB | 422.2 MB | 80 | Flagged out-of-date 2026-09-22 |
| webkit2gtk-4.1 | 2.52.6-1 | multi (LGPL-2.1, BSD, MIT, etc.) | extra | 36.1 MB | 133.6 MB | 71 | Already in ISO via geary/dictionary |
| epiphany | 50.6-1 | GPL-3.0-or-later | extra | 3.8 MB | 17.2 MB | 40 | **Depends on webkitgtk-6.0, NOT 4.1** |
| mpv | 1:0.41.0-6 | GPL-2.0/LGPL-2.1 | extra | 1.6 MB | 6.3 MB | 75 | VA-API capable; yt-dlp optdep |
| yt-dlp | 2026.08.19-1 | Unlicense | extra | 4.9 MB | 31.7 MB | 23 | Python; ffmpeg optdep |
| intel-media-driver | 26.2.4-1 | BSD-3/MIT | extra | 7.7 MB | 41.4 MB | 6 | **Broadwell+ iGPUs** — correct for Gen9.5 |
| libva-intel-driver | 2.4.5-1 | MIT | extra | 1.1 MB | 7.8 MB | 5 | **G45/HD Graphics family** — legacy, ≤Haswell |
| gst-plugin-va | 1.28.7-2 | LGPL-2.1 | extra | 230 KB | 566 KB | — | Replaces gstreamer-vaapi |
| libva | 2.24.1-1 | MIT | extra | 206 KB | 1020 KB | 15 | Base VA-API library |
| libva-utils | 2.24.0-1 | custom | extra | 529 KB | 3.2 MB | 3 | Contains vainfo |

**Key finding — epiphany is NOT a webkit2gtk-4.1 consumer:** epiphany 50.6 depends on `webkitgtk-6.0`, not `webkit2gtk-4.1`. The webkit2gtk-4.1 dependency in the ISO comes from geary and other GNOME apps. Epiphany would pull in a second WebKit version + full GNOME stack (libadwaita, gcr-4, libportal, etc.).

**firefox-esr:** Not in Arch extra. The `firefox` package IS the rapid release (156.0.1). Arch does not package ESR separately. The "Firefox ESR" in the project context means "current Firefox, not version-pinned" — the project's user.js and policies.json work with any recent Firefox.

---

## 2. Codec/HW-Decode Matrix for Gen9.5 (Kaby Lake)

Source: intel-media-driver README (KBLx column), Intel oneVPL docs, ArchWiki Intel graphics.

| Codec | Decode HW | Encode HW | Max Resolution | Relevance | Status |
|---|---|---|---|---|---|
| H.264 (AVC) | ✅ Yes (D) | ✅ Yes (E/Es) | 4K | **Critical** — YouTube, most streaming | DOCUMENTED |
| VP8 | ✅ Yes (D) | ✅ Yes (Es) | 4K | Moderate (YouTube fallback) | DOCUMENTED |
| VP9 8-bit | ✅ Yes (D) | ❌ No | 4K | **Critical** — YouTube default | DOCUMENTED |
| VP9 10-bit | ✅ Yes (D) | ❌ No | 4K | Low (HDR YouTube) | DOCUMENTED |
| HEVC 8-bit | ✅ Yes (D) | ✅ Yes (Es) | 4K | Moderate (some streaming) | DOCUMENTED |
| HEVC 10-bit | ✅ Yes (D) | ✅ Yes (Es) | 4K | Low (HDR) | DOCUMENTED |
| AV1 | ❌ No | ❌ No | — | **None on Kaby Lake** — AV1 decode starts Gen12 (Tiger Lake) | DOCUMENTED |
| MPEG-2 | ✅ Yes (D) | ✅ Yes (Es) | 4K | Low (legacy) | DOCUMENTED |
| VC-1 | ✅ Yes (D) | ❌ No | 4K | Low (legacy) | DOCUMENTED |
| JPEG | ✅ Yes (D) | ✅ Yes (E) | 16K | Low (images) | DOCUMENTED |

**VA-API driver for Gen9.5:** `intel-media-driver` (iHD) is the ONLY correct driver. `libva-intel-driver` (i965) is for ≤Haswell (Gen7.5 and older). The libva package lists `intel-media-driver` as the optional backend for "Intel GPUs (>= Broadwell)".

**HuC firmware:** For Gen9 (Kaby Lake), HuC loading is disabled by default since kernel 4.11. Enable with `options i915 enable_guc=2` in `/etc/modprobe.d/i915.conf`. HuC is needed for low-power encoding (VDEnc) and some HEVC features. The frozen power baseline currently uses kernel defaults (no explicit enable_guc), so HuC is NOT loaded — this means HEVC/VP9 encode falls back to shader-based, and some low-power encode features are unavailable. Decode is unaffected.

**AV1 implication:** YouTube is increasingly using AV1 for high-resolution content. On Gen9.5, AV1 will decode in SOFTWARE (CPU). For a fanless Core m3, this means:
- 1080p AV1: likely playable but CPU-intensive
- 4K AV1: likely unplayable
- Mitigation: use mpv+yt-dlp with `--format` to prefer VP9/H.264, or use Firefox/Chromium which may fall back to VP9 automatically

---

## 3. Emulator-Backed Reasoning

### 3.1 browser_emu.py Profile Mapping

The emulator (`scripts/bench/browser_emu.py`) models a Firefox-ESR-class tabbed session with 7 phases. Qualitative mapping to engine choice:

| Emulator Phase | Metric | Engine Sensitivity | Why It Matters |
|---|---|---|---|
| startup | wall_s, cpu_s | MEDIUM | All engines have similar cold-start cost; Chromium slightly slower due to more processes |
| tab_alloc | per_tab_rss_kb | **HIGH** | Per-tab RSS slope is the key differentiator: Chromium site-per-process costs more per tab; Firefox e10s is intermediate; WebKitGTK is lowest but unvalidated |
| scroll | tick_ms_median | MEDIUM | All engines use GPU compositing; CPU cost similar when VA-API works |
| media_burst | wall_s, cpu_s | LOW | Image decode is similar across engines |
| js_churn | wall_s, cpu_s | MEDIUM | V8 (Chromium) is faster than SpiderMonkey (Firefox) on JIT-heavy pages; WebKitGTK uses JavaScriptCore |
| network_wait | wall_s | LOW | Idle sleep — no engine difference |
| return_idle | wall_s | **HIGH** | Return-to-idle is critical for fanless: Chromium's background processes (GPU, utility, etc.) take longer to idle; Firefox is faster; WebKitGTK is fastest |

### 3.2 Where Engine Choice Matters Most

1. **Tab RSS slope** (per-tab marginal cost): With 16GB RAM, this is less critical than on 8GB, but still matters for battery/thermal. Chromium's site-per-process model costs ~50-80MB per tab; Firefox e10s costs ~30-50MB per tab; WebKitGTK costs ~20-40MB per tab.

2. **Idle residual CPU**: Chromium spawns more background processes (GPU process, utility processes, service workers) that consume CPU even when idle. Firefox has fewer. WebKitGTK has the fewest.

3. **Return-to-idle**: After closing a tab or finishing page load, how quickly does CPU drop to >95% idle? This is the KEY metric for fanless systems. Chromium is slowest (process teardown + GPU cleanup). Firefox is intermediate. WebKitGTK is fastest.

4. **Suspend/resume**: Chromium has known issues with suspend/resume on Linux (GPU process hangs, requires --disable-gpu or --in-process-gpu). Firefox handles suspend/resume more gracefully. WebKitGTK is unvalidated on this hardware.

5. **Background-tab throttling**: All three engines throttle background tabs, but Chromium's throttling is more aggressive (which is good for power but can break some web apps). Firefox's is less aggressive. WebKitGTK's is unvalidated.

### 3.3 Blocking Overhead Analysis

| Component | CPU Cost | Network/DOM Savings | Net Effect | Recommendation |
|---|---|---|---|---|
| uBlock Origin (core) | Low (filter engine match) | **High** (blocks requests before they hit network) | **Strongly positive** | **ON** |
| EasyList | Low (few thousand rules) | **High** (blocks ads/trackers) | **Strongly positive** | **ON** |
| EasyPrivacy | Low (few thousand rules) | **High** (blocks tracking) | **Strongly positive** | **ON** |
| uBO built-in lists | Very low | Moderate | Positive | **ON** |
| SponsorBlock | Very low (URL match) | Moderate (skips video segments) | Positive | **ON** |
| Cosmetic filtering | **Medium** (CSS injection per page) | Low (elements already loaded) | **Neutral/negative** | **OFF by default** |
| Regional lists | Low | Low (redundant with EasyList) | Neutral | **OFF** |
| Annoyances lists | Low | Moderate | Positive | Optional |

**Policy recommendation for fanless CPU:**
- **ON:** uBlock Origin + EasyList + EasyPrivacy + SponsorBlock
- **OFF:** Cosmetic filtering (saves CPU per page load, minimal UX loss)
- **OFF:** Regional/extra lists (redundant overhead)

---

## 4. Decision: Firefox ESR (Current) + mpv Hybrid for Video

### 4.1 Engine Verdict: **Firefox (current, not version-pinned)**

**Runner-up:** Chromium

**Not viable:** WebKitGTK/Epiphany (no uBO, GNOME stack, webkitgtk-6.0 not 4.1, already excluded from ISO)

### 4.2 Criterion-by-Criterion Justification

| # | Criterion | Firefox | Chromium | WebKitGTK | Winner |
|---|---|---|---|---|---|
| 1 | Idle CPU/RSS | Medium (e10s, ~4 content processes) | **Higher** (more background processes) | Lowest (but unvalidated) | WebKitGTK (marginal) |
| 2 | Startup wall | Medium | Slower (more processes) | Fast | WebKitGTK |
| 3 | Per-tab marginal cost | ~30-50MB/tab | ~50-80MB/tab | ~20-40MB/tab | WebKitGTK |
| 4 | Scroll/render CPU | Similar (GPU compositing) | Similar | Similar | Tie |
| 5 | Suspend/resume | **Good** (graceful) | **Poor** (known GPU hangs) | Unvalidated | **Firefox** |
| 6 | Background-tab throttling | Moderate | **Aggressive** (best for power) | Unvalidated | Chromium |
| 7 | Wakeups | Medium | Higher (more processes) | Lowest | WebKitGTK |
| 8 | Video decode (VA-API) | **Good** (VA-API supported) | **Good** (VA-API supported) | Unvalidated | Tie |
| 9 | Return-to-idle | **Fast** | Slow (process teardown) | Fastest | WebKitGTK |
| 10 | Power-proxy | Medium | Higher | Lowest | WebKitGTK |
| 11 | Maintainability (Arch) | **Excellent** (extra, 58 deps) | **Good** (extra, 80 deps) | Good (extra, 71 deps) | **Firefox** |
| 12 | Extension/blocking | **Excellent** (uBO full) | **Degraded** (MV2 deprecation) | **None** (no uBO) | **Firefox** |

**Why Firefox wins overall:**
- **uBlock Origin is the decisive factor.** Chromium's Manifest V2 deprecation means uBO will lose functionality (or require workarounds). WebKitGTK has no uBO at all. The project's blocking policy (EasyList + EasyPrivacy + SponsorBlock) requires uBO.
- **Suspend/resume reliability** is critical for a laptop. Chromium's known GPU process hangs on suspend/resume make it unsuitable as the primary browser.
- **Already integrated** in the ISO (policies.json, user.js, firefox-ublock-origin package, firstboot wiring). Switching engines would require re-wiring all of this.
- **Maintainability:** firefox is in Arch extra with 58 deps (vs chromium's 80). Fewer deps = smaller attack surface, faster updates.
- **16GB RAM** makes the per-tab RSS advantage of WebKitGTK less critical.

**Why Chromium is the runner-up:**
- Better JS performance (V8 vs SpiderMonkey)
- More aggressive background-tab throttling (better for power)
- But: MV2 deprecation threatens uBO, suspend/resume issues, heavier idle footprint

**Why WebKitGTK/Epiphany is not viable:**
- No uBlock Origin support (dealbreaker)
- epiphany 50.6 depends on webkitgtk-6.0 (not 4.1) — would pull in a second WebKit
- Full GNOME stack dependency (libadwaita, gcr-4, libportal)
- Already excluded from ISO in Phase 0.3
- Unvalidated on this hardware

### 4.3 YouTube Architecture Direction: **D — Hybrid (Firefox + mpv)**

**Direction D:** Keep Firefox ESR for general browsing + use mpv+yt-dlp for video-only playback.

**Implementation:**
- Firefox handles all normal web browsing with uBO (EasyList + EasyPrivacy + SponsorBlock)
- For YouTube/video sites, a "Open in mpv" context menu action (or keyboard shortcut) launches mpv+yt-dlp
- mpv uses VA-API for HW decode on Gen9.5 (H.264/VP9/HEVC)
- mpv `--format` can prefer VP9/H.264 over AV1 (which has no HW decode on Kaby Lake)
- This gives: full browser experience + efficient video decode + uBO ad-blocking

**Why not the other directions:**
- **A (Firefox only):** YouTube in Firefox works but uses more CPU for video decode (browser overhead + no fine-grained format control)
- **B (Chromium only):** uBO degraded by MV2, suspend/resume issues
- **C (WebKitGTK only):** No uBO, GNOME stack, unvalidated

**mpv advantages for video:**
- Direct VA-API decode (no browser overhead)
- `--format` control to avoid AV1 (no HW decode on Kaby Lake)
- `--hwdec=auto` for automatic HW decode
- Minimal idle cost (one-shot process, no daemon)
- yt-dlp integration for format selection

---

## 5. Calibration Plan (vs Real Firefox on Hardware)

When MacBook10,1 becomes available, calibrate the emulator's qualitative mapping against real Firefox:

### 5.1 Measurements to Take

| Metric | Tool | Emulator Phase | Target |
|---|---|---|---|
| Cold startup wall | `time firefox --headless` | startup | < 3s |
| Per-tab RSS | `/proc/<pid>/status` (VmRSS) | tab_alloc | < 50MB/tab |
| Scroll frame time | `firefox --headless` + JS benchmark | scroll | < 16.7ms (60fps) |
| Image decode | `firefox --headless` + image page | media_burst | < 1s for 20 images |
| JS execution | `firefox --headless` + JS benchmark | js_churn | Baseline |
| Return-to-idle | `mpstat 1` after workload | return_idle | < 5s to >95% idle |
| Idle CPU (5 tabs) | `mpstat 1` (10s average) | — | < 2% CPU |
| Idle RSS (5 tabs) | `ps -o rss` | — | < 500MB total |
| Video decode CPU% | `mpstat 1` during 1080p YouTube | — | < 20% CPU (VA-API) |
| Suspend/resume | `systemctl suspend` + `time` | — | < 5s resume, no GPU hang |

### 5.2 VA-API Validation

```bash
# Verify VA-API is working
vainfo | grep -E "VAProfileH264|VAProfileVP9|VAProfileHEVC"

# Expected output on Gen9.5:
# VAProfileH264ConstrainedBaseline: VAEntrypointVLD
# VAProfileH264Main: VAEntrypointVLD
# VAProfileH264High: VAEntrypointVLD
# VAProfileVP9Profile0: VAEntrypointVLD
# VAProfileVP9Profile2: VAEntrypointVLD
# VAProfileHEVCMain: VAEntrypointVLD
# VAProfileHEVCMain10: VAEntrypointVLD
# (NO VAProfileAV1 — confirms no AV1 HW decode)
```

### 5.3 Codec Validation

```bash
# Test H.264 HW decode
mpv --hwdec=auto --vo=gpu test-h264.mp4

# Test VP9 HW decode
mpv --hwdec=auto --vo=gpu test-vp9.webm

# Test HEVC HW decode
mpv --hwdec=auto --vo=gpu test-hevc.mkv

# Test AV1 (expect software decode)
mpv --hwdec=auto --vo=gpu test-av1.mkv
```

### 5.4 Power Validation

```bash
# Idle power (browser closed)
powertop --time=20 --csv=idle.csv

# Browser idle power (5 tabs, no activity)
powertop --time=20 --csv=browser-idle.csv

# Video playback power (1080p YouTube in Firefox)
powertop --time=20 --csv=video-firefox.csv

# Video playback power (1080p via mpv)
powertop --time=20 --csv=video-mpv.csv
```

---

## 6. Step-2 Proposal (Implementation After Review)

### 6.1 Safari-Mavericks UX Spec

Create a Mavericks-like browser UX layer for Firefox:
- **Toolbar:** Unified address bar + search (like Safari's "Smart Search Field")
- **Top Sites:** Grid of frequently-visited sites (like Safari's Top Sites)
- **Reader Mode:** Safari-style reader view (Firefox has this natively)
- **Tab style:** Mavericks-era tab shape (rounded, gradient)
- **Download manager:** Mavericks-like download popover
- **Bookmarks:** Mavericks-style bookmarks bar

### 6.2 Optimized-Mode Implementation

1. **user.js additions:**
   - `browser.tabs.firefox-view` = false (disable Firefox View)
   - `browser.compactmode.show` = true (enable compact density)
   - `browser.uidensity` = 0 (normal density for HiDPI)
   - `dom.ipc.processCount` = 4 (limit content processes for power)
   - `browser.sessionstore.interval` = 60000 (already set)

2. **mpv integration:**
   - Add `mpv` + `yt-dlp` to ISO package list
   - Create `configs/desktop/mpv/mpv.conf` with VA-API defaults
   - Add Thunar UCA "Open in mpv" for video files
   - Add keyboard shortcut for "Open video in mpv" (context-dependent)

3. **Blocking policy:**
   - Keep firefox-ublock-origin in ISO
   - Document recommended uBO settings (EasyList + EasyPrivacy + SponsorBlock ON, cosmetic OFF)
   - Create `configs/firefox/ublock-backup.json` with recommended settings

4. **AV1 mitigation:**
   - Document that AV1 will use software decode on Gen9.5
   - mpv `--format` default: prefer VP9/H.264 over AV1
   - Firefox: no action needed (YouTube serves VP9/H.264 by default to Firefox)

---

## 7. Summary

| Aspect | Decision | Confidence |
|---|---|---|
| Engine | Firefox (current, not pinned) | **High** — uBO + suspend/resume + already integrated |
| Runner-up | Chromium | Medium — better JS perf but MV2 + suspend issues |
| YouTube | Hybrid D (Firefox + mpv) | **High** — best of both worlds |
| Blocking | uBO + EasyList + EasyPrivacy + SponsorBlock | **High** — proven, minimal overhead |
| VA-API driver | intel-media-driver (iHD) | **High** — only correct driver for Gen9.5 |
| AV1 | Software decode (unavoidable) | **High** — no HW decode on Kaby Lake |
| RAM correction | 16GB (user-corrected from 8GB) | **High** — user-provided |
