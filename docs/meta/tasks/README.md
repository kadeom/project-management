# Задачи

Одна задача — одна ветка. Задача самодостаточна: цель, границы, шаги, критерии
приёмки, проверка и откат.

## Связь с реестром

- Пункт появляется в [`../../../BACKLOG.md`](../../../BACKLOG.md).
- ID не переиспользуется. Формат: `T-NNN`.
- Спецификация создаётся при переходе в статус `now`:
  `docs/meta/tasks/T-NNN.md`.
- Шаблон — [`TASK_TEMPLATE.md`](TASK_TEMPLATE.md).
- `done` удаляется из backlog при выпуске, запись идёт в `CHANGELOG.md`.

## История ID

Старые комментарии в коде ссылаются на короткие ID. Они сохранены, чтобы не
терять контекст решений.

| ID | Тема | Статус | Где видно |
|---|---|---|---|
| T-007 | SSOT путей и имён артефактов | done | `src/pm/paths.py` |
| T-008 | Версия пакета и зависимости | done | `tests/test_pm.py` |
| T-009 | Детерминизм XML, `SaveVersion=14` | done | `src/pm/msproject.py` |
| T-034 | UTF-8 консоль и LF в выводе | done | `build.py` |
| T-036 | `ruff` и `bandit` без стилевого шума | done | `pyproject.toml` |
| S-005 | Потолок Python из-за JPype1 | accepted | `docs/reference/version-matrix.md` |
| S-011 | `.docx` сравнивается по zip, не побайтово | accepted | `tests/test_pm.py` |

## Текущие задачи

Новые ID начинаются с `T-037`. Список — в `BACKLOG.md`.

## Источники

- https://basecamp.com/shapeup
- https://www.conventionalcommits.org/en/v1.0.0/
