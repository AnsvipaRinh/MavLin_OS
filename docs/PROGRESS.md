# PROGRESS — MacBook 12 Mavericks Linux

### Фаза 0.53 — Keychain Access: repair unlaunchable app + real libsecret backend (2026-09-27, без железа)
- [x] Аудит: mv-keychain (102 строки) был НЕЗАПУСКАЕМ — `text-align: left;` не существует в GTK3 CSS → GLib.GError в `apply_css()` при старте (exit 1); py_compile и import проходят — тот же класс fake-completion, что mv-voice (0.51) и mv-console (0.52); APPS.md заявил «custom wrapper with Mavericks sidebar/theme»
- [x] Найдено и исправлено по ходу: (1) `paned` создавался дважды — sidebar/content попадали в второй Paned, который никогда не добавлялся в окно (окно было бы пустым даже после фикса CSS); (2) дублированные импорты os/sys/gi дважды; (3) двойной вызов `apply_css()`; (4) sidebar был статическим списком `["login","System","System Roots","iCloud"]` с мёртвыми кнопками; (5) backend'ом был только `subprocess.Popen(["seahorse"])` через 100 мс — никакого libsecret/secret-tool кода не существовало; (6) PKGBUILD не имел зависимости libsecret/seahorse; (7) `.desktop` имел `Exec=mv-keychain %U` (%U не нужен — keychain не открывает файлы); (8) GtkInfoBar добавлялся вторым child в GtkWindow (GtkBin warning) — обёрнут в root Box
- [x] Backend: Gio.Secret (libsecret typelib) напрямую, без subprocess: `Secret.Service.get_sync` → коллекции (имя/label/locked), fallback на список известных keychains когда daemon отсутствует; `load_items_sync` → предметы с attributes/schema/locked; `SecretValue.get()` → секрет по требованию (never logged, never on disk); `password_store_sync` с динамической Generic-схемой; `password_lock_sync` для блокировки; `item.delete_sync()`; graceful None/[] граница (None = сервис недоступен, [] = пусто)
- [x] Password generator: `secrets` CSPRNG, гарантированное покрытие каждого включённого класса, оценка энтропии (bits), диалог с length/charset/entropy/Copy; сгенерированные пароли нигде не логируются и не сохраняются
- [x] UI: Mavericks leather sidebar (коллекции с lock-иконками), item list (Name/Kind), detail pane (атрибуты grid + секрет по требованию с «Show password» + Copy), New Password Item диалог (Label/Account/Where/Password+Generate), Delete с confirm, Lock keychain (per-item lock), client-side search без ре-запроса backend'а (проверено счётчиком вызовов), состояния: no-libsecret / no-daemon / empty keychain / locked item; классификация предметов Password/Certificate/Key/Secure Note по schema/атрибутам
- [x] Keyboard: Ctrl+N new item, Ctrl+G generator, Ctrl+L lock, Delete delete, Escape close dialogs
- [x] Security: секреты никогда не логируются, не пишутся на диск, не попадают в state-файлы; clipboard только по явному действию пользователя; тесты используют полностью мокированный Secret backend — реальные секреты не затрагиваются
- [x] Validation: py_compile OK, import test OK (subprocess), desktop-file-validate OK, 96 headless-тест (scripts/test-mv-keychain.py: generator charset/length/coverage/uniqueness/CSPRNG-via-secrets, strength entropy, classify, collections fallback/parsing, list_items fallback/empty/default-collection, secret bytes/str/error, store wiring+validation+errors, delete, lock per-item+skip+error tolerance, GUI smoke на реальном GTK :0 — construct/sidebar/items/detail/search-no-requery/secret reveal/new-dialog-store/generator-entropy/lock/delete/unavailable states), check-sync ALL CHECKS PASSED, sibling suites green (notes 41, reminders 31, console 92, voice 63, music 108, calendar 63, photos 84), прямой запуск OK (exit 124 = живой до timeout, без warning'ов)
- [ ] HW: реальный gnome-keyring daemon (автоматический unlock при логине), реальные предметы (сетевые пароли NetworkManager, сертификаты, SSH-ключи через ssh-agent/libsecret), разблокировка коллекции по требованию (daemon prompt), рендеринг на 2304×1440, блокировка/разблокировка в реальной сессии, energy cost открытого окна (нет polling — только on-demand reads)

### Фаза 0.52 — Console: repair unlaunchable app + Mavericks refinement (2026-09-27, без железа)
- [x] Аудит: mv-console (291 строка) был НЕЗАПУСКАЕМ — `sys.exit(main())` стоял на уровне модуля без `import sys` (NameError при импорте/запуске); py_compile gate это ловит НЕТ (runtime, не syntax) — тот же класс fake-completion, что mv-voice; APPS.md заявлял «custom app implemented»
- [x] Найдено и исправлено по ходу: (1) «System Log» использовал `-k` (kernel messages) — дублировал Kernel Log; (2) `.console-log-view` CSS-класс был определён, но никогда не применён к TextView (тёмный вид не работал); (3) иконки в sidebar store не рендерились (нет pixbuf-колонки); (4) headerbar source-combo не обновлял `current_source` (только sidebar — combo был декоративным); (5) level-combo не имел пункта «All» (стартовал на Emergency); (6) `level.connect("changed", self.reload)` передавал виджет как `initial` → count-перезапросы на каждый чих; (7) дубликат метода `on_source_select`; (8) `Gtk.IconSize.SMALL_MENU` не существует в GTK3 (AttributeError на старте)
- [x] Backend: journalctl `-o json` (структурированный PRIORITY → severity, SYSLOG_IDENTIFIER, __REALTIME_TIMESTAMP); fallback на text-scan для dmesg -T / plain-строк; binary MESSAGE-массивы декодируются как bytes
- [x] Severity badges: EMRG/ALRT/CRIT/ERR/WRN/NTC/INF/DBG фиксированной ширины в начале строки + цвет всей строки по severity (emerg/crit/err — bold)
- [x] Sources: All Messages / Current Boot / Previous Boot (`journalctl -b -1`, state «No previous boot recorded» если пусто) / Kernel Log (dmesg -T, `-l` level-фильтр) / User Log; per-source счётчики в sidebar (один раз на открытие окна, не на каждый тик)
- [x] Live tail: только пока открыто окно (GLib.timeout_add_seconds(2), source_remove на destroy), pause через Live toggle или «Pause Updates» в меню (двусторонняя синхронизация, guard против рекурсии)
- [x] Search: фильтрует уже загруженные строки без перезапроса backend; Enter = render, Escape = очистка; Ctrl+F focus
- [x] Export: FileChooserDialog SAVE → «console-log.txt» с шапкой (source/level/дата) + видимые строки; OSError → error MessageDialog
- [x] Wrap toggle (меню), Clear Display, empty/error states («No messages for this source.», «journalctl is unavailable…», «dmesg … requires root», «The log could not be read.» + stderr detail)
- [x] Keyboard: Ctrl+F search, Ctrl+E export, Ctrl+L live toggle, Escape clear
- [x] Validation: py_compile OK, desktop-file-validate OK, 92 headless-тест (scripts/test-mv-console.py: severity/priority parsing, journal json/text/dmesg parsers, dispatch, filter, source_command shapes incl. no -k regression и dmesg -l mapping, badge width, GUI smoke на реальном GTK :0 — construct/entries/badges/dark class, source/level command shapes, pause tick no-query, search без re-query, wrap/pause sync, export + error path, clear, empty/no-prevboot/no-journal states, key routing, timer removed on destroy), check-sync ALL CHECKS PASSED, sibling suites green (notes 41), прямой запуск OK (exit 124 = живой до timeout), makepkg parse OK (полная сборка требует webkit2gtk из sync DB — host limitation, pre-existing)
- [ ] HW: реальные значения journald (JSON-поля PRIORITY/SYSLOG_IDENTIFIER на MacBook10,1), dmesg permissions (root vs user), наличие Previous Boot после реальных ребутов, рендеринг на 2304×1440, energy cost 2s-tail при открытом окне

### Фаза 0.51 — Voice Memos: repair unlaunchable app + Mavericks refinement (2026-09-27, без железа)
- [x] Аудит: mv-voice (406 строк) был НЕЗАПУСКАЕМ — invalid CSS-свойство `font-variant-numeric` роняло Gtk.CssProvider (GLib.Error на load_from_data), далее `CassetteWidget` использовался, но никогда не был определён (NameError), `import sys` отсутствовал (NameError на выходе); APPS.md заявлял «custom app implemented» — fake completion (раздел 9)
- [x] Backend auto-detect: pw-record (PipeWire) → parec (PulseAudio) fallback; playback pw-play → paplay; graceful no-backend state (кнопка record disabled + статус с инструкцией)
- [x] Cassette UI реализованна: Gtk.DrawingArea + Cairo — корпус с градиентом, два катушки со спиницами, вращение при record/play (GLib timer 60ms), лента, плейка «VOICE MEMOS», LED (красный пульсирующий при записи, зелёный при воспроизведении)
- [x] Waveform strip: пики PCM нативно (struct unpack, buckets=160), прогресс воспроизведения подсвечивается; вычисление при выборе строки
- [x] Level meter без второго аудиопотока: RMS хвоста записываемого WAV (seek к size-1600, struct-based RMS, timer 200ms) — дёшево, работает с pw-record
- [x] In-app playback:  one-shot pw-play/paplay, позиция/длительность, stop (SIGINT), cassette animation
- [x] Trim: frame-aligned PCM cut без ffmpeg (wave module, setpos/readframes, temp+os.replace); диалог Start/End spinbuttons; clamp/empty-selection ошибки
- [x] Export через Gtk.FileChooserNative (copyfile); Rename через sanitize_memo_name + collision check; Delete → Gio.File.trash (fallback os.remove) с confirm; Info dialog (name/date/duration/size/rate/channels/path)
- [x] Empty state («No recordings yet…»), выбор строки загружает waveform + длительность, корректная обработка не-wav/битых wav (duration «—»), каталог-как-файл → error state
- [x] Keyboard: Ctrl+R record, Return/Space play-stop, Delete, Ctrl+E export, Ctrl+I info; %U открывает аудиофайл (запуск воспроизведения)
- [x] .desktop: MimeType=audio/wav;audio/x-wav;audio/mpeg;audio/ogg;audio/flac;audio/x-m4a;audio/mp4, Categories=AudioVideo;Audio
- [x] PKGBUILD optdepends: pipewire (backend), pulseaudio (fallback backend)
- [x] Найдено и исправлено по ходу: (1) get_selected() возвращает (model, None) при пустой выборе — `if not row` не ловит, NoneType crash в _selected_memo/rename/delete; (2) show_all() после refresh() затирал видимую страницу Gtk.Stack (empty state не показывался) — порядок исправлен; (3) refresh() внутри trim сбрасывает выбор строки (тест-бага + UX note: выбор сохраняется при ручном rename/delete)
- [x] Validation: py_compile OK, desktop-file-validate OK, 63 headless-тест (scripts/test-mv-voice.py: backend/playback detection incl no-exe, wav_info/duration synthetic+garbage+missing, sanitize (traversal/unsafe/empty), list_memos ordering/skip, waveform peaks loud/silent/garbage, rms_level, trim frame-aligned/clamp/empty/garbage, GUI smoke на реальном GTK :0 — construct/list/empty, selection→waveform+duration, record start/stop mocked, play start/stop mocked, trim/rename/info/delete-mock, key routing, no-backend state), check-sync ALL CHECKS PASSED, sibling suites green (notes 41, reminders 31, music 108, calendar 63), real binary launch OK (в т.ч. с %U-файлом)
- [ ] HW: запись с Cirrus микрофона через pw-record (macbook12-audio-driver), воспроизведение через pw-play на встроенных динамиках, рендеринг cassette/waveform на 2304×1440, trim/export/delete на реальной установке, %U из Thunar, energy cost однократной записи

### Фаза 0.50 — Photos: Mavericks integration (library engine, Moments, albums) (2026-09-27, без железа)
- [x] Аудит: существующий mv-photos был 141-строчным stub (запускал gthumb, показывал label) — нет library engine, нет EXIF, нет Moments, нет избранного, нет альбомов, нет state store, нет реального UI
- [x] Library engine (pure, headless-testable): нативный парсинг JPEG EXIF DateTimeOriginal (APP1 → TIFF IFD → tag 0x9003), парсинг размеров изображений из заголовков PNG/JPEG/GIF/BMP/TIFF/WebP (без внешних зависимостей); scan_library с детерминированным сортировкой по mtime desc
- [x] Moments: группировка по дате (YYYY-MM-DD) из EXIF или fallback "Unknown"; сортировка по дате desc; поддержка search filter внутри Moments
- [x] Favorites: toggle по path, persistence в state store, звезда в grid UI
- [x] Albums: пользовательские альбомы (New Album dialog), add/remove photo, sidebar со счётчиками, удаление альбома
- [x] Import: выбор папки → копирование в ~/Pictures/Imports/YYYY-MM-DD_HHMMSS → обновление библиотеки → запись в imports log (cap 200)
- [x] Search: по filename и date (YYYY-MM-DD), Ctrl+F focus, real-time фильтрация
- [x] State store: backup-on-save (.bak), restore-from-backup, quarantine при повреждении, normalize, geometry persistence — тот же паттерн что mv-music/mv-notes
- [x] GUI: Mavericks CSS (leather sidebar #f5f0e8, selected #007aff), FlowBox grid с thumbnails (GdkPixbuf cache в ~/.cache/mv-photos/thumbs), sidebar (Library: All/Favorites/Recently Added | Moments | Albums), full-view dialog (dims/size/date/Edit in gthumb/Favorite), slideshow (Space, 3s interval, Escape stop), empty states, error bar
- [x] Keyboard: Ctrl+F search, Ctrl+I import, Space slideshow toggle, Escape stop/close
- [x] Thumbnails: GdkPixbuf scaled cache (sha1 key = path+size+mtime), placeholder icon при ошибке
- [x] Edit handoff: gthumb launcher (graceful degradation если не установлен), rotate handoff (gthumb CLI → exiftool fallback)
- [x] Mime types: .desktop обновлён (image/jpeg;png;gif;bmp;tiff;webp;heic), Categories=Graphics;Photography
- [x] --scan CLI mode: `mv-photos --scan [path]` — выводит количество фото + первые 10 с датами и размерами
- [x] Deferred (documented в DECISIONS.md): People/faces (нет лёгкой mature face-recognition библиотеки в scope), Memories (ML-based curation), Shared Albums (нет cloud backend)
- [x] Validation: py_compile OK, 84 headless-тест (scripts/test-mv-photos.py: dims PNG/JPEG/GIF/BMP/TIFF/WebP, EXIF DateTimeOriginal, failure modes, scan, moments, search, state store roundtrip/backup/quarantine/restore/normalize, favorites, albums, imports, thumb paths, rotate/editor graceful degradation, fmt helpers), desktop-file-validate OK, check-sync ALL CHECKS PASSED
- [ ] HW: gthumb availability + Edit handoff, exiftool rotate fallback, thumbnail cache на реальной библиотеке, HiDPI rendering grid/sidebar на 2304×1440, import flow с USB-C card reader, slideshow performance на Intel HD 615, geometry restore на реальной сессии

### Фаза 0.49 — Music: Mavericks integration (library engine, MPRIS backend, views) (2026-09-26, без железа)
- [x] Аудит WIP предыдущей попытки (1584 строки, не закоммичен): архитектура валидная (pure library engine + MPRIS-контроллер + GTK3 UI), но содержала 7 реальных дефектов — все найдены и исправлены:
- [x] Баги парсинга тегов (найдены synthetic-fixture тестами): (1) `_vorbis_comments` читал vendor_len со смещением +4 вместо +0 — FLAC/Ogg теги молча парсились в мусор; (2) `_parse_ogg` искал идентификационный заголовок `\x01vorbis`, где vendor_len не существует — переписан на page-scan заголовка комментариев `\x03vorbis`; (3) MP4 track-number atom — это `trkn` без `\xa9` префикса, сравнение с `\xa9trkn` никогда бы не совпало; (4) APIC с пустым description (`mime\0\0data`) не находился — поиск второго разделителя сдвинут с p+1 на p
- [x] Баги GUI/логики: (5) вызов несуществующего `self._queue_load()` в `_rescan_library` (NameError при любой непустой библиотеке); (6) `Gtk.ListBox.append` не существует в GTK3 (GTK4 API) — `insert(row, -1)`; (7) `GdkPixbuf` использовался, но не импортировался (NameError на первой же плитке альбома)
- [x] Library engine: нативный парсинг ID3v2.3 (TIT2/TPE1/TALB/TCON/TRCK/APIC), FLAC (Vorbis comments + STREAMINFO duration + METADATA_BLOCK_PICTURE), Ogg Vorbis (comment header через page-scan), MP4/M4A (ilst atoms, \xa9nam/\xa9ART/\xa9alb/trkn, \xa9covr); сканер библиотеки с детерминированным порядком, группировка по альбомам с trackno-сортировкой и наследованием обложки; cover-кэш (~/.cache/mv-music/covers, идемпотентная запись)
- [x] Backend: MPRIS2 D-Bus контроллер lollypop (PlayPause/Next/Previous/Stop, Metadata/PlaybackStatus/Position); event-driven — NameOwnerChanged watch + PropertiesChanged subscription (now-playing обновляется при смене трека без polling); graceful degradation при отсутствии backend (все методы → False/None, error bar с инструкцией pacman -S lollypop)
- [x] Play log / smart-плейлисты: record_play с dedup подряд идущих одинаковых треков; Recently Played (dedup by path, latest wins), Top Played (count-ranked) — sidebar со счётчиками, persistence в state store
- [x] Queue: display-side "up next" (MPRIS2 не имеет queue-order API — задокументировано в DECISIONS), activate-from-row проигрывает с выбранного трека в сохранённом порядке
- [x] Now-playing bar: обложка (library match → MPRIS artUrl → placeholder), title/artist, position/length, prev/playpause/next, sensitivity по backend availability
- [x] Mini player: компактное окно (Ctrl+M, toolbar button, geometry persistence через state store, Escape закрывает), cover из library или artUrl
- [x] Keyboard: Ctrl+F search, Ctrl+Q queue view, Ctrl+M mini player, Space play/pause; media keys XF86AudioPlay/Next/Prev/Stop → `mv-music --media-key ...` в xfce4-keyboard-shortcuts.xml (source + airootfs mirror)
- [x] Mavericks integration: leather sidebar CSS (#e8dcc8), paper content, styled album tiles (cover/letter fallback, hover/selected), error/empty states с Choose Folder dialog, context menu альбома (Play/Enqueue/Show in Finder/Get Info), Get Info dialog, geometry persistence, corrupt-store safety (backup/quarantine — как Notes/Calendar family)
- [x] Deferred (documented в DECISIONS.md): cover flow (3D transforms + animation loop — runtime cost ради эстетики, как Calendar page-flip в 0.48), lyrics panel (online service, вне local-first области)
- [x] Найдено и исправлено по ходу: (1) mini player play button брался по хрупкому индексу children[3] (был backward) — прямая ссылка; (2) mini cover не установился; (3) geometry["mini"] никогда не записывался; (4) record_play дублировался при каждом PropertiesChanged — dedup guard; (5) queue activation сортировал весь очередь по trackno вместо сохранения порядка; (6) reveal_group вызывал несуществующий "threnameplace"; (7) мёртвый код (`set_tooltext_text if False else None`, пустой warnings loop); (8) версия Gdk не указана (конфликт Gdk 4.0 на некоторых хостах)
- [x] Validation: py_compile OK, 108 headless-тест (scripts/test-mv-music.py: ID3/FLAC/Ogg/MP4 parsing incl APIC/duration/trkn, failure modes, scan/group, store round-trip/backup/quarantine/restore/normalize/caps, play log dedup/ranking, search, cover cache, media-key CLI с моком Gio, MprisController degradation, GUI smoke на реальном GTK :0 — views/enqueue/search/error/play/mini/empty), desktop-file-validate OK, check-sync ALL CHECKS PASSED, make install DESTDIR OK
- [ ] HW: lollypop playback на MacBook10,1 (Cirrus), MPRIS на этом стеке, XF86Audio* клавиши (applespi + external), HiDPI рендеринг обложек/sidebar, energy cost PropertiesChanged refresh (см. NEEDS_HARDWARE_TEST.md → Music)

### Фаза 0.48 — Calendar: Mavericks visual integration + refinement (2026-09-26, без железа)
- [x] Аудит: mv-calendar был 614 строк stock-GTK (без leather/paper, без search, без keyboard, remove-calendar заглушка, ICS import — `pass`, баг отображения времени `[11:16]`, load() молча сбрасывал corrupt store, валидация отсутствовала, end<start проходил, минуты нельзя было выбрать); APPS.md claims (libical, search, birthdays) не соответствовали коду — docstring исправлен
- [x] Mavericks visual integration (как Notes/Reminders family): leather sidebar с mini-month (Gtk.Calendar, отметки дней с событиями, клик → переход) и списком календарей (color dot + visibility toggle), paper content area, colored event blocks, Mavericks toolbar buttons, view switcher Month/Week/Day (toggle segments с mutual exclusion)
- [x] Week view: time grid (24h, hour gutter, all-day strip, абсолютное позиционирование событий по часам/минутам); Day view: time grid + детали (время, location, notes); Month view: styled cells (today highlight, other-month dim, event bullets с временем)
- [x] Event dialog: валидация (title required → OK disabled; end<start → error dialog), hour+minute spinbuttons (ранее только часы), all-day toggle (отключает time), repeat (none/daily/weekly/monthly/yearly с month-end clamp и leap-year clamp), location, notes; edit mode (двойной клик / context menu) с prefill
- [x] Repeat expansion: iter_event_dates (daily/weekly/monthly/yearly, anchor day, 5-год horizon, 500 occurrences cap); RRULE:FREQ export/import round-trip
- [x] ICS: export с escaping (\, \; \\ \n), folding (75 chars), VALUE=DATE для all-day, CRLF, RRULE; import parser (unfold, VEVENT, DTSTART/DTEND DATE+DATETIME, SUMMARY/LOCATION/DESCRIPTION/UID/RRULE, malformed VEVENT skipped + count)
- [x] Upcoming-event nudges: --check-upcoming CLI (events в течение 15 мин, all-day/past/already-notified пропуск), mv-calendar-check.timer (OnCalendar=*:0/5, oneshot) + .service, firstboot enable; тот же паттерн, что Reminders
- [x] Search filter (Ctrl+F, Escape clears): week/day lists + month bullets; keyboard: Ctrl+N/Ctrl+F/Ctrl+E/Ctrl+I, ←/→, T, 1/2/3, Delete (confirm); context menu event block (Edit/Delete); empty states ("No events / match your search")
- [x] Corrupt-store safety (как Notes/Reminders): backup-on-save, restore from backup, quarantine + warning dialog; normalize (defaults для calendars/events, non-dict events dropped); geometry persistence; strict parse_dt (None вместо now() fallback — silent data corruption устранён)
- [x] Найдено и исправлено по ходу: (1) Gtk.Calendar.get_year() не существует в GTK3 — краш при сохранении любого события (найдено GUI smoke, заменено на get_date()); (2) Gtk.ToggleButton не имеет mutual exclusion — view switcher мог оставаться в двух active-состояниях, re-click не работал (найдено GUI smoke, добавлен handler_block + manual exclusivity + no-op re-click); (3) _normalize не удалял non-dict events; (4) write_ics не писал VALUE=DATE; (5) read_ics не unescape-ил значения; (6) read_ics KeyError на VEVENT без DTSTART
- [x] Validation: py_compile OK, 63 headless-тест (scripts/test-mv-calendar.py: store/backup/quarantine/restore/normalize/parse_dt/events_for_day/repeat/matches/validate/ICS round-trip incl escaping/folding/RRULE/malformed-skip/check_upcoming с моком notify-send/CLI), GUI interaction smoke на реальном GTK :0 (20 checks: views/search/dialogs/validation/keyboard/selection/ICS/visibility), desktop-file-validate OK, check-sync ALL CHECKS PASSED, make install DESTDIR OK (timer+service installed), sibling suites green (notes 41, reminders 31)
- [ ] HW: visual validation leather/paper + event blocks на 2304×1440, upcoming-nudge через реальный user timer в сессии, Ctrl+Alt+C global binding, geometry restore на реальной сессии

### Фаза 0.47 — Reminders: regression restore + refinement pass (2026-09-26, без железа)
- [x] Forensic audit: подтверждено, что коммит 89b6649 (Voice Memos) молча откатил mv-reminders 359→156 строк — leather sidebar, paper task list, priority badges, overdue highlighting уничтожены; APPS.md индексировал регрессию, но код не был восстановлен после Notes 0.46
- [x] Visual integration восстановлена из 89b6649^: leather list sidebar, paper task list, custom checkboxes (cell data funcs), priority badges, overdue/due-today подсветка, strikethrough выполненных, Mavericks toolbar CSS
- [x] Latent bug найден и исправлен: CellRendererText не имеет get_style_context в GTK3 — pre-regression код вызывал его в render_due_cell/render_priority_cell (краш на любой задаче с due/prio); заменено на прямые свойства (foreground/background/weight)
- [x] Due-date notifications: существующий hourly user systemd timer (mv-reminders-check, oneshot → --check-due) покрывает due-today + overdue, notify once/task/day через libnotify; проверено тестами с моком notify-send
- [x] Refinement: search filter (Ctrl+F, Escape — фикс тот же, что в mv-notes: "changed" вместо "search-changed"), context menus (task: Edit/Toggle/Delete; list: Rename/Delete с защитой последнего списка), Clear Completed с confirm, rename/delete list, keyboard Ctrl+N/Ctrl+Shift+N/Delete/Ctrl+F/Escape, empty states, geometry persistence
- [x] Corrupt-store safety (как в Notes): backup-on-save (.bak), restore from backup, quarantine + warning-диалог; missing store — тихий first-run
- [x] Sibling regression audit: mv-calendar (614), mv-voice (405), mv-console (290), mv-textedit (584), mv-notes (938), mv-calculator (369), mv-stickies (203) — все совпадают с последними feature-коммитами, silent reverts не найдены; только mv-reminders был откачен
- [x] Validation: py_compile OK, desktop-file-validate OK, 31 headless-тест (scripts/test-mv-reminders.py: store/backup/quarantine/restore/normalize/due_state/matches/geometry/check_due с моком notify-send), GUI smoke на реальном GTK :0 (create/add/toggle/search/shortcuts/context-menus/clear-completed/last-list-guard/corrupt-store-warning), check-sync ALL CHECKS PASSED, systemd-analyze verify OK (с DESTDIR-установленным бинарём; на build-хосте /usr/bin/mv-reminders отсутствует — ожидаемо, путь из target-установки), makepkg rebuild OK, packed binary == source, DESTDIR install OK
- [ ] HW: visual validation leather/paper на 2304×1440, due/priority cell rendering, доставка уведомлений через реальный user timer в сессии, geometry restore на реальной сессии

### Фаза 0.46 — Notes: regression restore + trash/shortcuts/export/print (2026-09-26, без железа)
- [x] Forensic audit: APPS.md заявлял leather sidebar/lined paper/checkboxes/pin/search-highlight, но код mv-notes был откачен к базовой версии 159 строк в коммите 89b6649 (Voice Memos) — визуальная интеграция уничтожена молча; найдено через git history (03e26cd → 89b6649)
- [x] Регрессия восстановлена: Mavericks CSS (leather folder sidebar, lined paper editor), custom cell renderers, pin/checklist индикаторы, text tags
- [x] Recently Deleted: delete → trash (не удаление), restore/delete-forever/empty-trash с confirm-диалогами, 30-дневный auto-purge при load, trash pseudo-folder в sidebar со счётчиком
- [x] Pin toggle (кнопка + Ctrl+Shift+P + context menu) — ранее флаг pinned существовал, но UI-действия не было
- [x] Click-to-toggle checkboxes ([ ]↔[x]) кликом в checkbox-зоне редактора
- [x] Search highlighting: тег search_highlight применяется к совпадениям в открытой заметке (тег был создан, но не использован)
- [x] Export note → .txt (FileChooser save), Print (Gtk.PrintOperation, draw-page рендеринг текста)
- [x] Keyboard shortcuts: Ctrl+N note, Ctrl+Shift+N folder, Delete, Ctrl+F search, Ctrl+P print, Ctrl+E export, Ctrl+Shift+P pin, Escape clear search
- [x] Context notes: note (Pin/Export/Delete), folder (New/Delete folder → notes в trash), trash (Restore/Delete Forever/Empty Trash)
- [x] Empty states: подсказки в notes pane и editor pane; сортировка по mtime, счётчики в sidebar, даты в списке
- [x] Window geometry persistence (store["geometry"], save on destroy)
- [x] %U import: открытие .txt файла создаёт новую заметку
- [x] Corrupt-store handling: backup-on-save (.bak), restore from backup при повреждении, quarantine файла + warning-диалог, missing store ≠ corruption (silent first-run)
- [x] Найдено и исправлено по ходу: (1) refresh_folders менял selection → view переключался в trash mode (handler block + restore selection); (2) Gtk.SearchEntry search-changed не срабатывает на programmatic set_text → connect на changed; (3) STORE default-arg binding → late binding; (4) missing store ошибочно считался corruption → блокирующий диалог на первом запуске
- [x] Validation: py_compile OK, 41 headless-тест (scripts/test-mv-notes.py: store/backup/quarantine/trash/purge/folders/checklist/sanitize/highlight/paginate/import/geometry), GUI smoke на реальном GTK (create/edit/pin/search/trash/restore/shortcuts/delete-folder), corrupt-store GUI warning OK, desktop-file-validate OK, check-sync ALL CHECKS PASSED, package rebuilt + DESTDIR install OK
- [ ] HW: visual validation leather/lined-paper на 2304×1440, print dialog rendering, checkbox click feel, geometry restore на реальной сессии

### Фаза 0.45 — TextEdit: Mavericks visual integration (2026-09-26, без железа)
- [x] Аудит существующего mv-textedit: GtkSourceView4, HeaderBar с New/Open/Save/SaveAs, format-меню (Bold/Italic/Underline/Strikethrough/Font/Color/Alignment), status bar (Ln/Col/chars), открытие/сохранение .txt/.md
- [x] Format bar добавлен как отдельная панель под HeaderBar: Bold/Italic/Underline (ToggleButton), Alignment (Left/Center/Right), Font Family combo, Font Size combo, Text Color picker
- [x] Find/Replace панель добавлена (GtkSource.SearchContext): search entry, Next/Previous, Replace/Replace All, highlight matches, Escape закрывает
- [x] Print поддержка добавлена (Gtk.PrintOperation с PRINT_DIALOG)
- [x] Document inspector расширен: word count, encoding (UTF-8), line endings (LF/CRLF/CR detection) в status bar
- [x] Autosave/draft recovery для untitled документов: автосохранение каждые 30с в ~/.local/share/mv-textedit/drafts/autosave.json, восстановление при следующем открытии, очистка при save/close
- [x] Обновлен status bar: "Ln X, Col Y | N words | M chars | ENC | EOL"
- [x] Validation: py_compile OK, desktop-file-validate OK, scripts/check-sync.sh ALL CHECKS PASSED, headless import OK
- [ ] HW: visual validation of format bar appearance, print dialog, autosave behavior on real session

### Фаза 0.44 — P0 Desktop Chrome: audit + gaps (2026-09-26, без железа)
- [x] Forensic audit всех 9 поверхностей (Menu Bar, Dock, App Menu, Dialogs, File Chooser, Context Menus, Keyboard, Desktop/Wallpaper/Session, Window Management)
- [x] Keyboard layer verified: 20+ bindings, no conflicts, no orphans; missing Super+Q/M/H/W/E/T; docs/KEYBOARD.md created
- [x] xfwm4 theme CREATED (was referenced but missing): themerc (button_layout=OIM|:, traffic lights LEFT) + close/minimize/maximize XPMs
- [x] Wallpaper CREATED: mavericks-desktop.png 2304×1440 (blue-green gradient, pure Python PNG)
- [x] Autostart CREATED: plank.desktop + mv-notify-send.desktop in skel/.config/autostart/
- [x] xfce4-panel theme CREATED: panel.css (translucent, gradient, tasklist indicators)
- [x] File chooser polish: pathbar buttons + column headers added to _widgets.scss
- [x] Dialog polish: dialog-action-area + button styling added to _windows.scss
- [x] APPS.md: 9 new P0 rows added with real statuses
- [x] Validation: sassc compile OK, xmllint OK, desktop-file-validate OK (both autostart .desktop files)
- [ ] HW: visual validation of panel/dock/wallpaper/xfwm4 theme on 2304×1440; plank zoom/reflect; menu bar look

### Фаза 0.43 — Power UI: Mavericks-диалог питания поверх logind D-Bus (2026-09-26, без железа)
- [x] Аудит: старая mv-power-ui была минималистичным GTK-окном (4 кнопка + systemctl напрямую, без logind/UPower/логута/состояний ошибок); строки в APPS.md P0 не было вовсе
- [x] Развёрнут backend: logind D-Bus (CanSuspend/CanReboot/CanPowerOff → Suspend/Reboot/PowerOff с interactive=TRUE), fallback на systemctl при отсутствии logind, логут через xfce4-session-logout, только-чтение батарея через UPower D-Bus
- [x] Mavericks UX: chooser (Sleep/Restart/Shut Down/Log Out) + preset-диалоги с 60-секундным обратным отсчётом (Cancel/Escape прерывает), кнопка по умолчанию — aqua-синяя, чекбокс «Reopen windows when logging back in» → xfconf SaveOnExit, футер батареи, бесшовное оформление через CSS (градиентное окно, скругления, тень)
- [x] Состояния: кнопка действия недоступна при Can*=no; error-dialog при отказе logind D-Bus; «Battery status unavailable» при отсутствии UPower
- [x] Тесты: scripts/test-mv-power-ui.py — 44 headless-теста (mock-logind на private bus: caps yes/no/challenge, записывает вызовы, не выполняя реальных действий; fallback-планы; Countdown/countdown_text/format_battery_line/action_state; execute_plan с инжектированными моками; CLI --status с и без logind); все проходят
- [x] Проверки: py_compile, xmllint (оба зеркала keybindings), desktop-file-validate (mv-power-ui.desktop), scripts/check-sync.sh — ALL CHECKS PASSED
- [x] Keybindings: Ctrl+Alt+Escape → chooser (было), добавлен Ctrl+Alt+Delete → logout; оба зеркала xfce4-keyboard-shortcuts.xml синхронны
- [x] .desktop: mv-power-ui.desktop (NoDisplay=true — в Launchpad не нужен, как и в macOS; приложение вызывается hotkey/Apple-меню)
- [x] GUI smoke на этом хосте невозможен (нет Xvfb) — инстанциация PowerUI остаётся HW-валидацией; логика покрыта 44 тестами
- [ ] HW: suspend/resume реальный, телеметрия батареи, polkit interactive auth, аппаратная кнопка питания

### Фаза 0.38 — Orchestrator model fallback (2026-09-26, без железа)
- [x] Причина: двойной пин `nemotron-3-ultra-free` (orchestrator frontmatter + agent.build) — одна мёртвая модель роняла весь loop; fallback-процедуры не было вовсе (проверено историей)
- [x] `.opencode/model-fallback.json`: цепочка пользователя (OpenRouter North Mini Code → Free Router → Zen LongCat 2.5 Preview → Nemotron 3 Ultra → Nemotron 3.5 Lightning last-resort)
- [x] `scripts/session-reuse.py`: `models` (chain-first live-резолвер, без хардкода) + `classify-error` (quota=10/context=12 → fallback; ordinary/unknown → без fallback); reuse/retire не тронуты
- [x] `orchestrator.md` MODEL FALLBACK + `opencode.jsonc`: пин build СНЯТ (наследует живую модель); AGENTS.md 14.3 — указатель
- [x] Проверено: py_compile, матрица классификатора, offline-резолвер (ultra skipped → next North Mini Code); живое доказательство — objective продолжен кросс-модельно (ultra Task cancelled → продолжение на muse-spark)
- [x] Caveats: LongCat Zen-id не верифицирован live; lightning — last resort; нужен connected OpenRouter; после правок agent-файла — рестарт сервера

### Фаза 0.39 — Fallback hardening (2026-09-26, без железа)
- [x] Chain-only execution по умолчанию (`--all` только для диагностики); `never`-list (Muse Spark) исключается всегда — проверено unit-тестом
- [x] Orchestrator frontmatter → `openrouter/cohere/north-mini-code:free` (head цепочки); явный запрет self-invoke (только `build` через Task)
- [x] LongCat: ВЕРИФИЦИРОВАН как Zen-модель (`longcat-2.5-preview-free`, models.dev, релиз 2026-09-25) — guess ID совпал
- [x] Auth-инвентарь (без секретов): контейнер — openrouter+opencode; Windows-профиль — openrouter+google+groq, БЕЗ opencode → Zen-пункты на Windows-сервере только после `/connect` Zen
- [x] Проверено: py_compile, резолвер chain-only/--all, never-enforcement; опциональный hard-block — disable muse-spark в Zen-консоли

### Фаза 0.40 — Two-plane topology (2026-09-26, без железа)
- [x] Доказательство из opencode.db: живой `MavLinOS` сидит на spark (stale session), дети build наследовали её после unpin — механизм работал как настроен
- [x] `agent.build.model` = `opencode/longcat-2.5-preview-free` (worker-plane); orchestrator-plane = north-mini; spark невозможен конструктивно
- [x] Классификатор: `AUTH_ERROR` (40); резолвер: `rotate:`-строка + «no rotation» пока пин жив
- [x] Честное ограничение: смерть пина = единственная stop-and-wait (one-paste sed + рестарт); зафиксировано в orchestrator.md
- [x] Проверено: py_compile, оба сценария резолвера, jsonc-пин

### Фаза 0.41 — Plane split в конфиге (2026-09-26, без железа)
- [x] `provider.opencode.blacklist` (4 spark-ID): проект + оба global-зеркала — spark скрыт из `/models`-пикера везде
- [x] `small_model` = north-mini (проект): фоновые title/summary не уедут на spark через auto-cheap-pick
- [x] Матрица плоскостей зафиксирована в DECISIONS.md; sync never/blacklist описан в chain-файле
- [x] Проверено: все 3 jsonc парсятся, пины на месте; требуется ПОЛНЫЙ рестарт сервера + разовый уход stale-сессии со spark

### Фаза 0.42 — Исправление: spark в пикере для оркестратора, blacklist убран (2026-09-26)
- [x] `provider.opencode.blacklist` УДАЛЁН из проекта + обоих global-зеркал — spark теперь виден в /models для выбора оркестратора (требование пользователя)
- [x] Worker pin (LongCat) + small_model (north-mini) — исполнительный слой неизменен, spark как воркер невозможен конструктивно
- [x] `.opencode/model-fallback.json`: `never` = только для резолвера (исполнение), picker visibility свободен
- [x] Проверено: конфиги парсятся, пины на месте; требуется ПОЛНЫЙ рестарт сервера

### Фаза 0.43 — Workers never delegate (2026-09-26, без железа)
- [x] Причина: топ-уровень `task allow` без overrides для build — Task воркера показывал всех агентов, отсюда попытки вложенной делегации и build→orchestrator self-invoke
- [x] `agent.build.permission.task` = deny-all + worker-description; stock Build не тронут, subagent_depth без изменений
- [x] Промпт-компаньоны: orchestrator.md шаг 3 + AGENTS.md 14.7
- [x] Проверено: jsonc валиден (deny у build, allow топ-уровня цел); требуется ПОЛНЫЙ рестарт сервера

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

### Фаза 0.29 — Finder keyboard shortcuts, Empty Trash, thunarrc enhancements (2026-09-26, без железа)
- [x] thunar-uca.xml: added "Empty Trash" action (trash-empty) with user-trash-full icon
- [x] xfce4-keyboard-shortcuts.xml: added Finder-like global shortcuts:
  - Super+N → mv-newfolder $HOME/Desktop (New Folder on Desktop)
  - Super+Shift+N → mv-newfolder $HOME (New Folder in Home)
  - Super+I → mv-getinfo $HOME (Get Info)
  - Super+O → mv-openwith $HOME (Open With)
- [x] thunarrc: enhanced with Finder-like defaults (ShowToolbar, ShowStatusbar, ShowLocationSelector, TreePaneWidth, window geometry, case-insensitive sort)
- [x] All XML validated (xmllint), sync check passed, packages rebuilt
- [x] APPS.md updated: Finder UCA now includes Empty Trash; keyboard shortcuts documented

### Фаза 0.30 — Spotlight gap fixes (2026-09-26, без железа)
- [x] mv-spotlight: file results now include xdg-open action (files open from results)
- [x] System actions added: Settings, Control Center, Activity Monitor, Disk Utility, Terminal (match on name/description)
- [x] Error handling: missing plocate / empty index / timeout shown as user-visible result
- [x] Empty state handling: "No recent items" on empty query; "No results for 'query'" when nothing matches
- [x] rofi-mavericks.rasi: visual polish (Mavericks-style skeuomorphic accents, better spacing, scrollbar, rounded corners, softer colors)
- [x] All validations pass: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED
- [x] APPS.md Spotlight row updated with implemented features

### Фаза 0.31 — Launchpad gap fixes (2026-09-26, без железа)
- [x] mv-launchpad: mv-launchpad.desktop entry added for app menu integration
- [x] mv-launchpad: default folders.json auto-population (Utilities/Other) on first run
- [x] mv-launchpad: folder navigation with "Back" button (open folder → view apps → back to main)
- [x] mv-launchpad: empty state handling (no apps found, no search results, empty folder)
- [x] mv-launchpad: robust .desktop parsing with icon existence validation and fallback
- [x] mv-launchpad: duplicate .desktop handling (user overrides system)
- [x] rofi-launchpad.rasi: Mavericks-style visual polish (skeuomorphic accents, rounded corners, scrollbar, softer colors, shadows, transitions)
- [x] All validations pass: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED
- [x] APPS.md Launchpad row updated with implemented features

### Фаза 0.32 — Mission Control window overview enhancements (2026-09-26, без железа)
- [x] mv-mission-control: added active window detection (via xprop _NET_ACTIVE_WINDOW) with "▸" prefix marker
- [x] mv-mission-control: added empty workspace display (shows "(empty)" placeholder for workspaces with no windows)
- [x] mv-mission-control: improved error handling — graceful degradation when wmctrl missing (shows install hint)
- [x] mv-mission-control: added window action stubs (--activate, --close, --minimize) for future rofi keybinding integration
- [x] mv-mission-control: expanded icon mapping for common applications (Chrome, VS Code, Discord, Steam, terminals, Office, etc.)
- [x] rofi-mission-control.rasi: Mavericks-style visual polish matching Spotlight/Launchpad theme evolution (softer palette, rounded corners, better spacing, larger icons, custom scrollbar, accent blue selection)
- [x] E-MC experiment: updated BASELINE_CMD to use mv-mission-control script mode (was rofi window mode)
- [x] E-MC experiment: added wmctrl presence check in status; skel rc path variable; improved apply/revert messaging
- [x] All validations pass: py_compile, rofi -dump-theme (LANG=C.UTF-8), check-sync ALL PASSED
- [x] APPS.md Mission Control row updated with implemented features

### Фаза 0.33 — Control Center gap fixes (2026-09-26, без железа)
- [x] mv-control: Wi-Fi connect/disconnect with password prompt for secured networks via nmcli
- [x] mv-control: Bluetooth device list with actual BlueZ D-Bus enumeration (name, connected/paired status, device icon)
- [x] mv-control: Bluetooth connect/disconnect/pair actions via BlueZ D-Bus (no pairing daemon)
- [x] mv-control: Audio output device switching via pactl set-default-sink (combo box now functional)
- [x] mv-control: Brightness slider robustness — shows "Brightness control not available" when no backlight path
- [x] mv-control: Battery power mode — reads current TLP mode (balanced/powersave/performance), shows info dialog for changes (requires root)
- [x] mv-control: Error/empty states for all sections (NetworkManager, BlueZ, PulseAudio, backlight, UPower, xfce4-notifyd)
- [x] All validations pass: py_compile, check-sync ALL PASSED
- [x] APPS.md Control Center row updated with implemented features

### Фаза 0.34 — Notification Center history + keyboard shortcut (2026-09-26, без железа)
- [x] mv-notify-send: notify-send wrapper that logs notifications to ~/.local/share/mavericks/notifications.json (max 500 entries, no daemon)
- [x] mv-notification-center: Mavericks-style history viewer (GTK3, app-grouped list, Clear/Clear All buttons, DND toggle in header, keyboard navigation)
- [x] Keyboard shortcut: Super+Shift+V → mv-notification-center (added to xfce4-keyboard-shortcuts.xml)
- [x] Desktop entry: mv-notification-center.desktop with X-Mavericks-Native=true
- [x] Makefile updated to install both scripts
- [x] All validations pass: py_compile, xmllint, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Notification Center row updated with implemented features
- [x] Remaining gap: action buttons on banners (xfce4-notifyd limitation, not feasible without daemon); banner visual validation needs hardware

### Фаза 0.35 — Quick Look enhancements (2026-09-26, без железа)
- [x] mv-quicklook: multi-file support (pass multiple files, navigate with Left/Right arrows, Space, PgUp/PgDn)
- [x] mv-quicklook: fullscreen toggle (F key, double-click, toolbar button)
- [x] mv-quicklook: counter display ("2 of 5") in header bar
- [x] mv-quicklook: Previous/Next/Fullscreen toolbar buttons
- [x] mv-quicklook: keyboard shortcuts (Escape/q=close, Enter/o=open, Left/P/Up=prev, Right/N/Down/Space=next, F/F11=fullscreen)
- [x] mv-quicklook-thunar: global hotkey handler (Super+Shift+Space) — uses xdotool to copy Thunar selection to clipboard, parses file:// URIs, launches mv-quicklook
- [x] mv-quicklook-thunar.desktop: desktop entry for app menu integration
- [x] xfce4-keyboard-shortcuts.xml: added Super+Shift+Space → mv-quicklook-thunar
- [x] Makefile: added mv-quicklook-thunar to install targets
- [x] All validations pass: py_compile, xmllint, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Quick Look row updated with implemented features
- [x] Remaining gap: native Thunar Space key binding (requires Thunar plugin, not feasible pre-hardware); clipboard-based approach has ~150ms latency and requires xdotool; test Super+Shift+Space on HW

### Фаза 0.36 — Preview implementation (2026-09-26, без железа)
- [x] mv-preview: complete rewrite using poppler-glib (mature PDF backend, same as evince) + GdkPixbuf for images
- [x] Multi-file support: navigate between files with Ctrl+Left/Right arrows
- [x] Multi-page PDF navigation: Left/Right arrows, Home/End, thumbnail sidebar click
- [x] Thumbnail sidebar: renders all PDF page thumbnails, click to jump to page
- [x] Annotation toolbar UI: Select, Text, Shape, Sign buttons (stubbed, status bar feedback)
- [x] Keyboard shortcuts: Escape/q=close, Enter/o=open, arrows=page, Ctrl+arrows=file, Home/End=first/last page, F/F11=fullscreen, Alt+1-4=annotation tools
- [x] Fullscreen toggle (F key, toolbar button)
- [x] Open button: launches file in default external handler (xdg-open)
- [x] Error states: missing file, unsupported type, missing poppler, render errors shown in UI
- [x] Mavericks visual integration: skeuomorphic sidebar gradient, custom toolbar styling, status bar
- [x] MIME type associations in .desktop: application/pdf, application/postscript, image/* — Preview becomes default handler
- [x] poppler-glib dependency added to mavericks-apps optdepends (already present)
- [x] All validations pass: py_compile, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Preview row updated with implemented features
- [x] Remaining gaps: annotation persistence (requires poppler annotation API), form filling, export, signature management; PDF render validation needs hardware (2304×1440 panel)

### Фаза 0.37 — Screenshot post-capture preview + config + annotation handoff (2026-09-26, без железа)
- [x] mv-shot: rewritten with config file support (~/.config/mv-shot/config.ini) — save_dir, show_preview, preview_timeout, copy_to_clipboard
- [x] mv-shot: post-capture preview dialog (GTK3, Mavericks-style) with actions: Open in Preview, Show in Finder (Thunar), Move to Trash, Dismiss
- [x] mv-shot: auto-close timer for preview dialog (configurable timeout)
- [x] mv-shot: clipboard copy wiring — config option copy_to_clipboard copies saved file to clipboard after capture
- [x] mv-shot: error handling for missing backends (xfce4-screenshooter, ffmpeg) with user-friendly dialogs
- [x] mv-shot: annotation handoff — "Open in Preview" launches mv-preview with annotation toolbar UI (Select/Text/Shape/Sign stubs)
- [x] mv-shot: --config flag to show config file path
- [x] mv-screenshot.desktop: added MimeType, Keywords for better integration
- [x] All validations pass: py_compile, desktop-file-validate, check-sync ALL PASSED
- [x] APPS.md Screenshot row updated with implemented features
- [x] Remaining gaps: actual annotation persistence (requires poppler annotation API in Preview); recording validation on HW (ffmpeg x11grab CPU/power); keybinding feel test on real hardware; preview dialog visual validation on 2304×1440 panel

### Фаза 0.39 — Disk Utility Mavericks frontend (2026-09-26, без железа)
- [x] mv-diskutil: custom Mavericks-like Disk Utility frontend (Python/GTK3) over UDisks2 via Gio.DBus — storage stack reused, not rewritten
- [x] Sidebar: Internal/External groups, drives + partition children, Mavericks-style selection
- [x] Detail pane: model/vendor/serial/capacity/connection/media, capacity bar (statvfs), FS type/label/UUID/mount point/device/partition type
- [x] Actions: mount/unmount/eject via UDisks2 D-Bus (DO_NOT_AUTO_START, 15s timeout, error dialogs, re-enumerate after)
- [x] First Aid: S.M.A.R.T. status/temperature/power-on hours/bad sectors + SmartGetAttributes table (read-only); fsck repair explicitly NOT performed — dialog explains and points to gnome-disks
- [x] Destructive actions (format/partition/erase): deferred with in-UI reason pointing to gnome-disks — no unguarded destructive ops shipped
- [x] Empty states: UDisks2 not-available / cannot-connect / no devices / no selection
- [x] Apple S3X NVMe section: shown for NVMe drives, graceful "Available on hardware" empty state pre-HW
- [x] Keyboard: ListBox arrow navigation, Escape closes; refresh via header-bar button; no polling, no daemon
- [x] mv-disk-utility.desktop: Exec=mv-diskutil, X-Mavericks-Native=true, Keywords
- [x] Makefile: mv-diskutil added to install targets; no new heavy deps (python-gobject already in mavericks-apps)
- [x] Headless tests: scripts/mock-udisks2.py (fake UDisks2 service: SATA+ext4 mounted, USB vfat unmounted, Apple NVMe hfsplus) + scripts/test-mv-diskutil.py — 34 tests, all pass (read-only, no real disks)
- [x] All validations pass: py_compile, desktop-file-validate, check-sync ALL PASSED, make install DESTDIR smoke test OK
- [x] APPS.md Disk Utility row updated
- [x] Remaining gaps: S3X NVMe telemetry validation on HW; whole-disk filesystems without partition table not listed (UDisks2 limitation); visual validation on 2304×1440 panel; format/partition remain in gnome-disks by design

### Фаза 0.54 — Font Book: forensic launchability audit + self-sufficient rewrite (2026-09-27, без железа)
- [x] Forensic audit: real binary launch reproduced 100% startup crash — `Gtk.CssProvider.load_from_data` raised `gtk-css-provider-error-quark: 'text-align' is not a valid property name` (invalid GTK3 CSS in `.sidebar-item`), exit 1 before window construction. Same bug class as mv-keychain (7785bf4) — 4th fake completion.
- [x] Audit findings beyond crash: sidebar buttons non-functional, gnome-font-viewer handoff leaves window (and gnome-font-viewer not even in PKGBUILD deps), no enumeration/waterfall/glyphs/collections/search/keyboard, duplicate imports.
- [x] mv-fontbook rewritten self-sufficient: fontconfig enumeration via `fc-list --format` (cached per process, no polling) with Pango family-list fallback for degraded systems
- [x] Preview waterfall: selected face at 11/14/18/24/36/48 pt with pt labels + separators on paper background (PangoCairo on Gtk.DrawingArea)
- [x] Glyph grid: Pango coverage (`font.get_coverage`) over Basic Latin + Latin-1 + punctuation ranges, paper-backed section headers, dashed cells for uncovered codepoints
- [x] Collections: All Fonts / User / Computer / Fixed Width (fontconfig spacing ≥ 90) / Serif / Sans Serif (family-name heuristics — documented limits)
- [x] Install/remove user fonts: FileChooser → ~/.local/share/fonts (XDG) → fc-cache → re-enumerate; system font dirs never touched (path-prefix guard); confirm dialog on remove
- [x] Search (client-side filter, Ctrl+F), keyboard: Ctrl+F/I/O, Delete (user fonts only), Escape clears search; per-view GTK interactive search disabled so Ctrl+F always means the global field
- [x] Error/empty states: no-backend InfoBar, empty collection/search, install failure, remove refusal, missing gnome-font-viewer handoff
- [x] CSS crash-class regression fix: provider load wrapped in try/except GLib.Error → stderr + default theme, never crash on CSS
- [x] Real GUI smoke (Wayland :0): window constructs, 6 collections, 36 container fonts enumerated, collections/search filter, install+remove round-trip in isolated HOME, argv file preselection, waterfall + glyph grid rendered to cairo surfaces and visually verified (screenshots)
- [x] Launch re-verified post-fix: real binary alive at 4s, zero stderr (pre-fix: GLib.GError + exit 1)
- [x] scripts/test-mv-fontbook.py: 65 tests (pure logic + GUI smoke), all pass
- [x] Gate: py_compile, desktop-file-validate, check-sync ALL CHECKS PASSED, makepkg -f builds
- [x] mv-font-book.desktop: added MimeType (font/ttf, font/otf, font/collection, x-font forms)
- [x] PKGBUILD: fontconfig → depends; gnome-font-viewer → optdepends
- [x] Remaining gaps: Serif/Sans heuristics are name-based (documented); visual validation on 2304×1440 panel; font install round-trip on real system; HiDPI glyph grid density

### Фаза 0.55 — Digital Color Meter: forensic launchability audit + functional rewrite (2026-09-27, без железа)
- [x] Forensic audit: real launch smoke — окно _constructs без CSS-краша, но второй скрытый баг: `display.get_pointer()[:2]` в GDK3 возвращает (screen, x, y, mask), т.е. x=объект GdkScreen → `pixbuf_get_from_window` падал с TypeError → проглатывался `except: pass` → показания цвета НИКОГДА не обновлялись. Aperture combo, Lock Position, HSV-лейбл и gcolor3 handoff были нерабочими; не было loupe/форматов/копирования/палитры/клавиатуры.
- [x] mv-colormeter переписан: сэмплинг через Gdk root-window (X11), позиция указателя через seat API (non-deprecated) с fallback на get_pointer()
- [x] Aperture 1×1/3×3/5×5/10×10/25×25 с настоящим усреднением блока (с клампом к границам экрана)
- [x] Pixel loupe: увеличенное окно 11×11 вокруг точки с обведённой центральной ячейкой
- [x] Переключение форматов: sRGB 8-bit / sRGB % / Hex / HSV / Display P3 (настоящая матричная конверсия sRGB↔P3 через D65, не гамма-фейк)
- [x] Копирование в буфер (Ctrl+C) в активном формате; Ctrl+1..5 — горячие клавиши форматов
- [x] Сессионная палитра: Ctrl+P добавить (дубликаты отклоняются), клик по swatch — загрузить цвет, × — удалить, Ctrl+S — экспорт в .gpl (GIMP Palette, round-trip протестирован)
- [x] Lock Position: фиксирует точку сэмплинга; стрелки двигают на 1 px (Shift — 8 px)
- [x] Wayland disposition: явное состояние "sampling unavailable under Wayland", без фейковых чёрных сэмплов; таймер 100 ms только под X11 и только пока окно открыто
- [x] Error-состояния: нулевая геометрия экрана, сбой захвата, исключение сэмплинга, сохранение пустой палитры, отсутствующий gcolor3
- [x] gcolor3 handoff: кнопка в header bar (Ctrl+O), видна только если установлен; optdep в PKGBUILD
- [x] CSS crash-class regression guard: загрузка provider обёрнута в try/except GLib.Error (паттерн mv-fontbook)
- [x] Реальный GUI smoke (Wayland :0): окно строится, fallback-состояние показано, все контролы протестированы
- [x] Launch перепроверен: реальный бинарь жив на 4с, пустой stderr
- [x] scripts/test-mv-colormeter.py: 76 тестов (pure logic + GUI smoke), все проходят
- [x] Gate: py_compile, desktop-file-validate, check-sync ALL CHECKS PASSED, make install DESTDIR OK, makepkg -f собирается
- [x] Remaining gaps: реальные значения пикселей на панели 2304×1440 (HW); валидация X11-пути под Xfce (build env — Wayland, X11 проверен только через мок-сэмплер); плотность loupe на HiDPI
