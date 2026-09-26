# HANDOFF.md — Сводка состояния (для чтения за 1 минуту)

**Дата:** 2026-09-26 (обновлено: Forensic audit + P0 gap fixes, Phase 0.19)
**Готовность к железу:** Phase 0.19 — Forensic audit complete, P0 gaps fixed pre-hardware

> Phase 0.5 — действующий baseline (source of truth: раздел 7 AGENTS.md,
> `docs/DECISIONS.md` «Phase 0.3 baseline»). Всё ниже, что противоречит
> старым записям про thermald/ananicy/Epiphany — считать устаревшим.

---

## ✅ ЧТО ГОТОВО (полностью, ждёт только физической проверки)

### Phase 0 — Базовая система
- ISO собирается: `mavericks-linux-2026.09.25-x86_64.iso` (2.2 GB)
- Загружается в QEMU+OVMF (UEFI) → systemd-boot меню → linux kernel → archiso hook находит ISO по label MAVERICKS → airootfs монтируется → systemd стартует
- **Ядро:** linux-zen (основное) + linux (для live boot с archiso hooks)
- **Загрузчик:** systemd-boot (UEFI only), таймаут 15с, дефолт: Mavericks Linux
- **ФС установленной системы:** btrfs с субволюмами (@, @home, @var_log, @snapshots), compression=zstd
- **Swap:** zram-generator (zram0 = RAM/2, zstd)
- **Initramfs:** mkinitcpio, hooks: base udev autodetect microcode modconf kms keyboard keymap block filesystems fsck; MODULES=(applespi spi_pxa2xx_platform intel_lpss_pci intel_lpss_acpi)

### Phase 1 — Железо (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
Все драйверы упакованы в профили/хуки, ждут решения по HARDWARE_DECISION_TREE.md:
- **Wi-Fi:** broadcom-wl-dkms (AUR) — приоритет для MacBook10,1; brcmfmac fallback — оба в modprobe.d
- **Аудио:** PKGBUILD macbook12-audio-driver (github.com/leifliddy/macbook12-audio-driver) готов в `packages/macbook12-audio-driver/`
- **Bluetooth:** macbook12-bluetooth-driver (AUR) + in-kernel btusb fallback
- **applespi (клавиатура/трекпад):** 3 стратегии документированы в HARDWARE_DECISION_TREE.md с лимитом попыток
- **Питание:** TLP ONLY (powersave governor, ASPM powersave, USB autosuspend,
  RUNTIME_PM auto). thermald и ananicy-cpp УДАЛЕНЫ (см. DECISIONS.md).
- **Kernel cmdline:** `quiet loglevel=3 pcie_port_pm=off i915.enable_psr=0`
  (Turbo ON, APST/FBC/GuC/THP/VM — defaults; `powertop --auto-tune` BANNED).

### Phase 2 — Оптимизация (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- zram, ananicy-cpp, урезанные systemd units, journald volatile — всё в ISO

### Phase 3 — Визуал (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- GTK3 тема Mavericks (скеоморфизм: текстуры, тени, стекло, градиенты)
- Иконки pre-flat стиль
- Dock: plank с рефлексией/зумом
- Панель: xfce4-panel как menu bar
- Thunar как Finder (боковая панель, Mavericks-иконки папок, GVfs trash,
  uca.xml: Quick Look / Put Back / Compress)
- xfce4-settings как System Preferences (mv-settings launcher)
- Уведомления: xfce4-notifyd ONLY (dunst удалён из ISO)
- Браузер: Firefox ESR + uBlock Origin (Epiphany НЕ в ISO;
  epiphany-mavericks-theme — DEFERRED, собирается только с `--all`)

---

## ❌ ЧТО ТРЕБУЕТ РЕАЛЬНОГО ЖЕЛЕЗА (НЕ ПРОВЕРЕНО)
| Компонент | Статус | Как проверить |
|-----------|--------|---------------|
| Wi-Fi (BCM43602) | ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО | `lspci -nn -d 14e4:` → выбор по HARDWARE_DECISION_TREE.md |
| Аудио (Cirrus) | ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО | `speaker-test -c 2` → тишина = нужен macbook12-audio-driver |
| Bluetooth | ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО | `btmgmt info` → нет контроллера = нужен AUR драйвер |
| applespi (KB/TP) | ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО | 3 стратегии, лимит 3 попытки → иначе "НЕ ПОДДЕРЖИВАЕТСЯ" |
| Термика/питание | ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО | `tlp-stat -c`, `sensors`, `cpupower frequency-info` |
| Визуал (HiDPI 2304×1440) | ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО | Фракционное масштабирование, рендеринг темы |

