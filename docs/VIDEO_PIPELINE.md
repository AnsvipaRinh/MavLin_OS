# Video Pipeline — codec selection & optimized playback

Status: IMPLEMENTED (pre-hardware). HW decode validation → NEEDS_HARDWARE_TEST.md.

## 1. Codec ranking (MEASURED, host-SW tier)

Source: `scripts/bench/results/video-codecs.json` (real run, not estimate).
Fixture: 1080p clips, 120 frames, 3 repeats, median. Deadline 41.67 ms/frame (24 fps).
Run metadata: AMD Ryzen 7 5800HS, 2 cores, ffmpeg n9.0.2, WSL2, 2026-09-28.

| Rank | Codec | cost/frame | ffmpeg fps | wall (120f) | CPU% | RSS | HW decode Gen9.5 (HD 615) | 1080p on Core m3-7Y32 |
|---|---|---|---|---|---|---|---|---|
| 1 | H.264 (avc1) | **4.20 ms** | 238.2 | 0.504 s | 107.0 | 65.3 MB | YES — preferred tier | Feasible: HW primary; SW fallback measurable |
| 2 | VP9 (vp09) | **5.57 ms** | 179.7 | 0.668 s | 102.2 | 73.6 MB | YES — preferred tier | Feasible: HW primary; SW fallback measurable |
| 3 | HEVC (hev1) | **7.99 ms** | 125.2 | 0.959 s | 111.0 | 97.8 MB | YES — preferred tier | Feasible: HW primary; SW fallback measurable (heaviest SW) |
| 4 | AV1 (av01) | **5.38 ms** | 185.8 | 0.646 s | 100.2 | 103.8 MB | NO — SW-only on Gen9.5 | Last resort only: no HW engine on target; SW cost moderate but SW-only |

All four codecs meet the 41.67 ms/frame deadline in host SW (max 7.99 ms). Ranking is by
**target feasibility** (HW engine availability on Gen9.5), not raw SW speed — AV1's SW
number is fine on this host but irrelevant on MacBook10,1 where it can never offload.

720p reference (same run): h264 2.37 ms, vp9 2.70 ms, hevc 4.00 ms, av1(SVT) 2.80 ms per frame.

## 2. Measurement tiers

| Tier | Status | What it proves |
|---|---|---|
| host-SW | **MEASURABLE** (this run) | Full numbers + ordering across codecs; SW fallback cost ceiling |
| VA-API | **HW-ONLY** | Unmeasurable on host: `vainfo` probe finds no usable VA driver (`vaGetDriverNames() failed`). Validate on target via `mpv --hwdec=auto` + `intel-media-driver` on HD 615 |
| power/thermal | **HW-ONLY** | Unmeasurable here; needs MacBook10,1 power/thermal instrumentation (battery discharge, RAPL/package vs whole-system, fanless throttling behavior) |

## 3. Selector rule (mv-ytplayer)

`packages/mavericks-apps/src/mavericks-apps/bin/mv-ytplayer` builds a yt-dlp format chain
in preference order. Real `--explain` output (captured 2026-09-28, host):

```
bestvideo[height<=1080][vcodec^=avc1]+bestaudio/best,bestvideo[height<=1080][vcodec^=vp09]+bestaudio/best,bestvideo[height<=1080][vcodec^=hev1]+bestaudio/best,bestvideo[height<=1080][vcodec!=av01]+bestaudio/best,bestvideo[height<=1080]+bestaudio/best
```

Chain semantics:

1. **avc1** — H.264, HW decode on Gen9.5 (preferred)
2. **vp09** — VP9, HW decode on Gen9.5
3. **hev1** — HEVC, HW decode on Gen9.5
4. **non-av01** — any codec except AV1 (last resort if no preferred codec)
5. **best** — ultimate fallback, any codec (AV1 reachable only here)

AV1 is excluded from positive preference: Gen9.5 has no AV1 HW engine, so an AV1
positive branch would silently force SW decode on the fanless Core M. Quality cap
`MV_YT_MAX_HEIGHT` (default 1080) applies to every branch. Audio is a separate
stream (`bestaudio`) merged by mpv — no audio codec decision in the chain.

### 3.1 Codec policy layer

The codec ranking is defined in `configs/mv-ytplayer/codec-policy.conf` — an easily
editable policy file. Edit the file to change codec preference order. The selector
chain is built from this list at runtime.

| Codec | vcodec prefix | HW decode Gen9.5 | Expected CPU (SW) | Expected GPU (HW) | Fallback |
|---|---|---|---|---|---|
| H.264 | avc1 | YES | 4.20 ms/frame | Lowest | Primary choice |
| VP9 | vp09 | YES | 5.57 ms/frame | Low | If avc1 unavailable |
| HEVC | hev1 | YES | 7.99 ms/frame | Low | If avc1/vp09 unavailable |
| AV1 | av01 | NO (SW-only) | 5.38 ms/frame | N/A (SW only) | Last resort (branch 5) |

**NO-CONCLUSION**: Final codec choice comes from measured power/thermal on MacBook10,1,
not from host bench. The host-SW numbers above are a ceiling, not a target. The
policy is a starting point based on Gen9.5 HW availability. See
`docs/HW_BROWSER_MATRIX.md` for the 4-mode measurement plan to validate on hardware.

## 4. Optimized playback mode (BY CONSTRUCTION)

`mv-ytplayer` is the optimized video path. It is not "Firefox with a lighter page" —
the page layer does not exist:

- **No page JS/DOM** — mpv plays the media stream URL directly (resolved by yt-dlp);
  there is no document, no script engine, no rendering tree for the video.
- **No ads** — the stream URL is the media file itself; no ad segments, no ad JS.
- **No tracking** — no page means no beacons, no telemetry, no cookies for playback.
- **No polling** — no page timers, no background wakeups; playback is event-driven
  inside mpv.
- **No network-page** — one stream fetch (+ separate audio stream); no page
  resources, no CSS/fonts/images.
- **One-shot process** — nothing resident after playback ends; no daemon, no
  autostart, no idle cost (PERF_AUDIT Phase-E: IGNORE-class).
- **HW decode** — `--hwdec=auto` picks VA-API/VDPAU when available; graceful SW
  fallback when not.
- **Audio via separate stream** — `bestaudio` merged by mpv; no muxed-container
  overhead for the video decision.

Contrast with Firefox page playback: full page JS + DOM, ad delivery, tracking,
background timers (pinned by `configs/firefox/user.js` throttling prefs as a
mitigation, not an elimination). Firefox remains the general-purpose path;
`mv-ytplayer` is the dedicated video path (Thunar UCA "Play video-only", opt-in).

## 5. Validation

- `scripts/test-mv-ytplayer.py`: 19/19 pass (chain construction, cap respected, av01
  excluded from positive branches, --explain paths, mpv flags, usage errors).
- `bash -n` clean; `desktop-file-validate` clean; `check-sync.sh` ALL CHECKS PASSED.
- HW decode behavior on Gen9.5 → NEEDS_HARDWARE_TEST.md (VA-API validation).
