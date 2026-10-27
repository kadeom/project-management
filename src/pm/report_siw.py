"""Отчёт по самостоятельной работе студента (СРС) из siw/siw.yaml.

СРС — это дополнительные задания к ЛР1–9: отдельные учебные файлы, типы
задач, профили загрузки, СДР, таблицы ставок, выравнивание, PERT и сценарии
сокращения критического пути. Текст заданий живёт в ``siw/siw.yaml``; числа
(сроки, стоимость, состав плана) берутся из ``project.yaml``, чтобы отчёт не
расходился с лабораторной частью.

Скриншоты не вставляются здесь: в документе остаются метки
``[ Вставьте скриншот siw_lrN_KK: … ]``. Их заполняет ``automation.fill_report``
после прогона ВМ-агента, как и метки лабораторного отчёта.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import analysis as a
from .md_docx import render_docx, render_markdown
from .model import Project


def load(path: str | Path) -> dict:
    """Прочитать siw.yaml и проверить обязательные поля."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "meta" not in data or "sections" not in data:
        raise ValueError("siw.yaml: нужны блоки meta и sections")
    seen: set[str] = set()
    for section in data["sections"]:
        for task in section.get("tasks", []):
            for key in ("id", "title", "what", "artifact", "criteria"):
                if not task.get(key):
                    raise ValueError(f"siw.yaml: у задания {task.get('id', '?')} нет поля {key}")
            if task["id"] in seen:
                raise ValueError(f"siw.yaml: повторяется id {task['id']}")
            seen.add(task["id"])
    return data


def blocks(project: Project, data: dict) -> list[tuple]:
    """Собрать блоки СРС в формате md_docx."""
    B: list[tuple] = []
    meta = data["meta"]
    finish = a.finish_of(project)
    phases = sum(t.summary for t in project.tasks)
    leaves = project.leaf_tasks
    works = [t for t in leaves if not t.milestone]
    milestones = [t for t in leaves if t.milestone]
    total = a.cost_summary(project)[1]

    B += [
        ("h", 1, "1. Назначение и состав работы"),
        ("p", meta.get("intro", "").strip()),
        ("p", f"Проект: «{project.meta['name']}» ({project.meta.get('short', '')}). "
              f"Плановый срок: {project.start:%d.%m.%Y} — {finish:%d.%m.%Y}; "
              f"фаз — {phases}, работ — {len(works)}, вех — {len(milestones)}, "
              f"ресурсов — {len(project.resources)}. Стоимость по таблице A — "
              f"{a.money(total)}."),
        ("p", f"Источник заданий — файл `{Path('siw/siw.yaml')}`. Он же связан с "
              "генератором `build_siw.py`: правьте YAML, а не готовый .docx."),
        ("h", 2, "1.1. Что сдаётся"),
        ("ul", [
            "отчёт `out/siw-report.docx` с выполненными заданиями и скриншотами;",
            "отдельные `.mpp` для учебных файлов и промежуточных состояний плана;",
            "скриншоты `automation/results/shots/siw_lrN_KK.png`;",
            "устные ответы по контрольным вопросам каждого задания.",
        ]),
        ("h", 2, "1.2. Как выполнять"),
        ("ol", [
            "Соберите базовый план: `python build.py`.",
            "Откройте XML или .mpp в MS Project и выполняйте задания по порядку.",
            "Сохраняйте промежуточные файлы под именами `siw_*`; не перезаписывайте базовый план.",
            "Снимайте экран в моменты, указанные в задании; ID снимка — `siw_lrN_KK`.",
            "Соберите отчёт: `python build_siw.py`, затем вставьте снимки "
            "`python -m automation.fill_report --src out/siw-report.docx --dst out/siw-report-final.docx`.",
        ]),
    ]

    # Карта заданий
    B += [("h", 1, "2. Карта заданий СРС"),
          ("table", ["ЛР", "Задание", "Артефакт", "Критерий"],
           [[f"ЛР{s['lab']}", t["title"], t["artifact"], t["criteria"]]
            for s in data["sections"] for t in s.get("tasks", [])])]

    # Содержание по лабораторным
    for section in data["sections"]:
        B += [("pagebreak",), ("h", 1, section["title"]),
              ("p", f"Цель: {section.get('goal', '')}")]
        for task in section.get("tasks", []):
            B += [("h", 2, task["title"]),
                  ("p", task["what"].strip())]
            if task.get("steps"):
                B += [("p", "Порядок выполнения:"), ("ol", task["steps"])]
            B += [("p", f"Артефакт: {task['artifact']}"),
                  ("p", f"Критерий приёмки: {task['criteria']}")]
            for shot in task.get("shots", []):
                B.append(("shot", f"[ Вставьте скриншот {shot}: {task['title']} ]"))

    # Самопроверка и источники
    B += [("pagebreak",), ("h", 1, "3. Самопроверка перед сдачей"),
          ("ul", [f"{s['lab']}.{i}: {t['criteria']}"
                  for s in data["sections"] for i, t in enumerate(s.get("tasks", []), start=1)]),
          ("h", 1, "4. Источники"),
          ("ul", [
              "ГОСТ Р 54869-2011. Проектный менеджмент. Требования к управлению проектом.",
              "ГОСТ Р 59793-2021. Автоматизированные системы. Стадии создания.",
              "ГОСТ Р ИСО 21500-2023. Управление проектами, программами и портфелями проектов.",
              "Методические указания по дисциплине «Управление проектами» (файл "
              "`docs/guidelines/methodical-guidelines.md`).",
              "Документация Microsoft Project: настраиваемые поля, таблицы норм затрат, "
              "выравнивание загрузки, повторяющиеся задачи.",
          ])]
    return B


def markdown(project: Project, data: dict) -> str:
    """Отрендерить СРС в Markdown (для вычитки без Word)."""
    return render_markdown(blocks(project, data))


def docx(project: Project, data: dict, path: str | Path) -> Path:
    """Отрендерить СРС в .docx с титульным листом и оглавлением."""
    meta = dict(data["meta"])
    meta.setdefault("organization", project.meta.get("company", "Учебный проект"))
    return render_docx(blocks(project, data), path, meta=meta, title_page=True, toc=True)
