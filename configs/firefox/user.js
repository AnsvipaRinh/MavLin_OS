// user.js — Mavericks Firefox baseline (current ESR, NOT version-pinned)
// Every non-default has a reason. Hardware-dependent items marked EXPERIMENT.
// Safe baseline first; acceleration validated on hardware.

// --- Startup / UI (safe baseline) ---
user_pref("browser.startup.homepage", "about:home");
user_pref("browser.newtabpage.enabled", true);
user_pref("browser.toolbars.bookmarks.visibility", "newtab");
user_pref("browser.uidensity", 0);                    // normal density; compact breaks HiDPI
user_pref("browser.theme.color_scheme", 1);           // light (Mavericks)
user_pref("widget.non-native-theme.enabled", true);   // allow GTK theme to apply

// --- Tabs / Toolbar (Safari-Mavericks UX, see docs/SAFARI_SPEC.md) ---
user_pref("browser.tabs.drawInTitlebar", true);       // tabs in title bar (compact)
user_pref("browser.tabs.closeButtons", 1);            // close button on active tab only
user_pref("browser.tabs.firefox-view", false);        // no Firefox View (not Mavericks)
user_pref("browser.tabs.firefox-view-next", false);   // no Firefox View Next
user_pref("browser.tabmanager.enabled", false);       // no tab manager button
user_pref("browser.sharepane.enabled", false);        // no share button on Linux

// --- Top Sites (Mavericks-style grid) ---
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
user_pref("browser.newtabpage.activity-stream.feeds.topsites", true);
user_pref("browser.newtabpage.activity-stream.feeds.section.highlights", false);

// --- Fonts (Mavericks look) ---
user_pref("font.default", "sans-serif");
user_pref("font.name.sans-serif.x-western", "San Francisco");
user_pref("font.name.serif.x-western", "Georgia");
user_pref("font.name.monospace.x-western", "Menlo");

// --- Privacy baseline (safe, no perf cost) ---
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.donottrackheader.enabled", true);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("app.shield.optoutstudies.enabled", false);

// --- Media / autoplay (safe baseline) ---
user_pref("media.autoplay.default", 1);               // block audio autoplay; video allowed

// --- AV1: prefer HW codecs, avoid AV1 SW decode on Gen9.5 ---
// media.av1.enabled is a real pref (Firefox 93+). Gen9.5 has no AV1 HW decode.
// Leaving default (true) means AV1 plays SW — costly on Core M. Prefer off.
// Comment out if site compatibility is affected; yt-dlp path avoids AV1 entirely.
// user_pref("media.av1.enabled", false);             // E-AV1: test site compat

// --- Cache / disk (SSD preservation, safe) ---
user_pref("browser.cache.disk.enable", true);
user_pref("browser.cache.disk.capacity", 102400);     // 100MB cap; memory cache handles rest
user_pref("browser.sessionstore.interval", 60000);    // 60s (default 15s) — fewer SSD writes

// --- Downloads (Mavericks behavior: save to default dir) ---
user_pref("browser.download.useDownloadDir", true);
user_pref("browser.download.start_downloads_in_tmp_dir", false);

// --- History / Find ---
user_pref("places.history.enabled", true);
user_pref("findbar.highlightAll", true);
user_pref("findbar.findAgainOnScroll", false);

// --- Extensions (uBlock Origin installed as system package firefox-ublock-origin) ---
user_pref("extensions.autoDisableScopes", 0);

// --- EXPERIMENT (validate on hardware; DO NOT assume) ---
// user_pref("media.ffmpeg.vaapi.enabled", true);     // E-VIDEO: test VAAPI on HD 615
// user_pref("gfx.webrender.all", true);              // E-WR: test WebRender vs basic compositor
// user_pref("layers.acceleration.force-enabled", true); // E-GPU: only if WebRender problematic
// user_pref("media.hardware-video-decoding.force-enabled", true); // E-VIDEO2
// user_pref("dom.ipc.processCount", 6);              // E-PROC: test 4 vs 6 vs 8 on 8-16GB
// user_pref("browser.tabs.unloadOnLowMemory", false); // E-MEM: test on 8GB

// Background-tab throttling prefs (MDN Page Visibility API + Firefox source modules/libpref/init/all.js)
// dom.min_background_timeout_value (default 1000)
// dom.min_tracking_background_timeout_value (default 10000)
// dom.timeout.tracking_throttling_delay (default 30000)
// dom.timeout.throttling_delay (default 30000)
// dom.timeout.enable_budget_timer_throttling (default true)
// Values = verified defaults (intent: pin against default drift; background-wakeup-class P0 guard)
// Do NOT invent other prefs.
user_pref("dom.min_background_timeout_value", 1000);
user_pref("dom.min_tracking_background_timeout_value", 10000);
user_pref("dom.timeout.tracking_throttling_delay", 30000);
user_pref("dom.timeout.throttling_delay", 30000);
user_pref("dom.timeout.enable_budget_timer_throttling", true);
