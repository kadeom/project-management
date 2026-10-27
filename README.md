# Проект: Организация научно-практической конференции (CONF-2026)

Учебный репозиторий для лабораторных работ по дисциплине «Управление проектами»
(моделирование в MS Project). Данные проекта и автоматизация полностью обезличены
и не содержат ничего специфичного для исходного домена.

## Тема проекта

Организация научно-практической конференции «Кыргызская Республика: вызовы и
перспективы цифровизации» (CONF-2026). Проект включает инициацию, работу
программного комитета, логистику, подготовку материалов, регистрацию участников
и проведение конференции.

## Содержимое репозитория

| Путь | Назначение | Отвечает за |
|------|-----------|-------------|
| `project.yaml` | Единый источник данных проекта: задачи, связи, ресурсы, коды работ, календарь | Все ЛР: здесь задаётся модель, из которой строятся все артефакты |
| `build.py` | Сборщик артефактов (XML MS Project, expected.json, analysis.md, отчёт .docx) | Воспроизводимая генерация результатов |
| `src/pm/` | Пакет расчётов (CPM, MS Project XML, анализ, отчёт) | Ядро автоматизации |
| `src/pm/model.py` | Загрузка и типизация `project.yaml` | Контроль схемы данных |
| `src/pm/cpm.py` | Критический путь (CPM), перегрузки, стоимости | ЛР6, ЛР7, ЛР5 (стоимость) |
| `src/pm/msproject.py` | Генерация и чтение XML MSPDI (через MPXJ/Java) | ЛР1-2, ЛР3-7, ЛР9 (импорт/экспорт) |
| `src/pm/analysis.py` | PERT, сценарии сокращения, сводка по фазам/кодам | ЛР8, аналитическая часть отчёта |
| `src/pm/report.py` | Генерация отчёта .docx (шаблон + таблицы) | Итоговый отчёт по ЛР |
| `src/pm/report_siw.py` | Генерация отчёта СРС (SIW) из `siw/siw.yaml` | Дополнительные задания к ЛР1–9 |
| `src/pm/md_docx.py` | Markdown → .docx для методичек и шаблонов | Методические указания, документы |
| `src/pm/paths.py` | SSOT путей и имён артефактов (манитест `out/`) | Согласованность всех скриптов |
| `src/pm/currency.py` | Курсы НБКР/ЦБ РФ, пересчёт USD→KGS | Смета дополнительного задания |
| `src/pm/report_infosec.py` | Отчёт по дополнительному заданию (PAM, DLP+SIEM) | Практическая работа |
| `build_infosec.py` | Сборка двух вариантов ДЗ: `.md`, `.docx`, XML, скриншоты | Дополнительное задание |
| `build_siw.py` | Сборка отчёта СРС (SIW) из `siw/siw.yaml` | Дополнительные задания к ЛР |
| `build_guidelines.py` | Сборка методических указаний из Markdown | `out/methodical-guidelines.docx` |
| `build_artifacts.py` | Сборка паспорта проекта из Markdown | `out/project-artifacts.docx` |
| `build_all.py` | Оркестратор: ЛР + СРС + ДЗ + методички + паспорт | Весь комплект одной командой |
| `additional-assignment/` | Модели, отчёты, методички и эксперимент Jira | Варианты 10 и 12 |
| `siw/` | Задания СРС (SIW) в YAML | Дополнительные задания |
| `docs/artifacts/` | Шаблоны устава, реестра рисков, RACI и др. | Управленческие документы |
| `vm/` | Windows-ВМ: прогон, сверка, сдача, checksums | Автоматизация MS Project |
| `scripts/xml_to_mpp.py` | Конвертация XML→`.mpp` через COM-автоматизацию MS Project (Windows + MS Project) | Готовые `.mpp` для студентов |
| `automation/ms_project_ui.py` | UI-автоматизация MS Project (COM + UIA): скриншоты 22 шагов ЛР1–9 | Автозаполнение отчёта |
| `automation/fill_report.py` | Вставка PNG-скриншотов в `.docx`-отчёт по меткам `labN_KK` | Готовый отчёт для сдачи |
| `tests/` | Автотесты модели, ЛР, XML, ссылок, ДЗ и валют | Самопроверка перед сдачей |
| `docs/` | Архитектура, ADR, чек-лист, справочники | Документация и решения |
| `schemas/`, `examples/` | Схема и примеры `project.yaml` | Формат данных |
| `scripts/check.sh` | Ссылки, `ruff`, `pytest` одной командой | Локальная проверка и CI |
| `requirements.txt`, `pyproject.toml` | Зависимости (pyyaml, mpxj, JPype1, python-docx, pytest) | Воспроизводимое окружение |
| `project-management-guidelines.docx` | Методические указания (источник требований к ЛР и защите) | Официальный источник формулировок |

