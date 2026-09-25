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

// --- Cache / disk (SSD preservation, safe) ---
user_pref("browser.cache.disk.enable", true);
user_pref("browser.cache.disk.capacity", 102400);     // 100MB cap; memory cache handles rest
user_pref("browser.sessionstore.interval", 60000);    // 60s (default 15s) — fewer SSD writes

// --- Extensions (uBlock Origin installed as system package firefox-ublock-origin) ---
user_pref("extensions.autoDisableScopes", 0);

// --- EXPERIMENT (validate on hardware; DO NOT assume) ---
// user_pref("media.ffmpeg.vaapi.enabled", true);     // E-VIDEO: test VAAPI on HD 615
// user_pref("gfx.webrender.all", true);              // E-WR: test WebRender vs basic compositor
// user_pref("layers.acceleration.force-enabled", true); // E-GPU: only if WebRender problematic
// user_pref("media.hardware-video-decoding.force-enabled", true); // E-VIDEO2
