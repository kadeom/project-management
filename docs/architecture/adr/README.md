# ADR

| ID | Решение | Статус |
|---|---|---|
| [0001](0001-yaml-ssot.md) | `project.yaml` — единственный источник данных | accepted |
| [0002](0002-run-from-source.md) | Запуск из исходников через `src/` в `sys.path` | accepted |
| [0003](0003-deterministic-artifacts.md) | Детерминированная сборка и `MANIFEST` | accepted |
| [0004](0004-committed-binaries.md) | `.mpp` и `out/` закоммичены | accepted |
| [0005](0005-additional-assignment.md) | Дополнительное задание переиспользует `pm` | accepted |

## Формат

Один файл — одно решение. Имя: `NNNN-kebab-case.md`. Статусы: `proposed`,
`accepted`, `deprecated`, `superseded`. Решение не редактируется после
принятия: новое решение ссылается на старое.

Шаблон — [0000-template.md](0000-template.md).

## Источники

- https://adr.github.io/
- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