## Как связаны файлы

```
project.yaml ──► src/pm/model.py (загрузка)
      │
      ├──► src/pm/cpm.py (CPM, перегрузки, стоимости)
      │         │
      │         ├──► src/pm/msproject.py (XML MSPDI) ──► out/*.xml
      │         │
      │         └──► src/pm/analysis.py (PERT, сценарии) ──► out/analysis.md, out/expected.json
      │
      └──► src/pm/report.py (отчёт .docx) ──► out/ms-project-labs-report.docx

build.py ──► вызывает все модули ──► out/ (см. src/pm/paths.py::MANIFEST)
build_siw.py ──► siw/siw.yaml + project.yaml ──► out/siw-report.docx, out/siw-report.md
build_guidelines.py ──► docs/guidelines/methodical-guidelines.md ──► out/methodical-guidelines.docx
build_infosec.py ──► два варианта ДЗ ──► out/infosec_v12_full.xml, out/infosec_v10_full.xml
tests/ ──► проверяют model, cpm, analysis, msproject, report, paths, СРС, методички, ДЗ, валюты, ссылки
```

## Термины

- **CONF-2026** — идентификатор учебного проекта.
- **Зарплата (оплата труда)** — считается из таблицы ставок ресурсов в `project.yaml`:
  поле `rate` (ставка, ₽/час) × часы задачи × доля назначения.
  Таблица B (ставки с датой действия) задаётся полем `rate_b` и `rate_change` — применяется
  автоматически при расчёте стоимости после указанной даты.
- **Стоимость задачи** — сумма по всем ресурсам + `fixed_cost` (фикс. затраты) + `per_use`
  (затраты за единицу использования, например, аренда зала).
- **Перегрузка (overallocation)** — когда суммарная загрузка ресурса в период превышает
  его доступность (`availability`). Требуется ≥3 перегрузок для ЛР6-7.
- **Критический путь** — цепочка задач с нулевым запасом (slack), определяющая длительность проекта.
- **Веха (milestone)** — задача с нулевой длительностью, отмечающая событие.
- **Ограничение (constraint)** — ограничение типа «начать не ранее» (SNET), «завершить не позже» (FNET) и т.д.
- **Запаздывание (lag)** — пауза между связями (например, «НН+1» — следующий рабочий день +1).

## Как защищать ЛР

Защита каждой лабораторной работы строится по схеме методических указаний
(`project-management-guidelines.docx`). Общий порядок:

1. **Показать артефакт** — открыть соответствующий файл из `out/` (XML в MS Project,
   analysis.md, expected.json, отчёт .docx).
2. **Обосновать решения** — объяснить, почему выбраны такие длительности, связи,
   ресурсы, ограничения (ссылаться на `project.yaml` и методичку).
3. **Продемонстрировать расчёты** — показать критический путь, перегрузки, стоимость,
   PERT-оценки (вывод из `expected.json` или `analysis.md`).
4. **Ответить на вопросы** — см. чек-лист ниже.

### Чек-лист защиты по ЛР

- **ЛР1-2** (создание проекта, задачи, связи, вехи, календарь): открыть `01_plan_lab1-2.xml`
  в MS Project, показать Ганта, таблицу связей, календарь проекта и исключения.
- **ЛР3** (ресурсы): показать таблицу ресурсов (work/material/cost), доступность PM (50%),
  назначения, перегрузки (включить фильтр «Перегруженные»).
- **ЛР4** (примечания и ссылки): показать задачи с примечаниями (`note`) и гиперссылками
  (`link`) в поле «Примечание» или «Информация».
