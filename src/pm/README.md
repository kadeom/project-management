# Пакет `pm`

Пакет не знает о CLI. `build.py` загружает модель, вызывает расчёты и рендеры.

| Модуль | Роль | Зависимости |
|---|---|---|
| [`model.py`](model.py) | разбор `project.yaml`, `Project`, `Task`, `Resource` | PyYAML |
| [`cpm.py`](cpm.py) | календарь, CPM, резервы, перегрузки, стоимость | стандартная библиотека |
| [`msproject.py`](msproject.py) | MSPDI XML через MPXJ, чтение обратно | MPXJ, JPype |
| [`analysis.py`](analysis.py) | PERT, сценарии сокращения, сводки | `cpm`, `model` |
| [`report.py`](report.py) | блоки отчёта, Markdown, `.docx` | python-docx |
| [`paths.py`](paths.py) | пути, имена, `MANIFEST` | стандартная библиотека |
| [`currency.py`](currency.py) | курсы НБКР/ЦБ РФ, пересчёт валют сметы | стандартная библиотека |
| [`report_infosec.py`](report_infosec.py) | отчёт дополнительного задания (PAM, DLP+SIEM) | `analysis`, `currency`, PyYAML, python-docx |

## Инварианты

- `project.yaml` — единственный источник данных.
- `model.load()` строит задачи в порядке WBS: фаза, затем её задачи.
- `cpm` не импортирует `msproject`: расчёт работает без JVM.
- `currency` применяет `fx` один раз; повторный вызов не меняет суммы.
- `report.blocks()` — единственный источник текста отчёта.
- `paths.py` — единственный источник имён артефактов.

## Добавление модуля

1. Опишите ответственность и границы в docstring.
2. Не добавляйте путь-литерал: используйте `paths`.
3. Добавьте тест в `tests/test_pm.py`.
4. Обновите [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md).
