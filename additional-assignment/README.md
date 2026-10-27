# Дополнительное задание

Практическая работа по дисциплине «Управление проектами в информационной
безопасности». Два варианта используют общий пакет `src/pm`:

| Каталог | Вариант | Система | XML в `out/` |
|---|---|---|---|
| [`01-pam/`](01-pam/) | 12 | PAM | `infosec_v12_full.xml` |
| [`02-dlp-siem/`](02-dlp-siem/) | 10 | DLP + SIEM | `infosec_v10_full.xml` |

В каждом каталоге лежат:

- `project.yaml` — модель проекта, смета, риски и тексты заданий;
- `additional-assignment-variant-*.md` — читаемая версия отчёта;
- `additional-assignment-variant-*.docx` — документ для сдачи;
- `additional-assignment-variant-*-with-screenshots.docx` — версия после `--full`.

## Сборка

```bash
pip install -r requirements.txt          # PyYAML, python-docx, MPXJ, JPype1
python build_infosec.py --no-xml        # только .md и .docx
python build_infosec.py                 # + XML в out/ (нужна Java)
python build_infosec.py --full          # + .mpp, 10 скриншотов, вставка в .docx
```

`--full` работает только на Windows с установленным MS Project. Подробный порядок —
[`docs/guides/additional-assignment.md`](../docs/guides/additional-assignment.md).

## Расчёты

- Сроки, критический путь и перегрузки — `src/pm/cpm.py` и `src/pm/analysis.py`.
- Смета в базовой валюте (сом) с импортными позициями в USD — `src/pm/currency.py`.
- Курс хранится в блоке `fx` и не запрашивается при сборке. Обновить вручную:
  `python scripts/fx_rate.py`.
- Документ собирает `src/pm/report_infosec.py`, оркестратор — `build_infosec.py`.
- Скриншоты: `v12_01`…`v12_05`, `v10_01`…`v10_05`; шаги — `infosec_shot_steps`
  в `automation/ms_project_ui.py`.

## Источники

- [`docs/reference/infosec/standards.md`](../docs/reference/infosec/standards.md) — нормативные документы.
- [`docs/reference/infosec/prices.md`](../docs/reference/infosec/prices.md) — цены и допущения сметы.
- [`docs/reference/infosec/habr.md`](../docs/reference/infosec/habr.md) — статьи для обоснований.
- Методички: [`infosec-assignment-guidelines.docx`](../infosec-assignment-guidelines.docx).

## Jira

Эксперимент с регистрацией в Jira лежит отдельно:
[`03-jira/`](03-jira/README.md). Он не входит в сборку и не
запускается в CI: нужны Playwright, браузер и внешний сервис.

## Безопасность

- Токены и профиль браузера не коммитятся: см. `.gitignore`.
- Адрес почты задаётся переменной `JIRA_SIGNUP_EMAIL`, не хранится в коде.
- `project.yaml` и `.docx` не содержат реальных персональных данных.