---

## 🔑 КЛЮЧЕВЫЕ РЕШЕНИЯ (без пользователя, зафиксированы в DECISIONS.md)
1. **Модель:** MacBook10,1 (Mid 2017) — явно, не предположение
2. **Ядро:** linux-zen (интерактивность на fanless Core M)
3. **Загрузка:** UEFI-only systemd-boot (нет BIOS/CSM на A1534; grub удалён из ISO)
4. **ФС:** btrfs + субволюмы + zstd (снапшоты, экономия SSD)
5. **Swap:** zram (нет диск swap — SSD распаян)
6. **Питание:** TLP ONLY (thermald/ananicy удалены; powertop только read-only)
7. **Визуал:** Mavericks (OS X 10.9) скеоморфизм на Xfce/GTK3 (минимум оверхеда)
8. **Браузер:** Firefox ESR + uBlock (Epiphany исключён из ISO)

---

## 📁 СТРУКТУРА ПРОЕКТА
```
macbook12-macos-linux/
├── archiso-profile/releng/     # Профиль archiso (ISO собирается отсюда)
│   └── packages.x86_64         # Полный desktop; local pkgs: mavericks-apps + mavericks-theme
│                               # (собрать scripts/build-local-pkgs.sh → подключить [mavericks] repo)
├── packages/                   # Локальные PKGBUILD (все repo-local, без network fetch)
│   ├── mavericks-apps/         # Кастомные apps (mv-settings/about/activity/...)
│   ├── mavericks-theme/        # GTK3/иконки/plank/курсоры (SCSS → sassc, проверено)
│   ├── epiphany-mavericks-theme/ # DEFERRED (Firefox ESR — браузер системы)
│   └── macbook12-audio-driver/ # Cirrus audio (апстрим leifliddy, HW validation)
├── scripts/                    # build-local-pkgs.sh, apply-hardware-selection.sh, install/
├── tools/diagnostics/          # mv-collect/mv-power/mv-suspend-test/mv-thermal (read-only)
├── tools/experiments/          # mv-experiment runner (E1-E12, E-MC skippy-xd)
├── configs/                    # desktop/firefox/profiles (baseline + experiments)
├── docs/
│   ├── HARDWARE.md             # Железо + конфиг базовой системы
│   ├── DECISIONS.md            # Архитектурные решения
│   ├── PROGRESS.md             # Чеклист фаз
│   ├── NEEDS_HARDWARE_TEST.md  # Что проверить на железе
│   ├── HARDWARE_DECISION_TREE.md # Алгоритм выбора драйверов
│   ├── APPS.md                 # App surface inventory + статусы
│   └── HANDOFF.md              # Этот файл
└── out/                        # Собранные ISO (в .gitignore)
```

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ (агент продолжает без пауз)
1. ISO пересобрана с аудит-fixes: mv-spotlight, enhanced filechooser theming, rofi theme fixes.
   QEMU+OVMF smoke-test пройден. NOPASSWD sudo разблокировано.
2. На железе: проверить Mavericks тему, E-MC apply (skippy-xd), Super+Space/mv-spotlight,
   Quick Look, HiDPI 2304×1440, filechooser theming.
3. P0 coherence: Finder (PARTIALLY - no Space binding), Spotlight (PARTIALLY - mv-spotlight),
   Launchpad (PARTIALLY - no pagination/folders), MC (EXPERIMENT READY - skippy-xd E-MC).
   Filechooser theming enhanced. Остаток P0/P1 — HW-валидация (NEEDS_HARDWARE_TEST.md).
4. APPS.md статусы скорректированы: никаких fake IMPLEMENTED.
5. Обновить HANDOFF.md по итогам следующей итерации.

**Никаких пауз "до железа".** Всё доводится до "ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО".