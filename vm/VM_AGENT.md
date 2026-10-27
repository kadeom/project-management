# Агент на Windows-ВМ с MS Project

Этот файл — готовое задание для агента, который запускает полный прогон на
Windows с установленным Microsoft Project 365 (русский интерфейс). Все
артефакты обезличены: в репозитории нет реальных студентов, организаций,
почты, токенов и коммерческих данных.

## 1. Что установить

```powershell
git pull
py -m pip install -r requirements.txt
py -m pip install -r requirements-vm.txt
```

Проверка:

```powershell
py -c "import win32com.client, psutil, pywinauto, docx; print('ok')"
powershell -NoProfile -ExecutionPolicy Bypass -File vm\collect_env.ps1
```

`vm\collect_env.ps1` пишет `automation/results/windows-env-pins.txt` — только
версии, без имён пользователей, компьютеров, IP и токенов.

## 2. Полный прогон

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File vm\run_all.ps1
```

Шаги:

1. `build_all.py` — отчёты ЛР, СРС (SIW), ДЗ 10/12 и методические указания.
2. `scripts/xml_to_mpp.py` — XML → `.mpp` (MS Project COM).
3. `automation.ms_project_ui shots` — 22 снимка ЛР.
4. `vm/verify.py` — сверка с `out/expected.json`.
5. `automation.fill_report` — вставка снимков в лабораторный отчёт и отчёт SIW.
6. `vm/make_submission.py` — папка `automation/results/submission/`.
7. `vm/hash_artifacts.py` — `checksums.sha256`.
8. `git` — коммит, если не указан `-NoGit`.

Полезные ключи:

```powershell
# не коммитить
powershell -File vm\run_all.ps1 -NoGit

# пересобрать XML (нужна Java 8+)
powershell -File vm\run_all.ps1 -Xml

# убить зависший WINPROJ перед стартом
powershell -File vm\run_all.ps1 -KillStale

# считать расхождения verify ошибкой
powershell -File vm\run_all.ps1 -Strict
```

## 3. Что должно получиться

| Путь | Что это |
|---|---|
| `out/*.xml` | MSPDI-планы ЛР и ДЗ |
| `out/*.mpp` | те же планы в формате MS Project |
| `out/ms-project-labs-report.docx` | отчёт ЛР (шаблон) |
| `out/siw-report.docx` | отчёт СРС (SIW) |
| `out/methodical-guidelines.docx` | методические указания |
| `out/project-artifacts.docx` | паспорт проекта: устав, риски, RACI и др. |
| `automation/results/shots/lab*.png` | снимки ЛР |
| `automation/results/shots/siw_*.png` | снимки СРС, если сняты |
| `automation/results/verify.json` | сверка с MS Project |
| `automation/results/submission/` | папка сдачи |
| `automation/results/checksums.sha256` | хеши `.mpp` |

## 4. Если шаг упал

- Не обходите сверку и не подгоняйте числа: истина — MS Project.
- Смотрите `automation/results/run_log.json` (если есть) и вывод шага.
- Для расхождений данных заполните `automation/results/NOTES.md`: что
  расходится, на сколько, почему, что считать верным.
- Если `WINPROJ.exe` завис на модальном окне — закройте процесс и повторите
  с `-KillStale`; не запускайте два прогона одновременно.
- Если XML не открывается, проверьте `out/02_full_safe.xml` (без настраиваемых
  полей) и настройки «Устаревшие форматы» в MS Project.

## 5. Ограничения

- COM-автоматизация Office не поддерживается Microsoft в unattended-режиме:
  нужна интерактивная сессия залогиненного пользователя.
- `.mpp` создаёт только MS Project; на Linux остаются XML и `.docx`.
- Скриншоты СРС (`siw_*`) снимаются отдельными шагами; если их нет,
  `fill_report` оставит метки в отчёте — это не ошибка сборки.

## 6. Что нельзя коммитить

- реальные имена, почту, телефоны, логины, токены, IP и имена компьютеров;
- содержимое старых приватных проектов и скриншоты с реальными данными;
- `automation/results/**` (каталог в `.gitignore`), кроме случаев, когда
  руководитель явно просит приложить готовую поставку.
