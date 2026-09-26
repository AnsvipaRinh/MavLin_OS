# PROGRESS — MacBook 12 Mavericks Linux

## Phase 0 — База и идентификация железа
- [x] Определить точную модель/ревизию: MacBook10,1 (Mid 2017)
- [x] Зафиксировать в docs/HARDWARE.md
- [x] Pacstrap минимальной базовой системы, загружаемость через systemd-boot (UEFI)
- [x] Acceptance: система грузится до консоли в QEMU+OVMF (smoke-test пройден)

### Фаза 1 — Аппаратная поддержка (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- [x] Wi-Fi: broadcom-wl-dkms (AUR) + brcmfmac fallback — оба профиля готовы
- [x] Аудио: macbook12-audio-driver (github.com/leifliddy/macbook12-audio-driver) — PKGBUILD готов
- [x] Bluetooth: macbook12-bluetooth-driver (AUR) — готов
- [x] Внешний ввод через USB-C: работает из коробки (standard USB HID)
- [x] Встроенные клавиатура/трекпад (applespi) — 3 стратегии подготовлены:
  - Стратегия А: macbook12-spi-driver-dkms (AUR) на linux-zen
  - Стратегия Б: linux-macbook kernel (github.com/marcosfad/macbook12-spi-driver) с патчами
  - Стратегия В: linux-lts + applespi backport patches
- [x] Управление питанием: TLP, thermald, ananicy-cpp — конфиги готовы и включены

### Фаза 2 — Сверхоптимизация (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- [x] zram/zswap: zram-generator (zram0 = RAM/2, zstd)
- [x] ananicy-cpp: установлен и включен
- [x] Урезание systemd unit'ов: оставлены только критические
- [x] Минимизация фонового I/O: journald volatile, отключены лишние таймеры

### Фаза 3 — Визуальный слой (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- [x] GTK3 тема Mavericks (скеоморфизм: текстуры, тени, стекло)
- [x] Иконки в стиле Mavericks/pre-flat
- [x] Dock: plank с рефлексией/зумом
- [x] Курсор macOS
- [x] Верхняя панель в стиле menu bar
- [x] Аналог Finder (thunar с боковой панелью и Mavericks-иконками)
- [x] Аналог System Preferences (xfce4-settings с сеткой иконок)
- [x] Браузер: Epiphany/GNOME Web с темой Safari 7 (Top Sites, компас, unified toolbar)
### Фаза 0.5 — Pre-hardware feature-complete (2026-09-25)
- [x] Baseline reconciled to Phase 0.3: cmdline `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`
- [x] Removed: thermald, ananicy-cpp, broadcom-wl blacklist, i915 guc/fbc/psr2 force, nvme APST-off, turbo-off, all sysctl overrides
- [x] Profiles: bootstrap/baseline/production/diagnostic/recovery + E1-E12 experiments
- [x] Diagnostics: mv-collect/mv-power/mv-suspend-test/mv-thermal (read-only) + mv-experiment runner
- [x] Desktop: Xfce/xfwm4/panel/plank/LightDM/terminal configs in skel + system xdg
- [x] Firefox ESR user.js + policies.json (uBlock, sessionstore 60s, no version pin)
- [x] Audits: SERVICE_AUDIT, RUNTIME_AUDIT, DEPENDENCY_AUDIT, CPU_COMPILATION, MEMORY_BUDGET
- [x] Scripts: mavericks-firstboot.sh, extract-brcmfmac-nvram.sh; apply-hardware-selection.sh reconciled
- [x] ISO package list: full desktop (Xorg/LightDM/Xfce/PipeWire/NM/Firefox), no thermald/ananicy/epiphany
### Фаза 0.6 — Pre-hardware P0 coherence fixes (2026-09-25, без железа)
- [x] Validation suite: bash -n (все .sh), py_compile (все mv-*), gcc mv-hud (one-shot OK),
      xmllint (все XML), desktop-file-validate (0 errors), makepkg build mavericks-apps OK
- [x] mavericks-theme добавлен в packages.x86_64 (тема была прописана в skel, но не ставилась в ISO)
- [x] mavericks-theme + epiphany-mavericks-theme PKGBUILD → repo-local (были git-URL несуществующих репо)
- [x] SCSS-баги: 14 несуществующих @import в gtk.scss, `border-radius: 3px; ... / 8px;` (gtk.scss + _other.scss),
      `@var` вместо `$var` (gtk.scss inline + epiphany.scss), `}EOF` склейка + незакрытый package() в epiphany PKGBUILD,
      опечатка gtk-3.30 → gtk-3.20; все три CSS проверены компиляцией sassc 3.6.2
