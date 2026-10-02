# ENVIRONMENT — build-контейнер: доступ и учётные данные

> Persistent state: как любой агент получает root в этом окружении.
> Обновлять, если образ контейнера пересобран или доступ изменился.

## Факты (проверено 2026-09-25)

- Пользователь: `builder` (uid 1000, группы `builder`, `wheel`). Пароля у
  `builder` НЕТ (`passwd -S builder` → `NP`) — пользователь пароли не
  назначал, это исходное состояние образа.
- `sudo` изначально требовал пароль (`sudo -n true` → fail), принять можно
  было **пустой пароль** (`printf '\n' | sudo -S true` → success).
- Docker-socket нет, capabilities нет (CapEff=0), единственный путь
  повышения — sudo/su через пароль.

## Что назначено (2026-09-25, по поручению пользователя)

Никакие пароли НЕ создавались и НЕ записывались — вместо этого убран сам
вопрос пароля для повседневной работы:

- В `/etc/sudoers` строка `builder ALL=(ALL) ALL` заменена на
  `builder ALL=(ALL) NOPASSWD: ALL` (`visudo -c` OK).
- Проверка после `sudo -K`: `sudo -n true` → success. Этого достаточно для
  `mkarchiso`, `pacstrap`, QEMU/KVM-тестов и всех скриптов репозитория.

## Ловушки (зафиксировано кровью)

1. Drop-in в `/etc/sudoers.d/` НЕ сработал: в конце `/etc/sudoers` ПОСЛЕ
   `@includedir` есть явная строка `builder ALL=(ALL) ALL` (и
   `<build-user-2> ALL=(ALL) ALL`) — действует последнее совпадение (last match wins),
   она перебивала NOPASSWD. Править надо сам `/etc/sudoers`.
2. `sudo -n true` сразу после `sudo -S ...` врет: timestamp закэширован,
   проверять только после `sudo -K`.
3. Пустой пароль builder (`printf '\n' | sudo -S ...`) работает и остался
   запасным путём, если NOPASSWD-строка потеряется при пересборке образа.

## Правила

1. Пароли root/builder НЕ назначать без явного поручения; хранить
   пароли в git (включая этот репозиторий) ЗАПРЕЩЕНО — они попадут
   в историю и, возможно, в публичный remote.
2. Если образ пересобран и `sudo -n true` снова падает — повторить:
   `printf '\n' | sudo -S true` (пустой пароль), затем проверить конец
   `/etc/sudoers` на строку `builder ALL=(ALL) ALL` и заменить её на
   NOPASSWD-вариант (drop-in НЕ поможет — см. ловушку 1). Если пустой
   пароль не подошёл — доступ потерян, это genuine blocker: запросить
   у владельца хоста `root` или пересоздание контейнера с NOPASSWD.
3. NOPASSWD здесь — осознанно: локальный одно-пользовательский
   build-контейнер (практика как у EC2/GitHub runners), не продакшен-хост.

## Быстрая проверка для нового агента

```
whoami; sudo -n true && echo ROOT-OK || echo ROOT-BLOCKED
```

## Ловушки build-окружения (mkarchiso)

4. `/tmp` — tmpfs 3.8G. mkarchiso workdir (`-w`) и локальный pacman-репо
   туда НЕ помещаются (только linux-zen-headers рвёт лимит): workdir —
   `/home/user/archiso-work` (на диске 940G+), репо собирается в
   `/home/user/mavericks-repo`, а `/tmp/mavericks-repo` — symlink
   на него (pacman.conf committed на `file:///tmp/mavericks-repo`;
   symlink слетает при ребуте — пересоздать). Остаток /tmp чистить sudo.
5. Остатки mkarchiso root-owned: `rm -rf` workdir только через sudo.
