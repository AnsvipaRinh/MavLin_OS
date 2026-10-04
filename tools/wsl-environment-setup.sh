#!/usr/bin/env bash
# ============================================================================
# wsl-environment-setup.sh
#
# Готовит новый WSL2-дистрибутив под задачу: "сборка кастомного Arch-based
# Linux ISO для MacBook 12" (2015-2017), заточенного под слабый Core M и
# оформленного под skeuomorphic macOS Mavericks (10.9)".
#
# ВАЖНО: этот скрипт рассчитан на то, что WSL-дистрибутив — ARCH LINUX,
# а не Ubuntu/Debian. Инструменты сборки ISO (archiso, mkarchiso, pacstrap,
# devtools) — нативно арчевые, на Ubuntu их пришлось бы городить через
# Docker/chroot, это лишний слой боли для агента.
#
# Если у тебя ещё нет Arch-дистрибутива в WSL — на Windows сначала:
#   wsl --install archlinux
# (доступен как готовый образ в Microsoft Store / через wsl --list --online)
# Потом зайди в него и запусти этот скрипт от обычного пользователя с sudo.
# ============================================================================

set -euo pipefail

echo "== 1. Базовые пакеты для сборки ISO и разработки =="
pacman -Syu --noconfirm --needed \
    base-devel git archiso arch-install-scripts devtools \
    qemu-full ovmf edk2-ovmf \
    reflector rsync wget curl unzip \
    linux-headers dkms \
    python python-pip \
    man-db man-pages \
    tmux htop ripgrep fd bat

echo "== 2. systemd в WSL2 (нужен для нормальной работы archiso/mkarchiso и dkms) =="
if [ ! -f /etc/wsl.conf ] || ! grep -q "systemd=true" /etc/wsl.conf 2>/dev/null; then
  tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true

[interop]
appendWindowsPath = false
EOF
  echo ">> /etc/wsl.conf обновлён. Нужно перезапустить дистрибутив:"
  echo "   в PowerShell/Windows Terminal: wsl --shutdown, затем открыть заново."
fi

echo "== 3. AUR-хелпер (yay) — понадобится для macbook12-*-driver пакетов =="
if ! command -v yay &> /dev/null; then
  tmpdir=$(mktemp -d)
  git clone https://aur.archlinux.org/yay-bin.git "$tmpdir/yay-bin"
  (cd "$tmpdir/yay-bin" && makepkg -si --noconfirm --skipcheck)
  rm -rf "$tmpdir"
fi

echo "== 4. Структура проекта =="
PROJECT_ROOT="$HOME/projects/MavLinOS"
mkdir -p "$PROJECT_ROOT"/{archiso-profile,packages,drivers,theme,scripts,docs,logs}
cd "$PROJECT_ROOT"

if [ ! -d .git ]; then
  git init
  cat > .gitignore <<'EOF'
*.iso
*.img
work/
out/
*.log
EOF
  git add .gitignore
  git commit -m "chore: init project skeleton"
fi

echo "== 5. Стартовый профиль archiso (releng как база) =="
if [ ! -d "$PROJECT_ROOT/archiso-profile/releng" ]; then
  cp -r /usr/share/archiso/configs/releng "$PROJECT_ROOT/archiso-profile/"
fi

echo "== 6. Заготовки под драйверы этого конкретного макбука =="
cat > "$PROJECT_ROOT/drivers/README.md" <<'EOF'
# Драйверы под MacBook 12" (A1534)

Известные компоненты (AUR/GitHub), специфичные именно для этой модели:

- macbook12-spi-driver-dkms (AUR)  — клавиатура + Force Touch трекпад (SPI).
  СТАТУС НЕСТАБИЛЕН на новых ядрах (таймауты SPI на ядрах 6.15+, сообщения
  на форуме Arch за июнь 2025). Планировать fallback на внешнюю
  USB/USB-C клавиатуру и мышь как обязательный сценарий, а не запасной.
- macbook12-audio-driver (github.com/leifliddy/macbook12-audio-driver)
  — патч для кодека Cirrus, без него не работают встроенные динамики
  (наушники по джеку работают и без патча).
- macbook12-bluetooth-driver (AUR)
- Wi-Fi: Broadcom BCM43602 — модуль brcmfmac (в ядре) или broadcom-wl-dkms,
  в зависимости от точной ревизии карты — определяется по lspci.
- Webcam (FaceTime HD): проект facetimehd (патентованная прошивка +
  модуль ядра) — низкий приоритет, если камера не критична.

Агенту: перед началом работы с драйверами определить ТОЧНУЮ модель
(MacBook8,1 / 9,1 / 10,1 — год 2015/2016/2017) по системному идентификатору
доставшегося железа — компоненты и фиксы отличаются между ревизиями.
EOF

git add -A
git commit -m "chore: project structure, archiso base profile, driver notes" || true

echo ""
echo "=============================================================="
echo "Готово. Проект: $PROJECT_ROOT"
echo "Дальше: положи AGENTS.md (второй файл) в корень проекта и"
echo "запускай агента оттуда, указав ему сразу читать docs/ и drivers/."
echo "=============================================================="