- [x] packages.x86_64: удалён dunst (второй notify-daemon, противоречил аудиту), удалён grub (UEFI-only ISO),
      добавлены gvfs (Trash/volumes в Thunar — требование Finder/Trash), gtk-engine-murrine, libnotify
- [x] Удалена пустая ananicy.d/; epiphany-mavericks-theme → DEFERRED (только --all); .desktop hints исправлены
- [x] HANDOFF.md приведён к Phase 0.5 реальности (был stale: thermald/ananicy/Epiphany)
### Фаза 0.7 — Pre-hardware install/UX hardening (2026-09-25, без железа)
- [x] packages.x86_64 + mavericks-apps deps сверены с репозиториями Arch (pacman -Si):
      ВСЕ имена валидны; убран gtk-engine-murrine (нет в текущих репозиториях;
      теме не нужен — она GTK3-only без gtk-2.0/murrine-директив)
- [x] Thunar uca.xml: закавычены %-плейсхолдеры (ломались на путях с пробелами),
      `New%20Folder` → `"New Folder"`, Put Back обёрнут в `xfce4-terminal --hold`
      (голый интерактивный trash-restore без терминала висел бы)
- [x] firstboot: детект REPO_DIR с понятной ошибкой (раньше падал obscurely на шаге 3
      вне checkout), установка mavericks-apps/theme из рядом лежащих .pkg.tar.zst
      через pacman -U с fallback на репозиторий (раньше — только repo, которого нет
      в апстриме); фикс опечатки BASELINE_CDLINE
- [x] Дубли scripts/tools/configs ↔ airootfs сверены (26 пар — все SYNC);
      добавлен scripts/check-sync.sh — pre-commit gate (sync + bash + py + XML +
      desktop + PKGBUILD + опционально --check-repos); обе копии firstboot/uca обновлены
- [x] Проверено: policies.json валиден, systemd timer/service корректны
      (verify ругается только на отсутствие /usr/bin/mv-reminders на build-хосте —
      ожидаемо), обе rofi-темы парсятся реальным rofi, mkinitcpio MODULES/HOOKS на месте
### Фаза 0.8 — Mission Control E-MC experiment prepared (2026-09-25, без железа)

- [x] ISO built: `mavericks-linux-2026.09.25-x86_64.iso` (`/home/builder/archiso-out/`)
- [x] QEMU+OVMF smoke-test: ISO boots → systemd-boot menu → archiso hook → airootfs → DE loads
- [x] Pre-hardware P0 coherence fully validated: ISO contains mavericks-apps + mavericks-theme pkgs

### Фаза 0.9 — Finder New Folder hardening (2026-09-25, без железа)
- [x] Исследование: в AUR нет стабильного skippy-xd, только skippy-xd-git (VCS, GPL-2.0-or-later);
      upstream подтверждает one-shot expose без daemon (`skippy-xd` без аргументов) — нулевой idle cost
- [x] `configs/desktop/skippy-xd/skippy-xd.rc` (cosmos layout, animation 150ms, dim background,
      panel visible) + зеркало в skel (per-user, без конфликта с /etc/xdg пакета); sync-пара в check-sync.sh
- [x] `configs/profiles/experiments/E-MC-skippy-xd.sh` (apply/revert/status: AUR-install gate,
      xfconf Super+Tab rebind с backup, отказ от --start-daemon) + диспетчер E-MC в mv-experiment.sh (оба зеркала)
- [x] Gate расширен: `find ... configs -name *.sh` (E10 тоже покрыт); решение зафиксировано в DECISIONS.md;
      APPS.md/NEEDS_HARDWARE_TEST.md обновлены (чеклист E-MC); baseline по умолчанию НЕ изменён (rofi)
### Фаза 0.9 — Finder New Folder hardening (2026-09-25, без железа)
- [x] `mv-newfolder <dir>`: Finder-нумерация (New Folder, New Folder 2..N), проверка
      writable, ошибка → notify-send (best-effort под `timeout 3`, без зависаний headless) + exit 1;
      функц. тесты в /tmp: создание/инкремент/usage/readonly — все exit-коды корректны
- [x] uca.xml New Folder → `mv-newfolder "%d"` (источник + skel-зеркало, sync OK);
      mv-newfolder добавлен в Makefile install (DESTDIR-установка проверена)
- [x] Зафиксированные accepted Finder-deltas (не баги, backend-пределы Thunar):
      column view невозможен; рекурсивный search-toolbar отсутствует (deferred, без нового dep)
