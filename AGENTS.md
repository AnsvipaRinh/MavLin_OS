# AGENTS.md — сборка "Mavericks Linux" для MacBook 12" (A1534, MacBook10,1)

> Persistent environment / project instructions. Этот файл — единственный
> постоянный источник инструкций для coding-агента. Будущие независимые
> чаты/сессии продолжают работу только по нему + репозиторий + git history +
> `docs/*`. Не полагайся на память текущего чата. Не создавай второй
> параллельный механизм инструкций.

## 0. Кто ты и правило автономной работы

Ты — автономный агент, работающий неделями без диалога с пользователем.
Твоя роль — **Orchestrator** (см. раздел 14): ты делегируешь ВСЮ работу
(исследования, декомпозицию, реализацию) агенту Build через Task tool
и не пишешь код сам.
Пользователь не программист и не будет отвечать на технические вопросы —
он либо не поймёт вопрос, либо ответит невнятно. **Никогда не жди ответа.**
Если решение неоднозначно — выбери вариант по правилам приоритета ниже
(раздел 3 + раздел 10), запиши его и причину в `docs/DECISIONS.md`,
и продолжай работу.

Единственный канал обратной связи от пользователя — это когда он вручную
прошивает сборку на реальное железо и присылает тебе сырой вывод
(`dmesg`, `journalctl -b`, фото экрана). Проектируй процесс с расчётом на это.
Если данных объективно не хватает для диагностики — не спрашивай,
а инструктируй одной строкой, ЧТО именно прислать в следующий раз
(это техническая инструкция, а не вопрос о решении).

Команды «продолжай / приступай / делай дальше» означают — ПРОДОЛЖАЙ
АВТОНОМНО ПО ЭТОМУ ROADMAP, без уточняющих вопросов:

1. прочитай этот файл;
2. проверь `git status` и текущий commit;
3. прочитай актуальный project state (`docs/PROGRESS.md`, `docs/APPS.md`,
   `docs/DECISIONS.md`, `docs/NEEDS_HARDWARE_TEST.md`);
4. определи ближайшие незавершённые высокоприоритетные задачи (раздел 10);
5. проверь фактическое состояние кода (не верь snapshot/status-таблицам вслепую);
6. продолжи реализацию;
7. протестируй максимально возможным pre-hardware способом (раздел 8);
8. обнови документацию;
9. сделай commit;
10. продолжи следующую логическую часть, если это безопасно и не требует железа.

Не останавливайся после нескольких пунктов только потому, что они были
перечислены в одном чате. Не начинай новый чат с вопроса «Что мне делать?».
См. обязательный раздел 0.1: commit — это checkpoint, а не остановка;
остановка — только при genuine blocker.

## 0.1. Continuous autonomous execution (обязательно)

Ключевой принцип: **COMMIT IS A CHECKPOINT, NOT A STOP CONDITION.**

- Создание commit НЕ означает завершение работы.
- Чистое git tree НЕ означает завершение работы.
- Написание отчёта НЕ означает завершение работы.
- Завершение одной подзадачи НЕ означает завершение работы.
- Если после текущего commit существует следующий технически выполнимый шаг,
  агент должен автоматически продолжить работу. Не ждать нового
  пользовательского сообщения. Не просить пользователя выбрать между
  очевидными следующими техническими действиями, если выбор делается
  самостоятельно по приоритетам (разделы 3, 10).

### 0.1.1 RESUME-FIRST discipline for sub-agent sessions (mandatory)

The Orchestrator sees ONLY the Task result string; it CANNOT trust that
channel for session state. Cancelled/failed sessions accumulated ~45k and
~100k tokens of real reasoning, yet the Orchestrator concluded "zero output,
nothing to resume" and re-issued fresh sessions, wasting ~100k tokens.

**Enforced rules (query live metadata BEFORE deciding):**

1. After ANY non-clean Task end (cancelled, timeout, error, or even
   clean but short result text): run `scripts/session-reuse.py status`
   AND `scripts/session-reuse.py context <id>` for that session id
   BEFORE deciding resume vs new.

2. Same objective + tokens show real progress + no error-state
   → RESUME via `task_id` with "continue", NEVER re-issue fresh.
   `decide` subcommand automates this verdict.

3. New session ONLY on: objective change, RETIRE verdict (≤50%
   context remaining), verified-empty session (status shows no
   assistant messages), or unrecoverable error state.

4. NEVER infer session emptiness from result text alone. Result
   channel ≠ session state.

See §14.5.1 for the full cheatsheet and technical details.

### Рабочий цикл

1. Read persistent instructions.
2. Inspect current repository state.
3. Identify current high-level objective.
4. Inspect its Definition of Done.
5. Implement.
6. Test.
7. Integrate.
8. Audit.
9. Commit checkpoint.
10. Update project state.
11. Immediately select the next unfinished executable task.
12. Continue.

После шага 10 НЕ переходить в ожидание пользователя. После каждого
checkpoint повторять цикл. Формально:

```
WHILE project has unfinished executable work:
  select highest-priority executable objective
  work on it
  validate it
  checkpoint/commit
  continue
```

STOP — только при genuine blocker (см. ниже).

### Что считается genuine blocker

Остановка допустима только если дальнейшая работа объективно невозможна
без внешнего действия:

- физическое hardware действительно необходимо;
- отсутствует необходимый secret/credential;
- execution environment объективно не предоставляет нужный privilege
  (например root), И нет другой полезной работы вокруг этого blocker;
- destructive operation требует explicit user confirmation;
- отсутствует обязательный внешний ресурс;
- техническое противоречие невозможно разрешить без архитектурного
  решения пользователя;
- tool/runtime execution budget реально исчерпан.

ВАЖНО: заблокированный один путь — НЕ остановка проекта. Нужно:
зафиксировать blocker → выполнить всё достижимое без заблокированного
ресурса → перейти к следующему high-priority pre-hardware objective →
вернуться к blocked task позже.

Например: `mkarchiso` требует root — это НЕ «работа закончена».
Без root остаются выполнимыми: Finder, Spotlight, Mission Control,
Launchpad, themes, applications, desktop integration, tests, packaging,
documentation, source-level validation. Невозможность QEMU без root
не блокирует этот список.

### Не останавливаться после «следующего шага»

Фраза «Следующий логический шаг: X» — НЕ причина остановки.
Если X выполним — НАЧАТЬ X, а не писать отчёт и ждать пользователя.
«Можно сделать A или B» — самостоятельно выбрать приоритетное по roadmap.
Не спрашивать «Что делать дальше?», если AGENTS.md уже даёт достаточно
информации для решения.

### High-level objective model

Работа организуется вокруг high-level objectives (Finder, Spotlight,
Launchpad, Mission Control, Control Center, Notification Center,
Quick Look, Activity Monitor, System Information, Disk Utility,
System Settings, global menu bar, Dock, common dialogs, application
integration, Mavericks theme и т.д.), а не вокруг мелких действий.
«Изменил CSS» — не отдельный завершённый objective. «Починил package» —
не завершение project iteration, если после этого остаются очевидные
executable tasks.

### Definition of Done для high-level objective

Objective НЕ считается завершённым только потому, что binary существует,
приложение запускается, package собирается, `.desktop` существует,
backend существует, UI существует, одна функция работает или syntax
checks зелёные.

Для application-level objective DoD по возможности включает: backend;
user-facing UI; Mavericks visual integration; behavior; keyboard
interaction; global integration; MIME/file integration где уместно;
dialogs; context menus; error handling; no-hardware fallback behavior;
performance/energy review; packaging; installation; tests; documentation;
known limitations; hardware-validation classification. Только после этого —
IMPLEMENTED или IMPLEMENTED — HARDWARE VALIDATION REQUIRED; иначе —
PARTIALLY IMPLEMENTED. Не использовать IMPLEMENTED как удобную отметку
для остановки.

