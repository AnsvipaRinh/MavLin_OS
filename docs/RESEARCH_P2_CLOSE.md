# P2 research close — Automator/Shortcuts, Grapher, Migration Assistant, App Store, Software Update polish

> Phase 0.63 (2026-09-27, pre-hardware). Research-only per roadmap; no implementation.
> Each item: candidates evaluated → verdict → reason → next trigger.

## #42 Automator/Shortcuts

**Candidates evaluated:**
- Custom action runner over existing mv-* scripts + Thunar UCA actions — the project already has the building blocks (Thunar UCA, keyboard shortcut layer, mv-* scripts), but a workflow-chaining UI is a large new surface with no mature Linux backend to reuse.
- Document-disposition workflow (watch folder → transform → move) — feasible with inotify + shell, but overlaps with existing Thunar actions and adds a persistent watcher (power cost).
- Wrapper over existing Linux automation (systemd units, cron, incron) — thin wrapper, low Mavericks coherence, no UX gain.

**Verdict: DEFERRED (implement-later).**
**Reason:** No mature Linux backend for visual workflow automation; a Mavericks-like Automator UI would require a persistent GUI daemon or a large custom engine, violating power budget and reuse-first. The project's existing action layer (Thunar UCA + global shortcuts) already covers the practical automation needs.
**Next trigger:** If a lightweight "workflow runner" pattern emerges from user workflows (e.g., repeated multi-step file operations), or if a mature Linux workflow engine (e.g., Node-RED headless) becomes a feasible dependency.

## #43 Grapher

**Candidates evaluated:**
- matplotlib (Python) — mature, heavy dep tree (numpy, pillow, cycler, fontutils, kiwisolver, pyparsing); plotting a simple equation pulls ~100MB of deps and a Python runtime. Power/space cost unjustified for a P2 utility.
- labplot (KDE) — Qt/KDE deps, large, not Xfce-coherent.
- kalgebra (KDE) — same KDE dep issue; also a full CAS, overkill.
- gnuplot — lightweight, scriptable, but no Mavericks-like UI; would require custom GTK frontend + plotting backend integration.
- Custom lightweight plotter (GTK DrawingArea + equation parser) — feasible but duplicates gnuplot/matplotlib functionality; reuse-first says no.

**Verdict: DEFERRED (implement-later).**
**Reason:** All mature candidates have dep/power budgets incompatible with the fanless Core M target; a custom plotter violates reuse-first. Equation plotting is not part of the core Mavericks desktop experience.
**Next trigger:** If a lightweight plotting need emerges from another app (e.g., Activity Monitor energy graphs), or if a future matplotlib-lite (e.g., plotly-lite canvas) becomes feasible without heavy deps.

## #44 Migration Assistant

**Candidates evaluated:**
- Migration from old Mac (Time Machine backup, direct transfer) — no Linux backend reads Apple's Time Machine format natively (tmutil/HFS+ sparse bundles); would require HFS+ mount + custom parser.
- Migration from Windows PC — feasible (rsync/SMB) but out of scope for a Mac-targeted DE.
- Firstboot wizard (existing) — already covers initial setup; Migration Assistant's value is *cross-machine* transfer, not first-run setup.

**Verdict: EXCLUDED (confirmed — exclusion stands).**
**Reason:** No feasible Linux backend for Mac-to-Linux data migration; the project's firstboot + manual setup covers the practical need. Explicitly excluded per AGENTS.md §13.2.
**Next trigger:** Revisit only if a user migration path from macOS becomes a hard requirement (would need HFS+/APFS read support + Time Machine sparse-bundle parser — multi-week effort).

## #45 App Store

**Candidates evaluated:**
- pamac (GUI package manager) — exists, GTK3, but is a generic Linux package manager, not a store; wrapping it in Mavericks chrome adds no UX value.
- pacman + custom store frontend — thin wrapper over `pacman -Ss/-Si`; no Mavericks coherence benefit; App Store's value is curated discovery, which has no Linux equivalent.
- Flatpak/Flathub store — exists but is a different ecosystem (sandboxed apps), not a Mac App Store equivalent.

**Verdict: EXCLUDED (confirmed — exclusion stands).**
**Reason:** Already rejected in DECISIONS.md (Launchpad section): "no Linux equivalent; Mac App Store is proprietary." No Linux store backend with Mavericks-like UX exists; a pacman wrapper would be a renamed Linux tool, not a Mavericks integration (§9 fake-completion rule).
**Next trigger:** Revisit only if a curated app-discovery surface becomes a user requirement (would need a curated metadata backend + review system — out of scope).

## #46 Software Update polish

**Candidates evaluated:**
- `checkupdates` + `pacman -Syu` with Mavericks-like progress dialog — feasible: `checkupdates` is lightweight (libalpm), `pacman -Syu` is the native flow; a GTK progress dialog over `pacman -Syuu` with a Mavericks alert-style confirm is implementable in ~200 lines.
- `pamac checkupdate` — heavier dep, same flow.
- flatpak update integration — separate ecosystem, not system update.
- AUR update check — requires AUR RPC (curl + parse), feasible but adds a network poller.

**Verdict: DEFERRED (implement-later — lowest implementation cost of the five).**
**Reason:** The flow is simple and a Mavericks-like UI is feasible, but it is a thin wrapper over pacman with limited Mavericks coherence gain (the update *experience* is the same terminal-equivalent flow). Not needed for P0/P1 desktop coherence. The existing `mv-about` + `mv-control` surfaces already expose system state.
**Next trigger:** If a system-update notification is needed for the Notification Center (e.g., "Updates available" banner), or if the user requests a GUI update flow. Estimated effort: ~1 session (GTK progress dialog + pacman -Syuu wiring + test).

---

## Summary

| # | Item | Verdict | Next trigger |
|---|---|---|---|
| 42 | Automator/Shortcuts | DEFERRED (implement-later) | Lightweight workflow-runner pattern emerges |
| 43 | Grapher | DEFERRED (implement-later) | Lightweight plotting need from another app |
| 44 | Migration Assistant | EXCLUDED (confirmed) | User migration path from macOS becomes hard requirement |
| 45 | App Store | EXCLUDED (confirmed) | Curated app-discovery surface becomes user requirement |
| 46 | Software Update polish | DEFERRED (implement-later) | Update notification needed in Notification Center |

**Net result:** 2 exclusions confirmed, 3 deferrals with explicit next triggers. No new pre-hardware implementation items. P2 research track is closed.