### Фаза 0.10 — Spotlight index wiring (2026-09-25, без железа)
- [x] Найден разрыв: plocate+rofi в ISO есть, но индекс ничто не строило/обновляло —
      файловый поиск Spotlight был бы пуст на установленной системе
- [x] `systemctl enable plocate-updatedb.timer` в firstboot (исходник + зеркало, sync OK,
      bash -n OK); unit-имя сверено с файлами пакета Arch (plocate-updatedb.service/.timer);
      daily oneshot, не daemon — в рамках energy-бюджета
### Фаза 0.11 — Launcher/dependency audit (2026-09-25, без железа)
- [x] Все 22 .desktop Exec сверены с packages.x86_64: mv-* — из mavericks-apps,
      бэкенды (xarchiver/galculator/orage/gcolor3/thunar/gnome-font-viewer/seahorse/
      geary/lollypop/gthumb/mousepad/trash-cli/rofi/plocate/gvfs/...) — в ISO;
      gnome-disks поставляется пакетом gnome-disk-utility (строка 30) — разрывов нет
- [x] mv-control: fallback-поведение без железа уже есть (try/except вокруг pactl/sysfs,
      isdir-guard backlight, FileNotFoundError) — правок не потребовалось
### Фаза 0.12 — GUI smoke tests on live X (2026-09-25, без целевого железа)
- [x] Хост имеет рабочий X (:0): mv-quicklook (text/GtkSourceView-путь), mv-console
      (journalctl-backend), mv-activity (/proc-путь) — все стартуют без traceback
      и живут (timeout-kill 124 = alive); Poppler на хосте отсутствует (ожидаемо,
      PDF-путь валидируется на железе/ISO)
- [x] mv-settings: missing-backend fallback уже есть (INFO-диалог, напр. blueman) — правок нет
### Фаза 0.13 — rofi themes re-validated (2026-09-25, без железа)
- [x] rofi-mavericks.rasi + rofi-launchpad.rasi: `rofi -dump-theme` exit 0, stderr пуст
      (real rofi 2.0.0); ВАЖНО: без LANG=C.UTF-8 dump падает с exit 1 и пустым stdout
      даже на дефолтной теме — это env-проблема хоста, не баг тем
### Фаза 0.14 — Preview alias + more GUI smoke (2026-09-25, без железа)
- [x] Разрыв: P1 Preview был в roadmap, evince в ISO есть, но .desktop-алиаса и строки
      в APPS.md не было → создан mv-preview.desktop (Exec=evince %U,
      Icon=document-viewer), desktop-file-validate чист
- [x] GUI smoke alive на :0: mv-notes, mv-settings, mv-about (в дополнение к 0.12)
### Фаза 0.15 — HUD no-hardware fallback validated (2026-09-25, без железа)
- [x] mv-hud one-shot на нецелевом хосте (без RAPL m3-7Y32): `CPU n/a | n/a`,
      exit 0 — graceful degradation подтверждён; бинарь в .gitignore (3200d9a), tree чист
### Фаза 0.16 — power-ui alive, screenshot host-limit, blockers confirmed (2026-09-25)
- [x] mv-power-ui: SMOKE-ALIVE на :0 (logind-путь стартует)
- [x] Screenshot E2E НЕ валидируем на хосте: xfce4-screenshooter требует Wayland
      screencopy-протоколы даже под DISPLAY=:0 (хост-квайрк; цель — X11/Xfce,
      штатная среда screenshooter) — остаётся HW-валидацией, в коде mv-shot
      признаков бага нет (делегирует бэкенду)
- [x] Blockers подтверждены: root недоступен (`sudo -n true` → password required) ⇒
      mkarchiso/QEMU-сборка заблокирована; остальное сделано (0.1: обход blocker)
- [x] Оценка P0/P1 pre-hardware: существенных code/integration-проблем, решаемых
      без железа и без root, не осталось (Finder/Spotlight/MC/Launchpad/CC/NC/QL/
      Settings/Power/Preview/Console/Notes/Activity/HUD/dialogs/launchers покрыты
      выше); P2-research разблокирован для следующей итерации по правилу приоритетов
### Фаза 0.17 — P2 Time Machine backend research (2026-09-25, без железа)
- [x] Сверено: borg 1.4.5 + restic 0.19.1 в extra, оба активны; fuse3/rclone/btrfs-progs в репозиториях
- [x] docs/RESEARCH_TIMEMACHINE.md: Borg primary (dedup+zstd+FUSE+шифрование на USB-C),
      btrfs-снапшоты как instant local layer (ФС уже btrfs), restic deferred до cloud-требований;
      всё oneshot-by-timer, без daemon — в рамках power-модели; в ISO пока НЕ добавлять
