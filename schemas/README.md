# Схемы данных

| Файл | Что описывает | Статус |
|---|---|---|
| [`project.schema.json`](project.schema.json) | структура `project.yaml` | справочная |

## Источник истины

Исполняемая проверка — `src/pm/model.py` и `tests/test_pm.py`. JSON Schema нужна
редактору и ревьюеру: она показывает поля, типы и обязательность. Если правила
разойдутся, права модель: тесты важнее схемы.

`project.yaml` начинается с директивы `yaml-language-server`, поэтому VS Code с
расширением YAML подхватывает схему автоматически.

## Проверка вручную

```bash
python -c "
import json, yaml
schema = json.load(open('schemas/project.schema.json'))
data = yaml.safe_load(open('project.yaml'))
assert data['project']['short'] == 'CONF-2026'
print('schema ok')
"
```

Полная валидация по JSON Schema запланирована в `BACKLOG.md`.

## Источники

- https://json-schema.org/
- https://yaml.org/