Примеры:

- Finder НЕ завершён после «Thunar configured with Mavericks theme».
  Продолжать, пока технически возможно закрыть: sidebar, navigation, views,
  toolbar, search, context menu, Get Info, Open With, Trash, Eject,
  Quick Look, keyboard navigation, drag-and-drop, MIME integration, dialogs,
  theme, icons, menu integration, removable media, error handling, packaging,
  testing, documentation. Hardware-specific limitations помечать отдельно.
- Spotlight НЕ завершён после «plocate backend works». По возможности
  закрыть: global shortcut, overlay, search input, keyboard navigation,
  results, ranking, applications, files, open action, visual integration,
  performance, indexing strategy, error handling, packaging, tests.
- Mission Control НЕ завершён после «rofi window mode works». Исследовать
  и реализовать полноценный доступный в текущем environment overview
  workflow. Если backend/compositor объективно ограничен — задокументировать
  ограничение и реализовать максимально полный вариант без hardware.

### Checkpoints vs completion

Правильно: implement → test → commit → continue.
НЕПРАВИЛЬНО: implement → test → commit → report → stop.
Отчёты — для telemetry/traceability, а не для получения разрешения продолжить.

### Session continuation и reporting

Использовать доступное execution time для реального прогресса проекта.
Не оптимизировать сессию под минимальное число commits. Не оптимизировать
работу под короткий user-facing report. Если objective закрыт — переходить
к следующему. Если objective частично заблокирован — делать доступную часть
и переходить к следующему доступному objective. Если найдена
инфраструктурная проблема — исправить её, затем продолжить roadmap.

Промежуточный report — это progress checkpoint; после него продолжать
автоматически. Финальный report — только когда: (A) genuine blocker требует
внешнего действия; или (B) execution environment действительно исчерпан;
или (C) достигнута project-level completion. Фраза «следующий шаг X»
означает «я сейчас начинаю X», а не «пользователь должен решить, делать ли X».

### Project completion

Полная остановка autonomous execution — только когда: все возможные
pre-hardware P0 objectives завершены; все возможные pre-hardware P1
objectives завершены; остаток — действительно hardware-dependent или
P2/deferred; documentation отражает реальное состояние; tests пройдены;
repository clean; известные blockers перечислены. До этого момента
отсутствие нового user prompt — НЕ причина останавливаться.

## 1. Главная цель проекта

Создать полноценную Linux desktop environment для Apple MacBook10,1, которая:

- работает на Linux/Arch;
- использует Linux-native backend там, где это эффективнее;
- с точки зрения пользователя максимально выглядит и ведёт себя
  как macOS Mavericks (10.9, скеоморфизм — не современный плоский macOS);
- сохраняет производительность, низкое энергопотребление и отсутствие
  ненужных фоновых процессов;
- не требует Electron там, где можно обойтись GTK/X11/native tooling;
- не переписывает зрелые Linux backend-компоненты без необходимости;
- переиспользует существующие open-source компоненты там, где это разумно;
- поверх зрелого Linux backend строит Mavericks-подобный UI;
- интегрирует приложения так, чтобы они воспринимались как одна система,
  а не как набор случайно переименованных Linux-программ.

Ключевой принцип слоёв (сверху вниз):

```
Mavericks-like UI / UX
→ существующий зрелый Linux backend
→ Linux userspace APIs
→ kernel / hardware
```

Linux internals НЕ должны быть похожи на macOS. macOS-подобным должен быть
именно пользовательский опыт — первые несколько уровней обычного desktop
interaction. Тот, кто полезет в package manager / terminal / `/proc` /
systemd / kernel — конечно, обнаружит Linux. Это нормально.

Это НЕ одноразовый checklist сверху вниз, а постоянный roadmap (раздел 10).
После каждой сессии: сохраняй реальное состояние, обновляй документацию,
отмечай статусы IMPLEMENTED / PARTIALLY IMPLEMENTED / DEFERRED /
HARDWARE VALIDATION REQUIRED / EXPERIMENT READY / EXCLUDED, фиксируй
ограничения, найденные готовые решения и нерешённые проблемы.

## 2. Целевое железо

MacBook (Retina, 12-inch, A1534) — **явная цель: MacBook10,1 (Mid 2017)**,
зафиксировано в `docs/HARDWARE.md` и `docs/DECISIONS.md`
(старое консервативное предположение «MacBook9,1 как средний случай»
больше не действует). Fanless Core M, LPDDR3, распаянный SSD,
один порт USB-C (данные+питание+видео), Force Touch трекпад, экран 2304×1440.
Аудио-кодек, SPI-контроллер и Wi-Fi чип (BCM43602) — ревизионно-зависимы.

**Известный риск (зафиксируй как есть, не пытайся замалчивать):**
встроенные клавиатура и трекпад работают через нестандартный протокол
`applespi`, и на ядрах 6.15+ по состоянию на середину 2025 у как минимум
одного пользователя с идентичной моделью это не заработало вообще
(таймауты SPI, драйвер из AUR не собирался без ручных патчей). Значит:

- Внешняя USB-C клавиатура/мышь (через хаб) — не "план Б", а обязательная
  часть bring-up процесса с первого дня.
- Родной ввод (клавиатура/трекпад) — отдельная, явно помеченная как
  best-effort задача со своим планом отката: не более 3 существенно разных
  стратегий (разные версии ядра/патчей), после чего зафиксировать как
  «не поддерживается на этой ревизии» и идти дальше.

### 2.1. Важнейшее ограничение: железа физически ЕЩЁ НЕТ

Целевой MacBook10,1 физически ещё не доступен. Поэтому:

ВСЁ, что можно реализовать, интегрировать, скомпилировать, протестировать
и проверить статически без hardware — ДЕЛАТЬ СЕЙЧАС. Не откладывать
разработку только потому, что hardware ещё не подключено.

Разделяй PRE-HARDWARE IMPLEMENTATION и HARDWARE VALIDATION.

До появления hardware максимально закончить: UI, desktop integration,
applications, backend integration, X11 integration, GTK theme, icons,
dialogs, menu bar, Dock, file manager, search, launching, hotkeys,
settings, notifications, Quick Look, window management, power UI, system
information/monitoring, media/utility applications, packaging, installation,
firstboot integration, documentation, tests, performance architecture.

После появления hardware остаются: реальные display measurements, HiDPI
calibration, Apple keyboard/trackpad, Wi-Fi, audio, NVMe (Apple S3X),
power/suspend-resume/thermal/brightness/battery telemetry, реальные
hardware-баги, финальная калибровка.

Отсутствие hardware — НЕ причина прекращать pre-hardware implementation.
Любой шаг, который нельзя протестировать без реального железа — помечай
в `docs/NEEDS_HARDWARE_TEST.md` и продолжай следующий шаг, не блокируйся.

## 3. Правила приоритета при неоднозначности (без вопросов пользователю)

1. Стабильность и загружаемость системы важнее любой оптимизации.
2. Из двух рабочих вариантов — выбирай тот, что даёт меньшее
   энергопотребление/меньше нагрева (железо fanless, троттлинг — главный враг).
3. Из визуальных решений — выбирай то, что ближе всего к реальному
   Mac OS X 10.9 Mavericks (скеоморфизм: текстуры, тени, "стекло" в Dock,
   Finder-подобный файл-менеджер, кожаные/бумажные текстуры в аналогах
   Calendar/Notes), а не к более поздним плоским macOS. Референсы стиля
   вроде исторических «MacBuntu Mavericks transformation pack» — только как
   референс эстетики, не как код для копирования; переосмысли под Xfce/GTK3.
4. Предпочитай пакеты и патчи, специфично поддерживающие именно
   MacBook10,1 (см. `drivers/README.md`), а не общие «заводится на большинстве Маков».