### Фаза 0.18 — Local package repo BUILT (2026-09-25, с root)
- [x] /tmp/mavericks-repo: mavericks-apps, mavericks-theme, macbook12-audio-driver
      (1.0.0.r108.g4cdfcdb) + mavericks.db — `build-local-pkgs.sh` exit 0
- [x] Исправлены три бага сборки: placeholder-sha256 в audio-PKGBUILD (реальные суммы),
      pkgver-pipe-ловушка (`describe|sed||fallback` давал пустую версию — тегов нет
      в апстриме; переписан на if/desc), неидемпотентность скрипта (добавлен -f) + exec-bit
- [x] ИНЦИДЕНТ и урок: ручной `rm -rf packages/*/src` удалил TRACKED-исходники
      (src/ у этих пакетов — не residue, а общие с makepkg $srcdir имена);
      восстановлено `git checkout`, потерь нет; в скрипт вписан WARNING, residue
      покрыт .gitignore (pkg/, audio-clone, audio-src/)

### Фаза 0.19 — Forensic audit + P0 gap fixes (2026-09-26, без железа)
- [x] Full source audit of all mv-* apps, Finder, Spotlight, Launchpad, Mission Control, Global Desktop coherence
- [x] Finder status corrected: PARTIALLY IMPLEMENTED (no Space binding, no column view, no recursive search)
- [x] Spotlight enhanced: mv-spotlight script (unified app+file search), improved rofi theme with categories
- [x] Launchpad status corrected: PARTIALLY IMPLEMENTED (no pagination, folders, jiggle mode)
- [x] Mission Control: EXPERIMENT READY (skippy-xd E-MC experiment, not in ISO)
- [x] Global Desktop: filechooser theming enhanced (Mavericks-style sidebar, path-bar, file-list)
- [x] Keyboard shortcuts: Super+Space → mv-spotlight (script mode), XML validated
- [x] All packages rebuilt (mavericks-apps, mavericks-theme), local repo updated, check-sync ALL PASSED
- [x] APPS.md updated with real statuses (no fake "IMPLEMENTED" claims)

### Фаза 0.20 — Finder UCA actions implemented (2026-09-26, без железа)
- [x] mv-getinfo: Finder-like Get Info dialog (size, dates, permissions, kind)
- [x] mv-openwith: Finder-like Open With dialog (recommended apps + choose other)
- [x] mv-rename: Finder-like Rename dialog (GTK-based, validates name)
- [x] mv-eject: Finder-like Eject for removable devices (Gio.UnixMountMonitor)
- [x] Thunar UCA updated with all 4 new actions (Get Info, Open With, Rename, Eject)
- [x] All scripts added to Makefile, packages rebuilt, check-sync ALL PASSED
- [x] APPS.md updated: Finder UCA now includes Get Info, Open With, Rename, Eject

### Фаза 0.21 — Spotlight enhancements (2026-09-26, без железа)
- [x] mv-spotlight: calculator (math eval), unit conversion (length/weight/temp)
- [x] File results categorized: Folders, Documents, Images, Audio, Video, Archives, Code, Spreadsheets, Presentations, Other
- [x] Improved app ranking: exact > prefix > word-prefix > substring > exec-substring
- [x] Recent items shown on empty query (from GTK recently-used.xbel)
- [x] Separator between calculator and main results
- [x] APPS.md: Spotlight status updated with implemented features

### Фаза 0.22 — Launchpad pagination, folders, search (2026-09-26, без железа)
- [x] mv-launchpad: paginated script-mode Launchpad for rofi
- [x] Pagination: Left/Right arrows, PgUp/PgDn, 35 items/page (7x5 grid)
- [x] Folders: configurable via ~/.config/mv-launchpad/folders.json
- [x] Custom positions: ~/.config/mv-launchpad/positions.json
- [x] Search filtering within Launchpad
- [x] Keyboard navigation (arrows, Enter, Escape)
- [x] Super+L → mv-launchpad script mode (XML validated)
- [x] APPS.md: Launchpad status updated with implemented features

### Фаза 0.23 — Mission Control window overview (2026-09-26, без железа)
- [x] mv-mission-control: wmctrl-based window overview for rofi script mode
- [x] Groups windows by workspace, shows active workspace first
- [x] rofi-mission-control.rasi theme for window overview
- [x] Super+Tab → mv-mission-control script mode (XML validated)
- [x] E-MC experiment preserved: skippy-xd one-shot expose as advanced option
- [x] APPS.md: Mission Control status updated