- **ЛР5** (стоимость): показать таблицу ставок (A/B), фикс. затраты (зала — 50 000 ₽),
  пересчёт при дате действия таблицы B.
- **ЛР6** (перегрузки, выравнивание): показать перегруженные ресурсы (PM, MET, BE),
  применить выравнивание (ручное или автоматическое), сравнить сроки до/после.
- **ЛР7** (оптимизация): показать критический путь, попробовать сократить длительность
  критических задач, оценить влияние на стоимость.
- **ЛР8** (PERT): показать три оценки (о/м/п), распределение, вероятность завершения
  к заданной дате (в `analysis.md`).
- **ЛР9** (структура/отчёт): показать WBS, коды работ (`code`), выгрузку в MS Project,
  итоговый отчёт `.docx`.

### Официальные источники

- Методические указания: `project-management-guidelines.docx` (Стамкулова Г.К., Кыргызский
  государственный технический университет им. И. Раззакова, Бишкек, 2021).
- Формат обмена MS Project: MSPDI (Microsoft Project Data Interchange), XML-схема
  поддерживается MS Project 2010/2013/2016/365 (SaveVersion=14).
- PERT-анализ: метод оценки и анализа программ (Program Evaluation and Review Technique),
  три оценки (оптимистическая, наиболее вероятная, пессимистическая).

## Быстрый старт

```bash
pip install -r requirements.txt          # Python 3.10-3.14 + Java 8+ для MPXJ
python build.py                          # сборка всех артефактов в out/
python -m pytest tests -q                # самопроверка
python build.py --no-xml                 # без Java: только expected.json, analysis.md, отчёт
python build_infosec.py --no-xml        # два документа дополнительного задания
```

Полный конвейер одним прогоном (Windows + установленный MS Project):

```bash
pip install '.[automation]'              # pywin32, pywinauto, psutil, pillow
python build.py --full                   # XML‖расчёты (параллельно) → .mpp → 22 скриншота
                                         #   → вставка в отчёт → out/ms-project-labs-report.docx
```

`--full` перезаписывает шаблон отчёта готовым файлом со скриншотами (22/22 `labN_KK`).

Дополнительное задание собирается отдельно:

```bash
python build_infosec.py --no-xml        # .md и .docx обоих вариантов
python build_infosec.py                 # + XML в out/ (Java)
python build_infosec.py --full          # + .mpp и 10 скриншотов (Windows + MS Project)
```

Подробнее — [`docs/guides/additional-assignment.md`](docs/guides/additional-assignment.md).
Без MS Project используйте `python build.py` + ручные скриншоты ([docs/guides/checklist.md](docs/guides/checklist.md)).

### Весь комплект одной командой

```bash
python build_all.py              # ЛР + СРС + ДЗ + методички без Java
python build_all.py --xml        # + XML MSPDI (Java 8+)
python build_all.py --full       # + .mpp и скриншоты (Windows + MS Project)
```

### СРС (SIW)

Самостоятельная работа студента — дополнительные задания к ЛР1–9. Задания
лежат в [`siw/siw.yaml`](siw/siw.yaml), отчёт собирается из `project.yaml`:

```bash
python build_siw.py              # out/siw-report.md + out/siw-report.docx
```

В именах файлов и ID снимков используется английское сокращение **SIW**
(student independent work); в русском тексте — «СРС». Скриншоты `siw_lrN_KK`
вставляются тем же `automation.fill_report`, что и лабораторные.

### Методические указания

Исходник — [`docs/guidelines/methodical-guidelines.md`](docs/guidelines/methodical-guidelines.md)
(заголовки, таблицы, списки и front matter). Готовый `.docx` не правят руками:

```bash
python build_guidelines.py       # out/methodical-guidelines.docx
```

Методичка покрывает ЛР1–9, СРС (SIW), два дополнительных задания 10/12,
управленческие артефакты и критерии оценивания.

### Управленческие артефакты

Шаблоны устава, реестра заинтересованных сторон, словаря СДР, RACI, реестра
рисков, планов качества и коммуникаций, журнала изменений, отчётов о статусе
и завершении — в [`docs/artifacts/templates/`](docs/artifacts/templates/).

