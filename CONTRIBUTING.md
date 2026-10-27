# Как внести изменение

## Ошибки и предложения

- Дефект — через форму «Дефект»: шаги, ожидаемое, фактическое.
- Задача — через форму «Задача»: цель, границы, критерии приёмки.
- Незапланированная работа сначала попадает в [`BACKLOG.md`](BACKLOG.md).

## Ветки

- `main` — стабильная ветка, артефакты в `out/` актуальны.
- `task/T-NNN-short-name` — одна задача.
- `fix/short-name` — дефект без задачи.
- `docs/short-name` — только документация.

## Коммиты

Conventional Commits, английский язык:

```
type(scope): imperative summary
```

Заголовок — до 72 символов. Тело — What / Why / How to verify. Footer —
`Refs: T-037 | ADR-0002`. Шаблон — [`.gitmessage`](.gitmessage).

Типы: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`,
`chore`, `revert`.

## Проверка перед коммитом

```bash
python build.py --no-xml            # быстро, без Java
python build_siw.py                 # СРС (SIW)
python build_guidelines.py          # методические указания
python build_artifacts.py           # паспорт проекта
python -m pytest tests -q
ruff check src/pm automation tests build_infosec.py scripts additional-assignment
./scripts/check.sh                  # ссылки + pytest + ruff
```

Если меняли XML-генерацию, запустите полную сборку с Java и проверьте diff
`out/`. Для дополнительного задания — `python build_infosec.py --no-xml`. Если меняли `.docx`, откройте отчёт и проверьте таблицы.

## Правила кода

- Python 3.10+, `from __future__ import annotations`.
- Данные — только из `project.yaml`; пути — только из `src/pm/paths.py`.
- Комментарий объясняет «почему», а не «что».
- Ошибка должна говорить, что делать. Пример — сообщение про JVM.
- Новый артефакт добавляется в `MANIFEST` и в README.
- Windows-код не импортируется на Linux без условия.

## Правила текста

- Одно действие — одно предложение.
- Активный залог, настоящее время.
- Один термин — одно значение.
- Аббревиатура расшифровывается при первом употреблении.
- Ссылка на источник обязательна для внешних утверждений.
- Без рекламных прилагательных и общих выводов.

## Pull request

В описании: что изменено, зачем, как проверить, какие артефакты пересобраны.
Шаблон — [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).

## Источники

- https://www.conventionalcommits.org/en/v1.0.0/
- https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors
- https://developers.google.com/style
