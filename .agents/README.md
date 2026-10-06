# .agents/ — заявки (claims) агентов

Протокол: `docs/COORDINATION.md`.

Один claim = один файл `.agents/claims/<id>.md`.
id = `YYYYMMDD-HHMM-<agent>-<slug>`, например `20261006-1500-grok-airdrop-hotkey`.
Файл создаёт только владелец claim и только он его удаляет (поэтому записи не конфликтуют между агентами).

```
agent: grok            # grok | gpt | opencode:<oid> | claude | human
task: короткая фраза, что делаешь
paths: packages/**/mv_hotkeys_core*, docs/KEYBOARD.md
expires: 2026-10-06T21:00Z
```

- `paths` — glob через запятую; `*` совпадает и с `/`.
- `expires` — UTC, не позже 6 часов от создания. Продлить можно, отредактировав собственный claim.
- Истёк или удалён — путь свободен. Просроченные claims CI показывает и просит удалить.
- В коммит или PR добавь строку `Claim: <id>`: так CI понимает, что правка в заявленных путях сделана владельцем.
- Защищённые файлы перечислены в `.agents/protected.txt` (по одному glob на строку, строки с `#` — комментарии).
