# AGENTS

Инструкции для агентов, работающих с этим репозиторием.

## Обзор

Учебный тулкит для лабораторных работ по управлению проектами. Единственный
источник данных — `project.yaml`. Остальное генерируется в `out/`:

- XML MSPDI для MS Project;
- `expected.json` и `analysis.md` с расчётами;
- отчёт `.docx`.

Репозиторий не является runtime агентной системы. Шаблон `agent-harness`
используется только как образец структуры и документации.

## Команды

```bash
pip install -r requirements.txt     # Python 3.10–3.14, Java 8+ для MPXJ
python build.py                     # все артефакты в out/
python build.py --no-xml            # только расчёты и отчёт, без Java
python build_infosec.py --no-xml    # два документа дополнительного задания
python -m pytest tests -q           # тесты
ruff check src/pm automation tests build_infosec.py scripts additional-assignment  # линт
./scripts/check.sh                  # единая проверка (линк + тесты + линт)
```

Windows + MS Project, полный конвейер:

```bash
pip install '.[automation]'
python build.py --full
```

## Правила

- Меняйте `project.yaml`, а не файлы в `out/`. `out/` — результат сборки.
- Пути и имена артефактов берите из `src/pm/paths.py`. Не дублируйте литералы.
- Сборка должна оставаться детерминированной: два прогона дают одинаковый `out/`.
- Расчёты `src/pm/cpm.py` независимы от MPXJ. XML проверяется через планировщик MPXJ.
- Windows-автоматизация не должна ломать кроссплатформенную сборку.
- Не добавляйте зависимость без записи в `pyproject.toml` и `requirements.txt`.
- Не коммитьте секреты, реальные персональные данные и локальные пути.
- Коммиты — Conventional Commits, английский, до 72 символов в заголовке.
- Задачи — `BACKLOG.md`, решения — `docs/architecture/adr/`.

## Структура

```text
src/pm/              пакет расчётов и генераторов (report_infosec, currency)
tests/               pytest
scripts/             конвертация XML→MPP, курсы валют, проверки
build_infosec.py     сборка двух вариантов дополнительного задания
additional-assignment/  модели и отчёты вариантов 10/12
automation/          Windows COM/UIA (скриншоты, вставка в отчёт)
docs/                архитектура, ADR, руководства, справочники
schemas/             контракт данных (README)
examples/            примеры формата project.yaml
out/                 сгенерированные артефакты (закоммичены)
```

## Документация

Вход — [`docs/README.md`](docs/README.md). Архитектура — [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Источники

- https://agents.md/
- https://opencode.ai/docs/rules/
- https://www.conventionalcommits.org/en/v1.0.0/