Заполненный пример для CONF-2026 собирается в один `.docx`:

```bash
python build_artifacts.py        # out/project-artifacts.docx
```

Источник — [`docs/artifacts/example-conference-2026.md`](docs/artifacts/example-conference-2026.md).
Это документы для адаптации, а не автогенерация управленческих решений:
часть полей нужно заменить на данные своего проекта.

### Windows-ВМ

Скрипты для машины с MS Project — в [`vm/`](vm/): полный прогон с watchdog,
сверка `verify.json`, папка сдачи, checksums и снимок окружения без PII.
Инструкция — [`vm/VM_AGENT.md`](vm/VM_AGENT.md).

Готовые `.mpp` (проприетарный бинарь MS Project) уже лежат в `out/` — открывайте их
напрямую в MS Project, без импорта XML. Если нужно пересобрать `.mpp` после изменения
`project.yaml` (Windows + установленный MS Project):

```bash
pip install pywin32
python scripts/xml_to_mpp.py             # out/*.xml → out/*.mpp через COM
```

## Автоскриншоты отчёта (Windows + MS Project)

Вместо ручных скриншотов ([docs/guides/checklist.md](docs/guides/checklist.md)) можно автоматизировать все 22 шага ЛР1–9.
Стек: Python 3.10–3.14, pywin32 (COM), pywinauto (UIA), Pillow (захват окна),
python-docx (вставка в отчёт); нужен установленный MS Project 2016/365 (русский
интерфейс) — модель данных берётся из `out/*.xml`/`out/*.mpp`.

```bash
pip install '.[automation]'                          # pywin32, pywinauto, psutil, pillow
python build.py --full                               # весь конвейер одним прогоном
# или по шагам:
py -m automation.ms_project_ui shots                 # 22 PNG → automation/results/shots/
py -m automation.fill_report --dst out/ms-project-labs-report.docx
```

`build.py --full` внутри себя: XML‖расчёты (параллельно, JVM в фоновом потоке) →
`scripts/xml_to_mpp.py` → `automation.ms_project_ui shots` → `automation.fill_report`.
COM-шаги последовательны (один WINPROJ.exe на машине); параллельна только
Python-часть сборки (JVM ‖ расчёты).

ID снимков (`lab1_01` … `lab9_03`) совпадают с метками в `out/ms-project-labs-report.docx`
(источник — `src/pm/report.py::shots`). Каждый шаг изолирован: упавший не роняет прогон,
журнал — `automation/results/run_log.json`. Для диагностики/человеческой подстраховки
оставьте ручной путь из [docs/guides/checklist.md](docs/guides/checklist.md): оба способа дополняют друг друга, не конфликтуют.

## Рекомендуемые LSP

Для разработки на Python в этом репо:

- **basedpyright** — строгая типизация (аналог pyright с дополнительными правилами);
  ставится один раз `pip install basedpyright` (или `npm i -g basedpyright`).
- **ruff** — линт/форматирование, уже в `dev`-зависимостях (`ruff>=0.9`).

Автопроверка перед коммитом/PR — `.github/workflows/ci.yml` (ruff, pytest). В opencode
LSP поднимается автоматически, если установлен; для ручной проверки типов вне CI:

```bash
basedpyright                                # или pyright, если он уже в PATH
ruff check src/pm automation tests
```


## Документация

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — архитектура и границы.
- [`docs/README.md`](docs/README.md) — вход в документацию.
- [`docs/architecture/adr/`](docs/architecture/adr/README.md) — принятые решения.
- [`docs/guides/checklist.md`](docs/guides/checklist.md) — ручные шаги ЛР1–ЛР9.
- [`docs/guides/additional-assignment.md`](docs/guides/additional-assignment.md) — дополнительное задание.
- [`additional-assignment/README.md`](additional-assignment/README.md) — варианты 10/12.
- [`docs/reference/infosec/README.md`](docs/reference/infosec/README.md) — источники и цены ДЗ.
- [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) — правила работы.
- [`BACKLOG.md`](BACKLOG.md), [`ROADMAP.md`](ROADMAP.md) — планы.

## Лицензия

Образовательный репозиторий. Код и данные — учебные примеры.
