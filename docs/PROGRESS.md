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
