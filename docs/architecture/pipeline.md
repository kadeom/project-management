# Конвейер данных

## Вход

`project.yaml` содержит метаданные, календарь, ресурсы, коды структуры и фазы с
задачами. Формат описан в [`schemas/README.md`](../../schemas/README.md).

## Шаги

```text
project.yaml
  → model.load()             Project: задачи, WBS, связи, ресурсы
  → cpm.schedule()           ранние/поздние сроки, резервы
  → cpm.costs()              стоимость по ставкам A/B
  → analysis.*               PERT, перегрузки, сценарии, сводки
  → msproject.build()        объекты MPXJ + MSPDIWriter
  → report.blocks()          Markdown и .docx из одного набора блоков
  → out/                     артефакты по манифесту
```

## Дополнительное задание

Тот же пакет, другой вход и отчёт:

```text
additional-assignment/<variant>/project.yaml
  → model.load()            + currency.apply_fx по блоку fx
  → cpm / analysis
  → report_infosec.blocks()     Markdown и .docx практической работы
  → build_infosec.py            документы, XML, .mpp, скриншоты v12_*/v10_*
```

Валютный слой работает только при наличии блока `fx`. Курс хранится в YAML,
поэтому сборка остаётся офлайн.

## Параллельность

`build.py` поднимает JVM в главном потоке, затем запускает генерацию XML в
фоновом потоке. Расчёты и отчёт пишутся параллельно. JVM нельзя стартовать из
worker-потока: JPype не потокобезопасен при инициализации.

## Детерминизм

- Версии MPXJ и JPype1 закреплены точно.
- GUID кодов структуры строятся из стабильной строки, а не случайно.
- JSON и Markdown пишутся с `newline="\n"`.
- Время в `.docx` не сравнивается побайтово: тест сравнивает содержимое zip-частей.

## Проверки

| Проверка | Где |
|---|---|
| инварианты модели | `tests/test_pm.py` |
| покрытие требований ЛР | `tests/test_pm.py` |
| XML ↔ MPXJ | `tests/test_pm.py` |
| детерминизм | `tests/test_pm.py` |
| ссылки в `project.yaml`, `out/` | `tests/test_pm.py` |
| Markdown-ссылки | `scripts/checks/docs-paths.sh` |
| блоки и снимки ДЗ | `tests/test_infosec.py` |
| курсы и пересчёт | `tests/test_currency.py` |

## Отказы

| Симптом | Причина | Действие |
|---|---|---|
| `JVMNotFoundException` | нет Java | поставить JRE 8+ или `--no-xml` |
| XML не открывается | неверный формат | открыть `02_full_safe.xml` |
| COM-шаг упал | нет MS Project | ручной путь из `guides/checklist.md` |
| Нет `.mpp` | клон без бинарей | импортировать XML и сохранить как `.mpp` |

## Источники

- https://mpxj.org/
- https://learn.microsoft.com/en-us/office/client-developer/project/
