# Дополнительное задание: пошагово

Практическая работа по внедрению СЗИ (система защиты информации, information security)
для вариантов 12 (PAM) и 10 (DLP + SIEM).
Модели лежат в [`additional-assignment/`](../../additional-assignment/README.md).

## 1. Подготовка

```bash
pip install -r requirements.txt     # Python 3.10+, Java 8+ для XML
```

Для `--full` дополнительно:

```bash
pip install '.[automation]'        # Windows, pywin32, pywinauto, Pillow
```

## 2. Сборка документов

```bash
python build_infosec.py --no-xml
```

Результат в каждом варианте:

- `additional-assignment-variant-*.md` — для чтения и ревью;
- `additional-assignment-variant-*.docx` — для сдачи.

Markdown пересобирается из тех же блоков, что и `.docx`. Числа берутся из
`project.yaml` и расчётов, а не вводятся в текст вручную.

## 3. Сборка XML

```bash
python build_infosec.py
```

Появятся `out/infosec_v12_full.xml` и `out/infosec_v10_full.xml`. Имена заданы в
`src/pm/paths.py`.

## 4. Скриншоты и `.mpp`

```bash
python build_infosec.py --full
```

Шаги:

1. `scripts/xml_to_mpp.py` — XML → `.mpp`.
2. `automation.ms_project_ui shots --only v12_01,...,v10_05` — 10 PNG.
3. `automation.fill_report` — вставка PNG в документы.

Если MS Project нет, используйте XML и ручные скриншоты. ID снимков стабильны:
`v12_01`…`v12_05`, `v10_01`…`v10_05`.

## 5. Проверка

```bash
python -m pytest tests -q
ruff check src/pm automation tests build_infosec.py scripts
./scripts/check.sh docs
```

Тесты проверяют блоки отчёта, ID снимков, `.docx`, формулы валют и идемпотентность
пересчёта.

## 6. Что менять

| Нужно | Где |
|---|---|
| задачи, ресурсы, сроки | `additional-assignment/<variant>/project.yaml` |
| тексты заданий и риски | блок `report:` в том же YAML |
| цены и обоснование | блок `cost_basis:` и `docs/reference/infosec/prices.md` |
| курс валют | блок `fx:` через `python scripts/fx_rate.py` |
| оформление отчёта | `src/pm/report_infosec.py` |

## 7. Ограничения

- Сеть при сборке не нужна: курс уже записан в `fx`.
- `--full` не входит в CI: нужен Windows и MS Project.
- Jira — отдельный эксперимент, см.
  [`additional-assignment/03-jira/README.md`](../../additional-assignment/03-jira/README.md).
