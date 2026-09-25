# HANDOFF.md — Сводка состояния (для чтения за 1 минуту)

**Дата:** 2026-09-25
**Готовность к железу:** Phase 0 — DONE (smoke-test в QEMU пройден)

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
- **Питание:** TLP (powersave, boost=0), thermald, ananicy-cpp — включены и настроены

### Phase 2 — Оптимизация (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- zram, ananicy-cpp, урезанные systemd units, journald volatile — всё в ISO

### Phase 3 — Визуал (ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО)
- GTK3 тема Mavericks (скеоморфизм: текстуры, тени, стекло, градиенты)
- Иконки pre-flat стиль
- Dock: plank с рефлексией/зумом
- Панель: xfce4-panel как menu bar
- Thunar как Finder (боковая панель, Mavericks-иконки папок)
- xfce4-settings как System Preferences (сетка иконок)
- Браузер: Epiphany/GNOME Web + тема Safari 7 (Top Sites, компас, unified toolbar)

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
3. **Загрузка:** UEFI-only systemd-boot (нет BIOS/CSM на A1534)
4. **ФС:** btrfs + субволюмы + zstd (снапшоты, экономия SSD)
5. **Swap:** zram (нет диск swap — SSD распаян)
6. **Питание:** TLP + thermald + ananicy-cpp (fanless = термика критична)
7. **Визуал:** Mavericks (OS X 10.9) скеоморфизм на Xfce/GTK3 (минимум оверхеда)
8. **Браузер:** Epiphany (WebKit) + Safari 7 тема (ближе к нативному рендерингу, легче Firefox)

---

## 📁 СТРУКТУРА ПРОЕКТА
```
macbook12-macos-linux/
├── archiso-profile/releng/     # Профиль archiso (ISO собирается отсюда)
├── packages/                   # PKGBUILD для нестандартных пакетов
│   ├── macbook12-audio-driver/
│   ├── linux-macbook/          # кастомное ядро для Стратегии 2 applespi
│   └── mavericks-theme/        # GTK3/иконки/планк тема
├── theme/                      # Исходники темы (SVG, CSS, assets)
├── scripts/                    # Утилиты (apply-hardware-selection.sh и др.)
├── docs/
│   ├── HARDWARE.md             # Железо + конфиг базовой системы
│   ├── DECISIONS.md            # Архитектурные решения
│   ├── PROGRESS.md             # Чеклист фаз
│   ├── NEEDS_HARDWARE_TEST.md  # Что проверить на железе
│   ├── HARDWARE_DECISION_TREE.md # Алгоритм выбора драйверов
│   └── HANDOFF.md              # Этот файл
└── out/                        # Собранные ISO (в .gitignore)
```

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ (агент продолжает без пауз)
1. Собрать PKGBUILD для `macbook12-audio-driver` в `packages/`
2. Собрать PKGBUILD для `mavericks-theme` (GTK3, icons, plank, cursors)
3. Собрать PKGBUILD для `epiphany-mavericks-theme` (Safari 7 стиль)
4. Создать `scripts/apply-hardware-selection.sh` для автоматизации пост-установки
5. Добавить все пакеты в `packages.x86_64` и пересобрать ISO
6. Обновить HANDOFF.md по итогам недели

**Никаких пауз "до железа".** Всё доводится до "ПОДГОТОВЛЕНО, НЕ ПРОВЕРЕНО".