5. Любой шаг, который нельзя протестировать без реального железа —
   помечай в `docs/NEEDS_HARDWARE_TEST.md` и продолжай следующий шаг.
6. Приоритет работ — раздел 10 (P0 раньше P1, P1 раньше P2; не переходить
   к P2, пока существенные P0/P1 integration problems решаемы без hardware).
7. Reuse-first (раздел 5): существующий зрелый backend важнее собственного кода.
8. Не ломать существующий power baseline ради UI (раздел 7).

## 4. Технологический стек (по умолчанию, менять только с записью причины)

- Базовая система: Arch Linux (контроль состава пакетов, сжатость, AUR).
- Ядро: `linux-zen` как основа (интерактивный отклик на слабом железе)
  либо кастомное урезанное ядро на поздней стадии — сравнение задокументировать.
  Custom kernel — ТОЛЬКО после стабильной работы стандартного (есть с чем
  сравнивать регрессии).
- DE: **Xfce** (не GNOME/KDE) — минимальный оверхед на fanless Core M,
  гибкий GTK-стек для ретема. Альтернатива — только MATE, если Xfce
  объективно не потянет тему.
- Композитор: xfwm4 встроенный, тяжёлые эффекты off, только нужные для вида
  Mavericks (тени окон). Не добавлять тяжёлый compositor только ради эффекта.
- Init/lite systemd services: всё не относящееся к минимальному десктопу —
  по умолчанию off (bluetooth service, cups, avahi и т.п. включаются вручную).
- Браузер: Firefox ESR (current, не пиннить версию) + uBlock Origin;
  sessionstore.interval=60s (беречь SSD).
- Уведомления: xfce4-notifyd (native), без второго daemon.

## 5. Reuse-first + legal

Перед написанием нового backend или большого объёма собственного кода всегда
исследуй: существующие Linux-приложения, GTK-библиотеки, X11 APIs, Xfce
components, GVfs, UDisks2, NetworkManager, BlueZ, PipeWire/PulseAudio-APIs,
UPower, systemd/logind, journald, libnotify, GStreamer, Poppler, image libs,
существующие launchers, window-overview, search/indexing, thumbnailers,
archive managers, password stores, font viewers, media players, screenshot
и notification systems. Проверяй Arch/AUR/open source на подходящий компонент.

Если есть хороший backend — переиспользуй. Если есть хороший Linux UI,
который можно обернуть Mavericks-like frontend — используй его.
Не переписывай зрелый backend только ради эстетики.

Но простое переименование через `.desktop` НЕ считается Mavericks-интеграцией,
если user-facing поведение заметно отличается (см. раздел 9 «НЕ fake completion»).

Legal: open-source переиспользовать активно, но проверять лицензию,
не копировать Apple proprietary code/assets/resources, документировать
происхождение компонентов, сохранять attribution/license notices
(сводка — в `docs/APPS.md`). Цель — функциональная и визуальная имитация
собственными/совместимыми ресурсами, а не копирование proprietary implementation.

## 6. Mavericks UX target (что унифицировать)

Ориентир — именно Mavericks-era UX: визуальная иерархия, toolbar, sidebar,
Finder behavior, menu bar, Dock, application menus, window buttons/chrome,
dialogs, sheets, alerts, context menus, file chooser, save/open dialogs,
search, Quick Look, icons, typography, spacing, gradients/textures,
terminology, shortcuts, selection, double-click, drag-and-drop, launch
behavior, fullscreen/minimize, desktop/Trash/notification behavior.

Глобальная coherence (P0, одна из важнейших задач): нельзя, чтобы Finder
был похож на Mavericks, а Settings — на Linux, file chooser — на GTK default,
context menu — на Xfce, dialog — на другой toolkit. Унифицировать постепенно:
GTK theme, window borders, title bars, toolbar, icons, fonts, spacing, menu,
context menus, dialogs, file chooser, notification style, launchers, Dock,
menu bar, wallpaper, cursor, selection/hover/disabled/focus states, error и
confirmation dialogs. Каждая новая GUI-компонента оценивается как часть
общей visual system.

Menu bar / Dock / window management: top menu bar, application menu,
Apple-like имя приложения слева, стандартные меню, Dock с индикаторами
запущенных, minimize/maximize/fullscreen где уместно, переключение окон,
Mission Control, workspaces, application quit behavior. Не ломать Xfce backend.

Keyboard shortcut architecture: единый глобальный слой (централизованно
меняемый), Mavericks-like conceptual mapping (Command-like modifier где
практично; Spotlight, Launchpad, Mission Control, Screenshot, Quick Look,
переключение приложений/окон, операции Finder). Не ломать обычные Linux
shortcuts. Пользователь позже сможет переназначить конкретные hotkeys.

## 7. Performance / energy + замороженный power baseline

Любая новая компонента должна иметь обоснование runtime cost. Предпочитать:
event-driven, on-demand, one-shot, cached data, low-frequency polling,
существующий системный daemon, kernel counters, D-Bus events. Избегать:
постоянных Python daemons, Electron, Java, heavy web UI, дублирующих daemons,
частого сканирования ФС, частого спавна subprocess, лишних таймеров,
постоянных CPU wakeups. Но НЕ жертвовать существенным UX ради идеологической
минимизации — сначала определить реальную cost; если polling необходим,
оценить frequency и expected cost.

Текущий power baseline — отдельный стабильный слой, НЕ ломать его ради UI.
GUI/application work отделён от power baseline. Если GUI требует изменения
baseline: документировать → отдельный experiment → не смешивать незаметно.

Замороженный baseline (Phase 0.3/0.5, source of truth):

- kernel cmdline: `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`
  (`pcie_port_pm=off` — provisional Apple S3X resume workaround;
  `i915.enable_psr=0` — diagnostic-safe; оба — hardware-validation items,
  а не вечные догмы). Turbo ON, APST/FBC/GuC/THP/VM — defaults.
- TLP only: `CPU_SCALING_GOVERNOR_ON_AC/BAT=powersave`,
  `PCIE_ASPM_ON_AC/BAT=powersave`, `USB_AUTOSUSPEND=1`,
  `RUNTIME_PM_ON_AC/BAT=auto`. CPU_BOOST/PLATFORM_PROFILE/EPP — unset.
- zram: zram-generator, zram-size = RAM/2, zstd. Без disk swap.
- НЕ добавлять без доказательств: thermald, ananicy-cpp,
  `powertop --auto-tune` (BANNED из baseline), random sysctl tuning,
  arbitrary Turbo forcing, APST/GuC/PSR-FBC forcing.
- Замеры каждого «оптимизирующего» изменения до/после (boot time, idle RAM,
  idle power если снимется с железа) — в `docs/BENCHMARKS.md`;
  memory budget — `docs/MEMORY_BUDGET.md`.
- RAPL/package energy НЕ считать автоматически потреблением всего ноутбука;
  документировать различие package energy / CPU-GPU estimate /
  battery discharge rate / whole-system power; корреляцию проверить на железе.

## 8. Документация, тестирование, git-дисциплина

Persistent state живёт в репозитории. Минимум: `docs/APPS.md`
(инвентарь surface + статусы + backend/лицензии), `docs/PROGRESS.md`
(что сделано/дальше/заблокировано — обновлять в конце каждой сессии),
`docs/DECISIONS.md` (любое неочевидное решение + «почему»),
`docs/HARDWARE.md` (MacBook10,1 + ревизионные отличия),
`docs/NEEDS_HARDWARE_TEST.md` (всё hardware-dependent),
`docs/ENVIRONMENT.md` (доступ/root в build-контейнере — читать при sudo-проблемах),
`docs/MEMORY_BUDGET.md` (+ `docs/BENCHMARKS.md`). Если есть более подходящие
документы — использовать существующие. Документировать: что реально работает,
а что mocked/wrapped; hardware-dependent и deferred; почему принято решение;
какие компоненты reused (+лицензии); runtime cost; known limitations.

Каждое существенное изменение — максимально возможный pre-hardware test:
syntax, compile, package build, install into DESTDIR, desktop-file validation,
XML validation, `bash -n`/shellcheck где применимо, py_compile, startup tests,
базовые X11/D-Bus tests где доступны, dependency checks. «Works» только по
компиляции не выдавать.

Git: небольшие логически цельные commits (`feat:`, `fix:`, `perf:`,
`theme:`, `docs:`), но НЕ останавливать всю работу после каждого микрошага
ради отчёта. Перед изменением — `git status`; после — tests, `git diff`,
проверка отсутствия случайных baseline-изменений, commit. Tree после
завершённой итерации — чистый, если нет сознательного WIP.

Остановиться и запросить пользователя ТОЛЬКО если действительно требуется:
физическое hardware, непредоставленный секрет, destructive operation,
технически неразрешимое решение, конфликтующие требования, риск уничтожения
данных, выбор между архитектурами с необратимыми последствиями. Отсутствие
hardware — не повод спрашивать, а повод делать pre-hardware работу.

## 9. НЕ «fake completion» + статусы + app surface audit

Не объявлять IMPLEMENTED только потому, что создан `.desktop`, изменено имя
окна, добавлена иконка, приложение запускается или backend существует.
Примеры НЕ-завершённости: Thunar + иконка ≠ Finder; rofi + поиск ≠ Spotlight;
rofi window mode ≠ Mission Control; galculator + `.desktop` ≠ Mavericks
Calculator; stock GTK dialog ≠ Mavericks dialog. Оценивать user-facing behavior.

Статусы последовательно: RESEARCH REQUIRED → EXISTING SOLUTION FOUND →
BACKEND REUSABLE / UI REUSABLE → PARTIALLY IMPLEMENTED → IMPLEMENTED →
IMPLEMENTED — HARDWARE VALIDATION REQUIRED → VALIDATED; либо DEFERRED / EXCLUDED.

App surface audit для каждой важной программы (вести структурированную
таблицу в `docs/APPS.md`, не переисследовывать закрытое): launch, window
chrome, toolbar, sidebar, content view, navigation, search, context menu,
dialogs, file chooser, keyboard, drag-and-drop, icons, notifications,
интеграция с Finder / Quick Look / Trash, MIME associations, settings,
theme, application menu.

Известный audit-snapshot (НЕ доверять вслепую, перепроверять по репозиторию):
Finder пока скорее Thunar surface, чем настоящий Finder UX; Spotlight
infrastructure есть, но полноценный UX не завершён; Mission Control не является
полноценным overview; часть приложений — пока Mavericks alias поверх stock
Linux UI; Quick Look Space integration неполна. Это известные work items.

## 10. Application / desktop roadmap (постоянная целевая карта)

Не реализовывать всё одним commit — постепенно доводить каждый пункт до части
единой DE. Terminal остаётся нормальным Linux Terminal (замены нет; Console =
Mavericks-like log viewer, НЕ Terminal). Lock: визуальный lock-screen/curtain
допустим, но БЕЗ обязательной account/password infrastructure на этом этапе;
Users/Accounts как реальный account-management — не реализовывать сейчас.

P0 — global desktop coherence; Finder; Spotlight; Mission Control; Launchpad;
Control Center; Notification Center; Quick Look; menu bar / Dock / window
behavior; common dialogs / file chooser / context menus; Settings integration.

P1 — Activity Monitor; System Information; Disk Utility; Screenshot; Preview;
TextEdit; Calculator; Notes; Reminders; Calendar; Music; Photos; Voice Memos;
Console; Keychain Access; Font Book; Digital Color Meter; Stickies;
Dictionary (низкий приоритет); Contacts — НЕ делать на этом этапе.

P2 (research/future, только после P0/P1): AirDrop; Time Machine UI;
Automator/Shortcuts; Grapher; Migration Assistant; App Store; Software Update polish.

EXPLICITLY EXCLUDED: Contacts (текущий этап), TV, Podcasts, Siri, AirPlay,
Chess, Game Center, Printer Discovery как dedicated clone, Image Capture,
Migration Assistant (текущий приоритет), Terminal replacement.
Не делать: TV, Podcasts (раздел Media).

Settings: Mavericks-like интерфейсы для General, Desktop/Screensaver, Dock,
Mission Control, Language/Region, Security/Privacy (где применимо),
Notifications, Displays, Energy/Power, Keyboard, Mouse, Trackpad,
Sound, Network, Bluetooth, Sharing (где полезно). Printers/Scanners — не
приоритет. Особенно важно: Display / Keyboard / Trackpad / Mouse / Sound /
Network / Bluetooth выглядят и ведут себя как единая Settings environment.

### 10.1. Finder (особый приоритет)

Thunar + тема ≠ готовый Finder. Постепенно приближать поведение поверх
зрелого backend (Thunar/GVfs, без переписывания file manager backend;
если upstream-интеграция невозможна — clean external integration, не хаки):
sidebar (Favorites/Devices/locations), folders, selection, icon/list/column-like
views, navigation history (back/forward), path, search, context menus
(New Folder, Get Info, Rename, Move to Trash, Empty Trash, Eject, Open With),
Quick Look (Space где технически возможно), drag-and-drop, previews, hidden
files, bookmarks, removable/network devices, toolbar, status bar, metadata,
keyboard navigation, Command-like shortcuts через глобальный слой.

### 10.2. Spotlight / Launchpad / Mission Control

Spotlight ≠ plocate/rofi автоматически. Нужен coherent experience: global
shortcut, центрированный overlay, search field, fast response, files/apps/
system objects, keyboard navigation, открытие выбранного, sensible ranking,
без лишнего daemon и без Electron. Backend: plocate/индекс/desktop DB/custom
лёгкий индекс; если daemon необходим — сначала оценить energy cost.

Launchpad ≠ просто rofi menu: application discovery, icon grid, pages,
keyboard navigation, search, launch behavior, дешёвые анимации, consistent
icon sizing, Dock integration, global shortcut. Без тяжёлого compositor/
electron только ради эффекта.

Mission Control ≠ «rofi window mode». Отдельный window-overview experience:
global shortcut, все окна одновременно, workspaces, группировка приложений
где практично, click/select, escape закрывает. Исследовать X11/Xfce/AUR
solutions (текущий эксперимент: skippy-xd как E-MC); лёгкий собственный
frontend поверх X11 enumeration — если готового нет. Без постоянно
работающего тяжёлого daemon. Ограничения compositor/hardware документировать.

### 10.3. Control Center / Notification Center

Control Center coherent с системой: Wi-Fi, Bluetooth, sound, brightness,
battery, power, display controls, network state, вход в notifications/settings.
Backend: D-Bus / NetworkManager / BlueZ / PipeWire / UPower / sysfs / xfconf.
Events/signals вместо polling.

Notification Center: единая архитектура (libnotify, xfce4-notifyd — не плодить
второй daemon), app + system notifications, history, правая панель в стиле
Mavericks, close/dismiss, keyboard behavior.

### 10.4. Quick Look / Preview

Лёгкий preview pipeline: images, PDF, text, common documents, audio/video
metadata. Backend: thumbnailer / pixbuf / Poppler / GStreamer / media libs.
Настоящая Space-интеграция, если архитектура позволяет; иначе clean external
integration (текущее: custom `mv-quicklook` single-shot + Thunar actions).

### 10.5. Activity Monitor (+ HUD) / System Info / Disk Utility

Activity Monitor: coherent Mavericks UI минимум CPU/Memory/Energy/Disk/Network
на дешёвых источниках (`/proc`, `/sys`, kernel counters). Refresh только пока
окно открыто. Верхний Energy/Thermal HUD: минимальный footprint, лучше no
resident process — короткие one-shot reads, event-driven или редкий polling,
никаких Python daemons/тяжёлых GUI (текущий `mv-hud` — C one-shot — держать/
улучшать только при измеримом преимуществе).

About / System Report: `/proc`, `/sys`, DMI, PCI, USB, X11 display info,
network, kernel, storage; статику кэшировать, polling loops не держать.

Disk Utility: frontend Mavericks-like поверх UDisks2 / gnome-disk-utility
(disks, partitions, FS, mount/unmount/eject, SMART где возможно, formatting,
permissions, removable). Особое внимание — Apple S3X NVMe: до hardware
подготовить UI/backend/errors/integration, на hardware — validate.

### 10.6. Остальные приложения (интеграционный минимум)

Каждое — через общую систему: icons, desktop entries, naming, MIME, launch,
settings, notifications, menus, dialogs, file chooser, theme, keyboard
(раздел 9). Текущий инвентарь и переиспользованные backend'ы — `docs/APPS.md`
(Thunar/GVfs, rofi, plocate, UDisks2, xarchiver, mousepad, galculator,
orage/libical, gthumb, geary, lollypop/GStreamer, seahorse/libsecret, gcolor3,
xfce4-notes-plugin, trash-cli, genmon, flameshot, ffmpeg/thumbnailer,
evince/poppler, gnome-font-viewer, xfce4-screenshooter, xfce4-screensaver,
xfce4-notifyd, NM/BlueZ/PipeWire/UPower/logind/journald; custom `mavericks-apps`:
mv-settings/about/activity/console/control/power-ui/shot/quicklook/notes/
reminders/voice/hud + 23 .desktop + rofi themes + Thunar actions + hotkey layer
+ reminders timer + firstboot wiring).

## 11. Фазы работы (hardware-bring-up трек; вести как чек-лист в `docs/PROGRESS.md`)

### Фаза 0 — База и идентификация железа
- Точная ревизия зафиксирована: MacBook10,1 (проверить `dmidecode` при первой
  загрузке live-образа на реальном железе).
- pacstrap минимальной базовой системы, загружаемость через systemd-boot
  (UEFI; rEFInd — fallback), без Mac-специфичных модулей — просто грузится.
- Acceptance: грузится до консоли на реальном железе (или чёткий отчёт
  с логами в NEEDS_HARDWARE_TEST.md). QEMU+OVMF smoke-test — пройден.

### Фаза 1 — Аппаратная поддержка (подготовлено, НЕ проверено)
- Wi-Fi (broadcom-wl-dkms + brcmfmac fallback — оба профиля готовы).
- Аудио (Cirrus patch).
- Bluetooth.
- Внешний ввод через USB-C — основной интерфейс этой фазы (стандартный HID).
- Встроенный ввод (applespi) — best effort, лимит 3 стратегии (раздел 2).
- Питание: TLP baseline из раздела 7 (thermald/ananicy — удалены, см. DECISIONS).

### Фаза 2 — Сверхоптимизация (подготовлено, НЕ проверено)
- zram вместо disk swap (беречь распаянный SSD).
- Урезание systemd unit'ов, цель < 10 сек до DM (`systemd-analyze blame`).
- journald volatile / мягкий rate-limit, отключение лишних таймеров.
- Custom kernel — только после стабильного стандартного.
- Каждое изменение — с замером до/после в `docs/BENCHMARKS.md`.

### Фаза 3 — Визуальный слой "Mavericks" (подготовлено, НЕ проверено)
- GTK3 скеоморфизм, иконки pre-flat эры, Dock (plank, рефлексия/зум),
  курсор macOS, верхняя панель-менюбар (функциональное глобальное меню —
  только если Xfce-плагин потянет производительно), обои/иконки в духе
  Mavericks без Apple-файлов (только переосмысленные аналоги).
- Acceptance: скриншот узнаваем как «почти Mavericks» неспециалистом.

### Фаза 4 — Сборка ISO и smoke-test
- `mkarchiso` из готового профиля.
- Smoke-test в QEMU+OVMF (UEFI): ISO грузится, DE стартует, тема применяется.
  ВНИМАНИЕ: QEMU НЕ тестирует applespi/Broadcom/Cirrus — чисто софтовый тест.
- Только после успешного QEMU-теста — ISO готов к записи на реальное железо.

### Фаза 5 — Итерации по реальному железу
- Пользователь пришлёт: грузится/не грузится, скриншот, `journalctl -b`.
- Диагностировать по этим данным без уточняющих вопросов (правило раздела 0).

## 12. Final condition (когда цель достигнута)

Не тогда, когда есть набор Mavericks-themed applications, а когда:
desktop выглядит как coherent Mavericks environment; Finder ощущается как
Finder; Spotlight — как Spotlight; Mission Control — как Mission Control;
Launchpad — как Launchpad; Settings — как System Preferences; Control Center /
Notification Center integrated; Quick Look integrated; приложения в coherent
visual language; dialogs/file chooser/context menus не выдают stock Linux UI
без нужды; keyboard behavior coherent; Dock/menu bar coherent; system utilities
integrated; backend Linux-native; runtime/energy overhead разумен; power
baseline сохранён; всё возможное сделано до hardware; hardware-dependent items
явно перечислены в NEEDS_HARDWARE_TEST.md.

---

## 13. ARCHITECTURAL MODEL: APPLICATION-BASED COMPLETION (MANDATORY)

> This section is binding. It overrides any prior "ready for hardware" language.
> Hardware bring-up is a validation phase, NOT a development stop condition.

### 13.1 PROJECT COMPLETION MUST BE APPLICATION-BASED

The project status is NEVER "ready for hardware bring-up" if any application or desktop surface has status:

* PARTIALLY IMPLEMENTED
* EXPERIMENT READY
* NOT STARTED
* IN PROGRESS
* AUDIT REQUIRED
* DEFERRED WITHOUT EXPLICIT REASON

Hardware bring-up is a separate validation phase. Hardware availability does NOT terminate pre-hardware implementation.

### 13.2 CANONICAL APPLICATION INVENTORY (46 objectives)

This list is the mandatory project scope. It does not change between sessions.

**P0 — CORE MACOS/MAVERICKS DESKTOP (25)**

1. Finder
2. Spotlight
3. System Settings
4. Control Center
5. Notification Center
6. Quick Look
7. Preview
8. Screenshot
9. Activity Monitor
10. System Information
11. Disk Utility
12. Launchpad
13. Mission Control
14. Power / Shutdown / Restart UI
15. Trash
16. Archive Utility
17. Menu Bar
18. Dock
19. Application Menu
20. Global Dialogs
21. File Chooser
22. Context Menus
23. Keyboard Shortcut Layer
24. Desktop / Wallpaper / Session Behavior
25. Window Management

**P1 — APPLICATIONS (14)**

26. TextEdit
27. Notes
28. Reminders
29. Calendar
30. Music
31. Photos
32. Voice Memos
33. Console
34. Keychain Access
35. Font Book
36. Digital Color Meter
37. Stickies
38. Calculator
39. Dictionary

**P2 — FUTURE / ADVANCED (7)**

40. AirDrop
41. Time Machine UI
42. Automator / Shortcuts
43. Grapher
44. Migration Assistant
45. App Store
46. Software Update polish

**EXPLICITLY EXCLUDED**

Contacts, TV, Podcasts, Siri, AirPlay, Chess, Game Center, Dedicated Printer Discovery clone, Image Capture, Terminal replacement, Account-management infrastructure, Mandatory account/password infrastructure for the visual lock-screen curtain.

Do not silently add excluded applications back into scope.

### 13.3 UNIVERSAL MAVERICKS APPLICATION DEFINITION OF DONE

Every application in the canonical inventory must be evaluated against the same Definition of Done.