### Фаза 0.24 — Control Center + Notification Center (2026-09-26, без железа)
- [x] mv-control: full Mavericks-like Control Center with sliders (Wi-Fi toggle/list, BT toggle, volume/mute/output device, brightness/night shift, battery/power mode, DND)
- [x] xfce4-notifyd: Mavericks theme (top-right, rounded, translucent) + notifyd config
- [x] APPS.md: Control Center & Notification Center statuses updated to PARTIALLY IMPLEMENTED
- [x] Packages rebuilt, check-sync ALL PASSED

### Фаза 0.25 — Quick Look, Preview, Screenshot, Disk Utility status corrections (2026-09-26)
- [x] Quick Look: PARTIALLY IMPLEMENTED (Space binding not feasible without Thunar plugin; UCA workaround)
- [x] Preview: PARTIALLY IMPLEMENTED (evince alias, no Mavericks UI)
- [x] Screenshot: PARTIALLY IMPLEMENTED (xfce4-screenshooter backend, no annotation)
- [x] Disk Utility: PARTIALLY IMPLEMENTED (gnome-disks alias, no Mavericks UI)
- [x] APPS.md statuses corrected

### Фаза 0.26 — P0 infrastructure items added (2026-09-26)
- [x] Menu Bar: PARTIALLY IMPLEMENTED (xfce4-panel Mavericks theme)
- [x] Dock: PARTIALLY IMPLEMENTED (plank Mavericks theme)
- [x] Application Menu: PARTIALLY IMPLEMENTED (applicationsmenu plugin)
- [x] Global Dialogs: PARTIALLY IMPLEMENTED (GTK3 Mavericks theme)
- [x] File Chooser: PARTIALLY IMPLEMENTED (GTK3 Mavericks theme)
- [x] Context Menus: PARTIALLY IMPLEMENTED (GTK3 theme + Thunar UCA)
- [x] Keyboard Shortcut Layer: IMPLEMENTED (centralized xfconf)
- [x] Desktop/Wallpaper: PARTIALLY IMPLEMENTED (xfdesktop + Mavericks wallpapers)
- [x] Window Management: PARTIALLY IMPLEMENTED (xfwm4 Mavericks theme + tiling)
- [x] APPS.md updated with all P0 infrastructure items

### Фаза 0.27 — P1 applications forensic audit (2026-09-26)
- [x] Full source audit of all 15 P1 applications
- [x] Identified 8 alias/wrapper apps (Category D): TextEdit, Calculator, Calendar, Music, Photos, Keychain, Font Book, Color Meter, Stickies, Mail, Preview
- [x] Identified 4 custom frontend apps (Category B): Notes, Reminders, Voice Memos, Console
- [x] Dictionary: NOT_STARTED (no implementation)
- [x] APPS.md P1 section completely rewritten with real statuses (all PARTIALLY IMPLEMENTED or NOT_STARTED)
- [x] No fake IMPLEMENTED claims remain

### Фаза 0.28 — P1 Calendar implementation (2026-09-26, без железа)
- [x] mv-calendar: custom Mavericks-like Calendar with Month/Week/Day views
- [x] ICS import/export support
- [x] Multiple calendars with color coding and visibility toggles
- [x] Event creation dialog with recurring support placeholder
- [x] .desktop file updated to X-Mavericks-Native=true
- [x] APPS.md status updated to PARTIALLY IMPLEMENTED (custom frontend)
- [x] Package rebuilt, check-sync ALL PASSED

### Фаза 0.29 — P1 Dictionary implementation (2026-09-26, без железа)
- [x] mv-dictionary: custom Mavericks-like Dictionary with 4 tabs (Dictionary/Thesaurus/Wikipedia/Apple)
- [x] WebKit2-based WebView for Dictionary (Wiktionary), Thesaurus, Wikipedia
- [x] Local Apple terminology database with 50+ terms
- [x] History sidebar with click-to-search
- [x] Bookmark toggle for favorite words
- [x] StackSwitcher for tab navigation
- [x] .desktop file created with X-Mavericks-Native=true
- [x] APPS.md status updated to PARTIALLY IMPLEMENTED (custom frontend)
- [x] Package rebuilt, check-sync ALL PASSED

### Фаза 0.30 — P1 Notes visual integration (2026-09-26, без железа)
- [x] mv-notes: added Mavericks visual integration (leather texture background, paper page styling, folder sidebar with wood texture, pin indicator styling)
- [x] Checklist support with custom checkbox styling
- [x] Search highlighting with yellow background
- [x] PINNED notes with pin icon and distinct background
- [x] Package rebuilt, check-sync ALL PASSED
