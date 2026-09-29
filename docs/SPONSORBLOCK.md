# SponsorBlock Integration — Privacy & Controls

## Overview

SponsorBlock is a crowdsourced system that skips sponsor segments, intros, outros, and other non-content parts of YouTube videos. This project integrates it in two independent paths:

| Path | Component | Status | Privacy Implication |
|------|-----------|--------|---------------------|
| **Firefox tabs** | `sponsorBlocker@ajay.app` extension (force-installed via `policies.json`) | **ACTIVE** | Video ID + segment hashes sent to `sponsor.ajay.app` per video played in Firefox |
| **mv-ytplayer** (mpv + yt-dlp) | yt-dlp `--sponsorblock-remove` flag (opt-in via config) | **OPT-IN (disabled by default)** | Video ID + segment hashes sent to `sponsor.ajay.app` per video played via mv-ytplayer |

---

## What Data Leaves the Machine

**Both paths** query the SponsorBlock API at `https://sponsor.ajay.app` (default) or a custom mirror.

**Per-video request** (HTTP GET):
```
GET https://sponsor.ajay.app/api/skipSegments?videoID=<VIDEO_ID>&categories=<CATEGORIES>
```

**Data sent:**
- **Video ID** (YouTube's 11-char identifier) — reveals exactly which video you're watching
- **Category filter** — which segment types you want (sponsor, intro, outro, etc.)

**Data received:**
- Segment timestamps (start/end) and category labels for that video

**No account, no cookies, no persistent identifier** — but the video ID alone is a strong fingerprint of viewing history. The SponsorBlock server operator (or anyone with access to their logs) can build a profile of videos you've watched.

**This is a deliberate feature, not a bug** — SponsorBlock requires a central database to function. The trade-off: automatic segment skipping vs. disclosing your video watches to a third party.

---

## Firefox Path (Browser Tabs)

**Enforcement point:** `configs/firefox/policies.json` → `ExtensionSettings.sponsorBlocker@ajay.app.installation_mode = "force_installed"`

**Behavior:**
- Extension auto-installs on first Firefox run (downloads from AMO)
- Runs in-browser, intercepts YouTube pages
- Sends video ID to `sponsor.ajay.app` when you load a YouTube video
- Skips segments in-page (no re-encoding)

**User toggle:**
- Click the SponsorBlock extension icon in Firefox toolbar → "Disable on this site" or "Disable everywhere"
- **Cannot uninstall** (force-installed by policy), but can be disabled per-session or globally via extension UI
- To re-enable: extension icon → "Enable"

**To disable via policy (admin):** Remove `sponsorBlocker@ajay.app` from `ExtensionSettings` in `policies.json` and rebuild ISO.

---

## mv-ytplayer Path (mpv + yt-dlp)

**Enforcement point:** `packages/mavericks-apps/src/mavericks-apps/bin/mv-ytplayer` → yt-dlp `--sponsorblock-remove` flag (controlled by config)

**Behavior:**
- **Disabled by default** (no SponsorBlock flags passed to yt-dlp)
- When enabled: yt-dlp queries SponsorBlock API *before* playback, removes marked segments from the stream fed to mpv
- Uses `--sponsorblock-remove default` (removes: sponsor, intro, outro, selfpromo, preview, filler, interaction, music_offtopic, hook, poi_highlight — i.e. "all" non-content)
- One-shot per invocation; no persistent daemon

**User toggle (config file):**
```
# /etc/mv-ytplayer/sponsorblock.conf
# Set to "1" to enable SponsorBlock segment removal
# Set to "0" or remove file to disable (default)
MV_YT_SPONSORBLOCK=1
```

**Environment override:**
```bash
MV_YT_SPONSORBLOCK=1 mv-ytplayer <URL>   # enable for this run
MV_YT_SPONSORBLOCK=0 mv-ytplayer <URL>   # disable for this run
```

**Categories** (if you want finer control, edit the script's `SB_CATEGORIES` variable):
- `default` — all non-content categories (sponsor, intro, outro, selfpromo, preview, filler, interaction, music_offtopic, hook, poi_highlight)
- `all` — includes `chapter` and `poi_highlight`
- Comma-separated list: `sponsor,intro,outro`

---

## Quick Decision Guide

| If you… | Do this |
|---------|---------|
| Want SponsorBlock everywhere, accept privacy trade-off | Keep Firefox extension enabled; set `MV_YT_SPONSORBLOCK=1` in `/etc/mv-ytplayer/sponsorblock.conf` |
| Want SponsorBlock only in browser | Keep Firefox extension enabled; leave mv-ytplayer default (disabled) |
| Want SponsorBlock only in mv-ytplayer | Disable Firefox extension via toolbar icon; set `MV_YT_SPONSORBLOCK=1` |
| Want **no** SponsorBlock (zero third-party video-ID requests) | Disable Firefox extension via toolbar icon; leave mv-ytplayer default (disabled) |
| Want to use a **self-hosted/alternative SponsorBlock API** | Set `MV_YT_SPONSORBLOCK_API="https://your-mirror.example.com"` in config (mv-ytplayer only); Firefox extension uses hardcoded upstream |

---

## Verification

**Check Firefox:** Open `about:addons` → Extensions → SponsorBlock → verify "Enabled" or "Disabled"

**Check mv-ytplayer:**
```bash
# With config enabled
MV_YT_SPONSORBLOCK=1 mv-ytplayer --explain "https://youtube.com/watch?v=..."
# Look for "SponsorBlock: ENABLED (categories: default)" in output

# With config disabled (default)
mv-ytplayer --explain "https://youtube.com/watch?v=..."
# Look for "SponsorBlock: DISABLED" in output
```

**Network verification (both paths):**
```bash
# Watch DNS/HTTP for sponsor.ajay.app
sudo tcpdump -n -i any port 443 | grep sponsor.ajay.app
# Or use browser devtools / mitmproxy
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `configs/firefox/policies.json` | Force-installs SponsorBlock extension in Firefox |
| `packages/mavericks-apps/src/mavericks-apps/bin/mv-ytplayer` | Video player script; reads `MV_YT_SPONSORBLOCK` config |
| `/etc/mv-ytplayer/sponsorblock.conf` | **User toggle** for mv-ytplayer (create to enable) |
| `docs/SPONSORBLOCK.md` | This document |