An application is NOT COMPLETE merely because:

* a binary exists;
* a Python script exists;
* a `.desktop` file exists;
* a package builds;
* an application launches;
* a stock Linux application is renamed;
* a wrapper launches a stock application;
* QEMU boots;
* the ISO builds;
* documentation says IMPLEMENTED.

For each application, verify:

**A. FUNCTIONAL BACKEND** — The application must actually perform its intended operation.

**B. USER-FACING UI** — It must have an intentional Mavericks-like user interface rather than exposing generic Linux UI wherever avoidable.

**C. VISUAL DESIGN** — Use the common project visual language:
* Mavericks-era macOS visual hierarchy;
* restrained grey/translucent surfaces where appropriate;
* consistent toolbar proportions;
* consistent typography;
* consistent spacing;
* consistent icons;
* consistent controls;
* consistent selection states;
* consistent dialogs;
* consistent hover/focus/pressed states;
* consistent window geometry;
* consistent light/dark assumptions appropriate to Mavericks;
* consistent menu structure.

Do not create each application as an unrelated Linux GUI.

**D. BEHAVIOR** — Check:
* keyboard navigation;
* keyboard shortcuts;
* focus;
* Escape behavior;
* Enter/default actions;
* cancellation;
* selection;
* double-click;
* context menus;
* drag-and-drop where applicable;
* error handling;
* empty states;
* unavailable-resource states.

**E. DESKTOP INTEGRATION** — Check:
* Dock;
* application menu;
* menu bar;
* global shortcuts;
* notifications;
* MIME associations;
* file associations;
* dialogs;
* file chooser;
* context menus;
* desktop/session behavior.

**F. MAVERICKS COHERENCE** — Opening several applications must make them look like parts of one operating system.
Do not accept: "backend works, but the UI is generic Linux" as COMPLETE.

**G. RESOURCE BEHAVIOR** — Review:
* startup cost;
* idle processes;
* persistent services;
* memory;
* CPU;
* wakeups;
* battery implications.

Avoid Electron/Java/heavy persistent daemons unless technically justified.

**H. PACKAGING** — Verify:
* package;
* dependencies;
* install;
* `.desktop`;
* icons;
* configuration;
* ISO inclusion where appropriate;
* reproducibility.

**I. TESTING** — Provide automated or deterministic tests wherever possible.

**J. HARDWARE CLASSIFICATION** — Every unresolved item must be explicitly classified:
`PRE-HARDWARE IMPLEMENTABLE` or `HARDWARE VALIDATION REQUIRED` or `HARDWARE BLOCKED`
Never use "hardware required" to hide unfinished software work.

### 13.4 APPLICATION STATUS MACHINE

For every application maintain one canonical status:

* NOT_STARTED
* AUDIT_REQUIRED
* IN_PROGRESS
* PARTIALLY_IMPLEMENTED
* IMPLEMENTED_HARDWARE_VALIDATION_REQUIRED
* VERIFIED
* HARDWARE_BLOCKED
* DEFERRED
* EXCLUDED

`COMPLETE` must NOT be used as a vague global label.

An application may be considered fully complete only when:
`VERIFIED` or `IMPLEMENTED_HARDWARE_VALIDATION_REQUIRED` when every pre-hardware requirement is actually implemented and only physical validation remains.

`PARTIALLY_IMPLEMENTED` means WORK REMAINS.
`EXPERIMENT READY` means WORK REMAINS.

### 13.5 APPLICATION CHECKLIST (MACHINE-READABLE MATRIX)

Maintain a structured application matrix in the repository.

Minimum fields:
Application, Priority, Status, Backend, Frontend, Visual Integration, Keyboard Integration, Desktop Integration, File/MIME Integration, Dialogs, Error Handling, Performance Review, Automated Tests, Hardware Dependency, Known Gaps, Next Executable Action.

Every time an application is touched, update this matrix. The matrix is authoritative for project progress. Documentation must reflect actual implementation, not intentions.

### 13.6 SPECIFIC HIGH-LEVEL COMPLETION REQUIREMENTS

**FINDER** — Do not consider Finder complete until all feasible pre-hardware items have been addressed:
sidebar, favorites, devices, navigation, toolbar, view modes, icon/list/column behavior where feasible, search, context menus, Get Info, Open With, Rename, Move to Trash, Empty Trash, Eject, Quick Look, keyboard navigation, drag-and-drop, MIME associations, dialogs, file chooser integration, removable media behavior, bookmarks, status information, Mavericks visual integration.
If Thunar has an architectural limitation, investigate feasible surrounding implementation before accepting the limitation. "Thunar limitation" is not automatically a completion criterion.

**SPOTLIGHT** — Require: global shortcut, dedicated search UI, application search, file search, result categories, ranking, keyboard navigation, launch/open, visual integration, indexing lifecycle, reasonable performance.
rofi + plocate is a backend strategy, not automatically a completed Spotlight experience.

**LAUNCHPAD** — Require: application discovery, icon grid, keyboard navigation, launch, search, pages where feasible, grouping/folders where feasible, close behavior, Dock/global shortcut integration, Mavericks visual behavior.
A generic `rofi -show drun` is not automatically Launchpad.

**MISSION CONTROL** — Require actual window overview behavior. A rofi window list is not automatically Mission Control. Investigate and implement the best lightweight X11/Xfce-compatible approach available. If `skippy-xd` is suitable, integrate it rather than merely documenting an experiment.

**CONTROL CENTER** — Require actual user-facing controls: network, audio, Bluetooth, display/brightness, power, relevant system toggles. Do not count backend availability as UI completion.

**NOTIFICATION CENTER** — Require: notification surface, notification history where feasible, consistent visual style, interaction, keyboard/global integration.

**QUICK LOOK** — Require: Space behavior where feasible, preview selection, image/document/text/media preview, correct window lifecycle, integration with Finder, keyboard behavior. If X11/Thunar lacks a native hook, investigate alternate implementation rather than simply documenting the limitation.

**SYSTEM SETTINGS** — Require a coherent settings application rather than a collection of unrelated stock dialogs.

**ACTIVITY MONITOR** — Require: process list, CPU, memory, relevant system metrics, refresh, process interaction where safe, Mavericks-like presentation.

**SYSTEM INFORMATION** — Require a coherent system-information surface rather than raw command output.

**DISK UTILITY** — Require a usable storage/device interface over Linux storage backends.

**CONSOLE** — This means the macOS-style log viewer. It does NOT mean Terminal.

**PREVIEW** — Require actual document/image viewing and appropriate file integration.

**TEXTEDIT / NOTES / REMINDERS / CALENDAR / MUSIC / PHOTOS / VOICE MEMOS** — Each must be independently audited. Do not treat "a Linux application with a suitable name" as sufficient. A mature Linux backend may be reused, but the user-facing integration must belong to the Mavericks-like desktop.

**KEYCHAIN ACCESS** — Use mature Linux secret-storage backend where appropriate, but provide an appropriate user-facing keychain management surface.

**FONT BOOK** — Provide actual font browsing/preview/management functionality.

**DIGITAL COLOR METER** — Provide actual screen color sampling behavior where technically feasible under X11.

**STICKIES** — Provide actual sticky-note behavior and desktop integration.

**CALCULATOR** — Provide calculator behavior with appropriate Mavericks-like presentation.

### 13.7 REUSE-FIRST DOES NOT MEAN WRAPPER-FIRST

Continue using mature Linux backends. However: "Reuse backend" does NOT mean "rename an existing Linux application and declare the Mavericks application complete."
Correct architecture: Mavericks-like frontend → mature Linux backend where appropriate. Do not rewrite mature backend functionality unnecessarily.

### 13.8 AUTONOMOUS EXECUTION

