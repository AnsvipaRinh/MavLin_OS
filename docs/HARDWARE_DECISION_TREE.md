# HARDWARE_DECISION_TREE.md — Чеклист выбора драйверов на реальном железе

> **Инструкция:** При первой загрузке на MacBook10,1 выполни команды ниже по порядку. Результат каждого пункта однозначно определяет, какой вариант драйвера выбрать. Никаких уточняющих вопросов — только сверка логов.

---

## 1. Подтверждение модели
```bash
dmidecode -s system-product-name
```
- **MacBook10,1** → продолжай ниже
- **MacBook9,1** или **MacBook8,1** → STOP. Обнови docs/HARDWARE.md, пересобери ISO с драйверами для этой ревизии.

---

## 2. Wi-Fi: Broadcom BCM43602
```bash
lspci -nn -d 14e4:
```
### Вариант А (приоритетный для MacBook10,1): `broadcom-wl-dkms`
- **Признак в логе:** `14e4:43ba` (или `14e4:43a3` rev 03+) — требует проприетарный `wl`
- **Действие:** Установи `broadcom-wl-dkms` (AUR), добавь в `MODULES=(wl)` в mkinitcpio, пересобери initramfs
- **Файл конфига:** `/etc/modprobe.d/99-mavericks.conf` уже имеет `blacklist brcmfmac brcmsmac b43 b43legacy ssb bcma`

### Вариант Б (fallback): `brcmfmac` (in-kernel)
- **Признак в логе:** `14e4:43ba` rev 01/02 — работает с in-kernel драйвером
- **Действие:** Раскомментируй `brcmfmac` в modprobe.d, установи `linux-firmware-broadcom` (если нужен), убери `broadcom-wl-dkms`
- **Проверка:** `dmesg | grep brcmfmac` — должен найти прошивку и подключиться к AP

### Вариант В (редко): `b43` / `b43legacy`
- **Признак:** старый чип BCM43xx (не BCM43602)
- **Действие:** `pacman -S b43-fwcutter`, извлеки прошивку, загрузи `b43`

---

## 3. Аудио: Cirrus Logic CS42L83 (или ревизия для MacBook10,1)
```bash
dmesg | grep -i -e cirrus -e cs42l83 -e snd_hda
cat /proc/asound/cards
```
### Вариант А: `macbook12-audio-driver` (github.com/leifliddy/macbook12-audio-driver)
- **Признак:** встроенные динамики не работают, только наушники; `dmesg` показывает `snd_hda_codec_cirrus` но нет звука
- **Действие:** Установи PKGBUILD из `packages/macbook12-audio-driver/`, пересобери initramfs (драйвер встроен в модуль ядра)
- **Проверка:** `speaker-test -c 2` — звук из встроенных колонок

### Вариант Б: in-kernel `snd_hda_codec_cirrus` (если патч уже в ядре 6.6+)
- **Признак:** звук работает из коробки
- **Действие:** Ничего не делай, удали PKGBUILD из автоустановки

---

## 4. Bluetooth
```bash
dmesg | grep -i bluetooth
btmgmt info
```
### Вариант А: `macbook12-bluetooth-driver` (AUR)
- **Признак:** контроллер не поднимается, `btmgmt` не видит адаптер
- **Действие:** Установи AUR пакет, включи `bluetooth.service`

### Вариант Б: in-kernel `btusb` + firmware
- **Признак:** контроллер виден, `hci0` поднимается
- **Действие:** Только `pacman -S bluez bluez-utils`, включи `bluetooth.service`

---

## 5. Клавиатура/Трекпад (applespi) — BEST EFFORT, ЛИМИТ 3 СТРАТЕГИИ
```bash
dmesg | grep -i applespi
ls /sys/bus/spi/devices/
```
### Стратегия 1: `macbook12-spi-driver-dkms` (AUR) на linux-zen
- **Признак:** `applespi` загружается, но `spi_pxa2xx_platform` таймаутится (ошибки `spi_master_xfer` timeout)
- **Действие:** Установи AUR пакет, добавь `applespi` в mkinitcpio MODULES, пересобери initramfs
- **Лимит попыток:** 1 сборка. Если не заводится → сразу Стратегия 2.

### Стратегия 2: `linux-macbook` kernel (github.com/marcosfad/macbook12-spi-driver) с патчами
- **Признак:** Стратегия 1 провалилась; ядро 6.6+ имеет улучшенную поддержку applespi
- **Действие:** Собери кастомное ядро `linux-macbook` (PKGBUILD в `packages/linux-macbook/`) с патчами applespi, замени `linux-zen` в загрузчике
- **Лимит попыток:** 1 сборка ядра. Если не заводится → Стратегия 3.

### Стратегия 3: `linux-lts` + backport applespi patches
- **Признак:** Стратегии 1 и 2 провалились
- **Действие:** Установи `linux-lts`, примени backport патчи applespi от 6.10+ к 6.6 LTS, пересобери
- **Результат:** Если не заводится → **ПОМЕТИТЬ В PROGRESS.md: "applespi: НЕ ПОДДЕРЖИВАЕТСЯ НА ЭТОЙ РЕВИЗИИ"**, используй внешний USB-C ввод навсегда.

---

## 6. Питание/Термика
```bash
sensors
cat /sys/class/power_supply/BAT0/capacity
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
```
- **TLP:** уже настроен (`/etc/tlp.d/99-mavericks.conf`). Проверь `tlp-stat -c` — governor powersave, boost=0
- **thermald:** если есть `/etc/thermald/thermal-conf.xml` для MacBook10,1 — включи. Иначе работает в авторежиме.
- **intel_pstate / HWP:** проверь `cpupower frequency-info` — должен показывать `intel_pstate` с HWP enabled.

---

## 7. Итоговая таблица принятия решений

| Компонент | Команда проверки | Если вижу X → Действие |
|-----------|------------------|------------------------|
| Wi-Fi | `lspci -nn -d 14e4:` | `14e4:43ba rev 03+` → `broadcom-wl-dkms`; `rev 01/02` → `brcmfmac` |
| Аудио | `speaker-test -c 2` | Тишина из колонок → `macbook12-audio-driver` |
| Bluetooth | `btmgmt info` | No controller found → `macbook12-bluetooth-driver` |
| applespi | `dmesg \| grep applespi` | Timeout errors → Стратегия 1 → 2 → 3 → "НЕ ПОДДЕРЖИВАЕТСЯ" |
| CPU governor | `cpupower frequency-info` | Не powersave → поправить TLP конфиг |

---

## Автоматизация (после ручной проверки)
Создай скрипт `scripts/apply-hardware-selection.sh`, который принимает результаты проверок и:
1. Устанавливает нужные пакеты (pacman/yay)
2. Обновляет `/etc/modprobe.d/99-mavericks.conf`
3. Пересобирает initramfs (`mkinitcpio -P`)
4. Обновляет загрузчик (`bootctl update`)
5. Перезагружает

**Цель:** После первой ручной проверки на железе — одна команда и система полностью настроена под конкретную ревизию.