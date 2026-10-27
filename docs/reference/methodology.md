# Методичка и требования

Источник формулировок — `project-management-guidelines.docx` в корне репозитория:
Стамкулова Г.К., «Управление проектами», Кыргызский государственный технический
университет им. И. Раззакова, Бишкек, 2021.

## Покрытие лабораторных работ

| ЛР | Тема | Артефакт | Проверка |
|---|---|---|---|
| 1–2 | проект, задачи, связи, вехи, календарь | `01_plan_lab1-2.xml` | `test_lab_requirements_covered` |
| 3 | ресурсы, доступность, назначения | `02_full_lab3-7_9.xml` | те же + XML |
| 4 | примечания и гиперссылки | XML, `analysis.md` | `test_xml_hyperlinks_*` |
| 5 | стоимость, ставки A/B | `expected.json` | `test_costs_*` |
| 6–7 | перегрузки, критический путь | `analysis.md` | `test_overallocation_*` |
| 8 | PERT | `03/04_*.xml` | `test_pert_*` |
| 9 | WBS, коды, отчёт | `.docx`, XML | `test_lab_requirements_covered` |
| ДЗ 10/12 | PAM, DLP+SIEM, смета в KGS | `additional-assignment/` | `tests/test_infosec.py`, `tests/test_currency.py` |

## Форматы обмена

- MSPDI XML, `SaveVersion=14` (MS Project 2010/2013/2016/365).
- `.mpp` — родной бинарь, создаётся MS Project.
- Отчёт — Office Open XML (`.docx`).

## Источники

- https://learn.microsoft.com/en-us/office/client-developer/project/
- https://mpxj.org/