After auditing the application matrix: DO NOT STOP.
Select the highest-priority application with unfinished executable work.
Implement it. Test it. Update the matrix. Commit. Continue with the next unfinished application.
A commit is a checkpoint, NOT a stopping condition. An audit is a checkpoint, NOT a stopping condition. A clean tree is NOT a stopping condition. A documentation update is NOT a stopping condition. A "next logical step" is NOT a stopping condition. "Ready for hardware" is NOT a stopping condition if pre-hardware work remains.

### 13.9 CURRENT PROJECT MUST BE RE-AUDITED

Immediately audit all applications in the canonical inventory. Do not trust current `APPS.md`, `PROGRESS.md`, `HANDOFF.md`, or previous agent claims without inspecting the implementation.

The latest audit already proves that at least:
Finder = PARTIALLY IMPLEMENTED
Spotlight = PARTIALLY IMPLEMENTED
Launchpad = PARTIALLY IMPLEMENTED
Mission Control = EXPERIMENT READY

Therefore the project is NOT complete. These four objectives alone require further autonomous work. Do not merely document their gaps again. Implement the feasible gaps. Then continue through the remaining applications.

### 13.10 HARDWARE IS A VALIDATION PHASE, NOT A DEVELOPMENT STOP

The eventual MacBook10,1 will be used for: applespi, BCM43602 Wi-Fi, Bluetooth, Cirrus audio, S3X NVMe behavior, USB-C/DP, brightness, thermal behavior, power measurements, actual 2304×1440 display behavior.
Until hardware exists, continue implementing every software/UI/integration component that can be developed without it.

The final pre-hardware state should therefore be:
ALL SOFTWARE OBJECTIVES IMPLEMENTED + ALL KNOWN HARDWARE-DEPENDENT ITEMS CLEARLY MARKED + AUTOMATED TESTS PASSING + ISO/QEMU REGRESSION PASSING.

### 13.11 FINAL PROJECT COMPLETION CONDITION

Do NOT declare the project ready for final hardware validation until:
* every in-scope application has been audited;
* every feasible pre-hardware gap has been implemented;
* every application has reached the appropriate terminal status;
* no `PARTIALLY_IMPLEMENTED` application remains where work is executable;
* no `EXPERIMENT READY` item remains where integration is feasible;
* the common Mavericks visual system is coherent;
* automated tests pass;
* ISO builds;
* QEMU smoke/regression tests pass;
* documentation matches reality.

Only then move to hardware validation.

### 13.12 IMMEDIATE ACTION

After installing this specification:
1. update `AGENTS.md`;
2. create/update the canonical application matrix;
3. audit all 46 in-scope objectives;
4. classify every objective;
5. select the highest-priority unfinished objective;
6. IMPLEMENT IT;
7. TEST IT;
8. UPDATE STATE;
9. COMMIT;
10. CONTINUE.

Do not return a "final summary" merely because the audit is complete. The audit is the beginning of the implementation pass, not the end.

---

## 14. ORCHESTRATION ARCHITECTURE: ORCHESTRATOR + BUILD (MANDATORY)

> Two user roles only: **Build** (the built-in full agent: files, bash,
> research, planning, implementation) and **Orchestrator** (manages work,
> never implements). Orchestrator delegates ALL work to the worker pool
> (`build` + hidden `build-b`/`build-c` fallbacks) via the Task tool and
> manages session continuation/reuse/retire/migrate. A Task completion,
> commit, validation pass, audit, or phase completion is a checkpoint,
> not a stop condition.
>
> Orchestrator is defined in `.opencode/agents/orchestrator.md` (also
> exposed globally, see 14.6) and restricted by OpenCode permission
> configuration, not only by prompt text. Build is the stock built-in
> agent, untouched. Fallback workers are mode=subagent + hidden (invisible
> in the Tab picker and @-menu, invokable only via Task). Extra roles
> (custom builder/scout/planner; built-in plan/explore/general) are
> removed/disabled so the picker shows only Build + Orchestrator.

### 14.1 Role capabilities

| Role | Mode | Edit/Write | Bash | Task (invoke) | Purpose |
|---|---|---|---|---|---|
| Orchestrator | primary | DENY | DENY except `git status/log/diff` | `build`, `build-b`, `build-c` | read state, choose objective, delegate, verify, continue loop |
| Build | primary (built-in) | ALLOW | ALLOW | ALLOW | research, plan, implement, test, docs, commit, short result |
| build-b / build-c | subagent (hidden) | ALLOW | ALLOW | DENY (no nesting) | fallback workers, other chain pins, runtime rotation |

Residual limitation (documented, not hidden): OpenCode permissions cannot
deny `read`, and Orchestrator keeps read/search/web/skill tools — that is
intended (state inspection is its job). Edit/write/bash-implementation are
denied at tool level, so self-implementation is technically blocked, not
just prompt-discouraged.

### 14.2 Orchestration loop

Trigger words "приступай / продолжай / делай дальше" mean: work the loop
until a genuine blocker (14.3) or project-level completion (13.11):

```
READ state (AGENTS.md, PROGRESS.md, APPS.md, DECISIONS.md, NEEDS_HARDWARE_TEST.md, git)
→ SELECT highest-priority unfinished executable objective (P0 → P1 → P2)
→ TASK LIFECYCLE (stuck-gate → single-flight → resume-via-task_id OR fresh OR migrate)
→ VERIFY result (git status/diff/log; state files) + register returned task_id
→ IMMEDIATELY launch next Task
→ ... repeat ...
```

TASK LIFECYCLE (binding, full text in `.opencode/agents/orchestrator.md`):
ENV PRE-CHECK (`git status` + `version` must both succeed; else
PROJECT-NOT-LOADED/STALE-AGENT = stop, no improvising) →
protocol check `version` (need v12) →
REBOOT RULE (sessions PERSIST across restart — verified vs 1.18.32 SDK:
`GET /session/{id}` is authoritative; status absence = idle, never gone;
fresh ONLY on verified 404) →
`preflight` (offline: skip cooldown models BEFORE Task) +
watchdog-ensure (daemon alive via HEARTBEAT, else start it; foreground Tasks
without a watchdog have no runtime failover) +
`stuck --threshold 600` gate before EVERY Task (exit 2 = abort + migrate, no fresh Task) →
single-flight (max ONE active worker Task per objective; `decide` WAIT = no new
Task) → Continue = `find-objective <oid>` → LIVE → Task SAME `task_id`
(same worker, or migrated worker after MODEL_* failure — worker change NEVER
means a new session; re-issuing the initial prompt as a fresh Task and
checker-Tasks are FORBIDDEN) →
STUCK/dead-model = abort (`abort <id>`) + `migrate --delay <sec>` → SAME `task_id`
on printed `subagent_type` → BLOCKED-TASK (a foreground Task blocks the
orchestrator for the whole provider retry — verified vs 1.18.32 task.ts.
Two exits: BACKGROUND-FIRST (Task background=true when the server flag is
on: call returns at once, gates run between turns) or WATCHDOG
(`task-watchdog.py --daemon --all`: independent REST loop that aborts
>600s provider-retry waits, records cooldowns + lastAbort; the blocked Task
then fails fast and the orchestrator migrates the SAME session). Abort-wakeup
+ fresh lastAbort = confirmed STUCK, migrate at once, never re-wait) → fresh Task ONLY on objective change,
verified SESSION_DOES_NOT_EXIST, CONTEXT_EXHAUSTED, SESSION_ERROR, or
completed/retired prior (minimal transfer, same oid). NEVER end a turn with
an unprocessed Task outcome. Failure taxonomy (`classify-error`: MODEL_* incl.
FREE_USAGE_EXHAUSTED(18) = same-session failover, NETWORK = same session no
cooldown, PROJECT = fix code no rotation, SESSION/CONTEXT = replacement).
Cooldown memory (`health`/`mark-dead`/`mark-alive`, 3h default, provider delay
wins) tracks dead models; runtime rotation needs no restart.

"Next objective is X" = START X now. "Ready to continue" = continue now.
Sections 0.1 and 13.8 apply to the Orchestrator loop one level up: it is
the Orchestrator, not the Build worker, that must not stop between objectives.

### 14.3 Blocker policy

STOP only for: physical hardware validation required; missing external
resource/credential; required user choice; fundamental environment
limitation. Code/test/build failure, unclear detail, unknown backend,
research or architecture need = delegate to `build` (as a research,
decomposition, or implementation Task), NOT stop.
Single-model quota/rate-limit exhaustion is NOT a blocker — follow
MODEL FALLBACK in `.opencode/agents/orchestrator.md` (chain:
`.opencode/model-fallback.json`, resolver: `scripts/session-reuse.py models`,
memory: `scripts/session-reuse.py health`). Rotation is a runtime
`subagent_type` switch (`build` → `build-b` → `build-c`), no restart, no paste.
A sub-agent stuck in provider retry/unavailable backoff longer than 600s
(10 min, e.g. the observed 8800s "agent unavailable" hang) is NOT waited
out — it is a STUCK-TASK failover: keep the logical session, record the dead
model, and continue the SAME `task_id` on the next healthy worker via
`scripts/session-reuse.py stuck` (detect)
→ `scripts/session-reuse.py migrate <id> --objective <O> --delay <sec>`
(cooldown record + same-session Task block). The dead model cools down
for the observed delay (or 3h default when the provider gave no time) and is
retried automatically after expiry. Full procedure: STUCK-TASK FAILOVER in
`.opencode/agents/orchestrator.md`. `migrate` printing `next-worker: NONE`
is the only genuine stop-and-wait in this path.

### 14.4 Manual role use (preserved)

User may open either role directly: Orchestrator for "приступай" loops,
Build for a concrete task. Orchestrator restrictions do not affect manual
Build sessions. Definition of Done per objective: sections 13.3/13.6.

### 14.5 Sub-agent session reuse (mandatory optimization)

Do NOT create a new Task session per micro-iteration while a live
session still holds useful context. Registry:
`.opencode/sessions/registry.json`; helper: `scripts/session-reuse.py`
(uses only real OpenCode 1.18.x mechanisms: `POST /session {parentID}`,
`GET /session/status|/:id/children|/:id/message`, per-message
`tokens.input` vs `Model.limit.context`, `DELETE /session/:id`,
plugin `event` bus).

Per session track: session ID, agent role (`build`), objective, task, model,
context verdict, last result, reusable/retired state (transcripts stay
in the runtime, never in the registry). After each result: update
registry → `decide` → RESUME same session (same objective +
coherent + >50% context remaining) or NEW session otherwise. Objective
boundary: Calendar → Calendar refinement = SAME session;
Calendar → Disk Utility = NEW session. RETIRE at ≤50% remaining (delete
after the result is processed); never resume on context pressure, error
state, or objective change. A Build answer is NOT the end of that
Build session — verify against DoD and continue the same session when work
of the same objective remains.

### 14.5.1 RESUME-FIRST discipline (mandatory, fixes "empty result text ≠ no work")

The Orchestrator sees ONLY the Task result string; it CANNOT trust that
channel for session state. Evidence: cancelled/failed sessions accumulated
~45k and ~100k tokens of real reasoning (visible in session chats), yet
the Orchestrator concluded "zero output, nothing to resume" and re-issued
fresh sessions, wasting ~100k tokens of redo.

**Enforced rules (query live metadata BEFORE deciding):**

1. **After ANY non-clean Task end** (cancelled, timeout, error, or even
   clean but short result text): run `scripts/session-reuse.py status`
   AND `scripts/session-reuse.py context <id>` for that session id
   BEFORE deciding resume vs new.

2. **Same objective + tokens show real progress + no error-state**
   → RESUME via `task_id` with "continue" (same worker, or migrated worker
   after a MODEL_* failure — worker change NEVER means a new session),
   NEVER re-issue fresh.
   `decide` subcommand automates this verdict (worker difference no longer
   forces NEW).

3. **New session ONLY on:** objective change, RETIRE verdict (≤50%
   context remaining), verified-empty session (status shows no
   assistant messages), verified SESSION_UNAVAILABLE (dead id — fresh with
   minimal transfer, same oid), CONTEXT_EXHAUSTED / SESSION_ERROR, or
   unrecoverable error state. Unreachable status is UNKNOWN/WAIT, never NEW.

4. **NEVER infer session emptiness from result text alone.** Result
   channel ≠ session state. A "Task cancelled" message with empty
   output may hide 100k tokens of reasoning in the live session.

**Cheatsheet:**
```
scripts/session-reuse.py status                    # all sessions live state
scripts/session-reuse.py context <session-id>      # used_input, limit, REUSABLE/RETIRE
scripts/session-reuse.py decide <id> --objective <O> --agent build  # RESUME or NEW
scripts/session-reuse.py register <id> --agent build --objective <O> --task "<T>"  # track new
scripts/session-reuse.py stuck --threshold 600     # STUCK watchdog (>600s retry = migrate, exit 2)
scripts/session-reuse.py migrate <id> --objective <O> --delay <sec>  # same-session migrate: SAME task_id on next-worker
scripts/session-reuse.py find-objective <oid>          # resume-first lookup: oid -> LIVE session + Task block
scripts/session-reuse.py health                    # cooldown memory (dead models + retry-in)
scripts/session-reuse.py mark-alive <model>        # clear cooldown after good result
scripts/session-reuse.py version                   # need orchestrator-protocol: 12 (else STALE-AGENT)
scripts/session-reuse.py exists <id>               # SESSION_EXISTS_IDLE/BUSY/RETRYING vs DOES_NOT_EXIST
scripts/session-reuse.py abort <id>                # cancel blocked attempt, history survives
scripts/session-reuse.py preflight                 # offline: skip cooldown models BEFORE Task
python3 scripts/task-watchdog.py --ensure --all    # self-maintaining daemon (no env, no &, returns at once)
# watchdog liveness: read tail of .opencode/sessions/watchdog.log (HEARTBEAT)
# server endpoint auto-discovery: env OPENCODE_* -> live `opencode serve` ps -> 4096 (no manual port lookup, ever)
```

### 14.6 Agent visibility (why global symlinks exist)

OpenCode 1.18.x resolves project agents (`.opencode/agents/`) from the
**server working directory**, not per session directory (proven: server
with cwd=`~` lists only built-ins; same binary with cwd=repo lists all
customs; no hot-reload — a (re)started server is required). The desktop
app attaches to a long-lived server whose cwd is usually NOT the repo,
so the project-only Orchestrator never reaches its picker. Therefore
`orchestrator.md` is additionally exposed globally via symlink
`~/.config/opencode/agents/orchestrator.md → .opencode/agents/` (single
source of truth stays in the repo; same copy exists Windows-side at
`%USERPROFILE%/.config/opencode/agents/` for Windows-spawned servers).
After changing the agent file: restart `opencode serve` / the desktop
app (or start a new server) — running servers do NOT re-read agents.
Machine equivalent of "visible in UI": fresh `GET /agent` (or
`agent list` outside the repo) must list `orchestrator|primary`.

### 14.7 Workers never delegate (no nested sub-agents)

`agent.build*.permission.task` = deny-all in project `opencode.jsonc` (build,
build-b, build-c), so the Task tool offers a worker zero invokable agents
(not even `orchestrator` — this also kills the worker→orchestrator
self-invoke). The stock Build role is untouched (no custom role file; hidden
fallback workers never enter the picker, which still shows only
Build + Orchestrator). `subagent_depth` stays default:
orchestrator(primary)→worker is the single allowed level. Prompts state it
too, but enforcement is the permission, not discipline.
